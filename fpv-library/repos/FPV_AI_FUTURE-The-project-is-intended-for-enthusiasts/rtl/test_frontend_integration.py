"""RTL INTEGRATION co-sim: the detect front-end blocks COMPOSED on one frame (M0 capstone).

The per-block co-sims prove each PL brick vs its Python counterpart in isolation. This test proves
they *compose*: one thermal frame is pushed through the real Verilog chain

    [bt656_rx.v] -> morph_tophat.v -> hist.v -> [PS threshold stats] -> ccl.v -> centroid_dp.v

with each stage's RTL output fed as the next stage's input, and the final centroid is asserted
bit-exact against the same chain computed in Python (`fpv.seeker.detect`). This is the PL analog of
`fpga/ps/seeker_backend` (which composed LOS/IMM/guidance on the PS): it catches interface/format
mismatches between blocks that the isolated per-block tests cannot. Skips cleanly if iverilog absent.

Two entry points:
  * ``test_frontend_chain_matches_python`` — a uint16 (14-bit-sim) patch straight into the detector.
  * ``test_frontend_chain_from_bt656`` — starts one stage earlier: an 8-bit frame (the FT640 CVBS
    reality) is encoded to a BT.656 byte stream, recovered by ``bt656_rx.v``, then run through the
    same chain — full ingest→centroid.

The PL/PS split is preserved: bt656 + tophat + histogram + connected-components + centroid run in
Verilog; the once-per-frame threshold STATS are the PS step (here the Python reference, proven == the
C ``threshold_stats.cpp`` elsewhere).
"""

from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from fpv.seeker.detect import (
    _STRUCT_ELEM,
    _SE_DIAMETER_PX,
    _compute_threshold,
    _connected_components,
    _white_tophat,
)

# Reuse the existing per-block iverilog harnesses (no duplicate plumbing).
from fpga.rtl.test_morph_tophat import _run_rtl as run_tophat, _synth_patch, _W, _H
from fpga.rtl.test_hist_rtl import _run_hist as run_hist, _NBINS
from fpga.rtl.test_ccl_rtl import _run_ccl as run_ccl
from fpga.rtl.test_centroid_dp_rtl import _run_rtl as run_centroid, _F
from fpga.rtl.test_bt656_rx import _encode_bt656, _run_rx

_IVERILOG = shutil.which("iverilog")
_VVP = shutil.which("vvp")
_CXX = shutil.which("clang++") or shutil.which("g++")
_PS_DIR = Path(__file__).resolve().parents[1] / "ps"     # fpga/ps -> threshold_stats.cpp (the PS block)
_R = int(_SE_DIAMETER_PX) // 2          # 5
_MARGIN = 2 * _R                        # tophat interior margin (border uncomputed by the RTL)


def _c_threshold_from_hist(cbin: Path, hist: dict[int, int], tmp_path: Path) -> float:
    """Feed the RTL histogram to the PS threshold_stats binary and parse its threshold."""
    hf = tmp_path / "hist_chain.txt"
    hf.write_text("".join(f"{b} {int(c)}\n" for b, c in sorted(hist.items()) if c))
    out = subprocess.run([str(cbin), str(hf)], check=True, capture_output=True, text=True)
    return float(out.stdout.split()[0])


def _assert_chain(frame: np.ndarray, tmp_path, center: tuple[float, float]) -> tuple[float, float, int, int]:
    """Run one frame through the composed RTL chain and assert it == the Python detect chain.

    Returns (cx_px, cy_px, n_components, den). Bit-exact on tophat / histogram / CCL grouping /
    fixed-point centroid.
    """
    lo, hi = _MARGIN, _H - 1 - _MARGIN

    # Python golden: the SAME data flow, restricted to the tophat interior.
    th_ref = _white_tophat(frame.astype(np.float32), _STRUCT_ELEM)
    interior_ref = np.clip(np.rint(np.array(
        [th_ref[y, x] for y in range(lo, hi + 1) for x in range(lo, hi + 1)])).astype(np.int64),
        0, _NBINS - 1)
    thr_py, _, _ = _compute_threshold(interior_ref.astype(np.float64))

    # Stage 1: RTL top-hat.
    th_rtl = run_tophat(frame, tmp_path)
    assert len(th_rtl) == (hi - lo + 1) ** 2
    assert not [(y, x) for y in range(lo, hi + 1) for x in range(lo, hi + 1)
                if th_rtl[(y, x)] != int(round(float(th_ref[y, x])))], "stage1 tophat mismatch"

    # Stage 2: RTL histogram of the RTL top-hat interior.
    rtl_interior = np.clip(np.array(
        [th_rtl[(y, x)] for y in range(lo, hi + 1) for x in range(lo, hi + 1)], dtype=np.int64),
        0, _NBINS - 1)
    hist_rtl = run_hist(rtl_interior, tmp_path)
    expected_hist = np.bincount(rtl_interior, minlength=_NBINS)
    assert not [b for b in range(_NBINS) if hist_rtl.get(b, 0) != int(expected_hist[b])], \
        "stage2 histogram mismatch"
    assert sum(hist_rtl.values()) == rtl_interior.size

    # PS threshold stats from the RTL histogram. Prefer the real C block (threshold_stats.cpp);
    # fall back to the Python reference if no C++ compiler. Either way it must match the golden.
    if _CXX is not None:
        cbin = tmp_path / "threshold_stats"
        if not cbin.exists():
            subprocess.run([_CXX, "-O2", "-std=c++14", "-o", str(cbin),
                            str(_PS_DIR / "threshold_stats.cpp")], check=True, capture_output=True, text=True)
        thr_chain = _c_threshold_from_hist(cbin, hist_rtl, tmp_path)     # RTL hist -> PS C threshold
        assert math.isclose(thr_chain, thr_py, rel_tol=1e-6, abs_tol=1e-6), \
            f"PS C threshold {thr_chain} != python {thr_py}"
    else:
        thr_chain, _, _ = _compute_threshold(rtl_interior.astype(np.float64))
        assert thr_chain == pytest.approx(thr_py)

    # Stage 3: mask from RTL tophat + PS threshold -> RTL connected-components.
    mask = np.zeros((_H, _W), dtype=bool)
    for y in range(lo, hi + 1):
        for x in range(lo, hi + 1):
            mask[y, x] = th_rtl[(y, x)] > thr_chain
    assert mask.sum() >= 3, "expected a detectable blob in the interior"

    _num, labels, _stats = _connected_components(mask)
    py_comp: dict[int, set[int]] = {}
    for y in range(_H):
        for x in range(_W):
            if mask[y, x]:
                py_comp.setdefault(int(labels[y, x]), set()).add(y * _W + x)

    ccl_out = run_ccl(mask, tmp_path)
    rtl_comp: dict[int, set[int]] = {}
    for idx, lab in ccl_out.items():
        rtl_comp.setdefault(lab, set()).add(idx)
    assert {frozenset(s) for s in py_comp.values()} == {frozenset(s) for s in rtl_comp.values()}, \
        "stage3 CCL grouping (RTL) != Python"

    # Stage 4: dominant component -> RTL centroid datapath, bit-exact vs the fixed-point reference.
    def _weight_sum(pixels: set[int]) -> int:
        return int(sum(int(frame[p // _W, p % _W]) for p in pixels))

    target = max(rtl_comp.values(), key=_weight_sum)
    local_bg = min(int(frame[p // _W, p % _W]) for p in target)
    pixels, num_x, num_y, den = [], 0, 0, 0
    for p in sorted(target):
        x, y = p % _W, p // _W
        w = max(int(frame[y, x]) - local_bg, 0)
        pixels.append((x, y, w))
        num_x += x * w
        num_y += y * w
        den += w
    assert den > 0, "degenerate component (zero weight)"
    q_x, q_y = (num_x << _F) // den, (num_y << _F) // den

    results = run_centroid([(pixels, q_x, q_y, den)], tmp_path)
    assert len(results) == 1
    cx, cy, den_rtl = results[0]
    assert den_rtl == den, f"stage4 den {den_rtl} != {den}"
    assert cx == q_x, f"stage4 cx_fixed {cx} != {q_x}"
    assert cy == q_y, f"stage4 cy_fixed {cy} != {q_y}"

    cx_px, cy_px = cx / 2 ** _F, cy / 2 ** _F
    assert abs(cx_px - center[0]) < 2.0 and abs(cy_px - center[1]) < 2.0, \
        f"centroid ({cx_px:.2f},{cy_px:.2f}) off-target {center}"
    return cx_px, cy_px, len(rtl_comp), den


@pytest.mark.skipif(_IVERILOG is None or _VVP is None, reason="iverilog/vvp not installed")
def test_frontend_chain_matches_python(tmp_path):
    """One uint16 frame through morph_tophat->hist->threshold->ccl->centroid (RTL) == the Python chain."""
    frame = _synth_patch()                                   # 32x32, cold sky + a hot blob (+ a spot)
    cx, cy, ncomp, den = _assert_chain(frame, tmp_path, center=(16.0, 16.0))
    print(f"\n[frontend-integration:u16] tophat->hist->threshold->ccl->centroid COMPOSED == Python: "
          f"{ncomp} comp(s), centroid ({cx:.3f}, {cy:.3f}) px, den={den}, bit-exact (F={_F}).")


@pytest.mark.skipif(_IVERILOG is None or _VVP is None, reason="iverilog/vvp not installed")
def test_frontend_chain_from_bt656(tmp_path):
    """Full INGEST->centroid: an 8-bit frame (FT640 CVBS reality) encoded to BT.656, recovered by
    bt656_rx.v, then run through the composed detect chain == the Python chain."""
    rng = np.random.default_rng(7)
    yy, xx = np.mgrid[0:_H, 0:_W]
    f = 40.0 + rng.normal(0.0, 2.0, (_H, _W))
    f += 180.0 * np.exp(-((xx - 16) ** 2 + (yy - 16) ** 2) / (2 * 1.8 ** 2))     # target blob
    f += 70.0 * np.exp(-((xx - 11) ** 2 + (yy - 21) ** 2) / (2 * 1.2 ** 2))      # a dimmer spot
    frame8 = np.clip(f, 1, 254).astype(np.uint16)                                # BT.656 luma range

    # Ingest: encode -> bt656_rx.v -> recover, byte-exact.
    rows = [[int(v) for v in frame8[r]] for r in range(_H)]
    recovered = _run_rx(_encode_bt656(rows), tmp_path)
    assert recovered == rows, "bt656_rx did not recover the frame byte-exact"
    frame = np.array(recovered, dtype=np.uint16)

    cx, cy, ncomp, den = _assert_chain(frame, tmp_path, center=(16.0, 16.0))
    print(f"\n[frontend-integration:bt656] bt656_rx->tophat->hist->threshold->ccl->centroid COMPOSED "
          f"== Python: {ncomp} comp(s), centroid ({cx:.3f}, {cy:.3f}) px, den={den}, bit-exact.")
