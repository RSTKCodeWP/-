from fastapi.testclient import TestClient
from dashboard.app import build_app, Broadcaster
from dashboard.hub import DashboardHub
from assistant.command_gen import CommandProposal


class _Agent:
    async def propose_stream(self, nl, on_delta):
        await on_delta("reply", "ok")
        return CommandProposal({"verb": "loiter"}, say="ok")
    async def execute(self, c): return {"status": "executed", "verb": c["verb"]}
    async def abort(self): return {"status": "aborted"}


class _Client:
    sent = []
    async def takeover(self): return {"status": "executed", "verb": "takeover"}
    async def handback(self): return {"status": "executed", "verb": "handback"}
    async def send_manual(self, f, r, d, yr): _Client.sent.append((f, r, d, yr))


def test_chat_streams_over_ws():
    hub = DashboardHub(_Agent(), _Client())
    app = build_app(hub, "http://v/stream.mjpg", broadcaster=Broadcaster(), client=_Client())
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "chat", "text": "hold"})
        types = set()
        for _ in range(12):
            types.add(ws.receive_json()["type"])
            if "proposal" in types:
                break
        assert {"chat_start", "chat_delta", "chat_end", "proposal"} <= types


def test_manual_routes_to_client():
    _Client.sent.clear()
    hub = DashboardHub(_Agent(), _Client())
    app = build_app(hub, "http://v/stream.mjpg", broadcaster=Broadcaster(), client=_Client())
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_json({"type": "manual", "forward": 1.0, "right": 0.0, "down": 0.0, "yaw_rate": 0.0})
        ws.send_json({"type": "cancel"})  # flush
        for _ in range(8):
            if ws.receive_json()["type"] == "narration":
                break
    assert _Client.sent and _Client.sent[-1] == (1.0, 0.0, 0.0, 0.0)
