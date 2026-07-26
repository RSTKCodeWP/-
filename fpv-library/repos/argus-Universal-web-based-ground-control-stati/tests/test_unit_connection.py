"""Tests for backend/connection.py — transport layer parsing and construction."""

from unittest.mock import MagicMock, patch

import pytest

from backend.connection import TcpWrapper, UdpWrapper, open_port


class TestOpenPortParsing:
    def test_tcp_returns_tcp_wrapper(self):
        mock_sock = MagicMock()
        with patch("backend.connection.socket.socket", return_value=mock_sock):
            result = open_port("tcp:localhost:5770", 57600)
        assert isinstance(result, TcpWrapper)
        mock_sock.connect.assert_called_once_with(("localhost", 5770))

    def test_tcp_custom_host_port(self):
        mock_sock = MagicMock()
        with patch("backend.connection.socket.socket", return_value=mock_sock):
            result = open_port("tcp:192.168.1.100:14550", 57600)
        assert isinstance(result, TcpWrapper)
        mock_sock.connect.assert_called_once_with(("192.168.1.100", 14550))

    def test_udp_with_port_only(self):
        mock_sock = MagicMock()
        with patch("backend.connection.socket.socket", return_value=mock_sock):
            result = open_port("udp:14550", 57600)
        assert isinstance(result, UdpWrapper)

    def test_udp_with_host_and_port(self):
        mock_sock = MagicMock()
        with patch("backend.connection.socket.socket", return_value=mock_sock):
            result = open_port("udp:0.0.0.0:14550", 57600)
        assert isinstance(result, UdpWrapper)

    def test_serial_fallback(self):
        mock_serial = MagicMock()
        with patch("serial.Serial", return_value=mock_serial):
            result = open_port("/dev/ttyUSB0", 115200)
        assert result is mock_serial


class TestTcpWrapper:
    def test_read_returns_bytes(self):
        mock_sock = MagicMock()
        mock_sock.recv.return_value = b"\xfe\x09"
        wrapper = TcpWrapper(mock_sock)
        assert wrapper.read(1024) == b"\xfe\x09"

    def test_read_timeout_returns_empty(self):
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = TimeoutError
        wrapper = TcpWrapper(mock_sock)
        assert wrapper.read(1024) == b""

    def test_write_calls_sendall(self):
        mock_sock = MagicMock()
        wrapper = TcpWrapper(mock_sock)
        wrapper.write(b"\x01\x02")
        mock_sock.sendall.assert_called_once_with(b"\x01\x02")

    def test_close(self):
        mock_sock = MagicMock()
        wrapper = TcpWrapper(mock_sock)
        wrapper.close()
        mock_sock.close.assert_called_once()

    def test_read_os_error_returns_empty(self):
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = OSError("connection reset")
        wrapper = TcpWrapper(mock_sock)
        assert wrapper.read(1024) == b""


class TestUdpWrapper:
    def _make_wrapper(self):
        mock_sock = MagicMock()
        with patch("backend.connection.socket.socket", return_value=mock_sock):
            wrapper = UdpWrapper(14550)
        return wrapper, mock_sock

    def test_read_sets_remote_on_first_packet(self):
        wrapper, mock_sock = self._make_wrapper()
        mock_sock.recvfrom.return_value = (b"\xfd\x09", ("192.168.1.10", 5760))
        data = wrapper.read(1024)
        assert data == b"\xfd\x09"
        assert wrapper._remote == ("192.168.1.10", 5760)

    def test_read_same_peer_updates_last_seen(self):
        wrapper, mock_sock = self._make_wrapper()
        wrapper._remote = ("192.168.1.10", 5760)
        wrapper._remote_last_seen = 100.0
        mock_sock.recvfrom.return_value = (b"\xfd", ("192.168.1.10", 5760))
        with patch("time.monotonic", return_value=200.0):
            data = wrapper.read(1024)
        assert data == b"\xfd"
        assert wrapper._remote_last_seen == 200.0

    def test_read_different_peer_while_active_drops(self):
        wrapper, mock_sock = self._make_wrapper()
        wrapper._remote = ("192.168.1.10", 5760)
        wrapper._remote_last_seen = 100.0
        mock_sock.recvfrom.return_value = (b"\xfd", ("10.0.0.1", 9999))
        with patch("time.monotonic", return_value=105.0):
            data = wrapper.read(1024)
        assert data == b""
        assert wrapper._remote == ("192.168.1.10", 5760)

    def test_read_different_peer_after_guard_timeout_accepts(self):
        wrapper, mock_sock = self._make_wrapper()
        wrapper._remote = ("192.168.1.10", 5760)
        wrapper._remote_last_seen = 100.0
        mock_sock.recvfrom.return_value = (b"\xfd\x01", ("10.0.0.2", 8888))
        with patch("time.monotonic", return_value=200.0):
            data = wrapper.read(1024)
        assert data == b"\xfd\x01"
        assert wrapper._remote == ("10.0.0.2", 8888)

    def test_write_sends_to_remote(self):
        wrapper, mock_sock = self._make_wrapper()
        wrapper._remote = ("192.168.1.10", 5760)
        wrapper.write(b"\x01\x02\x03")
        mock_sock.sendto.assert_called_once_with(b"\x01\x02\x03", ("192.168.1.10", 5760))

    def test_write_no_remote_does_nothing(self):
        wrapper, mock_sock = self._make_wrapper()
        assert wrapper._remote is None
        wrapper.write(b"\x01\x02")
        mock_sock.sendto.assert_not_called()

    def test_write_os_error_swallowed(self):
        wrapper, mock_sock = self._make_wrapper()
        wrapper._remote = ("192.168.1.10", 5760)
        mock_sock.sendto.side_effect = OSError("network unreachable")
        wrapper.write(b"\x01")

    def test_read_timeout_returns_empty(self):
        wrapper, mock_sock = self._make_wrapper()
        mock_sock.recvfrom.side_effect = TimeoutError
        assert wrapper.read(1024) == b""

    def test_read_os_error_returns_empty(self):
        wrapper, mock_sock = self._make_wrapper()
        mock_sock.recvfrom.side_effect = OSError("closed")
        assert wrapper.read(1024) == b""

    def test_close(self):
        wrapper, mock_sock = self._make_wrapper()
        wrapper.close()
        mock_sock.close.assert_called_once()

    def test_bind_called_on_init(self):
        mock_sock = MagicMock()
        with patch("backend.connection.socket.socket", return_value=mock_sock):
            UdpWrapper(14550, "0.0.0.0")
        mock_sock.bind.assert_called_once_with(("0.0.0.0", 14550))

    def test_udp_socket_closed_when_bind_fails(self):
        """Socket must be closed if bind() raises so the fd is not leaked."""
        mock_sock = MagicMock()
        mock_sock.bind.side_effect = OSError("address in use")
        with patch("backend.connection.socket.socket", return_value=mock_sock), pytest.raises(OSError):
            UdpWrapper(14550)
        mock_sock.close.assert_called_once()


class TestTcpSocketCleanup:
    def test_tcp_socket_closed_when_connect_fails(self):
        """Socket must be closed if connect() raises so the fd is not leaked."""
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = OSError("connection refused")
        with patch("backend.connection.socket.socket", return_value=mock_sock), pytest.raises(OSError):
            open_port("tcp:127.0.0.1:5770", 57600)
        mock_sock.close.assert_called_once()
