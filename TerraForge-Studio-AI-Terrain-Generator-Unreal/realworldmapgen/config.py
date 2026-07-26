"""
Configuration management for TerraForge Studio.

Settings are loaded from (in order of precedence):
  1. Environment variables
  2. The ``.env`` file in the working directory
  3. The defaults declared below

Every key documented in ``.env.example`` has a typed field here, and unknown
keys are ignored rather than rejected, so an ``.env`` that is ahead of (or
behind) the code never prevents the application from starting.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, List, Literal, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

#: List fields are parsed by :func:`_split_list` rather than by the built-in
#: JSON decoder, so both ``["a","b"]`` and ``a,b`` work in ``.env`` files.
StrList = Annotated[List[str], NoDecode]


def _split_list(value: Any) -> Any:
    """Parse a list field from JSON (``["a","b"]``) or CSV (``a,b``) form."""
    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    return [item.strip() for item in text.split(",") if item.strip()]


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Ignore unknown keys instead of raising: an ``.env`` copied from
        # ``.env.example`` must never break application startup.
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    app_name: str = "TerraForge Studio"
    app_version: str = "2.0.0"
    environment: Literal["development", "staging", "production"] = "development"

    # ------------------------------------------------------------------
    # API server
    # ------------------------------------------------------------------
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_reload: bool = False

    frontend_url: str = "http://localhost:5173"
    cors_origins: StrList = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "tauri://localhost",
    ]
    cors_allow_credentials: bool = True
    cors_allow_methods: StrList = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    cors_allow_headers: StrList = ["*"]

    # ------------------------------------------------------------------
    # Directories
    # ------------------------------------------------------------------
    output_dir: Path = Path("output")
    cache_dir: Path = Path("cache")
    temp_dir: Path = Path("temp")
    plugin_dir: Path = Path("plugins")
    log_file: Optional[Path] = None

    # ------------------------------------------------------------------
    # Terrain generation
    # ------------------------------------------------------------------
    default_resolution: int = 2048
    min_resolution: int = 64
    max_resolution: int = 8192
    default_scale: float = 1.0
    max_area_km2: float = 100.0
    default_area_km2: float = 10.0

    #: Ordered list of elevation sources tried when the request asks for ``auto``.
    elevation_source_priority: StrList = ["opentopography", "azure_maps", "srtm"]

    #: When every configured source fails, fall back to procedural terrain.
    #: Results are always flagged as synthetic so callers can tell them apart.
    allow_synthetic_fallback: bool = True

    # ------------------------------------------------------------------
    # SRTM / open terrain tiles (free, no API key required)
    # ------------------------------------------------------------------
    srtm_enabled: bool = True
    srtm_tile_url: str = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
    srtm_max_zoom: int = 14
    srtm_max_tiles: int = 256
    srtm_concurrency: int = 8
    srtm_timeout: int = 30
    srtm_tile_cache_enabled: bool = True

    # ------------------------------------------------------------------
    # Sentinel Hub
    # ------------------------------------------------------------------
    sentinelhub_enabled: bool = False
    sentinelhub_client_id: Optional[str] = None
    sentinelhub_client_secret: Optional[str] = None
    sentinelhub_instance_id: Optional[str] = None

    # ------------------------------------------------------------------
    # OpenTopography
    # ------------------------------------------------------------------
    opentopography_enabled: bool = False
    opentopography_api_key: Optional[str] = None

    # ------------------------------------------------------------------
    # Azure Maps
    # ------------------------------------------------------------------
    azure_maps_enabled: bool = False
    azure_maps_subscription_key: Optional[str] = None

    # ------------------------------------------------------------------
    # Google Earth Engine
    # ------------------------------------------------------------------
    google_earth_engine_enabled: bool = False
    google_earth_engine_service_account: Optional[str] = None
    google_earth_engine_private_key_path: Optional[Path] = None

    # ------------------------------------------------------------------
    # OpenStreetMap
    # ------------------------------------------------------------------
    #: Vector features (roads, buildings) over plain HTTP via Overpass.
    #: Needs no API key and no geospatial stack, so it is the default path.
    overpass_enabled: bool = True
    overpass_endpoints: StrList = [
        "https://overpass-api.de/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]
    overpass_timeout: int = 90
    #: Overpass is a shared public service; larger areas are skipped rather
    #: than submitted.
    overpass_max_area_km2: float = 25.0

    #: The osmnx-backed path. Richer, but requires the optional extras.
    osm_enabled: bool = True
    osm_user_agent: str = "TerraForge-Studio/2.0"
    osm_cache_enabled: bool = True
    osm_timeout: int = 180

    # ------------------------------------------------------------------
    # Cloud storage (optional)
    # ------------------------------------------------------------------
    s3_enabled: bool = False
    s3_bucket_name: Optional[str] = None
    s3_region: str = "us-east-1"
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None

    azure_blob_enabled: bool = False
    azure_blob_container: Optional[str] = None
    azure_blob_account_name: Optional[str] = None
    azure_blob_account_key: Optional[str] = None
    azure_blob_connection_string: Optional[str] = None

    # ------------------------------------------------------------------
    # Export defaults
    # ------------------------------------------------------------------
    ue5_heightmap_format: Literal["16bit_png", "raw"] = "16bit_png"
    ue5_default_landscape_size: int = 2017
    ue5_export_weightmaps: bool = True

    unity_heightmap_format: Literal["raw", "16bit_png"] = "raw"
    unity_default_terrain_size: int = 2049
    unity_export_splatmaps: bool = True

    #: Upper bound on GLTF mesh vertices per side. Meshes are decimated to this
    #: size before triangulation, which keeps exports of large terrains usable.
    gltf_max_mesh_resolution: int = 512

    # ------------------------------------------------------------------
    # Caching
    # ------------------------------------------------------------------
    enable_cache: bool = True
    cache_expiry_days: int = 30
    cache_max_size_gb: float = 10.0

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------
    parallel_processing: bool = True
    max_workers: int = 4
    chunk_size: int = 1024

    # ------------------------------------------------------------------
    # AI (optional)
    # ------------------------------------------------------------------
    ollama_enabled: bool = False
    ollama_host: str = "http://localhost:11434"
    ollama_vision_model: str = "qwen3-vl:235b-cloud"
    ollama_coder_model: str = "qwen3-coder:480b-cloud"
    ollama_timeout: int = 300
    enable_ai_analysis: bool = False

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["text", "json"] = "text"

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------
    api_key_enabled: bool = False
    api_keys: StrList = []

    #: Where user accounts are persisted. Deliberately outside the cache
    #: directory, which callers may reasonably clear.
    auth_storage_file: Path = Path("data/users.json")

    #: Where the settings UI persists its configuration, including the
    #: credentials it encrypts.
    settings_storage_file: Path = Path("data/settings.json")

    #: The Fernet key that encrypts stored credentials. Generated on first use
    #: and never regenerated; losing it means stored credentials cannot be
    #: decrypted and have to be re-entered.
    secret_key_file: Path = Path("data/.secret_key")

    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000
    rate_limit_per_day: int = 10000
    #: Only enable behind a reverse proxy that overwrites X-Forwarded-For.
    #: Trusting it when clients can set it themselves makes the limit
    #: bypassable by rotating the header value.
    rate_limit_trust_forwarded_for: bool = False

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator(
        "cors_origins",
        "cors_allow_methods",
        "cors_allow_headers",
        "elevation_source_priority",
        "overpass_endpoints",
        "api_keys",
        mode="before",
    )
    @classmethod
    def _parse_list(cls, value: Any) -> Any:
        return _split_list(value)

    @field_validator("log_format", "environment", mode="before")
    @classmethod
    def _normalize_enum_value(cls, value: Any) -> Any:
        """Tolerate ``text  # comment`` and mixed case in ``.env`` files."""
        if isinstance(value, str):
            return value.split("#")[0].strip().lower()
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: Any) -> Any:
        """``debug`` and ``DEBUG  # verbose`` both mean ``DEBUG``."""
        if isinstance(value, str):
            return value.split("#")[0].strip().upper()
        return value

    @field_validator(
        "sentinelhub_client_id",
        "sentinelhub_client_secret",
        "sentinelhub_instance_id",
        "opentopography_api_key",
        "azure_maps_subscription_key",
        "google_earth_engine_service_account",
        "google_earth_engine_private_key_path",
        "s3_bucket_name",
        "s3_access_key",
        "s3_secret_key",
        "azure_blob_container",
        "azure_blob_account_name",
        "azure_blob_account_key",
        "azure_blob_connection_string",
        "log_file",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, value: Any) -> Any:
        """Treat ``KEY=`` in an ``.env`` file as "not configured"."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("max_area_km2")
    @classmethod
    def _positive_area(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("max_area_km2 must be greater than 0")
        return value

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def azure_maps_key(self) -> Optional[str]:
        """Backwards-compatible alias for :attr:`azure_maps_subscription_key`."""
        return self.azure_maps_subscription_key

    def resolved_cors_origins(self) -> List[str]:
        """CORS origins including the configured frontend URL, de-duplicated."""
        origins = list(self.cors_origins)
        if self.frontend_url and self.frontend_url not in origins:
            origins.append(self.frontend_url)
        return origins


# Global settings instance
settings = Settings()


def ensure_directories() -> None:
    """Create the directories the application writes to."""
    for directory in (settings.output_dir, settings.cache_dir, settings.temp_dir):
        directory.mkdir(parents=True, exist_ok=True)
    if settings.log_file is not None:
        settings.log_file.parent.mkdir(parents=True, exist_ok=True)
