"""RTL co-simulation: hist.v == numpy bincount of the top-hat (M0, threshold PL side).

Streams a real top-hat's integer values through the Verilog histogram accumulator and asserts the
recovered bins equal numpy's bincount bit-exactly.  The threshold statistics themselves run on the
PS (fpga/ps/threshold_stats).  Skips cleanly if iverilog is absent.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from fpv.seeker.detect import _STRUCT_ELEM, _white_tophat
from fpv.seeker.thermal_sim import ThermalSceneConfig, ThermalSimulator

_NBINS = 2048
_RTL_DIR = Path(__file__).parent
_IVERILOG = shutil.which("iverilog")
_VVP = shutil.which("vvp")


def _tophat_values() -> np.ndarray:
    """Integer top-hat values of a small deterministic thermal patch (clamped into the bin range)."""
    cfg = ThermalSceneConfig(width=64, height=64, n_stars=6, seed=5, ffc_freeze_interval=0)
    frame, _gt = ThermalSimulator(cfg).generate(1)[0]
    th = _white_tophat(frame.astype(np.float32), _STRUCT_ELEM)
    vals = np.rint(th).astype(np.int64).reshape(-1)
    return np.clip(vals, 0, _NBINS - 1)


def _run_hist(vals: np.ndarray, tmp_path: Path) -> dict[int, int]:
    (tmp_path / "vals.txt").write_text("".join(f"{int(v)}\n" for v in vals))
    sim = tmp_path / "sim.vvp"
    subprocess.run(
        [_IVERILOG, "-g2012", "-o", str(sim),
         str(_RTL_DIR / "hist.v"), str(_RTL_DIR / "tb_hist.v")],
        check=True, capture_output=True, text=True)
    proc = subprocess.run([_VVP, str(sim)], cwd=tmp_path, check=True, capture_output=True, text=True)
    out: dict[int, int] = {}
    for line in proc.stdout.splitlines():
        if line.startswith("H "):
            _, b, c = line.split()
            out[int(b)] = int(c)
    return out


@pytest.mark.skipif(_IVERILOG is None or _VVP is None, reason="iverilog/vvp not installed")
def test_hist_matches_bincount(tmp_path):
    """The RTL histogram equals numpy's bincount of the top-hat, bin-for-bin."""
    vals = _tophat_values()
    expected = np.bincount(vals, minlength=_NBINS)
    rtl = _run_hist(vals, tmp_path)

    assert sum(rtl.values()) == len(vals), "RTL total count != number of pixels streamed"
    mism = [(b, rtl.get(b, 0), int(expected[b])) for b in range(_NBINS)
            if rtl.get(b, 0) != int(expected[b])]
    assert not mism, f"histogram mismatch at bins {mism[:8]} ({len(mism)} bins)"
    print(f"\n[hist] RTL histogram == numpy bincount over {len(vals)} px, "
          f"{len(rtl)} non-empty bins (max value {int(vals.max())})")
