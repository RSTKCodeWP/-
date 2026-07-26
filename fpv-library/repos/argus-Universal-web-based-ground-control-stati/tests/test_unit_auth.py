"""Unit tests for authentication flow.

Tests token generation, validation, middleware behavior, file I/O,
auth-disable mode, and concurrent access patterns.
"""

import os
import sys
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backend.auth as auth_module
from backend.app import app
from backend.auth import TOKEN_FILE, auth_required, generate_token, verify_token
from backend.drone_link import DroneLink
from backend.ws_manager import WSManager


@pytest.fixture(autouse=True)
def _reset_auth_state():
    """Reset auth module state before and after each test."""
    auth_module._token = None
    old_env = os.environ.pop("GCS_AUTH_TOKEN", None)
    existed = TOKEN_FILE.exists()
    if existed:
        backup = TOKEN_FILE.read_text()
        TOKEN_FILE.unlink()
    yield
    auth_module._token = None
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
    if existed:
        TOKEN_FILE.write_text(backup)
    if old_env is not None:
        os.environ["GCS_AUTH_TOKEN"] = old_env
    else:
        os.environ.pop("GCS_AUTH_TOKEN", None)


@pytest.fixture
def client():
    """FastAPI TestClient with app state initialized."""
    if not hasattr(app.state, "link"):
        app.state.link = DroneLink()
        app.state.ws_mgr = WSManager(app.state.link)
    return TestClient(app, raise_server_exceptions=False)


class TestTokenGeneration:
    def test_token_is_32_hex_chars(self):
        token = generate_token()
        assert len(token) == 32
        assert all(c in "0123456789abcdef" for c in token)

    def test_token_is_different_each_time(self):
        t1 = generate_token()
        auth_module._token = None
        if TOKEN_FILE.exists():
            TOKEN_FILE.unlink()
        t2 = generate_token()
        assert t1 != t2

    def test_token_file_created_on_generate(self):
        assert not TOKEN_FILE.exists()
        generate_token()
        assert TOKEN_FILE.exists()

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX file mode not applicable on Windows (uses ACLs instead)")
    def test_token_file_has_correct_permissions(self):
        generate_token()
        mode = TOKEN_FILE.stat().st_mode & 0o777
        assert mode == 0o600, f"Expected 0600, got {oct(mode)}"


class TestTokenValidation:
    def test_correct_token_passes(self):
        token = generate_token()
        assert verify_token(token) is True

    def test_wrong_token_fails(self):
        generate_token()
        assert verify_token("aaaabbbbccccddddeeeeffffgggghhhh") is False

    def test_empty_string_fails_when_auth_active(self):
        generate_token()
        assert verify_token("") is False

    def test_partial_token_fails(self):
        token = generate_token()
        assert verify_token(token[:16]) is False

    def test_token_from_file_read(self):
        """Token written to file can be read back for validation."""
        token = generate_token()
        auth_module._token = None  # force reload from file
        assert verify_token(token) is True

    def test_env_token_validation(self):
        """GCS_AUTH_TOKEN environment variable is accepted."""
        os.environ["GCS_AUTH_TOKEN"] = "env_secret_token_12345678"
        assert verify_token("env_secret_token_12345678") is True
        assert verify_token("wrong_value") is False


class TestAuthDisableMode:
    def test_no_token_means_auth_not_required(self):
        assert auth_required() is False

    def test_no_token_allows_any_value(self):
        assert verify_token("anything_at_all") is True

    def test_no_token_allows_empty_string(self):
        assert verify_token("") is True


class TestProtectedEndpoints:
    def test_unauthenticated_request_rejected(self, client):
        """Protected endpoint rejects requests without valid token."""
        generate_token()
        r = client.get("/api/session")
        assert r.status_code == 401
        data = r.json()
        assert data["error"] == "unauthorized"

    def test_authenticated_request_passes(self, client):
        """Protected endpoint accepts requests with valid token."""
        token = generate_token()
        r = client.get("/api/session", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200

    def test_query_param_token_rejected_for_http(self, client):
        """Token in query params is not accepted for HTTP — must use Authorization header."""
        token = generate_token()
        r = client.get(f"/api/session?token={token}")
        assert r.status_code == 401

    def test_health_endpoint_bypasses_auth(self, client):
        """Health endpoint is always accessible regardless of auth."""
        generate_token()
        r = client.get("/health")
        assert r.status_code == 200

    def test_login_endpoint_bypasses_auth(self, client):
        """Login endpoint is accessible without token."""
        token = generate_token()
        r = client.post("/api/auth/login", json={"token": token})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_login_with_bad_token_returns_401(self, client):
        generate_token()
        r = client.post("/api/auth/login", json={"token": "totally_wrong"})
        assert r.status_code == 401


class TestConcurrentAuth:
    def test_concurrent_verify_no_race(self):
        """Multiple threads verifying simultaneously should not corrupt state."""
        token = generate_token()
        results = []
        errors = []

        def worker():
            try:
                for _ in range(50):
                    r = verify_token(token)
                    results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Got errors: {errors}"
        assert all(r is True for r in results)

    def test_concurrent_verify_wrong_token(self):
        """Multiple threads verifying wrong tokens should all fail safely."""
        generate_token()
        results = []
        errors = []

        def worker():
            try:
                for _ in range(50):
                    r = verify_token("wrong_token_value_here!!")
                    results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert all(r is False for r in results)
