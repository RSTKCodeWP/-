import asyncio
import pytest
import pytest_asyncio
from flight_safety.bridge import FlightBridge
from flight_safety.models import Telemetry

pytestmark = pytest.mark.integration  # requires running PX4 SITL


# A single MAVSDK link owns the vehicle, so all integration tests share ONE
# FlightBridge connected once and torn down once. This matches the real
# architecture and avoids leaking mavsdk_server subprocesses that would
# otherwise collide on gRPC :50051 / udpin :14540 between tests.
@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def flight_bridge():
    bridge = FlightBridge("udpin://0.0.0.0:14540")
    await bridge.connect(timeout_s=30)
    try:
        yield bridge
    finally:
        await bridge.close()


# Because the 3 tests share one connection, ordering matters: telemetry first,
# then the arm/takeoff/goto flight, then the handback.
@pytest.mark.asyncio(loop_scope="module")
async def test_bridge_connects_and_streams_telemetry(flight_bridge):
    tlm = await asyncio.wait_for(flight_bridge.read_telemetry(), timeout=10)
    assert isinstance(tlm, Telemetry)
    assert 0.0 <= tlm.battery_pct <= 1.0


@pytest.mark.asyncio(loop_scope="module")
async def test_arm_takeoff_then_goto_is_telemetry_gated(flight_bridge):
    # Wait until position is healthy.
    for _ in range(30):
        t = await flight_bridge.read_telemetry()
        if t.gps_ok:
            break
        await asyncio.sleep(1)
    await flight_bridge.arm_takeoff(alt=5.0)
    t = await flight_bridge.read_telemetry()
    assert t.alt_m >= 3.0, "takeoff did not gate until altitude reached"
    home = (t.lat, t.lon)
    await flight_bridge.goto(home[0] + 0.0003, home[1], 5.0)  # ~30 m north
    t2 = await flight_bridge.read_telemetry()
    assert abs(t2.lat - home[0]) > 0.0001
    await flight_bridge.return_to_launch()


@pytest.mark.asyncio(loop_scope="module")
async def test_handback_switches_to_manual(flight_bridge):
    await flight_bridge.handback()
    t = await flight_bridge.read_telemetry()
    assert "POSCTL" in t.flight_mode.upper() or "MANUAL" in t.flight_mode.upper() \
        or "HOLD" in t.flight_mode.upper()
