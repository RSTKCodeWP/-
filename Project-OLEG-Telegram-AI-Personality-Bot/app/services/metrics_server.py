"""Simple HTTP server for Prometheus metrics endpoint."""

import asyncio
import logging
import time
from aiohttp import web

from app.services.metrics import metrics
from app.config import settings

logger = logging.getLogger(__name__)

# Global bot health state
_bot_health = {
    "polling_active": False,
    "last_update_time": 0.0,
    "startup_time": time.time(),
}


class MetricsServer:
    """HTTP server for exposing Prometheus metrics."""

    def __init__(self, host: str = "0.0.0.0", port: int = 9090):
        self.host = host
        self.port = port
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    async def _handle_metrics(self, request: web.Request) -> web.Response:
        """Handle /metrics endpoint."""
        try:
            metrics_text = await metrics.get_metrics()
            return web.Response(
                text=metrics_text,
                content_type="text/plain; charset=utf-8"
            )
        except Exception as e:
            logger.error(f"Error generating metrics: {e}")
            return web.Response(text="# Error generating metrics", status=500)

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Handle /health endpoint for K8s probes.
        
        Returns unhealthy if:
        - Polling is not active
        - No updates received for more than 5 minutes (after startup grace period)
        """
        import json
        
        now = time.time()
        uptime = now - _bot_health["startup_time"]
        
        # Grace period: 2 minutes after startup
        grace_period = 120
        # Max time without updates before considered unhealthy
        max_idle_time = 300  # 5 minutes
        
        is_healthy = True
        reason = "ok"
        
        if not _bot_health["polling_active"]:
            is_healthy = False
            reason = "polling_not_active"
        elif uptime > grace_period:
            # After grace period, check if we're receiving updates
            time_since_update = now - _bot_health["last_update_time"]
            if _bot_health["last_update_time"] > 0 and time_since_update > max_idle_time:
                # Only fail if we HAD updates before but stopped getting them
                is_healthy = False
                reason = f"no_updates_for_{int(time_since_update)}s"
        
        status_code = 200 if is_healthy else 503
        response_data = {
            "status": "healthy" if is_healthy else "unhealthy",
            "reason": reason,
            "polling_active": _bot_health["polling_active"],
            "uptime_seconds": int(uptime),
        }
        
        return web.Response(
            text=json.dumps(response_data),
            content_type="application/json",
            status=status_code
        )

    async def _handle_ready(self, request: web.Request) -> web.Response:
        """Handle /ready endpoint for K8s readiness probe."""
        # Check if bot is ready (could add more checks here)
        return web.Response(
            text='{"status": "ready"}',
            content_type="application/json"
        )

    async def start(self):
        """Start the metrics HTTP server."""
        self._app = web.Application()
        self._app.router.add_get("/metrics", self._handle_metrics)
        self._app.router.add_get("/health", self._handle_health)
        self._app.router.add_get("/healthz", self._handle_health)
        self._app.router.add_get("/ready", self._handle_ready)
        self._app.router.add_get("/readyz", self._handle_ready)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

        logger.info(f"Metrics server started at http://{self.host}:{self.port}")
        logger.info(f"  - Metrics: http://{self.host}:{self.port}/metrics")
        logger.info(f"  - Health:  http://{self.host}:{self.port}/health")
        logger.info(f"  - Ready:   http://{self.host}:{self.port}/ready")

    async def stop(self):
        """Stop the metrics HTTP server."""
        if self._runner:
            await self._runner.cleanup()
            logger.info("Metrics server stopped")


# Global metrics server instance
metrics_server = MetricsServer()


def set_polling_active(active: bool) -> None:
    """Set polling status for health checks."""
    _bot_health["polling_active"] = active
    if active:
        _bot_health["last_update_time"] = time.time()
    logger.debug(f"Polling status set to: {active}")


def record_update_received() -> None:
    """Record that an update was received from Telegram."""
    _bot_health["last_update_time"] = time.time()
