"""High-speed guidance DECISION gates (decoupled from the plant).

Feeds BearingRateGuidance.compute() with IMM + looming inputs for the high-speed engagement
geometries (threat 55-83 m/s, interceptor 150 m/s) and checks the doctrinal decision: engage the
feasible geometry, ABORT the infeasible one (abort is PASS, silent wrong-miss is HARD-FAIL).  The
g-wall the guidance enforces is cross-checked against fpv.guidance.engagement_regime.

FINDING pinned here: the fixed ``crossing_rate_threshold`` (0.15 rad/s) is tuned for the OLD slow
regime (Vc~20).  At Vc=150 the airframe g-wall is already exceeded at lambda_dot ~ 0.018 rad/s --
~8x below that threshold.  The dedicated HIGH_CROSSING abort therefore under-fires at high speed;
the envelope abort still catches an infeasible demand WHEN closing is detected (blend high), but the
crossing classifier should scale with Vc:  lambda_dot_wall = achievable_g * g / (N * Vc).
"""

from __future__ import annotations

import math

import pytest

from fpv.guidance.bearing_rate import BearingRateGuidance, GuidanceConfig, ROEAbort
from fpv.guidance.engagement_regime import InterceptGeometry, analyze
from fpv.seeker.imm import IMMEstimate
from fpv.seeker.looming import LoomingEstimate

_THETA_MAX = math.radians(40.0)   # ~0.84 g body


def _imm(az_rate: float, *, az: float = 0.0, el_rate: float = 0.0) -> IMMEstimate:
    return IMMEstimate(az_rad=az, el_rad=0.0, az_rate_radps=az_rate, el_rate_radps=el_rate,
                       mode_probs=(0.8, 0.2), maneuver_detected=False, frame_id=0)


def _looming(*, closing: bool) -> LoomingEstimate:
    return LoomingEstimate(
        tau_s=(1.5 if closing else float("inf")),
        tau_confidence=(0.9 if closing else 0.0),
        closing_sign=(1 if closing else 0),
        area_smoothed_px=60.0,
        d_area_dt_px_per_s=(40.0 if closing else 0.0))


def _run(guidance: BearingRateGuidance, imm: IMMEstimate, looming: LoomingEstimate,
         Vc: float, n: int = 140):
    """Tick past the crossing warmup (125). Returns ('abort', ROEAbort) or ('command', cmd)."""
    last = None
    for _ in range(n):
        try:
            last = guidance.compute(imm, looming, Vc_override_mps=Vc)
        except ROEAbort as ab:
            return "abort", ab
    return "command", last


def test_high_speed_broadside_crossing_is_aborted():
    """A broadside crosser at these speeds must ROE-ABORT, and the g-wall number matches the regime."""
    reg = analyze(InterceptGeometry(150, 83, 100, aspect_deg=90.0))   # Vc=150, lambda_dot=0.83
    assert not reg.feasible                                            # ~38 g -- infeasible
    g = BearingRateGuidance(GuidanceConfig(
        N=3.0, Vc_sched_mps=reg.closing_speed_mps, theta_max_rad=_THETA_MAX,
        crossing_rate_threshold_radps=0.15))
    kind, res = _run(g, _imm(reg.los_rate_radps), _looming(closing=False), reg.closing_speed_mps)
    assert kind == "abort", "high-speed broadside crossing must ABORT, not silently miss"
    assert res.required_g > 10.0 * res.achievable_g
    # cross-module: the guidance g-wall equals the engagement-regime g-wall (same N*Vc*lambda/g).
    assert math.isclose(res.required_g, reg.required_lateral_g, rel_tol=2e-3)


def test_high_speed_head_on_engages():
    """A feasible head-on (lambda_dot ~ 0) must ENGAGE: a finite in-envelope command, no abort."""
    reg = analyze(InterceptGeometry(150, 83, 200, aspect_deg=0.0))    # Vc=233, lambda_dot~0
    assert reg.feasible
    g = BearingRateGuidance(GuidanceConfig(
        N=3.0, Vc_sched_mps=reg.closing_speed_mps, theta_max_rad=_THETA_MAX))
    kind, cmd = _run(g, _imm(0.002), _looming(closing=True), reg.closing_speed_mps)
    assert kind == "command", "feasible head-on must engage, not abort"
    assert cmd.envelope_ok
    a_total = math.hypot(cmd.a_cmd_az_mps2, cmd.a_cmd_el_mps2)
    assert math.isfinite(a_total) and a_total <= 9.81 * math.tan(_THETA_MAX) + 1e-6


def test_envelope_abort_g_matches_engagement_regime():
    """When a closing engagement demands > the g-wall, the guidance aborts and required_g == regime."""
    # a modest off-head-on aspect at high Vc already exceeds the wall (regime says infeasible).
    reg = analyze(InterceptGeometry(150, 83, 150, aspect_deg=30.0))
    assert not reg.feasible and reg.los_rate_radps > 0.15               # also trips HIGH_CROSSING
    g = BearingRateGuidance(GuidanceConfig(
        N=3.0, Vc_sched_mps=reg.closing_speed_mps, theta_max_rad=_THETA_MAX,
        crossing_rate_threshold_radps=0.15))
    kind, res = _run(g, _imm(reg.los_rate_radps), _looming(closing=True), reg.closing_speed_mps)
    assert kind == "abort"
    assert math.isclose(res.required_g, reg.required_lateral_g, rel_tol=2e-3)


def test_crossing_threshold_is_mistuned_for_high_Vc_KNOWN_GAP():
    """Pin the finding: the fixed 0.15 rad/s crossing threshold is ~8x too high at Vc=150.

    The airframe g-wall is exceeded at lambda_dot_wall = achievable_g*g/(N*Vc); at Vc=150 that is
    ~0.018 rad/s, far below the 0.15 threshold.  The fix is a Vc-scaled crossing threshold; this
    gate documents the mismatch and its formula so the tuning is not forgotten.
    """
    N, Vc = 3.0, 150.0
    achievable_g = math.tan(_THETA_MAX)                # a_max/g
    lambda_dot_wall = achievable_g * 9.81 / (N * Vc)   # rad/s where required_g == achievable_g
    assert lambda_dot_wall < 0.02                       # ~0.0183 at Vc=150
    assert 0.15 > 5.0 * lambda_dot_wall, "the fixed crossing threshold is far above the g-wall rate"
    # sanity: at the OLD regime (Vc~20) the 0.15 threshold DID sit near the wall (that's its origin).
    lambda_dot_wall_slow = achievable_g * 9.81 / (N * 20.0)
    assert abs(lambda_dot_wall_slow - 0.15) < 0.03


def test_vc_scaled_threshold_off_is_bit_identical_on_recovers_the_wall():
    """The flag defaults OFF (fixed threshold, bit-identical); ON it IS the g-wall LOS rate."""
    off = GuidanceConfig(N=3.0, theta_max_rad=_THETA_MAX, crossing_rate_threshold_radps=0.15)
    for Vc in (20.0, 150.0, 233.0):
        assert off.effective_crossing_threshold(Vc) == 0.15         # OFF -> fixed, unchanged
    on = GuidanceConfig(N=3.0, theta_max_rad=_THETA_MAX, vc_scaled_crossing_threshold=True)
    a_max = 9.81 * math.tan(_THETA_MAX)
    assert math.isclose(on.effective_crossing_threshold(150.0), a_max / (3.0 * 150.0), rel_tol=1e-9)
    assert on.effective_crossing_threshold(150.0) < 0.02            # ~0.0183 at Vc=150
    assert abs(on.effective_crossing_threshold(20.0) - 0.15) < 0.02  # recovers the old value slow


def test_vc_scaled_threshold_closes_the_silent_miss_gap():
    """At Vc=150 a λ̇ between the g-wall (~0.018) and the fixed threshold (0.15) is infeasible
    (needs >2 g) yet NOT flagged HIGH_CROSSING with the fixed threshold -> a non-closing crosser can
    slip through un-aborted.  The Vc-scaled threshold aborts it, as doctrine requires."""
    Vc = 150.0
    imm = _imm(0.05, az=0.0)                    # 0.05 rad/s: > wall(0.018), < fixed(0.15); needs ~2.3 g
    loom = _looming(closing=False)             # not closing -> blend -> pursuit, boresight -> ~0 command
    off = BearingRateGuidance(GuidanceConfig(
        N=3.0, Vc_sched_mps=Vc, theta_max_rad=_THETA_MAX,
        crossing_rate_threshold_radps=0.15, vc_scaled_crossing_threshold=False))
    on = BearingRateGuidance(GuidanceConfig(
        N=3.0, Vc_sched_mps=Vc, theta_max_rad=_THETA_MAX,
        crossing_rate_threshold_radps=0.15, vc_scaled_crossing_threshold=True))
    kind_off, _ = _run(off, imm, loom, Vc)
    kind_on, res_on = _run(on, imm, loom, Vc)
    assert kind_off == "command", "with the fixed threshold the infeasible crosser is NOT aborted (gap)"
    assert kind_on == "abort", "the Vc-scaled threshold correctly ABORTS the infeasible crosser"
    assert res_on.required_g > res_on.achievable_g   # confirm it really was out of envelope
