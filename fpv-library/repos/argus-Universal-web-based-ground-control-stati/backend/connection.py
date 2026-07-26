"""Transport wrappers for TCP, UDP, serial, and tlog-replay connections."""

from __future__ import annotations

import socket
import time

from .config import cfg


class TcpWrapper:
    def __init__(self, sock: socket.socket):
        self._sock = sock

    @property
    def in_waiting(self) -> int:
        """Bytes buffered by the kernel, mirroring pyserial's property — the
        link loop uses it to drain bursts (log downloads) in one read instead
        of 1024 B per tick. Best-effort: 0 on platforms without FIONREAD."""
        try:
            import fcntl
            import struct as _struct
            import termios

            buf = fcntl.ioctl(self._sock.fileno(), termios.FIONREAD, b"\x00\x00\x00\x00")
            return _struct.unpack("=I", buf)[0]
        except (ImportError, OSError):
            return 0

    def read(self, n: int) -> bytes:
        try:
            return self._sock.recv(n)
        except (TimeoutError, OSError):
            return b""

    def write(self, data: bytes) -> None:
        self._sock.sendall(data)

    def close(self) -> None:
        self._sock.close()


class UdpWrapper:
    def __init__(self, port: int, host: str = ""):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.settimeout(cfg.UDP_READ_TIMEOUT)
        try:
            self._sock.bind((host or "", port))
        except OSError:
            self._sock.close()
            raise
        self._remote: tuple | None = None
        # Track when we last heard from _remote. If a different sender appears
        # while the current peer has been silent for `_PEER_HIJACK_GUARD`
        # seconds we follow the new peer (legitimate FC IP change). Otherwise
        # the new sender is ignored — an attacker can't inject one packet to
        # divert outbound commands to themselves (auditor finding).
        self._remote_last_seen: float = 0.0
        self._PEER_HIJACK_GUARD: float = 30.0

    def read(self, n: int) -> bytes:
        try:
            import time as _t

            data, addr = self._sock.recvfrom(n)
            now = _t.monotonic()
            if self._remote is None or (
                addr != self._remote and (now - self._remote_last_seen) > self._PEER_HIJACK_GUARD
            ):
                self._remote = addr
            elif addr != self._remote:
                # Same socket, different sender, current peer still active —
                # drop. Either a misdirected packet or an attempted hijack.
                return b""
            self._remote_last_seen = now
            return data
        except (TimeoutError, OSError):
            return b""

    def write(self, data: bytes) -> None:
        if self._remote:
            try:
                self._sock.sendto(data, self._remote)
            except OSError:
                pass

    def close(self) -> None:
        self._sock.close()


class ReplayWrapper:
    """Streams a recorded .tlog back through the normal link loop, paced by
    the recorded timestamps. Lets the full stack (backend parse → WS → UI)
    be driven by a real-FC session with no hardware attached.

    Port syntax: replay:<path>[@<speed>]  e.g. replay:logs/argus_x.tlog@10
    Writes are discarded — commands sent during a replay go nowhere.
    At end-of-log read() returns b"" forever; the link-lost auto-reconnect
    path then reopens the port, which restarts the replay from the top.

    In-log silence gaps are clamped to GAP_CLAMP_WALL wall-seconds: a
    recorded session containing a link outage longer than LINK_LOST_TIMEOUT
    would otherwise trip the auto-reconnect mid-log, restart the replay from
    the top, and loop over the same prefix forever.
    """

    GAP_CLAMP_WALL = 1.0

    def __init__(self, path: str, speed: float = 1.0):
        from .replay import read_tlog

        try:
            # FC frames only — replaying recorded GCS heartbeats would
            # fabricate vehicle state (see backend/replay.py GCS_SYSID).
            self._records = read_tlog(path, include_gcs=False)
        except ValueError as e:
            raise OSError(str(e)) from e
        if not self._records:
            raise OSError("no FC frames in %s" % path)
        self._speed = speed if speed > 0 else 1.0
        self._idx = 0
        self._t0_log = self._records[0][0]
        self._t0_wall = time.monotonic()

    def read(self, n: int) -> bytes:
        if self._idx >= len(self._records):
            time.sleep(0.05)  # EOF — mimic an idle transport, don't busy-spin
            return b""
        elapsed = (time.monotonic() - self._t0_wall) * self._speed
        due = (self._records[self._idx][0] - self._t0_log) / 1e6
        if elapsed < due:
            wall_wait = (due - elapsed) / self._speed
            if wall_wait > self.GAP_CLAMP_WALL:
                # Fast-forward the wall origin through recorded silence so
                # the remaining wait is exactly the clamp (see class doc).
                self._t0_wall -= wall_wait - self.GAP_CLAMP_WALL
                wall_wait = self.GAP_CLAMP_WALL
            time.sleep(min(0.05, wall_wait))
            return b""
        # Batch every frame that is already due (param bursts exceed the
        # one-frame-per-loop-tick rate), capped near n per the read contract.
        out = bytearray()
        while self._idx < len(self._records) and len(out) < n:
            ts, frame = self._records[self._idx]
            if (ts - self._t0_log) / 1e6 > elapsed:
                break
            out += frame
            self._idx += 1
        return bytes(out)

    def write(self, data: bytes) -> None:
        pass

    def close(self) -> None:
        pass


def _parse_replay_port(port: str) -> tuple[str, float]:
    spec = port[len("replay:") :]
    path, sep, speed_s = spec.rpartition("@")
    if sep:
        try:
            return path, float(speed_s)
        except ValueError:
            pass  # '@' was part of the filename, not a speed suffix
    return spec, 1.0


def open_port(port: str, baudrate: int):
    if port.startswith("replay:"):
        path, speed = _parse_replay_port(port)
        return ReplayWrapper(path, speed)
    elif port.startswith("udp:"):
        parts = port[4:].split(":")
        try:
            if len(parts) == 2:
                host, udp_port = parts[0], int(parts[1])
            else:
                host, udp_port = "", int(parts[0])
        except ValueError:
            raise OSError("Invalid UDP port: %s" % port)
        return UdpWrapper(udp_port, host)
    elif port.startswith("tcp:"):
        parts = port[4:].split(":")
        try:
            host, tcp_port = parts[0], int(parts[1])
        except (ValueError, IndexError):
            raise OSError("Invalid TCP address: %s" % port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(cfg.TCP_CONNECT_TIMEOUT)
        try:
            sock.connect((host, tcp_port))
        except OSError:
            sock.close()
            raise
        sock.settimeout(cfg.TCP_READ_TIMEOUT)
        return TcpWrapper(sock)
    else:
        import serial

        s = serial.Serial(port, baudrate, timeout=cfg.SERIAL_READ_TIMEOUT)
        s.reset_input_buffer()
        return s
