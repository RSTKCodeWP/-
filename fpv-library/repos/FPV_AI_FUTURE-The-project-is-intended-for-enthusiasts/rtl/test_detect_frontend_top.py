"""RTL co-sim: detect_frontend_top.v (streaming blocks wired in RTL) == Python tophat->threshold->CCL.

Where test_frontend_integration.py chains the blocks via Python orchestration, THIS drives a single RTL
top that wires the fielded streaming blocks together (morph_tophat_stream -> th_mem buffer -> injected
PS threshold -> mask -> ccl_stream) with hardware handshakes, and asserts the resulting components equal
the software tophat->threshold->CCL chain (partition + per-component bbox/area). The threshold is the PS
step, injected via +THR. Skips cleanly if iverilog is absent.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from fpv.seeker.detect import _STRUCT_ELEM, _SE_DIAMETER_PX, _compute_threshold, _connected_components, _white_tophat

from fpga.rtl.test_morph_tophat import _synth_patch, _W, _H
from fpga.rtl.test_ccl_rtl import _stats_from_pixels

_D = int(_SE_DIAMETER_PX)
_R = _D // 2
_LO, _HI = 2 * _R, _H - 1 - 2 * _R
_RTL_DIR = Path(__file__).parent
_IVERILOG = shutil.which("iverilog")
_VVP = shutil.which("vvp")


_F = 8


def _run(frame: np.ndarray, thr_int: int, tmp_path: Path) -> tuple[dict[int, int], tuple[int, int, int]]:
    (tmp_path / "frame.hex").write_text(
        "".join(f"{int(frame[i // _W, i % _W]):04x}\n" for i in range(_W * _H)))
    (tmp_path / "se.txt").write_text(
        "".join(f"{int(b)}\n" for b in np.asarray(_STRUCT_ELEM).reshape(-1)))
    sim = tmp_path / "sim.vvp"
    subprocess.run(
        [_IVERILOG, "-g2012", "-o", str(sim),
         str(_RTL_DIR / "win_reduce.v"), str(_RTL_DIR / "morph_tophat_stream.v"),
         str(_RTL_DIR / "ccl_stream.v"), str(_RTL_DIR / "centroid_dp.v"),
         str(_RTL_DIR / "detect_frontend_top.v"), str(_RTL_DIR / "tb_detect_frontend_top.v")],
        check=True, capture_output=True, text=True)
    proc = subprocess.run([_VVP, str(sim), f"+THR={int(thr_int)}"],
                          cwd=tmp_path, check=True, capture_output=True, text=True)
    out: dict[int, int] = {}
    cent = (0, 0, 0)
    for line in proc.stdout.splitlines():
        if line.startswith("L "):
            _, idx, lab = line.split()
            out[int(idx)] = int(lab)
        elif line.startswith("CENT "):
            _, cx, cy, den = line.split()
            cent = (int(cx), int(cy), int(den))
    return out, cent


@pytest.mark.skipif(_IVERILOG is None or _VVP is None, reason="iverilog/vvp not installed")
def test_detect_frontend_top_matches_python(tmp_path):
    """The wired streaming top yields the same components as the software tophat->threshold->CCL."""
    frame = _synth_patch()
    th = _white_tophat(frame.astype(np.float32), _STRUCT_ELEM)
    interior = np.array([th[y, x] for y in range(_LO, _HI + 1) for x in range(_LO, _HI + 1)])
    thr_py, _, _ = _compute_threshold(interior.astype(np.float64))
    thr_int = int(np.floor(thr_py))                          # integer threshold injected to the RTL

    # Python golden: identical mask (th > thr_int on the interior) -> connected components.
    mask = np.zeros((_H, _W), dtype=bool)
    for y in range(_LO, _HI + 1):
        for x in range(_LO, _HI + 1):
            mask[y, x] = int(round(float(th[y, x]))) > thr_int
    num, labels, stats = _connected_components(mask)
    py_comp: dict[int, set[int]] = {}
    for y in range(_H):
        for x in range(_W):
            if mask[y, x]:
                py_comp.setdefault(int(labels[y, x]), set()).add(y * _W + x)

    rtl, rtl_cent = _run(frame, thr_int, tmp_path)
    rtl_comp: dict[int, set[int]] = {}
    for idx, lab in rtl.items():
        rtl_comp.setdefault(lab, set()).add(idx)

    assert {frozenset(s) for s in py_comp.values()} == {frozenset(s) for s in rtl_comp.values()}, \
        f"grouping differs: {len(py_comp)} py vs {len(rtl_comp)} rtl comps"
    py_stats = sorted(tuple(int(v) for v in stats[k]) for k in range(1, num))
    rtl_stats = sorted(_stats_from_pixels(s) for s in rtl_comp.values())
    assert rtl_stats == py_stats, f"stats differ:\n  rtl={rtl_stats}\n  py ={py_stats}"

    # dominant component (max area, assumed unique) -> centroid, bit-exact vs the fixed-point ref
    comps = list(py_comp.values())
    areas = [len(s) for s in comps]
    assert areas.count(max(areas)) == 1, "test frame must have a unique max-area component"
    dom = comps[int(np.argmax(areas))]
    local_bg = min(int(frame[p // _W, p % _W]) for p in dom)
    num_x = num_y = den = 0
    for p in dom:
        x, y = p % _W, p // _W
        w = max(int(frame[y, x]) - local_bg, 0)
        num_x += x * w; num_y += y * w; den += w
    q_x, q_y = (num_x << _F) // den, (num_y << _F) // den
    assert rtl_cent == (q_x, q_y, den), f"centroid differs: rtl={rtl_cent} py=({q_x},{q_y},{den})"

    cx_px, cy_px = q_x / 2 ** _F, q_y / 2 ** _F
    print(f"\n[detect_frontend_top] frame->tophat->threshold->CCL->centroid (WIRED RTL) == Python chain: "
          f"{len(rtl_comp)} comp(s), dominant centroid ({cx_px:.3f},{cy_px:.3f})px den={den}, bit-exact.")
