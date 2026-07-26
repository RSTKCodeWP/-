"""
Tests for the SRTM / open terrain-tile elevation source.

Tile decoding, zoom selection, mosaicking and cropping are verified against
synthetic tiles, so the whole pipeline is covered without network access. The
single test that does hit the real tile server is marked ``network`` and is
deselected by default.
"""

from __future__ import annotations

import math
from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from realworldmapgen.core.sources.base import BoundingBox, DataSourceConfig
from realworldmapgen.core.sources.srtm import (
    TILE_SIZE,
    SRTMSource,
    choose_zoom,
    lonlat_to_tile_xy,
)


def encode_terrarium(elevation: np.ndarray) -> bytes:
    """Encode metres into a Terrarium PNG, the inverse of the decoder."""
    value = np.clip(elevation + 32768.0, 0, 256 * 256 - 1)
    red = np.floor(value / 256.0)
    green = np.floor(value - red * 256.0)
    blue = np.floor((value - red * 256.0 - green) * 256.0)

    rgb = np.dstack([red, green, blue]).astype(np.uint8)
    buffer = BytesIO()
    Image.fromarray(rgb, mode="RGB").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def source() -> SRTMSource:
    return SRTMSource(DataSourceConfig(enabled=True, timeout=5), cache_dir=None)


# ---------------------------------------------------------------------------
# Tile mathematics
# ---------------------------------------------------------------------------
def test_lonlat_to_tile_xy_origin():
    """Zoom 0 maps the whole world onto a single tile."""
    x, y = lonlat_to_tile_xy(0.0, 0.0, 0)
    assert x == pytest.approx(0.5)
    assert y == pytest.approx(0.5)


def test_lonlat_to_tile_xy_known_tile():
    """San Francisco falls in tile (1310, 3166) at zoom 13."""
    x, y = lonlat_to_tile_xy(-122.42, 37.77, 13)
    assert math.floor(x) == 1310
    assert math.floor(y) == 3166


def test_lonlat_to_tile_xy_clamps_poles():
    """Latitudes past the Mercator limit clamp instead of producing infinities."""
    _, y = lonlat_to_tile_xy(0.0, 89.9, 4)
    assert math.isfinite(y)
    assert 0 <= y <= 2**4


def test_choose_zoom_grows_with_requested_resolution():
    bbox = BoundingBox(north=37.80, south=37.75, east=-122.40, west=-122.45)

    low = choose_zoom(bbox, resolution=128, max_zoom=14, max_tiles=256)
    high = choose_zoom(bbox, resolution=2048, max_zoom=14, max_tiles=256)

    assert high > low


def test_choose_zoom_respects_tile_budget():
    """A tight tile budget must cap the zoom rather than blow through it."""
    bbox = BoundingBox(north=38.0, south=37.0, east=-122.0, west=-123.0)

    zoom = choose_zoom(bbox, resolution=8192, max_zoom=14, max_tiles=4)

    x0, y0 = lonlat_to_tile_xy(bbox.west, bbox.north, zoom)
    x1, y1 = lonlat_to_tile_xy(bbox.east, bbox.south, zoom)
    tiles = (int(x1) - int(x0) + 1) * (int(y1) - int(y0) + 1)
    assert tiles <= 4


# ---------------------------------------------------------------------------
# Decoding
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("elevation", [-100.0, 0.0, 512.0, 4000.0, 8848.0])
def test_decode_terrarium_roundtrip(elevation):
    """Decoding an encoded tile recovers the original metres."""
    tile = np.full((4, 4), elevation, dtype=np.float32)
    decoded = SRTMSource._decode_terrarium(encode_terrarium(tile))

    assert decoded is not None
    assert decoded == pytest.approx(tile, abs=0.01)


def test_decode_terrarium_rejects_garbage():
    assert SRTMSource._decode_terrarium(b"not a png") is None


# ---------------------------------------------------------------------------
# Mosaic and crop
# ---------------------------------------------------------------------------
def test_assemble_mosaic_places_tiles_by_coordinate():
    tile_a = np.full((TILE_SIZE, TILE_SIZE), 10.0, dtype=np.float32)
    tile_b = np.full((TILE_SIZE, TILE_SIZE), 20.0, dtype=np.float32)

    mosaic = SRTMSource._assemble_mosaic(
        {(5, 7): tile_a, (6, 7): tile_b}, x_min=5, x_max=6, y_min=7, y_max=7
    )

    assert mosaic.shape == (TILE_SIZE, TILE_SIZE * 2)
    assert mosaic[0, 0] == 10.0
    assert mosaic[0, TILE_SIZE] == 20.0


def test_assemble_mosaic_marks_missing_tiles_as_nan():
    tile = np.full((TILE_SIZE, TILE_SIZE), 42.0, dtype=np.float32)

    mosaic = SRTMSource._assemble_mosaic(
        {(0, 0): tile, (1, 0): None}, x_min=0, x_max=1, y_min=0, y_max=0
    )

    assert not np.isnan(mosaic[:, :TILE_SIZE]).any()
    assert np.isnan(mosaic[:, TILE_SIZE:]).all()


def test_crop_to_bbox_extracts_the_requested_window():
    mosaic = np.arange(TILE_SIZE * TILE_SIZE, dtype=np.float32).reshape(TILE_SIZE, TILE_SIZE)

    # Ask for the middle half of a single tile.
    crop = SRTMSource._crop_to_bbox(mosaic, 0.25, 0.25, 0.75, 0.75, x_min=0, y_min=0)

    assert crop.shape == (TILE_SIZE // 2, TILE_SIZE // 2)
    assert crop[0, 0] == mosaic[TILE_SIZE // 4, TILE_SIZE // 4]


def test_crop_to_bbox_never_returns_empty():
    """Degenerate crops must still yield at least one pixel."""
    mosaic = np.zeros((TILE_SIZE, TILE_SIZE), dtype=np.float32)

    crop = SRTMSource._crop_to_bbox(mosaic, 0.5, 0.5, 0.5, 0.5, x_min=0, y_min=0)

    assert crop.size > 0


# ---------------------------------------------------------------------------
# Resampling
# ---------------------------------------------------------------------------
def test_resample_produces_exact_square_shape():
    data = np.random.default_rng(0).normal(size=(137, 211)).astype(np.float32)
    assert SRTMSource._resample(data, 64).shape == (64, 64)


def test_resample_fills_nan_holes():
    data = np.full((32, 32), 100.0, dtype=np.float32)
    data[10:20, 10:20] = np.nan

    resampled = SRTMSource._resample(data, 32)

    assert np.isfinite(resampled).all()
    assert resampled == pytest.approx(np.full((32, 32), 100.0), abs=0.01)


def test_resample_of_empty_input_is_zeros():
    assert SRTMSource._resample(np.array([[]], dtype=np.float32), 8).shape == (8, 8)


# ---------------------------------------------------------------------------
# Full path with a stubbed network
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_elevation_data_end_to_end(source, monkeypatch):
    """A full request assembles stubbed tiles into the requested grid."""

    async def fake_fetch(coords, zoom, n_tiles):
        return {
            (x, y): np.full((TILE_SIZE, TILE_SIZE), 250.0, dtype=np.float32)
            for x, y in coords
        }

    monkeypatch.setattr(source, "_fetch_tiles", fake_fetch)

    bbox = BoundingBox(north=37.80, south=37.75, east=-122.40, west=-122.45)
    elevation = await source.get_elevation_data(bbox, resolution=64)

    assert elevation is not None
    assert elevation.shape == (64, 64)
    assert elevation == pytest.approx(np.full((64, 64), 250.0), abs=0.01)


@pytest.mark.asyncio
async def test_get_elevation_data_returns_none_when_all_tiles_fail(source, monkeypatch):
    async def fake_fetch(coords, zoom, n_tiles):
        return dict.fromkeys(coords)

    monkeypatch.setattr(source, "_fetch_tiles", fake_fetch)

    bbox = BoundingBox(north=37.80, south=37.75, east=-122.40, west=-122.45)
    assert await source.get_elevation_data(bbox, resolution=64) is None


@pytest.mark.asyncio
async def test_get_elevation_data_rejects_invalid_bbox(source):
    inverted = BoundingBox(north=37.0, south=37.8, east=-122.4, west=-122.5)
    assert await source.get_elevation_data(inverted, resolution=64) is None


@pytest.mark.asyncio
async def test_tile_cache_avoids_repeat_downloads(tmp_path):
    """A tile written to the cache is served from disk on the next request."""
    cached_source = SRTMSource(
        DataSourceConfig(enabled=True, timeout=5), cache_dir=tmp_path
    )
    tile = np.full((TILE_SIZE, TILE_SIZE), 321.0, dtype=np.float32)

    cached_source._write_cached_tile(10, 163, 395, encode_terrarium(tile))
    restored = cached_source._read_cached_tile(10, 163, 395)

    assert restored is not None
    assert restored == pytest.approx(tile, abs=0.01)


@pytest.mark.asyncio
async def test_is_available_when_enabled(source):
    assert await source.is_available() is True


@pytest.mark.asyncio
async def test_is_unavailable_when_disabled():
    disabled = SRTMSource(DataSourceConfig(enabled=False))
    assert await disabled.is_available() is False


# ---------------------------------------------------------------------------
# Live network check (opt-in: pytest -m network)
# ---------------------------------------------------------------------------
@pytest.mark.network
@pytest.mark.asyncio
async def test_real_elevation_matches_known_terrain(source):
    """Mount Everest must come back at roughly its real height."""
    bbox = BoundingBox(north=28.05, south=27.95, east=87.00, west=86.90)

    elevation = await source.get_elevation_data(bbox, resolution=128)

    assert elevation is not None
    assert 8000 < float(elevation.max()) < 9000
