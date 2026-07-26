"""Tests for the autonomous mission-chain supervisor (mission_fsm.py)."""

from __future__ import annotations

import math

from fpv_ai.betaflight_link.engage_fsm import EngageConfig, EngagePhase
from fpv_ai.betaflight_link.mission_fsm import (
    MissionAction,
    MissionController,
    MissionInputs,
    MissionPhase,
    freeze_reference,
)

_SNAP = {
    "class_label": "winged_uav", "class_confidence": 0.94,
    "silhouette_major_px": 22.0, "silhouette_minor_px": 7.0, "silhouette_orientation_rad": 0.1,
    "signature_peak": 1850.0, "signature_snr": 26.0,
    "az_rad": 0.01, "el_rad": -0.02, "az_rate_radps": 0.03, "el_rate_radps": 0.0,
    "range_m": 180.0, "closing_mps": 55.0,
}


def _inp(now=0.0, **kw) -> MissionInputs:
    return MissionInputs(now=now, **kw)


# ---------------------------------------------------------------------------
# Pre-trigger progression + regression (Axis I, revertible default-DENY)
# ---------------------------------------------------------------------------

def test_prelaunch_progression_idle_to_ready():
    m = MissionController()
    assert m.step(_inp(cued=False)).phase is MissionPhase.IDLE
    assert m.step(_inp(cued=True)).phase is MissionPhase.ACQUIRE
    assert m.step(_inp(cued=True, in_fov=True, lock_stable=True)).phase is MissionPhase.STUDY
    d = m.step(_inp(cued=True, in_fov=True, lock_stable=True, reference_ready=True, class_asserted=True))
    assert d.phase is MissionPhase.READY
    # default-DENY throughout: kinetic is NOT authorised in any pre-trigger phase.
    assert d.kinetic_authorized is False and d.action is MissionAction.OBSERVE


def test_prelaunch_regresses_on_lock_loss():
    m = MissionController()
    m.step(_inp(cued=True, in_fov=True, lock_stable=True, reference_ready=True, class_asserted=True))
    assert m.phase is MissionPhase.READY
    # Lose the lock -> automatically regress to ACQUIRE (pre-trigger is revertible).
    assert m.step(_inp(cued=True, in_fov=False, lock_stable=False)).phase is MissionPhase.ACQUIRE


def test_operator_cancel_reverts_to_idle():
    m = MissionController()
    m.step(_inp(cued=True, in_fov=True, lock_stable=True, reference_ready=True, class_asserted=True))
    d = m.step(_inp(now=1.0, operator_cancel=True, cued=True, in_fov=True, lock_stable=True))
    assert d.phase is MissionPhase.IDLE and d.reason == "operator_cancel" and d.kinetic_authorized is False


# ---------------------------------------------------------------------------
# The operator commit gate (default-DENY ends only on a valid trigger)
# ---------------------------------------------------------------------------

def _to_ready(m: MissionController):
    return m.step(_inp(cued=True, in_fov=True, lock_stable=True, reference_ready=True, class_asserted=True))


def test_trigger_denied_when_not_ready():
    m = MissionController()
    # Trigger while still only ACQUIRE (no reference) -> DENIED, never launches.
    d = m.step(_inp(cued=True, in_fov=True, lock_stable=False, operator_trigger=True,
                    authorization_valid=True, reference_snapshot=_SNAP))
    assert d.phase in (MissionPhase.ACQUIRE, MissionPhase.IDLE)
    assert d.kinetic_authorized is False and "denied" in d.reason


def test_trigger_denied_without_authorization():
    m = MissionController()
    _to_ready(m)
    d = m.step(_inp(cued=True, in_fov=True, lock_stable=True, reference_ready=True, class_asserted=True,
                    operator_trigger=True, authorization_valid=False, reference_snapshot=_SNAP))
    assert d.phase is MissionPhase.READY and d.kinetic_authorized is False and "denied" in d.reason
    assert m.reference is None


def test_valid_commit_freezes_reference_and_authorizes_kinetic():
    m = MissionController()
    _to_ready(m)
    d = m.step(_inp(now=2.0, cued=True, in_fov=True, lock_stable=True, reference_ready=True,
                    class_asserted=True, operator_trigger=True, authorization_valid=True,
                    reference_snapshot=_SNAP))
    assert d.phase is MissionPhase.ENGAGING and d.reason == "operator_commit"
    assert d.kinetic_authorized is True                 # default-DENY has ended
    # The immutable reference is frozen, bound to the operator commit.
    ref = m.reference
    assert ref is not None and ref.class_label == "winged_uav"
    assert ref.range_m == 180.0 and ref.closing_mps == 55.0 and ref.frozen_at_s == 2.0
    assert len(ref.reference_hash) == 64                # sha256 hex


def test_reference_hash_is_reproducible_and_binds_the_snapshot():
    a = freeze_reference(_SNAP, now=1.0)
    b = freeze_reference(_SNAP, now=1.0)
    assert a.reference_hash == b.reference_hash and len(a.reference_hash) == 64
    # A different target (bigger silhouette) yields a different reference identity.
    c = freeze_reference({**_SNAP, "silhouette_major_px": 40.0}, now=1.0)
    assert c.reference_hash != a.reference_hash


# ---------------------------------------------------------------------------
# Post-trigger: default-COMPLETE (Axis II) + hard self-safe only
# ---------------------------------------------------------------------------

def _commit(m: MissionController, now=0.0):
    _to_ready(m)
    return m.step(_inp(now=now, cued=True, in_fov=True, lock_stable=True, reference_ready=True,
                       class_asserted=True, operator_trigger=True, authorization_valid=True,
                       reference_snapshot=_SNAP))


def test_cancel_is_ignored_after_commit():
    # POST-trigger the seeker is a doer, not a doubter: an operator cancel does NOT abort (default-COMPLETE).
    m = MissionController()
    _commit(m, now=0.0)
    d = m.step(_inp(now=0.1, launched=True, in_fov=True, operator_cancel=True,
                    range_to_target_m=300.0, guidance_age_s=0.0))
    assert d.phase is MissionPhase.ENGAGING and d.kinetic_authorized is True   # cancel ignored


def test_hard_self_safe_still_aborts_after_commit():
    # A HARD self-safe (guidance ROE abort) DOES abort post-commit.
    m = MissionController()
    _commit(m, now=0.0)
    d = m.step(_inp(now=0.1, launched=True, in_fov=True, guidance_abort=True, guidance_age_s=0.0))
    assert d.phase is MissionPhase.ABORTED and d.action is MissionAction.ABORT
    assert m.step(_inp(now=0.2)).phase is MissionPhase.ABORTED   # sticky


def test_full_happy_path_to_intercept():
    m = MissionController(EngageConfig(commit_range_m=50.0))
    # cue -> ready -> commit
    d = _commit(m, now=0.0)
    assert d.phase is MissionPhase.ENGAGING
    # launch -> midcourse (link healthy, far)
    d = m.step(_inp(now=0.1, launched=True, in_fov=True, link_healthy=True,
                    range_to_target_m=300.0, guidance_age_s=0.0, t_go_s=5.0))
    assert d.engage_phase is EngagePhase.MIDCOURSE and d.kinetic_authorized is True
    # terminal commit (range <= 50) then intercept
    d = m.step(_inp(now=0.2, launched=True, in_fov=True, range_to_target_m=40.0,
                    guidance_age_s=0.0, t_go_s=0.4, intercepted=True))
    assert d.phase is MissionPhase.COMPLETE and d.action is MissionAction.CONTINUE
    assert m.step(_inp(now=0.3)).phase is MissionPhase.COMPLETE   # sticky


def test_non_finite_clock_fails_safe():
    m = MissionController()
    d = m.step(_inp(now=float("nan"), cued=True))
    assert d.phase is MissionPhase.ABORTED and d.kinetic_authorized is False
