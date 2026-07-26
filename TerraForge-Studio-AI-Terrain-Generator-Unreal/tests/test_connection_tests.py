"""
Tests for data-source connectivity probes.

The settings UI's "Test Connection" button used to report success whenever a
credential string was non-empty - and unconditionally for OSM - so a typo'd,
expired or revoked key still showed green.
"""

from __future__ import annotations

import pytest

from realworldmapgen.settings import connection_test as probes


class _Response:
    def __init__(self, status_code: int):
        self.status_code = status_code


def stub_request(monkeypatch, *, status_code=None, error=None):
    """Replace httpx.AsyncClient with a stub. Returns the recorded calls."""
    calls = []

    class _Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def request(self, method, url, **kwargs):
            calls.append((method, url, kwargs))
            if error is not None:
                raise error
            return _Response(status_code)

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    return calls


# ---------------------------------------------------------------------------
# Result semantics
# ---------------------------------------------------------------------------
def test_success_requires_a_completed_round_trip():
    """Being configured is not the same as being reachable."""
    configured_only = probes.ConnectionResult("x", configured=True, reachable=None, message="")
    assert configured_only.success is False

    reached = probes.ConnectionResult("x", configured=True, reachable=True, message="")
    assert reached.success is True


def test_unreachable_source_reports_an_error():
    result = probes.ConnectionResult("x", configured=True, reachable=False, message="boom")
    payload = result.as_dict()

    assert payload["success"] is False
    assert payload["error"] == "boom"


def test_successful_result_has_no_error():
    payload = probes.ConnectionResult("x", True, True, "Connection successful").as_dict()
    assert payload["error"] is None


# ---------------------------------------------------------------------------
# Credential handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_missing_credentials_do_not_attempt_a_request(monkeypatch):
    calls = stub_request(monkeypatch, status_code=200)

    result = await probes.test_opentopography(None)

    assert result.configured is False
    assert result.reachable is None
    assert result.success is False
    assert calls == []


@pytest.mark.asyncio
async def test_rejected_credentials_are_not_success(monkeypatch):
    """A 401 means the key is wrong; the old code called this success."""
    stub_request(monkeypatch, status_code=401)

    result = await probes.test_opentopography("wrong-key")

    assert result.success is False
    assert "credentials" in result.message


@pytest.mark.asyncio
async def test_forbidden_is_not_success(monkeypatch):
    stub_request(monkeypatch, status_code=403)
    assert (await probes.test_azure_maps("bad-key")).success is False


@pytest.mark.asyncio
async def test_rate_limiting_is_reported_distinctly(monkeypatch):
    stub_request(monkeypatch, status_code=429)

    result = await probes.test_azure_maps("a-key")

    assert result.success is False
    assert "Rate limited" in result.message


@pytest.mark.asyncio
async def test_valid_credentials_report_success(monkeypatch):
    stub_request(monkeypatch, status_code=200)
    assert (await probes.test_azure_maps("good-key")).success is True


@pytest.mark.asyncio
async def test_network_failure_is_reported_not_raised(monkeypatch):
    stub_request(monkeypatch, error=ConnectionError("no route to host"))

    result = await probes.test_srtm()

    assert result.success is False
    assert "Could not reach provider" in result.message


@pytest.mark.asyncio
async def test_sentinelhub_uses_the_token_endpoint(monkeypatch):
    calls = stub_request(monkeypatch, status_code=200)

    await probes.test_sentinelhub("id", "secret")

    method, url, kwargs = calls[0]
    assert method == "POST"
    assert "oauth/token" in url
    assert kwargs["data"]["grant_type"] == "client_credentials"


@pytest.mark.asyncio
async def test_overpass_probe_posts_a_query(monkeypatch):
    calls = stub_request(monkeypatch, status_code=200)

    await probes.test_overpass("https://overpass.example/api")

    method, url, kwargs = calls[0]
    assert method == "POST"
    assert url == "https://overpass.example/api"
    assert b"out count" in kwargs["content"]


@pytest.mark.asyncio
async def test_srtm_probe_fetches_a_tile(monkeypatch):
    calls = stub_request(monkeypatch, status_code=200)

    await probes.test_srtm()

    method, url, _ = calls[0]
    assert method == "GET"
    assert url.endswith(".png")


# ---------------------------------------------------------------------------
# Through the API
# ---------------------------------------------------------------------------
def test_unknown_source_is_rejected(client):
    payload = client.post("/api/settings/test-connection/not-a-source").json()

    assert payload["success"] is False
    assert "Unknown source" in payload["message"]


def test_disabled_source_is_not_reported_as_reachable(client):
    """A disabled source has nothing to reach, and must not claim success."""
    payload = client.post("/api/settings/test-connection/sentinelhub").json()

    assert payload["success"] is False
    assert payload["reachable"] is None


def test_response_exposes_configured_and_reachable_separately(client):
    payload = client.post("/api/settings/test-connection/opentopography").json()

    assert set(payload) >= {"source", "success", "configured", "reachable", "message"}


@pytest.mark.network
@pytest.mark.asyncio
async def test_srtm_probe_reaches_the_real_service():
    """The key-free elevation source must answer a live probe."""
    result = await probes.test_srtm()

    assert result.success is True, result.message
