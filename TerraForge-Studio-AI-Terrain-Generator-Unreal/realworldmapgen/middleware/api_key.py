"""
API key middleware.

``API_KEY_ENABLED`` and ``API_KEYS`` have been documented in ``.env.example``
for a long time while nothing read them, so setting them changed nothing. This
middleware makes them real: when enabled, every ``/api`` request must present a
configured key.

The gate is deployment-level, not per-user. It is independent of the session
authentication in :mod:`realworldmapgen.core.auth_manager`, and the two
compose: send the key in ``X-API-Key`` and the session token in
``Authorization``.
"""

from __future__ import annotations

import hmac
import logging
from typing import Iterable, Optional, Sequence, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

#: Reachable without a key: orchestrator probes, metrics scrapes and the
#: schema/docs endpoints that make the API discoverable.
DEFAULT_EXEMPT_PATHS: Tuple[str, ...] = (
    "/health",
    "/metrics",
    "/api/health",
    "/docs",
    "/redoc",
    "/openapi.json",
)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Requires a valid API key on ``/api`` requests."""

    def __init__(
        self,
        app,
        api_keys: Optional[Sequence[str]] = None,
        exempt_paths: Optional[Iterable[str]] = None,
    ):
        super().__init__(app)
        self.api_keys = tuple(key for key in (api_keys or ()) if key)
        self.exempt_paths = tuple(
            exempt_paths if exempt_paths is not None else DEFAULT_EXEMPT_PATHS
        )

        if not self.api_keys:
            # Fail closed rather than silently letting everything through: an
            # operator who turned the gate on must not end up with an open API
            # because the key list was empty.
            logger.error(
                "API_KEY_ENABLED is true but API_KEYS is empty - every /api "
                "request will be rejected until at least one key is configured"
            )

    def is_exempt(self, path: str) -> bool:
        """Whether a path is reachable without a key."""
        if any(path == prefix or path.startswith(prefix + "/") for prefix in self.exempt_paths):
            return True
        # Only the API is gated; the bundled frontend still has to load. The
        # prefix is matched loosely on purpose: a future route at /apikeys
        # should be gated by default rather than exposed by a missing slash.
        # No frontend asset lives under /api.
        return not path.startswith("/api")

    def extract_key(self, request: Request) -> Optional[str]:
        """Read the presented key from ``X-API-Key`` or a bearer token."""
        header = request.headers.get("X-API-Key")
        if header:
            return header.strip()

        authorization = request.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            return authorization[len("Bearer ") :].strip()
        return None

    def is_valid(self, presented: Optional[str]) -> bool:
        if not presented:
            return False
        # compare_digest against every key: a plain == would leak the shared
        # prefix through timing.
        return any(hmac.compare_digest(presented, known) for known in self.api_keys)

    async def dispatch(self, request: Request, call_next):
        if self.is_exempt(request.url.path):
            return await call_next(request)

        if not self.is_valid(self.extract_key(request)):
            logger.info("Rejected unkeyed request to %s", request.url.path)
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Unauthorized",
                    "message": "A valid API key is required. Send it as X-API-Key.",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)
