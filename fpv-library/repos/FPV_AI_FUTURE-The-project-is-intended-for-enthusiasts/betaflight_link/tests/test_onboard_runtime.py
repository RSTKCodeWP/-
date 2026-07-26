"""Integration tests for the onboard runtime (Block-3 S4) -- the whole safety+link chain."""

from __future__ import annotations

from dataclasses import dataclass

from fpv_ai.betaflight_link import msp_codec as mc
from fpv_ai.betaflight_link.arming import ArmingConfig, ArmingStateMachine, ArmState
from fpv_ai.betaflight_link.failsafe import FailsafeController
from fpv_ai.betaflight_link.hwkill import HardwareKill
from fpv_ai.betaflight_link.onboard_runtime import OnboardRuntime
from fpv_ai.betaflight_link.serial_link import MockFcChannel, MspLink
from fpv_ai.betaflight_link.tests.test_arming import live_auth


@dataclass
class _Cmd:
    roll_cmd: float
    pitch_cmd: float
    yaw_rate_cmd: float
    throttle_cmd: float


CMD = _Cmd(0.0, 0.0, 0.0, 0.5)


def _build():
    fc = MockFcChannel()
    link = MspLink.for_bench(fc)
    sm = ArmingStateMachine(ArmingConfig(armed_idle_dwell_s=0.02, stabilize_dwell_s=0.02, ramp_s=0.05))
    fs = FailsafeController()
    hk = HardwareKill()
    rt = OnboardRuntime(link=link, arming=sm, failsafe=fs, hwkill=hk)
    return fc, link, sm, fs, hk, rt


def _drive_to_ai_active(rt, hk, *, feed_beacon=True, dt=0.01, tmax=1.0):
    auth = live_auth(now=0.0, ttl=100.0)
    if feed_beacon:
        hk.permit_beacon(0.0)
    rt.step(0.0, authorization=auth, los_fresh=True, guidance_command=CMD)  # -> PREARM
    t, last = 0.0, None
    while t < tmax:
        t = round(t + dt, 5)
        if feed_beacon:
            hk.permit_beacon(t)
        last = rt.step(t, los_fresh=True, guidance_command=CMD)
        if last.arm_state == ArmState.AI_ACTIVE:
            break
    return last, t


def test_happy_path_reaches_ai_active_with_power_and_guidance_on_wire():
    fc, link, sm, fs, hk, rt = _build()
    last, _ = _drive_to_ai_active(rt, hk)
    assert last.arm_state == ArmState.AI_ACTIVE
    assert last.effective_motor_power is True          # armed AND hw-kill permits power
    assert last.hwkill_power is True
    # the guidance throttle (0.5 -> 1500us) actually reached the (mock) flight controller
    assert fc.last_rc[mc.RC_CHANNEL_ORDER.index("throttle")] == mc.throttle_to_us(0.5)
    assert fc.armed is True                            # FC armed via AUX1 from the runtime


def test_no_hwkill_beacon_vetoes_power_even_when_armed():
    fc, link, sm, fs, hk, rt = _build()
    last, _ = _drive_to_ai_active(rt, hk, feed_beacon=False)   # never feed the independent beacon
    assert last.arm_state == ArmState.AI_ACTIVE                 # arming core IS in AI_ACTIVE
    assert last.hwkill_power is False
    assert last.effective_motor_power is False                 # independent HW-kill vetoes power


def test_link_loss_aborts_armed_aircraft():
    fc, link, sm, fs, hk, rt = _build()
    last, t = _drive_to_ai_active(rt, hk)
    assert last.arm_state == ArmState.AI_ACTIVE

    fc.link_up = False                                  # the FC link dies (no telemetry/ack)
    killed = None
    deadline = t + 0.6
    while t < deadline:
        t = round(t + 0.01, 5)
        hk.permit_beacon(t)                             # beacon still up; link is what's lost
        s = rt.step(t, los_fresh=True, guidance_command=CMD)
        if s.arm_state == ArmState.KILLED:
            killed = s
            break
    assert killed is not None
    assert killed.failsafe_reason == "link_loss_timeout"
    assert killed.effective_motor_power is False
    assert killed.rc["aux1"] == sm.cfg.disarm_aux_us    # disarmed RC on the wire


def test_runtime_sends_every_step():
    fc, link, sm, fs, hk, rt = _build()
    s = rt.step(0.0, los_fresh=True)
    assert s.sent is True
    assert link.stats.frames_sent >= 1
