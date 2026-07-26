"""
Base Data Source Abstract Class
Defines interface for all geospatial data providers
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

import numpy as np

# Shapely is optional - desktop version may not have it
try:
    from shapely.geometry import box
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False
    box = None


class DataSourceType(Enum):
    """Type of geospatial data source"""

    ELEVATION = "elevation"  # DEM/DSM heightmaps
    IMAGERY = "imagery"  # Satellite/aerial imagery
    VECTOR = "vector"  # Roads, buildings, POI
    ANALYSIS = "analysis"  # Computed indices (NDVI, slope, etc.)


class DataSourceCapability(Enum):
    """Capabilities provided by data source"""

    ELEVATION_DEM = "elevation_dem"  # Digital Elevation Model
    ELEVATION_DSM = "elevation_dsm"  # Digital Surface Model
    IMAGERY_RGB = "imagery_rgb"  # True color imagery
    IMAGERY_NIR = "imagery_nir"  # Near-infrared
    IMAGERY_NDVI = "imagery_ndvi"  # Vegetation index
    VECTOR_ROADS = "vector_roads"  # Road networks
    VECTOR_BUILDINGS = "vector_buildings"  # Building footprints
    VECTOR_LANDUSE = "vector_landuse"  # Land use polygons
    VECTOR_POI = "vector_poi"  # Points of interest
    ANALYSIS_SLOPE = "analysis_slope"  # Slope calculation
    ANALYSIS_ASPECT = "analysis_aspect"  # Aspect calculation
    ANALYSIS_CLASSIFICATION = "analysis_classification"  # Land classification


@dataclass
class BoundingBox:
    """Geographic bounding box"""

    north: float
    south: float
    east: float
    west: float

    def to_shapely(self):
        """Convert to Shapely box (if shapely is available)"""
        if not SHAPELY_AVAILABLE:
            raise ImportError("shapely is not installed. Install with: pip install shapely")
        return box(self.west, self.south, self.east, self.north)

    @property
    def center(self) -> Tuple[float, float]:
        """Get center coordinates (lat, lon)"""
        lat = (self.north + self.south) / 2
        lon = (self.east + self.west) / 2
        return lat, lon

    @property
    def width_deg(self) -> float:
        """Width in degrees"""
        return self.east - self.west

    @property
    def height_deg(self) -> float:
        """Height in degrees"""
        return self.north - self.south


@dataclass
class DataSourceConfig:
    """Configuration for a data source"""

    enabled: bool = True
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: Optional[str] = None
    timeout: int = 300
    retry_attempts: int = 3
    cache_enabled: bool = True
    custom_params: Dict[str, Any] = None

    def __post_init__(self):
        if self.custom_params is None:
            self.custom_params = {}


class BaseDataSource(ABC):
    """
    Abstract base class for all geospatial data sources.

    All data sources must implement:
    - get_elevation_data()
    - get_imagery_data()
    - get_vector_data()
    - is_available()
    """

    def __init__(self, config: DataSourceConfig):
        self.config = config
        self._cache: Dict[str, Any] = {}

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the data source"""
        pass

    @property
    @abstractmethod
    def source_type(self) -> DataSourceType:
        """Primary type of data provided"""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> list[DataSourceCapability]:
        """List of capabilities supported by this source"""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """
        Check if the data source is available and configured.

        Returns:
            True if source is ready to use, False otherwise
        """
        pass

    @abstractmethod
    async def get_elevation_data(
        self,
        bbox: BoundingBox,
        resolution: int,
        dem_type: str = "dem",  # 'dem' or 'dsm'
    ) -> Optional[np.ndarray]:
        """
        Retrieve elevation data for the given bounding box.

        Args:
            bbox: Geographic bounding box
            resolution: Output resolution (pixels per side)
            dem_type: Type of elevation model ('dem' or 'dsm')

        Returns:
            numpy array of elevation values (meters), or None if unavailable
        """
        pass

    @abstractmethod
    async def get_imagery_data(
        self,
        bbox: BoundingBox,
        resolution: int,
        bands: list[str] = None,  # e.g., ['R', 'G', 'B', 'NIR']
    ) -> Optional[np.ndarray]:
        """
        Retrieve satellite/aerial imagery for the given bounding box.

        Args:
            bbox: Geographic bounding box
            resolution: Output resolution (pixels per side)
            bands: List of bands to retrieve (default RGB)

        Returns:
            numpy array of imagery (shape: [height, width, bands]), or None
        """
        pass

    @abstractmethod
    async def get_vector_data(
        self,
        bbox: BoundingBox,
        feature_types: list[str] = None,  # e.g., ['roads', 'buildings']
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve vector data (roads, buildings, etc.) for the given bounding box.

        Args:
            bbox: Geographic bounding box
            feature_types: Types of features to retrieve

        Returns:
            Dictionary of GeoJSON-like features, or None if unavailable
        """
        pass

    def _get_cache_key(self, bbox: BoundingBox, data_type: str, **kwargs) -> str:
        """Generate cache key for data request"""
        params = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return f"{self.name}_{data_type}_{bbox.north}_{bbox.south}_{bbox.east}_{bbox.west}_{params}"

    def _get_cached(self, cache_key: str) -> Optional[Any]:
        """Retrieve from cache if enabled"""
        if self.config.cache_enabled:
            return self._cache.get(cache_key)
        return None

    def _set_cached(self, cache_key: str, data: Any) -> None:
        """Store in cache if enabled"""
        if self.config.cache_enabled:
            self._cache[cache_key] = data

    async def test_connection(self) -> Tuple[bool, Optional[str]]:
        """
        Test connection to the data source.

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            is_available = await self.is_available()
            if is_available:
                return True, None
            else:
                return False, f"{self.name} is not available or not configured"
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"

    def __repr__(self) -> str:
        status = "enabled" if self.config.enabled else "disabled"
        return f"{self.__class__.__name__}(name='{self.name}', status={status})"

