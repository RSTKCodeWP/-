"""Security regression tests — adversarial inputs on API endpoints and commands."""

import socket
from unittest.mock import patch

from backend.commands import execute
from backend.config import cfg
from backend.drone_link import DroneLink
from backend.video import _validate_video_url


# Test env DNS may map *.example.com to a private placeholder (DHCP/captive
# resolver behavior on some networks), which the post-audit DNS-based SSRF
# guard correctly blocks. Mock getaddrinfo so the "domain names are allowed"
# tests are independent of the test runner's network.
def _mock_public_dns(host, *args, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 0))]


# ─── Video URL Validation Tests ────────────────────────────────────


class TestVideoUrlValidation:
    def test_valid_rtsp(self):
        assert _validate_video_url("rtsp://8.8.8.8:554/stream") is None

    def test_valid_rtmp(self):
        with patch("socket.getaddrinfo", side_effect=_mock_public_dns):
            assert _validate_video_url("rtmp://live.example.com/app/key") is None

    def test_valid_http(self):
        with patch("socket.getaddrinfo", side_effect=_mock_public_dns):
            assert _validate_video_url("http://cam.example.com:8080/video") is None

    def test_valid_https(self):
        with patch("socket.getaddrinfo", side_effect=_mock_public_dns):
            assert _validate_video_url("https://stream.example.com/live.m3u8") is None

    def test_reject_file_scheme(self):
        err = _validate_video_url("file:///etc/passwd")
        assert err is not None
        assert "scheme" in err.lower()

    def test_reject_ftp_scheme(self):
        assert _validate_video_url("ftp://evil.com/firmware.bin") is not None

    def test_reject_no_scheme(self):
        assert _validate_video_url("/etc/passwd") is not None

    def test_reject_localhost(self):
        err = _validate_video_url("rtsp://localhost:554/stream")
        assert err is not None

    def test_reject_loopback_ip(self):
        assert _validate_video_url("rtsp://127.0.0.1:554/stream") is not None

    def test_reject_private_ip_192(self):
        assert _validate_video_url("rtsp://192.168.1.1:554/stream") is not None

    def test_reject_private_ip_10(self):
        assert _validate_video_url("rtsp://10.0.0.1:554/stream") is not None

    def test_reject_private_ip_172(self):
        assert _validate_video_url("rtsp://172.16.0.1:554/stream") is not None

    def test_reject_too_long_url(self):
        url = "rtsp://example.com/" + "a" * 3000
        err = _validate_video_url(url)
        assert err is not None
        assert "long" in err.lower()

    def test_reject_empty_host(self):
        assert _validate_video_url("rtsp:///stream") is not None

    def test_public_ip_allowed(self):
        assert _validate_video_url("rtsp://8.8.8.8:554/stream") is None

    def test_domain_name_allowed(self):
        with patch("socket.getaddrinfo", side_effect=_mock_public_dns):
            assert _validate_video_url("rtsp://cameras.example.org:554/live") is None

    def test_hostname_resolving_to_loopback_blocked(self):
        """Regression: pre-audit code only blocked the literal 'localhost';
        an attacker-controlled DNS name that resolves to 127.0.0.1 is now
        rejected too (SSRF via DNS rebinding)."""

        def _mock_loopback_dns(host, *args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0))]

        with patch("socket.getaddrinfo", side_effect=_mock_loopback_dns):
            err = _validate_video_url("rtsp://attacker-controlled.example/cam")
            assert err is not None


# ─── Command Error Handling Tests ──────────────────────────────────


class TestCommandExecuteErrorHandling:
    def test_handler_exception_caught(self):
        from unittest.mock import MagicMock

        link = MagicMock()
        link.vehicle.autopilot = 3  # execute() gates on this before dispatch

        def bad_handler(_link, _param, _data):
            raise RuntimeError("simulated failure")

        import backend.commands as cmd_module

        cmd_module._DISPATCH["_test_bad"] = bad_handler
        try:
            result = execute("_test_bad", None, link)
            assert result is not None
            assert result["ok"] is False
            assert "simulated failure" in result["error"]
        finally:
            del cmd_module._DISPATCH["_test_bad"]

    def test_error_message_truncated(self):
        from unittest.mock import MagicMock

        link = MagicMock()
        link.vehicle.autopilot = 3  # execute() gates on this before dispatch

        def long_error_handler(_link, _param, _data):
            raise ValueError("x" * 500)

        import backend.commands as cmd_module

        cmd_module._DISPATCH["_test_long"] = long_error_handler
        try:
            result = execute("_test_long", None, link)
            assert len(result["error"]) <= 200
        finally:
            del cmd_module._DISPATCH["_test_long"]

    def test_unknown_command_returns_error_without_dispatch(self):
        """Unknown names must not reach any handler (no side effects on the
        link) and must fail loud with an error cmd_result — silence left
        callers with stale command names waiting forever."""
        from unittest.mock import MagicMock

        link = MagicMock()
        result = execute("nonexistent_cmd_xyz", None, link)
        assert result == {"ok": False, "error": "unknown command: nonexistent_cmd_xyz"}
        link.send.assert_not_called()


# ─── WS Input Validation Config Tests ─────────────────────────────


class TestWsInputSanitization:
    """Test the actual parsing functions, not just config values."""

    def test_baud_as_int(self):
        from backend.ws_manager import sanitize_baud

        assert sanitize_baud(57600) == 57600
        assert sanitize_baud(115200) == 115200

    def test_baud_as_string(self):
        from backend.ws_manager import sanitize_baud

        assert sanitize_baud("57600") == 57600
        assert sanitize_baud("115200") == 115200

    def test_baud_as_float(self):
        from backend.ws_manager import sanitize_baud

        assert sanitize_baud(57600.0) == 57600

    def test_baud_invalid_falls_back(self):
        from backend.ws_manager import sanitize_baud

        assert sanitize_baud("garbage") == cfg.SERIAL_BAUD
        assert sanitize_baud(None) == cfg.SERIAL_BAUD
        assert sanitize_baud(12345) == cfg.SERIAL_BAUD

    def test_port_valid(self):
        from backend.ws_manager import validate_port

        assert validate_port("tcp:localhost:5770") is True
        assert validate_port("/dev/ttyUSB0") is True
        assert validate_port("COM3") is True

    def test_port_invalid(self):
        from backend.ws_manager import validate_port

        assert validate_port("x" * 300) is False
        assert validate_port(12345) is False
        assert validate_port("bad\x00port") is False

    def test_protocol_valid(self):
        from backend.ws_manager import sanitize_protocol

        assert sanitize_protocol("auto") == "auto"
        assert sanitize_protocol("standard") == "standard"
        assert sanitize_protocol("pllink") == "pllink"

    def test_protocol_invalid_falls_back(self):
        from backend.ws_manager import sanitize_protocol

        assert sanitize_protocol("invalid") == "auto"
        assert sanitize_protocol("") == "auto"
        assert sanitize_protocol(None) == "auto"


# ─── Path Traversal Tests ─────────────────────────────────────────


class TestMbtilesPathTraversal:
    def test_dotdot_in_name_rejected(self):
        from fastapi.testclient import TestClient

        from backend.app import app

        client = TestClient(app)
        r = client.get("/api/mbtiles/../../etc/passwd.mbtiles/0/0/0")
        assert r.status_code == 404

    def test_absolute_path_rejected(self):
        from fastapi.testclient import TestClient

        from backend.app import app

        client = TestClient(app)
        r = client.get("/api/mbtiles/%2F..%2F..%2Fetc%2Fpasswd.mbtiles/0/0/0")
        assert r.status_code == 404


# ─── Firmware Upload Limits ────────────────────────────────────────


class TestFirmwareUploadSanitization:
    def test_traversal_filename_sanitized(self, tmp_path):
        from fastapi.testclient import TestClient  # noqa: PLC0415

        import backend.firmware as fw_mod
        from backend.app import app  # noqa: PLC0415

        client = TestClient(app)
        with patch.object(fw_mod, "FIRMWARE_DIR", tmp_path):
            r = client.post(
                "/api/firmware/upload",
                files={"file": ("../../exploit.apj", b"\x00" * 10, "application/octet-stream")},
            )
        if r.status_code == 200:
            data = r.json()
            assert data.get("filename") == "exploit.apj"
            assert ".." not in data.get("filename", "")

    def test_non_apj_rejected(self):
        from fastapi.testclient import TestClient

        from backend.app import app

        client = TestClient(app)
        r = client.post(
            "/api/firmware/upload",
            files={"file": ("malware.exe", b"\x00", "application/octet-stream")},
        )
        data = r.json()
        assert data["ok"] is False


# ─── Mission/Fence/Guided Validation ──────────────────────────────


class TestMissionUploadValidation:
    def setup_method(self):
        self.link = DroneLink()

    def test_latitude_out_of_range(self):
        result = execute(
            "mission_upload",
            None,
            self.link,
            data={
                "waypoints": [{"lat": 999, "lon": 120, "alt": 50}],
                "takeoff_alt": 30,
            },
        )
        assert result is not None
        assert result["ok"] is False

    def test_too_many_waypoints(self):
        wps = [{"lat": 30.0 + i * 0.001, "lon": 120.0, "alt": 50} for i in range(501)]
        result = execute(
            "mission_upload",
            None,
            self.link,
            data={
                "waypoints": wps,
                "takeoff_alt": 30,
            },
        )
        assert result is not None
        assert result["ok"] is False


class TestGuidedGotoValidation:
    def setup_method(self):
        self.link = DroneLink()

    def test_lat_out_of_range(self):
        result = execute(
            "guided_goto",
            None,
            self.link,
            data={
                "lat": 91.0,
                "lon": 120.0,
                "alt": 30,
            },
        )
        assert result is not None
        assert result["ok"] is False


class TestFenceValidation:
    def setup_method(self):
        self.link = DroneLink()

    def test_too_few_vertices(self):
        result = execute(
            "fence_upload",
            None,
            self.link,
            data={
                "polygon": [{"lat": 30, "lon": 120}],
            },
        )
        assert result is not None
        assert result["ok"] is False
