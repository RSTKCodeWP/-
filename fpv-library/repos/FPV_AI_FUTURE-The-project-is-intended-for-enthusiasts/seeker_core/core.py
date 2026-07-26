"""seeker_core.core — the bounded pipeline: detect → track → guidance → safety → actuators.

Stages are Protocols; the defaults here are HONEST default-deny stubs (they never claim a lock, never
fabricate range, never arm without a signed two-press). The proven `../fpv/` detector / tracker /
guidance drop in as the real implementations of these Protocols — this module owns the wiring, the
safety gate, and the actuator output bus, not the physics.

Safety boundary baked into the mapper: sensor/gimbal AIMING is allowed before commit (pointing a
camera is not engaging), but AIRFRAME steering/throttle is neutral unless Authority.committed is true.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from seeker_core.contracts import (
    ActuatorChannel,
    ActuatorCommand,
    ActuatorFrame,
    Authority,
    Detections,
    Frame,
    GimbalState,
    GuidanceCommand,
    ImuSample,
    OperatorButton,
    OperatorCommand,
    SeekerOutput,
    Track,
)


# ── stage Protocols (implemented by the proven fpv/ blocks in production) ──────────────────────────
class Detector(Protocol):
    def detect(self, frame: Frame) -> Detections: ...


class Tracker(Protocol):
    def update(self, detections: Detections, imu: Optional[ImuSample],
               gimbal: Optional[GimbalState], dt: float) -> Track: ...


class Guidance(Protocol):
    def command(self, track: Track) -> GuidanceCommand: ...


class GimbalStage(Protocol):
    def step(self, detections: Detections, imu: Optional[ImuSample], dt: float) -> GimbalState: ...


class SafetySupervisor(Protocol):
    def evaluate(self, track: Track, guidance: GuidanceCommand, op: OperatorCommand) -> Authority: ...


class ActuatorMapper(Protocol):
    def map(self, guidance: GuidanceCommand, track: Track, gimbal: Optional[GimbalState],
            authority: Authority) -> ActuatorFrame: ...


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


# ── honest default-deny stubs (safe, non-fabricating; real physics plugs in) ──────────────────────
class NullDetector:
    """Reference stub: finds nothing. The real detector (fpv.seeker.detect) implements this Protocol."""
    def detect(self, frame: Frame) -> Detections:
        return Detections(blobs=(), provenance=frame.provenance)


class CoastTracker:
    """Reference stub: never asserts a lock; emits an unlocked, range-unknown track (no fabrication)."""
    def update(self, detections: Detections, imu: Optional[ImuSample],
               gimbal: Optional[GimbalState], dt: float) -> Track:
        prov = detections.provenance
        return Track(locked=False, az_rad=0.0, el_rad=0.0, los_rate_az=0.0, los_rate_el=0.0,
                     range_m=None, t_go_s=None, quality=0.0, provenance=prov)


class HoldGuidance:
    """Reference stub: neutral command, no engage permit. The real law (fpv.guidance) implements this."""
    def command(self, track: Track) -> GuidanceCommand:
        return GuidanceCommand(a_cmd_az=0.0, a_cmd_el=0.0, roe_abort=False, engage_permit=False,
                               required_g=0.0, provenance=track.provenance)


class DefaultDenySupervisor:
    """Default-deny authority: commit ONLY on a valid two-press (COMMIT button + a present auth token),
    a live lock, and no ROE abort. ABORT latches kill. Everything else is safe/neutral."""
    def __init__(self) -> None:
        self._killed = False

    def evaluate(self, track: Track, guidance: GuidanceCommand, op: OperatorCommand) -> Authority:
        if op.button == OperatorButton.ABORT:
            self._killed = True
        if self._killed:
            return Authority(armed=False, committed=False, kill=True, reason="operator_abort_latched")
        authorised = (op.button == OperatorButton.COMMIT and op.auth_token is not None)
        committed = bool(authorised and track.locked and not guidance.roe_abort)
        reason = ("committed" if committed
                  else "no_auth_token" if op.auth_token is None
                  else "no_lock" if not track.locked
                  else "roe_abort" if guidance.roe_abort
                  else "standby")
        return Authority(armed=committed, committed=committed, kill=False, reason=reason)


@dataclass(frozen=True)
class MapperConfig:
    accel_to_cmd_gain: float = 0.2       # rad/s^2 -> normalised surface demand
    throttle_committed: float = 0.6      # cruise throttle once committed (0..1)


class StandardActuatorMapper:
    """Maps guidance + gimbal to the actuator bus. Gimbal AIMING (2 servos) is allowed pre-commit —
    pointing a camera is not engaging — but AIRFRAME steering/throttle is NEUTRAL unless committed."""
    def __init__(self, cfg: MapperConfig | None = None) -> None:
        self.cfg = cfg or MapperConfig()

    def map(self, guidance: GuidanceCommand, track: Track, gimbal: Optional[GimbalState],
            authority: Authority) -> ActuatorFrame:
        t_ns = track.provenance.t_capture_ns
        cmds: list[ActuatorCommand] = []

        # Gimbal AIMING: the head stabilises/tracks whenever a gimbal is present (allowed pre-commit).
        if gimbal is not None:
            cmds.append(ActuatorCommand(ActuatorChannel.GIMBAL_AZ, gimbal.pan_setpoint_rad, t_ns))
            cmds.append(ActuatorCommand(ActuatorChannel.GIMBAL_EL, gimbal.tilt_setpoint_rad, t_ns))

        # Airframe steering/throttle: ONLY when the human has committed and there is no kill.
        if authority.committed and not authority.kill:
            yaw = _clamp(guidance.a_cmd_az * self.cfg.accel_to_cmd_gain, -1.0, 1.0)
            pitch = _clamp(guidance.a_cmd_el * self.cfg.accel_to_cmd_gain, -1.0, 1.0)
            cmds.append(ActuatorCommand(ActuatorChannel.AIRFRAME_YAW, yaw, t_ns))
            cmds.append(ActuatorCommand(ActuatorChannel.AIRFRAME_PITCH, pitch, t_ns))
            cmds.append(ActuatorCommand(ActuatorChannel.AIRFRAME_ROLL, 0.0, t_ns))
            cmds.append(ActuatorCommand(ActuatorChannel.AIRFRAME_THROTTLE, self.cfg.throttle_committed, t_ns))
        else:
            # safe neutral: surfaces centred, throttle idle
            for ch in (ActuatorChannel.AIRFRAME_YAW, ActuatorChannel.AIRFRAME_PITCH,
                       ActuatorChannel.AIRFRAME_ROLL, ActuatorChannel.AIRFRAME_THROTTLE):
                cmds.append(ActuatorCommand(ch, 0.0, t_ns))

        return ActuatorFrame(commands=tuple(cmds), authority=authority, provenance=track.provenance)


# ── the core ──────────────────────────────────────────────────────────────────────────────────────
class SeekerCore:
    """Wires the stages and runs one tick. Owns the actuator bus and the safety gate — not the physics."""

    def __init__(self, *, detector: Detector, tracker: Tracker, guidance: Guidance,
                 supervisor: SafetySupervisor, mapper: ActuatorMapper,
                 gimbal: Optional[GimbalStage] = None) -> None:
        self.detector = detector
        self.tracker = tracker
        self.guidance = guidance
        self.supervisor = supervisor
        self.mapper = mapper
        self.gimbal = gimbal                 # None -> strapdown (no gimbal channels emitted)

    def step(self, frame: Frame, imu: Optional[ImuSample], op: OperatorCommand, dt: float) -> SeekerOutput:
        detections = self.detector.detect(frame)
        gstate = self.gimbal.step(detections, imu, dt) if self.gimbal is not None else None
        track = self.tracker.update(detections, imu, gstate, dt)
        guidance = self.guidance.command(track)
        authority = self.supervisor.evaluate(track, guidance, op)
        actuators = self.mapper.map(guidance, track, gstate, authority)
        return SeekerOutput(track=track, guidance=guidance, authority=authority,
                            actuators=actuators, gimbal=gstate)


def default_core() -> SeekerCore:
    """A safe, honest STRAPDOWN core wired from the default-deny stubs (no gimbal)."""
    return SeekerCore(
        detector=NullDetector(),
        tracker=CoastTracker(),
        guidance=HoldGuidance(),
        supervisor=DefaultDenySupervisor(),
        mapper=StandardActuatorMapper(),
    )


def gimbaled_core(gimbal: GimbalStage) -> SeekerCore:
    """A safe, honest core WITH a stabilized gimbal stage (see seeker_core.gimbal_stage)."""
    return SeekerCore(
        detector=NullDetector(),
        tracker=CoastTracker(),
        guidance=HoldGuidance(),
        supervisor=DefaultDenySupervisor(),
        mapper=StandardActuatorMapper(),
        gimbal=gimbal,
    )
