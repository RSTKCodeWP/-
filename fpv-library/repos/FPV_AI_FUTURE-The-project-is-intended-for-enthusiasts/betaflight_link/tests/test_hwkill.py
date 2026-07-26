"""Tests for the independent hardware kill (Block-3 S4) -- the last line below the FC."""

from __future__ import annotations

import pytest

from fpv_ai.betaflight_link.arming import ArmingStateMachine
from fpv_ai.betaflight_link.hwkill import (
    HardwareKill,
    HardwareKillConfig,
    effective_motor_power,
)
from fpv_ai.betaflight_link.tests.test_arming import live_auth


# ── invariant 1: default-deny ────────────────────────────────────────────────────
def test_default_deny_no_beacon_no_power():
    hk = HardwareKill()
    assert hk.motor_power_enabled(0.0) is False
    assert hk.status(0.0).reason == "permit_beacon_lost"


# ── invariant 2: loss of signal ──────────────────────────────────────────────────
def test_power_enabled_only_while_beacon_fresh():
    hk = HardwareKill(HardwareKillConfig(beacon_timeout_s=0.5))
    hk.permit_beacon(1.0)
    assert hk.motor_power_enabled(1.0) is True
    assert hk.motor_power_enabled(1.5) is True      # at timeout
    assert hk.motor_power_enabled(1.51) is False    # beacon lost -> cut
    assert hk.status(1.51).reason == "permit_beacon_lost"


def test_beacon_loss_is_autonomous():
    # no further input after the last beacon: the cut happens on the MCU's own timer
    hk = HardwareKill(HardwareKillConfig(beacon_timeout_s=0.2))
    hk.permit_beacon(0.0)
    assert hk.motor_power_enabled(0.1) is True
    assert hk.motor_power_enabled(0.3) is False


# ── invariant 3: operator kill is latched/sticky ─────────────────────────────────
def test_operator_kill_is_latched_and_dominates_a_fresh_beacon():
    hk = HardwareKill()
    hk.permit_beacon(1.0)
    assert hk.motor_power_enabled(1.0) is True
    hk.operator_kill("mushroom")
    assert hk.motor_power_enabled(1.0) is False             # cut now
    hk.permit_beacon(1.0)                                    # a fresh beacon must NOT re-enable
    assert hk.motor_power_enabled(1.0) is False
    assert hk.status(1.0).reason == "latched_kill:mushroom"


def test_reset_then_fresh_beacon_re_enables():
    hk = HardwareKill()
    hk.permit_beacon(1.0)
    hk.operator_kill()
    assert hk.motor_power_enabled(1.0) is False
    hk.reset()
    # reset alone is not enough; power still requires a live beacon
    hk.permit_beacon(2.0)
    assert hk.motor_power_enabled(2.0) is True


# ── invariant 4: non-finite clock ────────────────────────────────────────────────
def test_non_finite_clock_cuts():
    hk = HardwareKill()
    hk.permit_beacon(1.0)
    assert hk.motor_power_enabled(float("nan")) is False
    assert hk.motor_power_enabled(float("inf")) is False


def test_backwards_clock_cuts():
    # a clock jumping backwards must NOT keep a stale permit alive -> power CUT
    hk = HardwareKill(HardwareKillConfig(beacon_timeout_s=0.5))
    hk.permit_beacon(1000.0)
    assert hk.motor_power_enabled(999.0) is False    # 1s backwards
    assert hk.motor_power_enabled(0.0) is False       # far backwards
    assert hk.motor_power_enabled(1000.0) is True     # forward again, fresh


def test_config_validation():
    with pytest.raises(ValueError):
        HardwareKillConfig(beacon_timeout_s=0.0)


# ── the hard veto: independent of the FC/arming state ────────────────────────────
def test_hw_kill_vetoes_an_armed_aircraft():
    # the arming core says ARMED (FC would spin motors), but the independent hw-kill
    # has no beacon -> effective motor power is OFF. The hw-kill is the dominant authority.
    sm = ArmingStateMachine()
    sm.authorize(live_auth())
    sm.tick(0.0); sm.tick(0.0)
    assert sm.is_armed is True

    hk = HardwareKill()                       # no permit beacon -> default-deny
    fc_commands_motors = sm.is_armed
    assert effective_motor_power(fc_commands_motors=fc_commands_motors,
                                 hw_kill_enabled=hk.motor_power_enabled(0.0)) is False


def test_effective_power_requires_both():
    assert effective_motor_power(fc_commands_motors=True, hw_kill_enabled=True) is True
    assert effective_motor_power(fc_commands_motors=True, hw_kill_enabled=False) is False
    assert effective_motor_power(fc_commands_motors=False, hw_kill_enabled=True) is False
