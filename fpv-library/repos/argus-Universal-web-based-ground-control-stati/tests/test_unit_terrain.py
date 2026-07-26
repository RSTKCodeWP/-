"""Tests for backend/terrain.py — SRTM elevation lookup paths."""

import struct
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.drone_link import DroneLink
from backend.terrain import _get_srtm_elevation
from backend.ws_manager import WSManager

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _setup_app_state():
    if not hasattr(app.state, "link"):
        app.state.link = DroneLink()
        app.state.ws_mgr = WSManager(app.state.link)
    yield


def _make_hgt_data(elev: int, samples: int = 1201) -> bytes:
    """Build a minimal SRTM HGT file with uniform elevation."""
    return struct.pack(">h", elev) * (samples * samples)


class TestSrtmElevation:
    def test_cached_hgt_returns_elevation(self, tmp_path):
        import backend.terrain as t_mod

        hgt = _make_hgt_data(42)
        (tmp_path / "N30E120.hgt").write_bytes(hgt)
        with patch.object(t_mod, "SRTM_CACHE", tmp_path):
            import asyncio

            elev = asyncio.run(_get_srtm_elevation(30.5, 120.5))
        assert elev == 42.0

    def test_void_value_returns_zero(self, tmp_path):
        import backend.terrain as t_mod

        hgt = _make_hgt_data(-32768)
        (tmp_path / "N30E120.hgt").write_bytes(hgt)
        with patch.object(t_mod, "SRTM_CACHE", tmp_path):
            import asyncio

            elev = asyncio.run(_get_srtm_elevation(30.5, 120.5))
        assert elev == 0

    def test_3arcsec_file_detected(self, tmp_path):
        import backend.terrain as t_mod

        hgt = _make_hgt_data(100, samples=3601)
        (tmp_path / "N30E120.hgt").write_bytes(hgt)
        with patch.object(t_mod, "SRTM_CACHE", tmp_path):
            import asyncio

            elev = asyncio.run(_get_srtm_elevation(30.5, 120.5))
        assert elev == 100.0

    def test_wrong_size_hgt_returns_zero(self, tmp_path):
        import backend.terrain as t_mod

        (tmp_path / "N30E120.hgt").write_bytes(b"\x00" * 100)
        with patch.object(t_mod, "SRTM_CACHE", tmp_path):
            import asyncio

            elev = asyncio.run(_get_srtm_elevation(30.5, 120.5))
        assert elev == 0

    def test_cache_max_reached_returns_zero(self, tmp_path):
        import backend.terrain as t_mod

        with patch.object(t_mod, "SRTM_CACHE", tmp_path), patch.object(t_mod.cfg, "SRTM_CACHE_MAX", 0):
            import asyncio

            elev = asyncio.run(_get_srtm_elevation(30.5, 120.5))
        assert elev == 0

    def test_download_success(self, tmp_path):
        import backend.terrain as t_mod

        hgt = _make_hgt_data(55)
        mock_resp = MagicMock()
        mock_resp.read.return_value = hgt
        with (
            patch.object(t_mod, "SRTM_CACHE", tmp_path),
            patch("backend.terrain.urlreq.urlopen", return_value=mock_resp),
        ):
            import asyncio

            elev = asyncio.run(_get_srtm_elevation(30.5, 120.5))
        assert elev == 55.0
        assert (tmp_path / "N30E120.hgt").exists()

    def test_download_too_large_returns_zero(self, tmp_path):
        import backend.terrain as t_mod

        big = b"\x00" * t_mod.cfg.SRTM_FILE_MAX
        mock_resp = MagicMock()
        mock_resp.read.return_value = big
        with (
            patch.object(t_mod, "SRTM_CACHE", tmp_path),
            patch("backend.terrain.urlreq.urlopen", return_value=mock_resp),
        ):
            import asyncio

            elev = asyncio.run(_get_srtm_elevation(30.5, 120.5))
        assert elev == 0

    def test_download_oserror_returns_zero(self, tmp_path):
        import backend.terrain as t_mod

        with (
            patch.object(t_mod, "SRTM_CACHE", tmp_path),
            patch("backend.terrain.urlreq.urlopen", side_effect=OSError("timeout")),
        ):
            import asyncio

            elev = asyncio.run(_get_srtm_elevation(30.5, 120.5))
        assert elev == 0

    def test_southern_hemisphere_filename(self, tmp_path):
        import backend.terrain as t_mod

        hgt = _make_hgt_data(200)
        (tmp_path / "S10W045.hgt").write_bytes(hgt)
        with patch.object(t_mod, "SRTM_CACHE", tmp_path):
            import asyncio

            elev = asyncio.run(_get_srtm_elevation(-9.5, -44.5))
        assert elev == 200.0
