"""
Azure Maps Data Source
Vector data, routing, and POI from Microsoft Azure
"""

from typing import Any, Dict, Optional

import httpx
import numpy as np

from .base import (
    BaseDataSource,
    BoundingBox,
    DataSourceCapability,
    DataSourceConfig,
    DataSourceType,
)


class AzureMapsSource(BaseDataSource):
    """
    Azure Maps data source.

    Provides:
    - Vector data (roads, buildings, POI)
    - Elevation data via Elevation API
    - Routing and geocoding
    - Traffic information

    Requires subscription key from https://azure.microsoft.com/services/azure-maps/
    """

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self.base_url = config.base_url or "https://atlas.microsoft.com/map"
        self.elevation_url = "https://atlas.microsoft.com/elevation"

    @property
    def name(self) -> str:
        return "Azure Maps"

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.VECTOR

    @property
    def capabilities(self) -> list[DataSourceCapability]:
        return [
            DataSourceCapability.VECTOR_ROADS,
            DataSourceCapability.VECTOR_BUILDINGS,
            DataSourceCapability.VECTOR_POI,
            DataSourceCapability.ELEVATION_DEM,
        ]

    async def is_available(self) -> bool:
        """Check if Azure Maps is available and configured"""
        if not self.config.enabled:
            return False
        if not self.config.api_key:  # Subscription key
            return False
        return True

    async def get_elevation_data(
        self,
        bbox: BoundingBox,
        resolution: int,
        dem_type: str = "dem",
    ) -> Optional[np.ndarray]:
        """
        Retrieve elevation data from Azure Maps Elevation API.

        Uses the Get Data for Bounding Box endpoint.
        """
        if not await self.is_available():
            return None

        cache_key = self._get_cache_key(bbox, "elevation", resolution=resolution)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            # Azure Maps Elevation API endpoint
            url = f"{self.elevation_url}/lattice/json"

            # Create grid of points
            np.linspace(bbox.south, bbox.north, resolution)
            np.linspace(bbox.west, bbox.east, resolution)

            # Azure Maps accepts max 2000 points per request
            # For large resolutions, we need to chunk
            chunk_size = 40  # 40x40 = 1600 points
            if resolution > chunk_size:
                # TODO: Implement chunking for large requests
                print(
                    f"Warning: Resolution {resolution} too large for single Azure request"
                )
                return None

            # Build request
            bounds = [bbox.south, bbox.west, bbox.north, bbox.east]
            params = {
                "subscription-key": self.config.api_key,
                "api-version": "1.0",
                "bounds": ",".join(map(str, bounds)),
                "rows": resolution,
                "columns": resolution,
            }

            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                # Extract elevation values
                if "data" in data:
                    elevations = np.array(
                        [point["elevation"] for point in data["data"]]
                    )
                    elevation_grid = elevations.reshape(resolution, resolution)

                    self._set_cached(cache_key, elevation_grid)
                    return elevation_grid

            return None

        except Exception as e:
            print(f"Azure Maps elevation retrieval failed: {e}")
            return None

    async def get_imagery_data(
        self,
        bbox: BoundingBox,
        resolution: int,
        bands: list[str] = None,
    ) -> Optional[np.ndarray]:
        """Azure Maps provides satellite imagery but requires different API"""
        # Can be implemented using Render API with satellite style
        return None

    async def get_vector_data(
        self,
        bbox: BoundingBox,
        feature_types: list[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve vector data from Azure Maps.

        Uses the Search API to get POI and features.
        """
        if not await self.is_available():
            return None

        # Azure Maps uses Search API for POI
        # For full vector tiles, would use the Render API
        # This is a simplified implementation

        try:
            features = {"type": "FeatureCollection", "features": []}

            # Get POI within bounding box
            center_lat, center_lon = bbox.center
            radius_km = self._calculate_radius(bbox)

            url = "https://atlas.microsoft.com/search/poi/json"
            params = {
                "subscription-key": self.config.api_key,
                "api-version": "1.0",
                "lat": center_lat,
                "lon": center_lon,
                "radius": int(radius_km * 1000),  # Convert to meters
                "limit": 100,
            }

            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                if "results" in data:
                    for result in data["results"]:
                        feature = {
                            "type": "Feature",
                            "geometry": {
                                "type": "Point",
                                "coordinates": [
                                    result["position"]["lon"],
                                    result["position"]["lat"],
                                ],
                            },
                            "properties": {
                                "name": result.get("poi", {}).get("name", ""),
                                "category": result.get("poi", {}).get(
                                    "categories", []
                                ),
                            },
                        }
                        features["features"].append(feature)

            return features

        except Exception as e:
            print(f"Azure Maps vector data retrieval failed: {e}")
            return None

    def _calculate_radius(self, bbox: BoundingBox) -> float:
        """Calculate approximate radius in km from bounding box"""
        # Simple approximation using Pythagorean theorem
        # 1 degree ≈ 111 km at equator
        width_km = bbox.width_deg * 111 * np.cos(np.radians(bbox.center[0]))
        height_km = bbox.height_deg * 111
        radius_km = np.sqrt(width_km**2 + height_km**2) / 2
        return min(radius_km, 50)  # Max 50km radius

