"""Tests for firmware download/upload paths not covered by test_unit_app_routes."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.drone_link import DroneLink
from backend.ws_manager import WSManager

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _setup_app_state():
    if not hasattr(app.state, "link"):
        app.state.link = DroneLink()
        app.state.ws_mgr = WSManager(app.state.link)
    yield


class TestFirmwareUploadTooLarge:
    def test_upload_exceeding_max_size(self, tmp_path):
        import backend.firmware as fw_mod

        big_data = b"\x00" * 1024
        with patch.object(fw_mod, "FIRMWARE_DIR", tmp_path), patch.object(fw_mod.cfg, "FIRMWARE_MAX_SIZE", 500):
            r = client.post(
                "/api/firmware/upload",
                files={"file": ("big.apj", big_data, "application/octet-stream")},
            )
        data = r.json()
        assert data["ok"] is False
        assert "too large" in data["error"].lower()
        assert not (tmp_path / "big.apj").exists()
        assert not (tmp_path / "big.apj.tmp").exists()


class TestFirmwareListWithFiles:
    def test_list_returns_existing_apj_files(self, tmp_path):
        import backend.firmware as fw_mod

        (tmp_path / "a.apj").write_bytes(b"\x00" * 10)
        (tmp_path / "b.apj").write_bytes(b"\x00" * 20)
        (tmp_path / "c.txt").write_bytes(b"nope")
        with patch.object(fw_mod, "FIRMWARE_DIR", tmp_path):
            r = client.get("/api/firmware/list")
        data = r.json()
        assert len(data["files"]) == 2
        names = [f["name"] for f in data["files"]]
        assert "a.apj" in names
        assert "b.apj" in names
        assert data["files"][0]["size"] == 10


class TestFirmwareDownloadSuccess:
    def test_download_writes_file(self, tmp_path):
        import backend.firmware as fw_mod

        payload = b"\xab" * 256
        mock_resp = MagicMock()
        mock_resp.read.side_effect = [payload, b""]
        with (
            patch.object(fw_mod, "FIRMWARE_DIR", tmp_path),
            patch("backend.firmware.urlreq.urlopen", return_value=mock_resp),
            patch(
                "backend.firmware._socket.getaddrinfo",
                return_value=[
                    (2, 1, 6, "", ("93.184.216.34", 443)),
                ],
            ),
        ):
            r = client.post(
                "/api/firmware/download",
                json={
                    "url": "https://firmware.example.com/test.apj",
                    "filename": "test.apj",
                },
            )
        data = r.json()
        assert data["ok"] is True
        assert data["filename"] == "test.apj"
        assert data["size"] == 256
        assert (tmp_path / "test.apj").read_bytes() == payload

    def test_download_too_large_cleaned_up(self, tmp_path):
        import backend.firmware as fw_mod

        mock_resp = MagicMock()
        mock_resp.read.side_effect = [b"\x00" * 1024, b"\x00" * 1024, b""]
        with (
            patch.object(fw_mod, "FIRMWARE_DIR", tmp_path),
            patch.object(fw_mod.cfg, "FIRMWARE_MAX_SIZE", 500),
            patch("backend.firmware.urlreq.urlopen", return_value=mock_resp),
            patch(
                "backend.firmware._socket.getaddrinfo",
                return_value=[
                    (2, 1, 6, "", ("93.184.216.34", 443)),
                ],
            ),
        ):
            r = client.post(
                "/api/firmware/download",
                json={
                    "url": "https://firmware.example.com/huge.apj",
                    "filename": "huge.apj",
                },
            )
        data = r.json()
        assert data["ok"] is False
        assert "too large" in data["error"].lower()
        assert not (tmp_path / "huge.apj").exists()

    def test_download_dns_failure(self):
        import socket as _s

        with patch("backend.firmware._socket.getaddrinfo", side_effect=_s.gaierror("nope")):
            r = client.post(
                "/api/firmware/download",
                json={
                    "url": "https://nonexistent.example.com/fw.apj",
                    "filename": "fw.apj",
                },
            )
        data = r.json()
        assert data["ok"] is False
        assert "resolve" in data["error"].lower()

    def test_download_private_ip_rejected(self):
        with patch(
            "backend.firmware._socket.getaddrinfo",
            return_value=[
                (2, 1, 6, "", ("192.168.1.1", 443)),
            ],
        ):
            r = client.post(
                "/api/firmware/download",
                json={
                    "url": "https://internal.example.com/fw.apj",
                    "filename": "fw.apj",
                },
            )
        data = r.json()
        assert data["ok"] is False
        assert "internal" in data["error"].lower()

    def test_download_path_traversal_neutralized(self, tmp_path):
        """Path(filename).name strips ../ so traversal is neutralized."""
        import backend.firmware as fw_mod

        mock_resp = MagicMock()
        mock_resp.read.side_effect = [b"\x00" * 10, b""]
        with (
            patch.object(fw_mod, "FIRMWARE_DIR", tmp_path),
            patch(
                "backend.firmware._socket.getaddrinfo",
                return_value=[
                    (2, 1, 6, "", ("93.184.216.34", 443)),
                ],
            ),
            patch("backend.firmware.urlreq.urlopen", return_value=mock_resp),
        ):
            r = client.post(
                "/api/firmware/download",
                json={
                    "url": "https://example.com/fw.apj",
                    "filename": "../../../etc/passwd.apj",
                },
            )
        data = r.json()
        assert data["ok"] is True
        assert data["filename"] == "passwd.apj"
        assert (tmp_path / "passwd.apj").exists()

    def test_download_network_error(self):
        import urllib.error

        with (
            patch(
                "backend.firmware._socket.getaddrinfo",
                return_value=[
                    (2, 1, 6, "", ("93.184.216.34", 443)),
                ],
            ),
            patch("backend.firmware.urlreq.urlopen", side_effect=urllib.error.URLError("timeout")),
        ):
            r = client.post(
                "/api/firmware/download",
                json={
                    "url": "https://firmware.example.com/fw.apj",
                    "filename": "fw.apj",
                },
            )
        data = r.json()
        assert data["ok"] is False
        assert "failed" in data["error"].lower()
