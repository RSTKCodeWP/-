"""
Rate limiting middleware.

Enforces per-minute, per-hour and per-day request budgets using a sliding
window over request timestamps.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Iterable, Optional, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

#: Windows checked on every request, longest last.
_WINDOWS: Tuple[Tuple[str, int], ...] = (
    ("minute", 60),
    ("hour", 3600),
    ("day", 86400),
)


class RateLimitConfig:
    """Rate limit configuration."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        requests_per_day: int = 10000,
        trust_forwarded_for: bool = False,
        exempt_paths: Optional[Iterable[str]] = None,
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.requests_per_day = requests_per_day
        #: Only enable behind a proxy that overwrites X-Forwarded-For. When a
        #: client can set the header itself, trusting it makes the limit
        #: trivially bypassable by rotating the value.
        self.trust_forwarded_for = trust_forwarded_for
        #: Prefixes that skip the limit entirely. Orchestrator probes and
        #: metrics scrapes poll frequently and must never be throttled.
        self.exempt_paths = tuple(
            exempt_paths if exempt_paths is not None else ("/health", "/metrics")
        )

    def limit_for(self, window: str) -> int:
        return {
            "minute": self.requests_per_minute,
            "hour": self.requests_per_hour,
            "day": self.requests_per_day,
        }[window]


class RateLimiter:
    """
    Sliding-window rate limiter.

    Timestamps are kept once per client and counted against each window
    independently. An earlier implementation truncated the shared history to
    the shortest window before checking the longer ones, which made the hourly
    and daily budgets unreachable.
    """

    #: Clients idle for longer than the longest window are dropped, so the
    #: table cannot grow without bound on a long-running server.
    IDLE_EVICTION_SECONDS = 86400
    #: How often eviction runs, in requests handled.
    EVICTION_INTERVAL = 1000

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self._requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._since_eviction = 0

    # ------------------------------------------------------------------
    # Client identity
    # ------------------------------------------------------------------
    def client_id(self, request: Request) -> str:
        """Identify the caller, preferring an authenticated user id."""
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}"

        if self.config.trust_forwarded_for:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                return f"ip:{forwarded.split(',')[0].strip()}"

        host = request.client.host if request.client else "unknown"
        return f"ip:{host}"

    # ------------------------------------------------------------------
    # Accounting
    # ------------------------------------------------------------------
    def is_exempt(self, path: str) -> bool:
        return path.startswith(self.config.exempt_paths)

    def check(self, client: str, now: Optional[float] = None) -> Tuple[Optional[str], int]:
        """
        Record a request and report whether it exceeds a budget.

        Returns ``(exceeded_window, remaining_this_minute)``; the window is
        None when the request is allowed.
        """
        now = time.monotonic() if now is None else now

        with self._lock:
            history = self._requests[client]
            history.append(now)

            # Drop anything older than the longest window we track.
            longest = _WINDOWS[-1][1]
            while history and history[0] <= now - longest:
                history.popleft()

            exceeded: Optional[str] = None
            minute_count = 0
            for name, span in _WINDOWS:
                cutoff = now - span
                # History is chronological, so a reverse scan stops early.
                count = 0
                for timestamp in reversed(history):
                    if timestamp <= cutoff:
                        break
                    count += 1

                if name == "minute":
                    minute_count = count
                if exceeded is None and count > self.config.limit_for(name):
                    exceeded = name

            self._since_eviction += 1
            if self._since_eviction >= self.EVICTION_INTERVAL:
                self._evict_idle(now)
                self._since_eviction = 0

        remaining = max(0, self.config.requests_per_minute - minute_count)
        return exceeded, remaining

    def _evict_idle(self, now: float) -> None:
        """Drop clients with no activity inside the longest window."""
        cutoff = now - self.IDLE_EVICTION_SECONDS
        stale = [client for client, hist in self._requests.items() if not hist or hist[-1] <= cutoff]
        for client in stale:
            del self._requests[client]
        if stale:
            logger.debug("Evicted %d idle rate-limit entries", len(stale))

    def reset(self) -> None:
        """Forget all recorded history (used by tests)."""
        with self._lock:
            self._requests.clear()
            self._since_eviction = 0

    @staticmethod
    def retry_after(window: str) -> int:
        return {"minute": 60, "hour": 3600, "day": 86400}[window]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Applies a :class:`RateLimiter` to every request."""

    def __init__(self, app, limiter: Optional[RateLimiter] = None):
        super().__init__(app)
        self.limiter = limiter or RateLimiter()

    async def dispatch(self, request: Request, call_next):
        if self.limiter.is_exempt(request.url.path):
            return await call_next(request)

        client = self.limiter.client_id(request)
        exceeded, remaining = self.limiter.check(client)

        if exceeded:
            limit = self.limiter.config.limit_for(exceeded)
            retry_after = self.limiter.retry_after(exceeded)
            logger.info("Rate limit hit by %s (%s window)", client, exceeded)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit: {limit} per {exceeded}",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.limiter.config.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limiter.config.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


#: Shared limiter instance, configured when the app is created.
rate_limiter = RateLimiter()
