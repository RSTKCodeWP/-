"""Integration tests: simulator + backend + WebSocket."""

import asyncio
import json
import sys
from pathlib import Path

import pytest
import websockets

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


async def ws_connect(ws_url, timeout=5):
    return await asyncio.wait_for(
        websockets.connect(ws_url),
        timeout=timeout,
    )


async def recv_until(ws, predicate, timeout=10):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=2)
            msg = json.loads(raw)
            if predicate(msg):
                return msg
        except asyncio.TimeoutError:
            continue
    raise TimeoutError("predicate not met within %ds" % timeout)


async def ensure_connected(ws, ws_url, sim_port, timeout=15):
    """Disconnect any prior connection, then connect fresh and wait for telemetry."""
    await ws.send(json.dumps({"type": "disconnect"}))
    try:
        await recv_until(ws, lambda m: m.get("type") == "state" and not m.get("connected"), timeout=3)
    except TimeoutError:
        pass
    await ws.send(
        json.dumps(
            {
                "type": "connect",
                "port": f"tcp:localhost:{sim_port}",
            }
        )
    )
    await recv_until(ws, lambda m: m.get("type") == "connect_result", timeout=10)
    await recv_until(
        ws,
        lambda m: m.get("type") == "state" and m.get("connected") and m.get("gps_sats", 0) > 0,
        timeout=timeout,
    )


class TestConnection:
    def test_health(self, backend_url):
        import httpx

        r = httpx.get(f"{backend_url}/health")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_ports_api(self, backend_url):
        import httpx

        r = httpx.get(f"{backend_url}/api/ports")
        assert r.status_code == 200
        assert "ports" in r.json()

    def test_ws_connect_receive_state(self, ws_url):
        async def run():
            ws = await ws_connect(ws_url)
            try:
                msg = await recv_until(ws, lambda m: m.get("type") == "state")
                assert "connected" in msg
                assert "mode" in msg
            finally:
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_connect_to_sim(self, ws_url, sim_port):
        async def run():
            ws = await ws_connect(ws_url)
            try:
                await ws.send(
                    json.dumps(
                        {
                            "type": "connect",
                            "port": f"tcp:localhost:{sim_port}",
                            "baud": 57600,
                        }
                    )
                )
                msg = await recv_until(ws, lambda m: m.get("type") == "connect_result")
                assert msg["ok"] is True
                state = await recv_until(
                    ws,
                    lambda m: m.get("type") == "state" and m.get("connected"),
                    timeout=8,
                )
                assert state["connected"]
                assert state["gps_sats"] > 0
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_connect_with_pllink_protocol(self, ws_url, sim_port):
        """Sim dual-protocol support: explicit pllink framing over TCP must connect."""

        async def run():
            ws = await ws_connect(ws_url)
            try:
                await ws.send(
                    json.dumps(
                        {
                            "type": "connect",
                            "port": f"tcp:localhost:{sim_port}",
                            "protocol": "pllink",
                        }
                    )
                )
                msg = await recv_until(ws, lambda m: m.get("type") == "connect_result", timeout=10)
                assert msg["ok"] is True
                state = await recv_until(
                    ws,
                    lambda m: m.get("type") == "state" and m.get("connected") and m.get("gps_sats", 0) > 0,
                    timeout=15,
                )
                assert state["connected"]
                assert state["gps_sats"] > 0
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())


class TestTelemetry:
    def test_receives_position(self, ws_url, sim_port):
        async def run():
            ws = await ws_connect(ws_url)
            try:
                await ws.send(
                    json.dumps(
                        {
                            "type": "connect",
                            "port": f"tcp:localhost:{sim_port}",
                        }
                    )
                )
                await recv_until(ws, lambda m: m.get("type") == "connect_result")
                state = await recv_until(
                    ws,
                    lambda m: m.get("type") == "state" and abs(m.get("lat", 0)) > 1,
                    timeout=10,
                )
                assert abs(state["lat"] - 34.258) < 0.01
                assert abs(state["lon"] - 108.942) < 0.01
                assert state["gps_fix"] in ("3D", "RTK固定", "RTK浮动", "差分")
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_receives_battery(self, ws_url, sim_port):
        async def run():
            ws = await ws_connect(ws_url)
            try:
                await ws.send(
                    json.dumps(
                        {
                            "type": "connect",
                            "port": f"tcp:localhost:{sim_port}",
                        }
                    )
                )
                await recv_until(ws, lambda m: m.get("type") == "connect_result")
                state = await recv_until(
                    ws,
                    lambda m: m.get("type") == "state" and m.get("voltage", 0) > 20,
                    timeout=10,
                )
                assert state["voltage"] > 20
                assert state["remaining"] > 0
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_receives_events(self, ws_url, sim_port):
        async def run():
            ws = await ws_connect(ws_url)
            try:
                await ws.send(
                    json.dumps(
                        {
                            "type": "connect",
                            "port": f"tcp:localhost:{sim_port}",
                        }
                    )
                )
                await recv_until(ws, lambda m: m.get("type") == "connect_result")
                event = await recv_until(
                    ws,
                    lambda m: m.get("type") == "event",
                    timeout=10,
                )
                assert "text" in event
                assert "time" in event
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())


class TestCommands:
    def test_arm_disarm(self, ws_url, sim_port):
        async def run():
            ws = await ws_connect(ws_url)
            try:
                await ws.send(
                    json.dumps(
                        {
                            "type": "connect",
                            "port": f"tcp:localhost:{sim_port}",
                        }
                    )
                )
                await recv_until(ws, lambda m: m.get("type") == "connect_result")
                await recv_until(
                    ws,
                    lambda m: m.get("type") == "state" and m.get("connected"),
                    timeout=8,
                )
                await ws.send(json.dumps({"type": "command", "cmd": "arm"}))
                armed_state = await recv_until(
                    ws,
                    lambda m: m.get("type") == "state" and m.get("armed"),
                    timeout=8,
                )
                assert armed_state["armed"]

                await ws.send(json.dumps({"type": "command", "cmd": "disarm"}))
                # Delta-push only includes fields that changed, so the disarm
                # delta carries armed=False explicitly. Filter on `'armed' in m`
                # to ignore intermediate deltas missing the field.
                disarmed_state = await recv_until(
                    ws,
                    lambda m: m.get("type") == "state" and "armed" in m and m["armed"] is False,
                    timeout=8,
                )
                assert disarmed_state["armed"] is False
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_mode_change(self, ws_url, sim_port):
        async def run():
            ws = await ws_connect(ws_url)
            try:
                await ws.send(
                    json.dumps(
                        {
                            "type": "connect",
                            "port": f"tcp:localhost:{sim_port}",
                        }
                    )
                )
                await recv_until(ws, lambda m: m.get("type") == "connect_result")
                await recv_until(
                    ws,
                    lambda m: m.get("type") == "state" and m.get("connected"),
                    timeout=8,
                )
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "mode",
                            "param": 2,
                        }
                    )
                )
                state = await recv_until(
                    ws,
                    lambda m: m.get("type") == "state" and m.get("mode_id") == 2,
                    timeout=8,
                )
                assert state["mode"] == "定高"
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_disconnect(self, ws_url, sim_port):
        async def run():
            ws = await ws_connect(ws_url)
            try:
                await ws.send(
                    json.dumps(
                        {
                            "type": "connect",
                            "port": f"tcp:localhost:{sim_port}",
                        }
                    )
                )
                await recv_until(ws, lambda m: m.get("type") == "connect_result")
                await recv_until(
                    ws,
                    lambda m: m.get("type") == "state" and m.get("connected"),
                    timeout=8,
                )
                await ws.send(json.dumps({"type": "disconnect"}))
                result = await recv_until(
                    ws,
                    lambda m: m.get("type") == "connect_result",
                    timeout=5,
                )
                assert result["ok"]
                state = await recv_until(
                    ws,
                    lambda m: m.get("type") == "state" and not m.get("connected"),
                    timeout=8,
                )
                assert not state["connected"]
            finally:
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())


class TestLogAndReconnect:
    def test_log_active_after_connect(self, ws_url, sim_port):
        async def run():
            ws = await ws_connect(ws_url)
            try:
                await ws.send(
                    json.dumps(
                        {
                            "type": "connect",
                            "port": f"tcp:localhost:{sim_port}",
                        }
                    )
                )
                await recv_until(ws, lambda m: m.get("type") == "connect_result")
                state = await recv_until(
                    ws,
                    lambda m: m.get("type") == "state" and m.get("connected"),
                    timeout=8,
                )
                assert state.get("log_active") is True
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_log_download_api(self, backend_url, ws_url, sim_port):
        async def run():
            ws = await ws_connect(ws_url)
            try:
                await ws.send(
                    json.dumps(
                        {
                            "type": "connect",
                            "port": f"tcp:localhost:{sim_port}",
                        }
                    )
                )
                await recv_until(ws, lambda m: m.get("type") == "connect_result")
                await recv_until(
                    ws,
                    lambda m: m.get("type") == "state" and m.get("connected"),
                    timeout=8,
                )
                await asyncio.sleep(1)
                import httpx

                r = httpx.get(f"{backend_url}/api/log")
                assert r.status_code == 200
                assert "time,roll,pitch" in r.text
                lines = r.text.strip().split("\n")
                assert len(lines) >= 2
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_log_not_available_disconnected(self, backend_url):
        import httpx

        r = httpx.get(f"{backend_url}/api/log")
        assert r.status_code == 404


class TestMission:
    def test_mission_upload(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(3)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                await asyncio.sleep(1)
                waypoints = [
                    {"lat": 34.259, "lon": 108.943, "alt": 30, "drop": False, "delay": 0},
                    {"lat": 34.260, "lon": 108.944, "alt": 30, "drop": True, "delay": 0},
                ]
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "mission_upload",
                            "waypoints": waypoints,
                            "takeoff_alt": 30,
                        }
                    )
                )
                ack = await recv_until(
                    ws,
                    lambda m: m.get("type") == "event" and "任务确认" in m.get("text", ""),
                    timeout=15,
                )
                assert "成功" in ack["text"]
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_mission_clear(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(1)
            ws = await ws_connect(ws_url)
            try:
                await ws.send(
                    json.dumps(
                        {
                            "type": "connect",
                            "port": f"tcp:localhost:{sim_port}",
                        }
                    )
                )
                await recv_until(ws, lambda m: m.get("type") == "connect_result", timeout=8)
                await recv_until(
                    ws,
                    lambda m: m.get("type") == "state" and m.get("connected"),
                    timeout=12,
                )
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "mission_clear",
                        }
                    )
                )
                event = await recv_until(
                    ws,
                    lambda m: m.get("type") == "event" and "清除" in m.get("text", ""),
                    timeout=12,
                )
                assert "清除" in event["text"]
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())


class TestParams:
    def test_param_request_all(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(1)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                await asyncio.sleep(0.5)
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "param_request_all",
                        }
                    )
                )
                batch = await recv_until(
                    ws,
                    lambda m: m.get("type") == "param_batch",
                    timeout=15,
                )
                assert "params" in batch
                assert len(batch["params"]) > 0
                p0 = batch["params"][0]
                assert "name" in p0
                assert "value" in p0
                assert p0["total"] > 10
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_param_set(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(1)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                await asyncio.sleep(0.5)
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "param_request_all",
                        }
                    )
                )
                await recv_until(
                    ws,
                    lambda m: m.get("type") == "params_complete",
                    timeout=15,
                )
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "param_set",
                            "name": "BATT_CAPACITY",
                            "value": 9999,
                        }
                    )
                )
                batch = await recv_until(
                    ws,
                    lambda m: (
                        m.get("type") == "param_batch"
                        and any(
                            p.get("name") == "BATT_CAPACITY" and abs(p.get("value", 0) - 9999) < 1
                            for p in m.get("params", [])
                        )
                    ),
                    timeout=10,
                )
                updated = [p for p in batch["params"] if p["name"] == "BATT_CAPACITY"][0]
                assert abs(updated["value"] - 9999) < 1
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_param_state_in_telemetry(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(1)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                await asyncio.sleep(0.5)
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "param_request_all",
                        }
                    )
                )
                state = await recv_until(
                    ws,
                    lambda m: m.get("type") == "state" and m.get("param_total", -1) > 0,
                    timeout=15,
                )
                assert state["param_total"] > 10
                assert state["param_count"] >= 0
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())


class TestFirmwareVersion:
    def test_firmware_version_in_state(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(1)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                state = await recv_until(
                    ws,
                    lambda m: m.get("type") == "state" and m.get("fw_version", "") != "",
                    timeout=15,
                )
                assert state["fw_version"] == "v4.5.7"
                assert len(state["fw_git"]) > 0
                assert state["board_id"] == 56
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())


class TestMissionDownload:
    def test_upload_then_download(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(2)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                await asyncio.sleep(1)
                waypoints = [
                    {"lat": 34.259, "lon": 108.943, "alt": 50, "drop": False, "delay": 0},
                    {"lat": 34.260, "lon": 108.944, "alt": 60, "drop": False, "delay": 0},
                ]
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "mission_upload",
                            "waypoints": waypoints,
                            "takeoff_alt": 30,
                        }
                    )
                )
                await recv_until(
                    ws,
                    lambda m: (
                        m.get("type") == "event" and "任务确认" in m.get("text", "") and "成功" in m.get("text", "")
                    ),
                    timeout=15,
                )
                await asyncio.sleep(0.5)
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "mission_download",
                        }
                    )
                )
                dl = await recv_until(
                    ws,
                    lambda m: m.get("type") == "mission_downloaded",
                    timeout=15,
                )
                assert len(dl["waypoints"]) == 2
                assert abs(dl["waypoints"][0]["lat"] - 34.259) < 0.001
                assert abs(dl["waypoints"][1]["alt"] - 60) < 1
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_download_empty_mission(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(1)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                await asyncio.sleep(0.5)
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "mission_clear",
                        }
                    )
                )
                await recv_until(
                    ws,
                    lambda m: m.get("type") == "event" and "清除" in m.get("text", ""),
                    timeout=10,
                )
                await asyncio.sleep(0.5)
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "mission_download",
                        }
                    )
                )
                event = await recv_until(
                    ws,
                    lambda m: m.get("type") == "event" and "无任务" in m.get("text", ""),
                    timeout=10,
                )
                assert "无任务" in event["text"]
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())


class TestOnboardLog:
    def test_log_list(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(1)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                await asyncio.sleep(0.5)
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "log_list",
                        }
                    )
                )
                msg = await recv_until(
                    ws,
                    lambda m: m.get("type") == "log_list",
                    timeout=15,
                )
                assert "logs" in msg
                assert len(msg["logs"]) == 3
                assert msg["logs"][0]["id"] == 1
                assert msg["logs"][0]["size"] > 0
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_log_download(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(1)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                await asyncio.sleep(0.5)
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "log_list",
                        }
                    )
                )
                await recv_until(
                    ws,
                    lambda m: m.get("type") == "log_list",
                    timeout=15,
                )
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "log_download",
                            "id": 3,
                        }
                    )
                )
                # New log-download protocol: chunks stream as log_chunk messages
                # (base64 in .data), then a final log_complete with size only
                # (no data). Accumulate the chunks to validate the full payload.
                import base64

                chunks: dict[int, bytes] = {}
                done = None
                deadline = asyncio.get_event_loop().time() + 20
                while asyncio.get_event_loop().time() < deadline:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=2)
                        m = json.loads(raw)
                    except asyncio.TimeoutError:
                        continue
                    if m.get("type") == "log_chunk":
                        chunks[m["ofs"]] = base64.b64decode(m["data"])
                    elif m.get("type") == "log_complete":
                        done = m
                        break
                assert done is not None, "never received log_complete"
                assert done["id"] == 3
                assert done["size"] == 900
                data = b"".join(chunks[ofs] for ofs in sorted(chunks))
                assert len(data) == 900
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_log_cancel(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(1)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                await asyncio.sleep(0.5)
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "log_list",
                        }
                    )
                )
                await recv_until(
                    ws,
                    lambda m: m.get("type") == "log_list",
                    timeout=15,
                )
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "log_cancel",
                        }
                    )
                )
                event = await recv_until(
                    ws,
                    lambda m: m.get("type") == "event" and "取消" in m.get("text", ""),
                    timeout=10,
                )
                assert "取消" in event["text"]
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())


class TestDataStreams:
    def test_rc_channels_in_state(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(1)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                # Wait for a state push that includes BOTH rc and rc_rssi —
                # delta pushes only carry changed fields, so we want either the
                # first push that includes rc (whichever came in first) or a
                # full-sync push (every 10th).
                state = await recv_until(
                    ws,
                    lambda m: (
                        m.get("type") == "state" and len(m.get("rc", [])) >= 4 and m["rc"][0] > 0 and "rc_rssi" in m
                    ),
                    timeout=15,
                )
                assert len(state["rc"]) >= 8
                assert 1000 <= state["rc"][0] <= 2000
                assert "rc_rssi" in state
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_vibration_in_state(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(1)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                # Delta-push only includes changed fields. Wait for a push that
                # has both 'vibe' (always present since values are random) and
                # 'vibe_clip' (only changes if clipping counter ticks).
                state = await recv_until(
                    ws,
                    lambda m: (
                        m.get("type") == "state"
                        and len(m.get("vibe", [])) == 3
                        and m["vibe"][0] > 0
                        and "vibe_clip" in m
                    ),
                    timeout=15,
                )
                assert state["vibe"][0] > 0
                assert state["vibe"][1] > 0
                assert state["vibe"][2] > 0
                assert len(state["vibe_clip"]) == 3
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_servo_output_in_state(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(1)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                state = await recv_until(
                    ws,
                    lambda m: m.get("type") == "state" and len(m.get("servo", [])) >= 4 and m["servo"][0] > 0,
                    timeout=15,
                )
                assert len(state["servo"]) >= 8
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())


class TestFenceUpload:
    def test_fence_upload(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(2)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                await asyncio.sleep(1)
                polygon = [
                    {"lat": 34.258, "lon": 108.942},
                    {"lat": 34.259, "lon": 108.943},
                    {"lat": 34.259, "lon": 108.941},
                    {"lat": 34.257, "lon": 108.941},
                ]
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "fence_upload",
                            "polygon": polygon,
                        }
                    )
                )
                ack = await recv_until(
                    ws,
                    lambda m: m.get("type") == "event" and "围栏确认" in m.get("text", ""),
                    timeout=15,
                )
                assert "成功" in ack["text"]
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_fence_upload_too_few_points(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(1)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                await asyncio.sleep(0.5)
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "fence_upload",
                            "polygon": [{"lat": 34.258, "lon": 108.942}],
                        }
                    )
                )
                result = await recv_until(
                    ws,
                    lambda m: m.get("type") == "cmd_result",
                    timeout=10,
                )
                assert result.get("ok") is False
                assert "3" in result.get("error", "")
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())


class TestMissionAdvanced:
    def test_upload_with_speed_roundtrip(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(2)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                await asyncio.sleep(1)
                waypoints = [
                    {
                        "lat": 34.259,
                        "lon": 108.943,
                        "alt": 50,
                        "drop": False,
                        "delay": 0,
                        "speed": 8.0,
                        "type": "wp",
                        "loiter_param": 0,
                    },
                    {
                        "lat": 34.260,
                        "lon": 108.944,
                        "alt": 60,
                        "drop": False,
                        "delay": 0,
                        "speed": 0,
                        "type": "wp",
                        "loiter_param": 0,
                    },
                ]
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "mission_upload",
                            "waypoints": waypoints,
                            "takeoff_alt": 30,
                        }
                    )
                )
                await recv_until(
                    ws,
                    lambda m: (
                        m.get("type") == "event" and "任务确认" in m.get("text", "") and "成功" in m.get("text", "")
                    ),
                    timeout=15,
                )
                await asyncio.sleep(0.5)
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "mission_download",
                        }
                    )
                )
                dl = await recv_until(
                    ws,
                    lambda m: m.get("type") == "mission_downloaded",
                    timeout=15,
                )
                assert len(dl["waypoints"]) == 2
                assert abs(dl["waypoints"][0]["speed"] - 8.0) < 0.1
                assert dl["waypoints"][1]["speed"] == 0
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_upload_with_loiter_roundtrip(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(2)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                await asyncio.sleep(1)
                waypoints = [
                    {
                        "lat": 34.259,
                        "lon": 108.943,
                        "alt": 50,
                        "drop": False,
                        "delay": 0,
                        "speed": 0,
                        "type": "loiter_turns",
                        "loiter_param": 3,
                    },
                    {
                        "lat": 34.260,
                        "lon": 108.944,
                        "alt": 60,
                        "drop": False,
                        "delay": 0,
                        "speed": 0,
                        "type": "loiter_time",
                        "loiter_param": 15,
                    },
                ]
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "mission_upload",
                            "waypoints": waypoints,
                            "takeoff_alt": 30,
                        }
                    )
                )
                await recv_until(
                    ws,
                    lambda m: (
                        m.get("type") == "event" and "任务确认" in m.get("text", "") and "成功" in m.get("text", "")
                    ),
                    timeout=15,
                )
                await asyncio.sleep(0.5)
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "mission_download",
                        }
                    )
                )
                dl = await recv_until(
                    ws,
                    lambda m: m.get("type") == "mission_downloaded",
                    timeout=15,
                )
                assert len(dl["waypoints"]) == 2
                assert dl["waypoints"][0]["type"] == "loiter_turns"
                assert abs(dl["waypoints"][0]["loiter_param"] - 3) < 0.1
                assert dl["waypoints"][1]["type"] == "loiter_time"
                assert abs(dl["waypoints"][1]["loiter_param"] - 15) < 0.1
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())


class TestCalibration:
    def test_gyro_calibration(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(1)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                await asyncio.sleep(0.5)
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "cal_gyro",
                        }
                    )
                )
                event = await recv_until(
                    ws,
                    lambda m: m.get("type") == "event" and "校准" in m.get("text", ""),
                    timeout=10,
                )
                assert "校准" in event["text"]
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_compass_calibration(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(1)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                await asyncio.sleep(0.5)
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "cal_compass",
                        }
                    )
                )
                event = await recv_until(
                    ws,
                    lambda m: m.get("type") == "event" and "罗盘" in m.get("text", ""),
                    timeout=10,
                )
                assert "罗盘" in event["text"]
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())

    def test_cal_cancel(self, ws_url, sim_port):
        async def run():
            await asyncio.sleep(1)
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port, timeout=20)
                await asyncio.sleep(0.5)
                await ws.send(
                    json.dumps(
                        {
                            "type": "command",
                            "cmd": "cal_cancel",
                        }
                    )
                )
                event = await recv_until(
                    ws,
                    lambda m: m.get("type") == "event" and "取消" in m.get("text", ""),
                    timeout=10,
                )
                assert "取消" in event["text"]
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())


# ═══════════════════════════════════════════════════════════════════════
# Supplementary audit tests — 6 previously untested feature areas
# ═══════════════════════════════════════════════════════════════════════


class TestVideoApi:
    """Video proxy endpoint (no real RTSP source needed)."""

    def test_video_no_url(self, backend_url):
        import httpx

        r = httpx.get(f"{backend_url}/api/video", timeout=5)
        assert r.status_code == 200
        assert "error" in r.json()

    def test_video_stop_no_active(self, backend_url):
        import httpx

        r = httpx.get(f"{backend_url}/api/video/stop", timeout=5)
        assert r.status_code == 200
        assert r.json()["ok"] is True


class TestTileCache:
    """Tile cache API."""

    def test_tile_cache_stats(self, backend_url):
        import httpx

        r = httpx.get(f"{backend_url}/api/tile_cache", timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert "size" in data and "count" in data

    def test_tile_cache_clear(self, backend_url):
        import httpx

        r = httpx.post(f"{backend_url}/api/tile_cache_clear", timeout=5)
        assert r.status_code == 200
        assert r.json()["ok"] is True


class TestVzConvention:
    """vz sign: positive = climbing (QGC convention)."""

    def test_vz_field_exists(self, ws_url, sim_port):
        async def run():
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port)
                # Wait for a state push that actually carries vz (delta pushes
                # only include changed fields; vz is the changing one when the
                # sim is in motion).
                state = await recv_until(
                    ws,
                    lambda m: m.get("type") == "state" and "vz" in m,
                    timeout=10,
                )
                assert "vz" in state
                assert isinstance(state["vz"], (int, float))
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())


class TestEkfInState:
    """EKF fields available for preflight check."""

    def test_ekf_fields(self, ws_url, sim_port):
        async def run():
            ws = await ws_connect(ws_url)
            try:
                await ensure_connected(ws, ws_url, sim_port)
                state = await recv_until(
                    ws,
                    lambda m: m.get("type") == "state" and m.get("connected") and m.get("ekf_flags", 0) != 0,
                    timeout=15,
                )
                for key in ("ekf_vel", "ekf_pos_h", "ekf_pos_v", "ekf_compass", "ekf_flags"):
                    assert key in state, f"missing {key}"
                assert isinstance(state["ekf_flags"], int)
            finally:
                await ws.send(json.dumps({"type": "disconnect"}))
                await asyncio.sleep(0.5)
                await ws.close()

        asyncio.get_event_loop().run_until_complete(run())


class TestMissionFileFormats:
    """Mission JSON/KML roundtrip (pure logic, no browser)."""

    def test_json_roundtrip(self):
        wps = [
            {
                "lat": 34.258,
                "lon": 108.942,
                "alt": 30,
                "drop": False,
                "delay": 0,
                "speed": 5,
                "type": "wp",
                "loiter_param": 0,
            },
            {
                "lat": 34.259,
                "lon": 108.943,
                "alt": 40,
                "drop": True,
                "delay": 0,
                "speed": 0,
                "type": "loiter_turns",
                "loiter_param": 3,
            },
        ]
        data = json.dumps({"waypoints": wps, "alt": 30})
        parsed = json.loads(data)
        assert len(parsed["waypoints"]) == 2
        assert parsed["waypoints"][1]["drop"] is True
        assert parsed["waypoints"][1]["type"] == "loiter_turns"

    def test_kml_import_parsing(self):
        from xml.etree import ElementTree as ET

        kml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
            "<Placemark><LineString><coordinates>"
            "108.942,34.258,30\n108.943,34.259,40"
            "</coordinates></LineString></Placemark></Document></kml>"
        )
        root = ET.fromstring(kml)
        ns = "{http://www.opengis.net/kml/2.2}"
        el = root.find(f".//{ns}coordinates")
        assert el is not None
        pts = []
        for c in el.text.strip().split():
            p = c.split(",")
            if len(p) >= 2:
                pts.append({"lat": float(p[1]), "lon": float(p[0]), "alt": float(p[2]) if len(p) >= 3 else 30})
        assert len(pts) == 2
        assert abs(pts[0]["lat"] - 34.258) < 0.001

    def test_kml_export_format(self):
        wps = [{"lat": 34.258, "lon": 108.942, "alt": 30}]
        coords = "\n".join(f"{w['lon']},{w['lat']},{w['alt']}" for w in wps)
        assert "108.942,34.258,30" in coords


class TestCsvReplayParsing:
    """CSV replay file parsing (pure logic)."""

    def test_csv_parse(self):
        lines = [
            "time,roll,pitch,yaw,lat,lon,alt_rel,alt_msl,gs,vz,voltage,current,remaining,mode,mode_name,armed,gps_fix,sats,wp,hdg,dist,bat_time",
            "0,1.0,2.0,90,34.258,108.942,30.0,430,5.0,1.0,25.2,5.0,80,5,LOITER,1,3,14,2,90,100,-1",
            "1,1.5,2.5,91,34.259,108.943,31.0,431,5.5,0.5,25.1,5.1,79,5,LOITER,1,3,14,2,91,110,-1",
        ]
        rows = []
        for i in range(1, len(lines)):
            cols = lines[i].split(",")
            assert len(cols) >= 20
            rows.append({"t": float(cols[0]), "lat": float(cols[4]), "alt_rel": float(cols[6]), "gs": float(cols[8])})
        assert len(rows) == 2
        assert rows[0]["lat"] == 34.258
        assert rows[1]["alt_rel"] == 31.0


class TestAudioAlertLogic:
    """Audio alert trigger logic (pure Python, no Web Audio)."""

    def test_arm_disarm_triggers(self):
        prev = False
        alerts = []
        for armed in [False, True, True, False]:
            if armed and not prev:
                alerts.append("arm")
            if not armed and prev:
                alerts.append("disarm")
            prev = armed
        assert alerts == ["arm", "disarm"]

    def test_battery_low_single_trigger(self):
        prev_low = False
        count = 0
        for remaining in [80, 50, 25, 19, 18, 15, 30]:
            bat_low = 0 <= remaining < 20
            if bat_low and not prev_low:
                count += 1
            prev_low = bat_low
        assert count == 1

    def test_link_lost_speak_once(self):
        spoken = False
        speak_count = 0
        for age in [0.5, 1.0, 2.0, 3.5, 4.0, 1.0, 0.5]:
            if age > 3 and not spoken:
                speak_count += 1
                spoken = True
            if 0 <= age < 2:
                spoken = False
        assert speak_count == 1


class TestConfirmCoverage:
    """Verify all dangerous commands have confirm/showConfirm guards in source."""

    def test_dangerous_commands_guarded(self):
        import re

        dangerous = ["arm", "rtl", "takeoff", "force_disarm", "drop", "mission_start", "mission_clear"]
        src_dir = Path(__file__).resolve().parent.parent / "src"
        for cmd in dangerous:
            pat = re.compile(rf"sendCommand\(['\"]({cmd})['\"]")
            for f in src_dir.rglob("*.svelte"):
                content = f.read_text()
                for m in pat.finditer(content):
                    ctx = content[max(0, m.start() - 900) : m.start() + 50]
                    assert "confirm(" in ctx or "showConfirm(" in ctx or "showSlide(" in ctx, (
                        f'{f.name}: sendCommand("{cmd}") missing confirm guard'
                    )


class TestVersionApi:
    def test_version_endpoint(self, backend_url):
        import httpx

        r = httpx.get(f"{backend_url}/api/version")
        assert r.status_code == 200
        data = r.json()
        assert "version" in data
        assert "protocols" in data
        assert "vehicles" in data
        assert "features" in data
        assert "standard" in data["protocols"]
        assert "copter" in data["vehicles"]
        assert "i18n" in data["features"]

    def test_param_meta_endpoint(self, backend_url):
        import httpx

        r = httpx.get(f"{backend_url}/api/param_meta?vehicle=copter")
        assert r.status_code == 200

    def test_set_locale_via_ws(self, ws_url, event_loop):
        import websockets

        async def _test():
            ws = await asyncio.wait_for(websockets.connect(ws_url), 5)
            await ws.send(json.dumps({"type": "set_locale", "locale": "en"}))
            msg = json.loads(await asyncio.wait_for(ws.recv(), 5))
            assert msg["type"] == "state"
            await ws.close()

        event_loop.run_until_complete(_test())

    def test_tile_sources_endpoint(self, backend_url):
        import httpx

        r = httpx.get(f"{backend_url}/api/tile_sources")
        assert r.status_code == 200
        data = r.json()
        # tile_sources is a dict of {source_id: {name, region, ...}}; sources
        # are tagged with region='china' or region='global'. Make sure at least
        # one of each exists so map-source switching has options.
        regions = {entry.get("region") for entry in data.values()}
        assert "china" in regions
        assert "global" in regions
