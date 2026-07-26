"""RTSP → MJPEG video proxy for browser display."""

from __future__ import annotations

import asyncio
import ipaddress
import shutil
import subprocess
import threading
from urllib.parse import urlparse

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from .config import cfg

router = APIRouter()

_ALLOWED_SCHEMES = {"rtsp", "rtmp", "http", "https"}


def _is_private_or_special(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local or ip.is_multicast


def _validate_video_url(url: str) -> str | None:
    """Validate video URL. Returns error message or None if valid."""
    if len(url) > cfg.VIDEO_URL_MAX_LEN:
        return "URL too long"
    try:
        parsed = urlparse(url)
    except ValueError:
        return "Malformed URL"
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return "Only rtsp/rtmp/http/https schemes allowed"
    host = parsed.hostname or ""
    if not host:
        return "No hostname in URL"
    # Try IP literal first; if that fails, resolve the hostname via DNS and
    # check the result. Previously a hostname like `internal-server.lan`
    # that resolved to 127.0.0.1 / 169.254.169.254 (AWS metadata) would
    # slip past the IP-literal check entirely.
    try:
        addr = ipaddress.ip_address(host)
        if _is_private_or_special(addr):
            return "Private/loopback addresses not allowed"
        return None
    except ValueError:
        pass
    if host in ("localhost", "localhost.localdomain"):
        return "Private/loopback addresses not allowed"
    import socket as _socket

    try:
        addrs = _socket.getaddrinfo(host, None)
    except _socket.gaierror:
        return "Cannot resolve hostname"
    for _fam, *_rest, sockaddr in addrs:
        try:
            resolved = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if _is_private_or_special(resolved):
            return "Resolves to a private/loopback/reserved address"
    return None


_active_proc: subprocess.Popen | None = None
_proc_lock = threading.Lock()


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


@router.get("/api/video")
async def video_stream(url: str = ""):
    """Proxy RTSP/video stream as MJPEG for browser display."""
    if not url:
        return {"error": "No video URL provided"}
    url_err = _validate_video_url(url)
    if url_err:
        return {"error": f"Invalid video URL: {url_err}"}
    if not _ffmpeg_available():
        return {"error": "ffmpeg not installed on server"}

    with _proc_lock:
        if _active_proc is not None:
            try:
                _active_proc.kill()
                _active_proc.wait(timeout=3)
            except OSError:
                pass

    async def generate():
        global _active_proc  # noqa: PLW0603
        proc = subprocess.Popen(
            [
                "ffmpeg",
                "-rtsp_transport",
                "tcp",
                "-i",
                url,
                "-f",
                "mjpeg",
                "-q:v",
                "5",
                "-r",
                "15",
                "-an",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        with _proc_lock:
            _active_proc = proc
        loop = asyncio.get_event_loop()
        try:
            buf = b""
            # If the upstream isn't MJPEG (e.g. mis-configured URL), the
            # JPEG markers never appear and `buf += chunk` grows forever.
            # Cap at ~8MB and reset to recover.
            _MAX_BUF = 8 * 1024 * 1024
            while True:
                chunk = await loop.run_in_executor(
                    None,
                    proc.stdout.read,
                    4096,  # type: ignore[union-attr]
                )
                if not chunk:
                    break
                buf += chunk
                if len(buf) > _MAX_BUF:
                    # Keep only the trailing 64KB in case a partial header
                    # is in there.
                    buf = buf[-65536:]
                # Extract complete JPEG frames (FF D8 … FF D9).
                while True:
                    start = buf.find(b"\xff\xd8")
                    end = buf.find(b"\xff\xd9", start + 2) if start >= 0 else -1
                    if start >= 0 and end >= 0:
                        frame = buf[start : end + 2]
                        buf = buf[end + 2 :]
                        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
                    else:
                        break
        finally:
            try:
                proc.kill()
            except OSError:
                pass
            proc.wait()
            with _proc_lock:
                if _active_proc is proc:
                    _active_proc = None

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/api/video/stop")
async def video_stop():
    """Stop active video stream."""
    global _active_proc  # noqa: PLW0603
    with _proc_lock:
        if _active_proc is not None:
            try:
                _active_proc.kill()
                _active_proc.wait(timeout=3)
            except OSError:
                pass
            _active_proc = None
    return {"ok": True}


@router.get("/api/video/capabilities")
async def video_capabilities():
    """Report video streaming capabilities."""
    return {
        "mjpeg": _ffmpeg_available(),
        "webrtc": False,
        "protocols": ["rtsp", "rtmp", "http"] if _ffmpeg_available() else [],
    }
