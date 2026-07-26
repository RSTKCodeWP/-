"""
FastAPI application for TerraForge Studio.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import ensure_directories, settings
from ..core.generator_provider import get_generator
from ..middleware.api_key import APIKeyMiddleware
from ..middleware.rate_limiter import RateLimitConfig, RateLimiter, RateLimitMiddleware
from ..models import GenerationStatus, MapGenerationRequest, TaskStatus
from ..packaging import create_map_archive
from .ai_routes import router as ai_router
from .auth_routes import router as auth_router
from .batch_routes import router as batch_router
from .cache_routes import router as cache_router
from .cloud_routes import router as cloud_router
from .health import router as health_router
from .plugin_routes import router as plugin_router
from .settings_routes import router as settings_router
from .share_routes import router as share_router
from .webhook_routes import router as webhook_router
from .websocket_routes import router as websocket_router

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

API_VERSION = settings.app_version

#: Frontend build output, mounted at the root when present (desktop builds).
STATIC_DIR = Path(__file__).resolve().parents[2] / "frontend-new" / "dist"

#: Files downloadable through ``/api/maps/{name}/download/{type}``.
DOWNLOADABLE_FILES = {
    "heightmap": "unreal5/{name}_heightmap.png",
    "metadata": "unreal5/{name}_metadata.json",
    "thumbnail": "thumbnail.png",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepare the runtime environment before the first request is served."""
    ensure_directories()

    generator = get_generator()

    logger.info("Starting %s API v%s", settings.app_name, API_VERSION)
    logger.info("Environment: %s", settings.environment)
    logger.info("Elevation sources: %s", ", ".join(generator.sources) or "none")
    logger.info("Output directory: %s", settings.output_dir.resolve())

    if "srtm" in generator.sources:
        logger.info("SRTM open terrain tiles enabled - no API key required")
    else:
        logger.warning(
            "No key-free elevation source is enabled; generation will fall back "
            "to synthetic terrain unless a premium source is configured"
        )

    yield

    logger.info("Shutting down %s API", settings.app_name)


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Set caching headers appropriate to each kind of response."""

    STATIC_EXTENSIONS = (".js", ".css", ".woff2", ".woff", ".ttf")
    NO_STORE = "no-cache, no-store, must-revalidate"

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path

        if path.startswith("/api") or path.endswith(".html") or path == "/":
            response.headers["Cache-Control"] = self.NO_STORE
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        elif path.endswith(self.STATIC_EXTENSIONS):
            # Vite emits content-hashed filenames under /assets, which are safe
            # to cache indefinitely. Everything else gets a short TTL.
            if "/assets/" in path and "-" in path:
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                response.headers["Cache-Control"] = "public, max-age=3600, must-revalidate"

        return response


app = FastAPI(
    title=settings.app_name,
    description=(
        "Professional cross-platform 3D terrain and real-world map generator "
        "for Unreal Engine 5, Unity, and other game engines"
    ),
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS: a wildcard origin is incompatible with credentialed requests (browsers
# reject the combination outright), so origins are listed explicitly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.resolved_cors_origins(),
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)
app.add_middleware(CacheControlMiddleware)

# Rate limiting is advertised by RATE_LIMIT_* in .env; the middleware exists,
# so it is actually attached rather than merely configurable.
if settings.rate_limit_enabled:
    app.add_middleware(
        RateLimitMiddleware,
        limiter=RateLimiter(
            RateLimitConfig(
                requests_per_minute=settings.rate_limit_per_minute,
                requests_per_hour=settings.rate_limit_per_hour,
                requests_per_day=settings.rate_limit_per_day,
                trust_forwarded_for=settings.rate_limit_trust_forwarded_for,
            )
        ),
    )

# API_KEY_ENABLED / API_KEYS were documented in .env.example while nothing
# read them. The gate is attached here so setting them has an effect.
if settings.api_key_enabled:
    app.add_middleware(APIKeyMiddleware, api_keys=settings.api_keys)

for router in (
    health_router,
    settings_router,
    batch_router,
    ai_router,
    websocket_router,
    cache_router,
    share_router,
    plugin_router,
    auth_router,
    cloud_router,
    webhook_router,
):
    app.include_router(router)


def _safe_map_dir(map_name: str) -> Path:
    """
    Resolve a map directory inside the output root.

    Names are validated at the model layer, but download endpoints take raw
    path segments, so the resolved path is re-checked against the root to
    prevent traversal outside ``output_dir``.
    """
    root = settings.output_dir.resolve()
    candidate = (root / map_name).resolve()

    if candidate != root and root not in candidate.parents:
        raise HTTPException(status_code=400, detail="Invalid map name")
    if not candidate.is_dir():
        raise HTTPException(status_code=404, detail="Map not found")

    return candidate


@app.get("/api")
@app.get("/api/")
async def api_root() -> Dict[str, Any]:
    """API root endpoint"""
    return {
        "name": settings.app_name,
        "version": API_VERSION,
        "description": "Professional cross-platform 3D terrain and real-world map generator",
        "supported_engines": ["Unreal Engine 5", "Unity", "Generic (GLTF/GeoTIFF)"],
        "endpoints": {
            "generate": "/api/generate",
            "status": "/api/status/{task_id}",
            "tasks": "/api/tasks",
            "health": "/api/health",
            "sources": "/api/sources",
            "formats": "/api/formats",
            "docs": "/docs",
        },
        "repository": "https://github.com/bobberdolle1/TerraForge-Studio",
        "documentation": "https://github.com/bobberdolle1/TerraForge-Studio/tree/main/docs",
    }


@app.get("/api/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint reporting which data sources are usable."""
    generator = get_generator()

    available: List[str] = []
    for name, source in generator.sources.items():
        try:
            if await source.is_available():
                available.append(name)
        except Exception as exc:
            logger.debug("Availability check failed for %s: %s", name, exc)

    return {
        "status": "healthy",
        "version": API_VERSION,
        "environment": settings.environment,
        "data_sources": {
            "available": available,
            "configured": list(generator.sources),
            "total": len(generator.sources),
        },
        "settings": {
            "max_area_km2": settings.max_area_km2,
            "default_resolution": settings.default_resolution,
            "synthetic_fallback": settings.allow_synthetic_fallback,
        },
    }


@app.get("/api/sources")
async def get_data_sources() -> Dict[str, Any]:
    """Get available data sources and their status"""
    generator = get_generator()
    configured = generator.sources

    return {
        "elevation": {
            "srtm": {
                "name": "SRTM / Open Terrain Tiles",
                "resolution": "30m-90m",
                "coverage": "Global",
                "cost": "Free",
                "available": "srtm" in configured,
                "requires_api_key": False,
            },
            "opentopography": {
                "name": "OpenTopography",
                "resolution": "0.5m-30m (varies by region)",
                "coverage": "Regional (LiDAR) + Global (SRTM/ASTER)",
                "cost": "Free (with API key)",
                "available": "opentopography" in configured,
                "requires_api_key": True,
            },
            "azure_maps": {
                "name": "Azure Maps Elevation API",
                "resolution": "Varies",
                "coverage": "Global",
                "cost": "Paid (with free tier)",
                "available": "azure_maps" in configured,
                "requires_api_key": True,
            },
        },
        "imagery": {
            "sentinelhub": {
                "name": "Sentinel Hub",
                "resolution": "10m-60m",
                "coverage": "Global",
                "cost": "Paid (with trial)",
                "available": "sentinelhub" in configured,
                "requires_api_key": True,
            }
        },
        "vector": {
            "overpass": {
                "name": "OpenStreetMap (Overpass)",
                "type": "Vector (roads, buildings, land use)",
                "coverage": "Global",
                "cost": "Free",
                "available": "overpass" in configured,
                "requires_api_key": False,
            },
            "openstreetmap": {
                "name": "OpenStreetMap (osmnx)",
                "type": "Vector (roads, buildings, POI)",
                "coverage": "Global",
                "cost": "Free",
                "available": "osm" in configured,
                "requires_api_key": False,
            },
            "azure_maps": {
                "name": "Azure Maps",
                "type": "Vector + POI",
                "coverage": "Global",
                "cost": "Paid (with free tier)",
                "available": "azure_maps" in configured,
                "requires_api_key": True,
            },
        },
    }


@app.get("/api/formats")
async def get_export_formats() -> Dict[str, Any]:
    """Get available export formats"""
    return {
        "formats": {
            "unreal5": {
                "name": "Unreal Engine 5",
                "description": "Landscape heightmaps, weightmaps, and splines",
                "files": ["heightmap.png", "weightmap.png", "metadata.json", "import_script.py"],
                "valid_resolutions": [1009, 2017, 4033, 8129],
                "supports_weightmaps": True,
                "supports_roads": True,
                "supports_buildings": True,
            },
            "unity": {
                "name": "Unity Engine",
                "description": "Terrain heightmaps and prefabs",
                "files": ["heightmap.raw", "splatmap.png", "metadata.json", "import_script.cs"],
                "valid_resolutions": [513, 1025, 2049, 4097],
                "supports_weightmaps": True,
                "supports_roads": True,
                "supports_buildings": True,
            },
            "gltf": {
                "name": "GLTF/GLB",
                "description": "3D mesh format (universal)",
                "files": ["terrain.glb", "metadata.json"],
                "valid_resolutions": "Any",
                "supports_weightmaps": False,
                "supports_roads": False,
                "supports_buildings": False,
            },
            "geotiff": {
                "name": "GeoTIFF",
                "description": "Georeferenced raster for GIS software",
                "files": ["elevation.tif", "metadata.json"],
                "valid_resolutions": "Any",
                "supports_weightmaps": False,
                "supports_roads": False,
                "supports_buildings": False,
            },
        }
    }


@app.post("/api/generate", response_model=GenerationStatus, status_code=202)
async def generate_terrain(
    request: MapGenerationRequest, background_tasks: BackgroundTasks
) -> GenerationStatus:
    """
    Start terrain generation.

    Returns immediately with a queued task; poll ``/api/status/{task_id}`` for
    progress and the final result.
    """
    generator = get_generator()

    logger.info(
        "Generation request '%s': formats=%s resolution=%d source=%s",
        request.name,
        [fmt.value for fmt in request.export_formats],
        request.resolution,
        request.elevation_source.value,
    )

    area_km2 = request.bbox.area_km2()
    if area_km2 > settings.max_area_km2:
        raise HTTPException(
            status_code=400,
            detail=f"Area too large: {area_km2:.2f} km² (max: {settings.max_area_km2} km²)",
        )

    status = generator.create_task(request)

    async def run_generation() -> None:
        # generate_terrain reports failures through the task status, so this
        # wrapper only guards against a crash before that handling kicks in.
        try:
            await generator.generate_terrain(request, status.task_id)
        except Exception as exc:
            logger.exception("Background generation crashed for %s", status.task_id)
            status.status = TaskStatus.FAILED
            status.error = str(exc)

    background_tasks.add_task(run_generation)
    return status


@app.get("/api/status/{task_id}", response_model=GenerationStatus)
@app.get("/api/tasks/{task_id}", response_model=GenerationStatus)
async def get_generation_status(task_id: str) -> GenerationStatus:
    """Get the current status of a generation task."""
    status = get_generator().get_task_status(task_id)

    if status is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return status


@app.get("/api/tasks")
async def list_tasks() -> Dict[str, Any]:
    """List all generation tasks, newest first."""
    tasks = get_generator().list_tasks()
    return {"count": len(tasks), "tasks": tasks}


@app.get("/api/maps")
async def list_maps() -> Dict[str, Any]:
    """List generated maps discovered in the output directory."""
    output_dir = settings.output_dir

    if not output_dir.exists():
        return {"maps": []}

    maps: List[Dict[str, Any]] = []
    for map_dir in sorted(output_dir.iterdir()):
        if not map_dir.is_dir():
            continue

        entry: Dict[str, Any] = {
            "name": map_dir.name,
            "path": str(map_dir),
            "has_thumbnail": (map_dir / "thumbnail.png").exists(),
            "formats": sorted(
                child.name for child in map_dir.iterdir() if child.is_dir()
            ),
        }

        info_file = map_dir / "info.json"
        if info_file.exists():
            try:
                entry["info"] = json.loads(info_file.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Could not read %s: %s", info_file, exc)

        maps.append(entry)

    return {"count": len(maps), "maps": maps}


@app.get("/api/maps/{map_name}/download/{file_type}")
async def download_map_file(map_name: str, file_type: str) -> FileResponse:
    """
    Download a file from a generated map.

    ``file_type`` may be ``zip`` for the whole map, or one of the keys in
    :data:`DOWNLOADABLE_FILES`.
    """
    map_dir = _safe_map_dir(map_name)

    if file_type == "zip":
        archive = create_map_archive(map_dir, settings.output_dir, map_name)
        return FileResponse(archive, media_type="application/zip", filename=archive.name)

    if file_type not in DOWNLOADABLE_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Valid types: {sorted(DOWNLOADABLE_FILES)} or 'zip'",
        )

    file_path = map_dir / DOWNLOADABLE_FILES[file_type].format(name=map_name)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File '{file_type}' not found for this map")

    return FileResponse(
        file_path, media_type="application/octet-stream", filename=file_path.name
    )


# Static frontend is mounted last so it never shadows the API routes above.
if STATIC_DIR.is_dir():
    logger.info("Mounting static frontend from %s", STATIC_DIR)
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "realworldmapgen.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )
