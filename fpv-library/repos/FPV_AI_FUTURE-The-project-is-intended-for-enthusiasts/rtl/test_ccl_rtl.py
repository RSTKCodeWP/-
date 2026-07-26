"""RTL co-simulation: ccl.v vs fpv.seeker.detect._connected_components (M0, front-end labelling).

Runs a real detection mask (top-hat > threshold, with several separate blobs) through the Verilog
4-connected labeller and asserts it produces the SAME grouping as the software CCL -- identical
partition of the foreground into components, and identical per-component (left, top, width, height,
area) stats.  The label integers themselves are arbitrary and not compared.  Skips if iverilog absent.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from fpv.seeker.detect import (
    _STRUCT_ELEM,
    _compute_threshold,
    _connected_components,
    _white_tophat,
)

_W = _H = 32
_RTL_DIR = Path(__file__).parent
_IVERILOG = shutil.which("iverilog")
_VVP = shutil.which("vvp")


def _mask() -> np.ndarray:
    """A 32x32 detection mask with a few separate blobs (target + spots + a couple of hot pixels)."""
    rng = np.random.default_rng(3)
    yy, xx = np.mgrid[0:_H, 0:_W]
    f = 4096.0 + rng.normal(0.0, 12.0, (_H, _W))
    f += 1800.0 * np.exp(-((xx - 16) ** 2 + (yy - 15) ** 2) / (2 * 1.5 ** 2))   # target
    f += 1100.0 * np.exp(-((xx - 7) ** 2 + (yy - 24) ** 2) / (2 * 1.2 ** 2))    # spot 1
    f += 1000.0 * np.exp(-((xx - 25) ** 2 + (yy - 8) ** 2) / (2 * 1.1 ** 2))    # spot 2
    frame = np.clip(f, 0, 65535).astype(np.uint16)
    th = _white_tophat(frame.astype(np.float32), _STRUCT_ELEM)
    thr, _, _ = _compute_threshold(th.ravel())
    return th > thr


def _run_ccl(mask: np.ndarray, tmp_path: Path) -> dict[int, int]:
    (tmp_path / "mask.txt").write_text(
        "".join(f"{int(mask[i // _W, i % _W])}\n" for i in range(_W * _H)))
    sim = tmp_path / "sim.vvp"
    subprocess.run(
        [_IVERILOG, "-g2012", "-o", str(sim),
         str(_RTL_DIR / "ccl.v"), str(_RTL_DIR / "tb_ccl.v")],
        check=True, capture_output=True, text=True)
    proc = subprocess.run([_VVP, str(sim)], cwd=tmp_path, check=True, capture_output=True, text=True)
    out: dict[int, int] = {}
    for line in proc.stdout.splitlines():
        if line.startswith("L "):
            _, idx, lab = line.split()
            out[int(idx)] = int(lab)
    return out


def _stats_from_pixels(pixels: set[int]) -> tuple[int, int, int, int, int]:
    xs = [p % _W for p in pixels]
    ys = [p // _W for p in pixels]
    return (min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1, len(pixels))


@pytest.mark.skipif(_IVERILOG is None or _VVP is None, reason="iverilog/vvp not installed")
def test_ccl_matches_detector(tmp_path):
    """The RTL labeller yields the same components (partition + bbox/area) as _connected_components."""
    mask = _mask()
    assert mask.sum() >= 6, "need a non-trivial mask"

    num, labels, stats = _connected_components(mask)

    # Python components as pixel-sets (foreground only)
    py_comp: dict[int, set[int]] = {}
    for y in range(_H):
        for x in range(_W):
            if mask[y, x]:
                py_comp.setdefault(int(labels[y, x]), set()).add(y * _W + x)

    rtl = _run_ccl(mask, tmp_path)
    rtl_comp: dict[int, set[int]] = {}
    for idx, lab in rtl.items():
        rtl_comp.setdefault(lab, set()).add(idx)

    # (1) same partition of the foreground into components (label numbers irrelevant)
    py_sets = {frozenset(s) for s in py_comp.values()}
    rtl_sets = {frozenset(s) for s in rtl_comp.values()}
    assert py_sets == rtl_sets, (
        f"grouping differs: {len(py_sets)} py comps vs {len(rtl_sets)} rtl comps")

    # (2) identical per-component (left, top, width, height, area)
    py_stats = sorted(tuple(int(v) for v in stats[k]) for k in range(1, num))
    rtl_stats = sorted(_stats_from_pixels(s) for s in rtl_sets)
    assert rtl_stats == py_stats, f"stats differ:\n  rtl={rtl_stats}\n  py ={py_stats}"

    print(f"\n[ccl] RTL == _connected_components: {len(rtl_sets)} components, "
          f"bbox/area identical (areas={[s[4] for s in rtl_stats]})")
