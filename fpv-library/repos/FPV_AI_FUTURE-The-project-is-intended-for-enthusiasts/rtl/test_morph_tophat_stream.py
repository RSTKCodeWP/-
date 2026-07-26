"""RTL co-sim: morph_tophat_stream.v == fpv.seeker.detect._white_tophat (streaming white top-hat).

The synthesis-oriented streaming top-hat (two cascaded win_reduce line-buffer stages + an f frame
buffer for the subtract) must reproduce the SAME margin-2R interior as the software detector and the
frame-addressed morph_tophat.v, byte-for-byte. Skips cleanly if iverilog is absent.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from fpv.seeker.detect import _STRUCT_ELEM, _SE_DIAMETER_PX, _white_tophat

from fpga.rtl.test_morph_tophat import _synth_patch, _W, _H

_D = int(_SE_DIAMETER_PX)
_R = _D // 2
_RTL_DIR = Path(__file__).parent
_IVERILOG = shutil.which("iverilog")
_VVP = shutil.which("vvp")


def _run(frame: np.ndarray, tmp_path: Path) -> dict[tuple[int, int], int]:
    (tmp_path / "frame.hex").write_text(
        "".join(f"{int(frame[i // _W, i % _W]):04x}\n" for i in range(_W * _H)))
    (tmp_path / "se.txt").write_text(
        "".join(f"{int(b)}\n" for b in np.asarray(_STRUCT_ELEM).reshape(-1)))

    sim = tmp_path / "sim.vvp"
    subprocess.run(
        [_IVERILOG, "-g2012", "-o", str(sim),
         str(_RTL_DIR / "win_reduce.v"), str(_RTL_DIR / "morph_tophat_stream.v"),
         str(_RTL_DIR / "tb_morph_tophat_stream.v")],
        check=True, capture_output=True, text=True)
    proc = subprocess.run([_VVP, str(sim)], cwd=tmp_path, check=True, capture_output=True, text=True)

    out: dict[tuple[int, int], int] = {}
    for line in proc.stdout.splitlines():
        if line.startswith("TH "):
            _, y, x, v = line.split()
            out[(int(y), int(x))] = int(v)
    return out


@pytest.mark.skipif(_IVERILOG is None or _VVP is None, reason="iverilog/vvp not installed")
def test_morph_tophat_stream_matches_detector(tmp_path):
    """The streaming top-hat equals _white_tophat byte-exact on the margin-2R interior."""
    frame = _synth_patch()
    ref = _white_tophat(frame.astype(np.float32), _STRUCT_ELEM)
    rtl = _run(frame, tmp_path)

    lo, hi = 2 * _R, _H - 1 - 2 * _R
    assert len(rtl) == (hi - lo + 1) ** 2, f"streaming top-hat dumped {len(rtl)} interior px"
    mism = [(y, x, rtl[(y, x)], int(round(float(ref[y, x]))))
            for y in range(lo, hi + 1) for x in range(lo, hi + 1)
            if rtl[(y, x)] != int(round(float(ref[y, x])))]
    assert not mism, f"streaming top-hat mismatch at {mism[:8]} ({len(mism)} px)"

    peak = max(rtl.values())
    print(f"\n[morph_tophat_stream] streaming line-buffer top-hat == _white_tophat byte-exact on "
          f"{len(rtl)} interior px (margin {2*_R}); peak={peak}")
    assert peak > 100, "sanity: the central blob should leave a strong top-hat residual"
