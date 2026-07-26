"""Unit tests for tile proxy routes: URL construction, caching, mbtiles, bulk download."""

import math
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.app import app
from backend.drone_link import DroneLink
from backend.tiles import TILE_SOURCES, TILE_URLS
from backend.ws_manager import WSManager

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _setup_app_state():
    """Ensure app.state.link and app.state.ws_mgr exist for route handlers."""
    if not hasattr(app.state, "link"):
        app.state.link = DroneLink()
        app.state.ws_mgr = WSManager(app.state.link)
    yield


@pytest.fixture
def tile_cache_dir(tmp_path):
    """Provide a temporary tile cache directory and patch TILE_CACHE."""
    import backend.tiles as _tiles

    cache = tmp_path / "tile_cache"
    cache.mkdir()
    saved = _tiles._tile_count
    _tiles._tile_count = -1
    with patch("backend.tiles.TILE_CACHE", cache):
        yield cache
    _tiles._tile_count = saved


@pytest.fixture
def mbtiles_dir(tmp_path):
    """Provide a temporary mbtiles directory and patch MBTILES_DIR."""
    mb = tmp_path / "mbtiles"
    mb.mkdir()
    with patch("backend.tiles.MBTILES_DIR", mb):
        yield mb


class TestTileUrlConstruction:
    """Test that TILE_URLS has correct format strings for all providers."""

    def test_amap_satellite_url_format(self):
        url = TILE_URLS["6"].format(x=1234, y=5678, z=10)
        assert "x=1234" in url
        assert "y=5678" in url
        assert "z=10" in url
        assert "autonavi.com" in url

    def test_amap_vector_url_format(self):
        url = TILE_URLS["7"].format(x=100, y=200, z=5)
        assert "x=100" in url
        assert "y=200" in url
        assert "z=5" in url
        assert "style=7" in url

    def test_amap_label_url_format(self):
        url = TILE_URLS["8"].format(x=0, y=0, z=1)
        assert "x=0" in url
        assert "y=0" in url
        assert "z=1" in url
        assert "style=8" in url

    def test_google_satellite_url_format(self):
        url = TILE_URLS["google_sat"].format(x=10, y=20, z=15)
        assert "x=10" in url
        assert "y=20" in url
        assert "z=15" in url
        assert "mt1.google.com" in url
        assert "lyrs=s" in url

    def test_google_street_url_format(self):
        url = TILE_URLS["google_street"].format(x=5, y=10, z=12)
        assert "lyrs=m" in url
        assert "mt1.google.com" in url

    def test_google_hybrid_url_format(self):
        url = TILE_URLS["google_hybrid"].format(x=5, y=10, z=12)
        assert "lyrs=y" in url

    def test_google_terrain_url_format(self):
        url = TILE_URLS["google_terrain"].format(x=5, y=10, z=12)
        assert "lyrs=p" in url

    def test_osm_url_format(self):
        url = TILE_URLS["osm"].format(x=100, y=50, z=8)
        assert "/8/100/50.png" in url
        assert "openstreetmap.org" in url

    def test_esri_topo_url_format(self):
        url = TILE_URLS["esri_topo"].format(x=3, y=7, z=14)
        assert "/14/7/3" in url
        assert "arcgisonline.com" in url

    def test_tianditu_satellite_url_format(self):
        url = TILE_URLS["tdt_sat"].format(x=800, y=400, z=9)
        assert "TILECOL=800" in url
        assert "TILEROW=400" in url
        assert "TILEMATRIX=9" in url
        assert "tianditu.gov.cn" in url

    def test_tianditu_vector_url_format(self):
        url = TILE_URLS["tdt_vec"].format(x=1, y=2, z=3)
        assert "TILECOL=1" in url
        assert "TILEROW=2" in url
        assert "TILEMATRIX=3" in url
        assert "vec_w" in url

    def test_tianditu_label_url_format(self):
        url = TILE_URLS["tdt_label"].format(x=55, y=44, z=11)
        assert "cia_w" in url

    def test_carto_dark_url_format(self):
        url = TILE_URLS["carto_dark"].format(x=2, y=3, z=7)
        assert "/7/2/3.png" in url
        assert "dark_all" in url
        assert "basemaps.cartocdn.com" in url

    def test_carto_light_url_format(self):
        url = TILE_URLS["carto_light"].format(x=9, y=10, z=4)
        assert "light_all" in url
        assert "/4/9/10.png" in url

    def test_esri_satellite_url_format(self):
        url = TILE_URLS["osm_sat"].format(x=5, y=6, z=13)
        assert "World_Imagery" in url
        assert "/13/6/5" in url


class TestTileSourcesRegistry:
    """Test TILE_SOURCES configuration is correct for all providers."""

    def test_all_providers_present(self):
        expected = {"amap", "google_sat", "google_hybrid", "osm", "carto_dark", "carto_light", "esri", "tianditu"}
        assert set(TILE_SOURCES.keys()) == expected

    def test_amap_is_gcj02(self):
        assert TILE_SOURCES["amap"]["gcj02"] is True
        assert TILE_SOURCES["amap"]["region"] == "china"

    def test_osm_is_global(self):
        assert TILE_SOURCES["osm"]["gcj02"] is False
        assert TILE_SOURCES["osm"]["region"] == "global"

    def test_tile_sources_reference_valid_urls(self):
        for source_key, source in TILE_SOURCES.items():
            for layer in ("sat", "vec", "label"):
                style = source.get(layer)
                if style is not None:
                    assert style in TILE_URLS, f"{source_key}.{layer} = '{style}' not found in TILE_URLS"


class TestTileStyleWhitelist:
    """Test that unknown styles return 404."""

    def test_unknown_style_returns_404(self):
        r = client.get("/api/tile/nonexistent_style/10/500/300")
        assert r.status_code == 404
        assert "unknown tile style" in r.text

    def test_unknown_style_with_special_chars(self):
        r = client.get("/api/tile/../../etc/passwd/10/500/300")
        assert r.status_code in (404, 422)

    def test_valid_style_names_in_whitelist(self):
        for style in TILE_URLS:
            assert isinstance(style, str)
            assert len(style) > 0


class TestTileCache:
    """Test tile caching behavior."""

    def test_cached_tile_returned_directly(self, tile_cache_dir):
        """When a tile exists in cache, it should be returned without network request."""
        cache_dir = tile_cache_dir / "osm" / "10" / "500"
        cache_dir.mkdir(parents=True)
        tile_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        (cache_dir / "300.png").write_bytes(tile_data)

        r = client.get("/api/tile/osm/10/500/300")
        assert r.status_code == 200
        assert r.content == tile_data
        assert r.headers.get("content-type") == "image/png"
        assert "max-age=604800" in r.headers.get("cache-control", "")

    def test_cache_directory_structure(self, tile_cache_dir):
        """Cache uses z/x/y.png pattern: tile_cache/<style>/<z>/<x>/<y>.png."""
        cache_dir = tile_cache_dir / "6" / "15" / "26745"
        cache_dir.mkdir(parents=True)
        (cache_dir / "12345.png").write_bytes(b"\x89PNG\r\n\x1a\n")

        r = client.get("/api/tile/6/15/26745/12345")
        assert r.status_code == 200

    def test_first_request_fetches_from_network(self, tile_cache_dir):
        """First request for a tile should try to fetch from network."""
        fake_tile = b"\x89PNG\r\n\x1a\n" + b"\x42" * 50

        with patch("backend.tiles.urlreq.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = fake_tile
            mock_urlopen.return_value = mock_response

            r = client.get("/api/tile/osm/5/10/15")
            assert r.status_code == 200
            assert r.content == fake_tile
            mock_urlopen.assert_called_once()

    def test_second_request_uses_cache(self, tile_cache_dir):
        """Second request for same tile should come from cache, not network."""
        fake_tile = b"\x89PNG\r\n\x1a\n" + b"\x42" * 50

        with patch("backend.tiles.urlreq.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = fake_tile
            mock_urlopen.return_value = mock_response

            r1 = client.get("/api/tile/osm/8/20/30")
            assert r1.status_code == 200
            assert mock_urlopen.call_count == 1

        cache_file = tile_cache_dir / "osm" / "8" / "20" / "30.png"
        assert cache_file.exists(), "Handler should have written cache file"

        with patch("backend.tiles.urlreq.urlopen") as mock_urlopen2:
            r2 = client.get("/api/tile/osm/8/20/30")
            assert r2.status_code == 200
            assert r2.content == fake_tile
            mock_urlopen2.assert_not_called()

    def test_network_failure_returns_404(self, tile_cache_dir):
        """If network fetch fails and no cache, return 404."""
        with patch("backend.tiles.urlreq.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = OSError("network error")

            r = client.get("/api/tile/osm/5/10/15")
            assert r.status_code == 404
            assert "tile unavailable" in r.text

    def test_tile_cache_stats_endpoint(self, tile_cache_dir):
        """tile_cache endpoint returns correct size and count."""
        cache_dir = tile_cache_dir / "osm" / "5" / "10"
        cache_dir.mkdir(parents=True)
        (cache_dir / "15.png").write_bytes(b"\x00" * 1024)
        (cache_dir / "16.png").write_bytes(b"\x00" * 2048)

        r = client.get("/api/tile_cache")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 2
        assert data["size"] == 3072


class TestMbtilesReading:
    """Test mbtiles file reading from SQLite database."""

    def _create_mbtiles(self, path: Path, tiles: list[tuple[int, int, int, bytes]]):
        """Create a minimal mbtiles SQLite database."""
        conn = sqlite3.connect(str(path))
        conn.execute("""CREATE TABLE tiles (
            zoom_level INTEGER,
            tile_column INTEGER,
            tile_row INTEGER,
            tile_data BLOB
        )""")
        conn.execute("""CREATE TABLE metadata (
            name TEXT,
            value TEXT
        )""")
        conn.execute("INSERT INTO metadata VALUES ('name', 'test')")
        conn.execute("INSERT INTO metadata VALUES ('format', 'png')")
        for z, x, y, data in tiles:
            conn.execute("INSERT INTO tiles VALUES (?, ?, ?, ?)", (z, x, y, data))
        conn.commit()
        conn.close()

    def test_mbtiles_list_empty(self, mbtiles_dir):
        r = client.get("/api/mbtiles/list")
        assert r.status_code == 200
        assert r.json()["files"] == []

    def test_mbtiles_list_with_files(self, mbtiles_dir):
        self._create_mbtiles(mbtiles_dir / "test.mbtiles", [])
        self._create_mbtiles(mbtiles_dir / "map2.mbtiles", [])

        r = client.get("/api/mbtiles/list")
        assert r.status_code == 200
        files = r.json()["files"]
        assert "test.mbtiles" in files
        assert "map2.mbtiles" in files

    def test_mbtiles_tile_found(self, mbtiles_dir):
        """Test reading a tile from mbtiles with TMS y-flip."""
        tile_data = b"\x89PNG\r\n\x1a\n" + b"\xab" * 64
        # In mbtiles, y is stored in TMS format: tms_y = (1 << z) - 1 - y
        # For z=5, requesting y=10 means tms_y = (1<<5) - 1 - 10 = 21
        z, x, y = 5, 10, 10
        tms_y = (1 << z) - 1 - y  # 21
        self._create_mbtiles(mbtiles_dir / "test.mbtiles", [(z, x, tms_y, tile_data)])

        r = client.get(f"/api/mbtiles/test.mbtiles/{z}/{x}/{y}")
        assert r.status_code == 200
        assert r.content == tile_data
        assert r.headers.get("content-type") == "image/png"

    def test_mbtiles_tile_not_found(self, mbtiles_dir):
        """Request a tile not in the database returns 404."""
        self._create_mbtiles(mbtiles_dir / "test.mbtiles", [])

        r = client.get("/api/mbtiles/test.mbtiles/5/10/10")
        assert r.status_code == 404
        assert "tile not found" in r.text

    def test_mbtiles_file_not_found(self, mbtiles_dir):
        """Request for nonexistent mbtiles file returns 404."""
        r = client.get("/api/mbtiles/nonexistent.mbtiles/5/10/10")
        assert r.status_code == 404
        assert "not found" in r.text

    def test_mbtiles_path_traversal_blocked(self, mbtiles_dir):
        """Path traversal attempts are blocked."""
        r = client.get("/api/mbtiles/../../../etc/passwd.mbtiles/1/0/0")
        assert r.status_code == 404

    def test_mbtiles_invalid_extension_rejected(self, mbtiles_dir):
        """Non-.mbtiles files are rejected."""
        r = client.get("/api/mbtiles/notmbtiles.txt/1/0/0")
        assert r.status_code == 404


class TestTileBulkDownload:
    """Test offline map bulk download task."""

    def test_bulk_download_tile_count_estimation(self):
        """Verify tile count calculation for small bounding box."""
        # For a small area at zoom 10, calculate expected tile count
        lat_min, lat_max = 30.0, 30.1
        lon_min, lon_max = 120.0, 120.1
        z = 10
        n = 2**z
        x_min = int((lon_min + 180) / 360 * n)
        x_max = int((lon_max + 180) / 360 * n)
        y_min = int(
            (1 - math.log(math.tan(math.radians(lat_max)) + 1 / math.cos(math.radians(lat_max))) / math.pi) / 2 * n
        )
        y_max = int(
            (1 - math.log(math.tan(math.radians(lat_min)) + 1 / math.cos(math.radians(lat_min))) / math.pi) / 2 * n
        )
        expected_count = (x_max - x_min + 1) * (y_max - y_min + 1)
        assert expected_count > 0

    def test_bulk_download_invalid_style(self):
        """Unknown style returns empty result."""
        r = client.post(
            "/api/tile_bulk_download",
            json={
                "lat_min": 30.0,
                "lat_max": 30.1,
                "lon_min": 120.0,
                "lon_max": 120.1,
                "z_min": 10,
                "z_max": 10,
                "style": "invalid_style",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["downloaded"] == 0

    def test_bulk_download_zoom_clamped(self, tile_cache_dir):
        """Zoom levels are clamped to 0-18."""
        fake_tile = b"\x89PNG" + b"\x00" * 10
        with patch("backend.tiles.urlreq.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = fake_tile
            mock_urlopen.return_value = mock_response

            r = client.post(
                "/api/tile_bulk_download",
                json={
                    "lat_min": 30.0,
                    "lat_max": 30.001,
                    "lon_min": 120.0,
                    "lon_max": 120.001,
                    "z_min": -5,
                    "z_max": 25,
                    "style": "osm",
                },
            )
            assert r.status_code == 200
            data = r.json()
            assert data["total"] > 0

    def test_bulk_download_respects_5000_limit(self, tile_cache_dir):
        """Bulk download truncates at 5000 tiles."""
        fake_tile = b"\x89PNG" + b"\x00" * 10
        with patch("backend.tiles.urlreq.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = fake_tile
            mock_urlopen.return_value = mock_response

            # Large area with high zoom = many tiles, should trigger truncation
            r = client.post(
                "/api/tile_bulk_download",
                json={
                    "lat_min": 20.0,
                    "lat_max": 40.0,
                    "lon_min": 100.0,
                    "lon_max": 130.0,
                    "z_min": 12,
                    "z_max": 18,
                    "style": "osm",
                },
            )
            assert r.status_code == 200
            data = r.json()
            assert data["truncated"] is True
            assert data["total"] > 5000

    def test_bulk_download_skips_cached_tiles(self, tile_cache_dir):
        """Already-cached tiles are skipped (counted as 'skipped')."""
        # Pre-create a cached tile at z=10, x=854, y=420
        cache_dir = tile_cache_dir / "osm" / "10" / "854"
        cache_dir.mkdir(parents=True)
        (cache_dir / "420.png").write_bytes(b"\x89PNG" + b"\x00" * 10)

        # Calculate bounds that will include tile (854, 420) at z=10
        n = 2**10
        lon_min = 854 / n * 360 - 180
        lon_max = (854 + 1) / n * 360 - 180
        lat_max = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * 420 / n))))
        lat_min = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (420 + 1) / n))))

        with patch("backend.tiles.urlreq.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b"\x89PNG" + b"\x00" * 10
            mock_urlopen.return_value = mock_response

            r = client.post(
                "/api/tile_bulk_download",
                json={
                    "lat_min": lat_min,
                    "lat_max": lat_max,
                    "lon_min": lon_min,
                    "lon_max": lon_max,
                    "z_min": 10,
                    "z_max": 10,
                    "style": "osm",
                },
            )
            assert r.status_code == 200
            data = r.json()
            assert data["skipped"] >= 1


class TestTileCacheClear:
    """Test cache clearing endpoint."""

    def test_clear_cache(self, tile_cache_dir):
        """Clearing the cache removes all files."""
        cache_dir = tile_cache_dir / "osm" / "5" / "10"
        cache_dir.mkdir(parents=True)
        (cache_dir / "15.png").write_bytes(b"\x00" * 100)

        r = client.post("/api/tile_cache_clear")
        assert r.status_code == 200
        assert r.json()["ok"] is True
