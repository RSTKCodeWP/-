"""
Plugin management API routes
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


@router.get("/list")
async def list_plugins():
    """List all registered plugins"""
    try:
        from ..core.plugin_system import get_plugin_registry

        registry = get_plugin_registry()
        plugins = registry.list_plugins()

        return {
            "plugins": plugins,
            "count": len(plugins)
        }
    except Exception as e:
        logger.error(f"Failed to list plugins: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{plugin_name}")
async def get_plugin(plugin_name: str):
    """Get plugin details"""
    try:
        from ..core.plugin_system import get_plugin_registry

        registry = get_plugin_registry()
        plugin = registry.get_plugin(plugin_name)

        if not plugin:
            raise HTTPException(status_code=404, detail="Plugin not found")

        return plugin.metadata
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get plugin: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{plugin_name}/enable")
async def enable_plugin(plugin_name: str):
    """Enable a plugin"""
    try:
        from ..core.plugin_system import get_plugin_registry

        registry = get_plugin_registry()
        success = registry.enable_plugin(plugin_name)

        if not success:
            raise HTTPException(status_code=404, detail="Plugin not found")

        logger.info(f"Enabled plugin: {plugin_name}")

        return {
            "success": True,
            "message": f"Plugin {plugin_name} enabled"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable plugin: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{plugin_name}/disable")
async def disable_plugin(plugin_name: str):
    """Disable a plugin"""
    try:
        from ..core.plugin_system import get_plugin_registry

        registry = get_plugin_registry()
        success = registry.disable_plugin(plugin_name)

        if not success:
            raise HTTPException(status_code=404, detail="Plugin not found")

        logger.info(f"Disabled plugin: {plugin_name}")

        return {
            "success": True,
            "message": f"Plugin {plugin_name} disabled"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disable plugin: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/reload")
async def reload_plugins():
    """Reload all plugins from plugin directory"""
    try:
        from pathlib import Path

        from ..config import settings
        from ..core.plugin_system import get_plugin_registry

        plugin_dir = Path(getattr(settings, 'plugin_dir', './plugins'))

        registry = get_plugin_registry()
        count = registry.load_from_directory(plugin_dir)

        logger.info(f"Reloaded {count} plugins")

        return {
            "success": True,
            "message": f"Loaded {count} plugins",
            "count": count
        }
    except Exception as e:
        logger.error(f"Failed to reload plugins: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


class PluginUploadModel(BaseModel):
    name: str
    code: str


@router.post("/install")
async def install_plugin(plugin: PluginUploadModel):
    """
    Install a plugin from code (Development/Testing)
    In production, this should be more secure
    """
    try:
        from pathlib import Path

        from ..config import settings

        plugin_dir = Path(getattr(settings, 'plugin_dir', './plugins'))
        plugin_dir.mkdir(parents=True, exist_ok=True)

        plugin_file = plugin_dir / f"{plugin.name}.py"

        # Save plugin code
        with open(plugin_file, 'w') as f:
            f.write(plugin.code)

        logger.info(f"Installed plugin: {plugin.name}")

        return {
            "success": True,
            "message": f"Plugin {plugin.name} installed. Run /api/plugins/reload to activate.",
            "file": str(plugin_file)
        }
    except Exception as e:
        logger.error(f"Failed to install plugin: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

