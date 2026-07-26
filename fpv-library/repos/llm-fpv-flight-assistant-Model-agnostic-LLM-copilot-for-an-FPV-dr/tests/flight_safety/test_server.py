import asyncio
import time

from fastapi.testclient import TestClient
from flight_safety.server import build_app


class FakeDispatcher:
    def __init__(self): self.aborted = False
    async def handle(self, raw): return {"status": "executed", "verb": raw.get("verb")}
    async def abort(self): self.aborted = True


def test_command_endpoint_returns_status():
    disp = FakeDispatcher()
    app = build_app(disp)
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "command", "command": {"verb": "loiter"}})
        msg = ws.receive_json()
        assert msg["status"] == "executed"


def test_abort_endpoint_triggers_abort():
    disp = FakeDispatcher()
    app = build_app(disp)
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "abort"})
        msg = ws.receive_json()
        assert msg["status"] == "aborted"
    assert disp.aborted is True


def test_abort_preempts_inflight_command():
    class SlowDispatcher:
        def __init__(self):
            self.aborted = False
        async def handle(self, raw):
            await asyncio.sleep(5)  # simulate a long telemetry-gated command
            return {"status": "executed", "verb": raw.get("verb")}
        async def abort(self):
            self.aborted = True

    disp = SlowDispatcher()
    client = TestClient(build_app(disp))
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "command", "command": {"verb": "goto"}})
        ws.send_json({"type": "abort"})
        t0 = time.time()
        msg = ws.receive_json()
        elapsed = time.time() - t0
        assert msg["status"] == "aborted"
        assert elapsed < 3.0, f"abort was not prompt: {elapsed:.1f}s"
    assert disp.aborted is True


def test_get_telemetry_returns_snapshot():
    class TelemetryDispatcher:
        async def handle(self, raw): return {"status": "executed"}
        async def abort(self): ...
        async def telemetry(self):
            return {"lat": 47.0, "lon": 8.0, "alt_m": 0.0, "battery_pct": 0.9,
                    "flight_mode": "HOLD", "armed": False, "gps_ok": True, "ekf_ok": True,
                    "speed_ms": 0.0}
    client = TestClient(build_app(TelemetryDispatcher()))
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "get_telemetry"})
        msg = ws.receive_json()
        assert msg["type"] == "telemetry"
        assert msg["data"]["battery_pct"] == 0.9


def test_command_reply_echoes_id():
    disp = FakeDispatcher()
    client = TestClient(build_app(disp, telemetry_interval_s=999))  # suppress push noise
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "command", "id": 42, "command": {"verb": "loiter"}})
        msg = ws.receive_json()
        assert msg["status"] == "executed"
        assert msg["id"] == 42


def test_server_pushes_telemetry_frames():
    class TelDisp:
        async def handle(self, raw): return {"status": "executed"}
        async def abort(self): ...
        async def telemetry(self):
            return {"battery_pct": 0.77, "alt_m": 12.0, "flight_mode": "HOLD"}
    client = TestClient(build_app(TelDisp(), telemetry_interval_s=0.05))
    with client.websocket_connect("/ws") as ws:
        msg = ws.receive_json()  # arrives unsolicited from the push loop
        assert msg["type"] == "telemetry"
        assert msg["data"]["battery_pct"] == 0.77
