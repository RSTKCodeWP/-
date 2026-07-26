"""PS bearing-rate guidance (C) vs fpv.guidance.bearing_rate.compute() (M0 glue).

Drives ~140 ticks (past the 125-tick crossing warmup) mixing HEAD_ON (command), HIGH_CROSSING (abort)
and closing high-rate (envelope abort) cases through both the Python guidance and the C port, and
asserts the abort decision, geometry, command and required-g match.  Closes the PS chain
centroid -> LOS -> IMM -> guidance -> command in verified C.  Skips if no C++ compiler.
"""

from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from fpv.guidance.bearing_rate import BearingRateGuidance, GuidanceConfig, ROEAbort
from fpv.seeker.imm import IMMEstimate
from fpv.seeker.looming import LoomingEstimate

_PS_DIR = Path(__file__).parent
_CXX = shutil.which("clang++") or shutil.which("g++")
_WARMUP = 125
_GEOM = {"HEAD_ON": 0, "QUARTERING": 1, "HIGH_CROSSING": 2}


@pytest.fixture(scope="module")
def cbin(tmp_path_factory):
    if _CXX is None:
        pytest.skip("no C++ compiler")
    out = tmp_path_factory.mktemp("ps") / "guidance"
    subprocess.run([_CXX, "-O2", "-std=c++14", "-o", str(out), str(_PS_DIR / "guidance.cpp")],
                   check=True, capture_output=True, text=True)
    return out


def _frames(n: int = 140):
    """(az, el, az_rate, el_rate, mode_man, mdet, tau_conf, closing_sign, Vc) exercising all paths."""
    rng = np.random.default_rng(5)
    out = []
    for k in range(n):
        if k >= _WARMUP and k % 7 == 0:                 # broadside crosser -> HIGH_CROSSING abort
            azr, tc, cs = 0.30 + 0.1 * rng.random(), 0.0, 0
        elif k >= _WARMUP and k % 5 == 0:               # closing high-rate -> envelope abort
            azr, tc, cs = 0.25, 0.9, 1
        else:                                           # head-on -> command
            azr, tc, cs = 0.01 * float(rng.normal()), 0.8, 1
        out.append((0.01 * float(rng.normal()), 0.005 * float(rng.normal()),
                    azr, 0.004 * float(rng.normal()),
                    0.2, 0, tc, cs, 150.0 + 20.0 * float(rng.normal())))
    return out


def _cfg_line(c: GuidanceConfig) -> str:
    return (f"{c.N:.15e} {c.Vc_sched_mps:.15e} {c.theta_max_rad:.15e} {c.abort_g_margin:.15e} "
            f"{c.crossing_rate_threshold_radps:.15e} {int(c.vc_scaled_crossing_threshold)} "
            f"{c.tau_confidence_pursuit_threshold:.15e} {c.tau_confidence_full_brn_threshold:.15e} "
            f"{c.pursuit_gain_mps2_per_rad:.15e} {c.maneuver_prob_threshold:.15e} "
            f"{c.max_a_cmd_mps2:.15e} {c.acquire_settle_ticks} {c.acquire_settle_min_frac:.15e} "
            f"{_WARMUP}\n")


@pytest.mark.skipif(_CXX is None, reason="no C++ compiler")
def test_guidance_c_matches_python(cbin, tmp_path):
    cfg = GuidanceConfig(N=3.0, Vc_sched_mps=150.0, theta_max_rad=math.radians(40.0),
                         abort_g_margin=1.0, crossing_rate_threshold_radps=0.15)
    frames = _frames()

    g = BearingRateGuidance(cfg)
    ref = []
    for (az, el, azr, elr, mm, md, tc, cs, vc) in frames:
        imm = IMMEstimate(az_rad=az, el_rad=el, az_rate_radps=azr, el_rate_radps=elr,
                          mode_probs=(1 - mm, mm), maneuver_detected=bool(md), frame_id=0)
        loom = LoomingEstimate(tau_s=1.5, tau_confidence=tc, closing_sign=cs,
                               area_smoothed_px=60.0, d_area_dt_px_per_s=10.0)
        try:
            cmd = g.compute(imm, loom, Vc_override_mps=vc)
            ref.append((0, _GEOM[cmd.geometry.value], cmd.a_cmd_az_mps2, cmd.a_cmd_el_mps2,
                        cmd.required_g, cmd.achievable_g, int(cmd.envelope_ok),
                        cmd.blend_factor, cmd.N_effective))
        except ROEAbort as ab:
            ref.append((1, _GEOM[ab.geometry.value], 0.0, 0.0, ab.required_g, ab.achievable_g, 0, 0.0, 0.0))

    seqf = tmp_path / "seq.txt"
    with seqf.open("w") as fh:
        fh.write(_cfg_line(cfg))
        for (az, el, azr, elr, mm, md, tc, cs, vc) in frames:
            fh.write(f"{az:.15e} {el:.15e} {azr:.15e} {elr:.15e} {mm:.15e} {int(md)} "
                     f"{tc:.15e} {cs} {vc:.15e}\n")
    out = subprocess.run([str(cbin), str(seqf)], check=True, capture_output=True, text=True)
    cvals = [tuple(line.split()) for line in out.stdout.splitlines()]
    assert len(cvals) == len(ref)

    n_abort = n_cmd = 0
    for i, (r, cc) in enumerate(zip(ref, cvals)):
        c_abort, c_geom, c_ecmd = int(cc[0]), int(cc[1]), int(cc[6])
        assert c_abort == r[0], f"frame {i}: abort {c_abort} != {r[0]}"
        assert c_geom == r[1], f"frame {i}: geometry {c_geom} != {r[1]}"
        assert c_ecmd == r[6], f"frame {i}: envelope_ok {c_ecmd} != {r[6]}"
        # numeric fields
        for j, tol in ((2, 1e-9), (3, 1e-9), (5, 1e-12), (7, 1e-12), (8, 1e-12)):
            assert abs(float(cc[j]) - r[j]) < tol, f"frame {i} field {j}: {cc[j]} vs {r[j]}"
        assert abs(float(cc[4]) - r[4]) < 1e-9 * (1 + abs(r[4])), f"frame {i} required_g: {cc[4]} vs {r[4]}"
        n_abort += r[0]; n_cmd += 1 - r[0]

    print(f"\n[guidance.cpp] C == python compute() over {len(ref)} frames "
          f"({n_cmd} commands, {n_abort} aborts) -- abort/geometry/command all match")
    assert n_abort >= 3 and n_cmd >= 100, "sequence must exercise both commands and aborts"
