"""
Data models for TerraForge Studio.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator, model_validator


class TerrainType(str, Enum):
    """Types of terrain identified by AI"""
    FOREST = "forest"
    URBAN = "urban"
    SUBURBAN = "suburban"
    RURAL = "rural"
    WATER = "water"
    MOUNTAIN = "mountain"
    DESERT = "desert"
    INDUSTRIAL = "industrial"
    MIXED = "mixed"


class RoadType(str, Enum):
    """Types of roads from OSM"""
    MOTORWAY = "motorway"
    TRUNK = "trunk"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    RESIDENTIAL = "residential"
    SERVICE = "service"
    TRACK = "track"
    PATH = "path"
    FOOTWAY = "footway"


class BoundingBox(BaseModel):
    """Geographic bounding box in WGS84 degrees."""

    north: float = Field(..., ge=-90, le=90, description="North latitude")
    south: float = Field(..., ge=-90, le=90, description="South latitude")
    east: float = Field(..., ge=-180, le=180, description="East longitude")
    west: float = Field(..., ge=-180, le=180, description="West longitude")

    @model_validator(mode="after")
    def _check_ordering(self) -> "BoundingBox":
        """Reject degenerate or inverted boxes at the API boundary."""
        if self.north <= self.south:
            raise ValueError(
                f"north ({self.north}) must be greater than south ({self.south})"
            )
        if self.east <= self.west:
            raise ValueError(
                f"east ({self.east}) must be greater than west ({self.west}); "
                "boxes crossing the antimeridian are not supported"
            )
        return self

    def center(self) -> Tuple[float, float]:
        """Center point as ``(lat, lon)``."""
        return ((self.north + self.south) / 2, (self.east + self.west) / 2)

    def width_km(self) -> float:
        """East-west extent in kilometres at the box's mean latitude."""
        from math import cos, radians

        avg_lat = (self.north + self.south) / 2
        return abs(self.east - self.west) * 111.320 * cos(radians(avg_lat))

    def height_km(self) -> float:
        """North-south extent in kilometres."""
        return abs(self.north - self.south) * 110.574

    def area_km2(self) -> float:
        """Approximate area in square kilometres."""
        return self.width_km() * self.height_km()


class ExportFormat(str, Enum):
    """Available export formats"""
    UNREAL5 = "unreal5"
    UNITY = "unity"
    GLTF = "gltf"
    GEOTIFF = "geotiff"
    OBJ = "obj"
    ALL = "all"


class ElevationSource(str, Enum):
    """Available elevation data sources"""
    SRTM = "srtm"
    OPENTOPOGRAPHY = "opentopography"
    SENTINELHUB = "sentinelhub"
    AZURE_MAPS = "azure_maps"
    AUTO = "auto"  # Automatic selection based on availability


#: Characters allowed in a terrain name. Names become directory names, so
#: anything that could escape the output directory is rejected outright.
_SAFE_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}$"


class MapGenerationRequest(BaseModel):
    """Request to generate a terrain"""
    bbox: BoundingBox
    name: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=_SAFE_NAME_PATTERN,
        description="Terrain name (used as the output directory name)",
    )
    resolution: int = Field(
        2048, ge=64, le=8192, description="Heightmap resolution in pixels per side"
    )
    export_formats: List[ExportFormat] = Field(
        default_factory=lambda: [ExportFormat.UNREAL5],
        min_length=1,
        description="Export formats (unreal5, unity, gltf, geotiff, all)"
    )
    elevation_source: ElevationSource = Field(
        ElevationSource.AUTO,
        description="Elevation data source"
    )
    enable_ai_analysis: bool = Field(False, description="Enable AI terrain analysis (requires Ollama)")
    enable_roads: bool = Field(True, description="Generate roads")
    enable_buildings: bool = Field(True, description="Generate buildings")
    enable_vegetation: bool = Field(True, description="Generate vegetation")
    enable_water_bodies: bool = Field(True, description="Detect water bodies")
    enable_weightmaps: bool = Field(True, description="Generate material weightmaps (UE5/Unity)")
    enable_3d_preview: bool = Field(False, description="Generate 3D preview")

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("export_formats")
    @classmethod
    def _dedupe_formats(cls, value: List[ExportFormat]) -> List[ExportFormat]:
        """Drop duplicates while preserving the caller's ordering."""
        seen: set = set()
        unique: List[ExportFormat] = []
        for fmt in value:
            if fmt not in seen:
                seen.add(fmt)
                unique.append(fmt)
        return unique


class AIAnalysisResult(BaseModel):
    """Result from AI terrain analysis"""
    terrain_type: TerrainType
    dominant_features: List[str]
    building_density: float = Field(0.0, ge=0.0, le=1.0)
    vegetation_density: float = Field(0.0, ge=0.0, le=1.0)
    road_density: float = Field(0.0, ge=0.0, le=1.0)
    suggestions: List[str] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class RoadSegment(BaseModel):
    """A road segment"""
    osm_id: str
    road_type: RoadType
    geometry: List[Tuple[float, float]]  # List of (lat, lon) points
    name: Optional[str] = None
    lanes: int = 1
    width: float = 3.5  # meters
    max_speed: Optional[int] = None  # km/h
    oneway: bool = False
    surface: Optional[str] = None


class TrafficLight(BaseModel):
    """Traffic light placement"""
    position: Tuple[float, float]  # (lat, lon)
    osm_id: Optional[str] = None
    intersection_id: Optional[str] = None
    direction: Optional[float] = None  # degrees


class ParkingLot(BaseModel):
    """Parking lot"""
    osm_id: str
    geometry: List[Tuple[float, float]]  # Polygon points
    capacity: Optional[int] = None
    surface: Optional[str] = None
    parking_type: str = "surface"  # surface, underground, multi-storey


class Building(BaseModel):
    """Building structure"""
    osm_id: str
    geometry: List[Tuple[float, float]]  # Polygon points
    height: Optional[float] = None  # meters
    levels: Optional[int] = None
    building_type: Optional[str] = None


class VegetationArea(BaseModel):
    """Vegetation area"""
    geometry: List[Tuple[float, float]]  # Polygon points
    vegetation_type: str  # tree, grass, bush
    density: float = 0.5


class TrafficRoute(BaseModel):
    """AI-optimized traffic route"""
    waypoints: List[Tuple[float, float]]
    route_type: str = "primary"  # primary, secondary, local
    total_distance: float = 0.0  # in meters
    avg_speed: float = 50.0  # km/h
    priority: float = 1.0  # 0.0-1.0


class MapData(BaseModel):
    """Complete map data structure"""
    name: str
    bbox: BoundingBox
    ai_analysis: Optional[AIAnalysisResult] = None
    heightmap_path: Optional[str] = None
    roads: List[RoadSegment] = Field(default_factory=list)
    traffic_lights: List[TrafficLight] = Field(default_factory=list)
    parking_lots: List[ParkingLot] = Field(default_factory=list)
    buildings: List[Building] = Field(default_factory=list)
    vegetation: List[VegetationArea] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskStatus(str, Enum):
    """Lifecycle states of a generation task."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ElevationProvenance(BaseModel):
    """Where the elevation data actually came from."""

    source: str = Field(..., description="Identifier of the source that supplied the data")
    synthetic: bool = Field(
        False,
        description="True when the heightmap is procedurally generated rather "
                    "than derived from real-world measurements",
    )
    min_elevation_m: float = 0.0
    max_elevation_m: float = 0.0


class ExportResult(BaseModel):
    """Outcome of exporting to a single target format."""

    format: str
    success: bool
    directory: Optional[str] = None
    files: Dict[str, str] = Field(default_factory=dict)
    error: Optional[str] = None


class VectorSummary(BaseModel):
    """Vector features retrieved for a generation and where they were written."""

    source: str = Field(..., description="Identifier of the source that supplied the features")
    roads: int = 0
    buildings: int = 0
    landuse: int = 0
    #: GeoJSON file inside the output directory, included in the zip download.
    path: Optional[str] = None

    @property
    def total(self) -> int:
        return self.roads + self.buildings + self.landuse


class GenerationResult(BaseModel):
    """Summary of a completed generation, returned to API clients."""

    terrain_name: str
    resolution: int
    area_km2: float
    bbox: BoundingBox
    elevation: ElevationProvenance
    vectors: Optional[VectorSummary] = None
    exports: List[ExportResult] = Field(default_factory=list)
    output_directory: str
    thumbnail_path: Optional[str] = None
    thumbnail_base64: Optional[str] = None
    duration_seconds: Optional[float] = None
    cached: bool = False

    @property
    def successful_exports(self) -> List[ExportResult]:
        return [export for export in self.exports if export.success]


class GenerationStatus(BaseModel):
    """Status of map generation"""
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = Field(0.0, ge=0.0, le=100.0)
    current_step: str = ""
    message: Optional[str] = None
    result: Optional[GenerationResult] = None
    error: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    download_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def add_warning(self, warning: str) -> None:
        """Record a non-fatal issue, skipping duplicates."""
        if warning not in self.warnings:
            self.warnings.append(warning)
