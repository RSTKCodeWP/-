import pytest
from flight_safety.config import Limits
from flight_safety.models import Telemetry
from flight_safety.dispatcher import Dispatcher

GEOFENCE = [(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]
LIMITS = Limits()


class FakeBridge:
    def __init__(self):
        self.calls = []
        self._tlm = Telemetry(lat=0.0, lon=0.0, alt_m=10.0, speed_ms=0.0,
                              battery_pct=0.9, flight_mode="HOLD", armed=True,
                              gps_ok=True, ekf_ok=True)

    async def read_telemetry(self): return self._tlm
    async def goto(self, lat, lon, alt): self.calls.append(("goto", lat, lon, alt))
    async def orbit(self, r, a, c): self.calls.append(("orbit", r, a, c))
    async def arm_takeoff(self, alt): self.calls.append(("arm_takeoff", alt))
    async def loiter(self): self.calls.append(("loiter",))
    async def return_to_launch(self): self.calls.append(("rtl",))
    async def land(self): self.calls.append(("land",))
    async def takeover(self): self.calls.append(("takeover",))
    async def handback(self): self.calls.append(("handback",))


@pytest.mark.asyncio
async def test_valid_command_is_executed():
    bridge = FakeBridge()
    d = Dispatcher(bridge, LIMITS, GEOFENCE)
    res = await d.handle({"verb": "goto", "lat": 0.5, "lon": 0.5, "alt": 30})
    assert res["status"] == "executed"
    assert ("goto", 0.5, 0.5, 30) in bridge.calls


@pytest.mark.asyncio
async def test_unsafe_command_is_rejected_and_not_executed():
    bridge = FakeBridge()
    d = Dispatcher(bridge, LIMITS, GEOFENCE)
    res = await d.handle({"verb": "goto", "lat": 9.0, "lon": 0.0, "alt": 30})
    assert res["status"] == "rejected"
    assert "geofence" in res["reason"].lower()
    assert bridge.calls == []  # never executed


@pytest.mark.asyncio
async def test_malformed_command_is_rejected():
    bridge = FakeBridge()
    d = Dispatcher(bridge, LIMITS, GEOFENCE)
    res = await d.handle({"verb": "nonsense"})
    assert res["status"] == "rejected"
    assert bridge.calls == []


@pytest.mark.parametrize("raw,expected_call", [
    ({"verb": "arm_takeoff", "alt": 5}, ("arm_takeoff", 5)),
    ({"verb": "orbit", "radius": 20, "alt": 25}, ("orbit", 20, 25, None)),
    ({"verb": "loiter"}, ("loiter",)),
    ({"verb": "return_to_launch"}, ("rtl",)),
    ({"verb": "land"}, ("land",)),
    # NOTE: "takeover" requires armed+airborne (enforced in Dispatcher.takeover);
    # it cannot route from this ground-state fixture. Its bridge routing + the
    # armed+airborne gate are covered in test_dispatcher_offboard.py.
    ({"verb": "handback"}, ("handback",)),
])
@pytest.mark.asyncio
async def test_each_verb_routes_to_bridge(raw, expected_call):
    bridge = FakeBridge()
    # Ground state so every verb (incl. arm_takeoff, which forbids being already
    # armed+airborne) passes validation and reaches _execute.
    bridge._tlm = Telemetry(lat=0.0, lon=0.0, alt_m=0.0, speed_ms=0.0,
                            battery_pct=0.9, flight_mode="HOLD", armed=False,
                            gps_ok=True, ekf_ok=True)
    d = Dispatcher(bridge, LIMITS, GEOFENCE)
    res = await d.handle(raw)
    assert res["status"] == "executed"
    assert expected_call in bridge.calls


@pytest.mark.asyncio
async def test_abort_calls_handback():
    bridge = FakeBridge()
    d = Dispatcher(bridge, LIMITS, GEOFENCE)
    await d.abort()
    assert ("handback",) in bridge.calls


class FailingGotoBridge(FakeBridge):
    async def goto(self, lat, lon, alt):
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_execution_error_fails_safe():
    bridge = FailingGotoBridge()
    d = Dispatcher(bridge, LIMITS, GEOFENCE)
    res = await d.handle({"verb": "goto", "lat": 0.5, "lon": 0.5, "alt": 30})
    assert res["status"] == "error"
    assert "boom" in res["reason"]
    assert ("handback",) in bridge.calls  # safe fallback was invoked


class FailingTelemetryBridge(FakeBridge):
    async def read_telemetry(self):
        raise RuntimeError("link down")


@pytest.mark.asyncio
async def test_telemetry_read_error_is_rejected():
    bridge = FailingTelemetryBridge()
    d = Dispatcher(bridge, LIMITS, GEOFENCE)
    res = await d.handle({"verb": "goto", "lat": 0.5, "lon": 0.5, "alt": 30})
    assert res["status"] == "error"
    assert bridge.calls == []  # never executed
