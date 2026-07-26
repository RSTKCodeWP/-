"""
Settings API Routes
Endpoints for managing user settings
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ..settings import (
    MaskedCredentials,
    SettingsUpdate,
    UserSettings,
    settings_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/", response_model=UserSettings)
async def get_settings():
    """
    Get current user settings.

    Note: API keys are returned in plain text only when reading.
    They are encrypted when stored.
    """
    try:
        settings = settings_manager.get()
        return settings
    except Exception as e:
        logger.error(f"Failed to get settings: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/masked", response_model=MaskedCredentials)
async def get_masked_credentials():
    """
    Get credentials status without exposing secrets.
    Returns only whether each source is enabled and configured.
    """
    try:
        return settings_manager.get_masked_credentials()
    except Exception as e:
        logger.error(f"Failed to get masked credentials: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/", response_model=UserSettings)
async def update_settings(updates: SettingsUpdate):
    """
    Update user settings.

    Only updates the provided fields, leaves others unchanged.
    """
    try:
        settings = settings_manager.update(updates)
        logger.info("Settings updated successfully")
        return settings
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/test-connection/{source}")
async def test_connection(source: str):
    """
    Test connection to a data source.

    Args:
        source: Source name (sentinelhub, opentopography, azure_maps, osm)

    Returns:
        Success status and error message if any
    """
    try:
        # The manager performs a real request and reports both whether the
        # source is configured and whether it was actually reachable.
        return await settings_manager.test_connection(source)
    except Exception as e:
        logger.error(f"Connection test failed for {source}: {e}")
        return {
            "source": source,
            "success": False,
            "error": str(e)
        }


@router.get("/export")
async def export_settings(include_credentials: bool = False) -> Dict[str, Any]:
    """
    Export settings for backup/transfer.

    Args:
        include_credentials: If True, include encrypted credentials

    Returns:
        Settings dictionary
    """
    try:
        return settings_manager.export_settings(include_credentials)
    except Exception as e:
        logger.error(f"Failed to export settings: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/import")
async def import_settings(data: Dict[str, Any]) -> UserSettings:
    """
    Import settings from backup.

    Args:
        data: Settings dictionary

    Returns:
        Imported settings
    """
    try:
        settings = settings_manager.import_settings(data)
        logger.info("Settings imported successfully")
        return settings
    except Exception as e:
        logger.error(f"Failed to import settings: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/reset")
async def reset_settings() -> UserSettings:
    """
    Reset all settings to defaults.

    Warning: This will delete all configured API keys!
    """
    try:
        settings = settings_manager.reset_to_defaults()
        logger.warning("Settings reset to defaults")
        return settings
    except Exception as e:
        logger.error(f"Failed to reset settings: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/first-run")
async def check_first_run():
    """Check if this is the first run (show setup wizard)"""
    settings = settings_manager.get()
    return {
        "first_run": settings.first_run,
        "show_wizard": settings.first_run
    }


@router.post("/complete-wizard")
async def complete_wizard():
    """Mark setup wizard as completed"""
    settings = settings_manager.get()
    settings.first_run = False
    settings_manager.save()

    return {
        "success": True,
        "message": "Setup wizard completed"
    }

