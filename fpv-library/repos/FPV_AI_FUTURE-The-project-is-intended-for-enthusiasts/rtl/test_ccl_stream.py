"""RTL co-sim: ccl_stream.v (single-pass streaming union-find) == _connected_components.

Streams a real detection mask through the fielded single-pass labeller and asserts the SAME grouping
as the software CCL -- identical partition of the foreground into components, and identical
per-component (left, top, width, height, area). Label integers are arbitrary. Skips if iverilog absent.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from fpv.seeker.detect import _connected_components

from fpga.rtl.test_ccl_rtl import _mask, _stats_from_pixels, _W, _H

_RTL_DIR = Path(__file__).parent
_IVERILOG = shutil.which("iverilog")
_VVP = shutil.which("vvp")


def _run_ccl_stream(mask: np.ndarray, tmp_path: Path) -> dict[int, int]:
    (tmp_path / "mask.txt").write_text(
        "".join(f"{int(mask[i // _W, i % _W])}\n" for i in range(_W * _H)))
    sim = tmp_path / "sim.vvp"
    subprocess.run(
        [_IVERILOG, "-g2012", "-o", str(sim),
         str(_RTL_DIR / "ccl_stream.v"), str(_RTL_DIR / "tb_ccl_stream.v")],
        check=True, capture_output=True, text=True)
    proc = subprocess.run([_VVP, str(sim)], cwd=tmp_path, check=True, capture_output=True, text=True)
    out: dict[int, int] = {}
    for line in proc.stdout.splitlines():
        if line.startswith("L "):
            _, idx, lab = line.split()
            out[int(idx)] = int(lab)
    return out


@pytest.mark.skipif(_IVERILOG is None or _VVP is None, reason="iverilog/vvp not installed")
def test_ccl_stream_matches_detector(tmp_path):
    """The streaming union-find labeller yields the same components as _connected_components."""
    mask = _mask()
    assert mask.sum() >= 6, "need a non-trivial mask"

    num, labels, stats = _connected_components(mask)

    py_comp: dict[int, set[int]] = {}
    for y in range(_H):
        for x in range(_W):
            if mask[y, x]:
                py_comp.setdefault(int(labels[y, x]), set()).add(y * _W + x)

    rtl = _run_ccl_stream(mask, tmp_path)
    rtl_comp: dict[int, set[int]] = {}
    for idx, lab in rtl.items():
        rtl_comp.setdefault(lab, set()).add(idx)

    py_sets = {frozenset(s) for s in py_comp.values()}
    rtl_sets = {frozenset(s) for s in rtl_comp.values()}
    assert py_sets == rtl_sets, f"grouping differs: {len(py_sets)} py vs {len(rtl_sets)} rtl comps"

    py_stats = sorted(tuple(int(v) for v in stats[k]) for k in range(1, num))
    rtl_stats = sorted(_stats_from_pixels(s) for s in rtl_sets)
    assert rtl_stats == py_stats, f"stats differ:\n  rtl={rtl_stats}\n  py ={py_stats}"

    print(f"\n[ccl_stream] single-pass streaming union-find == _connected_components: "
          f"{len(rtl_sets)} components, bbox/area identical (areas={[s[4] for s in rtl_stats]})")
