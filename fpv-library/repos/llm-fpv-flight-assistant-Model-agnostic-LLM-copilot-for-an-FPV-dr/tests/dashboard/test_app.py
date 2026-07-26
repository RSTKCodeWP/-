import asyncio
import pytest
from fastapi.testclient import TestClient
from dashboard.app import Broadcaster, attach_telemetry, build_app


class FakeClient:
    def __init__(self): self.cb = None; self.sent = []
    async def get_telemetry(self): return {"battery_pct": 0.9}
    async def send_command(self, cmd): self.sent.append(cmd); return {"status": "executed", "verb": cmd["verb"]}
    async def abort(self): return {"status": "aborted"}
    def subscribe_telemetry(self, cb): self.cb = cb


@pytest.mark.asyncio
async def test_broadcaster_sends_to_all_registered():
    b = Broadcaster()
    got = []
    async def send(m): got.append(m)
    b.register(send)
    await b.broadcast({"type": "telemetry", "data": {"battery_pct": 0.5}})
    assert got == [{"type": "telemetry", "data": {"battery_pct": 0.5}}]


@pytest.mark.asyncio
async def test_attach_telemetry_forwards_pushes_to_broadcaster():
    client = FakeClient()
    b = Broadcaster()
    got = []
    async def send(m): got.append(m)
    b.register(send)
    attach_telemetry(client, b)
    client.cb({"battery_pct": 0.42})        # simulate a push from the safety link
    await asyncio.sleep(0)                   # let the scheduled broadcast run
    assert got and got[-1] == {"type": "telemetry", "data": {"battery_pct": 0.42}}


def test_browser_hub_error_yields_narration_not_disconnect():
    class BoomHub:
        control = "assistant"
        async def handle_chat(self, text, emit):
            raise RuntimeError("safety link closed")
    app = build_app(BoomHub(), video_stream_url="http://x/stream.mjpg")
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "text": "hold"})
        found = False
        for _ in range(6):  # skip initial video_status/control_state; expect an error narration
            f = ws.receive_json()
            if f.get("type") == "narration" and "Error handling request" in f.get("text", ""):
                found = True
                break
        assert found
