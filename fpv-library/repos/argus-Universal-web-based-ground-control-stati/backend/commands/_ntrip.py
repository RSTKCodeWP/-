"""NTRIP client — fetches RTCM corrections from a caster, injects to FC
via GPS_RTCM_DATA (msg 233). Runs in a daemon thread per DroneLink.

NTRIP v1 protocol (RFC-style, simplified):
  client -> caster:  GET /<mountpoint> HTTP/1.0 + Basic auth headers
  caster -> client:  "ICY 200 OK\\r\\n\\r\\n" then raw RTCM 3.x byte stream
NTRIP v2 uses standard HTTP/1.1; we accept both response forms.

We do NOT parse RTCM frames here — the FC's AP_GPS layer handles framing.
Just relay bytes in 180-byte chunks to GPS_RTCM_DATA. See cmd_inject_rtcm
in _hardware.py for the same wire format used by the manual paste path.
"""

from __future__ import annotations

import base64
import ipaddress
import socket
import struct
import threading
from typing import TYPE_CHECKING

from ..crc_extras import CRC_EXTRA
from ..locale_text import lt
from ..log import logger
from ..pllink_proto import bm

if TYPE_CHECKING:
    from ..drone_link import DroneLink

# GPS_RTCM_DATA payload data field capacity (the message reserves 180 bytes).
_RTCM_CHUNK = 180

# Socket read budget per recv. Larger == fewer syscalls but worse stop-event
# latency, since recv is the blocking point.
_RECV_BUF = 1024

# Header read cap — NTRIP responses are tiny; >4KB means a misbehaving caster.
_MAX_HEADER = 4096


def _inject_chunk(link, chunk: bytes, *, is_first: bool, is_last: bool) -> None:
    """Send one RTCM chunk via GPS_RTCM_DATA. Mirrors cmd_inject_rtcm bit flags.

    GPS_RTCM_DATA payload layout (msg 233, CRC_EXTRA=35):
      uint8 flags  -- bit0: fragmented stream (always 1 for our injections)
                      bit2: first fragment of an RTCM message (we set)
                      bit3: last fragment of an RTCM message (we set)
      uint8 len    -- valid data length in this fragment (≤180)
      uint8[180]   -- payload bytes, zero-padded to 180
    AP_GPS_MAV.cpp reassembles fragments by the bit0=0/1 distinction; since
    we always relay opaque chunks (not parsed RTCM frames), every fragment is
    marked first+last and the FC treats it as a complete fragment to forward.
    """
    flags = 0x01
    if is_first:
        flags |= 0x04
    if is_last:
        flags |= 0x08
    p = struct.pack("<BB", flags, len(chunk))
    p += chunk + b"\x00" * (_RTCM_CHUNK - len(chunk))
    link.send(bm(233, p, link.sq, CRC_EXTRA[233]))


def _ntrip_loop(
    link: DroneLink, host: str, port: int, mountpoint: str, username: str, password: str, stop_event: threading.Event
) -> None:
    """Connect to caster, validate response, stream RTCM to FC until stop."""
    sock: socket.socket | None = None
    try:
        sock = socket.create_connection((host, port), timeout=10)
        # Short recv timeout so the stop_event check runs every 2s even on
        # an idle stream. RTCM correctional data is typically 1-3 Hz so the
        # timeouts are expected and benign.
        sock.settimeout(2.0)

        auth = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        request = (
            f"GET /{mountpoint} HTTP/1.0\r\n"
            f"Host: {host}\r\n"
            f"User-Agent: NTRIP Argus/3.4.0\r\n"
            f"Authorization: Basic {auth}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode("ascii")
        sock.sendall(request)

        # Read headers until end-of-header marker (\r\n\r\n or \n\n).
        header = b""
        while True:
            try:
                chunk = sock.recv(512)
            except TimeoutError as e:
                raise RuntimeError("header read timeout") from e
            if not chunk:
                raise RuntimeError("connection closed during header")
            header += chunk
            if b"\r\n\r\n" in header or b"\n\n" in header:
                break
            if len(header) > _MAX_HEADER:
                raise RuntimeError("header too large")

        # Validate first line. Accept "ICY 200 OK" (NTRIP v1) or "HTTP/1.x 200" (v2).
        first_line = header.split(b"\n", 1)[0].rstrip(b"\r")
        ok = first_line.startswith(b"ICY 200") or (first_line.startswith(b"HTTP/") and b" 200" in first_line)
        if not ok:
            preview = first_line[:80].decode("utf-8", errors="replace")
            raise RuntimeError(f"bad response: {preview}")

        # Anything past the header is initial RTCM body bytes.
        sep = header.find(b"\r\n\r\n")
        if sep != -1:
            buf = header[sep + 4 :]
        else:
            sep = header.find(b"\n\n")
            buf = header[sep + 2 :] if sep != -1 else b""

        link.add_event(lt("ntrip_connected", link.locale) % mountpoint, "ntrip_connected")

        # Main stream loop. recv times out every 2s; stop_event check is cheap.
        while not stop_event.is_set():
            try:
                chunk = sock.recv(_RECV_BUF)
            except TimeoutError:
                continue
            if not chunk:
                break  # caster closed cleanly
            buf += chunk
            while len(buf) >= _RTCM_CHUNK:
                _inject_chunk(link, buf[:_RTCM_CHUNK], is_first=True, is_last=True)
                buf = buf[_RTCM_CHUNK:]
        # Flush trailing partial chunk on graceful exit.
        if buf and not stop_event.is_set():
            _inject_chunk(link, buf, is_first=True, is_last=True)

    except (OSError, RuntimeError) as e:
        # OSError covers DNS failure, ECONNREFUSED, etc. We deliberately do
        # NOT include credentials in error messages — RuntimeError messages
        # we raise above never carry them, and OSError str() doesn't either.
        logger.warning("ntrip thread error: %s", e)
        try:
            link.add_event(lt("ntrip_error", link.locale) % str(e)[:60], "ntrip_error")
        except Exception:
            pass
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        with link._state_lock:
            link.ntrip_thread = None
            link.ntrip_stop = None
        try:
            link.add_event(lt("ntrip_disconnected", link.locale), "ntrip_disconnected")
        except Exception:
            pass


def cmd_ntrip_start(link: DroneLink, param, data: dict):
    """Connect to an NTRIP caster and forward RTCM corrections to the FC.

    Required fields in `data`: host, port, mountpoint, username, password.
    Spawns a single background thread; rejects if one is already running.
    """
    host = str(data.get("host", "")).strip()
    if not host or len(host) > 255:
        return {"ok": False, "error": lt("err_ntrip_host", link.locale)}
    try:
        port = int(data.get("port", 2101))
    except (TypeError, ValueError):
        return {"ok": False, "error": lt("err_ntrip_port_type", link.locale)}
    if not 1 <= port <= 65535:
        return {"ok": False, "error": lt("err_ntrip_port_range", link.locale)}
    mountpoint = str(data.get("mountpoint", "")).strip()
    if not mountpoint or len(mountpoint) > 100:
        return {"ok": False, "error": lt("err_ntrip_mount", link.locale)}
    # Reject CR/LF in any field that goes into the HTTP request — prevents
    # header injection via crafted host/mountpoint/credentials.
    if any(c in host for c in ("\r", "\n")):
        return {"ok": False, "error": lt("err_ntrip_host", link.locale)}
    if any(c in mountpoint for c in ("\r", "\n")):
        return {"ok": False, "error": lt("err_ntrip_mount_chars", link.locale)}
    username = str(data.get("username", ""))[:128]
    password = str(data.get("password", ""))[:128]
    if any(c in username + password for c in ("\r", "\n")):
        return {"ok": False, "error": lt("err_ntrip_cred_chars", link.locale)}

    try:
        addrs = socket.getaddrinfo(host, port)
    except socket.gaierror:
        return {"ok": False, "error": lt("err_ntrip_resolve", link.locale)}
    for _fam, *_rest, sockaddr in addrs:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return {"ok": False, "error": lt("err_ntrip_private", link.locale)}

    with link._state_lock:
        existing = link.ntrip_thread
    if existing is not None and existing.is_alive():
        return {"ok": False, "error": lt("err_ntrip_running", link.locale)}

    stop_event = threading.Event()
    thread = threading.Thread(
        target=_ntrip_loop,
        args=(link, host, port, mountpoint, username, password, stop_event),
        daemon=True,
        name="ntrip-client",
    )
    with link._state_lock:
        link.ntrip_thread = thread
        link.ntrip_stop = stop_event
    thread.start()


def cmd_ntrip_stop(link: DroneLink, param, data: dict):
    """Signal the NTRIP thread to exit. Idempotent if nothing is running.

    Thread exit takes up to one recv timeout (2s) — the socket closes inside
    the thread's finally block, and the FC stops receiving RTCM frames.
    """
    with link._state_lock:
        stop = link.ntrip_stop
    if stop is not None:
        stop.set()
