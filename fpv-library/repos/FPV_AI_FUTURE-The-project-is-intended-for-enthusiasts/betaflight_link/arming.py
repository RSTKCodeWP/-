"""Arming / throttle-authority state machine (Block-3 S4) -- the safety core.

This owns the single most dangerous authority in the system: whether the aircraft is
ARMED and who commands throttle. It transitions the interceptor from SAFE (disarmed) to
live AI control ONLY through a deliberate, gated sequence, and it makes ``kill`` dominant
and sticky.

Sequence (design 3.4): SAFE -> PREARM -> ARMED_IDLE -> STABILIZE -> THROTTLE_RAMP -> AI_ACTIVE.

THE PHYSICAL FIRE KEYPRESS IS DATA INSIDE THE AUTHORIZATION, NOT A FREE-FLOATING SIGNAL.
The launch console captures the operator's ARM-key + FIRE-button as part of building the
dual-signed ``engagement_handoff`` authorization (``keypress_recorded`` + ``keypress_ts``,
within the auth's issued..expires window). The arming machine therefore arms on a *committed*
authorization -- it never holds a separate latched keypress that could go stale and auto-arm
a later, unrelated authorization. (That class of bug was found by adversarial review and
designed out here.)

Hard invariants (enforced + tested):
  1. The arm channel (AUX1) is HIGH only in ARMED_IDLE/STABILIZE/THROTTLE_RAMP/AI_ACTIVE.
     LOW (disarmed) in SAFE, PREARM and KILLED.
  2. Reaching ARMED_IDLE requires a COMMITTED authorization: verifier-passed, keypress
     recorded with a timestamp inside [issued, expires], unexpired, and -- for a LIVE
     engagement -- non-synthetic. Default-deny otherwise. There is no separate keypress to
     go stale.
  3. ``kill()`` from ANY state immediately forces KILLED (AUX1 low, throttle idle) and
     dominates everything in the same tick. Sticky: re-arming requires reset() AND a fresh
     committed authorization.
  4. Throttle stays at idle until THROTTLE_RAMP, then ramps smoothly; AI throttle authority
     applies only in AI_ACTIVE. A non-finite guidance command degrades to neutral/idle
     (msp_codec sanitises it) -- it never crashes the loop or commands high throttle.
  5. If the authorization expires while armed, the next tick aborts to KILLED.

The independent hardware kill (separate module/MCU) sits BELOW this. This module never opens
a serial port and never sends bytes -- it only computes the RC authority each tick. Callers
must pass a monotonic clock (time.monotonic); the ramp clamps elapsed >= 0 defensively.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass
from typing import Protocol

from fpv_ai.betaflight_link import msp_codec as mc


class ArmState(str, enum.Enum):
    SAFE = "SAFE"
    PREARM = "PREARM"
    ARMED_IDLE = "ARMED_IDLE"
    STABILIZE = "STABILIZE"
    THROTTLE_RAMP = "THROTTLE_RAMP"
    AI_ACTIVE = "AI_ACTIVE"
    KILLED = "KILLED"


_ARMED_STATES = frozenset({ArmState.ARMED_IDLE, ArmState.STABILIZE, ArmState.THROTTLE_RAMP, ArmState.AI_ACTIVE})


@dataclass(frozen=True)
class ArmingAuthorization:
    """A verified authorization to arm (produced by the launch console / safety verifier).

    The FIRE keypress is captured here as ``keypress_recorded`` + ``keypress_ts``; a valid
    commit requires the press timestamp to fall within the authorization's own window, so a
    press cannot predate (or outlive) the authorization it commits.
    """

    verifier_passed: bool
    keypress_recorded: bool
    keypress_ts: float
    issued_at_s: float
    expires_at_s: float
    mission_goal: str = "RECON"   # RECON | CONTACT | KINETIC
    synthetic: bool = True        # live engagement REQUIRES synthetic=False

    def authorized(self, now: float, *, allow_synthetic: bool) -> bool:
        """Right to enter PREARM: verifier passed, unexpired, and live (or bench-synthetic)."""
        # Non-finite INPUTS are never a right to arm. A NaN clock OR a NaN expiry both make
        # `now >= expires` evaluate False (read as "unexpired") and would defeat the in-flight
        # abort. Reject the whole non-finite class up front (clock here, auth window below).
        if not math.isfinite(now) or not math.isfinite(self.expires_at_s):
            return False
        if not self.verifier_passed:
            return False
        if now >= self.expires_at_s:
            return False
        if self.synthetic and not allow_synthetic:
            return False
        return True

    def committed(self, now: float, *, allow_synthetic: bool) -> bool:
        """Right to ARM: authorized AND a physical keypress recorded within this auth window."""
        if not self.authorized(now, allow_synthetic=allow_synthetic):
            return False
        if not self.keypress_recorded:
            return False
        if not (math.isfinite(self.issued_at_s) and math.isfinite(self.keypress_ts)):
            return False
        if not (self.issued_at_s <= self.keypress_ts <= self.expires_at_s):
            return False
        return True


@dataclass(frozen=True)
class ArmingConfig:
    idle_us: int = 1000
    neutral_us: int = 1500
    hover_base_us: int = 1500
    arm_aux_us: int = 2000
    disarm_aux_us: int = 1000
    armed_idle_dwell_s: float = 0.3
    stabilize_dwell_s: float = 0.3
    ramp_s: float = 1.0
    allow_synthetic_bench: bool = False  # LIVE default: a synthetic authorization cannot arm

    def __post_init__(self) -> None:
        if self.ramp_s <= 0:
            raise ValueError("ramp_s must be > 0 (a zero ramp removes the smooth-spin-up invariant)")
        if self.armed_idle_dwell_s < 0 or self.stabilize_dwell_s < 0:
            raise ValueError("dwell times must be non-negative")


class _AICommandLike(Protocol):
    roll_cmd: float
    pitch_cmd: float
    yaw_rate_cmd: float
    throttle_cmd: float


@dataclass(frozen=True)
class ArmingOutput:
    state: ArmState
    rc: dict[str, int]
    armed: bool
    reason: str


class ArmingStateMachine:
    def __init__(self, config: ArmingConfig | None = None) -> None:
        self.cfg = config or ArmingConfig()
        self._state = ArmState.SAFE
        self._auth: ArmingAuthorization | None = None
        self._killed = False
        self._kill_reason = ""
        self._t_enter = 0.0  # time the current state was entered

    # ── external events ──────────────────────────────────────────────────────────
    def authorize(self, auth: ArmingAuthorization) -> None:
        """Provide a verified (and typically committed) authorization. Ignored once killed."""
        if self._killed:
            return
        self._auth = auth

    def clear_authorization(self) -> None:
        self._auth = None

    def kill(self, reason: str = "manual_kill") -> None:
        """Dominant, sticky kill: disarm now and stay disarmed until reset()."""
        self._killed = True
        if not self._kill_reason:
            self._kill_reason = reason

    def abort(self, reason: str) -> None:
        """An abort condition (auth expired, geofence, lost-link, operator). Safe action = disarm."""
        self.kill(reason)

    def reset(self) -> None:
        """Recover from KILLED back to SAFE. Re-arming still requires a fresh committed authorization."""
        self._killed = False
        self._kill_reason = ""
        self._auth = None
        self._state = ArmState.SAFE
        self._t_enter = 0.0

    # ── per-tick advance ─────────────────────────────────────────────────────────
    def tick(self, now: float, guidance_cmd: _AICommandLike | None = None) -> ArmingOutput:
        # (0) a non-finite clock is a critical fault -> fail safe to a sticky KILLED.
        # (The authorized() guard already blocks arming on NaN; this makes time-source
        # corruption an explicit, recoverable-only-via-reset abort rather than a silent hold.)
        if not math.isfinite(now):
            self.kill("non_finite_clock")
            self._state = ArmState.KILLED
            return self._disarmed(ArmState.KILLED, "non_finite_clock")

        # (1) kill dominates everything, evaluated FIRST.
        if self._killed:
            self._goto(ArmState.KILLED, now)
            return self._disarmed(ArmState.KILLED, self._kill_reason or "killed")

        # (2) once armed, an expired/invalid authorization aborts immediately.
        if self._state in _ARMED_STATES and not self._authorized(now):
            self.kill("authorization_expired")
            self._goto(ArmState.KILLED, now)
            return self._disarmed(ArmState.KILLED, "authorization_expired")

        if self._state == ArmState.SAFE:
            return self._tick_safe(now)
        if self._state == ArmState.PREARM:
            return self._tick_prearm(now)
        if self._state == ArmState.ARMED_IDLE:
            return self._dwell(now, ArmState.STABILIZE, self.cfg.armed_idle_dwell_s, throttle=self.cfg.idle_us)
        if self._state == ArmState.STABILIZE:
            return self._dwell(now, ArmState.THROTTLE_RAMP, self.cfg.stabilize_dwell_s, throttle=self.cfg.idle_us)
        if self._state == ArmState.THROTTLE_RAMP:
            return self._tick_ramp(now)
        if self._state == ArmState.AI_ACTIVE:
            return self._tick_ai(now, guidance_cmd)
        return self._disarmed(self._state, "unknown_state")  # unreachable

    # ── per-state handlers ───────────────────────────────────────────────────────
    def _tick_safe(self, now: float) -> ArmingOutput:
        if self._authorized(now):
            self._goto(ArmState.PREARM, now)
            return self._disarmed(ArmState.PREARM, "authorized_prearm")
        return self._disarmed(ArmState.SAFE, "safe_disarmed")

    def _tick_prearm(self, now: float) -> ArmingOutput:
        if not self._authorized(now):
            self._goto(ArmState.SAFE, now)
            return self._disarmed(ArmState.SAFE, "authorization_lost")
        if self._committed(now):
            self._goto(ArmState.ARMED_IDLE, now)
            return self._armed_neutral(ArmState.ARMED_IDLE, self.cfg.idle_us, "armed_on_commit")
        return self._disarmed(ArmState.PREARM, "prearm_waiting_commit")

    def _tick_ramp(self, now: float) -> ArmingOutput:
        elapsed = max(0.0, now - self._t_enter)  # defensive against a backwards clock
        frac = elapsed / self.cfg.ramp_s
        frac = 1.0 if frac > 1.0 else frac
        throttle = int(round(self.cfg.idle_us + frac * (self.cfg.hover_base_us - self.cfg.idle_us)))
        if frac >= 1.0:
            self._goto(ArmState.AI_ACTIVE, now)
            return self._armed_neutral(ArmState.AI_ACTIVE, self.cfg.hover_base_us, "ramp_complete_ai_active")
        return self._armed_neutral(ArmState.THROTTLE_RAMP, throttle, "throttle_ramp")

    def _tick_ai(self, now: float, cmd: _AICommandLike | None) -> ArmingOutput:
        if cmd is None:
            return self._armed_neutral(ArmState.AI_ACTIVE, self.cfg.hover_base_us, "ai_active_hold")
        rc = {
            "roll": mc.symmetric_to_us(cmd.roll_cmd),
            "pitch": mc.symmetric_to_us(cmd.pitch_cmd),
            "yaw": mc.symmetric_to_us(cmd.yaw_rate_cmd),
            "throttle": mc.throttle_to_us(cmd.throttle_cmd),
            "aux1": self.cfg.arm_aux_us,
            "aux2": 1000, "aux3": 1000, "aux4": 1000,
        }
        return ArmingOutput(ArmState.AI_ACTIVE, rc, armed=True, reason="ai_active")

    # ── helpers ──────────────────────────────────────────────────────────────────
    def _dwell(self, now: float, nxt: ArmState, dwell_s: float, *, throttle: int) -> ArmingOutput:
        if (now - self._t_enter) >= dwell_s:
            self._goto(nxt, now)
            return self._armed_neutral(nxt, throttle, f"enter_{nxt.value.lower()}")
        return self._armed_neutral(self._state, throttle, f"{self._state.value.lower()}_dwell")

    def _authorized(self, now: float) -> bool:
        return self._auth is not None and self._auth.authorized(now, allow_synthetic=self.cfg.allow_synthetic_bench)

    def _committed(self, now: float) -> bool:
        return self._auth is not None and self._auth.committed(now, allow_synthetic=self.cfg.allow_synthetic_bench)

    def _goto(self, state: ArmState, now: float) -> None:
        if state != self._state:
            self._state = state
            self._t_enter = now

    def _disarmed(self, state: ArmState, reason: str) -> ArmingOutput:
        rc = {
            "roll": self.cfg.neutral_us, "pitch": self.cfg.neutral_us, "yaw": self.cfg.neutral_us,
            "throttle": self.cfg.idle_us, "aux1": self.cfg.disarm_aux_us,
            "aux2": 1000, "aux3": 1000, "aux4": 1000,
        }
        return ArmingOutput(state, rc, armed=False, reason=reason)

    def _armed_neutral(self, state: ArmState, throttle: int, reason: str) -> ArmingOutput:
        rc = {
            "roll": self.cfg.neutral_us, "pitch": self.cfg.neutral_us, "yaw": self.cfg.neutral_us,
            "throttle": throttle, "aux1": self.cfg.arm_aux_us,
            "aux2": 1000, "aux3": 1000, "aux4": 1000,
        }
        return ArmingOutput(state, rc, armed=True, reason=reason)

    @property
    def state(self) -> ArmState:
        return self._state

    @property
    def is_armed(self) -> bool:
        return self._state in _ARMED_STATES
