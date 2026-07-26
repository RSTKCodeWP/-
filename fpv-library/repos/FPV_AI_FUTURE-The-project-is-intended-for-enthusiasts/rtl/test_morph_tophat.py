"""RTL co-simulation: morph_tophat.v vs fpv.seeker.detect._white_tophat (M0, front-end middle).

Runs a 32x32 thermal patch through the Verilog white-top-hat engine (loaded with the SAME 11x11
cv2 ellipse SE the software detector uses) and asserts the recovered top-hat matches the Python
detector byte-for-byte on the margin-2R interior (where the window is fully inside the frame, so the
border policy is irrelevant and the target always sits).  This proves the morphology numerics --
erode(min) -> dilate(max) -> subtract -- in real RTL.  Skips cleanly if iverilog is absent.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from fpv.seeker.detect import _STRUCT_ELEM, _SE_DIAMETER_PX, _white_tophat

_W = _H = 32
_D = int(_SE_DIAMETER_PX)          # 11
_R = _D // 2                       # 5
_RTL_DIR = Path(__file__).parent
_IVERILOG = shutil.which("iverilog")
_VVP = shutil.which("vvp")


def _synth_patch(seed: int = 3) -> np.ndarray:
    """A small thermal patch: cold sky + read noise + a central hot blob + an off-centre spot."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:_H, 0:_W]
    f = 4096.0 + rng.normal(0.0, 12.0, (_H, _W))
    f += 1800.0 * np.exp(-((xx - 16) ** 2 + (yy - 16) ** 2) / (2 * 1.5 ** 2))
    f += 900.0 * np.exp(-((xx - 12) ** 2 + (yy - 20) ** 2) / (2 * 1.3 ** 2))
    return np.clip(f, 0, 65535).astype(np.uint16)


def _run_rtl(frame: np.ndarray, tmp_path: Path) -> dict[tuple[int, int], int]:
    (tmp_path / "frame.hex").write_text(
        "".join(f"{int(frame[i // _W, i % _W]):04x}\n" for i in range(_W * _H)))
    (tmp_path / "se.txt").write_text(
        "".join(f"{int(b)}\n" for b in np.asarray(_STRUCT_ELEM).reshape(-1)))

    sim = tmp_path / "sim.vvp"
    subprocess.run(
        [_IVERILOG, "-g2012", "-o", str(sim),
         str(_RTL_DIR / "morph_tophat.v"), str(_RTL_DIR / "tb_morph_tophat.v")],
        check=True, capture_output=True, text=True)
    proc = subprocess.run([_VVP, str(sim)], cwd=tmp_path, check=True, capture_output=True, text=True)

    out: dict[tuple[int, int], int] = {}
    for line in proc.stdout.splitlines():
        if line.startswith("TH "):
            _, y, x, v = line.split()
            out[(int(y), int(x))] = int(v)
    return out


@pytest.mark.skipif(_IVERILOG is None or _VVP is None, reason="iverilog/vvp not installed")
def test_morph_tophat_matches_detector_interior(tmp_path):
    """The RTL white-top-hat equals _white_tophat byte-exact on the margin-2R interior."""
    frame = _synth_patch()
    ref = _white_tophat(frame.astype(np.float32), _STRUCT_ELEM)   # integer-valued (proven exact)
    rtl = _run_rtl(frame, tmp_path)

    lo, hi = 2 * _R, _H - 1 - 2 * _R
    assert len(rtl) == (hi - lo + 1) ** 2, f"RTL dumped {len(rtl)} interior pixels"

    mism = [(y, x, rtl[(y, x)], int(round(float(ref[y, x]))))
            for y in range(lo, hi + 1) for x in range(lo, hi + 1)
            if rtl[(y, x)] != int(round(float(ref[y, x])))]
    assert not mism, f"top-hat mismatch at {mism[:8]} ({len(mism)} pixels)"

    peak = max(rtl.values())
    print(f"\n[morph_tophat] RTL == _white_tophat byte-exact on {len(rtl)} interior px "
          f"(margin {2*_R}); interior top-hat peak={peak}")
    assert peak > 100, "sanity: the central blob should leave a strong top-hat residual"
