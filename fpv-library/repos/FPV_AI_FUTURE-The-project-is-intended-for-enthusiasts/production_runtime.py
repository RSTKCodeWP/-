"""End-to-end onboard PRODUCTION assembly (Block-3 S4) -- the real closed loop.

    pixels -> SeekerGuidancePipeline (detect/track/IMM/guidance)
           -> VERIFIED operator authority (Ed25519 dual-signature commit)
           -> ArmingStateMachine RC + independent HW-kill

Device seams: the MSP `link` and the frame source are INJECTED, so the SAME loop runs on recorded
clips (HWIL replay) or the real camera + serial (flight). This is the production wiring the audit
flagged as missing -- unlike sil_runtime it uses the REAL crypto verifier (not a fabricated synthetic
bench auth). A synthetic authorization cannot arm (ArmingConfig.allow_synthetic_bench=False).

TARGET CONFIRMATION IS THE OPERATOR'S. The learned drone-vs-not classifier and its dataset were
REMOVED (2026-07-11, untrusted). The pipeline keeps an OPTIONAL ``discriminator`` hook (default None)
for a future TRUSTED engage-permission veto; with None the machine never asserts a target class -- the
kinetic gate rests entirely on the operator's dual-signed commit + the non-learned kinematic gates.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from fpv.guidance.pipeline import SeekerGuidancePipeline
from fpv.seeker.geometry import CameraIntrinsics
from fpv_ai.betaflight_link.arming import (ArmingAuthorization, ArmingConfig, ArmingStateMachine, ArmState)
from fpv_ai.betaflight_link.authorization import verify_operator_commit
from fpv_ai.betaflight_link.engage_fsm import EngagePhase
from fpv_ai.betaflight_link.failsafe import FailsafeController
from fpv_ai.betaflight_link.hwkill import HardwareKill
from fpv_ai.betaflight_link.mission_fsm import MissionPhase
from fpv_ai.betaflight_link.onboard_runtime import OnboardRuntime, RuntimeStep
from fpv_ai.mission_runtime import MissionRuntime, MissionRuntimeConfig


@dataclass
class ProductionConfig:
    auth_min_signatures: int = 2                  # dual-operator commit
    fire_and_forget: bool = True
    target_span_m: float = 4.0                    # for the range-aided reference / true PN
    require_measured_range: bool = False          # replay clips need not close; a real engagement sets True
    # Size-free passive range from bearings + our own maneuver, feeding the commit gate when subtense has no
    # measurement. OFF by default; the caller must also supply own_accel_xyz from INS for it to do anything.
    passive_range: bool = False
    # Doctrine (default TRUE): do NOT arm until the mission has been STUDIED+CONFIRMED and the operator has
    # committed (READY -> ENGAGING).  So default-DENY covers BOTH the guidance command AND arming, not just
    # the command.  FALSE isolates the crypto arming gate (arms on a verified commit regardless of phase).
    require_mission_commit_to_arm: bool = True
    arming_config: ArmingConfig = field(default_factory=ArmingConfig)   # LIVE: no synthetic arm
    # Occlusion-aware lock-hold: coast the seeker through a brief target occlusion (behind a cloud) instead of
    # deleting the track + re-acquiring onto the brightest clutter (the sun). Validated: on-truth 40%->96%,
    # false-lock 18%->0% on the occlusion stress. ~20 frames @60Hz ≈ 330 ms.
    occlusion_coast_frames: int = 20


class ProductionRuntime:
    """Assemble the verified components into one onboard loop, DRIVEN BY THE MISSION SUPERVISOR.

    The mission chain (acquire -> study -> ready -> commit -> engage -> terminal) is owned by an embedded
    ``MissionRuntime`` (perception + the discrete supervisor); this class adds the production safety shell:
    the REAL Ed25519 arming authority, the independent HW-kill, and the MSP link.  Two independent gates
    compose (defence-in-depth): the mission's default-DENY (no command until the operator commit) AND the
    crypto arming (no motors until a verified dual-signature).  `link` + frames are injected seams.
    """

    def __init__(self, *, link, operator_public_keys, intrinsics: CameraIntrinsics | None = None,
                 classifier=None, acquisition_box=None, config: ProductionConfig | None = None,
                 pipeline_kwargs: dict | None = None) -> None:
        self.cfg = config or ProductionConfig()
        self.keys = list(operator_public_keys)
        # ``classifier`` is an OPTIONAL trusted engage-permission veto (default None -> the machine never
        # asserts a target class; the removed drone-vs-not model is NOT auto-loaded). When supplied it
        # feeds both the pipeline discriminator and the mission class_vote; both can only WITHHOLD engage.
        pipe = SeekerGuidancePipeline(intrinsics=intrinsics, discriminator=classifier,
                                      acquisition_box=acquisition_box, target_span_m=self.cfg.target_span_m,
                                      occlusion_coast_frames=self.cfg.occlusion_coast_frames,
                                      **(pipeline_kwargs or {}))
        self.mission = MissionRuntime(
            pipeline=pipe, class_vote=_classifier_vote(classifier),
            config=MissionRuntimeConfig(require_measured_range=self.cfg.require_measured_range,
                                        passive_range=self.cfg.passive_range))
        self.arming = ArmingStateMachine(self.cfg.arming_config)
        self.runtime = OnboardRuntime(link=link, arming=self.arming,
                                      failsafe=FailsafeController(), hwkill=HardwareKill())
        self.seen_nonces: set = set()
        self.committed = False
        self.passive_range = None                # last passive parallax estimate (observability)
        self._launched = False

    # -- introspection ----------------------------------------------------------------------------------
    @property
    def pipe(self) -> SeekerGuidancePipeline:
        return self.mission._pipe   # noqa: SLF001 (kept for API compatibility / observability)

    @property
    def mission_phase(self) -> MissionPhase:
        return self.mission.phase

    @property
    def reference(self):
        """The immutable target reference, frozen at the operator commit (None before)."""
        return self.mission.reference

    def designate(self, center_px) -> None:
        """Operator designation -> raise the cue (IDLE leaves for ACQUIRE)."""
        self.mission.designate(center_px)

    def submit_authorization(self, envelope: dict) -> ArmingAuthorization:
        """Verify a dual-signed operator commit -> ArmingAuthorization whose verifier_passed comes
        from REAL Ed25519 + replay checks (default-deny on any failure)."""
        return verify_operator_commit(envelope, self.keys,
                                      min_signatures=self.cfg.auth_min_signatures,
                                      seen_nonces=self.seen_nonces).authorization

    def step(self, now: float, frame_u16, gyro_omega_xyz, dt: float, *,
             authorization: ArmingAuthorization | None = None, link_alive: bool = True,
             operator_cancel: bool = False,
             own_accel_xyz: tuple[float, float, float] | None = None,
             own_velocity_xyz: tuple[float, float, float] | None = None):
        """One onboard tick. Returns (PipelineOutput, RuntimeStep).

        ``operator_cancel`` is the physical CANCEL button PRE-trigger: it vetoes the mission back to IDLE
        (drop the lock / change target).  It is honoured only in the revertible pre-trigger phases — the
        post-trigger doctrine ignores mission CANCEL, so cancelling a launched engagement is the operator's
        dominant ``arming.kill()`` (wired at the console), not this flag.
        """
        # A verified operator authorization IS the operator commit (trigger + dual-auth) for the mission.
        auth_ok = authorization is not None and authorization.verifier_passed
        res = self.mission.step(
            now, frame_u16, gyro_omega_xyz, dt,
            operator_trigger=auth_ok, operator_cancel=operator_cancel, authorization_valid=auth_ok,
            launched=self._launched, link_healthy=link_alive,
            own_accel_xyz=own_accel_xyz, own_velocity_xyz=own_velocity_xyz)
        out = res.pipeline
        self.passive_range = res.passive_range
        self.committed = res.decision.engage_phase is EngagePhase.COMMITTED

        if link_alive or self.committed:
            self.runtime.hwkill.permit_beacon(now)          # F&F latches the beacon onboard post-commit
        # Doctrine gate: withhold the arming authorization until the mission has committed (studied +
        # confirmed + operator commit), so default-DENY covers arming too.  Once committed the operator
        # authorization arms (the commit and the arm are simultaneous — the trigger IS the commit).
        arm_auth = (authorization if (not self.cfg.require_mission_commit_to_arm
                                      or res.decision.kinetic_authorized) else None)
        rt: RuntimeStep = self.runtime.step(
            now, guidance_command=res.command, los_fresh=out.locked,   # mission-gated command (default-DENY)
            authorization=arm_auth, engagement_committed=self.committed,
            engage_permitted=out.engage_permitted)           # AI-firewall gate (model-wrong AND CNN)
        # "launched" for the mission's post-trigger delegate: the system reached live AI control.
        if rt.arm_state == ArmState.AI_ACTIVE:
            self._launched = True
        return out, rt


def _classifier_vote(classifier):
    """Adapt a classifier into the mission class-vote ``(frame, centroid) -> (permitted, confidence)``.

    Prefers a ``permits`` + ``prob_drone`` API (a trusted vote object); falls back to a plain
    ``discriminator`` bool; ``None`` classifier -> no vote (class never asserted -> default-deny).
    """
    if classifier is None:
        return None
    if hasattr(classifier, "permits") and hasattr(classifier, "prob_drone"):
        return lambda f, c: (bool(classifier.permits(f, c)), float(classifier.prob_drone(f, c)))
    return lambda f, c: (bool(classifier(f, c)), 1.0)
