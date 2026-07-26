"""
Kubernetes-style health and metrics endpoints.

Paths here match the probes in ``k8s/deployment.yml`` (``/health/live``,
``/health/ready``) and the Prometheus scrape target in ``prometheus.yml``
(``/metrics``).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Response, status

from ..config import settings

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    PSUTIL_AVAILABLE = False

router = APIRouter(tags=["health"])

STARTUP_TIME = time.time()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Basic health check; returns 200 while the service is running."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "timestamp": _now(),
        "uptime_seconds": int(time.time() - STARTUP_TIME),
    }


@router.get("/health/live")
async def liveness_check() -> Dict[str, Any]:
    """Liveness probe - the process is up and the event loop is responsive."""
    return {"status": "alive", "timestamp": _now()}


@router.get("/health/ready")
async def readiness_check(response: Response) -> Dict[str, Any]:
    """
    Readiness probe.

    Verifies what the service actually needs in order to serve a generation
    request: a writable output directory and at least one usable elevation
    source. Anything unmet returns 503, so the orchestrator keeps traffic away
    until the instance can do real work.
    """
    checks: Dict[str, Dict[str, Any]] = {}

    # Output directory must exist and be writable.
    try:
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        probe = settings.output_dir / ".readiness"
        probe.write_text("ok")
        probe.unlink()
        checks["storage"] = {"status": "healthy", "path": str(settings.output_dir)}
    except OSError as exc:
        checks["storage"] = {"status": "unhealthy", "error": str(exc)}

    # At least one elevation source has to be configured and reachable.
    try:
        from ..core.generator_provider import get_generator

        generator = get_generator()
        available = []
        for name, source in generator.sources.items():
            try:
                if await source.is_available():
                    available.append(name)
            except Exception:  # noqa: BLE001 - a broken source is simply unavailable
                continue

        checks["data_sources"] = {
            "status": "healthy" if available else "unhealthy",
            "available": available,
        }
    except Exception as exc:  # noqa: BLE001
        checks["data_sources"] = {"status": "unhealthy", "error": str(exc)}

    ready = all(check.get("status") == "healthy" for check in checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if ready else "not_ready",
        "checks": checks,
        "timestamp": _now(),
    }


@router.get("/metrics")
async def metrics() -> Dict[str, Any]:
    """System and application metrics for monitoring."""
    payload: Dict[str, Any] = {
        "application": {
            "version": settings.app_version,
            "environment": settings.environment,
            "uptime_seconds": int(time.time() - STARTUP_TIME),
            "timestamp": _now(),
        }
    }

    try:
        from ..core.generator_provider import get_generator

        tasks = get_generator().list_tasks()
        payload["application"]["tasks"] = {
            "total": len(tasks),
            "processing": sum(1 for task in tasks if task.status == "processing"),
            "completed": sum(1 for task in tasks if task.status == "completed"),
            "failed": sum(1 for task in tasks if task.status == "failed"),
        }
    except Exception:  # noqa: BLE001 - metrics must never break the endpoint
        pass

    if not PSUTIL_AVAILABLE:
        payload["system"] = {"available": False, "reason": "psutil is not installed"}
        return payload

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(str(settings.output_dir.resolve().anchor or "/"))

    payload["system"] = {
        "available": True,
        # interval=None reports usage since the previous call instead of
        # blocking the event loop for a second on every scrape.
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": memory.percent,
        "memory_used_mb": round(memory.used / (1024 * 1024), 1),
        "memory_total_mb": round(memory.total / (1024 * 1024), 1),
        "disk_percent": disk.percent,
        "disk_used_gb": round(disk.used / (1024**3), 2),
        "disk_total_gb": round(disk.total / (1024**3), 2),
    }

    return payload
