"""Pins the high-speed engagement regime (threat 55-83 m/s, interceptor 100-150 m/s).

These gates encode the load-bearing design consequences so a later change that silently assumes the
old slow regime (Vc ~15-23 m/s) trips a red test.
"""

from __future__ import annotations

import math

from fpv.guidance.engagement_regime import (
    InterceptGeometry,
    analyze,
    max_feasible_aspect_deg,
)


def test_head_on_is_the_feasible_collision_geometry():
    """Pure head-on: no tangential motion -> ~zero LOS rate, ~zero PN demand -> feasible."""
    r = analyze(InterceptGeometry(interceptor_speed_mps=150, target_speed_mps=83,
                                  range_m=200, aspect_deg=0.0))
    assert r.closing_speed_mps == 233.0                     # Vi + Vt head-on
    assert r.los_rate_radps < 1e-9 and r.required_lateral_g < 1e-9
    assert r.feasible
    assert math.isclose(r.time_to_go_s, 200 / 233.0, rel_tol=1e-6)  # ~0.86 s to intercept


def test_broadside_crossing_is_geometrically_unachievable():
    """A broadside crosser demands tens of g -- past the ~0.84 g airframe wall by >>10x."""
    r100 = analyze(InterceptGeometry(150, 83, 100, aspect_deg=90.0))
    r50 = analyze(InterceptGeometry(150, 83, 50, aspect_deg=90.0))
    assert not r100.feasible and r100.required_lateral_g > 10.0     # ~38 g
    assert not r50.feasible and r50.required_lateral_g > r100.required_lateral_g  # worse closer in


def test_terminal_is_near_ballistic():
    """At 150 m/s and 0.84 g the turn radius dwarfs the thermal engagement range."""
    r = analyze(InterceptGeometry(150, 83, 100, aspect_deg=0.0))
    assert r.turn_radius_m > 2000.0                          # ~2.7 km >> 50-200 m
    # maneuver authority over the engagement range is a few percent of a radian.
    assert (100.0 / r.turn_radius_m) < 0.06


def test_lead_cone_is_narrow_so_the_handover_must_pre_aim():
    """The terminal seeker can only trim a sub-degree residual aspect; the LEAD must be pre-set.

    ``max_feasible_aspect`` is the pointing accuracy the ground cue + midcourse must deliver at
    handover -- wider than this and no achievable terminal maneuver closes the miss.
    """
    assert max_feasible_aspect_deg(InterceptGeometry(150, 83, 100, 0)) < 2.0
    assert max_feasible_aspect_deg(InterceptGeometry(150, 83, 200, 0)) < 3.0
    # more range -> a bit more forgiving, but still single-digit degrees.
    mfa500 = max_feasible_aspect_deg(InterceptGeometry(150, 83, 500, 0))
    assert 1.0 < mfa500 < 6.0


def test_track_holding_needs_prediction_not_reaction():
    """A crosser sweeps ~10 px/frame at 60 Hz -> a last-position ROI must be wide; predict instead."""
    r = analyze(InterceptGeometry(150, 83, 100, aspect_deg=90.0))
    assert 8.0 < r.px_per_frame < 12.0
    # a reactive (last-position) ROI would need this half-width just to still contain the target:
    assert r.min_roi_halfwidth_px(margin_frames=2.0, blob_radius_px=4.0) > 20.0


def test_latency_is_a_metric_scale_miss_at_these_speeds():
    """Loop latency buys miss distance: this is why deterministic sub-frame (FPGA) latency matters."""
    crosser = analyze(InterceptGeometry(150, 83, 100, aspect_deg=90.0))
    head_on = analyze(InterceptGeometry(150, 83, 200, aspect_deg=0.0))
    # crossing target lateral slip during the loop delay: ~35 ms Pi loop vs ~3 ms FPGA pipeline.
    assert crosser.lateral_slip_m(0.035) > 2.0
    assert crosser.lateral_slip_m(0.003) < 0.3
    # head-on blind closure during 35 ms at Vc=233 is metres of range.
    assert head_on.blind_closure_m(0.035) > 8.0
    assert head_on.blind_closure_m(0.003) < 1.0
