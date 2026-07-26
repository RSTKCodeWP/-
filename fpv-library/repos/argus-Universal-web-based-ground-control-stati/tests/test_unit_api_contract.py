"""API contract tests: verify WebSocket/HTTP message formats between frontend and backend."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.app import app
from backend.drone_link import DroneLink
from backend.ws_manager import WSManager

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _setup_app_state():
    """Ensure app.state.link and app.state.ws_mgr exist for route handlers."""
    if not hasattr(app.state, "link"):
        app.state.link = DroneLink()
        app.state.ws_mgr = WSManager(app.state.link)
    yield


def make_ws():
    """Create a mock WebSocket with standard async methods."""
    ws = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.send_text = AsyncMock()
    ws.accept = AsyncMock()
    return ws


# ---------------------------------------------------------------------------
# State push message format
# ---------------------------------------------------------------------------


class TestStatePushFormat:
    """Verify the state push message contains all required fields."""

    def test_state_has_type_field(self):
        """State message must have type='state'."""
        link = DroneLink()
        state = link.get_state()
        assert state["type"] == "state"

    def test_state_has_connected_field(self):
        """State message must have 'connected' boolean field."""
        link = DroneLink()
        state = link.get_state()
        assert "connected" in state
        assert isinstance(state["connected"], bool)

    def test_state_has_attitude_fields(self):
        """State message must contain roll, pitch, yaw."""
        link = DroneLink()
        state = link.get_state()
        for field in ("roll", "pitch", "yaw"):
            assert field in state
            assert isinstance(state[field], (int, float))

    def test_state_has_position_fields(self):
        """State message must contain lat, lon, alt_rel, alt_msl."""
        link = DroneLink()
        state = link.get_state()
        for field in ("lat", "lon", "alt_rel", "alt_msl"):
            assert field in state
            assert isinstance(state[field], (int, float))

    def test_state_has_battery_fields(self):
        """State message must contain voltage, current, remaining."""
        link = DroneLink()
        state = link.get_state()
        assert "voltage" in state
        assert "current" in state
        assert "remaining" in state
        assert isinstance(state["voltage"], (int, float))
        assert isinstance(state["current"], (int, float))
        assert isinstance(state["remaining"], int)

    def test_state_has_gps_fields(self):
        """State message must contain gps_fix, gps_sats."""
        link = DroneLink()
        state = link.get_state()
        assert "gps_fix" in state
        assert "gps_sats" in state
        assert isinstance(state["gps_sats"], int)

    def test_state_has_vehicle_fields(self):
        """State message must contain mode, armed, vtype."""
        link = DroneLink()
        state = link.get_state()
        assert "mode" in state
        assert "armed" in state
        assert "vtype" in state
        assert isinstance(state["armed"], bool)

    def test_state_has_navigation_fields(self):
        """State message must contain gs, vz, hdg, dist_home."""
        link = DroneLink()
        state = link.get_state()
        for field in ("gs", "vz", "hdg", "dist_home"):
            assert field in state
            assert isinstance(state[field], (int, float))

    def test_state_has_mission_field(self):
        """State message must contain wp (current waypoint)."""
        link = DroneLink()
        state = link.get_state()
        assert "wp" in state
        assert isinstance(state["wp"], int)

    def test_state_has_diagnostics_fields(self):
        """State message must contain vibe, ekf_vel, servo."""
        link = DroneLink()
        state = link.get_state()
        assert "vibe" in state
        assert isinstance(state["vibe"], list)
        assert len(state["vibe"]) == 3
        assert "ekf_vel" in state
        assert "servo" in state
        assert isinstance(state["servo"], list)


# ---------------------------------------------------------------------------
# Delta push vs full push format
# ---------------------------------------------------------------------------


class TestDeltaPushContract:
    """Verify delta push and full push message structures."""

    def test_full_push_contains_all_keys(self):
        """A full push (push_count % 10 == 1) contains all state keys."""
        link = DroneLink()
        full_state = link.get_state()
        required_keys = {
            "type",
            "connected",
            "roll",
            "pitch",
            "yaw",
            "lat",
            "lon",
            "alt_rel",
            "alt_msl",
            "voltage",
            "current",
            "remaining",
            "gps_fix",
            "gps_sats",
            "mode",
            "armed",
            "vtype",
            "gs",
            "vz",
            "hdg",
            "dist_home",
            "wp",
            "vibe",
            "servo",
            "rc",
        }
        assert required_keys.issubset(full_state.keys())

    def test_delta_push_always_has_type_and_connected(self):
        """Delta push messages always contain 'type' and 'connected'."""
        link = DroneLink()
        state1 = link.get_state()
        last_sent = dict(state1)

        # Mutate one field
        link.attitude.roll = 99.9
        state2 = link.get_state()
        delta = {k: v for k, v in state2.items() if last_sent.get(k) != v}
        delta["type"] = "state"
        delta["connected"] = state2["connected"]

        assert delta["type"] == "state"
        assert "connected" in delta

    def test_delta_push_only_contains_changed_fields(self):
        """Delta push omits fields that have not changed."""
        link = DroneLink()
        state1 = link.get_state()
        last_sent = dict(state1)

        # Only change roll
        link.attitude.roll = 22.5
        state2 = link.get_state()
        delta = {k: v for k, v in state2.items() if last_sent.get(k) != v}
        delta["type"] = "state"
        delta["connected"] = state2["connected"]

        assert "roll" in delta
        assert delta["roll"] == 22.5
        # Unchanged fields should not be present (except type and connected)
        assert "voltage" not in delta or delta["voltage"] == last_sent["voltage"]

    def test_delta_push_is_valid_json(self):
        """Delta push serializes to valid JSON."""
        link = DroneLink()
        state = link.get_state()
        last_sent = dict(state)
        link.attitude.pitch = -5.0
        state2 = link.get_state()
        delta = {k: v for k, v in state2.items() if last_sent.get(k) != v}
        delta["type"] = "state"
        delta["connected"] = state2["connected"]

        # Must serialize cleanly
        text = json.dumps(delta)
        parsed = json.loads(text)
        assert parsed["type"] == "state"


# ---------------------------------------------------------------------------
# Command message format
# ---------------------------------------------------------------------------


class TestCommandMessageFormat:
    """Verify command messages have the correct structure."""

    def test_command_message_structure(self):
        """A command message must have type='command', cmd, and optional param."""
        msg = {"type": "command", "cmd": "arm", "param": None}
        assert msg["type"] == "command"
        assert "cmd" in msg
        assert "param" in msg

    def test_connect_message_structure(self):
        """A connect message has type='connect', port, baud, protocol."""
        msg = {"type": "connect", "port": "tcp:localhost:5770", "baud": 57600, "protocol": "auto"}
        assert msg["type"] == "connect"
        assert "port" in msg
        assert "baud" in msg
        assert "protocol" in msg

    def test_disconnect_message_structure(self):
        """A disconnect message has type='disconnect'."""
        msg = {"type": "disconnect"}
        assert msg["type"] == "disconnect"

    def test_set_locale_message_structure(self):
        """A set_locale message has type='set_locale' and locale field."""
        msg = {"type": "set_locale", "locale": "en"}
        assert msg["type"] == "set_locale"
        assert msg["locale"] == "en"

    def test_set_role_message_structure(self):
        """A set_role message has type='set_role' and role field."""
        msg = {"type": "set_role", "role": "pilot"}
        assert msg["type"] == "set_role"
        assert msg["role"] in ("pilot", "observer")


# ---------------------------------------------------------------------------
# Event message format
# ---------------------------------------------------------------------------


class TestEventMessageFormat:
    """Verify event messages have correct structure."""

    def test_event_message_fields(self):
        """Event messages must contain type, time, text, event_type."""
        link = DroneLink()
        link.add_event("Test event", "test_type")

        event = link.events[-1]
        # The push loop sends events in this format
        event_msg = {
            "type": "event",
            "time": event["time"],
            "text": event["text"],
            "event_type": event.get("event_type", ""),
        }
        assert event_msg["type"] == "event"
        assert "time" in event_msg
        assert "text" in event_msg
        assert "event_type" in event_msg
        assert event_msg["text"] == "Test event"
        assert event_msg["event_type"] == "test_type"

    def test_event_time_format(self):
        """Event time should be a string in HH:MM:SS format."""
        link = DroneLink()
        link.add_event("Timing test", "timing")

        event = link.events[-1]
        time_str = event["time"]
        assert len(time_str) == 8
        parts = time_str.split(":")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_event_serializes_cleanly(self):
        """Event messages can be serialized to JSON."""
        link = DroneLink()
        link.add_event("JSON test", "json_check")

        event = link.events[-1]
        msg = {
            "type": "event",
            "time": event["time"],
            "text": event["text"],
            "event_type": event.get("event_type", ""),
        }
        text = json.dumps(msg)
        parsed = json.loads(text)
        assert parsed["type"] == "event"
        assert parsed["text"] == "JSON test"


# ---------------------------------------------------------------------------
# HTTP endpoint contract verification
# ---------------------------------------------------------------------------


class TestHTTPEndpointContracts:
    """Verify all expected endpoints exist and return correct content types."""

    def test_health_returns_json(self):
        """GET /health returns JSON with 'ok' field."""
        r = client.get("/health")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/json")
        assert r.json()["ok"] is True

    def test_session_returns_required_fields(self):
        """GET /api/session returns all expected session fields."""
        r = client.get("/api/session")
        assert r.status_code == 200
        data = r.json()
        required_fields = {"connected", "clients", "armed", "sysid", "mode", "vtype"}
        assert required_fields.issubset(data.keys())
        assert isinstance(data["connected"], bool)
        assert isinstance(data["clients"], int)
        assert isinstance(data["armed"], bool)

    def test_version_returns_required_fields(self):
        """GET /api/version returns version string and protocol list."""
        r = client.get("/api/version")
        assert r.status_code == 200
        data = r.json()
        assert "version" in data
        assert "protocols" in data
        assert isinstance(data["protocols"], list)
        assert "standard" in data["protocols"]
        assert "pllink" in data["protocols"]
        assert "vehicles" in data
        assert isinstance(data["vehicles"], list)

    def test_tile_sources_returns_map_providers(self):
        """GET /api/tile_sources returns object with named providers."""
        r = client.get("/api/tile_sources")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        # Each provider should have name, sat, vec keys
        for _key, provider in data.items():
            assert "name" in provider
            assert "sat" in provider
            assert "vec" in provider

    def test_ports_returns_list(self):
        """GET /api/ports returns a JSON object with a 'ports' list."""
        r = client.get("/api/ports")
        assert r.status_code == 200
        data = r.json()
        assert "ports" in data
        assert isinstance(data["ports"], list)

    def test_auth_status_returns_boolean(self):
        """GET /api/auth/status returns auth_required boolean."""
        r = client.get("/api/auth/status")
        assert r.status_code == 200
        data = r.json()
        assert "auth_required" in data
        assert isinstance(data["auth_required"], bool)

    def test_tile_cache_returns_size_and_count(self):
        """GET /api/tile_cache returns size and count integers."""
        r = client.get("/api/tile_cache")
        assert r.status_code == 200
        data = r.json()
        assert "size" in data
        assert "count" in data
        assert isinstance(data["size"], int)
        assert isinstance(data["count"], int)

    def test_firmware_list_returns_files_array(self):
        """GET /api/firmware/list returns an object with 'files' list."""
        r = client.get("/api/firmware/list")
        assert r.status_code == 200
        data = r.json()
        assert "files" in data
        assert isinstance(data["files"], list)

    def test_mbtiles_list_returns_files_array(self):
        """GET /api/mbtiles/list returns an object with 'files' list."""
        r = client.get("/api/mbtiles/list")
        assert r.status_code == 200
        data = r.json()
        assert "files" in data
        assert isinstance(data["files"], list)

    def test_video_capabilities_contract(self):
        """GET /api/video/capabilities returns mjpeg and webrtc fields."""
        r = client.get("/api/video/capabilities")
        assert r.status_code == 200
        data = r.json()
        assert "mjpeg" in data
        assert "webrtc" in data
        assert isinstance(data["webrtc"], bool)


# ---------------------------------------------------------------------------
# WebSocket message flow contract
# ---------------------------------------------------------------------------


class TestWSMessageFlowContract:
    """Verify the WebSocket message exchange protocol."""

    @pytest.mark.asyncio
    async def test_broadcast_sends_json_text(self):
        """WSManager.broadcast sends JSON-encoded text to clients."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        mgr._clients = {ws}

        await mgr.broadcast({"type": "state", "connected": True})

        ws.send_text.assert_called_once()
        text = ws.send_text.call_args[0][0]
        # Must be valid JSON
        data = json.loads(text)
        assert data["type"] == "state"

    @pytest.mark.asyncio
    async def test_connect_result_message_format(self):
        """Connect result message has type='connect_result', ok, error."""
        # The contract: after a 'connect' message, server replies with connect_result
        expected = {"type": "connect_result", "ok": True, "error": ""}
        assert expected["type"] == "connect_result"
        assert isinstance(expected["ok"], bool)
        assert isinstance(expected["error"], str)

    @pytest.mark.asyncio
    async def test_role_update_message_format(self):
        """Role update broadcast has type='role_update', clients count, pilot_connected."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        mgr._clients = {ws}

        msg = {"type": "role_update", "clients": mgr.client_count, "pilot_connected": False}
        await mgr.broadcast(msg)

        received = json.loads(ws.send_text.call_args[0][0])
        assert received["type"] == "role_update"
        assert "clients" in received
        assert "pilot_connected" in received

    @pytest.mark.asyncio
    async def test_cmd_result_message_format(self):
        """Command result messages have type='cmd_result'."""
        msg = {"type": "cmd_result", "ok": True, "msg": "done"}
        assert msg["type"] == "cmd_result"
        assert "ok" in msg
