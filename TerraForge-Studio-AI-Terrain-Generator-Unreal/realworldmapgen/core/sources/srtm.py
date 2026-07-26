"""
SRTM / open terrain-tile elevation source.

Fetches real-world elevation from the AWS Open Data "Terrain Tiles" dataset
(https://registry.opendata.aws/terrain-tiles/), which packages SRTM, ASTER,
NED and other public DEMs as Web-Mercator raster tiles.

The tiles use the *Terrarium* encoding, where each RGB pixel stores a single
elevation sample in metres::

    elevation = (R * 256 + G + B / 256) - 32768

No API key or registration is required, so this source is what makes terrain
generation work out of the box.
"""

from __future__ import annotations

import asyncio
import logging
import math
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .base import (
    BaseDataSource,
    BoundingBox,
    DataSourceCapability,
    DataSourceConfig,
    DataSourceType,
)

logger = logging.getLogger(__name__)

TILE_SIZE = 256
#: Terrarium's sentinel for "no data"; the encoding's minimum representable value.
TERRARIUM_NODATA = -32768.0


def lonlat_to_tile_xy(lon: float, lat: float, zoom: float) -> Tuple[float, float]:
    """Convert lon/lat (degrees) to fractional Web-Mercator tile coordinates."""
    lat = max(min(lat, 85.05112878), -85.05112878)
    n = 2.0**zoom

    x = (lon + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n

    # Rounding at the Mercator limit can push y a hair outside [0, n], which
    # would later be read as a non-existent tile row.
    return _clamp(x, 0.0, n), _clamp(y, 0.0, n)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def choose_zoom(bbox: BoundingBox, resolution: int, max_zoom: int, max_tiles: int) -> int:
    """
    Pick the smallest zoom level that supplies at least ``resolution`` samples
    across the bounding box, without exceeding ``max_tiles`` downloads.

    Sampling above the native tile density only wastes bandwidth, so the zoom
    is capped once the tile budget or ``max_zoom`` is reached.
    """
    for zoom in range(0, max_zoom + 1):
        x0, y0 = lonlat_to_tile_xy(bbox.west, bbox.north, zoom)
        x1, y1 = lonlat_to_tile_xy(bbox.east, bbox.south, zoom)

        px_width = abs(x1 - x0) * TILE_SIZE
        px_height = abs(y1 - y0) * TILE_SIZE

        tiles_x = int(math.floor(x1)) - int(math.floor(x0)) + 1
        tiles_y = int(math.floor(y1)) - int(math.floor(y0)) + 1
        if tiles_x * tiles_y > max_tiles:
            # This zoom already busts the budget - use the previous one.
            return max(0, zoom - 1)

        if px_width >= resolution and px_height >= resolution:
            return zoom

    return max_zoom


class SRTMSource(BaseDataSource):
    """
    Free, global elevation data from open Terrarium terrain tiles.

    Coverage is global (SRTM between 60°N and 56°S, supplemented by ASTER, NED
    and GMTED elsewhere), the vertical unit is metres above sea level, and the
    horizontal resolution depends on the zoom level chosen for the request.
    """

    def __init__(
        self,
        config: DataSourceConfig,
        tile_url: str = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png",
        cache_dir: Optional[Path] = None,
        max_zoom: int = 14,
        max_tiles: int = 256,
        concurrency: int = 8,
        user_agent: str = "TerraForge-Studio/2.0",
    ):
        super().__init__(config)
        self.tile_url = tile_url
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.max_zoom = max_zoom
        self.max_tiles = max_tiles
        self.concurrency = max(1, concurrency)
        self.user_agent = user_agent

    # ------------------------------------------------------------------
    # BaseDataSource interface
    # ------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "SRTM (Open Terrain Tiles)"

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.ELEVATION

    @property
    def capabilities(self) -> List[DataSourceCapability]:
        return [DataSourceCapability.ELEVATION_DEM, DataSourceCapability.ANALYSIS_SLOPE]

    async def is_available(self) -> bool:
        """Available whenever the source is enabled and httpx is importable."""
        if not self.config.enabled:
            return False
        try:
            import httpx  # noqa: F401
        except ImportError:
            logger.warning("httpx is not installed - SRTM elevation source disabled")
            return False
        return True

    async def get_imagery_data(
        self,
        bbox: BoundingBox,
        resolution: int,
        bands: Optional[List[str]] = None,
    ) -> Optional[np.ndarray]:
        """Terrain tiles carry elevation only, no imagery."""
        return None

    async def get_vector_data(
        self,
        bbox: BoundingBox,
        feature_types: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Terrain tiles carry elevation only, no vector features."""
        return None

    async def get_elevation_data(
        self,
        bbox: BoundingBox,
        resolution: int,
        dem_type: str = "dem",
    ) -> Optional[np.ndarray]:
        """
        Download and mosaic terrain tiles covering ``bbox``.

        Returns a ``resolution x resolution`` float32 array of metres above sea
        level, cropped precisely to the requested bounds, or ``None`` when no
        tile could be retrieved.
        """
        if not self._validate_bbox(bbox):
            logger.error("Invalid bounding box for elevation request: %s", bbox)
            return None

        zoom = choose_zoom(bbox, resolution, self.max_zoom, self.max_tiles)

        x0f, y0f = lonlat_to_tile_xy(bbox.west, bbox.north, zoom)
        x1f, y1f = lonlat_to_tile_xy(bbox.east, bbox.south, zoom)

        n_tiles = 2**zoom
        tile_x_min, tile_x_max = int(math.floor(x0f)), int(math.floor(x1f))
        tile_y_min, tile_y_max = int(math.floor(y0f)), int(math.floor(y1f))

        tile_count = (tile_x_max - tile_x_min + 1) * (tile_y_max - tile_y_min + 1)
        logger.info(
            "Fetching elevation: zoom=%d, tiles=%d (%dx%d), bbox=%s",
            zoom,
            tile_count,
            tile_x_max - tile_x_min + 1,
            tile_y_max - tile_y_min + 1,
            bbox,
        )

        coords = [
            (x, y)
            for y in range(tile_y_min, tile_y_max + 1)
            for x in range(tile_x_min, tile_x_max + 1)
        ]
        tiles = await self._fetch_tiles(coords, zoom, n_tiles)

        if not any(tile is not None for tile in tiles.values()):
            logger.warning("No terrain tiles could be downloaded for %s", bbox)
            return None

        mosaic = self._assemble_mosaic(tiles, tile_x_min, tile_x_max, tile_y_min, tile_y_max)

        # Crop to the exact bbox in mosaic pixel space, then resample.
        crop = self._crop_to_bbox(mosaic, x0f, y0f, x1f, y1f, tile_x_min, tile_y_min)
        return self._resample(crop, resolution)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_bbox(bbox: BoundingBox) -> bool:
        return (
            bbox.north > bbox.south
            and bbox.east > bbox.west
            and -90 <= bbox.south < bbox.north <= 90
            and -180 <= bbox.west < bbox.east <= 180
        )

    async def _fetch_tiles(
        self, coords: List[Tuple[int, int]], zoom: int, n_tiles: int
    ) -> Dict[Tuple[int, int], Optional[np.ndarray]]:
        """Download every tile concurrently, tolerating individual failures."""
        import httpx

        semaphore = asyncio.Semaphore(self.concurrency)
        timeout = httpx.Timeout(self.config.timeout)
        headers = {"User-Agent": self.user_agent}

        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:

            async def worker(x: int, y: int) -> Tuple[Tuple[int, int], Optional[np.ndarray]]:
                async with semaphore:
                    return (x, y), await self._fetch_tile(client, zoom, x, y, n_tiles)

            results = await asyncio.gather(
                *(worker(x, y) for x, y in coords), return_exceptions=True
            )

        tiles: Dict[Tuple[int, int], Optional[np.ndarray]] = {}
        for item in results:
            if isinstance(item, BaseException):
                logger.warning("Tile download task failed: %s", item)
                continue
            key, data = item
            tiles[key] = data
        return tiles

    async def _fetch_tile(
        self, client: Any, zoom: int, x: int, y: int, n_tiles: int
    ) -> Optional[np.ndarray]:
        """Fetch and decode a single tile, using the on-disk cache when possible."""
        # Wrap longitude, clamp latitude - out-of-range rows simply do not exist.
        x_wrapped = x % n_tiles
        if y < 0 or y >= n_tiles:
            return None

        cached = self._read_cached_tile(zoom, x_wrapped, y)
        if cached is not None:
            return cached

        url = self.tile_url.format(z=zoom, x=x_wrapped, y=y)

        last_error: Optional[Exception] = None
        for attempt in range(max(1, self.config.retry_attempts)):
            try:
                response = await client.get(url)
                if response.status_code == 404:
                    # Legitimately missing tile (e.g. open ocean) - not an error.
                    logger.debug("Tile %d/%d/%d not present (404)", zoom, x_wrapped, y)
                    return None
                response.raise_for_status()

                tile = self._decode_terrarium(response.content)
                if tile is not None:
                    self._write_cached_tile(zoom, x_wrapped, y, response.content)
                return tile
            except Exception as exc:  # network hiccup, truncated body, ...
                last_error = exc
                if attempt + 1 < max(1, self.config.retry_attempts):
                    await asyncio.sleep(0.5 * (2**attempt))

        logger.warning("Failed to fetch tile %d/%d/%d: %s", zoom, x_wrapped, y, last_error)
        return None

    @staticmethod
    def _decode_terrarium(content: bytes) -> Optional[np.ndarray]:
        """Decode Terrarium-encoded PNG bytes into metres above sea level."""
        from PIL import Image

        try:
            image = Image.open(BytesIO(content)).convert("RGB")
        except Exception as exc:
            logger.warning("Could not decode terrain tile: %s", exc)
            return None

        rgb = np.asarray(image, dtype=np.float32)
        if rgb.ndim != 3 or rgb.shape[2] < 3:
            logger.warning("Unexpected terrain tile shape: %s", rgb.shape)
            return None

        elevation = (rgb[:, :, 0] * 256.0 + rgb[:, :, 1] + rgb[:, :, 2] / 256.0) - 32768.0
        return elevation.astype(np.float32)

    # -- tile cache ----------------------------------------------------
    def _tile_cache_path(self, zoom: int, x: int, y: int) -> Optional[Path]:
        if not self.cache_dir or not self.config.cache_enabled:
            return None
        return self.cache_dir / "terrain_tiles" / str(zoom) / str(x) / f"{y}.png"

    def _read_cached_tile(self, zoom: int, x: int, y: int) -> Optional[np.ndarray]:
        path = self._tile_cache_path(zoom, x, y)
        if path is None or not path.exists():
            return None
        try:
            return self._decode_terrarium(path.read_bytes())
        except Exception as exc:
            logger.debug("Ignoring unreadable cached tile %s: %s", path, exc)
            return None

    def _write_cached_tile(self, zoom: int, x: int, y: int, content: bytes) -> None:
        path = self._tile_cache_path(zoom, x, y)
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        except OSError as exc:
            logger.debug("Could not cache tile %s: %s", path, exc)

    # -- mosaicking ----------------------------------------------------
    @staticmethod
    def _assemble_mosaic(
        tiles: Dict[Tuple[int, int], Optional[np.ndarray]],
        x_min: int,
        x_max: int,
        y_min: int,
        y_max: int,
    ) -> np.ndarray:
        """Stitch tiles into one array, filling gaps with NaN."""
        height = (y_max - y_min + 1) * TILE_SIZE
        width = (x_max - x_min + 1) * TILE_SIZE
        mosaic = np.full((height, width), np.nan, dtype=np.float32)

        for (x, y), tile in tiles.items():
            if tile is None:
                continue
            row = (y - y_min) * TILE_SIZE
            col = (x - x_min) * TILE_SIZE
            mosaic[row : row + TILE_SIZE, col : col + TILE_SIZE] = tile

        # Terrarium's floor value means "no data", not "32 km below sea level".
        mosaic[mosaic <= TERRARIUM_NODATA] = np.nan
        return mosaic

    @staticmethod
    def _crop_to_bbox(
        mosaic: np.ndarray,
        x0f: float,
        y0f: float,
        x1f: float,
        y1f: float,
        x_min: int,
        y_min: int,
    ) -> np.ndarray:
        """Crop the mosaic to the requested bounds using fractional tile offsets."""
        left = int(round((x0f - x_min) * TILE_SIZE))
        right = int(round((x1f - x_min) * TILE_SIZE))
        top = int(round((y0f - y_min) * TILE_SIZE))
        bottom = int(round((y1f - y_min) * TILE_SIZE))

        left = max(0, min(left, mosaic.shape[1] - 1))
        top = max(0, min(top, mosaic.shape[0] - 1))
        right = max(left + 1, min(right, mosaic.shape[1]))
        bottom = max(top + 1, min(bottom, mosaic.shape[0]))

        return mosaic[top:bottom, left:right]

    @staticmethod
    def _resample(data: np.ndarray, resolution: int) -> np.ndarray:
        """
        Resample to a square ``resolution`` grid.

        NaN holes (missing tiles, ocean) are filled with the mean of the valid
        samples first, so interpolation never smears NaN across the output.
        """
        if data.size == 0:
            return np.zeros((resolution, resolution), dtype=np.float32)

        filled = data.astype(np.float32, copy=True)
        invalid = ~np.isfinite(filled)
        if invalid.any():
            valid_values = filled[~invalid]
            fill_value = float(valid_values.mean()) if valid_values.size else 0.0
            filled[invalid] = fill_value

        if filled.shape == (resolution, resolution):
            return filled

        try:
            from scipy.ndimage import zoom as ndzoom

            factors = (resolution / filled.shape[0], resolution / filled.shape[1])
            # order=1 keeps elevation monotone; cubic can overshoot into spikes.
            resampled = ndzoom(filled, factors, order=1, mode="nearest")
        except ImportError:
            from PIL import Image

            image = Image.fromarray(filled)
            resampled = np.asarray(
                image.resize((resolution, resolution), Image.Resampling.BILINEAR),
                dtype=np.float32,
            )

        # ndzoom rounding can be a pixel off; force the exact requested shape.
        if resampled.shape != (resolution, resolution):
            resampled = np.resize(resampled, (resolution, resolution))

        return resampled.astype(np.float32)
