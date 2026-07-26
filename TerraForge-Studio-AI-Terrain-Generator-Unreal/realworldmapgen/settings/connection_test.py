"""
Real connectivity probes for configured data sources.

``SettingsManager.test_connection`` previously only checked that a credential
string was non-empty and then reported "Connection successful", so a typo'd,
expired or revoked key still produced a green result in the settings UI. Every
probe here performs an actual request against the provider.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

#: Probes are deliberately small and quick; this is a UI affordance, not a
#: health check.
PROBE_TIMEOUT = 15.0

#: A single terrain tile over open ocean - tiny, and always present.
_SRTM_PROBE_TILE = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/1/1/1.png"

#: The cheapest well-formed Overpass query: ask for a count of nothing.
_OVERPASS_PROBE_QUERY = "[out:json][timeout:10];out count;"


@dataclass
class ConnectionResult:
    """Outcome of probing one source."""

    source: str
    #: Credentials (if any) are present.
    configured: bool
    #: A real request reached the provider and was accepted. None when no
    #: request was attempted, e.g. because nothing is configured.
    reachable: Optional[bool]
    message: str

    @property
    def success(self) -> bool:
        """Only a completed round trip counts as success."""
        return self.reachable is True

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "success": self.success,
            "configured": self.configured,
            "reachable": self.reachable,
            "message": self.message,
            "error": None if self.success else self.message,
        }


def _not_configured(source: str, detail: str) -> ConnectionResult:
    return ConnectionResult(
        source=source,
        configured=False,
        reachable=None,
        message=detail,
    )


def _unreachable(source: str, detail: str) -> ConnectionResult:
    return ConnectionResult(source=source, configured=True, reachable=False, message=detail)


def _ok(source: str, detail: str = "Connection successful") -> ConnectionResult:
    return ConnectionResult(source=source, configured=True, reachable=True, message=detail)


async def _probe(method: str, url: str, **kwargs) -> tuple[bool, str]:
    """Issue one request, translating the outcome into (ok, message)."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as client:
            response = await client.request(method, url, **kwargs)

        if response.status_code in (401, 403):
            return False, f"Rejected by provider (HTTP {response.status_code}) - check credentials"
        if response.status_code == 429:
            return False, "Rate limited by provider - try again shortly"
        if response.status_code >= 400:
            return False, f"Provider returned HTTP {response.status_code}"
        return True, "Connection successful"
    except Exception as exc:  # noqa: BLE001 - any failure means "unreachable"
        return False, f"Could not reach provider: {exc}"


# ---------------------------------------------------------------------------
# Per-source probes
# ---------------------------------------------------------------------------
async def test_srtm() -> ConnectionResult:
    """Fetch one terrain tile. Needs no credentials."""
    ok, message = await _probe("GET", _SRTM_PROBE_TILE)
    return ConnectionResult(source="srtm", configured=True, reachable=ok, message=message)


async def test_overpass(endpoint: Optional[str] = None) -> ConnectionResult:
    """Run a trivial Overpass query against the first configured mirror."""
    from ..config import settings

    target = endpoint or (
        settings.overpass_endpoints[0]
        if settings.overpass_endpoints
        else "https://overpass-api.de/api/interpreter"
    )
    ok, message = await _probe("POST", target, content=_OVERPASS_PROBE_QUERY.encode())
    return ConnectionResult(source="osm", configured=True, reachable=ok, message=message)


async def test_opentopography(api_key: Optional[str]) -> ConnectionResult:
    """Request a minimal DEM extract; an invalid key is rejected outright."""
    if not api_key:
        return _not_configured("opentopography", "Missing API key")

    ok, message = await _probe(
        "GET",
        "https://portal.opentopography.org/API/globaldem",
        params={
            "demtype": "SRTMGL3",
            "south": 0.0,
            "north": 0.01,
            "west": 0.0,
            "east": 0.01,
            "outputFormat": "GTiff",
            "API_Key": api_key,
        },
    )
    return _ok("opentopography", message) if ok else _unreachable("opentopography", message)


async def test_azure_maps(subscription_key: Optional[str]) -> ConnectionResult:
    """Call the elevation endpoint with the configured subscription key."""
    if not subscription_key:
        return _not_configured("azure_maps", "Missing subscription key")

    ok, message = await _probe(
        "GET",
        "https://atlas.microsoft.com/search/address/json",
        params={
            "api-version": "1.0",
            "subscription-key": subscription_key,
            "query": "London",
            "limit": 1,
        },
    )
    return _ok("azure_maps", message) if ok else _unreachable("azure_maps", message)


async def test_sentinelhub(client_id: Optional[str], client_secret: Optional[str]) -> ConnectionResult:
    """Exchange the client credentials for a token - the real auth path."""
    if not client_id or not client_secret:
        return _not_configured("sentinelhub", "Missing client ID or secret")

    ok, message = await _probe(
        "POST",
        "https://services.sentinel-hub.com/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    return _ok("sentinelhub", message) if ok else _unreachable("sentinelhub", message)
