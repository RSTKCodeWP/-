"""Onboard runtime -- the per-loop orchestrator that ties Block-3 together (S4 integration).

Each loop tick it runs the SAFETY + LINK chain in the correct order:

  telemetry (FC gyro/ack)  -> failsafe.on_telemetry
  fresh guidance (LOS/IMM) -> failsafe.on_guidance
  failsafe.evaluate        -> ABORT disarms the arming core (only while armed)
  arming.tick(guidance)    -> the authoritative RC (AUX1 arm + roll/pitch/yaw/throttle)
  independent HW-kill       -> observed; the physical motor-power veto (below the FC)
  MspLink.send_set_raw_rc   -> the RC goes on the wire

The PERCEPTION->GUIDANCE pipeline (S1-S3) runs upstream and feeds this loop a guidance
command + an LOS-freshness flag; this runtime owns the command/arm AUTHORITY and the link.
It holds NO independent flight logic -- every decision routes through the verified modules.

The HW-kill is genuinely independent hardware (a separate MCU); this runtime only OBSERVES
its status for the effective-power readout. The kill itself happens below the flight
controller and cannot be overridden from here.
"""

from __future__ import annotations

from dataclasses import dataclass

from fpv_ai.betaflight_link.arming import ArmingAuthorization, ArmingStateMachine, ArmState
from fpv_ai.betaflight_link.failsafe import FailsafeAction, FailsafeController
from fpv_ai.betaflight_link.hwkill import HardwareKill, effective_motor_power
from fpv_ai.betaflight_link.msp_codec import channels_to_list
from fpv_ai.betaflight_link.serial_link import MspLink


@dataclass(frozen=True)
class RuntimeStep:
    now: float
    arm_state: ArmState
    rc: dict[str, int]
    failsafe: FailsafeAction
    failsafe_reason: str
    hwkill_power: bool             # does the independent HW-kill currently permit power
    effective_motor_power: bool    # the physical truth: armed AND hwkill-permitted
    telemetry_seen: bool
    sent: bool


class _GuidanceCommand:
    """Structural type: any object with roll_cmd/pitch_cmd/yaw_rate_cmd/throttle_cmd floats."""


class OnboardRuntime:
    def __init__(self, *, link: MspLink, arming: ArmingStateMachine,
                 failsafe: FailsafeController, hwkill: HardwareKill) -> None:
        self.link = link
        self.arming = arming
        self.failsafe = failsafe
        self.hwkill = hwkill

    def operator_abort(self, reason: str = "operator_abort") -> None:
        """An operator ABORT that reached the Pi over the uplink: disarm the arming core.
        The SAME physical ABORT independently drives the HW-kill below the FC -- so power is
        cut even if this software path is dead. Both are exercised by the launch console."""
        self.arming.abort(reason)

    def step(self, now: float, *, guidance_command=None, los_fresh: bool = False,
             authorization: ArmingAuthorization | None = None,
             engagement_committed: bool = False,
             engage_permitted: bool = True) -> RuntimeStep:
        # 0. AI-FIREWALL (the wire the audit flagged as missing in production): the seeker's
        #    engage-permission (sustained IMM model-wrong alarm AND/OR the learned drone-vs-not
        #    classifier vote) gates the flight command here, in the runtime itself, so ANY caller
        #    gets default-deny for free -- not only the demo call site. When it is withheld we drop
        #    the command to None -> the arming core holds neutral (ai_active_hold). This NEVER
        #    touches the LOS/tracker/centroid spine (Inv 2); it only suppresses the RC command.
        if not engage_permitted:
            guidance_command = None

        # 1. Read FC telemetry (gyro / RC ack). Its arrival proves the link is alive.
        frames = self.link.poll()
        telemetry_seen = bool(frames)
        if telemetry_seen:
            self.failsafe.on_telemetry(now)

        # 2. A fresh line-of-sight / guidance estimate keeps the guidance watchdog alive.
        if los_fresh:
            self.failsafe.on_guidance(now)

        # 3. Authorization (from the launch console) may have arrived this loop.
        if authorization is not None:
            self.arming.authorize(authorization)

        # 4. Failsafe: while ARMED, an ABORT decision disarms via the single safety authority.
        #    On the ground (not armed) a stale link is moot -- the auth gate already blocks arming.
        #    FIRE-AND-FORGET (engage_fsm, Phase C): once the terminal engagement is COMMITTED, a
        #    LOST LINK no longer aborts -- the interceptor completes autonomously (a fast interceptor
        #    leaves RF range immediately).  Every OTHER abort (guidance lost, etc.) still fires, and
        #    pre-commit link loss still aborts.  engagement_committed=False -> legacy tether behaviour.
        decision = self.failsafe.evaluate(now)
        if decision.action == FailsafeAction.ABORT and self.arming.is_armed:
            link_loss = decision.reason == "link_loss_timeout"
            if not (link_loss and engagement_committed):
                self.arming.abort(decision.reason)

        # 5. The arming core produces the authoritative RC. Guidance only bites in AI_ACTIVE.
        out = self.arming.tick(now, guidance_command)

        # 6. Independent HW-kill: observed here, enforced in hardware below the FC.
        hk_power = self.hwkill.motor_power_enabled(now)
        eff = effective_motor_power(fc_commands_motors=out.armed, hw_kill_enabled=hk_power)

        # 7. Transmit the RC on the wire.
        self.link.send_set_raw_rc(channels_to_list(out.rc))

        return RuntimeStep(
            now=now, arm_state=out.state, rc=out.rc,
            failsafe=decision.action, failsafe_reason=decision.reason,
            hwkill_power=hk_power, effective_motor_power=eff,
            telemetry_seen=telemetry_seen, sent=True,
        )
