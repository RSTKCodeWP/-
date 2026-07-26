"""Stress tests for WSManager: high-frequency push, concurrent clients, rapid connect/disconnect."""

import asyncio
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


def make_slow_ws(delay: float = 0.01):
    """Create a mock WebSocket that simulates slow network sends."""
    ws = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.accept = AsyncMock()

    async def slow_send(text):
        await asyncio.sleep(delay)

    ws.send_text = AsyncMock(side_effect=slow_send)
    return ws


class TestHighFrequencyPush:
    """Test that broadcast works correctly under high-frequency push scenarios."""

    @pytest.mark.asyncio
    async def test_rapid_broadcast_many_messages(self):
        """Broadcast 100 messages rapidly to 5 clients without data loss."""
        link = DroneLink()
        mgr = WSManager(link)
        clients = [make_ws() for _ in range(5)]
        mgr._clients = set(clients)

        for i in range(100):
            await mgr.broadcast({"type": "state", "seq": i})

        for ws in clients:
            assert ws.send_text.call_count == 100

    @pytest.mark.asyncio
    async def test_broadcast_message_content_integrity(self):
        """Verify broadcast message content is not corrupted under load."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        mgr._clients = {ws}

        messages = [{"type": "state", "value": i, "data": "x" * 1000} for i in range(50)]
        for msg in messages:
            await mgr.broadcast(msg)

        assert ws.send_text.call_count == 50
        for i, call in enumerate(ws.send_text.call_args_list):
            received = json.loads(call[0][0])
            assert received["value"] == i
            assert received["data"] == "x" * 1000

    @pytest.mark.asyncio
    async def test_high_frequency_does_not_skip_clients(self):
        """All clients receive all messages even at high push frequency."""
        link = DroneLink()
        mgr = WSManager(link)
        clients = [make_ws() for _ in range(20)]
        mgr._clients = set(clients)

        for i in range(50):
            await mgr.broadcast({"type": "state", "n": i})

        for ws in clients:
            assert ws.send_text.call_count == 50

    @pytest.mark.asyncio
    async def test_concurrent_broadcasts(self):
        """Multiple concurrent broadcast calls do not lose messages."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        mgr._clients = {ws}

        tasks = [mgr.broadcast({"type": "state", "seq": i}) for i in range(30)]
        await asyncio.gather(*tasks)

        assert ws.send_text.call_count == 30


class TestConcurrentClients:
    """Test behavior with many simultaneous clients."""

    @pytest.mark.asyncio
    async def test_50_clients_broadcast(self):
        """Broadcast to 50 clients delivers to all."""
        link = DroneLink()
        mgr = WSManager(link)
        clients = [make_ws() for _ in range(50)]
        mgr._clients = set(clients)

        await mgr.broadcast({"type": "state", "connected": True})

        for ws in clients:
            assert ws.send_text.call_count == 1
            data = json.loads(ws.send_text.call_args[0][0])
            assert data["type"] == "state"
            assert data["connected"] is True

    @pytest.mark.asyncio
    async def test_client_count_with_many_clients(self):
        """client_count property tracks many clients correctly."""
        link = DroneLink()
        mgr = WSManager(link)
        clients = [make_ws() for _ in range(100)]
        mgr._clients = set(clients)
        assert mgr.client_count == 100

    @pytest.mark.asyncio
    async def test_failed_client_removed_others_unaffected(self):
        """When multiple clients fail, only those are removed."""
        link = DroneLink()
        mgr = WSManager(link)
        ok_clients = [make_ws() for _ in range(10)]
        fail_clients = [make_ws() for _ in range(5)]
        for ws in fail_clients:
            ws.send_text.side_effect = ConnectionError("connection reset")
        mgr._clients = set(ok_clients + fail_clients)

        await mgr.broadcast({"type": "state", "test": True})

        assert mgr.client_count == 10
        for ws in ok_clients:
            assert ws in mgr._clients
        for ws in fail_clients:
            assert ws not in mgr._clients

    @pytest.mark.asyncio
    async def test_partial_failure_does_not_block_others(self):
        """A client failing mid-broadcast does not prevent other clients from receiving."""
        link = DroneLink()
        mgr = WSManager(link)
        ws_ok1 = make_ws()
        ws_ok2 = make_ws()
        ws_fail = make_ws()
        ws_fail.send_text.side_effect = ConnectionError("broken pipe")
        mgr._clients = {ws_ok1, ws_ok2, ws_fail}

        await mgr.broadcast({"type": "state", "connected": False})

        assert ws_ok1.send_text.call_count == 1
        assert ws_ok2.send_text.call_count == 1
        assert ws_fail not in mgr._clients


class TestRapidConnectDisconnect:
    """Test rapid connect/disconnect cycles."""

    @pytest.mark.asyncio
    async def test_rapid_add_remove_clients(self):
        """Adding and removing clients rapidly keeps state consistent."""
        link = DroneLink()
        mgr = WSManager(link)

        for _ in range(100):
            ws = make_ws()
            mgr._clients.add(ws)
            mgr._clients.discard(ws)

        assert mgr.client_count == 0

    @pytest.mark.asyncio
    async def test_add_during_broadcast(self):
        """Adding a client during iteration does not cause errors."""
        link = DroneLink()
        mgr = WSManager(link)
        ws1 = make_ws()
        ws_new = make_ws()
        mgr._clients = {ws1}

        # Simulate: ws_new is added while broadcast iterates a copy of _clients
        original_send = ws1.send_text

        async def add_new_client(text):
            mgr._clients.add(ws_new)
            return await original_send(text)

        ws1.send_text = AsyncMock(side_effect=add_new_client)

        await mgr.broadcast({"type": "state"})

        # ws1 should have received; ws_new was added after snapshot
        assert ws1.send_text.call_count == 1

    @pytest.mark.asyncio
    async def test_remove_during_broadcast(self):
        """Removing a client during broadcast is handled gracefully."""
        link = DroneLink()
        mgr = WSManager(link)
        ws1 = make_ws()
        ws2 = make_ws()
        mgr._clients = {ws1, ws2}

        # ws2 raises exception -> gets removed
        ws2.send_text.side_effect = RuntimeError("disconnected")

        await mgr.broadcast({"type": "test"})

        assert ws2 not in mgr._clients
        assert ws1 in mgr._clients

    @pytest.mark.asyncio
    async def test_disconnect_reconnect_cycle(self):
        """Simulating a client disconnect and reconnect cycle."""
        link = DroneLink()
        mgr = WSManager(link)

        for cycle in range(20):
            ws = make_ws()
            mgr._clients.add(ws)
            await mgr.broadcast({"type": "state", "cycle": cycle})
            assert ws.send_text.call_count == 1
            mgr._clients.discard(ws)

        assert mgr.client_count == 0


class TestMessageOrdering:
    """Verify that message ordering is preserved."""

    @pytest.mark.asyncio
    async def test_broadcast_order_preserved(self):
        """Messages arrive in the order they were sent."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        mgr._clients = {ws}

        for i in range(100):
            await mgr.broadcast({"type": "state", "seq": i})

        for i, call in enumerate(ws.send_text.call_args_list):
            msg = json.loads(call[0][0])
            assert msg["seq"] == i

    @pytest.mark.asyncio
    async def test_interleaved_state_and_event_ordering(self):
        """Mixed message types preserve per-client ordering."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        mgr._clients = {ws}

        sequence = []
        for i in range(20):
            msg = {"type": "state", "seq": i} if i % 2 == 0 else {"type": "event", "seq": i}
            await mgr.broadcast(msg)
            sequence.append(msg)

        assert ws.send_text.call_count == 20
        for i, call in enumerate(ws.send_text.call_args_list):
            received = json.loads(call[0][0])
            assert received["seq"] == sequence[i]["seq"]
            assert received["type"] == sequence[i]["type"]

    @pytest.mark.asyncio
    async def test_ordering_across_multiple_clients(self):
        """Each client independently receives messages in order."""
        link = DroneLink()
        mgr = WSManager(link)
        clients = [make_ws() for _ in range(10)]
        mgr._clients = set(clients)

        for i in range(50):
            await mgr.broadcast({"type": "state", "index": i})

        for ws in clients:
            for i, call in enumerate(ws.send_text.call_args_list):
                msg = json.loads(call[0][0])
                assert msg["index"] == i

    @pytest.mark.asyncio
    async def test_delta_push_sequence_logic(self):
        """Delta push logic produces correct sequence: full on 1st, delta on 2nd-9th, full on 11th."""
        link = DroneLink()
        results = []

        last_sent = {}
        for push_count in range(1, 22):
            state = link.get_state()
            if push_count % 10 == 1:
                delta = state
                results.append("full")
            else:
                delta = {k: v for k, v in state.items() if last_sent.get(k) != v}
                delta["type"] = "state"
                delta["connected"] = state["connected"]
                results.append("delta")
            last_sent.update(state)

        # Push 1 and 11 and 21 should be full
        assert results[0] == "full"
        assert results[10] == "full"
        assert results[20] == "full"
        # All others should be delta
        for i in [1, 2, 3, 4, 5, 6, 7, 8, 9]:
            assert results[i] == "delta"


class TestBroadcastUnderLoad:
    """Test broadcast does not lose data when system is under load."""

    @pytest.mark.asyncio
    async def test_large_payload_broadcast(self):
        """Large JSON payloads are delivered intact to all clients."""
        link = DroneLink()
        mgr = WSManager(link)
        clients = [make_ws() for _ in range(10)]
        mgr._clients = set(clients)

        large_state = link.get_state()
        large_state["extra_data"] = list(range(1000))

        await mgr.broadcast(large_state)

        for ws in clients:
            received = json.loads(ws.send_text.call_args[0][0])
            assert received["extra_data"] == list(range(1000))
            assert received["type"] == "state"

    @pytest.mark.asyncio
    async def test_state_mutation_between_broadcasts(self):
        """State changes between broadcasts are reflected correctly."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        mgr._clients = {ws}

        state1 = link.get_state()
        await mgr.broadcast(state1)

        link.attitude.roll = 45.0
        link.attitude.pitch = -10.0
        state2 = link.get_state()
        await mgr.broadcast(state2)

        first_msg = json.loads(ws.send_text.call_args_list[0][0][0])
        second_msg = json.loads(ws.send_text.call_args_list[1][0][0])
        assert first_msg["roll"] == 0.0
        assert second_msg["roll"] == 45.0
        assert second_msg["pitch"] == -10.0

    @pytest.mark.asyncio
    async def test_no_message_loss_with_failing_clients_in_batch(self):
        """Surviving clients receive all messages even when others fail during burst."""
        link = DroneLink()
        mgr = WSManager(link)
        ws_ok = make_ws()
        ws_flaky = make_ws()
        call_count = [0]

        async def flaky_send(text):
            call_count[0] += 1
            if call_count[0] == 5:
                raise ConnectionError("connection dropped")

        ws_flaky.send_text = AsyncMock(side_effect=flaky_send)
        mgr._clients = {ws_ok, ws_flaky}

        for i in range(20):
            await mgr.broadcast({"type": "state", "n": i})

        # ws_ok should have received all 20 messages
        assert ws_ok.send_text.call_count == 20

    @pytest.mark.asyncio
    async def test_broadcast_with_empty_client_set(self):
        """Broadcasting with no clients does not raise errors."""
        link = DroneLink()
        mgr = WSManager(link)
        mgr._clients = set()

        # Should complete without error
        await mgr.broadcast({"type": "state", "connected": False})
        assert mgr.client_count == 0

    @pytest.mark.asyncio
    async def test_json_serialization_consistency(self):
        """All clients receive identical JSON serialization of the same message."""
        link = DroneLink()
        mgr = WSManager(link)
        clients = [make_ws() for _ in range(10)]
        mgr._clients = set(clients)

        msg = {"type": "state", "connected": True, "roll": 1.5, "nested": {"a": [1, 2, 3]}}
        await mgr.broadcast(msg)

        expected_text = json.dumps(msg)
        for ws in clients:
            assert ws.send_text.call_args[0][0] == expected_text
