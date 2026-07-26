"""Tests for backend/commands/_ntrip.py — additional coverage for uncovered paths."""

import socket
import threading
from unittest.mock import MagicMock, patch

from backend.commands._ntrip import _inject_chunk, _ntrip_loop, cmd_ntrip_start, cmd_ntrip_stop
from backend.drone_link import DroneLink


def make_link():
    link = DroneLink()
    link._ser = MagicMock()
    link.connected = True
    link.vehicle.sysid = 1
    return link


class TestInjectChunk:
    def test_first_flag(self):
        link = make_link()
        _inject_chunk(link, b"\xd3" * 10, is_first=True, is_last=False)
        assert link._ser.write.called

    def test_last_flag(self):
        link = make_link()
        _inject_chunk(link, b"\xd3" * 10, is_first=False, is_last=True)
        assert link._ser.write.called

    def test_both_flags(self):
        link = make_link()
        _inject_chunk(link, b"\xd3" * 10, is_first=True, is_last=True)
        assert link._ser.write.called


class TestNtripLoopEdgeCases:
    def test_header_too_large(self, monkeypatch):
        sock = MagicMock()
        sock.recv.return_value = b"X" * 512
        monkeypatch.setattr(socket, "create_connection", lambda *a, **kw: sock)

        link = make_link()
        stop = threading.Event()
        t = threading.Thread(target=_ntrip_loop, args=(link, "h", 1, "M", "u", "p", stop), daemon=True)
        t.start()
        t.join(timeout=5)
        assert not t.is_alive()
        event_types = [e["event_type"] for e in link.events]
        assert "ntrip_error" in event_types

    def test_connection_closed_during_header(self, monkeypatch):
        sock = MagicMock()
        sock.recv.return_value = b""
        monkeypatch.setattr(socket, "create_connection", lambda *a, **kw: sock)

        link = make_link()
        stop = threading.Event()
        t = threading.Thread(target=_ntrip_loop, args=(link, "h", 1, "M", "u", "p", stop), daemon=True)
        t.start()
        t.join(timeout=3)
        event_types = [e["event_type"] for e in link.events]
        assert "ntrip_error" in event_types

    def test_header_timeout(self, monkeypatch):
        sock = MagicMock()
        sock.recv.side_effect = TimeoutError("read timeout")
        monkeypatch.setattr(socket, "create_connection", lambda *a, **kw: sock)

        link = make_link()
        stop = threading.Event()
        t = threading.Thread(target=_ntrip_loop, args=(link, "h", 1, "M", "u", "p", stop), daemon=True)
        t.start()
        t.join(timeout=3)
        event_types = [e["event_type"] for e in link.events]
        assert "ntrip_error" in event_types

    def test_http_v2_200_accepted(self, monkeypatch):
        sock = MagicMock()
        calls = {"n": 0}

        def fake_recv(_n):
            calls["n"] += 1
            if calls["n"] == 1:
                return b"HTTP/1.1 200 OK\r\nContent-Type: gnss\r\n\r\n"
            if calls["n"] <= 3:
                return b"\xd3" * 50
            return b""

        sock.recv.side_effect = fake_recv
        monkeypatch.setattr(socket, "create_connection", lambda *a, **kw: sock)

        link = make_link()
        stop = threading.Event()
        t = threading.Thread(target=_ntrip_loop, args=(link, "h", 1, "M", "u", "p", stop), daemon=True)
        t.start()
        t.join(timeout=3)
        event_types = [e["event_type"] for e in link.events]
        assert "ntrip_connected" in event_types

    def test_lf_only_header_separator(self, monkeypatch):
        sock = MagicMock()
        calls = {"n": 0}

        def fake_recv(_n):
            calls["n"] += 1
            if calls["n"] == 1:
                return b"ICY 200 OK\n\n"
            return b""

        sock.recv.side_effect = fake_recv
        monkeypatch.setattr(socket, "create_connection", lambda *a, **kw: sock)

        link = make_link()
        stop = threading.Event()
        t = threading.Thread(target=_ntrip_loop, args=(link, "h", 1, "M", "u", "p", stop), daemon=True)
        t.start()
        t.join(timeout=3)
        event_types = [e["event_type"] for e in link.events]
        assert "ntrip_connected" in event_types

    def test_recv_timeout_continues(self, monkeypatch):
        """recv timeout during stream should not terminate — only EOF does."""
        sock = MagicMock()
        calls = {"n": 0}

        def fake_recv(_n):
            calls["n"] += 1
            if calls["n"] == 1:
                return b"ICY 200 OK\r\n\r\n"
            if calls["n"] <= 3:
                raise TimeoutError()
            if calls["n"] == 4:
                return b"\xd3" * 10
            return b""

        sock.recv.side_effect = fake_recv
        monkeypatch.setattr(socket, "create_connection", lambda *a, **kw: sock)

        link = make_link()
        stop = threading.Event()
        t = threading.Thread(target=_ntrip_loop, args=(link, "h", 1, "M", "u", "p", stop), daemon=True)
        t.start()
        t.join(timeout=3)
        assert "ntrip_connected" in [e["event_type"] for e in link.events]
        assert link._ser.write.called


class TestCmdNtripStartFullPath:
    def test_ssrf_guard_rejects_loopback(self):
        link = make_link()
        with patch(
            "backend.commands._ntrip.socket.getaddrinfo",
            return_value=[
                (2, 1, 6, "", ("127.0.0.1", 2101)),
            ],
        ):
            r = cmd_ntrip_start(
                link,
                None,
                {
                    "host": "evil.com",
                    "port": 2101,
                    "mountpoint": "M",
                    "username": "u",
                    "password": "p",
                },
            )
        assert r and r["ok"] is False
        assert r["error"]  # non-empty error message (locale-dependent)

    def test_dns_failure_rejected(self):
        link = make_link()
        with patch("backend.commands._ntrip.socket.getaddrinfo", side_effect=socket.gaierror("nope")):
            r = cmd_ntrip_start(
                link,
                None,
                {
                    "host": "nonexistent.example",
                    "port": 2101,
                    "mountpoint": "M",
                },
            )
        assert r and r["ok"] is False
        assert r["error"]  # non-empty error message (locale-dependent)

    def test_already_running_rejected(self):
        link = make_link()
        fake_thread = MagicMock()
        fake_thread.is_alive.return_value = True
        link.ntrip_thread = fake_thread
        with patch(
            "backend.commands._ntrip.socket.getaddrinfo",
            return_value=[
                (2, 1, 6, "", ("93.184.216.34", 2101)),
            ],
        ):
            r = cmd_ntrip_start(
                link,
                None,
                {
                    "host": "rtk.example.com",
                    "port": 2101,
                    "mountpoint": "M",
                },
            )
        assert r and r["ok"] is False
        assert r["error"]  # non-empty error (locale-dependent)

    def test_successful_start_spawns_thread(self):
        link = make_link()
        with (
            patch(
                "backend.commands._ntrip.socket.getaddrinfo",
                return_value=[
                    (2, 1, 6, "", ("93.184.216.34", 2101)),
                ],
            ),
            patch("backend.commands._ntrip.socket.create_connection", side_effect=OSError("refused")),
        ):
            cmd_ntrip_start(
                link,
                None,
                {
                    "host": "rtk.example.com",
                    "port": 2101,
                    "mountpoint": "M",
                    "username": "u",
                    "password": "p",
                },
            )
        # Thread was spawned (even though it will fail immediately)
        import time

        time.sleep(0.5)
        assert link.ntrip_thread is None  # thread exited after connection error

    def test_crlf_in_host_rejected(self):
        """CRLF in host would inject an extra HTTP header — must be rejected."""
        link = make_link()
        r = cmd_ntrip_start(
            link,
            None,
            {
                "host": "rtk.example.com\r\nX-Evil: injected",
                "port": 2101,
                "mountpoint": "M",
                "username": "u",
                "password": "p",
            },
        )
        assert r and r["ok"] is False
        assert r["error"]

    def test_crlf_in_credentials_rejected(self):
        link = make_link()
        r = cmd_ntrip_start(
            link,
            None,
            {
                "host": "rtk.example.com",
                "port": 2101,
                "mountpoint": "M",
                "username": "admin\r\n",
                "password": "pass",
            },
        )
        assert r and r["ok"] is False
        assert r["error"]  # non-empty error (locale-dependent)


class TestCmdNtripStop:
    def test_stop_sets_event(self):
        link = make_link()
        stop_event = threading.Event()
        link.ntrip_stop = stop_event
        cmd_ntrip_stop(link, None, {})
        assert stop_event.is_set()

    def test_stop_noop_when_none(self):
        link = make_link()
        cmd_ntrip_stop(link, None, {})  # must not raise
