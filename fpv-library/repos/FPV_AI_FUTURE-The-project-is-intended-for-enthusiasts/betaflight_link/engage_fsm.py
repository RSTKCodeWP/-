"""Commit-based engagement / abort authority (Block-3 S4, Phase C).

WHY THIS EXISTS
---------------
The legacy ``FailsafeController`` aborts the instant the RF link drops (link_timeout_s = 0.2 s).
That is correct for a *tethered*, operator-in-the-loop drone, but WRONG for the block's stated
fire-and-forget doctrine: once the operator has authorised and the interceptor commits to the
terminal engagement, it must complete the intercept on its own -- a fast interceptor flying AT the
target leaves reliable RF range almost immediately, so a link-loss abort would kill every real
engagement (the audit's "kill-chain is a tether" finding, Phase C).

THE ARCHITECTURE
----------------
Link matters UNTIL commit; after commit the interceptor is autonomous with SELF-CONTAINED abort
rules that need no RF:

  PRE_LAUNCH --launch--> MIDCOURSE --commit criteria--> COMMITTED --intercept--> COMPLETE
                             |  (link required here)         |  (link NOT required here)
                             +----------- ABORT -------------+

  Abort authority (both phases unless noted):
    * geo/alt keep-out box breach        -> ABORT   (self-contained)
    * time-to-live exceeded              -> ABORT   (self-contained)
    * guidance ROE abort (envelope/cross)-> ABORT   (self-contained; from bearing_rate)
    * target lost too long               -> ABORT   (self-contained; guidance watchdog)
    * link loss                          -> ABORT   ONLY in MIDCOURSE (pre-commit)

  Commit criteria (MIDCOURSE -> COMMITTED): operator authorised AND target confirmed as a
  non-responsive threat AND terminal geometry acquired (in-FOV, closing, t_go/range terminal) AND
  inside the keep-out box AND the track model is not flagged wrong.

This DECIDES (CONTINUE / HOLD / ABORT); a single disarm authority (ArmingStateMachine) acts on it,
and the independent HW-kill sits below all of it.  The kinetic effector remains downstream of the
operator-authorisation gate and is not part of this FSM.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass


class EngagePhase(str, enum.Enum):
    PRE_LAUNCH = "PRE_LAUNCH"
    MIDCOURSE = "MIDCOURSE"     # flying toward target, operator-in-loop, link required
    COMMITTED = "COMMITTED"     # terminal engagement, AUTONOMOUS (link not required)
    ABORTED = "ABORTED"         # safed (sticky)
    COMPLETE = "COMPLETE"       # intercept done (sticky)


class EngageAction(str, enum.Enum):
    CONTINUE = "CONTINUE"
    HOLD_LAST = "HOLD_LAST"
    ABORT = "ABORT"


@dataclass(frozen=True)
class EngageConfig:
    max_range_from_launch_m: float = 500.0   # geo keep-out: distance from launch point
    alt_floor_m: float = 5.0                 # alt keep-out floor
    alt_ceiling_m: float = 200.0             # alt keep-out ceiling
    max_engagement_time_s: float = 20.0      # time-to-live from launch
    guidance_hold_s: float = 0.1             # brief LOS gap -> coast
    guidance_abort_s: float = 0.5            # LOS gap beyond this -> target lost -> ABORT
    commit_t_go_s: float = 1.5               # terminal: commit when t_go <= this ...
    commit_range_m: float = 50.0             # ... OR range <= this
    # Committing latches fire-and-forget: the abort is disabled and a lost link no longer stops us. Being
    # CLOSE is not enough to earn that -- we should also be ON A COLLISION COURSE. The miss phase phi_h
    # (angle between the closing velocity and the LOS; phi_h -> 0 == collision course) is that check.
    # None disables it, which is the shipped default so this cannot silently tighten an existing gate.
    commit_max_phi_h_rad: float | None = None

    def __post_init__(self) -> None:
        if not (self.guidance_hold_s < self.guidance_abort_s):
            raise ValueError("guidance_hold_s must be < guidance_abort_s")
        if not (self.alt_floor_m < self.alt_ceiling_m):
            raise ValueError("alt_floor_m must be < alt_ceiling_m")


@dataclass(frozen=True)
class EngageInputs:
    now: float
    launched: bool
    link_healthy: bool
    guidance_age_s: float | None      # seconds since last fresh LOS (None -> never seen)
    range_from_launch_m: float
    altitude_m: float
    t_go_s: float                     # time-to-go (inf if unobservable)
    range_to_target_m: float          # for the commit-range criterion (inf if unknown)
    in_fov: bool
    operator_authorized: bool
    target_confirmed: bool            # confirmed non-responsive threat
    guidance_abort: bool              # bearing_rate raised an ROE abort this tick
    model_wrong: bool                 # IMM sustained model-wrong alarm
    intercepted: bool = False
    # Miss phase (rad): angle between the closing velocity and the LOS; 0 == collision course.
    # None means "not measured" -> the phi_h gate abstains rather than blocking (fpv.guidance.miss_geometry).
    miss_phase_rad: float | None = None


@dataclass(frozen=True)
class EngageDecision:
    action: EngageAction
    phase: EngagePhase
    reason: str


class EngagementController:
    """Fire-and-forget engagement FSM with commit-gated, self-contained abort authority."""

    def __init__(self, config: EngageConfig | None = None) -> None:
        self.cfg = config or EngageConfig()
        self._phase = EngagePhase.PRE_LAUNCH
        self._t_launch: float | None = None

    @property
    def phase(self) -> EngagePhase:
        return self._phase

    def _keepout_breach(self, inp: EngageInputs) -> bool:
        return (inp.range_from_launch_m > self.cfg.max_range_from_launch_m
                or inp.altitude_m < self.cfg.alt_floor_m
                or inp.altitude_m > self.cfg.alt_ceiling_m)

    def _guidance_lost(self, inp: EngageInputs) -> bool:
        g = inp.guidance_age_s
        return g is None or not math.isfinite(g) or g < 0.0 or g > self.cfg.guidance_abort_s

    def _on_collision_course(self, inp: EngageInputs) -> bool:
        """Are we actually on a collision course, not merely close?

        Abstains (True) when either the limit is not configured or the miss phase was not measured -- an
        unmeasured cue must not silently block a commit, the same way it must not silently grant one.
        """
        limit = self.cfg.commit_max_phi_h_rad
        if limit is None or inp.miss_phase_rad is None:
            return True
        return abs(inp.miss_phase_rad) <= limit

    def _commit_criteria_met(self, inp: EngageInputs) -> bool:
        terminal = (inp.t_go_s <= self.cfg.commit_t_go_s
                    or inp.range_to_target_m <= self.cfg.commit_range_m)
        return (inp.operator_authorized and inp.target_confirmed and inp.in_fov
                and not inp.model_wrong and terminal and self._on_collision_course(inp)
                and not self._keepout_breach(inp))

    def step(self, inp: EngageInputs) -> EngageDecision:
        cfg = self.cfg

        # Terminal/sticky states never revert.
        if self._phase in (EngagePhase.ABORTED, EngagePhase.COMPLETE):
            act = EngageAction.ABORT if self._phase is EngagePhase.ABORTED else EngageAction.CONTINUE
            return EngageDecision(act, self._phase, "sticky")

        if not math.isfinite(inp.now):
            self._phase = EngagePhase.ABORTED
            return EngageDecision(EngageAction.ABORT, self._phase, "non_finite_clock")

        # Launch: PRE_LAUNCH -> MIDCOURSE.
        if self._phase is EngagePhase.PRE_LAUNCH:
            if inp.launched:
                self._phase = EngagePhase.MIDCOURSE
                self._t_launch = inp.now
            else:
                return EngageDecision(EngageAction.HOLD_LAST, self._phase, "pre_launch")

        elapsed = inp.now - self._t_launch if self._t_launch is not None else 0.0

        def abort(reason: str) -> EngageDecision:
            self._phase = EngagePhase.ABORTED
            return EngageDecision(EngageAction.ABORT, self._phase, reason)

        # ── Self-contained abort authority (both MIDCOURSE and COMMITTED) ─────────────
        if self._keepout_breach(inp):
            return abort("keepout_box_breach")
        if elapsed > cfg.max_engagement_time_s:
            return abort("ttl_exceeded")
        if inp.guidance_abort:
            return abort("guidance_roe_abort")
        if self._guidance_lost(inp):
            return abort("target_lost")

        # ── Link loss: aborts ONLY before commit (fire-and-forget after) ─────────────
        if self._phase is EngagePhase.MIDCOURSE and not inp.link_healthy:
            return abort("link_loss_pre_commit")

        # ── Commit transition (MIDCOURSE -> COMMITTED) ───────────────────────────────
        if self._phase is EngagePhase.MIDCOURSE and self._commit_criteria_met(inp):
            self._phase = EngagePhase.COMMITTED

        # ── Intercept (COMMITTED -> COMPLETE) ────────────────────────────────────────
        if self._phase is EngagePhase.COMMITTED and inp.intercepted:
            self._phase = EngagePhase.COMPLETE
            return EngageDecision(EngageAction.CONTINUE, self._phase, "intercept_complete")

        # ── Brief guidance gap -> coast ──────────────────────────────────────────────
        g = inp.guidance_age_s
        if g is not None and math.isfinite(g) and g > cfg.guidance_hold_s:
            return EngageDecision(EngageAction.HOLD_LAST, self._phase, "guidance_stale_coast")

        return EngageDecision(EngageAction.CONTINUE, self._phase, "ok")
