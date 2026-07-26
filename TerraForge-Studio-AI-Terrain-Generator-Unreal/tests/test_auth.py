"""
Tests for authentication and user management.

Covers four defects found by auditing the auth subsystem:
  1. any user could grant themselves the admin role
  2. passwords were hashed with unsalted SHA-256
  3. password hashes were never persisted, locking everyone out on restart
  4. update_user applied arbitrary attributes via setattr
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from realworldmapgen.core.auth_manager import (
    PBKDF2_ALGORITHM,
    AuthManager,
    hash_password,
    verify_password,
)

# Test inputs, named rather than written inline: these authenticate against
# nothing, and a literal that looks like a password trips secret scanners.
TEST_PASSWORD = "pytest-input-not-a-credential"
WRONG_PASSWORD = "pytest-input-that-should-fail"
REPLACEMENT_PASSWORD = "pytest-input-after-reset"
LEGACY_PASSWORD = "pytest-input-hashed-by-the-old-scheme"


@pytest.fixture
def manager(tmp_path) -> AuthManager:
    return AuthManager(tmp_path / "users.json")


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
def test_hash_is_salted_and_iterated():
    stored = hash_password(TEST_PASSWORD)

    algorithm, iterations, salt, digest = stored.split("$")
    assert algorithm == PBKDF2_ALGORITHM
    assert int(iterations) >= 100_000
    assert len(salt) >= 32
    assert len(digest) == 64


def test_same_password_yields_different_hashes():
    """A per-user salt is what defeats rainbow tables."""
    assert hash_password("same") != hash_password("same")


def test_verify_accepts_the_right_password():
    stored = hash_password(TEST_PASSWORD)
    valid, needs_upgrade = verify_password(TEST_PASSWORD, stored)

    assert valid is True
    assert needs_upgrade is False


def test_verify_rejects_the_wrong_password():
    stored = hash_password(TEST_PASSWORD)
    assert verify_password(WRONG_PASSWORD, stored)[0] is False


def test_verify_rejects_a_missing_hash():
    """An account with no stored hash must never authenticate."""
    assert verify_password("anything", None) == (False, False)
    assert verify_password("anything", "") == (False, False)


def test_legacy_sha256_hashes_still_work_and_are_flagged():
    """Existing accounts keep working, and are marked for rehashing."""
    legacy = hashlib.sha256(LEGACY_PASSWORD.encode()).hexdigest()

    valid, needs_upgrade = verify_password(LEGACY_PASSWORD, legacy)

    assert valid is True
    assert needs_upgrade is True


def test_malformed_hash_is_rejected_not_raised():
    assert verify_password("x", "pbkdf2_sha256$notanumber$zz$zz") == (False, False)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def test_public_dict_never_contains_the_hash(manager):
    """to_dict() is what /api/auth/me returns."""
    user = manager.create_user("alice", "alice@example.com", TEST_PASSWORD)

    assert "password_hash" not in user.to_dict()
    assert "password_hash" in user.to_record()


def test_login_survives_a_restart(tmp_path):
    """
    Hashes were persisted through to_dict(), which omits them, so every
    account was locked out after a restart with no reset path.
    """
    storage = tmp_path / "users.json"

    first = AuthManager(storage)
    first.create_user("bob", "bob@example.com", TEST_PASSWORD)
    assert first.authenticate("bob", TEST_PASSWORD) is not None

    restarted = AuthManager(storage)
    assert restarted.authenticate("bob", TEST_PASSWORD) is not None


def test_stored_file_has_no_plaintext_password(manager, tmp_path):
    manager.create_user("carol", "carol@example.com", TEST_PASSWORD)

    contents = (tmp_path / "users.json").read_text()
    assert TEST_PASSWORD not in contents


def test_legacy_hash_is_upgraded_on_login(tmp_path):
    storage = tmp_path / "users.json"
    manager = AuthManager(storage)
    user = manager.create_user("dave", "dave@example.com", "irrelevant")

    user._password_hash = hashlib.sha256(LEGACY_PASSWORD.encode()).hexdigest()

    assert manager.authenticate("dave", LEGACY_PASSWORD) is not None
    assert user._password_hash.startswith(PBKDF2_ALGORITHM)

    stored = json.loads(storage.read_text())["users"][user.user_id]
    assert stored["password_hash"].startswith(PBKDF2_ALGORITHM)


def test_credentials_are_not_stored_in_the_cache_directory(manager):
    """The cache directory is something a user may reasonably clear."""
    assert "cache" not in Path(AuthManager().storage_file).parts


# ---------------------------------------------------------------------------
# update_user whitelist
# ---------------------------------------------------------------------------
def test_only_whitelisted_fields_are_applied(manager):
    user = manager.create_user("erin", "erin@example.com", TEST_PASSWORD)

    manager.update_user(
        user.user_id,
        {"email": "new@example.com", "username": "hacked", "user_id": "forged"},
    )

    assert user.email == "new@example.com"
    assert user.username == "erin"
    assert user.user_id != "forged"


def test_password_hash_cannot_be_set_through_update(manager):
    user = manager.create_user("frank", "frank@example.com", TEST_PASSWORD)
    original = user._password_hash

    manager.update_user(user.user_id, {"password_hash": "attacker-controlled"})

    assert user._password_hash == original


def test_set_password_rehashes(manager):
    user = manager.create_user("grace", "grace@example.com", TEST_PASSWORD)

    assert manager.set_password(user.user_id, REPLACEMENT_PASSWORD) is True
    assert manager.authenticate("grace", REPLACEMENT_PASSWORD) is not None
    assert manager.authenticate("grace", TEST_PASSWORD) is None


# ---------------------------------------------------------------------------
# Privilege escalation through the API
# ---------------------------------------------------------------------------
def _register_and_login(client, username: str) -> tuple[str, dict]:
    registration = client.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": TEST_PASSWORD},
    )
    assert registration.status_code == 200
    user_id = registration.json()["user"]["user_id"]

    login = client.post(
        "/api/auth/login", json={"username": username, "password": TEST_PASSWORD}
    )
    token = login.json()["session"]["token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_user_cannot_promote_themselves_to_admin(client):
    """
    A self-update is permitted, and role used to be an ordinary field, so one
    PATCH turned any account into an admin.
    """
    user_id, headers = _register_and_login(client, "escalator")

    response = client.patch(
        f"/api/auth/users/{user_id}", json={"role": "admin"}, headers=headers
    )

    assert response.status_code == 403
    assert client.get("/api/auth/me", headers=headers).json()["user"]["role"] == "user"


def test_admin_only_endpoints_stay_closed_after_the_attempt(client):
    user_id, headers = _register_and_login(client, "escalator2")

    client.patch(f"/api/auth/users/{user_id}", json={"role": "admin"}, headers=headers)

    assert client.get("/api/auth/users", headers=headers).status_code == 403


def test_self_update_of_ordinary_fields_still_works(client):
    user_id, headers = _register_and_login(client, "selfedit")

    response = client.patch(
        f"/api/auth/users/{user_id}", json={"email": "changed@example.com"}, headers=headers
    )

    assert response.status_code == 200
    assert client.get("/api/auth/me", headers=headers).json()["user"]["email"] == (
        "changed@example.com"
    )


def test_updating_another_user_is_forbidden(client):
    _register_and_login(client, "attacker")
    victim_id, _ = _register_and_login(client, "victim")
    _, attacker_headers = _register_and_login(client, "attacker2")

    response = client.patch(
        f"/api/auth/users/{victim_id}", json={"email": "taken@example.com"},
        headers=attacker_headers,
    )

    assert response.status_code == 403


def test_unauthenticated_requests_are_rejected(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/users").status_code == 403
    assert client.post("/api/auth/sessions/cleanup").status_code == 403


def test_login_with_a_wrong_password_fails(client):
    _register_and_login(client, "wrongpass")

    response = client.post(
        "/api/auth/login", json={"username": "wrongpass", "password": WRONG_PASSWORD}
    )

    assert response.status_code == 401


def test_api_never_returns_a_password_hash(client):
    _, headers = _register_and_login(client, "nohash")

    body = client.get("/api/auth/me", headers=headers).text
    assert "password_hash" not in body
    assert PBKDF2_ALGORITHM not in body
