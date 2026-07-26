"""Safety-core tests for the arming / throttle-authority state machine (Block-3 S4).

Every hard invariant has its own test. A failure here is a flight-safety failure.
The FIRE keypress lives inside the authorization (keypress_recorded + keypress_ts); there
is no free-floating press to go stale -- the regression tests below lock that in.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from fpv_ai.betaflight_link import msp_codec as mc
from fpv_ai.betaflight_link.arming import (
    ArmingAuthorization,
    ArmingConfig,
    ArmingStateMachine,
    ArmState,
)

CFG = ArmingConfig()
ARM_HI = CFG.arm_aux_us       # 2000
ARM_LO = CFG.disarm_aux_us    # 1000
IDLE = CFG.idle_us            # 1000


def live_auth(now: float = 0.0, ttl: float = 100.0, *, keypress_ts: float | None = None,
              keypress: bool = True, synthetic: bool = False, verified: bool = True) -> ArmingAuthorization:
    return ArmingAuthorization(
        verifier_passed=verified,
        keypress_recorded=keypress,
        keypress_ts=now if keypress_ts is None else keypress_ts,
        issued_at_s=now,
        expires_at_s=now + ttl,
        synthetic=synthetic,
        mission_goal="KINETIC",
    )


@dataclass
class _Cmd:
    roll_cmd: float
    pitch_cmd: float
    yaw_rate_cmd: float
    throttle_cmd: float


def _to_armed_idle(sm: ArmingStateMachine, t: float = 0.0) -> None:
    sm.authorize(live_auth(now=t))
    sm.tick(t)          # SAFE -> PREARM
    sm.tick(t)          # PREARM -> ARMED_IDLE (committed authorization)


# ── invariant 1: AUX1 arm channel ────────────────────────────────────────────────
def test_initial_state_is_safe_and_disarmed():
    out = ArmingStateMachine().tick(0.0)
    assert out.state == ArmState.SAFE and out.armed is False
    assert out.rc["aux1"] == ARM_LO and out.rc["throttle"] == IDLE


def test_aux_low_in_safe_prearm_killed_high_when_armed():
    sm = ArmingStateMachine()
    assert sm.tick(0.0).rc["aux1"] == ARM_LO                 # SAFE
    sm.authorize(live_auth())
    assert sm.tick(0.0).rc["aux1"] == ARM_LO                 # PREARM
    assert sm.tick(0.0).rc["aux1"] == ARM_HI                 # ARMED_IDLE
    sm.kill()
    assert sm.tick(0.0).rc["aux1"] == ARM_LO                 # KILLED


# ── invariant 2: arm gate (committed authorization) ──────────────────────────────
def test_uncommitted_auth_never_arms():
    # verifier ok + unexpired, but NO keypress recorded -> stays PREARM forever
    sm = ArmingStateMachine()
    sm.authorize(live_auth(keypress=False))
    assert sm.tick(0.0).state == ArmState.PREARM
    assert sm.tick(0.0).state == ArmState.PREARM
    assert sm.tick(0.0).armed is False


def test_keypress_before_authorization_does_not_arm():
    # THE regression: a press whose timestamp predates the authorization window must NOT commit it
    sm = ArmingStateMachine()
    sm.authorize(live_auth(now=30.0, keypress_ts=5.0))  # press at t=5, auth issued at t=30
    assert sm.tick(30.0).state == ArmState.PREARM
    out = sm.tick(30.0)
    assert out.state == ArmState.PREARM
    assert out.armed is False


def test_keypress_after_expiry_does_not_arm():
    sm = ArmingStateMachine()
    sm.authorize(live_auth(now=0.0, ttl=10.0, keypress_ts=20.0))  # press after expiry
    sm.tick(0.0)
    assert sm.tick(0.0).state == ArmState.PREARM
    assert sm.tick(0.0).armed is False


def test_expired_authorization_never_arms():
    sm = ArmingStateMachine()
    sm.authorize(live_auth(now=0.0, ttl=0.0))   # already expired at now=0
    assert sm.tick(0.0).state == ArmState.SAFE
    assert sm.tick(0.0).armed is False


def test_unverified_authorization_never_arms():
    sm = ArmingStateMachine()
    sm.authorize(live_auth(verified=False))
    assert sm.tick(0.0).state == ArmState.SAFE


def test_synthetic_auth_blocked_live_allowed_on_bench():
    syn = live_auth(synthetic=True)
    live_sm = ArmingStateMachine()                              # LIVE default
    live_sm.authorize(syn)
    live_sm.tick(0.0)
    assert live_sm.tick(0.0).state == ArmState.SAFE             # synthetic cannot arm live
    bench_sm = ArmingStateMachine(ArmingConfig(allow_synthetic_bench=True))
    bench_sm.authorize(syn)
    bench_sm.tick(0.0)
    assert bench_sm.tick(0.0).state == ArmState.ARMED_IDLE      # bench may arm synthetic


def test_arm_happens_at_idle_throttle():
    sm = ArmingStateMachine()
    _to_armed_idle(sm)
    assert sm.tick(0.0).rc["throttle"] == IDLE


# ── invariant 3: kill dominance & stickiness ─────────────────────────────────────
def test_kill_from_safe():
    sm = ArmingStateMachine()
    sm.kill()
    out = sm.tick(0.0)
    assert out.state == ArmState.KILLED and out.armed is False
    assert out.rc["aux1"] == ARM_LO and out.rc["throttle"] == IDLE


def test_kill_dominates_a_committed_authorization():
    sm = ArmingStateMachine()
    sm.authorize(live_auth())
    sm.tick(0.0)          # -> PREARM (committed auth present, would arm next tick)
    sm.kill()
    assert sm.tick(0.0).state == ArmState.KILLED


def test_kill_is_sticky_until_reset():
    sm = ArmingStateMachine()
    sm.kill("operator_abort")
    assert sm.tick(0.0).state == ArmState.KILLED
    sm.authorize(live_auth())                  # ignored while killed
    assert sm.tick(0.0).state == ArmState.KILLED
    sm.reset()
    assert sm.tick(0.0).state == ArmState.SAFE
    sm.authorize(live_auth())
    sm.tick(0.0)
    assert sm.tick(0.0).state == ArmState.ARMED_IDLE   # re-arm requires fresh committed auth


def test_abort_disarms():
    sm = ArmingStateMachine()
    _to_armed_idle(sm)
    sm.abort("geofence_exit")
    out = sm.tick(0.0)
    assert out.state == ArmState.KILLED and out.reason == "geofence_exit"


# ── invariant 4: throttle handoff & ramp ─────────────────────────────────────────
def test_full_sequence_to_ai_active():
    sm = ArmingStateMachine()
    sm.authorize(live_auth())
    assert sm.tick(0.0).state == ArmState.PREARM
    assert sm.tick(0.0).state == ArmState.ARMED_IDLE
    assert sm.tick(0.3).state == ArmState.STABILIZE
    assert sm.tick(0.6).state == ArmState.THROTTLE_RAMP
    mid = sm.tick(1.1)
    assert mid.state == ArmState.THROTTLE_RAMP and IDLE < mid.rc["throttle"] < CFG.hover_base_us
    assert sm.tick(1.6).state == ArmState.AI_ACTIVE


def test_throttle_ramp_is_monotonic_and_bounded():
    sm = ArmingStateMachine()
    sm.authorize(live_auth())
    sm.tick(0.0); sm.tick(0.0); sm.tick(0.3); sm.tick(0.6)  # entered THROTTLE_RAMP at 0.6
    last = IDLE
    for t in (0.6, 0.8, 1.0, 1.3, 1.55):
        thr = sm.tick(t).rc["throttle"]
        assert IDLE <= thr <= CFG.hover_base_us and thr >= last
        last = thr


def test_ai_active_passes_guidance_throttle_and_attitude():
    sm = ArmingStateMachine()
    sm.authorize(live_auth())
    sm.tick(0.0); sm.tick(0.0); sm.tick(0.3); sm.tick(0.6); sm.tick(1.7)  # -> AI_ACTIVE
    out = sm.tick(1.8, _Cmd(roll_cmd=1.0, pitch_cmd=0.0, yaw_rate_cmd=-1.0, throttle_cmd=0.5))
    assert out.state == ArmState.AI_ACTIVE
    assert out.rc["roll"] == 2000 and out.rc["yaw"] == 1000
    assert out.rc["throttle"] == mc.throttle_to_us(0.5)
    assert out.rc["aux1"] == ARM_HI


def test_ai_active_safe_hold_without_command():
    sm = ArmingStateMachine()
    sm.authorize(live_auth())
    sm.tick(0.0); sm.tick(0.0); sm.tick(0.3); sm.tick(0.6)
    out = sm.tick(1.7, None)
    assert out.state == ArmState.AI_ACTIVE
    assert out.rc["throttle"] == CFG.hover_base_us and out.rc["roll"] == CFG.neutral_us


def test_ai_active_nan_command_degrades_to_neutral_idle():
    # a degenerate guidance command (NaN/inf) must not crash the loop or command high throttle
    sm = ArmingStateMachine()
    sm.authorize(live_auth())
    sm.tick(0.0); sm.tick(0.0); sm.tick(0.3); sm.tick(0.6); sm.tick(1.7)
    nan = float("nan")
    out = sm.tick(1.8, _Cmd(roll_cmd=nan, pitch_cmd=float("inf"), yaw_rate_cmd=nan, throttle_cmd=nan))
    assert out.state == ArmState.AI_ACTIVE
    assert out.rc["roll"] == CFG.neutral_us
    assert out.rc["throttle"] == IDLE   # NaN throttle -> idle, never high


# ── invariant 5: expiry while armed ──────────────────────────────────────────────
def test_authorization_expiry_in_flight_aborts():
    sm = ArmingStateMachine()
    sm.authorize(live_auth(now=0.0, ttl=0.2))
    sm.tick(0.0); sm.tick(0.0)
    assert sm.tick(0.1).state == ArmState.ARMED_IDLE
    out = sm.tick(0.3)                                    # auth expired at 0.2
    assert out.state == ArmState.KILLED and out.reason == "authorization_expired"


def test_non_finite_clock_never_arms():
    # a NaN/inf clock must not pass the (now < expires) check and arm the aircraft
    for bad in (float("nan"), float("inf"), float("-inf")):
        sm = ArmingStateMachine()
        sm.authorize(live_auth())          # committed, finite window
        out1 = sm.tick(bad)
        out2 = sm.tick(bad)
        assert out1.armed is False and out2.armed is False
        assert out1.state == ArmState.KILLED


def test_non_finite_clock_aborts_in_flight():
    sm = ArmingStateMachine()
    _to_armed_idle(sm)                      # ARMED with a finite clock
    assert sm.is_armed is True
    out = sm.tick(float("nan"))            # clock glitches to NaN while armed
    assert out.state == ArmState.KILLED
    assert out.reason == "non_finite_clock"
    assert out.armed is False


def test_non_finite_auth_window_does_not_arm():
    # a malformed authorization with NaN/inf timestamps must default-deny, not arm
    for field in ("expires", "issued", "keypress"):
        sm = ArmingStateMachine()
        bad = {
            "expires": ArmingAuthorization(True, True, 0.0, 0.0, float("inf"), synthetic=False),
            "issued": ArmingAuthorization(True, True, 0.0, float("nan"), 100.0, synthetic=False),
            "keypress": ArmingAuthorization(True, True, float("nan"), 0.0, 100.0, synthetic=False),
        }[field]
        sm.authorize(bad)
        sm.tick(0.0)
        assert sm.tick(0.0).state != ArmState.ARMED_IDLE, f"{field} non-finite armed!"


def test_is_armed_property():
    sm = ArmingStateMachine()
    assert sm.is_armed is False
    _to_armed_idle(sm)
    assert sm.is_armed is True
    sm.kill(); sm.tick(0.0)
    assert sm.is_armed is False


# ── config validation ────────────────────────────────────────────────────────────
def test_config_rejects_zero_ramp():
    with pytest.raises(ValueError):
        ArmingConfig(ramp_s=0.0)
