"""MARCH protocol: inertial-trajectory dead-reckon + slew-to-cue reacquisition beyond the FOV."""

from __future__ import annotations

from fpv_ai.bench.march_sim import MarchConfig, run_march


def test_march_reacquires_a_target_that_left_the_fov():
    """With MARCH the gimbal slews to the predicted inertial bearing during the occlusion, so the target
    re-enters the narrow FOV and re-locks. Without MARCH (hold) the target ends up tens of degrees
    off-frame -- unreachable by any pixel-gate expansion."""
    off = run_march(march=False)
    on = run_march(march=True)
    assert not off.reacquired, "holding the gimbal must lose a target that moved off-frame"
    assert off.max_offframe_deg > 60.0, f"target should end far off-frame without MARCH, {off.max_offframe_deg:.0f}°"
    assert on.reacquired, "MARCH must slew-to-cue and reacquire the target when it reappears"
    assert on.t_reacquire_s is not None and on.t_reacquire_s < 2.5


def test_march_keeps_the_prediction_near_truth_through_the_gap():
    """The dead-reckon estimate holds the gimbal close to the true bearing through the blind window
    (constant-velocity target it learned before the loss)."""
    on = run_march(march=True)
    assert on.max_offframe_deg < 10.0, f"MARCH should track within the FOV, peaked {on.max_offframe_deg:.1f}°"


def test_march_gives_up_when_dead_reckon_window_is_blown():
    """Honest limit: if the target stays hidden past the MARCH budget the state reaches LOST (no infinite
    hunt on a diverging dead-reckon)."""
    cfg = MarchConfig(occl_end_s=99.0, march_budget_s=0.6, tmax=3.0)   # never reappears
    r = run_march(cfg, march=True)
    assert not r.reacquired
    assert any(row["state"] == "LOST" for row in r.log), "must reach LOST once the budget is exceeded"
