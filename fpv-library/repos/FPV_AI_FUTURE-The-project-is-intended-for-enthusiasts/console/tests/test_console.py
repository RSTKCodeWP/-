"""Launch console + verifier tests, and the FULL authorized engagement (console -> RC)."""

from __future__ import annotations

from dataclasses import replace

from fpv.seeker.thermal_sim import ThermalSceneConfig, ThermalSimulator
from fpv.guidance.pipeline import SeekerGuidancePipeline

from fpv_ai.betaflight_link.arming import ArmingConfig, ArmingStateMachine, ArmState
from fpv_ai.betaflight_link.failsafe import FailsafeController
from fpv_ai.betaflight_link.hwkill import HardwareKill
from fpv_ai.betaflight_link.onboard_runtime import OnboardRuntime
from fpv_ai.betaflight_link.serial_link import MockFcChannel, MspLink
from fpv_ai.console.console import ConsoleConfig, HandoffVerifier, LaunchConsole
from fpv_ai.console.handoff import (
    EngagementOrder,
    TargetRef,
    generate_keypair,
    sign_order,
)

DT = 1.0 / 60.0


def _keys():
    pk, pk_pub = generate_keypair()
    sk, sk_pub = generate_keypair()
    return pk, pk_pub, sk, sk_pub


def _order(now=0.0, *, goal="CONTACT", synthetic=True, roe=True, ttl=90.0, keypress=None):
    return EngagementOrder(
        handoff_id="hk-1", schema_version="engagement_handoff.v1",
        issued_at_s=now, expires_at_s=now + ttl, mission_goal=goal,
        target=TargetRef("trk-1", "hostile_uav", 1.0),
        keypress_ts=now if keypress is None else keypress, roe_pass=roe, synthetic=synthetic,
    )


# ── verifier ─────────────────────────────────────────────────────────────────────
def test_verifier_accepts_valid_dual_signed():
    pk, pk_pub, sk, sk_pub = _keys()
    v = HandoffVerifier({pk_pub, sk_pub})
    signed = sign_order(_order(), primary_key=pk, primary_pub=pk_pub, secondary_key=sk, secondary_pub=sk_pub)
    r = v.verify(signed, now=1.0)
    assert r.accepted and r.authorization.verifier_passed is True


def test_verifier_rejects_tampered_order():
    pk, pk_pub, sk, sk_pub = _keys()
    v = HandoffVerifier({pk_pub, sk_pub})
    signed = sign_order(_order(), primary_key=pk, primary_pub=pk_pub, secondary_key=sk, secondary_pub=sk_pub)
    tampered = replace(signed, order=replace(signed.order, mission_goal="KINETIC"))  # body changed, sigs stale
    r = v.verify(tampered, now=1.0)
    assert not r.accepted and "signature_invalid" in r.reason


def test_verifier_rejects_untrusted_and_single_key():
    pk, pk_pub, sk, sk_pub = _keys()
    rogue_key, rogue_pub, _, _ = _keys()   # a matching but UNTRUSTED keypair
    v = HandoffVerifier({pk_pub, sk_pub})
    # untrusted secondary
    s1 = sign_order(_order(), primary_key=pk, primary_pub=pk_pub, secondary_key=rogue_key, secondary_pub=rogue_pub)
    assert v.verify(s1, now=1.0).reason == "secondary_key_untrusted"
    # same key for both -> not dual-key
    s2 = sign_order(_order(), primary_key=pk, primary_pub=pk_pub, secondary_key=pk, secondary_pub=pk_pub)
    assert v.verify(s2, now=1.0).reason == "not_dual_key"


def test_verifier_rejects_expired_and_keypress_window():
    pk, pk_pub, sk, sk_pub = _keys()
    v = HandoffVerifier({pk_pub, sk_pub})
    s = sign_order(_order(now=0.0, ttl=10.0), primary_key=pk, primary_pub=pk_pub,
                   secondary_key=sk, secondary_pub=sk_pub)
    assert v.verify(s, now=20.0).reason == "expired"
    s2 = sign_order(_order(now=0.0, ttl=10.0, keypress=20.0), primary_key=pk, primary_pub=pk_pub,
                    secondary_key=sk, secondary_pub=sk_pub)
    assert v.verify(s2, now=5.0).reason == "keypress_out_of_window"


def test_verifier_blocks_synthetic_kinetic_live_and_roe_fail():
    pk, pk_pub, sk, sk_pub = _keys()
    v = HandoffVerifier({pk_pub, sk_pub}, allow_synthetic_bench=False)
    s = sign_order(_order(goal="KINETIC", synthetic=True), primary_key=pk, primary_pub=pk_pub,
                   secondary_key=sk, secondary_pub=sk_pub)
    assert v.verify(s, now=1.0).reason == "synthetic_kinetic_blocked"
    s2 = sign_order(_order(goal="KINETIC", synthetic=False, roe=False), primary_key=pk, primary_pub=pk_pub,
                    secondary_key=sk, secondary_pub=sk_pub)
    assert v.verify(s2, now=1.0).reason == "roe_fail"


# ── launch console ───────────────────────────────────────────────────────────────
def test_console_fire_requires_arm_key_and_positive_id():
    pk, pk_pub, sk, sk_pub = _keys()
    v = HandoffVerifier({pk_pub, sk_pub}, allow_synthetic_bench=True)
    c = LaunchConsole(verifier=v, primary_key=pk, primary_pub=pk_pub, secondary_key=sk, secondary_pub=sk_pub)
    assert c.press_fire(1.0) == (None, "no_arm_key")          # no secondary authority
    c.insert_arm_key()
    assert c.press_fire(1.0) == (None, "no_positive_id")      # no seeker lock
    c.update_seeker(locked=True)
    auth, reason = c.press_fire(1.0)
    assert reason == "accepted" and auth is not None and auth.verifier_passed is True


def test_console_abort_latches_hwkill():
    pk, pk_pub, sk, sk_pub = _keys()
    v = HandoffVerifier({pk_pub, sk_pub})
    hk = HardwareKill()
    c = LaunchConsole(verifier=v, primary_key=pk, primary_pub=pk_pub, secondary_key=sk,
                      secondary_pub=sk_pub, hwkill=hk)
    c.permit_beacon(1.0)
    assert hk.motor_power_enabled(1.0) is True
    c.abort("operator_abort")
    assert hk.motor_power_enabled(1.0) is False               # latched kill
    c.permit_beacon(1.0)                                       # aborted -> no more beacons
    assert hk.motor_power_enabled(1.0) is False


# ── FULL authorized engagement: console -> pipeline -> runtime -> RC ──────────────
def test_full_authorized_engagement_to_rc_then_abort():
    pk, pk_pub, sk, sk_pub = _keys()
    verifier = HandoffVerifier({pk_pub, sk_pub}, allow_synthetic_bench=True)
    fc = MockFcChannel()
    link = MspLink.for_bench(fc)
    sm = ArmingStateMachine(ArmingConfig(armed_idle_dwell_s=0.02, stabilize_dwell_s=0.02,
                                         ramp_s=0.05, allow_synthetic_bench=True))
    hk = HardwareKill()
    rt = OnboardRuntime(link=link, arming=sm, failsafe=FailsafeController(), hwkill=hk)
    console = LaunchConsole(verifier=verifier, primary_key=pk, primary_pub=pk_pub,
                            secondary_key=sk, secondary_pub=sk_pub, hwkill=hk,
                            config=ConsoleConfig(mission_goal="CONTACT", synthetic=True, ttl_s=90.0))
    sim = ThermalSimulator(ThermalSceneConfig(ffc_freeze_interval=0))
    frames = sim.generate(40)
    pipe = SeekerGuidancePipeline()

    auth = None
    states = []
    last_now = 0.0
    for i, (frame, _gt) in enumerate(frames):
        now = i * DT
        last_now = now
        console.permit_beacon(now)
        out = pipe.step(now, frame, (0.0, 0.0, 0.0), DT)
        console.update_seeker(locked=out.locked)
        if auth is None and out.locked:                       # operator: positive-ID -> ARM key -> FIRE
            console.insert_arm_key()
            auth, _r = console.press_fire(now)
        states.append(rt.step(now, guidance_command=out.command, los_fresh=out.locked, authorization=auth))

    assert auth is not None and auth.verifier_passed is True
    assert any(s.arm_state == ArmState.AI_ACTIVE for s in states)
    assert states[-1].effective_motor_power is True            # full authorized engagement is live

    # operator hits ABORT: it drives BOTH the independent HW-kill AND the runtime disarm path
    console.abort("operator_abort")
    rt.operator_abort("operator_abort")
    end = rt.step(last_now + DT, guidance_command=None, los_fresh=False, authorization=auth)
    assert end.arm_state == ArmState.KILLED                    # arming core disarmed
    assert end.effective_motor_power is False                  # and HW-kill cut power independently
