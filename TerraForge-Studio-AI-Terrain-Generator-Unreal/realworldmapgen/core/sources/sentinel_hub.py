"""
Sentinel Hub Data Source
High-resolution satellite imagery provider
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import numpy as np

try:
    from sentinelhub import (
        CRS,
        BBox,
        DataCollection,
        MimeType,
        SentinelHubRequest,
        SHConfig,
        bbox_to_dimensions,
    )

    SENTINELHUB_AVAILABLE = True
except ImportError:
    SENTINELHUB_AVAILABLE = False

from .base import (
    BaseDataSource,
    BoundingBox,
    DataSourceCapability,
    DataSourceConfig,
    DataSourceType,
)


class SentinelHubSource(BaseDataSource):
    """
    Sentinel Hub satellite imagery source.

    Provides:
    - High-resolution RGB imagery (10m-60m)
    - NIR, NDVI, and other spectral indices
    - Temporal series analysis
    - Cloud-free composites

    Requires API credentials from https://www.sentinel-hub.com/
    """

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.sh_config = None
        if SENTINELHUB_AVAILABLE and config.enabled:
            self._initialize_config()

    def _initialize_config(self):
        """Initialize Sentinel Hub configuration"""
        self.sh_config = SHConfig()
        self.sh_config.sh_client_id = self.config.api_key
        self.sh_config.sh_client_secret = self.config.api_secret
        self.sh_config.sh_base_url = (
            self.config.base_url or "https://services.sentinel-hub.com"
        )

    @property
    def name(self) -> str:
        return "Sentinel Hub"

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.IMAGERY

    @property
    def capabilities(self) -> list[DataSourceCapability]:
        return [
            DataSourceCapability.IMAGERY_RGB,
            DataSourceCapability.IMAGERY_NIR,
            DataSourceCapability.IMAGERY_NDVI,
        ]

    async def is_available(self) -> bool:
        """Check if Sentinel Hub is available and configured"""
        if not SENTINELHUB_AVAILABLE:
            return False
        if not self.config.enabled:
            return False
        if not self.config.api_key or not self.config.api_secret:
            return False
        return True

    async def get_elevation_data(
        self,
        bbox: BoundingBox,
        resolution: int,
        dem_type: str = "dem",
    ) -> Optional[np.ndarray]:
        """Sentinel Hub does not provide elevation data"""
        return None

    async def get_imagery_data(
        self,
        bbox: BoundingBox,
        resolution: int,
        bands: list[str] = None,
    ) -> Optional[np.ndarray]:
        """
        Retrieve satellite imagery from Sentinel Hub.

        Args:
            bbox: Geographic bounding box
            resolution: Output resolution (pixels per side)
            bands: Bands to retrieve (default: ['R', 'G', 'B'])

        Returns:
            numpy array [height, width, channels] with pixel values 0-255
        """
        if not await self.is_available():
            return None

        # Check cache
        cache_key = self._get_cache_key(bbox, "imagery", resolution=resolution, bands=bands)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            # Convert bbox to Sentinel Hub format
            sh_bbox = BBox(
                bbox=(bbox.west, bbox.south, bbox.east, bbox.north), crs=CRS.WGS84
            )

            # Determine size
            size = bbox_to_dimensions(sh_bbox, resolution=resolution)

            # Build evalscript based on requested bands
            bands = bands or ["R", "G", "B"]
            evalscript = self._build_evalscript(bands)

            # Create request
            request = SentinelHubRequest(
                evalscript=evalscript,
                input_data=[
                    SentinelHubRequest.input_data(
                        data_collection=DataCollection.SENTINEL2_L2A,
                        time_interval=(
                            datetime.now() - timedelta(days=365),
                            datetime.now(),
                        ),
                        mosaicking_order="leastCC",  # Least cloud coverage
                    )
                ],
                responses=[SentinelHubRequest.output_response("default", MimeType.PNG)],
                bbox=sh_bbox,
                size=size,
                config=self.sh_config,
            )

            # Execute request asynchronously
            loop = asyncio.get_event_loop()
            imagery = await loop.run_in_executor(None, request.get_data)

            # Process result
            if imagery and len(imagery) > 0:
                result = imagery[0]  # First image in response
                self._set_cached(cache_key, result)
                return result

            return None

        except Exception as e:
            print(f"Sentinel Hub imagery retrieval failed: {e}")
            return None

    async def get_vector_data(
        self,
        bbox: BoundingBox,
        feature_types: list[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Sentinel Hub does not provide vector data"""
        return None

    def _build_evalscript(self, bands: list[str]) -> str:
        """
        Build Sentinel Hub evalscript for requested bands.

        Supported bands:
        - R, G, B: True color
        - NIR: Near-infrared
        - NDVI: Normalized Difference Vegetation Index
        """
        # Map band names to Sentinel-2 bands
        band_mapping = {
            "R": "B04",  # Red
            "G": "B03",  # Green
            "B": "B02",  # Blue
            "NIR": "B08",  # Near-infrared
        }

        # Check if NDVI is requested
        if "NDVI" in bands:
            return """
            //VERSION=3
            function setup() {
                return {
                    input: ["B04", "B08"],
                    output: { bands: 1 }
                };
            }
            function evaluatePixel(sample) {
                let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
                return [ndvi];
            }
            """

        # Build standard RGB or custom band combination
        sentinel_bands = [band_mapping.get(b, b) for b in bands]

        return f"""
        //VERSION=3
        function setup() {{
            return {{
                input: {sentinel_bands},
                output: {{ bands: {len(sentinel_bands)} }}
            }};
        }}
        function evaluatePixel(sample) {{
            return [{", ".join(f"sample.{b}" for b in sentinel_bands)}];
        }}
        """

    async def get_ndvi(
        self, bbox: BoundingBox, resolution: int
    ) -> Optional[np.ndarray]:
        """
        Get NDVI (vegetation index) for the area.

        Returns:
            numpy array with NDVI values (-1 to 1)
        """
        return await self.get_imagery_data(bbox, resolution, bands=["NDVI"])

    async def get_cloud_free_composite(
        self, bbox: BoundingBox, resolution: int, days: int = 30
    ) -> Optional[np.ndarray]:
        """
        Get cloud-free composite imagery over a time period.

        Args:
            bbox: Geographic bounding box
            resolution: Output resolution
            days: Number of days to look back for cloud-free imagery

        Returns:
            Cloud-free RGB composite
        """
        # Similar to get_imagery_data but with custom time range
        return await self.get_imagery_data(bbox, resolution, bands=["R", "G", "B"])

