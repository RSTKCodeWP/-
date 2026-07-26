"""
Tests for the rate limiting middleware.
"""

from __future__ import annotations

import pytest

from realworldmapgen.middleware.rate_limiter import RateLimitConfig, RateLimiter


@pytest.fixture
def limiter() -> RateLimiter:
    return RateLimiter(
        RateLimitConfig(requests_per_minute=3, requests_per_hour=5, requests_per_day=7)
    )


def test_allows_requests_under_the_limit(limiter):
    for _ in range(3):
        exceeded, _ = limiter.check("client", now=0.0)
        assert exceeded is None


def test_blocks_once_the_minute_budget_is_exceeded(limiter):
    for _ in range(3):
        limiter.check("client", now=0.0)

    exceeded, remaining = limiter.check("client", now=0.0)
    assert exceeded == "minute"
    assert remaining == 0


def test_hour_budget_is_reachable():
    """
    The hourly limit must actually trigger.

    The previous implementation truncated the shared history to the one-minute
    window before checking the longer windows, so the hour and day budgets
    could never be exceeded.
    """
    limiter = RateLimiter(
        RateLimitConfig(requests_per_minute=1000, requests_per_hour=5, requests_per_day=1000)
    )

    # Spread requests a minute apart: never more than one per minute window,
    # but six within the hour.
    for index in range(5):
        exceeded, _ = limiter.check("client", now=index * 61.0)
        assert exceeded is None

    exceeded, _ = limiter.check("client", now=5 * 61.0)
    assert exceeded == "hour"


def test_day_budget_is_reachable():
    limiter = RateLimiter(
        RateLimitConfig(requests_per_minute=1000, requests_per_hour=1000, requests_per_day=3)
    )

    for index in range(3):
        assert limiter.check("client", now=index * 3601.0)[0] is None

    assert limiter.check("client", now=3 * 3601.0)[0] == "day"


def test_window_slides_forward(limiter):
    for _ in range(3):
        limiter.check("client", now=0.0)
    assert limiter.check("client", now=0.0)[0] == "minute"

    # Once the old requests age out of the minute window, traffic resumes.
    assert limiter.check("client", now=61.0)[0] is None


def test_clients_are_tracked_independently(limiter):
    for _ in range(4):
        limiter.check("client-a", now=0.0)

    assert limiter.check("client-b", now=0.0)[0] is None


def test_remaining_never_goes_negative(limiter):
    for _ in range(10):
        _, remaining = limiter.check("client", now=0.0)
        assert remaining >= 0


def test_idle_clients_are_evicted():
    """The client table must not grow without bound."""
    limiter = RateLimiter(RateLimitConfig(requests_per_minute=1_000_000))
    limiter.EVICTION_INTERVAL = 10

    for index in range(10):
        limiter.check(f"client-{index}", now=0.0)
    assert len(limiter._requests) == 10

    # Eviction is amortized over EVICTION_INTERVAL requests, so it takes that
    # many later calls before the idle entries are swept.
    later = limiter.IDLE_EVICTION_SECONDS + 100.0
    for _ in range(limiter.EVICTION_INTERVAL):
        limiter.check("fresh", now=later)

    assert "client-0" not in limiter._requests
    assert "fresh" in limiter._requests


@pytest.mark.parametrize("path", ["/health", "/health/live", "/health/ready", "/metrics"])
def test_probe_paths_are_exempt(limiter, path):
    """Orchestrator probes and metrics scrapes must never be throttled."""
    assert limiter.is_exempt(path) is True


def test_api_paths_are_not_exempt(limiter):
    assert limiter.is_exempt("/api/generate") is False


# ---------------------------------------------------------------------------
# Client identification
# ---------------------------------------------------------------------------
class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    def __init__(self, headers=None, host="1.2.3.4", user_id=None):
        self.headers = headers or {}
        self.client = _FakeClient(host)
        self.state = type("S", (), {"user_id": user_id})()


def test_forwarded_for_is_ignored_by_default(limiter):
    """
    A spoofable header must not define identity.

    Trusting X-Forwarded-For unconditionally lets any client evade the limit
    by rotating the header value.
    """
    request = _FakeRequest(headers={"X-Forwarded-For": "9.9.9.9"})
    assert limiter.client_id(request) == "ip:1.2.3.4"


def test_forwarded_for_is_used_when_explicitly_trusted():
    limiter = RateLimiter(RateLimitConfig(trust_forwarded_for=True))
    request = _FakeRequest(headers={"X-Forwarded-For": "9.9.9.9, 10.0.0.1"})

    assert limiter.client_id(request) == "ip:9.9.9.9"


def test_authenticated_user_takes_precedence(limiter):
    request = _FakeRequest(headers={"X-Forwarded-For": "9.9.9.9"}, user_id="u-42")
    assert limiter.client_id(request) == "user:u-42"


# ---------------------------------------------------------------------------
# Middleware behaviour through the real app
# ---------------------------------------------------------------------------
def test_middleware_returns_429_with_retry_after(app):
    """A saturated client gets a 429 carrying standards-compliant headers."""
    from fastapi.testclient import TestClient

    from realworldmapgen.middleware.rate_limiter import RateLimitMiddleware

    # Locate the limiter the app was built with, if rate limiting is enabled.
    limiter = None
    for middleware in app.user_middleware:
        if middleware.cls is RateLimitMiddleware:
            limiter = middleware.kwargs.get("limiter")

    if limiter is None:
        pytest.skip("rate limiting is disabled in this configuration")

    limiter.reset()
    original = limiter.config.requests_per_minute
    limiter.config.requests_per_minute = 2
    try:
        with TestClient(app) as client:
            for _ in range(2):
                assert client.get("/api").status_code == 200

            blocked = client.get("/api")
            assert blocked.status_code == 429
            assert blocked.headers["Retry-After"] == "60"
            assert blocked.headers["X-RateLimit-Remaining"] == "0"
            assert blocked.json()["error"] == "Rate limit exceeded"
    finally:
        limiter.config.requests_per_minute = original
        limiter.reset()
