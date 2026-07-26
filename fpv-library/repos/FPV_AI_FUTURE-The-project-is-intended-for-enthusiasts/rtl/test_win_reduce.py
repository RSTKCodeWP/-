"""RTL co-sim: win_reduce.v (streaming line-buffer windowed min/max) == numpy erode/dilate.

Streams a thermal patch through the FIELDED sliding-window morphology block (line buffers, one
SE-masked reduce per interior center) and asserts it matches a numpy erode (min) and dilate (max) over
the same 11x11 SE on the margin-R interior -- bit-exact. This is the synthesis-oriented replacement for
the frame-addressed footprint sweep in morph_tophat.v; two of these chain into an opening (see
morph_tophat_stream.v). Skips cleanly if iverilog is absent.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from fpv.seeker.detect import _STRUCT_ELEM, _SE_DIAMETER_PX

from fpga.rtl.test_morph_tophat import _synth_patch, _W, _H

_D = int(_SE_DIAMETER_PX)
_R = _D // 2
_RTL_DIR = Path(__file__).parent
_IVERILOG = shutil.which("iverilog")
_VVP = shutil.which("vvp")


def _reduce_ref(frame: np.ndarray, maxop: bool) -> dict[tuple[int, int], int]:
    """min (erode) or max (dilate) over the SE, on the margin-R interior [R,H-1-R] x [R,W-1-R]."""
    se = np.asarray(_STRUCT_ELEM)
    out: dict[tuple[int, int], int] = {}
    for y in range(_R, _H - _R):
        for x in range(_R, _W - _R):
            best = None
            for dy in range(_D):
                for dx in range(_D):
                    if se[dy, dx]:
                        v = int(frame[y + dy - _R, x + dx - _R])
                        best = v if best is None else (max(best, v) if maxop else min(best, v))
            out[(y, x)] = int(best)
    return out


def _run(frame: np.ndarray, tmp_path: Path, maxop: bool) -> dict[tuple[int, int], int]:
    (tmp_path / "frame.hex").write_text(
        "".join(f"{int(frame[i // _W, i % _W]):04x}\n" for i in range(_W * _H)))
    (tmp_path / "se.txt").write_text(
        "".join(f"{int(b)}\n" for b in np.asarray(_STRUCT_ELEM).reshape(-1)))

    sim = tmp_path / "sim.vvp"
    cmd = [_IVERILOG, "-g2012", "-o", str(sim),
           str(_RTL_DIR / "win_reduce.v"), str(_RTL_DIR / "tb_win_reduce.v")]
    if maxop:
        cmd.insert(1, "-DMAXOP")
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    proc = subprocess.run([_VVP, str(sim)], cwd=tmp_path, check=True, capture_output=True, text=True)

    out: dict[tuple[int, int], int] = {}
    for line in proc.stdout.splitlines():
        if line.startswith("R "):
            _, y, x, v = line.split()
            out[(int(y), int(x))] = int(v)
    return out


@pytest.mark.skipif(_IVERILOG is None or _VVP is None, reason="iverilog/vvp not installed")
@pytest.mark.parametrize("maxop,name", [(False, "erode/min"), (True, "dilate/max")])
def test_win_reduce_matches_numpy(maxop, name, tmp_path):
    """The streaming windowed reduce equals numpy erode/dilate over the SE on the interior."""
    frame = _synth_patch()
    ref = _reduce_ref(frame, maxop)
    rtl = _run(frame, tmp_path, maxop)

    n = (_H - 2 * _R) * (_W - 2 * _R)
    assert len(rtl) == n, f"{name}: RTL emitted {len(rtl)} centers, expected {n}"
    mism = [(y, x, rtl[(y, x)], ref[(y, x)]) for (y, x) in ref if rtl.get((y, x)) != ref[(y, x)]]
    assert not mism, f"{name}: mismatch at {mism[:6]} ({len(mism)} px)"
    print(f"\n[win_reduce:{name}] streaming line-buffer == numpy over {len(rtl)} interior px (D={_D})")
