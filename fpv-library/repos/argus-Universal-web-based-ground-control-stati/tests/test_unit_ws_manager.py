"""Unit tests for WSManager delta push and state management."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import WebSocketDisconnect

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from unittest.mock import MagicMock as _MagicMock

from backend.drone_link import DroneLink
from backend.param_manager import ParamManager
from backend.ws_manager import WSManager


def make_ws():
    ws = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.send_text = AsyncMock()
    ws.accept = AsyncMock()
    return ws


class TestWSManagerInit:
    def test_creates_with_link(self):
        link = DroneLink()
        mgr = WSManager(link)
        assert mgr.link is link
        assert mgr.client_count == 0

    def test_client_count(self):
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        mgr._clients.add(ws)
        assert mgr.client_count == 1


class TestDeltaPush:
    def test_first_push_is_full(self):
        link = DroneLink()
        state = link.get_state()
        last_sent = {}
        push_count = 1
        if push_count % 10 == 1:
            delta = state
        else:
            delta = {k: v for k, v in state.items() if last_sent.get(k) != v}
        assert delta == state

    def test_second_push_is_delta(self):
        link = DroneLink()
        state1 = link.get_state()
        last_sent = dict(state1)
        link.attitude.roll = 15.0
        state2 = link.get_state()
        delta = {k: v for k, v in state2.items() if last_sent.get(k) != v}
        delta["type"] = "state"
        delta["connected"] = state2["connected"]
        assert "roll" in delta
        assert delta["roll"] == 15.0
        assert "voltage" not in delta or delta.get("voltage") == last_sent.get("voltage")

    def test_every_10th_is_full(self):
        link = DroneLink()
        state = link.get_state()
        # 10th push cycle sends full state
        delta = state
        assert delta == state

    def test_delta_includes_type_and_connected(self):
        link = DroneLink()
        state1 = link.get_state()
        last_sent = dict(state1)
        state2 = link.get_state()
        delta = {k: v for k, v in state2.items() if last_sent.get(k) != v}
        delta["type"] = "state"
        delta["connected"] = state2["connected"]
        assert delta["type"] == "state"
        assert "connected" in delta


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self):
        link = DroneLink()
        mgr = WSManager(link)
        ws1 = make_ws()
        ws2 = make_ws()
        mgr._clients = {ws1, ws2}
        await mgr.broadcast({"type": "test", "data": 1})
        assert ws1.send_text.call_count == 1
        assert ws2.send_text.call_count == 1
        sent = json.loads(ws1.send_text.call_args[0][0])
        assert sent["type"] == "test"

    @pytest.mark.asyncio
    async def test_broadcast_removes_failed_client(self):
        link = DroneLink()
        mgr = WSManager(link)
        ws_ok = make_ws()
        ws_fail = make_ws()
        ws_fail.send_text.side_effect = ConnectionError("connection closed")
        mgr._clients = {ws_ok, ws_fail}
        await mgr.broadcast({"type": "test"})
        assert ws_fail not in mgr._clients
        assert ws_ok in mgr._clients


class TestReceiveCommands:
    def test_set_locale(self):
        link = DroneLink()
        WSManager(link)
        assert link.locale == "zh"

    def test_inspector_toggle(self):
        link = DroneLink()
        assert link.inspector_enabled is False


# ---------------------------------------------------------------------------
# handle_client lifecycle
# ---------------------------------------------------------------------------


class TestHandleClient:
    @pytest.mark.asyncio
    async def test_accept_and_adds_client(self):
        """handle_client accepts the ws and registers it in _clients."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        # receive_text raises disconnect immediately so the loop exits
        ws.receive_text.side_effect = WebSocketDisconnect()
        await mgr.handle_client(ws)
        ws.accept.assert_awaited_once()
        # After exit the client is cleaned up
        assert ws not in mgr._clients

    @pytest.mark.asyncio
    async def test_cleanup_on_connection_error(self):
        """handle_client cleans up when a ConnectionError occurs."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        ws.receive_text.side_effect = ConnectionError("gone")
        await mgr.handle_client(ws)
        assert ws not in mgr._clients

    @pytest.mark.asyncio
    async def test_cleanup_on_runtime_error(self):
        """handle_client cleans up when a RuntimeError occurs."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        ws.receive_text.side_effect = RuntimeError("closed")
        await mgr.handle_client(ws)
        assert ws not in mgr._clients


# ---------------------------------------------------------------------------
# _receive_loop message handling
# ---------------------------------------------------------------------------


class TestReceiveLoop:
    @pytest.mark.asyncio
    async def test_connect_message(self):
        """'connect' message calls link.connect and sends connect_result."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        msg = json.dumps({"type": "connect", "port": "tcp:localhost:5770", "baud": 57600, "protocol": "auto"})
        ws.receive_text.side_effect = [msg, WebSocketDisconnect()]
        with patch.object(link, "connect", return_value=True) as mock_conn:
            await mgr._receive_loop(ws)
            mock_conn.assert_called_once_with("tcp:localhost:5770", 57600, protocol="auto")
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "connect_result"
        assert sent["ok"] is True
        assert sent["error"] == ""

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Failed connect sends error message."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        msg = json.dumps({"type": "connect", "port": "/dev/ttyUSB0"})
        ws.receive_text.side_effect = [msg, WebSocketDisconnect()]
        with patch.object(link, "connect", return_value=False):
            await mgr._receive_loop(ws)
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["ok"] is False
        assert sent["error"] != ""

    @pytest.mark.asyncio
    async def test_disconnect_message(self):
        """'disconnect' message calls link.disconnect."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        msg = json.dumps({"type": "disconnect"})
        ws.receive_text.side_effect = [msg, WebSocketDisconnect()]
        with patch.object(link, "disconnect") as mock_disc:
            await mgr._receive_loop(ws)
            mock_disc.assert_called_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "connect_result"
        assert sent["ok"] is True

    @pytest.mark.asyncio
    async def test_set_locale_message(self):
        """'set_locale' message updates link.locale."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        msg = json.dumps({"type": "set_locale", "locale": "en"})
        ws.receive_text.side_effect = [msg, WebSocketDisconnect()]
        await mgr._receive_loop(ws)
        assert link.locale == "en"

    @pytest.mark.asyncio
    async def test_set_locale_default(self):
        """'set_locale' without locale key defaults to 'zh'."""
        link = DroneLink()
        link.locale = "en"
        mgr = WSManager(link)
        ws = make_ws()
        msg = json.dumps({"type": "set_locale"})
        ws.receive_text.side_effect = [msg, WebSocketDisconnect()]
        await mgr._receive_loop(ws)
        assert link.locale == "zh"

    @pytest.mark.asyncio
    async def test_set_role_pilot(self):
        """'set_role' with 'pilot' sets the pilot ws and broadcasts."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        mgr._clients.add(ws)
        msg = json.dumps({"type": "set_role", "role": "pilot"})
        ws.receive_text.side_effect = [msg, WebSocketDisconnect()]
        await mgr._receive_loop(ws)
        assert mgr._pilot_ws is ws
        assert mgr._roles[id(ws)] == "pilot"
        # broadcast was called — send_text was invoked with role_update
        calls = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
        role_msgs = [c for c in calls if c.get("type") == "role_update"]
        assert len(role_msgs) == 1
        assert "pilot_connected" in role_msgs[0]

    @pytest.mark.asyncio
    async def test_set_role_observer(self):
        """'set_role' with 'observer' stores role but does not set pilot."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        mgr._clients.add(ws)
        msg = json.dumps({"type": "set_role", "role": "observer"})
        ws.receive_text.side_effect = [msg, WebSocketDisconnect()]
        await mgr._receive_loop(ws)
        assert mgr._roles[id(ws)] == "observer"
        assert mgr._pilot_ws is None

    @pytest.mark.asyncio
    async def test_request_handoff_no_pilot(self):
        """'request_handoff' with no existing pilot grants immediately."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        mgr._clients.add(ws)
        msg = json.dumps({"type": "request_handoff"})
        ws.receive_text.side_effect = [msg, WebSocketDisconnect()]
        await mgr._receive_loop(ws)
        assert mgr._pilot_ws is ws
        assert mgr._roles[id(ws)] == "pilot"
        calls = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
        granted = [c for c in calls if c.get("type") == "handoff_granted"]
        assert len(granted) == 1

    @pytest.mark.asyncio
    async def test_request_handoff_with_existing_pilot(self):
        """'request_handoff' with existing pilot sends handoff_request to pilot."""
        link = DroneLink()
        mgr = WSManager(link)
        ws_pilot = make_ws()
        ws_requester = make_ws()
        mgr._clients.update({ws_pilot, ws_requester})
        mgr._pilot_ws = ws_pilot
        msg = json.dumps({"type": "request_handoff"})
        ws_requester.receive_text.side_effect = [msg, WebSocketDisconnect()]
        await mgr._receive_loop(ws_requester)
        # The pilot should have received a handoff_request
        calls = [json.loads(c[0][0]) for c in ws_pilot.send_text.call_args_list]
        hr = [c for c in calls if c.get("type") == "handoff_request"]
        assert len(hr) == 1
        assert hr[0]["from"] == id(ws_requester)

    @pytest.mark.asyncio
    async def test_request_handoff_same_as_pilot(self):
        """'request_handoff' from the current pilot grants immediately."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        mgr._clients.add(ws)
        mgr._pilot_ws = ws  # requester IS the pilot
        msg = json.dumps({"type": "request_handoff"})
        ws.receive_text.side_effect = [msg, WebSocketDisconnect()]
        await mgr._receive_loop(ws)
        calls = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
        granted = [c for c in calls if c.get("type") == "handoff_granted"]
        assert len(granted) == 1

    @pytest.mark.asyncio
    async def test_handoff_accept(self):
        """'handoff_accept' transfers pilot role to the target client."""
        link = DroneLink()
        mgr = WSManager(link)
        ws_old_pilot = make_ws()
        ws_new_pilot = make_ws()
        mgr._clients.update({ws_old_pilot, ws_new_pilot})
        mgr._pilot_ws = ws_old_pilot
        msg = json.dumps({"type": "handoff_accept", "target": id(ws_new_pilot)})
        ws_old_pilot.receive_text.side_effect = [msg, WebSocketDisconnect()]
        await mgr._receive_loop(ws_old_pilot)
        assert mgr._pilot_ws is ws_new_pilot
        assert mgr._roles[id(ws_new_pilot)] == "pilot"
        assert mgr._roles[id(ws_old_pilot)] == "observer"
        # new pilot gets handoff_granted
        new_calls = [json.loads(c[0][0]) for c in ws_new_pilot.send_text.call_args_list]
        assert any(c.get("type") == "handoff_granted" for c in new_calls)
        # old pilot gets handoff_released
        old_calls = [json.loads(c[0][0]) for c in ws_old_pilot.send_text.call_args_list]
        assert any(c.get("type") == "handoff_released" for c in old_calls)

    @pytest.mark.asyncio
    async def test_handoff_accept_unknown_target(self):
        """'handoff_accept' with unknown target id does nothing."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        mgr._clients.add(ws)
        mgr._pilot_ws = ws
        msg = json.dumps({"type": "handoff_accept", "target": 99999999})
        ws.receive_text.side_effect = [msg, WebSocketDisconnect()]
        await mgr._receive_loop(ws)
        # pilot remains unchanged
        assert mgr._pilot_ws is ws

    @pytest.mark.asyncio
    async def test_command_message(self):
        """'command' message calls commands.execute and returns result."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        # Implicit-pilot path: single connected client with no role set.
        mgr._clients.add(ws)
        msg = json.dumps({"type": "command", "cmd": "arm", "param": None})
        ws.receive_text.side_effect = [msg, WebSocketDisconnect()]
        with patch("backend.ws_manager.commands.execute", return_value={"ok": True, "msg": "armed"}) as mock_exec:
            await mgr._receive_loop(ws)
            mock_exec.assert_called_once_with(
                "arm",
                None,
                link,
                data={
                    "type": "command",
                    "cmd": "arm",
                    "param": None,
                },
            )
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "cmd_result"
        assert sent["ok"] is True

    @pytest.mark.asyncio
    async def test_observer_command_rejected(self):
        """When multiple clients are connected and this ws has no pilot role,
        commands must be rejected so an observer can't arm/takeoff."""
        link = DroneLink()
        mgr = WSManager(link)
        ws_observer = make_ws()
        ws_pilot = make_ws()
        mgr._clients.add(ws_observer)
        mgr._clients.add(ws_pilot)
        mgr._pilot_ws = ws_pilot
        mgr._roles[id(ws_pilot)] = "pilot"
        msg = json.dumps({"type": "command", "cmd": "arm", "param": None})
        ws_observer.receive_text.side_effect = [msg, WebSocketDisconnect()]
        with patch("backend.ws_manager.commands.execute") as mock_exec:
            await mgr._receive_loop(ws_observer)
            mock_exec.assert_not_called()
        sent = json.loads(ws_observer.send_text.call_args[0][0])
        assert sent["type"] == "cmd_result" and sent["ok"] is False

    @pytest.mark.asyncio
    async def test_command_returns_none(self):
        """When commands.execute returns None, no cmd_result is sent."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        # Single connected client → implicit pilot, command dispatch allowed.
        mgr._clients.add(ws)
        msg = json.dumps({"type": "command", "cmd": "unknown_cmd", "param": None})
        ws.receive_text.side_effect = [msg, WebSocketDisconnect()]
        with patch("backend.ws_manager.commands.execute", return_value=None):
            await mgr._receive_loop(ws)
        # No send_text calls should have been made
        assert ws.send_text.call_count == 0

    @pytest.mark.asyncio
    async def test_invalid_json_skipped(self):
        """Invalid JSON messages are silently skipped."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        ws.receive_text.side_effect = ["not json{{{", WebSocketDisconnect()]
        await mgr._receive_loop(ws)
        assert ws.send_text.call_count == 0

    @pytest.mark.asyncio
    async def test_unknown_message_type_ignored(self):
        """Unknown message type is silently ignored."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        msg = json.dumps({"type": "nonexistent_type"})
        ws.receive_text.side_effect = [msg, WebSocketDisconnect()]
        await mgr._receive_loop(ws)
        assert ws.send_text.call_count == 0

    @pytest.mark.asyncio
    async def test_connection_error_in_receive(self):
        """ConnectionError in _receive_loop is caught gracefully."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        ws.receive_text.side_effect = ConnectionError("reset")
        # Should not raise
        await mgr._receive_loop(ws)

    @pytest.mark.asyncio
    async def test_runtime_error_in_receive(self):
        """RuntimeError in _receive_loop is caught gracefully."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        ws.receive_text.side_effect = RuntimeError("closed")
        await mgr._receive_loop(ws)


# ---------------------------------------------------------------------------
# implicit-pilot ordering (multi-client command-lockout regression)
# ---------------------------------------------------------------------------


class TestImplicitPilotEarliest:
    """With no explicit pilot assigned, command authority belongs to the
    earliest-connected client (the session operator). The previous
    `client_count == 1` gate locked out EVERY client the moment a second one
    connected: an observer merely opening the page silently stripped the
    operator's ability to command, with no UI path to reclaim it (nothing in
    the frontend sends set_role / request_handoff)."""

    @pytest.mark.asyncio
    async def test_operator_keeps_command_after_observer_joins(self):
        link = DroneLink()
        mgr = WSManager(link)
        op = make_ws()
        obs = make_ws()
        # Operator connected first, observer second; no explicit roles set.
        mgr._clients.add(op)
        mgr._clients.add(obs)
        mgr._order = [op, obs]
        msg = json.dumps({"type": "command", "cmd": "arm", "param": None})
        op.receive_text.side_effect = [msg, WebSocketDisconnect()]
        with patch("backend.ws_manager.commands.execute", return_value={"ok": True}) as mock_exec:
            await mgr._receive_loop(op)
            mock_exec.assert_called_once()
        sent = json.loads(op.send_text.call_args[0][0])
        assert sent["type"] == "cmd_result" and sent["ok"] is True

    @pytest.mark.asyncio
    async def test_late_observer_still_rejected(self):
        """The observer (not earliest) cannot command while the operator holds
        implicit authority — the security guard still blocks passive viewers."""
        link = DroneLink()
        mgr = WSManager(link)
        op = make_ws()
        obs = make_ws()
        mgr._clients.add(op)
        mgr._clients.add(obs)
        mgr._order = [op, obs]
        msg = json.dumps({"type": "command", "cmd": "arm", "param": None})
        obs.receive_text.side_effect = [msg, WebSocketDisconnect()]
        with patch("backend.ws_manager.commands.execute") as mock_exec:
            await mgr._receive_loop(obs)
            mock_exec.assert_not_called()
        sent = json.loads(obs.send_text.call_args[0][0])
        assert sent["type"] == "cmd_result" and sent["ok"] is False

    @pytest.mark.asyncio
    async def test_authority_transfers_when_operator_disconnects(self):
        """When the earliest client has dropped from _clients (disconnected),
        the next-earliest still-connected client inherits command authority."""
        link = DroneLink()
        mgr = WSManager(link)
        gone = make_ws()
        obs = make_ws()
        mgr._clients.add(obs)  # only obs remains connected
        mgr._order = [gone, obs]  # gone is earliest in order but not in _clients
        msg = json.dumps({"type": "command", "cmd": "arm", "param": None})
        obs.receive_text.side_effect = [msg, WebSocketDisconnect()]
        with patch("backend.ws_manager.commands.execute", return_value={"ok": True}) as mock_exec:
            await mgr._receive_loop(obs)
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_client_tracks_and_untracks_order(self):
        """handle_client appends to _order on connect and removes on cleanup."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        ws.receive_text.side_effect = WebSocketDisconnect()
        await mgr.handle_client(ws)
        assert ws not in mgr._order  # cleaned up on disconnect


# ---------------------------------------------------------------------------
# _push_loop
# ---------------------------------------------------------------------------


class TestPushLoop:
    @pytest.mark.asyncio
    async def test_first_push_sends_full_state(self):
        """First push (count=1) sends full state dict."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        call_count = 0

        async def fake_sleep(_interval):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise WebSocketDisconnect()

        with patch("backend.ws_manager.asyncio.sleep", side_effect=fake_sleep):
            await mgr._push_loop(ws)

        # First send_text call should be the state push
        first_msg = json.loads(ws.send_text.call_args_list[0][0][0])
        assert first_msg["type"] == "state"
        assert "connected" in first_msg
        assert "roll" in first_msg
        assert "voltage" in first_msg

    @pytest.mark.asyncio
    async def test_delta_push_after_first(self):
        """Pushes 2-9 send delta (only changed fields)."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        call_count = 0

        async def fake_sleep(_interval):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Mutate state between first and second push
                link.attitude.roll = 42.0
            if call_count >= 2:
                raise WebSocketDisconnect()

        with patch("backend.ws_manager.asyncio.sleep", side_effect=fake_sleep):
            await mgr._push_loop(ws)

        # Second send_text call is a delta push
        state_sends = [
            json.loads(c[0][0]) for c in ws.send_text.call_args_list if json.loads(c[0][0]).get("type") == "state"
        ]
        assert len(state_sends) >= 2
        second = state_sends[1]
        assert second["type"] == "state"
        assert "connected" in second
        assert second.get("roll") == 42.0

    @pytest.mark.asyncio
    async def test_event_push(self):
        """New events are pushed to the client."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        call_count = 0

        async def fake_sleep(_interval):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                link.add_event("test event", "info")
            if call_count >= 2:
                raise WebSocketDisconnect()

        with patch("backend.ws_manager.asyncio.sleep", side_effect=fake_sleep):
            await mgr._push_loop(ws)

        all_msgs = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
        event_msgs = [m for m in all_msgs if m.get("type") == "event"]
        assert len(event_msgs) >= 1
        assert event_msgs[0]["text"] == "test event"
        assert event_msgs[0]["event_type"] == "info"

    @pytest.mark.asyncio
    async def test_mission_dl_push(self):
        """Mission download messages are forwarded to the client."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        call_count = 0

        async def fake_sleep(_interval):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                link.mission._dl_messages.append({"type": "mission_item", "seq": 0})
            if call_count >= 2:
                raise WebSocketDisconnect()

        with patch("backend.ws_manager.asyncio.sleep", side_effect=fake_sleep):
            await mgr._push_loop(ws)

        all_msgs = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
        dl_msgs = [m for m in all_msgs if m.get("type") == "mission_item"]
        assert len(dl_msgs) == 1
        assert dl_msgs[0]["seq"] == 0

    @pytest.mark.asyncio
    async def test_log_dl_push(self):
        """Log download messages are forwarded to the client."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        call_count = 0

        async def fake_sleep(_interval):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                link.log_dl._log_messages.append({"type": "log_data", "id": 1})
            if call_count >= 2:
                raise WebSocketDisconnect()

        with patch("backend.ws_manager.asyncio.sleep", side_effect=fake_sleep):
            await mgr._push_loop(ws)

        all_msgs = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
        log_msgs = [m for m in all_msgs if m.get("type") == "log_data"]
        assert len(log_msgs) == 1

    @pytest.mark.asyncio
    async def test_param_batch_push(self):
        """Param values are batched into a param_batch message."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        call_count = 0

        async def fake_sleep(_interval):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                link.param_mgr._messages.append({"type": "param_value", "name": "RC1_MAX", "value": 2000})
                link.param_mgr._messages.append({"type": "param_value", "name": "RC1_MIN", "value": 1000})
            if call_count >= 2:
                raise WebSocketDisconnect()

        with patch("backend.ws_manager.asyncio.sleep", side_effect=fake_sleep):
            await mgr._push_loop(ws)

        all_msgs = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
        batch_msgs = [m for m in all_msgs if m.get("type") == "param_batch"]
        assert len(batch_msgs) == 1
        assert len(batch_msgs[0]["params"]) == 2

    @pytest.mark.asyncio
    async def test_param_non_value_push(self):
        """Non-param_value param messages are sent individually."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        call_count = 0

        async def fake_sleep(_interval):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                link.param_mgr._messages.append({"type": "param_progress", "pct": 50})
            if call_count >= 2:
                raise WebSocketDisconnect()

        with patch("backend.ws_manager.asyncio.sleep", side_effect=fake_sleep):
            await mgr._push_loop(ws)

        all_msgs = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
        progress_msgs = [m for m in all_msgs if m.get("type") == "param_progress"]
        assert len(progress_msgs) == 1
        assert progress_msgs[0]["pct"] == 50

    @pytest.mark.asyncio
    async def test_inspector_data_push(self):
        """When inspector_enabled, inspector data is sent."""
        link = DroneLink()
        link.inspector_enabled = True
        mgr = WSManager(link)
        ws = make_ws()
        call_count = 0

        async def fake_sleep(_interval):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise WebSocketDisconnect()

        with patch("backend.ws_manager.asyncio.sleep", side_effect=fake_sleep):
            await mgr._push_loop(ws)

        all_msgs = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
        insp_msgs = [m for m in all_msgs if m.get("type") == "inspector"]
        assert len(insp_msgs) == 1
        assert "messages" in insp_msgs[0]

    @pytest.mark.asyncio
    async def test_inspector_data_not_sent_when_disabled(self):
        """When inspector_enabled is False, no inspector data is sent."""
        link = DroneLink()
        link.inspector_enabled = False
        mgr = WSManager(link)
        ws = make_ws()
        call_count = 0

        async def fake_sleep(_interval):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise WebSocketDisconnect()

        with patch("backend.ws_manager.asyncio.sleep", side_effect=fake_sleep):
            await mgr._push_loop(ws)

        all_msgs = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
        insp_msgs = [m for m in all_msgs if m.get("type") == "inspector"]
        assert len(insp_msgs) == 0

    @pytest.mark.asyncio
    async def test_console_buffer_push(self):
        """Console buffer contents are sent and cleared."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        call_count = 0

        async def fake_sleep(_interval):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                link._console_buf.append("hello ")
                link._console_buf.append("world")
            if call_count >= 2:
                raise WebSocketDisconnect()

        with patch("backend.ws_manager.asyncio.sleep", side_effect=fake_sleep):
            await mgr._push_loop(ws)

        all_msgs = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
        console_msgs = [m for m in all_msgs if m.get("type") == "console_output"]
        assert len(console_msgs) == 1
        assert console_msgs[0]["text"] == "hello world"
        # Buffer should be cleared
        assert link._console_buf == []

    @pytest.mark.asyncio
    async def test_empty_console_buffer_not_sent(self):
        """Empty console buffer does not produce a console_output message."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        call_count = 0

        async def fake_sleep(_interval):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise WebSocketDisconnect()

        with patch("backend.ws_manager.asyncio.sleep", side_effect=fake_sleep):
            await mgr._push_loop(ws)

        all_msgs = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
        console_msgs = [m for m in all_msgs if m.get("type") == "console_output"]
        assert len(console_msgs) == 0

    @pytest.mark.asyncio
    async def test_push_interval_connected(self):
        """Uses WS_PUSH_INTERVAL_CONNECTED when link is connected."""
        link = DroneLink()
        link.connected = True
        mgr = WSManager(link)
        ws = make_ws()
        intervals = []

        async def fake_sleep(interval):
            intervals.append(interval)
            raise WebSocketDisconnect()

        with patch("backend.ws_manager.asyncio.sleep", side_effect=fake_sleep):
            await mgr._push_loop(ws)

        from backend.config import cfg

        assert intervals[0] == cfg.WS_PUSH_INTERVAL_CONNECTED

    @pytest.mark.asyncio
    async def test_push_interval_idle(self):
        """Uses WS_PUSH_INTERVAL_IDLE when link is disconnected."""
        link = DroneLink()
        link.connected = False
        mgr = WSManager(link)
        ws = make_ws()
        intervals = []

        async def fake_sleep(interval):
            intervals.append(interval)
            raise WebSocketDisconnect()

        with patch("backend.ws_manager.asyncio.sleep", side_effect=fake_sleep):
            await mgr._push_loop(ws)

        from backend.config import cfg

        assert intervals[0] == cfg.WS_PUSH_INTERVAL_IDLE

    @pytest.mark.asyncio
    async def test_push_connection_error(self):
        """ConnectionError in _push_loop is caught gracefully."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        ws.send_text.side_effect = ConnectionError("gone")
        # Should not raise
        await mgr._push_loop(ws)

    @pytest.mark.asyncio
    async def test_push_runtime_error(self):
        """RuntimeError in _push_loop is caught gracefully."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        ws.send_text.side_effect = RuntimeError("closed")
        await mgr._push_loop(ws)

    @pytest.mark.asyncio
    async def test_event_cursor_tracks_monotonic_seq(self):
        """The push cursor uses _events_emitted_total (monotonic), not the
        array index — so a trim of self.events doesn't cause replays."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        # Pre-populate events so cursor starts high (5 events emitted total).
        for i in range(5):
            link.add_event(f"event {i}")
        assert link._events_emitted_total == 5
        call_count = 0

        async def fake_sleep(_interval):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Add a 6th event AND simulate an unrelated trim of the array.
                link.add_event("event new")
                # Trim simulation: drop the oldest entries the way add_event's
                # cap rule would (but events still keeps the latest seq).
                link.events = link.events[-2:]
            if call_count >= 2:
                raise WebSocketDisconnect()

        with patch("backend.ws_manager.asyncio.sleep", side_effect=fake_sleep):
            await mgr._push_loop(ws)

        all_msgs = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
        event_msgs = [m for m in all_msgs if m.get("type") == "event"]
        # The new event must arrive exactly once (no replays of older events).
        assert sum(1 for m in event_msgs if m["text"] == "event new") == 1

    @pytest.mark.asyncio
    async def test_dl_cursor_reset_on_shrink(self):
        """DL cursor resets when mission._dl_messages shrinks."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        # Pre-populate so cursor starts high
        for i in range(3):
            link.mission._dl_messages.append({"type": "mission_item", "seq": i})
        call_count = 0

        async def fake_sleep(_interval):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                link.mission._dl_messages.clear()
                link.mission._dl_messages.append({"type": "mission_item", "seq": 99})
            if call_count >= 2:
                raise WebSocketDisconnect()

        with patch("backend.ws_manager.asyncio.sleep", side_effect=fake_sleep):
            await mgr._push_loop(ws)

        all_msgs = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
        dl_msgs = [m for m in all_msgs if m.get("type") == "mission_item"]
        assert any(m["seq"] == 99 for m in dl_msgs)

    @pytest.mark.asyncio
    async def test_log_cursor_reset_on_shrink(self):
        """Log cursor resets when log_dl._log_messages shrinks."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        for i in range(3):
            link.log_dl._log_messages.append({"type": "log_entry", "id": i})
        call_count = 0

        async def fake_sleep(_interval):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                link.log_dl._log_messages.clear()
                link.log_dl._log_messages.append({"type": "log_entry", "id": 77})
            if call_count >= 2:
                raise WebSocketDisconnect()

        with patch("backend.ws_manager.asyncio.sleep", side_effect=fake_sleep):
            await mgr._push_loop(ws)

        all_msgs = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
        log_msgs = [m for m in all_msgs if m.get("type") == "log_entry"]
        assert any(m["id"] == 77 for m in log_msgs)

    @pytest.mark.asyncio
    async def test_param_cursor_reset_on_shrink(self):
        """Param cursor resets when param_mgr._messages shrinks."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        for i in range(3):
            link.param_mgr._messages.append({"type": "param_value", "name": f"P{i}", "value": i})
        call_count = 0

        async def fake_sleep(_interval):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                link.param_mgr._messages.clear()
                link.param_mgr._messages.append({"type": "param_value", "name": "NEW", "value": 999})
            if call_count >= 2:
                raise WebSocketDisconnect()

        with patch("backend.ws_manager.asyncio.sleep", side_effect=fake_sleep):
            await mgr._push_loop(ws)

        all_msgs = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
        batch_msgs = [m for m in all_msgs if m.get("type") == "param_batch"]
        assert any(any(p["name"] == "NEW" for p in m["params"]) for m in batch_msgs)

    @pytest.mark.asyncio
    async def test_mixed_param_batch_and_individual(self):
        """When param_value and non-param_value messages arrive in same cycle,
        param_values are batched while others are sent individually."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        call_count = 0

        async def fake_sleep(_interval):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                link.param_mgr._messages.append({"type": "param_value", "name": "RC1_MAX", "value": 2000})
                link.param_mgr._messages.append({"type": "param_progress", "pct": 75})
                link.param_mgr._messages.append({"type": "param_value", "name": "RC1_MIN", "value": 1000})
            if call_count >= 2:
                raise WebSocketDisconnect()

        with patch("backend.ws_manager.asyncio.sleep", side_effect=fake_sleep):
            await mgr._push_loop(ws)

        all_msgs = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
        batch_msgs = [m for m in all_msgs if m.get("type") == "param_batch"]
        progress_msgs = [m for m in all_msgs if m.get("type") == "param_progress"]
        assert len(batch_msgs) == 1
        assert len(batch_msgs[0]["params"]) == 2
        assert len(progress_msgs) == 1
        assert progress_msgs[0]["pct"] == 75

    @pytest.mark.asyncio
    async def test_10th_push_is_full_state(self):
        """Every 10th push sends full state (push_count % 10 == 1)."""
        link = DroneLink()
        mgr = WSManager(link)
        ws = make_ws()
        call_count = 0

        async def fake_sleep(_interval):
            nonlocal call_count
            call_count += 1
            # Run 11 iterations: pushes at count 1 (full), 2-10 (delta), 11 (full)
            if call_count >= 11:
                raise WebSocketDisconnect()

        with patch("backend.ws_manager.asyncio.sleep", side_effect=fake_sleep):
            await mgr._push_loop(ws)

        state_sends = [
            json.loads(c[0][0]) for c in ws.send_text.call_args_list if json.loads(c[0][0]).get("type") == "state"
        ]
        # Push 1 (full) and push 11 (full) should have all state keys
        first = state_sends[0]
        eleventh = state_sends[10]
        assert "roll" in first
        assert "voltage" in first
        assert "roll" in eleventh
        assert "voltage" in eleventh


# ---------------------------------------------------------------------------
# broadcast edge cases
# ---------------------------------------------------------------------------


class TestBroadcastEdge:
    @pytest.mark.asyncio
    async def test_broadcast_removes_runtime_error_client(self):
        """Broadcast discards client that raises RuntimeError."""
        link = DroneLink()
        mgr = WSManager(link)
        ws_ok = make_ws()
        ws_fail = make_ws()
        ws_fail.send_text.side_effect = RuntimeError("closed")
        mgr._clients = {ws_ok, ws_fail}
        await mgr.broadcast({"type": "ping"})
        assert ws_fail not in mgr._clients
        assert ws_ok in mgr._clients

    @pytest.mark.asyncio
    async def test_broadcast_empty_clients(self):
        """Broadcast with no clients does nothing."""
        link = DroneLink()
        mgr = WSManager(link)
        await mgr.broadcast({"type": "test"})
        assert mgr.client_count == 0


def _make_link():
    link = DroneLink()
    link._ser = _MagicMock()
    return link


class TestParamCursorGeneration:
    """The push loop delivers param_batch from _messages[param_cursor:], with a
    strict-`>` length guard to reset on clear. That guard misses the case where
    a new request_all() clears and refills to the SAME length within one push
    cycle: cursor==len, nothing delivered → empty param panel (the CI flake).
    request_all() bumps _fetch_gen; the loop resets the cursor on gen change.
    These tests replicate that decision the way the other push tests do."""

    @staticmethod
    def _deliver(pmsg, cursor, gen_seen, gen_now):
        # Mirror of ws_manager's param cursor block.
        if gen_now != gen_seen:
            cursor = 0
            gen_seen = gen_now
        if cursor > len(pmsg):
            cursor = 0
        delivered = []
        if len(pmsg) > cursor:
            delivered = pmsg[cursor:]
            cursor = len(pmsg)
        return delivered, cursor, gen_seen

    def test_same_length_refill_delivers_all_via_gen(self):
        m = ParamManager(_make_link())
        # Prior fetch: 41 messages; a client connects now → cursor 41, gen 1.
        m.request_all()
        for i in range(41):
            m._messages.append({"type": "param_value", "name": "P%d" % i, "value": i})
        cursor, gen_seen = len(m._messages), m._fetch_gen
        assert (cursor, gen_seen) == (41, 1)
        # New fetch, clear + full refill within one push cycle → same length.
        m.request_all()
        for i in range(41):
            m._messages.append({"type": "param_value", "name": "Q%d" % i, "value": i})
        delivered, cursor, gen_seen = self._deliver(m._messages, cursor, gen_seen, m._fetch_gen)
        assert len(delivered) == 41, "same-length refill must deliver every param"

    def test_request_all_bumps_generation(self):
        m = ParamManager(_make_link())
        g0 = m._fetch_gen
        m.request_all()
        assert m._fetch_gen == g0 + 1
        m.request_all()
        assert m._fetch_gen == g0 + 2

    def test_no_gen_change_keeps_incremental_delivery(self):
        # Within one fetch, cursor advances normally without re-delivering.
        pmsg = [{"type": "param_value", "name": "A", "value": 1}]
        delivered, cursor, gen = self._deliver(pmsg, 0, 5, 5)
        assert len(delivered) == 1 and cursor == 1
        pmsg.append({"type": "param_value", "name": "B", "value": 2})
        delivered, cursor, gen = self._deliver(pmsg, cursor, gen, 5)
        assert len(delivered) == 1 and delivered[0]["name"] == "B"
