import json, asyncio, pytest
from assistant.safety_client import SafetyClient

class _WS:
    def __init__(self): self.sent=[]
    async def send(self, s): self.sent.append(json.loads(s))
    async def close(self): pass

async def test_send_manual_fire_and_forget():
    c = SafetyClient("ws://x"); c._ws=_WS()
    c._reader = asyncio.create_task(asyncio.sleep(3600))  # appear "connected"
    await c.send_manual(1.0, 2.0, 0.0, 5.0)
    assert c._ws.sent[-1] == {"type": "manual", "forward": 1.0, "right": 2.0, "down": 0.0, "yaw_rate": 5.0}
    assert "id" not in c._ws.sent[-1]
    c._reader.cancel()

def test_last_telemetry_updates_from_push():
    c = SafetyClient("ws://x")
    c._dispatch({"type": "telemetry", "data": {"alt_m": 5.0}})
    assert c.last_telemetry == {"alt_m": 5.0}
