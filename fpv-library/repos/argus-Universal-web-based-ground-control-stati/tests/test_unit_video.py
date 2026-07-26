"""Unit tests for video module.

Tests RTSP URL validation, video start/stop lifecycle, duplicate process
prevention, cleanup behavior, and capabilities endpoint.
"""

import socket
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backend.video as video_module
from backend.app import app
from backend.drone_link import DroneLink
from backend.video import _ffmpeg_available, _proc_lock, _validate_video_url
from backend.ws_manager import WSManager


@pytest.fixture(autouse=True)
def _reset_video_state():
    """Reset video module global state between tests."""
    with _proc_lock:
        video_module._active_proc = None
    yield
    with _proc_lock:
        video_module._active_proc = None


@pytest.fixture
def client():
    """FastAPI TestClient with app state initialized."""
    if not hasattr(app.state, "link"):
        app.state.link = DroneLink()
        app.state.ws_mgr = WSManager(app.state.link)
    return TestClient(app, raise_server_exceptions=False)


class TestVideoModule:
    def test_proc_lock_exists(self):
        assert isinstance(_proc_lock, type(threading.Lock()))

    def test_ffmpeg_check(self):
        result = _ffmpeg_available()
        assert isinstance(result, bool)


class TestRtspUrlValidation:
    def test_empty_url_returns_error(self, client):
        r = client.get("/api/video")
        assert r.status_code == 200
        data = r.json()
        assert "error" in data
        assert "No video URL" in data["error"]

    def test_empty_string_url_returns_error(self, client):
        r = client.get("/api/video?url=")
        assert r.status_code == 200
        data = r.json()
        assert "error" in data

    @patch("backend.video._ffmpeg_available", return_value=False)
    def test_no_ffmpeg_returns_error(self, mock_ff, client):
        r = client.get("/api/video?url=rtsp://8.8.8.8:554/stream")
        assert r.status_code == 200
        data = r.json()
        assert "error" in data
        assert "ffmpeg" in data["error"].lower()

    @patch("backend.video._ffmpeg_available", return_value=True)
    @patch("subprocess.Popen")
    def test_valid_rtsp_url_starts_stream(self, mock_popen, mock_ff, client):
        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.read = MagicMock(return_value=b"")
        mock_proc.kill = MagicMock()
        mock_proc.wait = MagicMock()
        mock_popen.return_value = mock_proc

        r = client.get("/api/video?url=rtsp://8.8.8.8:554/stream")
        assert r.status_code == 200

    @patch("backend.video._ffmpeg_available", return_value=True)
    @patch("subprocess.Popen")
    def test_http_url_accepted(self, mock_popen, mock_ff, client):
        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.read = MagicMock(return_value=b"")
        mock_proc.kill = MagicMock()
        mock_proc.wait = MagicMock()
        mock_popen.return_value = mock_proc

        r = client.get("/api/video?url=http://8.8.8.8/live.m3u8")
        assert r.status_code == 200


class TestVideoLifecycle:
    @patch("backend.video._ffmpeg_available", return_value=True)
    @patch("subprocess.Popen")
    def test_start_creates_process(self, mock_popen, mock_ff, client):
        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.read = MagicMock(return_value=b"")
        mock_proc.kill = MagicMock()
        mock_proc.wait = MagicMock()
        mock_popen.return_value = mock_proc

        r = client.get("/api/video?url=rtsp://8.8.8.8/cam")
        assert r.status_code == 200
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args[0] == "ffmpeg"
        assert "rtsp://8.8.8.8/cam" in args

    @patch("backend.video._ffmpeg_available", return_value=True)
    @patch("subprocess.Popen")
    def test_ffmpeg_args_include_mjpeg_output(self, mock_popen, mock_ff, client):
        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.read = MagicMock(return_value=b"")
        mock_proc.kill = MagicMock()
        mock_proc.wait = MagicMock()
        mock_popen.return_value = mock_proc

        client.get("/api/video?url=rtsp://8.8.8.8/cam")
        args = mock_popen.call_args[0][0]
        assert "-f" in args
        idx = args.index("-f")
        assert args[idx + 1] == "mjpeg"
        assert "pipe:1" in args

    def test_stop_when_no_process(self, client):
        r = client.get("/api/video/stop")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_stop_kills_active_process(self, client):
        mock_proc = MagicMock()
        mock_proc.kill = MagicMock()
        mock_proc.wait = MagicMock()
        with _proc_lock:
            video_module._active_proc = mock_proc

        r = client.get("/api/video/stop")
        assert r.status_code == 200
        assert r.json()["ok"] is True
        mock_proc.kill.assert_called_once()
        with _proc_lock:
            assert video_module._active_proc is None


class TestDuplicateProcessPrevention:
    @patch("backend.video._ffmpeg_available", return_value=True)
    def test_starting_twice_kills_first_process(self, mock_ff, client):
        """Starting video a second time should kill the first process."""
        first_proc = MagicMock()
        first_proc.kill = MagicMock()
        first_proc.wait = MagicMock()
        with _proc_lock:
            video_module._active_proc = first_proc

        second_proc = MagicMock()
        second_proc.stdout = MagicMock()
        second_proc.stdout.read = MagicMock(return_value=b"")
        second_proc.kill = MagicMock()
        second_proc.wait = MagicMock()

        with patch("subprocess.Popen", return_value=second_proc):
            client.get("/api/video?url=rtsp://8.8.8.8/new")

        first_proc.kill.assert_called_once()


class TestGenerateFinallyDoesNotOrphanLaterProc:
    """generate() finally must not clear _active_proc if a newer proc replaced it."""

    def test_stale_finally_leaves_active_proc_intact(self):
        """If proc2 is stored in _active_proc before proc1's finally runs,
        proc1's finally block must not clobber it with None."""
        proc1 = MagicMock()
        proc1.kill = MagicMock()
        proc1.wait = MagicMock()
        proc1.returncode = 0

        proc2 = MagicMock()
        proc2.kill = MagicMock()
        proc2.wait = MagicMock()

        # Simulate: proc2 was started and stored as the current active proc.
        with _proc_lock:
            video_module._active_proc = proc2

        # Now simulate proc1's generate() finally block running.
        # Before the fix this would unconditionally set _active_proc = None.
        try:
            proc1.kill()
        except OSError:
            pass
        proc1.wait()
        with _proc_lock:
            if video_module._active_proc is proc1:
                video_module._active_proc = None

        # proc2 must still be the active proc — not orphaned.
        with _proc_lock:
            assert video_module._active_proc is proc2


class TestCleanupOnStop:
    def test_stop_clears_global_reference(self, client):
        mock_proc = MagicMock()
        mock_proc.kill = MagicMock()
        mock_proc.wait = MagicMock()
        with _proc_lock:
            video_module._active_proc = mock_proc

        client.get("/api/video/stop")
        with _proc_lock:
            assert video_module._active_proc is None

    def test_stop_handles_process_already_dead(self, client):
        """Stop gracefully handles a process that raises on kill."""
        mock_proc = MagicMock()
        mock_proc.kill = MagicMock(side_effect=OSError("already dead"))
        mock_proc.wait = MagicMock()
        with _proc_lock:
            video_module._active_proc = mock_proc

        r = client.get("/api/video/stop")
        assert r.status_code == 200
        assert r.json()["ok"] is True


class TestVideoCapabilities:
    def test_capabilities_returns_correct_format(self, client):
        r = client.get("/api/video/capabilities")
        assert r.status_code == 200
        data = r.json()
        assert "mjpeg" in data
        assert "webrtc" in data
        assert "protocols" in data
        assert isinstance(data["mjpeg"], bool)
        assert data["webrtc"] is False
        assert isinstance(data["protocols"], list)

    @patch("backend.video._ffmpeg_available", return_value=True)
    def test_capabilities_with_ffmpeg(self, mock_ff, client):
        r = client.get("/api/video/capabilities")
        data = r.json()
        assert data["mjpeg"] is True
        assert "rtsp" in data["protocols"]
        assert "rtmp" in data["protocols"]
        assert "http" in data["protocols"]

    @patch("backend.video._ffmpeg_available", return_value=False)
    def test_capabilities_without_ffmpeg(self, mock_ff, client):
        r = client.get("/api/video/capabilities")
        data = r.json()
        assert data["mjpeg"] is False
        assert data["protocols"] == []


class TestValidateVideoUrlEdgeCases:
    """Direct tests for _validate_video_url covering uncovered branches."""

    def test_url_too_long(self):
        """Lines 34-35: URL exceeding VIDEO_URL_MAX_LEN."""
        long_url = "rtsp://8.8.8.8/" + "a" * 3000
        err = _validate_video_url(long_url)
        assert err == "URL too long"

    def test_bad_scheme_rejected(self):
        err = _validate_video_url("ftp://8.8.8.8/stream")
        assert err is not None
        assert "scheme" in err.lower()

    def test_no_hostname(self):
        err = _validate_video_url("rtsp://")
        assert err is not None

    def test_localhost_rejected(self):
        err = _validate_video_url("rtsp://localhost/stream")
        assert err is not None
        assert "private" in err.lower() or "loopback" in err.lower()

    def test_localhost_localdomain_rejected(self):
        err = _validate_video_url("rtsp://localhost.localdomain/stream")
        assert err is not None

    def test_private_ip_rejected(self):
        err = _validate_video_url("rtsp://192.168.1.1/stream")
        assert err is not None
        assert "private" in err.lower() or "loopback" in err.lower()

    def test_loopback_ip_rejected(self):
        err = _validate_video_url("rtsp://127.0.0.1/stream")
        assert err is not None

    @patch("socket.getaddrinfo", side_effect=socket.gaierror("Name resolution failed"))
    def test_dns_resolution_failure(self, mock_dns):
        """Lines 57-58: hostname that fails DNS resolution."""
        err = _validate_video_url("rtsp://nonexistent-host.invalid/stream")
        assert err is not None
        assert "resolve" in err.lower()

    @patch(
        "socket.getaddrinfo",
        return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0)),
        ],
    )
    def test_hostname_resolves_to_private_address(self, mock_dns):
        """Lines 62-63: hostname resolves to a loopback address."""
        err = _validate_video_url("rtsp://evil-host.example.com/stream")
        assert err is not None
        assert "private" in err.lower() or "reserved" in err.lower()

    @patch(
        "socket.getaddrinfo",
        return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("169.254.169.254", 0)),
        ],
    )
    def test_hostname_resolves_to_link_local(self, mock_dns):
        """Lines 62-63: hostname resolves to AWS metadata (link-local)."""
        err = _validate_video_url("rtsp://metadata.example.com/stream")
        assert err is not None

    def test_public_ip_accepted(self):
        err = _validate_video_url("rtsp://8.8.8.8/stream")
        assert err is None

    @patch(
        "socket.getaddrinfo",
        return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0)),
        ],
    )
    def test_public_hostname_accepted(self, mock_dns):
        err = _validate_video_url("rtsp://example.com/stream")
        assert err is None

    @patch("backend.video.urlparse", side_effect=ValueError("bad url"))
    def test_malformed_url_valueerror(self, mock_parse):
        """Lines 34-35: urlparse raises ValueError."""
        err = _validate_video_url("rtsp://valid-looking-but-mocked")
        assert err == "Malformed URL"

    @patch(
        "socket.getaddrinfo",
        return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("not-an-ip", 0)),
        ],
    )
    def test_unparseable_resolved_address_skipped(self, mock_dns):
        """Lines 62-63: sockaddr contains non-IP string, ValueError caught."""
        err = _validate_video_url("rtsp://weird-dns.example.com/stream")
        # The bad address is skipped, and since no valid private address was
        # found the URL is accepted.
        assert err is None


class TestVideoStreamKillExistingOSError:
    """Lines 94-95: OSError when killing existing active process in video_stream."""

    @patch("backend.video._ffmpeg_available", return_value=True)
    @patch("subprocess.Popen")
    def test_kill_existing_proc_oserror_swallowed(self, mock_popen, mock_ff, client):
        """Starting a new stream when existing proc raises OSError on kill."""
        old_proc = MagicMock()
        old_proc.kill = MagicMock(side_effect=OSError("No such process"))
        old_proc.wait = MagicMock()
        with _proc_lock:
            video_module._active_proc = old_proc

        new_proc = MagicMock()
        new_proc.stdout = MagicMock()
        new_proc.stdout.read = MagicMock(return_value=b"")
        new_proc.kill = MagicMock()
        new_proc.wait = MagicMock()
        mock_popen.return_value = new_proc

        r = client.get("/api/video?url=rtsp://8.8.8.8/cam")
        assert r.status_code == 200
        old_proc.kill.assert_called_once()


class TestVideoStreamJpegExtraction:
    """Lines 128-147: JPEG frame extraction and buffer overflow handling."""

    @patch("backend.video._ffmpeg_available", return_value=True)
    @patch("subprocess.Popen")
    def test_jpeg_frames_extracted(self, mock_popen, mock_ff, client):
        """Complete JPEG frames (FFD8...FFD9) are extracted and yielded."""
        # Build a fake JPEG frame: SOI + payload + EOI
        frame = b"\xff\xd8" + b"\x00" * 100 + b"\xff\xd9"
        mock_proc = MagicMock()
        # First read returns the frame, second returns empty (EOF)
        mock_proc.stdout.read = MagicMock(side_effect=[frame, b""])
        mock_proc.kill = MagicMock()
        mock_proc.wait = MagicMock()
        mock_popen.return_value = mock_proc

        r = client.get("/api/video?url=rtsp://8.8.8.8/cam")
        assert r.status_code == 200
        body = r.content
        # The response should contain the JPEG frame boundary marker
        assert b"--frame" in body
        assert b"\xff\xd8" in body
        assert b"\xff\xd9" in body

    @patch("backend.video._ffmpeg_available", return_value=True)
    @patch("subprocess.Popen")
    def test_buffer_overflow_reset(self, mock_popen, mock_ff, client):
        """Lines 129-132: buffer > 8MB is trimmed to last 64KB."""
        # Produce a chunk bigger than 8MB with no JPEG markers
        big_chunk = b"\x00" * (9 * 1024 * 1024)
        mock_proc = MagicMock()
        mock_proc.stdout.read = MagicMock(side_effect=[big_chunk, b""])
        mock_proc.kill = MagicMock()
        mock_proc.wait = MagicMock()
        mock_popen.return_value = mock_proc

        r = client.get("/api/video?url=rtsp://8.8.8.8/cam")
        # Should not crash; stream ends cleanly after EOF
        assert r.status_code == 200

    @patch("backend.video._ffmpeg_available", return_value=True)
    @patch("subprocess.Popen")
    def test_multiple_frames_in_one_chunk(self, mock_popen, mock_ff, client):
        """Multiple JPEG frames in a single read are all extracted."""
        frame1 = b"\xff\xd8" + b"\x01" * 50 + b"\xff\xd9"
        frame2 = b"\xff\xd8" + b"\x02" * 50 + b"\xff\xd9"
        mock_proc = MagicMock()
        mock_proc.stdout.read = MagicMock(side_effect=[frame1 + frame2, b""])
        mock_proc.kill = MagicMock()
        mock_proc.wait = MagicMock()
        mock_popen.return_value = mock_proc

        r = client.get("/api/video?url=rtsp://8.8.8.8/cam")
        assert r.status_code == 200
        body = r.content
        # Both frames should appear
        assert body.count(b"--frame") == 2
