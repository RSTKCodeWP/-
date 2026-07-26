"""PS IMM filter (C) vs fpv.seeker.imm.IMMFilter (M0 glue).

Drives a maneuvering-target LOS sequence (a mid-run jink so the maneuver mode activates) through both
the Python IMMFilter and the C port and asserts the combined state, mode probabilities and A4
diagnostics match within float tolerance.  (The C uses a Gauss-Jordan 4x4 inverse vs numpy's LAPACK,
so the two differ at ~1e-14 per step -- accumulated but far below sensor noise.)  Skips if no C++.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from fpv.seeker.imm import IMMConfig, IMMFilter
from fpv.seeker.los import LOSObservation

_PS_DIR = Path(__file__).parent
_CXX = shutil.which("clang++") or shutil.which("g++")


@pytest.fixture(scope="module")
def cbin(tmp_path_factory):
    if _CXX is None:
        pytest.skip("no C++ compiler")
    out = tmp_path_factory.mktemp("ps") / "imm"
    subprocess.run([_CXX, "-O2", "-std=c++14", "-o", str(out), str(_PS_DIR / "imm.cpp")],
                   check=True, capture_output=True, text=True)
    return out


def _sequence(n: int = 60):
    """(az, el, az_rate, el_rate, ego_quality, dt) with a jink in az_rate at frame 30."""
    rng = np.random.default_rng(11)
    dt = 1.0 / 60.0
    az = 0.0
    el = 0.0
    seq = []
    for k in range(n):
        base = 0.10 if k < 30 else 0.55                     # jink -> maneuver mode should react
        azr = base + float(rng.normal(0, 0.01))
        elr = 0.02 + float(rng.normal(0, 0.005))
        az += base * dt
        el += 0.02 * dt
        seq.append((az + float(rng.normal(0, 3e-4)), el + float(rng.normal(0, 3e-4)),
                    azr, elr, 1.0, dt))
    return seq


def _cfg_line(cfg: IMMConfig) -> str:
    return (f"{cfg.sigma_meas_az:.15e} {cfg.sigma_meas_el:.15e} {cfg.sigma_meas_az_rate:.15e} "
            f"{cfg.sigma_meas_el_rate:.15e} {cfg.q_cv_rate:.15e} {cfg.q_maneuver_rate:.15e} "
            f"{cfg.transition_prob_stay:.15e} {cfg.ego_gate_radps:.15e} {cfg.ego_gate_damping:.15e} "
            f"{cfg.n_sustain_for_maneuver} {cfg.init_mode_prob_cv:.15e} "
            f"{cfg.ego_quality_r_inflation:.15e} {cfg.nis_chi2_bound:.15e} "
            f"{cfg.nis_gate_chi2:.15e} {cfg.nis_sustain_for_alarm}\n")


@pytest.mark.skipif(_CXX is None, reason="no C++ compiler")
def test_imm_c_matches_python(cbin, tmp_path, capsys):
    cfg = IMMConfig()
    seq = _sequence()

    filt = IMMFilter(cfg)
    ref = []
    for k, (az, el, azr, elr, eq, dt) in enumerate(seq):
        los = LOSObservation(az_rad=az, el_rad=el, az_rate_radps=azr, el_rate_radps=elr,
                             ego_quality=eq, ego_source="gyro", frame_id=k, t_capture_ns=None)
        e = filt.update(los, dt)
        ref.append((e.az_rad, e.el_rad, e.az_rate_radps, e.el_rate_radps,
                    e.mode_probs[0], e.mode_probs[1], e.nis, e.lock_quality, e.nis_true))

    seqf = tmp_path / "seq.txt"
    with seqf.open("w") as fh:
        fh.write(_cfg_line(cfg))
        for az, el, azr, elr, eq, dt in seq:
            fh.write(f"{az:.15e} {el:.15e} {azr:.15e} {elr:.15e} {eq:.15e} {dt:.15e}\n")
    out = subprocess.run([str(cbin), str(seqf)], check=True, capture_output=True, text=True)
    cvals = [tuple(float(v) for v in line.split()) for line in out.stdout.splitlines()]
    assert len(cvals) == len(ref)

    names = ["az", "el", "az_rate", "el_rate", "p_cv", "p_man", "nis", "lock_q", "nis_true"]
    worst = [0.0] * 9
    for r, cc in zip(ref, cvals):
        for i in range(9):
            worst[i] = max(worst[i], abs(r[i] - cc[i]))
    with capsys.disabled():
        print("\n[imm.cpp] worst |C - python| per field over", len(ref), "frames:")
        for nm, w in zip(names, worst):
            print(f"    {nm:9s} {w:.2e}")

    # state + mode probs must track tightly; diagnostics (nis/nis_true involve the inverse) a bit looser.
    for i in range(6):
        assert worst[i] < 1e-8, f"{names[i]} diverged: {worst[i]:.2e}"
    assert worst[6] < 1e-6 and worst[8] < 1e-6, "nis diagnostics diverged"
    assert worst[7] < 1e-8, "lock_quality diverged"
