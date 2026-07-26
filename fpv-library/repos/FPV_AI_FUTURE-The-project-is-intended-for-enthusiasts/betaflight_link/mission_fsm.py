"""Autonomous MISSION-CHAIN supervisor — assembles the whole seeker engagement into ONE runtime.

WHY THIS EXISTS
---------------
The verified pieces existed but were never sequenced into a single autonomous chain: the post-trigger
flight logic (`engage_fsm.EngagementController`: LAUNCH -> MIDCOURSE -> COMMITTED -> COMPLETE/ABORTED),
the crypto arming authority (`authorization.verify_operator_commit`), the perception/estimation pipeline,
the classifier and the silhouette/MOSSE reference — all live, none composed.  This module is the missing
DISCRETE SUPERVISOR: a hierarchical hybrid state machine that owns the PRE-trigger phases, freezes the
immutable target reference at the operator commit, and DELEGATES the post-trigger flight to the embedded
`EngagementController`.  It is pure logic (no I/O), deterministic, and unit-testable in isolation.

DOCTRINE MAPPED TO STATES (BLOCK03_MATURE_GSN_DOCTRINE §5)
---------------------------------------------------------
    [cue / wide search]
        v   (Axis I)
    IDLE ---cued---> ACQUIRE ---lock stable---> STUDY ---reference+class---> READY
        (default-DENY: kinetic_authorized = False throughout the pre-trigger phases; CANCEL reverts to IDLE)
        v   operator TRIGGER + valid dual-auth + reference ready   <-- default-DENY ENDS here
    ENGAGING  (delegates to EngagementController: MIDCOURSE -> COMMITTED, default-COMPLETE)
        v
    COMPLETE / ABORTED   (sticky)

TWO COMMITS (do not conflate)
-----------------------------
1. OPERATOR COMMIT = the trigger, on the ground/hand, pre-launch: default-DENY ends, the reference is
   frozen, arming is authorised (Ed25519 dual-sign + keypress, verified upstream).  This module's
   READY -> ENGAGING transition.
2. TERMINAL COMMIT = in flight, fire-and-forget point (link no longer required): the embedded
   `EngagementController`'s MIDCOURSE -> COMMITTED.

TWO-PHASE SAFETY (Axis II) — a FORMAL property of this FSM
----------------------------------------------------------
The set of aborting/reverting conditions SHRINKS after the operator commit:
  * PRE-trigger  (IDLE/ACQUIRE/STUDY/READY): revertible on ANY loss (lock lost -> back to ACQUIRE) and
    CANCELlable by the operator (veto -> IDLE).  ``kinetic_authorized`` is False.  This is default-DENY.
  * POST-trigger (ENGAGING+): CANCEL is IGNORED (default-COMPLETE — a doer, not a doubter); only the
    embedded engage-FSM's HARD self-safe rules (geo/alt keep-out, TTL, guidance ROE, genuine target loss)
    can abort.  ``kinetic_authorized`` is True.
"""

from __future__ import annotations

import enum
import math
from dataclasses import asdict, dataclass, replace
from typing import Optional

from fpv.safety.verifier import canonical_payload
from fpv_ai.betaflight_link.engage_fsm import (
    EngageAction,
    EngageConfig,
    EngageInputs,
    EngagePhase,
    EngagementController,
)

try:
    import hashlib
    _HAS_HASH = True
except ImportError:  # pragma: no cover
    _HAS_HASH = False


class MissionPhase(str, enum.Enum):
    IDLE = "IDLE"           # no cue / nothing acquired
    ACQUIRE = "ACQUIRE"     # cue present; detecting + stabilising the reticle-cued lock
    STUDY = "STUDY"         # lock stable; building the immutable reference (class + silhouette + kinematics)
    READY = "READY"         # reference built + class asserted; monitor shows the operator; awaiting trigger
    ENGAGING = "ENGAGING"   # post-trigger, launched; delegated to the EngagementController
    COMPLETE = "COMPLETE"   # intercept done (sticky)
    ABORTED = "ABORTED"     # safed (sticky)


class MissionAction(str, enum.Enum):
    OBSERVE = "OBSERVE"       # pre-trigger: sense only, NO kinetic (default-DENY)
    CONTINUE = "CONTINUE"     # post-trigger: fly the engagement
    HOLD_LAST = "HOLD_LAST"   # coast (brief guidance gap, pre-launch hold)
    ABORT = "ABORT"           # self-safe


@dataclass(frozen=True)
class TargetReference:
    """Immutable target reference, FROZEN at the operator commit (Axis III — target fidelity).

    Post-commit the seeker holds ONLY this target; ``reference_hash`` binds into the operator
    authorization so the flying seeker provably matches what the operator confirmed on the monitor.
    """

    class_label: str
    class_confidence: float
    silhouette_major_px: float
    silhouette_minor_px: float
    silhouette_orientation_rad: float
    signature_peak: float
    signature_snr: float
    az_rad: float
    el_rad: float
    az_rate_radps: float
    el_rate_radps: float
    range_m: float
    closing_mps: float
    frozen_at_s: float
    reference_hash: str = ""


def freeze_reference(snapshot: dict, now: float) -> TargetReference:
    """Build the immutable :class:`TargetReference` from a STUDY-phase snapshot + a stable hash.

    The hash is computed over the canonical (sorted-key) JSON of the reference fields EXCLUDING the hash
    itself, using the same canonicalisation the safety verifier signs with — so the reference identity is
    reproducible and bindable into the operator authorization.
    """
    ref = TargetReference(
        class_label=str(snapshot.get("class_label", "unknown")),
        class_confidence=float(snapshot.get("class_confidence", 0.0)),
        silhouette_major_px=float(snapshot.get("silhouette_major_px", 0.0)),
        silhouette_minor_px=float(snapshot.get("silhouette_minor_px", 0.0)),
        silhouette_orientation_rad=float(snapshot.get("silhouette_orientation_rad", 0.0)),
        signature_peak=float(snapshot.get("signature_peak", 0.0)),
        signature_snr=float(snapshot.get("signature_snr", 0.0)),
        az_rad=float(snapshot.get("az_rad", 0.0)),
        el_rad=float(snapshot.get("el_rad", 0.0)),
        az_rate_radps=float(snapshot.get("az_rate_radps", 0.0)),
        el_rate_radps=float(snapshot.get("el_rate_radps", 0.0)),
        range_m=float(snapshot.get("range_m", 0.0)),
        closing_mps=float(snapshot.get("closing_mps", 0.0)),
        frozen_at_s=float(now),
        reference_hash="",
    )
    body = canonical_payload({k: v for k, v in asdict(ref).items() if k != "reference_hash"})
    digest = hashlib.sha256(body).hexdigest() if _HAS_HASH else str(abs(hash(body)))
    return replace(ref, reference_hash=digest)


@dataclass(frozen=True)
class MissionInputs:
    now: float
    # ── perception / estimation (from the pipeline) ─────────────────────────────
    cued: bool = False               # a target cue exists (designation / ground cue) — Axis I
    in_fov: bool = False             # the reticle-cued target is in FOV
    lock_stable: bool = False        # lock stabilised over the confirmation window
    class_asserted: bool = False     # classifier asserts the winged-UAV class (sustained, confident)
    reference_ready: bool = False    # silhouette resolved + track-quality OK + signature captured
    reference_snapshot: Optional[dict] = None   # the STUDY-built reference bundle (frozen at commit)
    # ── operator ────────────────────────────────────────────────────────────────
    operator_trigger: bool = False
    operator_cancel: bool = False
    authorization_valid: bool = False   # dual-sign + keypress verified upstream (verify_operator_commit)
    # ── post-launch (delegated to the EngagementController) ─────────────────────
    launched: bool = False
    link_healthy: bool = True
    guidance_age_s: Optional[float] = 0.0
    range_from_launch_m: float = 0.0
    altitude_m: float = 50.0
    t_go_s: float = float("inf")
    range_to_target_m: float = float("inf")
    # Miss phase (rad): angle between the closing velocity and the LOS; 0 == collision course. None means
    # "not measured" -> the engage-FSM's collision-course gate abstains (fpv.guidance.miss_geometry).
    miss_phase_rad: float | None = None
    guidance_abort: bool = False
    model_wrong: bool = False
    intercepted: bool = False


@dataclass(frozen=True)
class MissionDecision:
    phase: MissionPhase
    action: MissionAction
    reason: str
    kinetic_authorized: bool                     # THE invariant: False pre-trigger, True post-valid-commit
    engage_phase: Optional[EngagePhase] = None   # the delegated post-launch phase (None pre-launch)


class MissionController:
    """Hierarchical mission supervisor: pre-trigger phases + reference freeze + post-trigger delegation."""

    def __init__(self, engage_config: EngageConfig | None = None) -> None:
        self._phase = MissionPhase.IDLE
        self._engage = EngagementController(engage_config)
        self._reference: Optional[TargetReference] = None

    @property
    def phase(self) -> MissionPhase:
        return self._phase

    @property
    def reference(self) -> Optional[TargetReference]:
        """The immutable target reference, available once the operator has committed (else None)."""
        return self._reference

    # -- pre-trigger phase progression (monotone with automatic regression on loss) ------------------
    @staticmethod
    def _prelaunch_phase(inp: MissionInputs) -> MissionPhase:
        if not inp.cued:
            return MissionPhase.IDLE
        if not (inp.in_fov and inp.lock_stable):
            return MissionPhase.ACQUIRE
        if not (inp.reference_ready and inp.class_asserted):
            return MissionPhase.STUDY
        return MissionPhase.READY

    def _to_engage_inputs(self, inp: MissionInputs) -> EngageInputs:
        # Post-trigger: the operator HAS authorised and the target IS confirmed (that is what the trigger
        # + STUDY established), so these are True into the engage-FSM; the flight self-safe rules do the rest.
        return EngageInputs(
            now=inp.now,
            launched=inp.launched,
            link_healthy=inp.link_healthy,
            guidance_age_s=inp.guidance_age_s,
            range_from_launch_m=inp.range_from_launch_m,
            altitude_m=inp.altitude_m,
            t_go_s=inp.t_go_s,
            range_to_target_m=inp.range_to_target_m,
            miss_phase_rad=inp.miss_phase_rad,
            in_fov=inp.in_fov,
            operator_authorized=True,
            target_confirmed=True,
            guidance_abort=inp.guidance_abort,
            model_wrong=inp.model_wrong,
            intercepted=inp.intercepted,
        )

    def step(self, inp: MissionInputs) -> MissionDecision:
        # Terminal/sticky states never revert.
        if self._phase in (MissionPhase.COMPLETE, MissionPhase.ABORTED):
            act = MissionAction.ABORT if self._phase is MissionPhase.ABORTED else MissionAction.CONTINUE
            return MissionDecision(self._phase, act, "sticky",
                                   kinetic_authorized=self._phase is MissionPhase.COMPLETE)

        # Fail-safe on a malformed clock (matches engage_fsm).
        if not math.isfinite(inp.now):
            self._phase = MissionPhase.ABORTED
            return MissionDecision(self._phase, MissionAction.ABORT, "non_finite_clock", kinetic_authorized=False)

        # ── PRE-TRIGGER phases: default-DENY, revertible, CANCELlable ────────────────────────────────
        if self._phase in (MissionPhase.IDLE, MissionPhase.ACQUIRE, MissionPhase.STUDY, MissionPhase.READY):
            # Operator veto -> back to IDLE (SAFE returns to standby; re-acquire on next cue).
            if inp.operator_cancel:
                self._phase = MissionPhase.IDLE
                return MissionDecision(self._phase, MissionAction.OBSERVE, "operator_cancel",
                                       kinetic_authorized=False)

            # Trigger: honoured ONLY from READY, with a valid authorization AND a ready reference.
            if inp.operator_trigger:
                ready = self._prelaunch_phase(inp) is MissionPhase.READY
                if ready and inp.authorization_valid and inp.reference_snapshot is not None:
                    # OPERATOR COMMIT: freeze the immutable reference, default-DENY ends.
                    self._reference = freeze_reference(inp.reference_snapshot, inp.now)
                    self._phase = MissionPhase.ENGAGING
                    return self._step_engaging(inp, just_committed=True)
                # A trigger without readiness/authorization is DENIED — never launches.
                self._phase = self._prelaunch_phase(inp)
                return MissionDecision(self._phase, MissionAction.OBSERVE,
                                       "trigger_denied_not_ready_or_unauthorized", kinetic_authorized=False)

            # No trigger: advance/regress the pre-trigger phase from the perception state.
            self._phase = self._prelaunch_phase(inp)
            return MissionDecision(self._phase, MissionAction.OBSERVE, self._phase.value.lower(),
                                   kinetic_authorized=False)

        # ── POST-TRIGGER: delegate to the EngagementController (default-COMPLETE) ────────────────────
        return self._step_engaging(inp, just_committed=False)

    def _step_engaging(self, inp: MissionInputs, *, just_committed: bool) -> MissionDecision:
        dec = self._engage.step(self._to_engage_inputs(inp))
        # Map the engage-FSM outcome onto the mission phase.
        if dec.phase is EngagePhase.COMPLETE:
            self._phase = MissionPhase.COMPLETE
            action = MissionAction.CONTINUE
        elif dec.phase is EngagePhase.ABORTED:
            self._phase = MissionPhase.ABORTED
            action = MissionAction.ABORT
        else:
            self._phase = MissionPhase.ENGAGING
            action = {
                EngageAction.CONTINUE: MissionAction.CONTINUE,
                EngageAction.HOLD_LAST: MissionAction.HOLD_LAST,
                EngageAction.ABORT: MissionAction.ABORT,
            }[dec.action]
        reason = ("operator_commit" if just_committed and self._phase is MissionPhase.ENGAGING
                  else dec.reason)
        # Kinetic is authorised the moment the operator committed (post-trigger), regardless of the
        # in-flight sub-phase; the terminal effector is still gated below by engage/arming/hw-kill.
        return MissionDecision(self._phase, action, reason,
                               kinetic_authorized=self._phase is not MissionPhase.ABORTED,
                               engage_phase=dec.phase)
