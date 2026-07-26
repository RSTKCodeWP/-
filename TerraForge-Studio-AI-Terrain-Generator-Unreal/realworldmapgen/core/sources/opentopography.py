"""
OpenTopography Data Source
High-resolution elevation data from LiDAR and global DEMs
"""

from io import BytesIO
from typing import Any, Dict, Optional

import httpx
import numpy as np

# Rasterio is optional - desktop version may not have it
try:
    import rasterio
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False
    rasterio = None

from .base import (
    BaseDataSource,
    BoundingBox,
    DataSourceCapability,
    DataSourceConfig,
    DataSourceType,
)


class OpenTopographySource(BaseDataSource):
    """
    OpenTopography elevation data source.

    Provides:
    - High-resolution LiDAR DEMs (0.5m-2m in some regions)
    - Global SRTM data (30m-90m)
    - ASTER GDEM (30m)
    - ALOS World 3D (30m)

    Requires API key from https://opentopography.org/
    """

    # Available datasets
    DATASETS = {
        "SRTMGL3": {
            "name": "SRTM GL3 (90m)",
            "resolution": 90,
            "coverage": "global",
        },
        "SRTMGL1": {
            "name": "SRTM GL1 (30m)",
            "resolution": 30,
            "coverage": "60N-60S",
        },
        "SRTMGL1_E": {
            "name": "SRTM GL1 Ellipsoidal (30m)",
            "resolution": 30,
            "coverage": "60N-60S",
        },
        "AW3D30": {
            "name": "ALOS World 3D (30m)",
            "resolution": 30,
            "coverage": "global",
        },
        "AW3D30_E": {
            "name": "ALOS World 3D Ellipsoidal (30m)",
            "resolution": 30,
            "coverage": "global",
        },
        "SRTM15Plus": {
            "name": "SRTM15+ (500m global bathymetry)",
            "resolution": 500,
            "coverage": "global",
        },
    }

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.base_url = config.base_url or "https://portal.opentopography.org/API/globaldem"
        self.default_dataset = config.custom_params.get("default_dataset", "SRTMGL1")

    @property
    def name(self) -> str:
        return "OpenTopography"

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.ELEVATION

    @property
    def capabilities(self) -> list[DataSourceCapability]:
        return [
            DataSourceCapability.ELEVATION_DEM,
            DataSourceCapability.ANALYSIS_SLOPE,
            DataSourceCapability.ANALYSIS_ASPECT,
        ]

    async def is_available(self) -> bool:
        """Check if OpenTopography is available and configured"""
        if not self.config.enabled:
            return False
        if not self.config.api_key:
            return False
        return True

    async def get_elevation_data(
        self,
        bbox: BoundingBox,
        resolution: int,
        dem_type: str = "dem",
    ) -> Optional[np.ndarray]:
        """
        Retrieve elevation data from OpenTopography.

        Args:
            bbox: Geographic bounding box
            resolution: Output resolution (pixels per side)
            dem_type: 'dem' for terrain elevation (default)

        Returns:
            numpy array of elevation values in meters
        """
        if not await self.is_available():
            return None

        # Check cache
        cache_key = self._get_cache_key(
            bbox, "elevation", resolution=resolution, dem_type=dem_type
        )
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            # Select best dataset based on area
            dataset = self._select_dataset(bbox)

            # Build request parameters
            params = {
                "demtype": dataset,
                "south": bbox.south,
                "north": bbox.north,
                "west": bbox.west,
                "east": bbox.east,
                "outputFormat": "GTiff",
                "API_Key": self.config.api_key,
            }

            # Make async HTTP request
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()

                # Read GeoTIFF from response
                geotiff_data = BytesIO(response.content)

                # Use rasterio to read elevation data
                with rasterio.open(geotiff_data) as dataset:
                    elevation = dataset.read(1)  # Read first band

                    # Resample to requested resolution if needed
                    if elevation.shape != (resolution, resolution):
                        from scipy.ndimage import zoom

                        zoom_factor = (
                            resolution / elevation.shape[0],
                            resolution / elevation.shape[1],
                        )
                        elevation = zoom(elevation, zoom_factor, order=1)

                # Cache and return
                self._set_cached(cache_key, elevation)
                return elevation

        except httpx.HTTPStatusError as e:
            print(f"OpenTopography HTTP error: {e.response.status_code}")
            return None
        except Exception as e:
            print(f"OpenTopography elevation retrieval failed: {e}")
            return None

    async def get_imagery_data(
        self,
        bbox: BoundingBox,
        resolution: int,
        bands: list[str] = None,
    ) -> Optional[np.ndarray]:
        """OpenTopography does not provide imagery data"""
        return None

    async def get_vector_data(
        self,
        bbox: BoundingBox,
        feature_types: list[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """OpenTopography does not provide vector data"""
        return None

    def _select_dataset(self, bbox: BoundingBox) -> str:
        """
        Select best dataset based on geographic coverage.

        Priority:
        1. SRTMGL1 (30m) for latitudes between 60N and 60S
        2. AW3D30 (30m) for other areas
        3. SRTMGL3 (90m) as fallback
        """
        lat_center = (bbox.north + bbox.south) / 2

        # Use SRTM GL1 if within coverage
        if -60 <= lat_center <= 60:
            return "SRTMGL1"

        # Use ALOS World 3D otherwise
        return "AW3D30"

    async def get_slope_data(
        self, bbox: BoundingBox, resolution: int
    ) -> Optional[np.ndarray]:
        """
        Calculate slope from elevation data.

        Returns:
            numpy array of slope values in degrees (0-90)
        """
        elevation = await self.get_elevation_data(bbox, resolution)
        if elevation is None:
            return None

        # Calculate slope using gradient
        dy, dx = np.gradient(elevation)
        slope = np.degrees(np.arctan(np.sqrt(dx**2 + dy**2)))

        return slope

    async def get_aspect_data(
        self, bbox: BoundingBox, resolution: int
    ) -> Optional[np.ndarray]:
        """
        Calculate aspect (direction of slope) from elevation data.

        Returns:
            numpy array of aspect values in degrees (0-360)
            0 = North, 90 = East, 180 = South, 270 = West
        """
        elevation = await self.get_elevation_data(bbox, resolution)
        if elevation is None:
            return None

        # Calculate aspect using gradient
        dy, dx = np.gradient(elevation)
        aspect = np.degrees(np.arctan2(-dx, dy))

        # Convert to 0-360 range
        aspect = (aspect + 360) % 360

        return aspect

    def get_dataset_info(self, dataset_name: str = None) -> Dict[str, Any]:
        """
        Get information about available datasets.

        Args:
            dataset_name: Specific dataset name, or None for all

        Returns:
            Dictionary with dataset information
        """
        if dataset_name:
            return self.DATASETS.get(dataset_name, {})
        return self.DATASETS

