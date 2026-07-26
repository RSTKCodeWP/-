"""Betaflight fork V&V harness (Block-3 S4): the 3 mandatory bench gates + arbitration.

Arming requires a low->high arm-switch EDGE (matching the arming state machine's
disarm->arm AUX output and stock Betaflight). A kill/failsafe latches re-arm inhibit, so the
craft never auto-re-arms when a link returns. These gate ANY props-on test.
"""

from __future__ import annotations

import pytest

from fpv_ai.betaflight_link.fork_model import ControlSource, ForkConfig, ForkModel


def rc(*, throttle: int = 1000, aux1: int = 1000, aux2: int = 1000,
       roll: int = 1500, pitch: int = 1500, yaw: int = 1500) -> dict[str, int]:
    return {"roll": roll, "pitch": pitch, "yaw": yaw, "throttle": throttle,
            "aux1": aux1, "aux2": aux2, "aux3": 1000, "aux4": 1000}


def _arm_via_msp(fork: ForkModel, t: float = 0.0):
    """Realistic arm: a disarmed frame (switch low) then an armed frame (low->high edge)."""
    fork.msp_rc(t, rc(aux1=1000, throttle=1000))   # switch low -> clears inhibit
    fork.update(t)
    fork.msp_rc(t, rc(aux1=1800, throttle=1000))   # rising edge -> arm
    return fork.update(t)


# ── V&V-1: ELRS AUX-kill disarms WHILE MSP is actively overriding ─────────────────
def test_vv1_elrs_kill_disarms_while_msp_overrides():
    fork = ForkModel()
    s = _arm_via_msp(fork, 0.0)
    assert s.in_control == ControlSource.MSP and s.armed and s.motors_driven

    fork.msp_rc(0.05, rc(aux1=1800, throttle=1400))     # MSP STILL actively overriding
    assert fork.update(0.05).motors_driven is True

    fork.elrs_rc(0.05, rc(aux2=1900))                   # operator flips ELRS AUX-kill
    s = fork.update(0.05)
    assert s.in_control == ControlSource.ELRS
    assert s.armed is False and s.motors_driven is False
    assert s.reason == "elrs_kill"


# ── V&V-2: MSP silence -> RXFAIL -> ELRS handover within msp_timeout (<=200 ms) ───
def test_vv2_msp_silence_handover_within_200ms():
    fork = ForkModel(ForkConfig(msp_timeout_s=0.2))
    _arm_via_msp(fork, 0.0)
    fork.elrs_rc(0.0, rc())
    assert fork.update(0.0).in_control == ControlSource.MSP

    fork.elrs_rc(0.2, rc())
    assert fork.update(0.2).in_control == ControlSource.MSP        # exactly at timeout: still fresh
    fork.elrs_rc(0.2001, rc())
    s = fork.update(0.2001)                                         # just past -> handover
    assert s.in_control == ControlSource.ELRS and s.reason == "rxfail_elrs_handover"


# ── V&V-3: MSP override does NOT stop motors after arm (#13416 must not reproduce) ─
def test_vv3_motors_not_stopped_after_arm():
    fork = ForkModel()
    assert _arm_via_msp(fork, 0.0).armed is True
    fork.msp_rc(0.05, rc(aux1=1800, throttle=1500))     # override continues, throttle up
    s = fork.update(0.05)
    assert s.armed is True and s.motors_driven is True


# ── new safe behaviour: no auto-re-arm; latched ELRS kill ─────────────────────────
def test_no_auto_rearm_after_failsafe():
    fork = ForkModel()
    _arm_via_msp(fork, 0.0)
    assert fork.update(1.0).in_control == ControlSource.RX_FAILSAFE   # both stale -> disarm
    # MSP returns with the arm switch STILL high -> must NOT auto-re-arm (no fresh edge)
    fork.msp_rc(1.0, rc(aux1=1800, throttle=1000))
    assert fork.update(1.0).armed is False
    # operator deliberately re-commits: switch low, then high
    fork.msp_rc(1.0, rc(aux1=1000, throttle=1000)); fork.update(1.0)
    fork.msp_rc(1.0, rc(aux1=1800, throttle=1000))
    assert fork.update(1.0).armed is True


def test_elrs_kill_latches_through_dropout():
    fork = ForkModel()
    _arm_via_msp(fork, 0.0)
    fork.elrs_rc(0.0, rc(aux2=1900))                    # ELRS kill
    assert fork.update(0.0).armed is False
    # ELRS goes silent (> elrs_timeout); MSP keeps the arm switch high
    for t in (0.1, 0.6, 1.0):
        fork.msp_rc(t, rc(aux1=1800, throttle=1000))
        assert fork.update(t).armed is False           # kill survives the ELRS dropout


def test_held_high_switch_does_not_arm_at_boot():
    # default-deny: an arm switch already high at boot must NOT arm until cycled low->high
    fork = ForkModel()
    fork.msp_rc(0.0, rc(aux1=1800, throttle=1000))
    assert fork.update(0.0).armed is False


# ── arbitration invariants ───────────────────────────────────────────────────────
def test_no_rx_is_failsafe_disarmed():
    assert ForkModel().update(0.0).in_control == ControlSource.RX_FAILSAFE


def test_arm_requires_low_throttle():
    fork = ForkModel()
    fork.msp_rc(0.0, rc(aux1=1000, throttle=1000)); fork.update(0.0)   # prime the edge
    fork.msp_rc(0.0, rc(aux1=1800, throttle=1500))                     # high throttle
    assert fork.update(0.0).armed is False


def test_elrs_kill_dominant_even_when_msp_would_arm():
    fork = ForkModel()
    fork.msp_rc(0.0, rc(aux1=1800, throttle=1000))
    fork.elrs_rc(0.0, rc(aux2=1900))
    s = fork.update(0.0)
    assert s.armed is False and s.reason == "elrs_kill"


def test_backwards_and_non_finite_clock_are_safe():
    fork = ForkModel()
    fork.msp_rc(1000.0, rc(aux1=1800, throttle=1000))
    assert fork.update(999.0).in_control == ControlSource.RX_FAILSAFE     # backwards -> stale
    assert fork.update(float("nan")).in_control == ControlSource.RX_FAILSAFE


def test_config_validation():
    with pytest.raises(ValueError):
        ForkConfig(msp_timeout_s=0.0)
