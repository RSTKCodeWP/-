"""
OpenStreetMap vector data via the Overpass API.

Talks to Overpass over plain HTTP, so roads and buildings work with nothing
beyond ``httpx``. The alternative path, :mod:`.osm_source`, needs osmnx and its
geospatial stack (geopandas, GDAL, shapely, rtree), which is a heavy install
and is why vector data was effectively unavailable on a default setup.

Responses use Overpass' ``out geom`` form, where each way carries its own
coordinate list, and are converted to GeoJSON features.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from .base import (
    BaseDataSource,
    BoundingBox,
    DataSourceCapability,
    DataSourceConfig,
    DataSourceType,
)

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

#: Highway values excluded from road extraction: footpaths and similar are not
#: drivable surfaces and would bloat the response for most use cases.
EXCLUDED_HIGHWAYS = "footway|cycleway|path|pedestrian|steps|bridleway|corridor"

#: Status codes worth another attempt: Overpass returns 429 when rate limiting
#: and 504 when a query outruns the server's budget.
RETRYABLE_STATUS = frozenset({429, 502, 503, 504})


class OverpassSource(BaseDataSource):
    """Roads, buildings and land use from OpenStreetMap, no API key required."""

    def __init__(
        self,
        config: DataSourceConfig,
        endpoints: Optional[Sequence[str]] = None,
        user_agent: str = "TerraForge-Studio/2.0",
        max_area_km2: float = 25.0,
    ):
        super().__init__(config)
        self.endpoints = tuple(endpoints) if endpoints else DEFAULT_ENDPOINTS
        self.user_agent = user_agent
        #: Overpass is a shared public service; very large bounding boxes are
        #: refused rather than submitted, to stay a good citizen.
        self.max_area_km2 = max_area_km2

    # ------------------------------------------------------------------
    # BaseDataSource interface
    # ------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "OpenStreetMap (Overpass)"

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.VECTOR

    @property
    def capabilities(self) -> List[DataSourceCapability]:
        return [
            DataSourceCapability.VECTOR_ROADS,
            DataSourceCapability.VECTOR_BUILDINGS,
            DataSourceCapability.VECTOR_LANDUSE,
        ]

    async def is_available(self) -> bool:
        if not self.config.enabled:
            return False
        try:
            import httpx  # noqa: F401
        except ImportError:
            logger.warning("httpx is not installed - Overpass source disabled")
            return False
        return True

    async def get_elevation_data(
        self, bbox: BoundingBox, resolution: int, dem_type: str = "dem"
    ) -> Optional[np.ndarray]:
        """Overpass serves vector data only."""
        return None

    async def get_imagery_data(
        self, bbox: BoundingBox, resolution: int, bands: Optional[List[str]] = None
    ) -> Optional[np.ndarray]:
        """Overpass serves vector data only."""
        return None

    async def get_vector_data(
        self,
        bbox: BoundingBox,
        feature_types: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch vector features for ``bbox``.

        Returns a GeoJSON FeatureCollection whose features carry a
        ``properties.type`` of ``road``, ``building`` or ``landuse``, or None
        when nothing could be retrieved.
        """
        feature_types = feature_types or ["roads", "buildings"]

        area = self._area_km2(bbox)
        if area > self.max_area_km2:
            logger.warning(
                "Area %.1f km² exceeds the Overpass limit of %.1f km²; skipping vector data",
                area,
                self.max_area_km2,
            )
            return None

        cache_key = self._get_cache_key(
            bbox, "vector", feature_types="_".join(sorted(feature_types))
        )
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        query = self._build_query(bbox, feature_types)
        if query is None:
            return None

        payload = await self._execute(query)
        if payload is None:
            return None

        collection = self._to_geojson(payload)
        logger.info(
            "Overpass returned %d feature(s) for %.2f km²", len(collection["features"]), area
        )

        self._set_cached(cache_key, collection)
        return collection

    # ------------------------------------------------------------------
    # Query construction
    # ------------------------------------------------------------------
    @staticmethod
    def _area_km2(bbox: BoundingBox) -> float:
        import math

        avg_lat = (bbox.north + bbox.south) / 2
        width = abs(bbox.east - bbox.west) * 111.320 * math.cos(math.radians(avg_lat))
        height = abs(bbox.north - bbox.south) * 110.574
        return width * height

    def _build_query(self, bbox: BoundingBox, feature_types: Sequence[str]) -> Optional[str]:
        """Assemble one Overpass QL query covering every requested feature type."""
        # Overpass bbox order is (south, west, north, east).
        extent = f"{bbox.south},{bbox.west},{bbox.north},{bbox.east}"
        clauses: List[str] = []

        if "roads" in feature_types:
            clauses.append(
                f'way["highway"]["highway"!~"{EXCLUDED_HIGHWAYS}"]'
                f'["access"!~"private|no"]({extent});'
            )
        if "buildings" in feature_types:
            clauses.append(f'way["building"]({extent});')
        if "landuse" in feature_types:
            clauses.append(f'way["landuse"]({extent});')

        if not clauses:
            logger.warning("No supported feature types requested: %s", list(feature_types))
            return None

        body = "\n  ".join(clauses)
        return f"[out:json][timeout:{self.config.timeout}];\n(\n  {body}\n);\nout geom;"

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------
    async def _execute(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Run a query, falling back across endpoints and retrying transient errors.

        Overpass mirrors fail independently and rate-limit aggressively, so a
        single endpoint is not dependable.
        """
        import httpx

        timeout = httpx.Timeout(self.config.timeout)
        headers = {"User-Agent": self.user_agent, "Content-Type": "text/plain; charset=utf-8"}
        attempts = max(1, self.config.retry_attempts)
        last_error: Optional[str] = None

        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            for endpoint in self.endpoints:
                for attempt in range(attempts):
                    try:
                        response = await client.post(endpoint, content=query.encode("utf-8"))

                        if response.status_code == 200:
                            return response.json()

                        last_error = f"HTTP {response.status_code}"
                        if response.status_code in RETRYABLE_STATUS:
                            logger.warning(
                                "Overpass %s from %s (attempt %d/%d)",
                                last_error,
                                endpoint,
                                attempt + 1,
                                attempts,
                            )
                            if attempt + 1 < attempts:
                                await asyncio.sleep(2**attempt)
                            continue

                        # Anything else is a hard failure for this endpoint.
                        logger.warning("Overpass %s from %s", last_error, endpoint)
                        break

                    except Exception as exc:  # noqa: BLE001 - try the next mirror
                        last_error = str(exc)
                        logger.warning("Overpass request to %s failed: %s", endpoint, exc)
                        if attempt + 1 < attempts:
                            await asyncio.sleep(2**attempt)

        logger.error("All Overpass endpoints failed. Last error: %s", last_error)
        return None

    # ------------------------------------------------------------------
    # Response conversion
    # ------------------------------------------------------------------
    @staticmethod
    def _feature_type(tags: Dict[str, Any]) -> Optional[str]:
        if "highway" in tags:
            return "road"
        if "building" in tags:
            return "building"
        if "landuse" in tags:
            return "landuse"
        return None

    @staticmethod
    def _parse_int(value: Any) -> Optional[int]:
        """Read an OSM numeric tag, which is free text and often malformed."""
        if value is None:
            return None
        try:
            # Values like "50 mph" or "2;3" appear in the wild.
            return int(str(value).split(";")[0].strip().split()[0])
        except (ValueError, IndexError):
            return None

    @classmethod
    def _to_geojson(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convert an Overpass ``out geom`` response into a FeatureCollection."""
        features: List[Dict[str, Any]] = []

        for element in payload.get("elements", []):
            if element.get("type") != "way":
                continue

            geometry = element.get("geometry") or []
            if len(geometry) < 2:
                continue

            tags = element.get("tags") or {}
            kind = cls._feature_type(tags)
            if kind is None:
                continue

            # GeoJSON is (lon, lat); Overpass reports lat/lon separately.
            coordinates = [[point["lon"], point["lat"]] for point in geometry]

            properties: Dict[str, Any] = {
                "type": kind,
                "osm_id": str(element.get("id", "")),
                "name": tags.get("name"),
            }

            if kind == "road":
                # A road is a line even when its endpoints coincide.
                geom = {"type": "LineString", "coordinates": coordinates}
                properties.update(
                    {
                        "highway": tags.get("highway"),
                        "lanes": cls._parse_int(tags.get("lanes")),
                        "maxspeed": cls._parse_int(tags.get("maxspeed")),
                        "surface": tags.get("surface"),
                        "oneway": tags.get("oneway") in ("yes", "true", "1", "-1"),
                        "bridge": "bridge" in tags,
                        "tunnel": "tunnel" in tags,
                    }
                )
            else:
                # Areas must be explicitly closed for valid GeoJSON polygons.
                ring = list(coordinates)
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
                if len(ring) < 4:
                    continue
                geom = {"type": "Polygon", "coordinates": [ring]}

                if kind == "building":
                    properties.update(
                        {
                            "building": tags.get("building"),
                            "levels": cls._parse_int(tags.get("building:levels")),
                            "height": cls._parse_int(tags.get("height")),
                        }
                    )
                else:
                    properties["landuse"] = tags.get("landuse")

            features.append({"type": "Feature", "geometry": geom, "properties": properties})

        return {"type": "FeatureCollection", "features": features}
