"""Miss geometry: the identity that makes the commit cue usable, and the range-free fallback."""

from __future__ import annotations

import math

import numpy as np
import pytest

from fpv.guidance.miss_geometry import (
    COLLISION_LAMBDA_DOT_RADPS,
    from_los_rate,
    from_relative_state,
    t_go_from_range_rate,
)

_CASES = [
    ((30.0, 40.0, 100.0), (-3.0, -11.0, -35.0)),
    ((5.0, 2.0, 60.0), (-1.0, 0.5, -38.0)),
    ((-20.0, 35.0, 80.0), (4.0, -9.0, -30.0)),
]


@pytest.mark.parametrize("r,v", _CASES)
def test_phi_h_equals_atan_lambda_dot_times_t_go(r, v):
    """The identity the whole cue rests on: phi_h = atan(lambda_dot * t_go), for t_go = R/Vc.

    This is what makes the miss phase reachable from the seeker's own LOS rate instead of from a metric
    relative state we cannot measure passively.
    """
    exact = from_relative_state(r, v)
    R = float(np.linalg.norm(r))
    Vc = -float(np.asarray(r) @ np.asarray(v)) / R
    t_go = t_go_from_range_rate(R, Vc)

    approx = from_los_rate(exact.lambda_dot_radps, t_go)
    assert math.degrees(abs(approx.phi_h_rad - exact.phi_h_rad)) < 0.01


@pytest.mark.parametrize("r,v", _CASES)
def test_miss_ratio_is_invariant_to_the_range_scale(r, v):
    """phi_h and the normalised miss are angles between directions, so scaling the range leaves them alone.
    (The metric miss does scale -- that part genuinely needs range.)"""
    base = from_relative_state(r, v)
    scaled = from_relative_state(np.asarray(r) * 3.0, v)
    assert abs(scaled.miss_ratio - base.miss_ratio) < 1e-9
    assert abs(scaled.phi_h_rad - base.phi_h_rad) < 1e-9
    assert scaled.miss_m > base.miss_m * 2.5


def test_collision_course_is_range_free():
    """The load-bearing property: a constant bearing means a collision course, and asserting that needs
    NO range, NO target size and NO filter -- which is the only commit evidence a passive seeker can
    produce on its own."""
    head_on = from_los_rate(0.0)                      # perfectly constant bearing
    assert head_on.on_collision_course
    assert head_on.t_go_s is None and head_on.source == "los-rate-only"

    crossing = from_los_rate(0.4)                     # bearing sweeping fast -> not a collision course
    assert not crossing.on_collision_course


def test_zero_miss_when_exactly_on_collision_course():
    """Relative velocity straight down the LOS -> zero miss, zero miss phase, zero LOS rate."""
    r = np.array([30.0, 40.0, 100.0])
    g = from_relative_state(r, -r * 0.3)              # v anti-parallel to r
    assert g.miss_m < 1e-9 and g.phi_h_rad < 1e-9
    assert abs(g.lambda_dot_radps) < 1e-12 and g.on_collision_course


def test_t_go_declines_to_manufacture_a_terminal_cue_when_not_closing():
    """An opening or stationary geometry must not be able to produce a t_go -- otherwise a receding target
    could satisfy a terminal commit criterion."""
    assert t_go_from_range_rate(50.0, -10.0) is None
    assert t_go_from_range_rate(50.0, 0.0) is None
    assert t_go_from_range_rate(50.0, 25.0) == pytest.approx(2.0)


def test_t_go_uses_the_cpa_form_not_the_biased_range_over_rate():
    """Palumbo eq. 44 (time to CPA) differs from the naive R/Rdot (eq. 41) off head-on; we must use the
    CPA form for the exact geometry so the commit gate is not biased in crossing engagements."""
    r, v = (30.0, 40.0, 100.0), (-3.0, -11.0, -35.0)
    exact = from_relative_state(r, v)
    R = float(np.linalg.norm(r))
    naive = t_go_from_range_rate(R, -float(np.asarray(r) @ np.asarray(v)) / R)
    assert exact.t_go_s < naive                       # CPA arrives before the range-rate extrapolation
    assert abs(exact.t_go_s - naive) > 0.01


def test_degenerate_inputs_return_no_cue_rather_than_a_wrong_one():
    g = from_relative_state((0.0, 0.0, 0.0), (0.0, 0.0, -30.0))
    assert g.t_go_s is None and g.miss_ratio is None
    assert from_los_rate(0.02, 0.0).t_go_s is None
    assert from_los_rate(0.02, float("inf")).t_go_s is None


def test_collision_threshold_is_above_the_seeker_noise_floor():
    """Guard the tuning: the threshold must not be so tight that it gates on seeker noise. ~0.3 deg of
    bearing noise at 50 Hz is ~0.26 rad/s of apparent rate on a single frame pair."""
    assert COLLISION_LAMBDA_DOT_RADPS > math.radians(0.3) * 2
