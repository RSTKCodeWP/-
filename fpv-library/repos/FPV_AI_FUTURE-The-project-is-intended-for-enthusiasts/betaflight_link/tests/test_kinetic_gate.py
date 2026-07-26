"""Tests for the kinetic-release confluence gate (kinetic_gate.py)."""

from __future__ import annotations

from types import SimpleNamespace

from contracts.engagement_handoff import build_kill_handoff
from fpv_ai.betaflight_link.engage_fsm import EngagePhase
from fpv_ai.betaflight_link.kinetic_gate import compose_kinetic_release

NOW = "2026-07-08T10:00:00Z"
FUTURE = "2026-07-08T11:00:00Z"
PAST = "2026-07-08T09:00:00Z"
_BOX = {"center_lat": 50.0, "center_lon": 30.0, "radius_m": 400.0}
_REF = SimpleNamespace(reference_hash="ref_abc")


def _handoff(ref_hash="ref_abc", expires=FUTURE, confirmed=True):
    return build_kill_handoff(handoff_id="h", authorization_id="a", authorization_hash="ah",
                              target_reference_hash=ref_hash, kill_box=_BOX, issued_at_utc=NOW,
                              expires_at_utc=expires, target_confirmed_nonresponsive=confirmed)


def _compose(**kw):
    base = dict(kinetic_authorized=True, engage_phase=EngagePhase.COMMITTED, mission_reference=_REF,
                handoff=_handoff(), now_utc=NOW, authorization_valid=True)
    base.update(kw)
    return compose_kinetic_release(**base)


def test_all_gates_pass_releases():
    r = _compose()
    assert r.released is True and "all gates passed" in r.reason
    assert r.target_reference_hash == "ref_abc"


def test_gate1_not_committed():
    r = _compose(kinetic_authorized=False)
    assert r.released is False and "gate 1" in r.reason and "not committed" in r.reason


def test_gate2_not_terminal():
    r = _compose(engage_phase=EngagePhase.MIDCOURSE)
    assert r.released is False and "gate 2" in r.reason and "MIDCOURSE" in r.reason


def test_gate3_no_handoff():
    r = _compose(handoff=None)
    assert r.released is False and "gate 3" in r.reason and "no engagement hand-off" in r.reason


def test_gate3_invalid_handoff_expired():
    r = _compose(handoff=_handoff(expires=PAST))
    assert r.released is False and "gate 3" in r.reason and "expired" in r.reason


def test_gate3_invalid_handoff_unconfirmed_threat():
    r = _compose(handoff=_handoff(confirmed=False))
    assert r.released is False and "gate 3" in r.reason and "non-responsive threat" in r.reason


def test_gate4_reference_mismatch_refuses_substituted_target():
    # THE Axis-III enforcement at the effector: a hand-off for a DIFFERENT target hash is refused.
    r = _compose(handoff=_handoff(ref_hash="some_other_target"))
    assert r.released is False and "gate 4" in r.reason and "does NOT match" in r.reason


def test_gate4_no_frozen_reference():
    r = _compose(mission_reference=None)
    assert r.released is False and "gate 4" in r.reason and "no frozen target reference" in r.reason
