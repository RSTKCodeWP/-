"""
Tests for the API key gate.

``API_KEY_ENABLED`` and ``API_KEYS`` were documented in ``.env.example`` while
nothing in the codebase read them, so turning the setting on left the API wide
open.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from realworldmapgen.middleware.api_key import APIKeyMiddleware

# Test inputs, named rather than written inline: they gate nothing, and a
# literal that looks like a key trips secret scanners.
VALID_KEY = "pytest-input-not-a-credential"
SECOND_KEY = "pytest-input-second-entry"


def build_app(keys, **kwargs) -> FastAPI:
    app = FastAPI()
    app.add_middleware(APIKeyMiddleware, api_keys=keys, **kwargs)

    @app.get("/api/generate")
    async def generate():
        return {"ok": True}

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready():
        return {"status": "ok"}

    @app.get("/metrics")
    async def metrics():
        return {"requests": 0}

    @app.get("/")
    async def index():
        return {"page": "spa"}

    return app


@pytest.fixture
def gated() -> TestClient:
    return TestClient(build_app([VALID_KEY, SECOND_KEY]))


# ---------------------------------------------------------------------------
# Enforcement
# ---------------------------------------------------------------------------
def test_request_without_a_key_is_rejected(gated):
    response = gated.get("/api/generate")

    assert response.status_code == 401
    assert response.json()["error"] == "Unauthorized"


def test_request_with_the_key_is_allowed(gated):
    response = gated.get("/api/generate", headers={"X-API-Key": VALID_KEY})

    assert response.status_code == 200


def test_any_configured_key_is_accepted(gated):
    assert gated.get("/api/generate", headers={"X-API-Key": SECOND_KEY}).status_code == 200


def test_a_wrong_key_is_rejected(gated):
    assert gated.get("/api/generate", headers={"X-API-Key": "guess"}).status_code == 401


def test_a_key_prefix_is_not_enough(gated):
    """Guards against a truncated or partial-match comparison."""
    assert gated.get("/api/generate", headers={"X-API-Key": VALID_KEY[:6]}).status_code == 401


def test_bearer_tokens_are_also_accepted(gated):
    response = gated.get(
        "/api/generate", headers={"Authorization": f"Bearer {VALID_KEY}"}
    )

    assert response.status_code == 200


def test_the_key_header_wins_over_a_session_token(gated):
    """The gate and per-user sessions compose: both headers travel together."""
    response = gated.get(
        "/api/generate",
        headers={"X-API-Key": VALID_KEY, "Authorization": "Bearer a-session-token"},
    )

    assert response.status_code == 200


def test_rejection_advertises_the_scheme(gated):
    assert gated.get("/api/generate").headers["WWW-Authenticate"] == "Bearer"


# ---------------------------------------------------------------------------
# Exemptions
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path", ["/health/ready", "/metrics", "/api/health"])
def test_probes_stay_reachable_without_a_key(gated, path):
    """A gated /health would take the deployment down at the orchestrator."""
    assert gated.get(path).status_code == 200


def test_the_frontend_still_loads_without_a_key(gated):
    assert gated.get("/").status_code == 200


def test_the_prefix_match_fails_closed():
    """
    A route added at /apikeys - no separating slash - must be gated by
    default rather than exposed by an exact-prefix check.
    """
    app = build_app(["k"])

    @app.get("/apikeys")
    async def api_keys():
        return {"keys": []}

    assert TestClient(app).get("/apikeys").status_code == 401


# ---------------------------------------------------------------------------
# Misconfiguration
# ---------------------------------------------------------------------------
def test_enabled_with_no_keys_fails_closed():
    """Turning the gate on with an empty key list must not open the API."""
    client = TestClient(build_app([]))

    assert client.get("/api/generate").status_code == 401
    assert client.get("/api/health").status_code == 200


def test_blank_entries_are_not_usable_keys():
    client = TestClient(build_app(["", "  ", "real-key"]))

    assert client.get("/api/generate", headers={"X-API-Key": ""}).status_code == 401
    assert client.get("/api/generate", headers={"X-API-Key": "real-key"}).status_code == 200


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------
def test_the_gate_is_not_attached_by_default():
    import realworldmapgen.api.main as main
    from realworldmapgen.config import settings

    assert settings.api_key_enabled is False
    assert not any(m.cls is APIKeyMiddleware for m in main.app.user_middleware)


def test_setting_api_key_enabled_gates_the_real_app(tmp_path):
    """
    End to end: the setting has to reach the application. It was previously
    read by nothing, so turning it on changed nothing at all.

    Settings are built at import time, so this runs in a fresh interpreter.
    """
    import json
    import subprocess
    import sys

    script = """
import json
from fastapi.testclient import TestClient
from realworldmapgen.api.main import app

with TestClient(app) as client:
    print(json.dumps({
        "unkeyed": client.get("/api/sources").status_code,
        "keyed": client.get("/api/sources", headers={"X-API-Key": "k1"}).status_code,
        "wrong": client.get("/api/sources", headers={"X-API-Key": "nope"}).status_code,
        "health": client.get("/api/health").status_code,
    }))
"""
    environment = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
        "API_KEY_ENABLED": "true",
        "API_KEYS": "k1,k2",
        "OUTPUT_DIR": str(tmp_path / "output"),
        "CACHE_DIR": str(tmp_path / "cache"),
        "TEMP_DIR": str(tmp_path / "temp"),
        "PLUGIN_DIR": str(tmp_path / "plugins"),
        "AUTH_STORAGE_FILE": str(tmp_path / "data" / "users.json"),
        "SETTINGS_STORAGE_FILE": str(tmp_path / "data" / "settings.json"),
        "SECRET_KEY_FILE": str(tmp_path / "data" / ".secret_key"),
        "SRTM_ENABLED": "false",
        "OSM_ENABLED": "false",
        "OVERPASS_ENABLED": "false",
    }
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=environment,
        cwd=tmp_path,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stderr

    statuses = json.loads(completed.stdout.strip().splitlines()[-1])
    assert statuses == {"unkeyed": 401, "keyed": 200, "wrong": 401, "health": 200}
