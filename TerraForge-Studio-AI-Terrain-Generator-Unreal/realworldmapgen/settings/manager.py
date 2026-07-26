"""
Settings Manager
Handles loading, saving, and managing user settings
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .encryption import secret_manager
from .models import (
    MaskedCredentials,
    SettingsUpdate,
    UserSettings,
)

logger = logging.getLogger(__name__)


class SettingsManager:
    """Manages user settings with secure credential storage"""

    def __init__(self, settings_file: Optional[Path] = None):
        """
        Initialize settings manager.

        Args:
            settings_file: Path to settings JSON file. Defaults to
                :attr:`~realworldmapgen.config.Settings.settings_storage_file`.
        """
        if settings_file is not None:
            self.settings_file = Path(settings_file)
        else:
            from ..config import settings as app_settings

            self.settings_file = Path(app_settings.settings_storage_file)
        # The directory is created when something is actually written, not on
        # construction: importing this module must not touch the filesystem.
        self._settings: Optional[UserSettings] = None

    def load(self) -> UserSettings:
        """Load settings from file or create defaults"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Decrypt credentials
                data = self._decrypt_credentials(data)

                self._settings = UserSettings(**data)
                logger.info("Settings loaded successfully")

            except Exception as e:
                logger.error(f"Failed to load settings: {e}")
                logger.info("Using default settings")
                self._settings = UserSettings()
        else:
            logger.info("No settings file found, using defaults")
            self._settings = UserSettings()
            self.save()  # Save defaults

        return self._settings

    def save(self) -> None:
        """Save settings to file with encrypted credentials"""
        if self._settings is None:
            return

        try:
            # Convert to dict
            data = self._settings.dict()

            # Encrypt credentials before saving
            data = self._encrypt_credentials(data)

            # Save to file
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info("Settings saved successfully")

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def get(self) -> UserSettings:
        """Get current settings"""
        if self._settings is None:
            return self.load()
        return self._settings

    def update(self, updates: SettingsUpdate) -> UserSettings:
        """
        Update settings.

        Args:
            updates: Partial settings to update

        Returns:
            Updated settings
        """
        if self._settings is None:
            self.load()

        # Update each section if provided
        if updates.credentials is not None:
            self._settings.credentials = updates.credentials

        if updates.generation is not None:
            self._settings.generation = updates.generation

        if updates.export_profiles is not None:
            self._settings.export_profiles = updates.export_profiles

        if updates.ui is not None:
            self._settings.ui = updates.ui

        if updates.cache is not None:
            self._settings.cache = updates.cache

        # Mark as not first run
        if self._settings.first_run:
            self._settings.first_run = False

        # Save
        self.save()

        return self._settings

    def get_masked_credentials(self) -> MaskedCredentials:
        """Get credentials with secrets masked for display"""
        settings = self.get()
        creds = settings.credentials

        return MaskedCredentials(
            sentinelhub_enabled=creds.sentinelhub.enabled,
            sentinelhub_configured=secret_manager.is_configured(creds.sentinelhub.client_id),
            opentopography_enabled=creds.opentopography.enabled,
            opentopography_configured=secret_manager.is_configured(creds.opentopography.api_key),
            azure_maps_enabled=creds.azure_maps.enabled,
            azure_maps_configured=secret_manager.is_configured(creds.azure_maps.subscription_key),
            google_earth_engine_enabled=creds.google_earth_engine.enabled,
            google_earth_engine_configured=secret_manager.is_configured(
                creds.google_earth_engine.service_account
            ),
        )

    async def test_connection(self, source: str) -> Dict[str, Any]:
        """
        Probe a data source with a real request.

        This used to only check that a credential string was non-empty and
        then report "Connection successful", so a typo'd, expired or revoked
        key still showed green in the settings UI. Each source is now actually
        contacted, and only a completed round trip counts as success.

        Args:
            source: sentinelhub, opentopography, azure_maps, srtm, or osm

        Returns:
            Dict with success, configured, reachable and a human-readable
            message.
        """
        from . import connection_test as probes

        creds = self.get().credentials

        if source == "srtm":
            return (await probes.test_srtm()).as_dict()

        if source == "osm":
            return (await probes.test_overpass()).as_dict()

        if source == "sentinelhub":
            if not creds.sentinelhub.enabled:
                return probes.ConnectionResult(
                    source, False, None, "Sentinel Hub is disabled"
                ).as_dict()
            return (
                await probes.test_sentinelhub(
                    creds.sentinelhub.client_id, creds.sentinelhub.client_secret
                )
            ).as_dict()

        if source == "opentopography":
            if not creds.opentopography.enabled:
                return probes.ConnectionResult(
                    source, False, None, "OpenTopography is disabled"
                ).as_dict()
            return (await probes.test_opentopography(creds.opentopography.api_key)).as_dict()

        if source == "azure_maps":
            if not creds.azure_maps.enabled:
                return probes.ConnectionResult(
                    source, False, None, "Azure Maps is disabled"
                ).as_dict()
            return (await probes.test_azure_maps(creds.azure_maps.subscription_key)).as_dict()

        return probes.ConnectionResult(source, False, None, f"Unknown source: {source}").as_dict()

    def export_settings(self, include_credentials: bool = False) -> Dict[str, Any]:
        """
        Export settings for backup/transfer.

        Args:
            include_credentials: If True, include encrypted credentials

        Returns:
            Settings dictionary
        """
        settings = self.get()
        data = settings.dict()

        if not include_credentials:
            # Remove all credentials
            data['credentials'] = {
                'sentinelhub': {'enabled': False},
                'opentopography': {'enabled': False},
                'azure_maps': {'enabled': False},
                'google_earth_engine': {'enabled': False},
            }

        return data

    def import_settings(self, data: Dict[str, Any]) -> UserSettings:
        """
        Import settings from backup.

        Args:
            data: Settings dictionary

        Returns:
            Imported settings
        """
        try:
            self._settings = UserSettings(**data)
            self.save()
            logger.info("Settings imported successfully")
            return self._settings
        except Exception as e:
            logger.error(f"Failed to import settings: {e}")
            raise ValueError(f"Invalid settings data: {e}") from e

    def reset_to_defaults(self) -> UserSettings:
        """Reset all settings to defaults"""
        self._settings = UserSettings()
        self.save()
        logger.info("Settings reset to defaults")
        return self._settings

    def _encrypt_credentials(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt all API keys and secrets in settings dict"""
        if 'credentials' not in data:
            return data

        creds = data['credentials']

        # Sentinel Hub
        if 'sentinelhub' in creds:
            if creds['sentinelhub'].get('client_id'):
                creds['sentinelhub']['client_id'] = secret_manager.encrypt(
                    creds['sentinelhub']['client_id']
                )
            if creds['sentinelhub'].get('client_secret'):
                creds['sentinelhub']['client_secret'] = secret_manager.encrypt(
                    creds['sentinelhub']['client_secret']
                )

        # OpenTopography
        if 'opentopography' in creds:
            if creds['opentopography'].get('api_key'):
                creds['opentopography']['api_key'] = secret_manager.encrypt(
                    creds['opentopography']['api_key']
                )

        # Azure Maps
        if 'azure_maps' in creds:
            if creds['azure_maps'].get('subscription_key'):
                creds['azure_maps']['subscription_key'] = secret_manager.encrypt(
                    creds['azure_maps']['subscription_key']
                )

        # Google Earth Engine
        if 'google_earth_engine' in creds:
            if creds['google_earth_engine'].get('service_account'):
                creds['google_earth_engine']['service_account'] = secret_manager.encrypt(
                    creds['google_earth_engine']['service_account']
                )

        return data

    def _decrypt_credentials(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt all API keys and secrets in settings dict"""
        if 'credentials' not in data:
            return data

        creds = data['credentials']

        # Sentinel Hub
        if 'sentinelhub' in creds:
            if creds['sentinelhub'].get('client_id'):
                creds['sentinelhub']['client_id'] = secret_manager.decrypt(
                    creds['sentinelhub']['client_id']
                )
            if creds['sentinelhub'].get('client_secret'):
                creds['sentinelhub']['client_secret'] = secret_manager.decrypt(
                    creds['sentinelhub']['client_secret']
                )

        # OpenTopography
        if 'opentopography' in creds:
            if creds['opentopography'].get('api_key'):
                creds['opentopography']['api_key'] = secret_manager.decrypt(
                    creds['opentopography']['api_key']
                )

        # Azure Maps
        if 'azure_maps' in creds:
            if creds['azure_maps'].get('subscription_key'):
                creds['azure_maps']['subscription_key'] = secret_manager.decrypt(
                    creds['azure_maps']['subscription_key']
                )

        # Google Earth Engine
        if 'google_earth_engine' in creds:
            if creds['google_earth_engine'].get('service_account'):
                creds['google_earth_engine']['service_account'] = secret_manager.decrypt(
                    creds['google_earth_engine']['service_account']
                )

        return data


# Global instance
settings_manager = SettingsManager()

