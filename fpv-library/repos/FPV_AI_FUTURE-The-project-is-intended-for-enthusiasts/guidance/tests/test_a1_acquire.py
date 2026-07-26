"""A1 — ACQUIRE low-gain settling before full PN (+ R3 falcon-low N option).

The PN gain ramps from a benign fraction to full N over the first ticks of the engagement, so
the first corrections after lock are gentle while the LOS estimate settles (the falcon's
feed-forward lock-on phase). Behind acquire_settle_ticks (0 = off -> bit-identical).
"""

from __future__ import annotations

from fpv.seeker.imm import IMMEstimate
from fpv.seeker.looming import LoomingEstimate
from fpv.guidance.bearing_rate import BearingRateGuidance, GuidanceConfig


def _imm(az_rate=0.02, fid=0):
    return IMMEstimate(az_rad=0.0, el_rad=0.0, az_rate_radps=az_rate, el_rate_radps=0.0,
                       mode_probs=(0.9, 0.1), maneuver_detected=False, frame_id=fid)


def _looming(conf=0.8):
    return LoomingEstimate(tau_s=2.0, tau_confidence=conf, closing_sign=1,
                           area_smoothed_px=100.0, d_area_dt_px_per_s=10.0)


def test_acquire_ramp_makes_early_commands_gentle():
    g = BearingRateGuidance(GuidanceConfig(Vc_sched_mps=20.0, acquire_settle_ticks=20,
                                           acquire_settle_min_frac=0.3))
    imm = _imm()
    first = g.compute(imm, _looming())
    last = None
    for _ in range(25):
        last = g.compute(imm, _looming())
    assert first.N_effective < last.N_effective                 # gain ramps up over the engagement
    assert abs(first.brn_az_mps2) < abs(last.brn_az_mps2)        # the first command is gentler


def test_acquire_off_is_full_gain_from_tick_one():
    g_off = BearingRateGuidance(GuidanceConfig(Vc_sched_mps=20.0, acquire_settle_ticks=0))
    g_ramp = BearingRateGuidance(GuidanceConfig(Vc_sched_mps=20.0, acquire_settle_ticks=20))
    imm = _imm()
    off = g_off.compute(imm, _looming())
    ramp = g_ramp.compute(imm, _looming())
    assert abs(off.brn_az_mps2 - 3.0 * 20.0 * 0.02) < 1e-9      # OFF: full N from tick 1
    assert abs(ramp.brn_az_mps2) < abs(off.brn_az_mps2)         # ramp ON: gentler at tick 1


def test_falcon_low_n_reduces_the_gain():
    imm = _imm()
    b3 = BearingRateGuidance(GuidanceConfig(Vc_sched_mps=20.0, N=3.0)).compute(imm, _looming()).brn_az_mps2
    b26 = BearingRateGuidance(GuidanceConfig(Vc_sched_mps=20.0, N=2.6)).compute(imm, _looming()).brn_az_mps2
    assert abs(b26) < abs(b3)
    assert abs(b26 - 2.6 * 20.0 * 0.02) < 1e-9                  # falcon-low N is a plain config value
