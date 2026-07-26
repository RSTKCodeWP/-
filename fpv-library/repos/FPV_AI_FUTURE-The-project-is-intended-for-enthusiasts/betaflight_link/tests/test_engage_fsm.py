"""Tests for the commit-based fire-and-forget engagement / abort FSM (Phase C).

The load-bearing behaviour: link loss ABORTS in MIDCOURSE (pre-commit) but is IGNORED once COMMITTED
(the interceptor completes the terminal engagement autonomously), while the self-contained rules
(geo/alt keep-out, TTL, ROE, target-lost) abort in BOTH phases.
"""

from __future__ import annotations

import math

from fpv_ai.betaflight_link.engage_fsm import (
    EngageAction,
    EngageConfig,
    EngageInputs,
    EngagePhase,
    EngagementController,
)


def _inp(now: float = 0.0, **kw) -> EngageInputs:
    d = dict(
        now=now, launched=True, link_healthy=True, guidance_age_s=0.0,
        range_from_launch_m=100.0, altitude_m=50.0, t_go_s=float("inf"),
        range_to_target_m=200.0, in_fov=True, operator_authorized=True,
        target_confirmed=True, guidance_abort=False, model_wrong=False, intercepted=False)
    d.update(kw)
    return EngageInputs(**d)


def _committed() -> EngagementController:
    """A controller stepped into COMMITTED (terminal geometry, all criteria met)."""
    c = EngagementController()
    d = c.step(_inp(now=0.0, t_go_s=1.0))     # terminal -> commit
    assert c.phase is EngagePhase.COMMITTED, d
    return c


def test_pre_launch_then_launch():
    c = EngagementController()
    d = c.step(_inp(launched=False))
    assert c.phase is EngagePhase.PRE_LAUNCH and d.action is EngageAction.HOLD_LAST
    d = c.step(_inp(launched=True))
    assert c.phase is EngagePhase.MIDCOURSE and d.action is EngageAction.CONTINUE


def test_midcourse_link_loss_aborts():
    c = EngagementController()
    d = c.step(_inp(link_healthy=False))       # not terminal -> stays midcourse
    assert d.action is EngageAction.ABORT and d.reason == "link_loss_pre_commit"
    assert c.phase is EngagePhase.ABORTED


def test_commit_when_terminal_geometry():
    c = EngagementController()
    d = c.step(_inp(t_go_s=1.0))
    assert c.phase is EngagePhase.COMMITTED and d.action is EngageAction.CONTINUE
    # or via close range
    c2 = EngagementController()
    c2.step(_inp(range_to_target_m=40.0))
    assert c2.phase is EngagePhase.COMMITTED


def test_committed_link_loss_is_ignored():
    """THE fire-and-forget property: after commit, a lost link does NOT abort."""
    c = _committed()
    d = c.step(_inp(now=0.05, t_go_s=0.8, link_healthy=False))
    assert d.action is EngageAction.CONTINUE, "committed engagement must survive link loss"
    assert c.phase is EngagePhase.COMMITTED


def test_committed_keepout_box_breach_aborts():
    c = _committed()
    d = c.step(_inp(now=0.05, t_go_s=0.8, link_healthy=False, range_from_launch_m=600.0))
    assert d.action is EngageAction.ABORT and d.reason == "keepout_box_breach"


def test_committed_ttl_aborts():
    c = _committed()
    d = c.step(_inp(now=25.0, t_go_s=0.8, link_healthy=False))
    assert d.action is EngageAction.ABORT and d.reason == "ttl_exceeded"


def test_committed_target_lost_aborts():
    c = _committed()
    d = c.step(_inp(now=0.6, t_go_s=0.8, guidance_age_s=0.6))
    assert d.action is EngageAction.ABORT and d.reason == "target_lost"


def test_guidance_roe_abort_in_both_phases():
    for terminal in (float("inf"), 1.0):          # midcourse and committed
        c = EngagementController()
        c.step(_inp(t_go_s=terminal))
        d = c.step(_inp(now=0.05, t_go_s=terminal, guidance_abort=True))
        assert d.action is EngageAction.ABORT and d.reason == "guidance_roe_abort"


def test_altitude_keepout_breach_aborts():
    c = EngagementController()
    assert c.step(_inp(altitude_m=2.0)).reason == "keepout_box_breach"       # below floor
    c2 = EngagementController()
    assert c2.step(_inp(altitude_m=250.0)).reason == "keepout_box_breach"    # above ceiling


def test_aborted_is_sticky():
    c = EngagementController()
    c.step(_inp(link_healthy=False))
    assert c.phase is EngagePhase.ABORTED
    d = c.step(_inp())                             # fully healthy -> still aborted
    assert d.action is EngageAction.ABORT and c.phase is EngagePhase.ABORTED


def test_commit_blocked_without_authorization_or_confirmation():
    for kw in ({"operator_authorized": False}, {"target_confirmed": False}, {"model_wrong": True},
               {"in_fov": False}):
        c = EngagementController()
        c.step(_inp(t_go_s=1.0, **kw))             # terminal but a criterion missing
        assert c.phase is EngagePhase.MIDCOURSE, f"must not commit with {kw}"


def test_brief_guidance_gap_holds():
    c = EngagementController()
    d = c.step(_inp(guidance_age_s=0.2))           # between hold (0.1) and abort (0.5)
    assert d.action is EngageAction.HOLD_LAST and c.phase is EngagePhase.MIDCOURSE


def test_intercept_completes():
    c = _committed()
    d = c.step(_inp(now=0.05, t_go_s=0.2, intercepted=True))
    assert c.phase is EngagePhase.COMPLETE
    assert c.step(_inp(now=0.1)).action is EngageAction.CONTINUE   # sticky complete


# ── Collision-course gate on the commit (miss phase phi_h) ──────────────────────────────────────────────
# Committing latches fire-and-forget: the abort is disabled and a lost link stops stopping us. Being CLOSE
# should not be enough to earn that -- we should also be ON a collision course. phi_h is that check, and it
# is computable from the seeker's own LOS rate (phi_h = atan(lambda_dot * t_go)), so unlike the old range
# threshold it does not depend on an assumed target size.

def _terminal(**kw):
    """Inputs that satisfy every commit criterion except whatever the caller overrides."""
    return _inp(t_go_s=1.0, range_to_target_m=30.0, **kw)


def test_commit_gate_abstains_when_the_miss_phase_is_not_configured():
    """Shipped default: no limit configured -> behaves exactly as before, so enabling the cue cannot
    silently tighten an existing gate."""
    c = EngagementController(EngageConfig())
    c.step(_inp(t_go_s=float("inf")))
    assert c.step(_terminal(miss_phase_rad=1.4)).phase is EngagePhase.COMMITTED


def test_commit_gate_abstains_when_the_miss_phase_was_not_measured():
    """An UNMEASURED cue must not block a commit, the same way it must not grant one. Absence of evidence
    is not evidence -- the gate abstains and the other criteria decide."""
    c = EngagementController(EngageConfig(commit_max_phi_h_rad=math.radians(10.0)))
    c.step(_inp(t_go_s=float("inf")))
    assert c.step(_terminal(miss_phase_rad=None)).phase is EngagePhase.COMMITTED


def test_commit_is_refused_when_close_but_not_on_a_collision_course():
    """The point of the gate: terminal range alone must not latch fire-and-forget."""
    c = EngagementController(EngageConfig(commit_max_phi_h_rad=math.radians(10.0)))
    c.step(_inp(t_go_s=float("inf")))
    d = c.step(_terminal(miss_phase_rad=math.radians(35.0)))
    assert d.phase is EngagePhase.MIDCOURSE, "a 35 deg miss phase is not a collision course"


def test_commit_is_granted_on_a_real_collision_course():
    """And it must still pass what a genuine intercept looks like: measured phi_h in our own runs is
    ~3 deg median, 8 deg worst."""
    c = EngagementController(EngageConfig(commit_max_phi_h_rad=math.radians(10.0)))
    c.step(_inp(t_go_s=float("inf")))
    assert c.step(_terminal(miss_phase_rad=math.radians(3.0))).phase is EngagePhase.COMMITTED
