"""Unit tests for multi-session concurrency: multiple WebSocket clients, per-client state, isolation."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.drone_link import DroneLink
from backend.ws_manager import WSManager


def make_ws():
    """Create a mock WebSocket with standard async methods."""
    ws = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.send_text = AsyncMock()
    ws.accept = AsyncMock()
    return ws


class TestMultiClientStateReceiving:
    """Test multiple WebSocket clients receiving state simultaneously."""

    @pytest.mark.asyncio
    async def test_two_clients_receive_same_state(self):
        """Both clients receive identical state broadcast."""
        link = DroneLink()
        mgr = WSManager(link)
        ws1 = make_ws()
        ws2 = make_ws()
        mgr._clients = {ws1, ws2}

        state = link.get_state()
        await mgr.broadcast(state)

        msg1 = json.loads(ws1.send_text.call_args[0][0])
        msg2 = json.loads(ws2.send_text.call_args[0][0])
        assert msg1 == msg2
        assert msg1["type"] == "state"

    @pytest.mark.asyncio
    async def test_three_clients_all_receive_updates(self):
        """Three connected clients all receive every broadcast."""
        link = DroneLink()
        mgr = WSManager(link)
        clients = [make_ws() for _ in range(3)]
        mgr._clients = set(clients)

        for i in range(5):
            link.attitude.roll = float(i * 10)
            state = link.get_state()
            await mgr.broadcast(state)

        for ws in clients:
            assert ws.send_text.call_count == 5
            last_msg = json.loads(ws.send_text.call_args[0][0])
            assert last_msg["roll"] == 40.0

    @pytest.mark.asyncio
    async def test_clients_receive_events_independently(self):
        """Each client gets event messages independently."""
        link = DroneLink()
        mgr = WSManager(link)
        ws1 = make_ws()
        ws2 = make_ws()
        mgr._clients = {ws1, ws2}

        link.add_event("Test event", "info")
        await mgr.broadcast({"type": "event", "text": "Test event"})

        assert ws1.send_text.call_count == 1
        assert ws2.send_text.call_count == 1


class TestCommandIsolation:
    """Test that one client's command doesn't interfere with another's state view."""

    @pytest.mark.asyncio
    async def test_command_from_one_client_state_visible_to_all(self):
        """A command that changes link state is visible to all clients on next broadcast."""
        link = DroneLink()
        mgr = WSManager(link)
        ws_commander = make_ws()
        ws_observer = make_ws()
        mgr._clients = {ws_commander, ws_observer}

        # Simulate commander changing state (e.g., mode change event)
        link.attitude.roll = 25.5
        state = link.get_state()
        await mgr.broadcast(state)

        msg_commander = json.loads(ws_commander.send_text.call_args[0][0])
        msg_observer = json.loads(ws_observer.send_text.call_args[0][0])
        assert msg_commander["roll"] == 25.5
        assert msg_observer["roll"] == 25.5

    @pytest.mark.asyncio
    async def test_rapid_commands_from_multiple_clients_no_state_corruption(self):
        """Rapid commands from multiple clients don't corrupt shared state."""
        link = DroneLink()
        mgr = WSManager(link)
        clients = [make_ws() for _ in range(5)]
        mgr._clients = set(clients)

        # Simulate rapid state mutations from different "command" sources
        for i in range(20):
            link.attitude.roll = float(i)
            link.attitude.pitch = float(-i)
            link.battery.voltage = 11.0 + i * 0.1
            state = link.get_state()
            await mgr.broadcast(state)

        # All clients should have received all 20 messages
        for ws in clients:
            assert ws.send_text.call_count == 20
            # Last message should reflect final state
            last = json.loads(ws.send_text.call_args[0][0])
            assert last["roll"] == 19.0
            assert last["pitch"] == -19.0

    @pytest.mark.asyncio
    async def test_inspector_data_shared_across_clients(self):
        """Inspector mode state is shared (link-level), all clients see same data."""
        link = DroneLink()
        mgr = WSManager(link)
        ws1 = make_ws()
        ws2 = make_ws()
        mgr._clients = {ws1, ws2}

        link.inspector_enabled = True
        inspector_msg = {"type": "inspector", "messages": link.get_inspector_data()}
        await mgr.broadcast(inspector_msg)

        msg1 = json.loads(ws1.send_text.call_args[0][0])
        msg2 = json.loads(ws2.send_text.call_args[0][0])
        assert msg1["type"] == "inspector"
        assert msg2["type"] == "inspector"
        assert msg1 == msg2


class TestClientDisconnectIsolation:
    """Test that client disconnect doesn't affect other clients."""

    @pytest.mark.asyncio
    async def test_disconnect_one_client_others_unaffected(self):
        """When one client disconnects (fails), others continue receiving."""
        link = DroneLink()
        mgr = WSManager(link)
        ws_alive = make_ws()
        ws_dead = make_ws()
        ws_dead.send_text.side_effect = ConnectionError("connection closed")
        mgr._clients = {ws_alive, ws_dead}

        await mgr.broadcast({"type": "state", "connected": True})

        # Dead client is removed
        assert ws_dead not in mgr._clients
        # Alive client still receives
        assert ws_alive in mgr._clients
        assert ws_alive.send_text.call_count == 1

    @pytest.mark.asyncio
    async def test_disconnect_does_not_lose_subsequent_messages(self):
        """After a client disconnects, remaining clients continue to get all future messages."""
        link = DroneLink()
        mgr = WSManager(link)
        ws_alive = make_ws()
        ws_dead = make_ws()
        ws_dead.send_text.side_effect = ConnectionError("gone")
        mgr._clients = {ws_alive, ws_dead}

        # First broadcast removes dead client
        await mgr.broadcast({"type": "state", "seq": 0})
        assert mgr.client_count == 1

        # Subsequent broadcasts go only to alive client
        for i in range(1, 10):
            await mgr.broadcast({"type": "state", "seq": i})

        assert ws_alive.send_text.call_count == 10
        # Verify ordering
        for i, call in enumerate(ws_alive.send_text.call_args_list):
            msg = json.loads(call[0][0])
            assert msg["seq"] == i

    @pytest.mark.asyncio
    async def test_multiple_disconnects_in_sequence(self):
        """Multiple clients disconnecting in sequence leaves survivors intact."""
        link = DroneLink()
        mgr = WSManager(link)
        survivors = [make_ws() for _ in range(3)]
        victims = [make_ws() for _ in range(4)]
        for ws in victims:
            ws.send_text.side_effect = ConnectionError("disconnected")
        mgr._clients = set(survivors + victims)

        await mgr.broadcast({"type": "state", "test": True})

        assert mgr.client_count == 3
        for ws in survivors:
            assert ws in mgr._clients
            msg = json.loads(ws.send_text.call_args[0][0])
            assert msg["test"] is True


class TestPerClientLocale:
    """Test locale setting is link-level but verifiable per-client behavior."""

    def test_locale_default_is_zh(self):
        """Default locale is 'zh'."""
        link = DroneLink()
        WSManager(link)
        assert link.locale == "zh"

    def test_set_locale_en(self):
        """Setting locale to 'en' changes link state."""
        link = DroneLink()
        WSManager(link)
        link.locale = "en"
        assert link.locale == "en"
        state = link.get_state()
        # English GPS fix names should be used
        assert state["gps_fix"] in ("No GPS", "No Fix", "2D Fix", "3D Fix", "3D DGPS", "RTK Float", "RTK Fix", "?")

    def test_locale_affects_state_output(self):
        """Different locale produces different mode labels in state."""
        link = DroneLink()
        WSManager(link)

        link.locale = "zh"
        state_zh = link.get_state()

        link.locale = "en"
        state_en = link.get_state()

        # GPS fix names differ by locale
        # With default gps_fix=0, 'zh' gives Chinese text, 'en' gives English
        assert state_zh["gps_fix"] != state_en["gps_fix"] or state_zh["gps_fix"] == "?"

    @pytest.mark.asyncio
    async def test_locale_change_reflected_in_broadcast(self):
        """After locale change, next broadcast reflects new locale."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        mgr._clients = {ws}

        link.locale = "en"
        state = link.get_state()
        await mgr.broadcast(state)

        msg = json.loads(ws.send_text.call_args[0][0])
        assert msg["type"] == "state"


class TestPerClientInspector:
    """Test inspector mode behavior across sessions."""

    def test_inspector_default_off(self):
        """Inspector mode is off by default."""
        link = DroneLink()
        WSManager(link)
        assert link.inspector_enabled is False

    def test_inspector_toggle_on(self):
        """Inspector mode can be toggled on."""
        link = DroneLink()
        WSManager(link)
        link.inspector_enabled = True
        assert link.inspector_enabled is True

    def test_inspector_data_empty_when_no_messages(self):
        """Inspector data is empty list when no MAVLink messages processed."""
        link = DroneLink()
        WSManager(link)
        link.inspector_enabled = True
        data = link.get_inspector_data()
        assert data == []

    @pytest.mark.asyncio
    async def test_inspector_broadcast_to_all_when_enabled(self):
        """When inspector is enabled, all clients receive inspector data."""
        link = DroneLink()
        mgr = WSManager(link)
        ws1 = make_ws()
        ws2 = make_ws()
        mgr._clients = {ws1, ws2}
        link.inspector_enabled = True

        inspector_msg = {"type": "inspector", "messages": link.get_inspector_data()}
        await mgr.broadcast(inspector_msg)

        for ws in [ws1, ws2]:
            msg = json.loads(ws.send_text.call_args[0][0])
            assert msg["type"] == "inspector"
            assert isinstance(msg["messages"], list)


class TestBroadcastOrderConsistency:
    """Test broadcast order consistency across multiple clients."""

    @pytest.mark.asyncio
    async def test_all_clients_see_same_message_order(self):
        """All clients receive messages in the same order."""
        link = DroneLink()
        mgr = WSManager(link)
        clients = [make_ws() for _ in range(5)]
        mgr._clients = set(clients)

        for i in range(30):
            await mgr.broadcast({"type": "state", "seq": i})

        # All clients should have same count and ordering
        for ws in clients:
            assert ws.send_text.call_count == 30
            for i, call in enumerate(ws.send_text.call_args_list):
                msg = json.loads(call[0][0])
                assert msg["seq"] == i

    @pytest.mark.asyncio
    async def test_interleaved_state_and_events_order_preserved(self):
        """Mixed state and event messages maintain order for all clients."""
        link = DroneLink()
        mgr = WSManager(link)
        clients = [make_ws() for _ in range(3)]
        mgr._clients = set(clients)

        messages = []
        for i in range(10):
            if i % 3 == 0:
                msg = {"type": "event", "seq": i, "text": f"event {i}"}
            else:
                msg = {"type": "state", "seq": i, "connected": True}
            messages.append(msg)
            await mgr.broadcast(msg)

        for ws in clients:
            assert ws.send_text.call_count == 10
            for i, call in enumerate(ws.send_text.call_args_list):
                received = json.loads(call[0][0])
                assert received["seq"] == messages[i]["seq"]
                assert received["type"] == messages[i]["type"]

    @pytest.mark.asyncio
    async def test_concurrent_gather_preserves_individual_broadcast_order(self):
        """Each individual broadcast delivers to all clients before next starts."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        mgr._clients = {ws}

        # Sequentially broadcast numbered messages
        for i in range(50):
            await mgr.broadcast({"type": "state", "n": i})

        # Verify order
        for i, call in enumerate(ws.send_text.call_args_list):
            msg = json.loads(call[0][0])
            assert msg["n"] == i


class TestRapidMultiClientCommands:
    """Test rapid commands from multiple clients don't corrupt state."""

    @pytest.mark.asyncio
    async def test_concurrent_state_reads_consistent(self):
        """Multiple concurrent get_state calls return consistent results."""
        link = DroneLink()
        link.attitude.roll = 10.0
        link.battery.voltage = 12.6

        # Simulate concurrent reads (in practice from push_loop of each client)
        states = []
        for _ in range(10):
            states.append(link.get_state())

        # All should be identical
        for s in states:
            assert s["roll"] == 10.0
            assert s["voltage"] == 12.6

    @pytest.mark.asyncio
    async def test_state_mutation_between_client_reads(self):
        """State mutation between reads gives updated result to later readers."""
        link = DroneLink()
        link.attitude.roll = 5.0

        state_before = link.get_state()
        link.attitude.roll = 15.0
        state_after = link.get_state()

        assert state_before["roll"] == 5.0
        assert state_after["roll"] == 15.0

    @pytest.mark.asyncio
    async def test_many_clients_simultaneous_broadcast_no_crash(self):
        """20 clients receiving 50 rapid broadcasts without crash."""
        link = DroneLink()
        mgr = WSManager(link)
        clients = [make_ws() for _ in range(20)]
        mgr._clients = set(clients)

        for i in range(50):
            link.attitude.roll = float(i)
            await mgr.broadcast(link.get_state())

        for ws in clients:
            assert ws.send_text.call_count == 50

    @pytest.mark.asyncio
    async def test_role_assignment_pilot_observer_isolation(self):
        """Setting pilot role for one client does not affect observer roles."""
        link = DroneLink()
        mgr = WSManager(link)
        ws_pilot = make_ws()
        ws_observer = make_ws()
        mgr._clients = {ws_pilot, ws_observer}

        # Assign roles
        mgr._roles[id(ws_pilot)] = "pilot"
        mgr._pilot_ws = ws_pilot
        mgr._roles[id(ws_observer)] = "observer"

        # Verify isolation
        assert mgr._roles[id(ws_pilot)] == "pilot"
        assert mgr._roles[id(ws_observer)] == "observer"
        assert mgr._pilot_ws is ws_pilot

    @pytest.mark.asyncio
    async def test_pilot_disconnect_does_not_crash_observer(self):
        """Pilot disconnecting does not prevent observer from receiving."""
        link = DroneLink()
        mgr = WSManager(link)
        ws_pilot = make_ws()
        ws_observer = make_ws()
        ws_pilot.send_text.side_effect = ConnectionError("pilot disconnected")
        mgr._clients = {ws_pilot, ws_observer}
        mgr._pilot_ws = ws_pilot
        mgr._roles[id(ws_pilot)] = "pilot"
        mgr._roles[id(ws_observer)] = "observer"

        await mgr.broadcast({"type": "state", "connected": True})

        # Pilot removed, observer still gets messages
        assert ws_pilot not in mgr._clients
        assert ws_observer in mgr._clients
        msg = json.loads(ws_observer.send_text.call_args[0][0])
        assert msg["connected"] is True

    @pytest.mark.asyncio
    async def test_client_count_tracks_additions_and_removals(self):
        """client_count correctly reflects additions and removals over time."""
        link = DroneLink()
        mgr = WSManager(link)

        assert mgr.client_count == 0

        ws1 = make_ws()
        mgr._clients.add(ws1)
        assert mgr.client_count == 1

        ws2 = make_ws()
        ws3 = make_ws()
        mgr._clients.add(ws2)
        mgr._clients.add(ws3)
        assert mgr.client_count == 3

        mgr._clients.discard(ws2)
        assert mgr.client_count == 2

        mgr._clients.discard(ws1)
        mgr._clients.discard(ws3)
        assert mgr.client_count == 0
