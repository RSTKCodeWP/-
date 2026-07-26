"""The g-envelope ROE abort must ride out a transient spike but still give up on a persistent one.

Background (measured 2026-07-19): the abort fired on a SINGLE over-demand tick. In launch_and_forget that
killed engagements at ~1.2 s -- while the target was still ~100 m out -- on a spike that decayed within a few
frames (3.53 -> 2.80 -> 2.31 g). Worse, the abort is disabled post-commit BY DESIGN, so it deadlocked the
commit: the abort prevented the commit that would have disabled the abort. Continuing through a transient is
safe because the command clamp already saturates the demand at max-g.
"""

from __future__ import annotations

import math

from fpv.guidance.bearing_rate import BearingRateGuidance, GuidanceConfig, ROEAbort
from fpv.seeker.imm import IMMEstimate
from fpv.seeker.looming import LoomingEstimate


def _imm(az_rate: float, fid: int = 0) -> IMMEstimate:
    return IMMEstimate(az_rad=0.02, el_rad=0.02, az_rate_radps=az_rate, el_rate_radps=0.0,
                       mode_probs=(0.9, 0.1), maneuver_detected=False, frame_id=fid)


def _looming() -> LoomingEstimate:
    return LoomingEstimate(tau_s=2.0, tau_confidence=0.8, closing_sign=1,
                           area_smoothed_px=100.0, d_area_dt_px_per_s=10.0)


def _cfg(persist: int) -> GuidanceConfig:
    return GuidanceConfig(N=4.0, Vc_sched_mps=40.0, theta_max_rad=math.radians(40.0),
                          envelope_abort_persist_ticks=persist)


def _drive(g: BearingRateGuidance, rates, look):
    """Feed a sequence of LOS rates; return the tick index that aborted, or None."""
    for i, r in enumerate(rates):
        try:
            g.compute(_imm(r, fid=i), look)
        except ROEAbort:
            return i
    return None


def test_isolated_spike_does_not_abort():
    """A few over-demand frames inside an otherwise in-envelope run must NOT end the engagement."""
    look = _looming()
    g = BearingRateGuidance(_cfg(25))
    calm, spike = 0.002, 0.9
    rates = [calm] * 40 + [spike] * 3 + [calm] * 40
    assert _drive(g, rates, look) is None, "a 3-tick spike must not abort"


def test_persistent_over_demand_still_aborts():
    """The abort must still do its real job: give up on an engagement that is genuinely beyond the airframe."""
    look = _looming()
    g = BearingRateGuidance(_cfg(25))
    assert _drive(g, [0.9] * 200, look) is not None, "sustained over-demand must still abort"


def test_intermittent_over_demand_accumulates():
    """The spikes we actually saw were intermittent, not consecutive -- a consecutive-run counter would reset
    on every good frame and never fire. The leaky accumulator must still catch a mostly-over-envelope run."""
    look = _looming()
    g = BearingRateGuidance(_cfg(25))
    rates = ([0.9] * 3 + [0.002]) * 200          # 75% over-demand
    assert _drive(g, rates, look) is not None, "a mostly-over-envelope run must eventually abort"


def test_zero_persistence_restores_fire_on_first_tick():
    """Backwards-compatible escape hatch: persistence 0 == the old instant abort, exactly."""
    look = _looming()
    g = BearingRateGuidance(_cfg(0))
    assert _drive(g, [0.9] * 10, look) == 0, "with persistence 0 the first over-demand tick must abort"


def test_flying_a_saturated_command_is_worse_than_flying_none():
    """The measured reason `envelope_abort_persist_ticks` ships at 0.

    When the demand exceeds the envelope there are two options: zero the lateral command (what the abort
    path does today) or fly the CLAMPED command (what riding through does). Zeroing wins, systematically:
    the miss is ~2x smaller on every seed tried. The mechanism is saturation, not a terminal effect --
    riding through pins the airframe at full bank ~8x longer, and on a STRAPDOWN seeker full bank tilts the
    camera and corrupts the lambda-dot the guidance is steering on.

    This test exists so that a future change which flips the default has to confront the measurement.
    """
    from fpv.guidance.tests.test_true_pn_measured_vc import ClosedLoop, _cfg

    for seed in (1, 4):
        misses = {}
        for persist in (0, 25):
            cfg = _cfg(measured_vc=True)
            cfg.sim.__dict__["seed"] = seed
            cfg.guidance.__dict__["envelope_abort_persist_ticks"] = persist
            misses[persist] = ClosedLoop(cfg).run().miss_distance_m
        assert misses[0] < misses[25], (
            f"seed {seed}: zeroing the unreachable command should beat flying it clamped "
            f"({misses[0]:.3f} m vs {misses[25]:.3f} m)")
