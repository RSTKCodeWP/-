"""MissionRuntime — the LIVE per-tick runtime that drives the mission supervisor from real perception.

This turns the discrete mission-chain backbone (`mission_fsm.MissionController`) into a running system:
each tick it runs the real seeker pipeline (detect -> track -> ego -> LOS -> IMM -> looming -> subtense
range -> guidance), DERIVES the supervisor's `MissionInputs` from the pipeline output + a class vote +
sustained-confirmation counters, steps the `MissionController`, and ENFORCES the architectural invariant at
the runtime boundary:

    the guidance command is emitted ONLY when the supervisor reports ``kinetic_authorized`` (i.e. after a
    valid operator commit).  Pre-trigger the runtime is SENSE-ONLY (default-DENY) — it observes, studies,
    and builds the reference, but never emits a kinetic command.

Derivation (pipeline -> MissionInputs)
--------------------------------------
    cued            : an operator designation exists (``designate`` was called).
    in_fov          : the pipeline holds a lock this frame.
    lock_stable     : LOCK sustained for ``n_lock_stable`` consecutive frames (the confirmation window).
    class_asserted  : the class vote permits for ``n_class_sustain`` consecutive frames (SPRT-like).
    reference_ready : lock_stable AND class_asserted AND silhouette resolved AND (measured range, if req'd).
    reference_snapshot : the STUDY bundle (class + silhouette + signature + kinematics) built when ready.
    t_go/range/model_wrong/guidance_abort : straight from the pipeline output (range channel + IMM + ROE).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

from contracts.engagement_handoff import EngagementHandoff
from fpv.guidance.miss_geometry import from_los_rate
from fpv.guidance.passive_range import PassiveRangeEstimate, PassiveRangeEstimator
from fpv.guidance.pipeline import PipelineOutput, SeekerGuidancePipeline
from fpv_ai.betaflight_link.engage_fsm import EngageConfig, EngagePhase
from fpv_ai.betaflight_link.kinetic_gate import KineticRelease, compose_kinetic_release
from fpv_ai.betaflight_link.mission_fsm import (
    MissionController,
    MissionDecision,
    MissionInputs,
    MissionPhase,
)

# A class vote: (frame_u16, centroid_px) -> (permitted, confidence).  OPTIONAL trusted engage-permission
# veto; default None means the class is NEVER asserted (the learned classifier + its dataset were removed
# 2026-07-11). With None the machine does not classify target type -- confirmation is the operator's.
ClassVote = Callable[[object, tuple], "tuple[bool, float]"]


@dataclass(frozen=True)
class MissionRuntimeConfig:
    n_lock_stable: int = 5            # consecutive LOCK frames before lock_stable
    n_class_sustain: int = 5          # consecutive class-permit frames before class_asserted
    require_measured_range: bool = True   # reference_ready needs a confident MEASURED range
    target_class_label: str = "winged_uav"
    # Passive (size-free) range from bearings + our own maneuver. OFF by default: it only produces a range
    # once we have EARNED parallax, and it needs the caller to supply our own accel/velocity from INS.
    # When on, it supplies range/t_go to the commit gate whenever subtense has not measured one.
    passive_range: bool = False


@dataclass(frozen=True)
class MissionStepResult:
    decision: MissionDecision
    pipeline: PipelineOutput
    command: object | None            # bounded AICommand — emitted ONLY when kinetic_authorized
    lock_frames: int
    class_frames: int
    # The effector-cue gate: released True ONLY at the confluence of ALL gates (committed + terminal +
    # valid KILL hand-off + bound target reference).  None until an engagement_handoff is supplied.
    kinetic_release: KineticRelease | None = None
    # Passive parallax range — observability. Present even when untrusted, so a run can be audited for
    # WHY the commit gate did or did not see a range.
    passive_range: PassiveRangeEstimate | None = None


class MissionRuntime:
    """Compose the seeker pipeline + the mission supervisor into one live, sense-then-strike runtime."""

    def __init__(
        self,
        *,
        pipeline: SeekerGuidancePipeline | None = None,
        class_vote: ClassVote | None = None,
        config: MissionRuntimeConfig | None = None,
        engage_config: EngageConfig | None = None,
        target_span_m: float = 4.0,
    ) -> None:
        # A range-aided pipeline (target_span_m) so the runtime can OBSERVE range/closing for the reference.
        self._pipe = pipeline or SeekerGuidancePipeline(target_span_m=target_span_m)
        self._class_vote = class_vote
        self._cfg = config or MissionRuntimeConfig()
        self._mission = MissionController(engage_config)
        self._lock_frames = 0
        self._class_frames = 0
        self._cued = False
        self._engage_committed = False   # feeds the pipeline's two-phase terminal on the next tick
        self._last_lock_now: float | None = None   # clock of the last LOCKED frame -> LOS age for coast/abort
        self._passive = PassiveRangeEstimator() if self._cfg.passive_range else None
        self._passive_est: PassiveRangeEstimate | None = None   # observability only; never steers directly

    @property
    def phase(self) -> MissionPhase:
        return self._mission.phase

    @property
    def reference(self):
        return self._mission.reference

    def designate(self, center_px: tuple[float, float]) -> None:
        """Operator designation: seed the acquisition basket and raise the cue (IDLE -> ACQUIRE)."""
        self._pipe.designate(center_px)
        self._cued = True

    def clear_cue(self) -> None:
        self._cued = False

    def _los_age(self, now: float, locked: bool) -> float | None:
        """Seconds since the last LOCKED frame: 0.0 when locked now, None until the first ever lock."""
        if locked:
            self._last_lock_now = now
            return 0.0
        return None if self._last_lock_now is None else max(0.0, now - self._last_lock_now)

    def _trusted_passive(self) -> PassiveRangeEstimate | None:
        """The passive estimate ONLY when it has earned its parallax; otherwise it does not exist."""
        est = self._passive_est
        return est if (est is not None and est.trusted) else None

    def _commit_range(self, out: PipelineOutput) -> float:
        """Range for the commit gate. Subtense first (direct, low-latency); passive parallax as the
        size-free fallback when subtense has no measurement. inf = unknown -> the gate stays shut."""
        if out.range_m is not None:
            return float(out.range_m)
        est = self._trusted_passive()
        return float(est.range_m) if est is not None else float("inf")

    def _commit_t_go(self, out: PipelineOutput) -> float:
        if out.t_go_s is not None:
            return float(out.t_go_s)
        est = self._trusted_passive()
        return float(est.t_go_s) if (est is not None and est.t_go_s is not None) else float("inf")

    def _miss_phase(self, out: PipelineOutput, t_go: float) -> float | None:
        """Miss phase from the MEASURED LOS rate: phi_h = atan(lambda_dot * t_go); 0 == collision course.

        The LOS rate is the seeker's own primary measurement, so this is far better grounded than anything
        derived from range. Returns None when there is no LOS or no usable t_go -- the gate then abstains
        rather than inventing a cue (see fpv.guidance.miss_geometry).
        """
        if out.imm is None or not math.isfinite(t_go) or t_go <= 0.0:
            return None
        lam = math.hypot(out.imm.az_rate_radps, out.imm.el_rate_radps)
        return from_los_rate(lam, t_go).phi_h_rad

    def _build_snapshot(self, out: PipelineOutput, class_conf: float) -> dict:
        az = out.imm.az_rad if out.imm is not None else 0.0
        el = out.imm.el_rad if out.imm is not None else 0.0
        azr = out.imm.az_rate_radps if out.imm is not None else 0.0
        elr = out.imm.el_rate_radps if out.imm is not None else 0.0
        return {
            "class_label": self._cfg.target_class_label,
            "class_confidence": float(class_conf),
            "silhouette_major_px": float(out.extent_px or 0.0),
            "silhouette_minor_px": float(out.extent_minor_px or 0.0),
            "silhouette_orientation_rad": float(out.extent_orientation_rad or 0.0),
            "signature_peak": float(out.signature_peak or 0.0),
            "signature_snr": float(out.snr or 0.0),
            "az_rad": float(az), "el_rad": float(el),
            "az_rate_radps": float(azr), "el_rate_radps": float(elr),
            "range_m": float(out.range_m or 0.0),
            "closing_mps": float(out.closing_mps or 0.0),
        }

    def step(
        self,
        now: float,
        frame_u16,
        gyro_omega_xyz: tuple[float, float, float],
        dt: float,
        *,
        operator_trigger: bool = False,
        operator_cancel: bool = False,
        authorization_valid: bool = False,
        launched: bool = False,
        link_healthy: bool = True,
        altitude_m: float = 50.0,
        range_from_launch_m: float = 0.0,
        intercepted: bool = False,
        engagement_handoff: EngagementHandoff | None = None,
        now_utc: str | None = None,
        own_accel_xyz: tuple[float, float, float] | None = None,
        own_velocity_xyz: tuple[float, float, float] | None = None,
    ) -> MissionStepResult:
        # ── Continuous inner loop: the real seeker pipeline (two-phase terminal after terminal commit) ──
        out = self._pipe.step(now, frame_u16, gyro_omega_xyz, dt, committed=self._engage_committed)

        # ── Derive the supervisor inputs ────────────────────────────────────────────────────────────
        locked = bool(out.locked) and out.tracking_state == "LOCKED"
        self._lock_frames = self._lock_frames + 1 if locked else 0
        lock_stable = self._lock_frames >= self._cfg.n_lock_stable

        class_ok, class_conf = False, 0.0
        if locked and self._class_vote is not None and out.centroid_px is not None:
            v = self._class_vote(frame_u16, out.centroid_px)
            class_ok, class_conf = (v if isinstance(v, tuple) else (bool(v), 1.0 if v else 0.0))
        self._class_frames = self._class_frames + 1 if class_ok else 0
        class_asserted = self._class_frames >= self._cfg.n_class_sustain

        # ── Passive (size-free) range from bearings + our OWN maneuver ────────────────────────────────
        # Fed only while we hold a real LOS. It releases a range only once the parallax our own maneuver
        # has earned clears the gate -- never on the filter's self-assessed confidence, which is
        # demonstrably overconfident on a straight run (see fpv.guidance.passive_range).
        if self._passive is not None and out.imm is not None and locked and own_accel_xyz is not None:
            self._passive_est = self._passive.update(
                dt, out.imm.az_rad, out.imm.el_rad, own_accel_xyz, own_velocity_xyz)

        range_ok = (not self._cfg.require_measured_range) or (out.range_aiding_source == "measured")
        silhouette_ok = out.extent_px is not None
        reference_ready = lock_stable and class_asserted and silhouette_ok and range_ok
        snapshot = self._build_snapshot(out, class_conf) if reference_ready else None

        _tgo = self._commit_t_go(out)
        inp = MissionInputs(
            now=now, cued=self._cued, in_fov=bool(out.locked), lock_stable=lock_stable,
            class_asserted=class_asserted, reference_ready=reference_ready, reference_snapshot=snapshot,
            operator_trigger=operator_trigger, operator_cancel=operator_cancel,
            authorization_valid=authorization_valid,
            launched=launched, link_healthy=link_healthy,
            # LOS age = seconds since the last LOCKED frame (0 when locked now, None if never locked).
            # This lets the engage-FSM COAST through brief tracker gaps (PREDICTIVE_TRACK) up to
            # guidance_abort_s instead of aborting on the first single non-locked frame.
            guidance_age_s=self._los_age(now, bool(out.locked)),
            range_from_launch_m=range_from_launch_m, altitude_m=altitude_m,
            t_go_s=_tgo, range_to_target_m=self._commit_range(out),
            miss_phase_rad=self._miss_phase(out, _tgo),
            guidance_abort=bool(out.roe_abort), model_wrong=not out.engage_permitted,
            intercepted=intercepted,
        )

        dec = self._mission.step(inp)
        self._engage_committed = dec.engage_phase is EngagePhase.COMMITTED

        # ── Runtime enforcement of default-DENY: emit the guidance command ONLY when authorised ───────
        command = out.command if dec.kinetic_authorized else None

        # ── Effector-cue gate: compose ALL authorities (committed + terminal + valid KILL hand-off +
        #    bound target reference).  Released True ONLY at their confluence; None until a hand-off exists.
        kinetic_release = None
        if engagement_handoff is not None:
            _now_utc = now_utc or datetime.now(timezone.utc).isoformat()
            kinetic_release = compose_kinetic_release(
                kinetic_authorized=dec.kinetic_authorized, engage_phase=dec.engage_phase,
                mission_reference=self._mission.reference, handoff=engagement_handoff,
                now_utc=_now_utc, authorization_valid=authorization_valid)

        return MissionStepResult(dec, out, command, self._lock_frames, self._class_frames,
                                 kinetic_release=kinetic_release, passive_range=self._passive_est)
