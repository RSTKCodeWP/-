"""
Base Exporter Abstract Class
Defines interface for all terrain export formats
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np


class ExportFormat(Enum):
    """Supported export formats"""

    UNREAL5 = "unreal5"
    UNITY = "unity"
    GLTF = "gltf"
    GEOTIFF = "geotiff"
    OBJ = "obj"
    USDZ = "usdz"


@dataclass
class TerrainData:
    """
    Container for terrain data to be exported.

    This standardized format is used by all exporters.
    """

    # Core elevation data
    heightmap: np.ndarray  # 2D array of elevation values (meters)
    resolution: int  # Pixels per side (e.g., 2048)

    # Geographic metadata
    bbox_north: float
    bbox_south: float
    bbox_east: float
    bbox_west: float
    crs: str = "EPSG:4326"  # Coordinate reference system

    # Optional material/texture data
    weightmaps: Optional[Dict[str, np.ndarray]] = None  # Material layers (R, G, B, A)
    albedo_map: Optional[np.ndarray] = None  # Color/texture map
    normal_map: Optional[np.ndarray] = None  # Normal map for detail

    # Optional vector data
    roads: Optional[Dict[str, Any]] = None  # Road network GeoJSON
    buildings: Optional[Dict[str, Any]] = None  # Building footprints GeoJSON
    vegetation: Optional[Dict[str, Any]] = None  # Tree/vegetation placement

    # Metadata
    name: str = "terrain"
    scale: float = 1.0  # Horizontal scale multiplier
    vertical_scale: float = 1.0  # Vertical scale multiplier
    min_elevation: float = 0.0
    max_elevation: float = 0.0

    def __post_init__(self):
        """Calculate min/max elevation if not provided"""
        if self.min_elevation == 0.0 and self.max_elevation == 0.0:
            self.min_elevation = float(np.min(self.heightmap))
            self.max_elevation = float(np.max(self.heightmap))


class BaseExporter(ABC):
    """
    Abstract base class for all terrain exporters.

    Each exporter must implement:
    - export()
    - validate()
    """

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Human-readable name of export format"""
        pass

    @property
    @abstractmethod
    def file_extensions(self) -> list[str]:
        """List of file extensions produced by this exporter"""
        pass

    @abstractmethod
    async def export(self, terrain_data: TerrainData) -> Dict[str, Path]:
        """
        Export terrain data to target format.

        Args:
            terrain_data: Standardized terrain data container

        Returns:
            Dictionary mapping file types to their paths
            Example: {'heightmap': Path('terrain_heightmap.png'),
                     'metadata': Path('metadata.json')}
        """
        pass

    @abstractmethod
    def validate(self, terrain_data: TerrainData) -> tuple[bool, Optional[str]]:
        """
        Validate terrain data for this export format.

        Args:
            terrain_data: Terrain data to validate

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
        """
        pass

    def create_metadata(self, terrain_data: TerrainData) -> Dict[str, Any]:
        """
        Create metadata dictionary for export.

        Common metadata used by all exporters.
        """
        return {
            "name": terrain_data.name,
            "format": self.format_name,
            "resolution": terrain_data.resolution,
            "bbox": {
                "north": terrain_data.bbox_north,
                "south": terrain_data.bbox_south,
                "east": terrain_data.bbox_east,
                "west": terrain_data.bbox_west,
            },
            "crs": terrain_data.crs,
            "elevation": {
                "min": terrain_data.min_elevation,
                "max": terrain_data.max_elevation,
                "vertical_scale": terrain_data.vertical_scale,
            },
            "scale": terrain_data.scale,
            "exported_at": self._get_timestamp(),
        }

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        from datetime import datetime

        return datetime.now().isoformat()

    def _normalize_heightmap(
        self, heightmap: np.ndarray, target_min: float, target_max: float
    ) -> np.ndarray:
        """
        Normalize heightmap values to target range.

        Args:
            heightmap: Input heightmap array
            target_min: Target minimum value
            target_max: Target maximum value

        Returns:
            Normalized heightmap
        """
        current_min = np.min(heightmap)
        current_max = np.max(heightmap)

        if current_max == current_min:
            return np.full_like(heightmap, target_min)

        normalized = (heightmap - current_min) / (current_max - current_min)
        scaled = normalized * (target_max - target_min) + target_min

        return scaled

    def _resize_heightmap(
        self, heightmap: np.ndarray, target_size: int
    ) -> np.ndarray:
        """
        Resize heightmap to target resolution.

        Uses high-quality interpolation.
        """
        if heightmap.shape[0] == target_size and heightmap.shape[1] == target_size:
            return heightmap

        from scipy.ndimage import zoom

        zoom_factor = (target_size / heightmap.shape[0], target_size / heightmap.shape[1])
        resized = zoom(heightmap, zoom_factor, order=3)  # Cubic interpolation

        return resized

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(format='{self.format_name}', output_dir='{self.output_dir}')"

