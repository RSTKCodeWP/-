import pytest
from flight_safety.bridge import FlightBridge

class _Offboard:
    def __init__(self): self.started=False; self.stopped=False; self.vel=None
    async def set_velocity_body(self, v): self.vel=v
    async def start(self): self.started=True
    async def stop(self): self.stopped=True

class _Action:
    def __init__(self): self.held=False
    async def hold(self): self.held=True

class _Drone:
    def __init__(self): self.offboard=_Offboard(); self.action=_Action()

@pytest.fixture
def bridge():
    b = FlightBridge("udpin://0.0.0.0:14540")
    b._drone = _Drone()
    return b

async def test_takeover_starts_offboard(bridge):
    await bridge.takeover()
    assert bridge._drone.offboard.started is True
    assert bridge._drone.offboard.vel is not None  # zero setpoint sent first

async def test_set_velocity_body_forwards(bridge):
    await bridge.set_velocity_body(1.0, 2.0, -0.5, 30.0)
    v = bridge._drone.offboard.vel
    assert (v.forward_m_s, v.right_m_s, v.down_m_s, v.yawspeed_deg_s) == (1.0, 2.0, -0.5, 30.0)

async def test_handback_stops_offboard_and_holds(bridge):
    await bridge.handback()
    assert bridge._drone.offboard.stopped is True
    assert bridge._drone.action.held is True
