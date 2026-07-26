"""
Secure encryption for API keys and secrets
Uses Fernet (symmetric encryption) from cryptography library
"""

import base64
import logging
import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class SecretManager:
    """Manages encryption and decryption of sensitive data"""

    def __init__(self, key_file: Optional[Path] = None):
        """
        Initialize secret manager.

        Args:
            key_file: Path to store encryption key. Defaults to
                :attr:`~realworldmapgen.config.Settings.secret_key_file`.
        """
        if key_file is not None:
            self.key_file = Path(key_file)
        else:
            from ..config import settings

            self.key_file = Path(settings.secret_key_file)
        self._cipher = None

    def _get_or_create_key(self) -> bytes:
        """
        Return the encryption key, generating one on first use.

        The key used to be derived with PBKDF2 from a hardcoded password and a
        hardcoded salt, both visible in this file. Every install therefore had
        the same key, and anyone holding a copy of the settings file could
        recompute it and read the stored credentials without ever seeing the
        key file. It is now random per install.
        """
        if self.key_file.exists():
            # Includes keys written by the old derivation, so credentials
            # encrypted before this change still decrypt.
            return self.key_file.read_bytes()

        key = Fernet.generate_key()

        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        # Create with 0600 from the start rather than chmod'ing afterwards,
        # which leaves the key world-readable in between.
        try:
            descriptor = os.open(self.key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            # Another process won the race; its key is the one to use.
            return self.key_file.read_bytes()
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(key)
        except BaseException:
            self.key_file.unlink(missing_ok=True)
            raise

        logger.info("Generated a new credential encryption key at %s", self.key_file)
        return key

    @property
    def cipher(self) -> Fernet:
        """Get cipher instance"""
        if self._cipher is None:
            key = self._get_or_create_key()
            self._cipher = Fernet(key)
        return self._cipher

    def encrypt(self, data: str) -> str:
        """
        Encrypt string data.

        Args:
            data: Plaintext string

        Returns:
            Base64-encoded encrypted string
        """
        if not data:
            return ""

        encrypted = self.cipher.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt encrypted data.

        Args:
            encrypted_data: Base64-encoded encrypted string

        Returns:
            Decrypted plaintext string
        """
        if not encrypted_data:
            return ""

        try:
            encrypted = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.cipher.decrypt(encrypted)
            return decrypted.decode()
        except Exception:
            # If decryption fails, return empty string
            # This can happen if key changed or data corrupted
            return ""

    def mask_secret(self, secret: Optional[str], show_chars: int = 4) -> str:
        """
        Mask secret for display (show only last N chars).

        Args:
            secret: Secret to mask
            show_chars: Number of characters to show

        Returns:
            Masked string like "****abcd"
        """
        if not secret or len(secret) == 0:
            return ""

        if len(secret) <= show_chars:
            return "*" * len(secret)

        visible = secret[-show_chars:]
        masked = "*" * (len(secret) - show_chars)
        return f"{masked}{visible}"

    def is_configured(self, secret: Optional[str]) -> bool:
        """Check if secret is configured (not None and not empty)"""
        return bool(secret and len(secret) > 0)


# Global instance
secret_manager = SecretManager()

