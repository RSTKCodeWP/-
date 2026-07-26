"""
Shared pytest fixtures for the TerraForge Studio backend test suite.

These tests exercise the FastAPI application in-process through
``TestClient`` - no running server, no network access, and no API keys are
required. Browser-driven tests live in ``tests/e2e`` and are opt-in.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterator

import pytest

# ---------------------------------------------------------------------------
# Runtime isolation.
#
# ``realworldmapgen.config`` builds its Settings singleton at import time, and
# test modules import it during collection - before any fixture runs. The
# environment therefore has to be patched here, at conftest import time, which
# pytest guarantees happens first.
# ---------------------------------------------------------------------------
_TEST_ROOT = Path(tempfile.mkdtemp(prefix="terraforge-tests-"))

os.environ.update(
    {
        "OUTPUT_DIR": str(_TEST_ROOT / "output"),
        "CACHE_DIR": str(_TEST_ROOT / "cache"),
        "TEMP_DIR": str(_TEST_ROOT / "temp"),
        "PLUGIN_DIR": str(_TEST_ROOT / "plugins"),
        # Keep the suite hermetic: no outbound tile or Overpass requests.
        "SRTM_ENABLED": "false",
        "OSM_ENABLED": "false",
        "OVERPASS_ENABLED": "false",
        "ALLOW_SYNTHETIC_FALLBACK": "true",
        "ENVIRONMENT": "development",
        # The middleware stays attached so it remains testable, but the budget
        # is raised far beyond what the suite generates: every request shares
        # one client identity, and the suite outgrew the 60/min default.
        # test_rate_limiter lowers the limit itself for its own assertions.
        "RATE_LIMIT_PER_MINUTE": "100000",
        "RATE_LIMIT_PER_HOUR": "100000",
        "RATE_LIMIT_PER_DAY": "100000",
        # Keep everything the app persists inside the temporary root, so a
        # test run never writes into the checkout.
        "AUTH_STORAGE_FILE": str(_TEST_ROOT / "data" / "users.json"),
        "SETTINGS_STORAGE_FILE": str(_TEST_ROOT / "data" / "settings.json"),
        "SECRET_KEY_FILE": str(_TEST_ROOT / "data" / ".secret_key"),
    }
)


@pytest.fixture(scope="session")
def app():
    """The FastAPI application under test."""
    from realworldmapgen.api.main import app as fastapi_app

    return fastapi_app


@pytest.fixture
def client(app) -> Iterator["TestClient"]:  # noqa: F821
    """A TestClient that runs the app's lifespan (startup/shutdown)."""
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def output_dir() -> Path:
    """The temporary output directory used by the app during tests."""
    from realworldmapgen.config import settings

    settings.output_dir.mkdir(parents=True, exist_ok=True)
    return settings.output_dir


@pytest.fixture
def sample_bbox() -> dict:
    """A small, valid bounding box over San Francisco."""
    return {"north": 37.80, "south": 37.79, "east": -122.40, "west": -122.41}
