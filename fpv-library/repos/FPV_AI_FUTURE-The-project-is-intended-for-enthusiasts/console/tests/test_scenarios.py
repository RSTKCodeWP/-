"""Full-system scenario tests (Block-3 testing phase): the closed console->pipeline->runtime
loop under hard conditions -- target loss/reacquire, long loss, link loss, FFC freeze.
Every condition is deterministically controlled so the tests are not flaky; each asserts the
system degrades SAFELY (coast, or abort to KILLED with motor power cut), never an unsafe state.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from fpv.seeker.thermal_sim import ThermalSceneConfig, ThermalSimulator
from fpv.guidance.pipeline import SeekerGuidancePipeline

from fpv_ai.betaflight_link.arming import ArmingConfig, ArmingStateMachine, ArmState
from fpv_ai.betaflight_link.failsafe import FailsafeAction, FailsafeController
from fpv_ai.betaflight_link.hwkill import HardwareKill
from fpv_ai.betaflight_link.onboard_runtime import OnboardRuntime
from fpv_ai.betaflight_link.serial_link import MockFcChannel, MspLink
from fpv_ai.console.console import ConsoleConfig, HandoffVerifier, LaunchConsole
from fpv_ai.console.handoff import generate_keypair

DT = 1.0 / 60.0
COLD = np.full((512, 640), 4096, dtype=np.uint16)


@dataclass
class _Sys:
    console: LaunchConsole
    rt: OnboardRuntime
    pipe: SeekerGuidancePipeline
    fc: MockFcChannel


def _make_system(scene: ThermalSceneConfig | None = None) -> _Sys:
    pk, pk_pub, sk, sk_pub = (*generate_keypair(), *generate_keypair())
    verifier = HandoffVerifier({pk_pub, sk_pub}, allow_synthetic_bench=True)
    fc = MockFcChannel()
    link = MspLink.for_bench(fc)
    sm = ArmingStateMachine(ArmingConfig(armed_idle_dwell_s=0.02, stabilize_dwell_s=0.02,
                                         ramp_s=0.05, allow_synthetic_bench=True))
    hk = HardwareKill()
    rt = OnboardRuntime(link=link, arming=sm, failsafe=FailsafeController(), hwkill=hk)
    console = LaunchConsole(verifier=verifier, primary_key=pk, primary_pub=pk_pub,
                            secondary_key=sk, secondary_pub=sk_pub, hwkill=hk,
                            config=ConsoleConfig(mission_goal="CONTACT", synthetic=True))
    return _Sys(console=console, rt=rt, pipe=SeekerGuidancePipeline(), fc=fc)


def _target_frames(n: int) -> list[tuple[np.ndarray, str]]:
    sim = ThermalSimulator(ThermalSceneConfig(ffc_freeze_interval=0))
    return [(frame, "READY") for frame, _gt in sim.generate(n)]


def _drive(s: _Sys, frames: list[tuple[np.ndarray, str]], *, kill_link_at: int | None = None):
    trace = []
    auth = None
    for i, (frame, ffc_state) in enumerate(frames):
        now = i * DT
        if kill_link_at is not None and i >= kill_link_at:
            s.fc.link_up = False
        s.console.permit_beacon(now)
        out = s.pipe.step(now, frame, (0.0, 0.0, 0.0), DT, ffc_state=ffc_state)
        s.console.update_seeker(locked=out.locked)
        if auth is None and out.locked:
            s.console.insert_arm_key()
            auth, _r = s.console.press_fire(now)
        step = s.rt.step(now, guidance_command=out.command, los_fresh=out.locked, authorization=auth)
        # safety invariants hold on EVERY step regardless of scenario
        assert step.rc["throttle"] >= 1000
        if not step.effective_motor_power:
            pass  # cut is always safe
        trace.append((out, step))
    return trace, auth


def _reached_ai_active(trace) -> bool:
    return any(st.arm_state == ArmState.AI_ACTIVE for _o, st in trace)


# ── scenario 1: brief target loss -> coast -> reacquire, engagement SURVIVES ──────
def test_brief_target_loss_coasts_and_survives():
    tgt = _target_frames(25)
    frames = tgt[:10] + [(COLD, "READY")] * 8 + tgt[10:]   # ~0.13s gap (< 0.5s abort window)
    s = _make_system()
    trace, auth = _drive(s, frames)
    assert auth is not None and _reached_ai_active(trace)
    # never killed by a brief loss
    assert all(st.arm_state != ArmState.KILLED for _o, st in trace)
    # the seeker re-locks after the gap
    assert any(o.locked for o, _st in trace[18:])
    # the failsafe coasted (HOLD_LAST) during the gap rather than flying a stale command
    assert any(st.failsafe == FailsafeAction.HOLD_LAST for _o, st in trace)


# ── scenario 2: long target loss -> guidance watchdog -> ABORT to KILLED ──────────
def test_long_target_loss_aborts():
    tgt = _target_frames(12)
    frames = tgt + [(COLD, "READY")] * 45                  # ~0.75s gap (> 0.5s abort window)
    s = _make_system()
    trace, auth = _drive(s, frames)
    assert _reached_ai_active(trace)
    killed = [st for _o, st in trace if st.arm_state == ArmState.KILLED]
    assert killed and killed[-1].effective_motor_power is False
    assert any(st.failsafe_reason == "guidance_lost" for _o, st in trace)


# ── scenario 3: link loss mid-flight -> ABORT to KILLED, power cut ────────────────
def test_link_loss_midflight_aborts():
    s = _make_system()
    trace, auth = _drive(s, _target_frames(45), kill_link_at=20)
    assert _reached_ai_active(trace)
    final = trace[-1][1]
    assert final.arm_state == ArmState.KILLED
    assert final.failsafe_reason == "link_loss_timeout"
    assert final.effective_motor_power is False


# ── scenario 4: FFC freeze in the loop -> no false target, engagement SURVIVES ────
def test_ffc_freeze_survives_without_false_target():
    sim = ThermalSimulator(ThermalSceneConfig(ffc_freeze_interval=22, ffc_freeze_frames=12))
    frames = [(frame, gt.ffc_state) for frame, gt in sim.generate(45)]
    assert any(ffc != "READY" for _f, ffc in frames)        # the run actually contains an FFC event
    s = _make_system()
    trace, auth = _drive(s, frames)
    assert auth is not None and _reached_ai_active(trace)
    # an FFC freeze (~0.2s) is shorter than the abort window -> the engagement survives it
    assert all(st.arm_state != ArmState.KILLED for _o, st in trace)
    # during a freeze the detector emits NO blob, so the seeker never locks a false target
    for (_frame, ffc), (out, _st) in zip(frames, trace):
        if ffc == "FREEZE":
            assert out.command is None    # no command produced from a frozen frame
