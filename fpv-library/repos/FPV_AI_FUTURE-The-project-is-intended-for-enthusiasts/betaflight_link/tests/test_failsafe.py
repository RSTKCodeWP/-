"""Tests for the failsafe / watchdog layer (Block-3 S4)."""

from __future__ import annotations

import pytest

from fpv_ai.betaflight_link.arming import ArmingStateMachine, ArmState
from fpv_ai.betaflight_link.failsafe import (
    FailsafeAction,
    FailsafeConfig,
    FailsafeController,
    Watchdog,
)
from fpv_ai.betaflight_link.tests.test_arming import live_auth


# ── Watchdog ─────────────────────────────────────────────────────────────────────
def test_watchdog_unfed_is_not_healthy():
    wd = Watchdog(0.2)
    assert wd.healthy(0.0) is False
    assert wd.silent_for(0.0) is None


def test_watchdog_healthy_within_timeout():
    wd = Watchdog(0.2)
    wd.feed(1.0)
    assert wd.healthy(1.0) is True
    assert wd.healthy(1.2) is True      # exactly at timeout
    assert wd.healthy(1.21) is False    # just past
    assert wd.silent_for(1.15) == pytest.approx(0.15)


def test_watchdog_ignores_non_finite():
    wd = Watchdog(0.2)
    wd.feed(float("nan"))               # not a valid heartbeat
    assert wd.healthy(0.0) is False
    wd.feed(1.0)
    assert wd.healthy(float("inf")) is False  # non-finite now -> not healthy


def test_watchdog_rejects_bad_timeout():
    with pytest.raises(ValueError):
        Watchdog(0.0)


# ── FailsafeController ───────────────────────────────────────────────────────────
def test_all_fresh_is_continue():
    fc = FailsafeController()
    fc.on_telemetry(1.0)
    fc.on_guidance(1.0)
    d = fc.evaluate(1.05)
    assert d.action == FailsafeAction.CONTINUE


def test_stale_guidance_holds_last():
    fc = FailsafeController()
    fc.on_telemetry(1.0)
    fc.on_guidance(1.0)
    d = fc.evaluate(1.15)               # 0.15s guidance gap: > hold(0.1), < abort(0.5)
    assert d.action == FailsafeAction.HOLD_LAST
    assert d.reason == "guidance_stale_coast"


def test_long_guidance_gap_aborts():
    fc = FailsafeController()
    fc.on_telemetry(2.0)               # link kept alive
    fc.on_guidance(1.0)
    fc.on_telemetry(1.6)
    d = fc.evaluate(1.6)               # guidance gap 0.6s > abort(0.5), link fresh
    assert d.action == FailsafeAction.ABORT
    assert d.reason == "guidance_lost"


def test_link_loss_aborts_and_dominates():
    fc = FailsafeController()
    fc.on_telemetry(1.0)
    fc.on_guidance(1.0)
    d = fc.evaluate(1.3)               # link silent 0.3s > 0.2 -> ABORT regardless of guidance
    assert d.action == FailsafeAction.ABORT
    assert d.reason == "link_loss_timeout"


def test_no_signals_aborts():
    fc = FailsafeController()
    assert fc.evaluate(0.0).action == FailsafeAction.ABORT


def test_non_finite_clock_aborts():
    fc = FailsafeController()
    fc.on_telemetry(1.0)
    fc.on_guidance(1.0)
    assert fc.evaluate(float("nan")).action == FailsafeAction.ABORT


def test_backwards_clock_aborts():
    # a clock that jumps backwards must NOT read as "fresh" -> fail safe to ABORT
    fc = FailsafeController()
    fc.on_telemetry(1000.0)
    fc.on_guidance(1000.0)
    assert fc.evaluate(0.0).action == FailsafeAction.ABORT       # link watchdog fooled? no.
    assert fc.evaluate(999.0).action == FailsafeAction.ABORT     # 1s backwards


def test_watchdog_backwards_clock_not_healthy():
    wd = Watchdog(0.5)
    wd.feed(1000.0)
    assert wd.healthy(999.0) is False     # backwards
    assert wd.healthy(1000.0) is True     # same instant ok
    assert wd.healthy(1000.4) is True


def test_config_validation():
    with pytest.raises(ValueError):
        FailsafeConfig(guidance_hold_s=0.6, guidance_abort_s=0.5)  # hold must be < abort


# ── integration: link loss disarms the arming core ───────────────────────────────
def test_link_loss_disarms_armed_aircraft():
    sm = ArmingStateMachine()
    sm.authorize(live_auth())
    sm.tick(0.0); sm.tick(0.0)         # -> ARMED_IDLE
    assert sm.is_armed is True

    fc = FailsafeController()
    fc.on_telemetry(0.0)
    fc.on_guidance(0.0)
    # link goes silent; at t=0.3 the failsafe fires and we wire ABORT -> arming
    decision = fc.evaluate(0.3)
    assert decision.action == FailsafeAction.ABORT
    sm.abort(decision.reason)
    out = sm.tick(0.3)
    assert out.state == ArmState.KILLED
    assert out.reason == "link_loss_timeout"
    assert out.armed is False
