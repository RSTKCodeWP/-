"""Nav quality gate — pure logic for warmup, hold, and FLIGHT OK (unit-testable)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GateInputs:
    tracking_ok: bool
    nav_ready: bool
    armed: bool
    hold_last_on_drop: bool
    warmup_s: float
    now: float
    nav_valid_since: float
    fps: float
    camera_ok: bool


@dataclass
class GateState:
    nav_valid: bool
    holding: bool
    nav_valid_since: float
    zero_fps_since: float


def step_gate(prev: GateState, inp: GateInputs) -> GateState:
    """One control-cycle update for nav_valid / holding."""
    nav_valid_since = prev.nav_valid_since
    holding = prev.holding
    zero_fps = prev.zero_fps_since

    if inp.tracking_ok and inp.nav_ready:
        if nav_valid_since <= 0:
            nav_valid_since = inp.now
        nav_valid = (inp.now - nav_valid_since) >= inp.warmup_s
        holding = False
    else:
        nav_valid_since = 0.0
        nav_valid = False
        holding = inp.hold_last_on_drop and inp.armed

    # FPS watchdog while armed
    if inp.fps < 1.0 and inp.armed:
        if zero_fps <= 0:
            zero_fps = inp.now
        elif inp.now - zero_fps > 1.0:
            holding = True
            nav_valid = False
    else:
        zero_fps = 0.0

    if not inp.camera_ok:
        nav_valid = False
        if inp.armed and inp.hold_last_on_drop:
            holding = True

    return GateState(
        nav_valid=nav_valid,
        holding=holding,
        nav_valid_since=nav_valid_since,
        zero_fps_since=zero_fps,
    )


def flight_ok(*, health_ready: bool, nav_valid: bool, armed: bool, holding: bool) -> bool:
    """Safe to arm PosHold from RC."""
    if armed:
        return nav_valid and not holding
    return health_ready and nav_valid
