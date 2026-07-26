"""
Tests for credential storage in the settings subsystem.

The encryption key used to be derived with PBKDF2 from a password and a salt
that were both hardcoded in ``encryption.py``. Every install produced the same
key, so "encrypted at rest" credentials could be read by anyone holding the
settings file - the key file itself was never needed.
"""

from __future__ import annotations

import base64
import stat

import pytest
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from realworldmapgen.settings.encryption import SecretManager
from realworldmapgen.settings.manager import SettingsManager

#: Stand-in for a stored credential. It authenticates against nothing, and is
#: named rather than written inline so secret scanners have nothing to flag.
PLAINTEXT = "pytest-input-not-a-credential"

#: The key the old implementation produced, recomputed here from the constants
#: that used to live in the source.
LEGACY_KEY = base64.urlsafe_b64encode(
    PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b"salt", iterations=100_000)
    .derive(b"password")
)


@pytest.fixture
def secrets(tmp_path) -> SecretManager:
    return SecretManager(tmp_path / ".secret_key")


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------
def test_key_is_not_the_hardcoded_one(secrets):
    secrets.encrypt("anything")

    assert secrets.key_file.read_bytes() != LEGACY_KEY


def test_two_installs_get_different_keys(tmp_path):
    first = SecretManager(tmp_path / "a" / ".secret_key")
    second = SecretManager(tmp_path / "b" / ".secret_key")

    first.encrypt("x")
    second.encrypt("x")

    assert first.key_file.read_bytes() != second.key_file.read_bytes()


def test_ciphertext_cannot_be_read_with_the_legacy_key(secrets):
    """This is the whole point: the key file must actually be required."""
    token = secrets.encrypt(PLAINTEXT)

    with pytest.raises(InvalidToken):
        Fernet(LEGACY_KEY).decrypt(base64.urlsafe_b64decode(token.encode()))


def test_key_file_is_not_world_readable(secrets):
    secrets.encrypt("x")

    mode = secrets.key_file.stat().st_mode
    assert not mode & stat.S_IRGRP
    assert not mode & stat.S_IROTH


def test_key_is_generated_once_and_reused(secrets):
    token = secrets.encrypt("stable")
    key = secrets.key_file.read_bytes()

    reopened = SecretManager(secrets.key_file)

    assert reopened.decrypt(token) == "stable"
    assert secrets.key_file.read_bytes() == key


def test_existing_legacy_key_files_keep_working(tmp_path):
    """Credentials encrypted before this change must still decrypt."""
    key_file = tmp_path / ".secret_key"
    key_file.write_bytes(LEGACY_KEY)
    old_token = base64.urlsafe_b64encode(
        Fernet(LEGACY_KEY).encrypt(b"key-stored-before-the-fix")
    ).decode()

    assert SecretManager(key_file).decrypt(old_token) == "key-stored-before-the-fix"


# ---------------------------------------------------------------------------
# Round trip
# ---------------------------------------------------------------------------
def test_encrypt_decrypt_round_trip(secrets):
    assert secrets.decrypt(secrets.encrypt(PLAINTEXT)) == PLAINTEXT


def test_empty_values_are_passed_through(secrets):
    assert secrets.encrypt("") == ""
    assert secrets.decrypt("") == ""


def test_undecryptable_data_returns_empty_rather_than_raising(secrets):
    assert secrets.decrypt("not-valid-base64-ciphertext") == ""


def test_masking_keeps_only_the_tail(secrets):
    assert secrets.mask_secret("abcdefgh") == "****efgh"
    assert secrets.mask_secret("ab") == "**"
    assert secrets.mask_secret(None) == ""


# ---------------------------------------------------------------------------
# Storage location
# ---------------------------------------------------------------------------
def test_importing_the_module_does_not_create_directories(tmp_path):
    """Construction used to mkdir, so merely importing wrote to the checkout."""
    target = tmp_path / "not-created-yet"

    SettingsManager(target / "settings.json")
    SecretManager(target / ".secret_key")

    assert not target.exists()


def test_saving_creates_the_storage_directory(tmp_path):
    manager = SettingsManager(tmp_path / "nested" / "settings.json")

    manager.load()

    assert manager.settings_file.exists()


def test_storage_paths_come_from_configuration():
    from realworldmapgen.config import settings

    assert SettingsManager().settings_file == settings.settings_storage_file
    assert SecretManager().key_file == settings.secret_key_file
