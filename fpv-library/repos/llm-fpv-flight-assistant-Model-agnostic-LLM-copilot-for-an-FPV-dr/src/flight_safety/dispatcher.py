import asyncio
import math
import time

from pydantic import ValidationError
from flight_safety.config import Limits
from flight_safety.geofence import inside_geofence, project_latlon
from flight_safety.models import (
    parse_command, GotoCommand, OrbitCommand, ArmTakeoffCommand,
)
from flight_safety.validation import validate_command


class Dispatcher:
    """Validate then execute commands against a bridge. Pure glue, no transport."""

    def __init__(self, bridge, limits: Limits, geofence: list[tuple[float, float]]):
        self._bridge = bridge
        self._limits = limits
        self._geofence = geofence
        self._offboard = False
        self._setpoint = (0.0, 0.0, 0.0, 0.0)
        self._setpoint_ts = 0.0
        self._tlm_cache = None  # type: ignore
        self._stream_task = None
        self._clock = time.monotonic
        self._stale_s = 0.5
        self._stream_hz = 20

    async def handle(self, raw: dict) -> dict:
        try:
            cmd = parse_command(raw)
        except ValidationError as e:
            return {"status": "rejected", "reason": f"Malformed command: {e.errors()[0]['msg']}"}
        try:
            tlm = await self._bridge.read_telemetry()
        except Exception as e:  # telemetry unavailable -> fail safe, do not actuate
            return {"status": "error", "reason": f"Telemetry read failed: {e}"}
        result = validate_command(cmd, tlm, self._limits, self._geofence)
        if not result.ok:
            return {"status": "rejected", "reason": result.reason}
        try:
            await self._execute(cmd)
        except Exception as e:
            # Actuation failed mid-command: attempt to fail safe (hand back to human / hold).
            try:
                await self._bridge.handback()
            except Exception:
                pass
            return {"status": "error", "verb": cmd.verb, "reason": f"Execution failed: {e}"}
        return {"status": "executed", "verb": cmd.verb}

    async def _execute(self, cmd) -> None:
        if isinstance(cmd, GotoCommand):
            await self._bridge.goto(cmd.lat, cmd.lon, cmd.alt)
        elif isinstance(cmd, OrbitCommand):
            await self._bridge.orbit(cmd.radius, cmd.alt, cmd.center)
        elif isinstance(cmd, ArmTakeoffCommand):
            await self._bridge.arm_takeoff(cmd.alt)
        elif cmd.verb == "loiter":
            await self._bridge.loiter()
        elif cmd.verb == "return_to_launch":
            await self._bridge.return_to_launch()
        elif cmd.verb == "land":
            await self._bridge.land()
        elif cmd.verb == "takeover":
            await self.takeover()
        elif cmd.verb == "handback":
            await self.handback()

    def manual_setpoint(self, forward: float, right: float,
                        down: float, yaw_rate: float) -> None:
        """Validate + store a manual velocity setpoint (no-op unless OFFBOARD)."""
        if not self._offboard:
            return
        lim = self._limits
        # clamp horizontal magnitude, vertical, yaw-rate
        horiz = math.hypot(forward, right)
        if horiz > lim.max_speed_ms and horiz > 0:
            scale = lim.max_speed_ms / horiz
            forward, right = forward * scale, right * scale
        down = max(-lim.max_speed_ms, min(lim.max_speed_ms, down))
        yaw_rate = max(-lim.max_yaw_rate_dps, min(lim.max_yaw_rate_dps, yaw_rate))
        # geofence brake: if projected position would be outside, zero horizontal
        t = self._tlm_cache
        if t is not None and self._geofence:
            plat, plon = project_latlon(t.lat, t.lon, t.yaw, forward, right, dt=1.0)
            if not inside_geofence(plat, plon, self._geofence):
                forward, right = 0.0, 0.0
        self._setpoint = (forward, right, down, yaw_rate)
        self._setpoint_ts = self._clock()

    def _effective_setpoint(self, now: float) -> tuple[float, float, float, float]:
        if now - self._setpoint_ts > self._stale_s:
            return (0.0, 0.0, 0.0, 0.0)
        return self._setpoint

    async def takeover(self) -> None:
        tlm = await self._bridge.read_telemetry()
        if not (tlm.armed and tlm.alt_m > 1.0):
            raise RuntimeError("take off first (must be armed and airborne)")
        await self._bridge.takeover()
        self._offboard = True
        self._setpoint = (0.0, 0.0, 0.0, 0.0)
        self._setpoint_ts = self._clock()
        if self._stream_task is None or self._stream_task.done():
            self._stream_task = asyncio.create_task(self._stream_loop())

    async def handback(self) -> None:
        self._offboard = False
        if self._stream_task is not None:
            self._stream_task.cancel()
            self._stream_task = None
        await self._bridge.handback()

    async def _stream_loop(self) -> None:
        period = 1.0 / self._stream_hz
        try:
            ticks = 0
            while self._offboard:
                # refresh telemetry cache ~5 Hz for the geofence brake
                if ticks % max(1, self._stream_hz // 5) == 0:
                    try:
                        self._tlm_cache = await self._bridge.read_telemetry()
                    except Exception:
                        pass
                f, r, dn, yr = self._effective_setpoint(self._clock())
                try:
                    await self._bridge.set_velocity_body(f, r, dn, yr)
                except Exception:
                    pass
                ticks += 1
                await asyncio.sleep(period)
        except asyncio.CancelledError:
            pass

    async def abort(self) -> None:
        """Immediate safe state: leave OFFBOARD, hand control back / hold."""
        await self.handback()

    async def telemetry(self) -> dict:
        """Return a current telemetry snapshot as a plain dict (for the assistant)."""
        return (await self._bridge.read_telemetry()).model_dump()
