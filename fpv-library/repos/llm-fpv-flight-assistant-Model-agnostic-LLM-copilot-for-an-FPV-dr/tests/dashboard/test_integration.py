import asyncio
import json
import os
import pytest
import websockets

pytestmark = pytest.mark.integration  # requires SITL + flight-safety + dashboard running

# Default port is 8080; override with DASH_E2E_WS when the dashboard runs elsewhere
# (e.g. this box's 8080/8082 are taken by other services -> run dashboard on 8090).
DASH_WS = os.environ.get("DASH_E2E_WS", "ws://127.0.0.1:8080/ws")


@pytest.mark.asyncio
async def test_dashboard_chat_to_execute():
    """With SITL, flight-safety (:8765) and dashboard up: chat -> proposal -> confirm.

    Run beforehand (separate terminals):
      python -m flight_safety
      DASH_PORT=8090 python -m dashboard   # then DASH_E2E_WS=ws://127.0.0.1:8090/ws
    """
    async with websockets.connect(DASH_WS) as ws:
        saw_telemetry = False
        await ws.send(json.dumps({"type": "chat", "text": "loiter"}))
        proposal = None
        for _ in range(50):
            frame = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if frame.get("type") == "telemetry":
                saw_telemetry = True
            if frame.get("type") == "proposal":
                proposal = frame
                break
        assert proposal is not None and proposal["command"]["verb"] == "loiter"
        assert saw_telemetry, "expected live telemetry push frames"
        await ws.send(json.dumps({"type": "confirm"}))
        result = None
        for _ in range(50):
            frame = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if frame.get("type") == "result":
                result = frame
                break
        assert result is not None and result["status"] in ("executed", "rejected")


@pytest.mark.asyncio
async def test_chat_streams_and_proposes():
    """Streaming chat: chat_start -> chat_delta -> chat_end -> proposal."""
    async with websockets.connect(DASH_WS) as ws:
        await ws.send(json.dumps({"type": "chat", "text": "loiter here"}))
        kinds = []
        proposal = None
        for _ in range(80):
            f = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            kinds.append(f.get("type"))
            if f.get("type") == "proposal":
                proposal = f
                break
        assert "chat_start" in kinds and "chat_delta" in kinds and "chat_end" in kinds
        assert proposal is not None and proposal["command"]["verb"] == "loiter"


@pytest.mark.asyncio
async def test_take_control_and_manual_setpoints():
    """Quick takeoff -> take control (OFFBOARD) -> stream setpoints -> release."""
    async with websockets.connect(DASH_WS) as ws:
        # take off first via quick + confirm
        await ws.send(json.dumps({"type": "quick", "verb": "arm_takeoff", "args": {"alt": 8}}))
        for _ in range(40):
            f = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if f.get("type") == "proposal":
                await ws.send(json.dumps({"type": "confirm"}))
                break
        # wait for the takeoff result
        for _ in range(80):
            f = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if f.get("type") == "result":
                break
        # take control, expect control_state -> manual
        await ws.send(json.dumps({"type": "take_control"}))
        saw_manual = False
        for _ in range(40):
            f = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if f.get("type") == "control_state" and f.get("who") == "manual":
                saw_manual = True
                break
        assert saw_manual, "expected control_state manual after take_control"
        # stream a few forward setpoints, then release
        for _ in range(20):
            await ws.send(json.dumps({"type": "manual", "forward": 2.0,
                                      "right": 0.0, "down": 0.0, "yaw_rate": 0.0}))
            await asyncio.sleep(0.05)
        await ws.send(json.dumps({"type": "release_control"}))
