import asyncio
from mavsdk import System
from mavsdk.action import OrbitYawBehavior
from mavsdk.offboard import VelocityBodyYawspeed
from flight_safety.models import Telemetry


class FlightBridge:
    """Owns the single MAVSDK connection and exposes telemetry + executors."""

    def __init__(self, address: str) -> None:
        self._address = address
        self._drone = System()
        self._connected = False

    async def connect(self, timeout_s: float = 30.0) -> None:
        await self._drone.connect(system_address=self._address)
        async def _wait():
            async for state in self._drone.core.connection_state():
                if state.is_connected:
                    return
        await asyncio.wait_for(_wait(), timeout=timeout_s)
        self._connected = True

    async def read_telemetry(self) -> Telemetry:
        """Read one consistent telemetry snapshot."""
        pos = await self._drone.telemetry.position().__anext__()
        bat = await self._drone.telemetry.battery().__anext__()
        mode = await self._drone.telemetry.flight_mode().__anext__()
        armed = await self._drone.telemetry.armed().__anext__()
        health = await self._drone.telemetry.health().__anext__()
        vel = await self._drone.telemetry.velocity_ned().__anext__()
        att = await self._drone.telemetry.attitude_euler().__anext__()
        speed = (vel.north_m_s ** 2 + vel.east_m_s ** 2 + vel.down_m_s ** 2) ** 0.5
        # MAVSDK's remaining_percent is 0-100 in this version (older versions: 0.0-1.0);
        # normalize to the 0.0-1.0 scale the rest of the system expects.
        raw_batt = bat.remaining_percent
        battery_pct = raw_batt / 100.0 if raw_batt > 1.0 else raw_batt
        return Telemetry(
            lat=pos.latitude_deg,
            lon=pos.longitude_deg,
            alt_m=pos.relative_altitude_m,
            speed_ms=speed,
            battery_pct=battery_pct,
            flight_mode=str(mode),
            armed=armed,
            gps_ok=health.is_global_position_ok,
            ekf_ok=health.is_local_position_ok,
            roll=att.roll_deg,
            pitch=att.pitch_deg,
            yaw=att.yaw_deg,
        )

    @property
    def drone(self) -> System:
        return self._drone

    async def _wait_until(self, predicate, timeout_s: float, poll_s: float = 0.5) -> None:
        """Telemetry-gate: block until predicate(Telemetry) is true or timeout."""
        async def _loop():
            while True:
                t = await self.read_telemetry()
                if predicate(t):
                    return
                await asyncio.sleep(poll_s)
        await asyncio.wait_for(_loop(), timeout=timeout_s)

    async def arm_takeoff(self, alt: float) -> None:
        await self._drone.action.set_takeoff_altitude(alt)
        await self._drone.action.arm()
        await self._drone.action.takeoff()
        await self._wait_until(lambda t: t.alt_m >= alt * 0.9, timeout_s=30)

    async def goto(self, lat: float, lon: float, alt: float) -> None:
        pos = await self._drone.telemetry.position().__anext__()
        amsl = pos.absolute_altitude_m - pos.relative_altitude_m + alt
        await self._drone.action.goto_location(lat, lon, amsl, float("nan"))
        await self._wait_until(
            lambda t: abs(t.lat - lat) < 1e-4 and abs(t.lon - lon) < 1e-4,
            timeout_s=60,
        )

    async def orbit(self, radius: float, alt: float,
                    center: tuple[float, float] | None) -> None:
        pos = await self._drone.telemetry.position().__anext__()
        lat, lon = center if center else (pos.latitude_deg, pos.longitude_deg)
        amsl = pos.absolute_altitude_m - pos.relative_altitude_m + alt
        await self._drone.action.do_orbit(
            radius, 3.0, OrbitYawBehavior.HOLD_FRONT_TO_CIRCLE_CENTER, lat, lon, amsl,
        )
        await asyncio.sleep(3)  # allow the orbit to establish

    async def loiter(self) -> None:
        await self._drone.action.hold()

    async def return_to_launch(self) -> None:
        await self._drone.action.return_to_launch()

    async def land(self) -> None:
        await self._drone.action.land()

    async def takeover(self) -> None:
        """Enter OFFBOARD so velocity setpoints drive the vehicle (assistant or human-via-GCS)."""
        await self._drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
        await self._drone.offboard.start()

    async def set_velocity_body(self, forward: float, right: float,
                                down: float, yaw_rate: float) -> None:
        await self._drone.offboard.set_velocity_body(
            VelocityBodyYawspeed(forward, right, down, yaw_rate))

    async def handback(self) -> None:
        """Leave OFFBOARD and park in HOLD (safe autonomous state)."""
        try:
            await self._drone.offboard.stop()
        except Exception:
            pass  # not in offboard -> ignore
        await self._drone.action.hold()

    async def close(self) -> None:
        # MAVSDK has no public disconnect, but System spawns a mavsdk_server
        # subprocess that binds gRPC :50051 and the MAVLink udpin port. If we
        # only drop our flag, that subprocess leaks and collides with the next
        # FlightBridge's server on those ports. mavsdk 3.15 exposes a private
        # _stop_mavsdk_server() that kills the Popen and re-inits the System;
        # call it defensively so teardown never raises and stays idempotent
        # (a second call is a no-op once _server_process is reset to None).
        self._connected = False
        stop = getattr(self._drone, "_stop_mavsdk_server", None)
        if callable(stop):
            try:
                stop()
            except Exception:
                pass  # teardown must never raise
