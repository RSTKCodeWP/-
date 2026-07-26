"""
Settings Data Models
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class Language(str, Enum):
    """Supported languages"""
    EN = "en"
    RU = "ru"


class Theme(str, Enum):
    """UI themes"""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


class ExportEngine(str, Enum):
    """Export engines"""
    UNREAL5 = "unreal5"
    UNITY = "unity"
    GENERIC = "generic"


# ========================================
# Data Source Credentials
# ========================================

class SentinelHubCredentials(BaseModel):
    """Sentinel Hub API credentials"""
    enabled: bool = False
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    instance_id: Optional[str] = None


class OpenTopographyCredentials(BaseModel):
    """OpenTopography API credentials"""
    enabled: bool = False
    api_key: Optional[str] = None


class AzureMapsCredentials(BaseModel):
    """Azure Maps API credentials"""
    enabled: bool = False
    subscription_key: Optional[str] = None


class GoogleEarthEngineCredentials(BaseModel):
    """Google Earth Engine credentials"""
    enabled: bool = False
    service_account: Optional[str] = None
    private_key_path: Optional[str] = None


class DataSourceCredentials(BaseModel):
    """All data source credentials"""
    sentinelhub: SentinelHubCredentials = Field(default_factory=SentinelHubCredentials)
    opentopography: OpenTopographyCredentials = Field(default_factory=OpenTopographyCredentials)
    azure_maps: AzureMapsCredentials = Field(default_factory=AzureMapsCredentials)
    google_earth_engine: GoogleEarthEngineCredentials = Field(default_factory=GoogleEarthEngineCredentials)


# ========================================
# Generation Defaults
# ========================================

class GenerationDefaults(BaseModel):
    """Default parameters for terrain generation"""

    # Resolution
    default_resolution: int = Field(2048, ge=512, le=8192)

    # Area limits
    max_area_km2: float = Field(100.0, gt=0, le=500.0)

    # Elevation source priority (ordered list)
    elevation_source_priority: List[str] = Field(
        default=["opentopography", "srtm", "aster"]
    )

    # Default features
    enable_roads: bool = True
    enable_buildings: bool = True
    enable_vegetation: bool = True
    enable_weightmaps: bool = True
    enable_water_bodies: bool = True

    # Processing
    parallel_processing: bool = True
    max_workers: int = Field(4, ge=1, le=16)

    @validator('elevation_source_priority')
    def validate_sources(cls, v):
        valid = ['opentopography', 'srtm', 'aster', 'azure_maps', 'sentinelhub']
        for source in v:
            if source not in valid:
                raise ValueError(f"Invalid elevation source: {source}")
        return v


# ========================================
# Export Profiles
# ========================================

class Unreal5Profile(BaseModel):
    """Unreal Engine 5 export settings"""
    default_landscape_size: int = Field(2017, description="1009, 2017, 4033, 8129")
    heightmap_format: str = Field("16bit_png", description="16bit_png or raw")
    export_weightmaps: bool = True
    export_splines: bool = True
    generate_import_script: bool = True

    @validator('default_landscape_size')
    def validate_size(cls, v):
        valid_sizes = [1009, 2017, 4033, 8129]
        if v not in valid_sizes:
            raise ValueError(f"Size must be one of {valid_sizes}")
        return v


class UnityProfile(BaseModel):
    """Unity export settings"""
    default_terrain_size: int = Field(2049, description="513, 1025, 2049, 4097")
    heightmap_format: str = Field("raw", description="raw or 16bit_png")
    export_splatmaps: bool = True
    export_prefabs: bool = True
    generate_import_script: bool = True

    @validator('default_terrain_size')
    def validate_size(cls, v):
        valid_sizes = [513, 1025, 2049, 4097]
        if v not in valid_sizes:
            raise ValueError(f"Size must be one of {valid_sizes}")
        return v


class GenericProfile(BaseModel):
    """Generic export settings"""
    export_gltf: bool = True
    export_geotiff: bool = True
    export_obj: bool = False
    gltf_binary_format: bool = True  # GLB vs GLTF+BIN


class ExportProfiles(BaseModel):
    """Export profiles for different engines"""
    unreal5: Unreal5Profile = Field(default_factory=Unreal5Profile)
    unity: UnityProfile = Field(default_factory=UnityProfile)
    generic: GenericProfile = Field(default_factory=GenericProfile)
    default_engine: ExportEngine = ExportEngine.UNREAL5


# ========================================
# UI Preferences
# ========================================

class UIPreferences(BaseModel):
    """User interface preferences"""
    language: Language = Language.EN
    theme: Theme = Theme.LIGHT
    show_tooltips: bool = True
    show_tutorial: bool = True  # First-time wizard
    compact_mode: bool = False
    default_map_view: str = Field("2d", description="2d or 3d")


# ========================================
# Cache & Storage
# ========================================

class CacheSettings(BaseModel):
    """Cache and storage settings"""
    cache_dir: str = "./cache"
    output_dir: str = "./output"
    enable_cache: bool = True
    cache_expiry_days: int = Field(30, ge=1, le=365)
    auto_cleanup_old_projects: bool = True
    cleanup_threshold_days: int = Field(30, ge=1, le=365)


# ========================================
# Complete User Settings
# ========================================

class AISettings(BaseModel):
    """AI Assistant settings"""
    enabled: bool = False
    ollama_url: str = "http://localhost:11434"
    vision_model: str = "qwen3-vl:235b-cloud"
    coder_model: str = "qwen3-coder:480b-cloud"
    auto_analyze: bool = False
    timeout_seconds: int = 120


class UserSettings(BaseModel):
    """Complete user settings"""

    # User profile
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    # Core settings
    credentials: DataSourceCredentials = Field(default_factory=DataSourceCredentials)
    generation: GenerationDefaults = Field(default_factory=GenerationDefaults)
    export_profiles: ExportProfiles = Field(default_factory=ExportProfiles)
    ui: UIPreferences = Field(default_factory=UIPreferences)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    ai: Optional[AISettings] = Field(default_factory=AISettings)

    # Meta
    version: str = "1.0.0"
    first_run: bool = True  # Show setup wizard

    class Config:
        json_schema_extra = {
            "example": {
                "user_name": "John Doe",
                "generation": {
                    "default_resolution": 2048,
                    "max_area_km2": 100.0,
                },
                "ui": {
                    "language": "en",
                    "theme": "light",
                }
            }
        }


# ========================================
# Settings Update Models
# ========================================

class SettingsUpdate(BaseModel):
    """Partial settings update"""
    credentials: Optional[DataSourceCredentials] = None
    generation: Optional[GenerationDefaults] = None
    export_profiles: Optional[ExportProfiles] = None
    ui: Optional[UIPreferences] = None
    cache: Optional[CacheSettings] = None
    ai: Optional[AISettings] = None


class MaskedCredentials(BaseModel):
    """Credentials with masked secrets (for display)"""
    sentinelhub_enabled: bool
    sentinelhub_configured: bool
    opentopography_enabled: bool
    opentopography_configured: bool
    azure_maps_enabled: bool
    azure_maps_configured: bool
    google_earth_engine_enabled: bool
    google_earth_engine_configured: bool

