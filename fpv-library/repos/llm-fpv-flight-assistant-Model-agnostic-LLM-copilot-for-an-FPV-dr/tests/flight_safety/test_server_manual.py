from fastapi.testclient import TestClient
from flight_safety.server import build_app

class _Disp:
    def __init__(self): self.manual=[]
    async def telemetry(self): return {"alt_m": 1.0}
    def manual_setpoint(self, f, r, d, yr): self.manual.append((f, r, d, yr))
    async def handle(self, cmd): return {"status": "executed", "verb": cmd.get("verb")}
    async def abort(self): pass

def test_manual_message_routes_to_dispatcher_no_reply():
    disp = _Disp()
    app = build_app(disp, telemetry_interval_s=999)  # suppress push noise
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "manual", "forward": 1.0, "right": 2.0, "down": 0.0, "yaw_rate": 5.0})
        ws.send_json({"type": "get_telemetry", "id": "x"})  # round-trip to flush
        reply = ws.receive_json()
        assert reply.get("id") == "x"
    assert disp.manual == [(1.0, 2.0, 0.0, 5.0)]
