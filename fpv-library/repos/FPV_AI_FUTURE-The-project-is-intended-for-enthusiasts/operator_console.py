"""Physical two-button operator console — maps button edges to the engagement protocol (Block-3 HITL).

TWO buttons on the bench, the whole human authority ([[block03-human-authority-doctrine]]):

  * BUTTON 1 — CAPTURE / LAUNCH (a two-press):
        press in STANDBY  -> DESIGNATE the target (lock the seeker onto the current aim)   -> LOCKED
        press in LOCKED   -> LAUNCH: submit the dual-signed commit (arms once studied+READY) -> LAUNCHED
  * BUTTON 2 — CHANGE / CANCEL:
        press in LOCKED   -> operator VETO: revert the mission to IDLE (change target / drop the lock)
        press in LAUNCHED -> ABORT: force the sticky hardware KILL (cancel the launch)         -> ABORTED

This module is PURE LOGIC — no GPIO, no crypto, no runtime.  It consumes debounced button *edges* plus
the observable mission state, and emits an ``OperatorIntent`` the runner applies to the ProductionRuntime
(designate / submit-commit / operator-cancel / kill).  Post-launch it is a DOER, not a doubter: a second
CAPTURE press is ignored, and only the CANCEL button (mapped to the dominant KILL) can stop it.  KILL is
sticky — once ABORTED the console stays safe until it is rebuilt (a deliberate power/soft reset).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ConsoleState(str, Enum):
    STANDBY = "STANDBY"     # nothing locked; CAPTURE designates a target
    LOCKED = "LOCKED"       # target designated, studying; CAPTURE launches, CANCEL changes/drops it
    LAUNCHED = "LAUNCHED"   # commit submitted (arming in progress/live); CANCEL aborts (KILL)
    ABORTED = "ABORTED"     # sticky safe — operator killed the engagement


@dataclass(frozen=True)
class OperatorIntent:
    """What the runner should do to the ProductionRuntime this tick (default: nothing)."""
    designate: bool = False        # rt.designate(current aim) — lock the seeker onto the target
    submit_commit: bool = False    # sign + submit the dual-Ed25519 commit -> arms when READY
    operator_cancel: bool = False  # mission veto (pre-launch) -> revert to IDLE (change/drop target)
    kill: bool = False             # dominant sticky disarm (post-launch) -> cancel the launch
    note: str = ""                 # human-readable reason (telemetry / dump)


class OperatorConsole:
    """The two-button state machine. Feed it debounced edges + mission observability each tick."""

    def __init__(self) -> None:
        self._state = ConsoleState.STANDBY

    @property
    def state(self) -> ConsoleState:
        return self._state

    def on_tick(self, *, capture_edge: bool, cancel_edge: bool, target_available: bool) -> OperatorIntent:
        """One console tick.

        ``capture_edge`` / ``cancel_edge`` are single rising edges (one True per physical press, already
        debounced).  ``target_available`` is True when the seeker currently has something to lock (a blob
        in view) — CAPTURE from STANDBY is ignored without it (can't lock empty sky).
        """
        # ABORTED is sticky: the KILL latched. No button revives it (rebuild the console to re-enable).
        if self._state is ConsoleState.ABORTED:
            return OperatorIntent(note="aborted_sticky")

        # CANCEL is evaluated first so a simultaneous double-press fails SAFE (cancel wins over launch).
        if cancel_edge:
            if self._state is ConsoleState.LOCKED:
                self._state = ConsoleState.STANDBY
                return OperatorIntent(operator_cancel=True, note="cancel_change_target")
            if self._state is ConsoleState.LAUNCHED:
                self._state = ConsoleState.ABORTED
                return OperatorIntent(kill=True, note="cancel_launch_abort")
            return OperatorIntent(note="cancel_noop")   # nothing to cancel in STANDBY

        if capture_edge:
            if self._state is ConsoleState.STANDBY:
                if not target_available:
                    return OperatorIntent(note="capture_no_target")
                self._state = ConsoleState.LOCKED
                return OperatorIntent(designate=True, note="designate_lock")
            if self._state is ConsoleState.LOCKED:
                self._state = ConsoleState.LAUNCHED
                return OperatorIntent(submit_commit=True, note="launch_commit")
            # LAUNCHED: a doer, not a doubter — a second CAPTURE does nothing.
            return OperatorIntent(note="capture_ignored_post_launch")

        return OperatorIntent()   # no edge this tick
