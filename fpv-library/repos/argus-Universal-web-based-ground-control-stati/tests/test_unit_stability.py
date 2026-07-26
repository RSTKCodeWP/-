"""Long-running stability tests for backend components."""

import struct
import sys
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.drone_link import DroneLink
from backend.param_manager import ParamManager
from backend.ws_manager import WSManager


def _make_link():
    link = MagicMock()
    link.sysid = 1
    link.sq = 0
    link.add_event = MagicMock()
    link.send = MagicMock()
    link.locale = "zh"
    link.vehicle = MagicMock()
    link.vehicle.sysid = 1
    return link


def _make_ws():
    ws = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.send_text = AsyncMock()
    ws.accept = AsyncMock()
    return ws


def _param_value_payload(name: str, value: float, index: int, total: int, ptype: int = 9) -> bytes:
    name_bytes = name.encode("ascii")[:16].ljust(16, b"\x00")
    return struct.pack("<f", value) + struct.pack("<HH", total, index) + name_bytes + struct.pack("<B", ptype)


class TestStateManagerRapidUpdates:
    """Test that DroneLink state handles 10000 rapid updates without errors."""

    def test_rapid_attitude_updates(self):
        link = DroneLink()
        errors = []
        for i in range(10000):
            try:
                link.attitude.roll = float(i % 360)
                link.attitude.pitch = float(i % 90)
                link.attitude.yaw = float(i % 360)
                link.attitude.lat = 30.0 + (i * 0.0001)
                link.attitude.lon = 120.0 + (i * 0.0001)
            except Exception as e:
                errors.append(e)
        assert errors == [], f"Errors during rapid attitude updates: {errors}"
        assert link.attitude.roll == float(9999 % 360)

    def test_rapid_battery_updates(self):
        link = DroneLink()
        errors = []
        for i in range(10000):
            try:
                link.battery.voltage = 10.0 + (i % 100) * 0.01
                link.battery.current = float(i % 50)
                link.battery.remaining = i % 101
            except Exception as e:
                errors.append(e)
        assert errors == [], f"Errors during rapid battery updates: {errors}"

    def test_rapid_get_state_under_load(self):
        link = DroneLink()
        errors = []
        for i in range(10000):
            try:
                link.attitude.roll = float(i)
                link.battery.voltage = float(i % 100)
                state = link.get_state()
                assert isinstance(state, dict)
                assert "roll" in state
                assert "voltage" in state
            except Exception as e:
                errors.append(e)
        assert errors == [], f"Errors during rapid get_state: {errors}"

    def test_concurrent_rapid_updates(self):
        link = DroneLink()
        errors = []
        stop = threading.Event()
        iterations = {"writer": 0, "reader": 0}

        def writer():
            i = 0
            while not stop.is_set() and i < 10000:
                try:
                    link.attitude.roll = float(i % 360)
                    link.attitude.lat = 30.0 + (i * 0.0001)
                    link.battery.voltage = 10.0 + (i % 100) * 0.01
                    link.gps.gps_sats = i % 20
                except Exception as e:
                    errors.append(("writer", e))
                i += 1
            iterations["writer"] = i

        def reader():
            i = 0
            while not stop.is_set() and i < 10000:
                try:
                    state = link.get_state()
                    assert isinstance(state, dict)
                except Exception as e:
                    errors.append(("reader", e))
                i += 1
            iterations["reader"] = i

        w = threading.Thread(target=writer, daemon=True)
        r = threading.Thread(target=reader, daemon=True)
        w.start()
        r.start()
        w.join(timeout=30)
        r.join(timeout=30)
        stop.set()
        assert errors == [], f"Errors during concurrent rapid updates: {errors}"
        assert iterations["writer"] > 0
        assert iterations["reader"] > 0


class TestWSManagerConnectDisconnect:
    """Test that WSManager handles 100 rapid connect/disconnect cycles."""

    @pytest.mark.asyncio
    async def test_rapid_client_add_remove(self):
        link = DroneLink()
        mgr = WSManager(link)
        errors = []

        for _i in range(100):
            ws = _make_ws()
            try:
                mgr._clients.add(ws)
                assert ws in mgr._clients
                mgr._clients.discard(ws)
                assert ws not in mgr._clients
            except Exception as e:
                errors.append(e)

        assert errors == [], f"Errors during rapid connect/disconnect: {errors}"
        assert mgr.client_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_with_many_failed_clients(self):
        link = DroneLink()
        mgr = WSManager(link)

        # Add 100 clients that will fail on send
        for _ in range(100):
            ws = _make_ws()
            ws.send_text.side_effect = ConnectionError("connection closed")
            mgr._clients.add(ws)

        assert mgr.client_count == 100

        # Broadcast should remove all failed clients without error
        await mgr.broadcast({"type": "state", "connected": False})
        assert mgr.client_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_interleaved_good_and_bad(self):
        link = DroneLink()
        mgr = WSManager(link)
        good_clients = []
        bad_clients = []

        for i in range(100):
            ws = _make_ws()
            if i % 2 == 0:
                good_clients.append(ws)
            else:
                ws.send_text.side_effect = ConnectionError("closed")
                bad_clients.append(ws)
            mgr._clients.add(ws)

        assert mgr.client_count == 100
        await mgr.broadcast({"type": "state", "connected": True})

        # All bad clients removed, good clients remain
        assert mgr.client_count == 50
        for ws in good_clients:
            assert ws in mgr._clients
        for ws in bad_clients:
            assert ws not in mgr._clients

    @pytest.mark.asyncio
    async def test_repeated_broadcast_cycles(self):
        link = DroneLink()
        mgr = WSManager(link)
        errors = []

        for cycle in range(100):
            ws = _make_ws()
            mgr._clients.add(ws)
            try:
                await mgr.broadcast({"type": "state", "cycle": cycle})
                assert ws.send_text.call_count == 1
            except Exception as e:
                errors.append(e)
            finally:
                mgr._clients.discard(ws)

        assert errors == [], f"Errors during broadcast cycles: {errors}"
        assert mgr.client_count == 0


class TestEventBufferBounds:
    """Test that the event buffer doesn't grow unbounded."""

    def test_events_capped_at_100(self):
        link = DroneLink()
        # Add 200 events, buffer should cap
        for i in range(200):
            link.add_event(f"event_{i}", "test")

        # DroneLink caps at 100, trimming to last 50
        assert len(link.events) <= 100

    def test_events_trimmed_to_last_50(self):
        link = DroneLink()
        for i in range(200):
            link.add_event(f"event_{i}", "test")

        # After trimming, should have the most recent events
        assert link.events[-1]["text"] == "event_199"
        assert len(link.events) <= 100

    def test_ws_queue_capped_at_2000(self):
        link = DroneLink()
        for i in range(3000):
            link.queue_ws({"type": "test", "i": i})

        # queue_ws caps at 2000, trimming to last 1000
        assert len(link._ws_queue) <= 2000

    def test_ws_queue_retains_recent(self):
        link = DroneLink()
        for i in range(3000):
            link.queue_ws({"type": "test", "i": i})

        # Most recent messages should be preserved
        assert link._ws_queue[-1]["i"] == 2999


class TestParamManagerStability:
    """Test that parameter manager handles duplicate and bulk operations."""

    def test_duplicate_param_sets_dont_inflate_count(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.fetching = True

        # Set the same param 100 times
        for _ in range(100):
            p = _param_value_payload("BATT_CAPACITY", 5000.0, 0, 10)
            mgr.handle_param_value(p, len(p))

        # received_count should be 1 since it's the same parameter
        assert mgr.received_count == 1
        assert len(mgr.params) == 1

    def test_messages_buffer_trimmed_on_large_param_set(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.fetching = True
        mgr.total_count = 2500

        for i in range(2500):
            name = "P%04d" % i
            p = _param_value_payload(name, float(i), i, 2500)
            mgr.handle_param_value(p, len(p))

        # Messages buffer should be trimmed (cap at 2000, trim to 1000)
        assert len(mgr._messages) <= 1500
        assert mgr.received_count == 2500

    def test_rapid_set_param_calls(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.params = {
            f"PARAM_{i}": {"name": f"PARAM_{i}", "value": float(i), "type": 9, "index": i} for i in range(100)
        }

        errors = []
        for i in range(100):
            try:
                mgr.set_param(f"PARAM_{i}", float(i * 2))
            except Exception as e:
                errors.append(e)

        assert errors == [], f"Errors during rapid set_param: {errors}"
        assert link.send.call_count == 100

    def test_handle_param_with_invalid_payloads(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.fetching = True

        # Short payloads should be ignored silently
        for _ in range(100):
            mgr.handle_param_value(b"\x00" * 10, 10)

        assert len(mgr.params) == 0
        assert mgr.received_count == 0

    def test_interleaved_valid_and_invalid_params(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.fetching = True

        valid_count = 0
        for i in range(200):
            if i % 2 == 0:
                # Valid payload
                name = "V%04d" % (i // 2)
                p = _param_value_payload(name, float(i), i // 2, 200)
                mgr.handle_param_value(p, len(p))
                valid_count += 1
            else:
                # Invalid short payload
                mgr.handle_param_value(b"\x00" * 5, 5)

        assert mgr.received_count == valid_count
        assert len(mgr.params) == valid_count
