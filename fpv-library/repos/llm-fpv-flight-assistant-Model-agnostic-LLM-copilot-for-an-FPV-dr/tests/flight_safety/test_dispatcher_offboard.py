import asyncio, pytest
from flight_safety.config import Limits
from flight_safety.dispatcher import Dispatcher
from flight_safety.models import Telemetry

class _Bridge:
    def __init__(self): self.took=False; self.gave=False; self.vels=[]
    async def takeover(self): self.took=True
    async def handback(self): self.gave=True
    async def set_velocity_body(self, f, r, d, yr): self.vels.append((f, r, d, yr))
    async def read_telemetry(self):
        return Telemetry(lat=47.3978, lon=8.5456, alt_m=10.0, speed_ms=0.0,
                         battery_pct=1.0, flight_mode="OFFBOARD", armed=True,
                         gps_ok=True, ekf_ok=True, yaw=0.0)

async def test_takeover_sets_offboard_and_streams_zero():
    b = _Bridge()
    d = Dispatcher(b, Limits(), [])
    d._stream_hz = 100  # fast loop for the test
    await d.takeover()
    assert b.took is True and d._offboard is True
    await asyncio.sleep(0.05)   # let the loop tick
    assert b.vels and b.vels[-1] == (0.0, 0.0, 0.0, 0.0)
    await d.handback()
    assert b.gave is True and d._offboard is False

async def test_handback_stops_stream():
    b = _Bridge(); d = Dispatcher(b, Limits(), []); d._stream_hz = 100
    await d.takeover(); await d.handback()
    n = len(b.vels); await asyncio.sleep(0.05)
    assert len(b.vels) == n  # no more setpoints after handback

async def test_takeover_refused_when_not_airborne():
    class _Grounded(_Bridge):
        async def read_telemetry(self):
            from flight_safety.models import Telemetry
            return Telemetry(lat=47.0, lon=8.0, alt_m=0.0, speed_ms=0.0, battery_pct=1.0,
                             flight_mode="HOLD", armed=False, gps_ok=True, ekf_ok=True, yaw=0.0)
    b = _Grounded(); d = Dispatcher(b, Limits(), [])
    with pytest.raises(Exception):
        await d.takeover()
    assert d._offboard is False
    assert b.took is False   # bridge.takeover() never called
