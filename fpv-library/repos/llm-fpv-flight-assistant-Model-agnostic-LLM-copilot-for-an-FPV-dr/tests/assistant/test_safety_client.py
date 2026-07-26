import asyncio, json, pytest, websockets
from assistant.safety_client import SafetyClient


async def _fake_server(websocket):
    # proactively push one telemetry frame (no id) to exercise demux
    await websocket.send(json.dumps({"type": "telemetry", "data": {"battery_pct": 0.5}}))
    async for raw in websocket:
        msg = json.loads(raw)
        rid = msg.get("id")
        if msg["type"] == "get_telemetry":
            await websocket.send(json.dumps({"type": "telemetry", "data": {"battery_pct": 0.8}, "id": rid}))
        elif msg["type"] == "command":
            await websocket.send(json.dumps({"status": "executed", "verb": msg["command"]["verb"], "id": rid}))
        elif msg["type"] == "abort":
            await websocket.send(json.dumps({"status": "aborted", "id": rid}))


@pytest.mark.asyncio
async def test_client_roundtrips_with_id():
    async with websockets.serve(_fake_server, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = SafetyClient(f"ws://127.0.0.1:{port}")
        await client.connect()
        assert (await client.get_telemetry())["battery_pct"] == 0.8
        res = await client.send_command({"verb": "loiter"})
        assert res["status"] == "executed" and res["verb"] == "loiter"
        assert (await client.abort())["status"] == "aborted"
        await client.close()


@pytest.mark.asyncio
async def test_push_telemetry_reaches_subscriber():
    async with websockets.serve(_fake_server, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = SafetyClient(f"ws://127.0.0.1:{port}")
        got = []
        client.subscribe_telemetry(lambda d: got.append(d))
        await client.connect()
        # the pushed frame (no id) must NOT resolve a request; it goes to the subscriber
        await client.send_command({"verb": "loiter"})
        await asyncio.sleep(0.05)
        assert got and got[0]["battery_pct"] == 0.5
        await client.close()


@pytest.mark.asyncio
async def test_raising_subscriber_does_not_kill_reader():
    async with websockets.serve(_fake_server, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = SafetyClient(f"ws://127.0.0.1:{port}")
        client.subscribe_telemetry(lambda _: (_ for _ in ()).throw(ValueError("bad")))
        await client.connect()
        # the pushed id-less frame triggers the raising callback; the reader must
        # survive so this request still resolves
        res = await client.send_command({"verb": "loiter"})
        assert res["status"] == "executed"
        await client.close()
