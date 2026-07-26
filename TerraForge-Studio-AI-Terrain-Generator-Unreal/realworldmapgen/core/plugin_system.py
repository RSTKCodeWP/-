"""
TerraForge Plugin System
Extensible plugin architecture for custom terrain processing
"""

import importlib.util
import inspect
import logging
from abc import ABC
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class PluginHookType:
    """Available plugin hook types"""
    ON_TERRAIN_GENERATED = "on_terrain_generated"
    ON_EXPORT = "on_export"
    ON_PREVIEW = "on_preview"
    ON_CACHE_HIT = "on_cache_hit"
    ON_ELEVATION_ACQUIRED = "on_elevation_acquired"
    ON_VECTOR_ACQUIRED = "on_vector_acquired"
    PRE_PROCESS = "pre_process"
    POST_PROCESS = "post_process"


class TerraForgePlugin(ABC):  # noqa: B024  # hooks are opt-in, none are required
    """
    Base class for TerraForge plugins

    To create a plugin, inherit from this class and override the hooks you
    need. Every hook has a no-op default, so no method is mandatory - which is
    why this class deliberately declares no abstract methods.
    """

    def __init__(self):
        self.name = "UnnamedPlugin"
        self.version = "1.0.0"
        self.author = "Unknown"
        self.description = "No description provided"
        self.enabled = True

    @property
    def metadata(self) -> Dict[str, Any]:
        """Get plugin metadata"""
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "enabled": self.enabled,
        }

    # Lifecycle hooks (optional - override as needed)

    def on_terrain_generated(self, terrain_data: Any, metadata: Dict) -> Optional[Any]:
        """
        Called after terrain is generated but before export

        Args:
            terrain_data: Elevation data and terrain information
            metadata: Generation metadata (bbox, resolution, etc.)

        Returns:
            Modified terrain_data or None to keep original
        """
        return None

    def on_export(self, export_data: Any, format: str, metadata: Dict) -> Optional[Any]:
        """
        Called before exporting to a specific format

        Args:
            export_data: Data to be exported
            format: Export format (unreal5, unity, gltf, etc.)
            metadata: Export metadata

        Returns:
            Modified export_data or None to keep original
        """
        return None

    def on_preview(self, preview_data: Any, metadata: Dict) -> Optional[Any]:
        """
        Called when generating preview/thumbnail

        Args:
            preview_data: Preview data
            metadata: Preview metadata

        Returns:
            Modified preview_data or None to keep original
        """
        return None

    def on_cache_hit(self, cache_key: str, cached_data: Any) -> None:  # noqa: B027
        """
        Called when a cache hit occurs

        Args:
            cache_key: The cache key that was hit
            cached_data: The cached data
        """
        pass

    def on_elevation_acquired(self, elevation_data: Any, source: str, metadata: Dict) -> Optional[Any]:
        """
        Called after elevation data is acquired from a source

        Args:
            elevation_data: Raw elevation data
            source: Data source name
            metadata: Acquisition metadata

        Returns:
            Modified elevation_data or None to keep original
        """
        return None

    def on_vector_acquired(self, vector_data: Any, source: str, metadata: Dict) -> Optional[Any]:
        """
        Called after vector data (roads, buildings) is acquired

        Args:
            vector_data: Raw vector data
            source: Data source name
            metadata: Acquisition metadata

        Returns:
            Modified vector_data or None to keep original
        """
        return None

    def pre_process(self, request: Any) -> Optional[Any]:
        """
        Called before terrain generation starts

        Args:
            request: Generation request

        Returns:
            Modified request or None to keep original
        """
        return None

    def post_process(self, result: Any, metadata: Dict) -> Optional[Any]:
        """
        Called after terrain generation completes

        Args:
            result: Generation result
            metadata: Generation metadata

        Returns:
            Modified result or None to keep original
        """
        return None

    # Helper methods

    def log_info(self, message: str):
        """Log info message with plugin name"""
        logger.info(f"[{self.name}] {message}")

    def log_warning(self, message: str):
        """Log warning message with plugin name"""
        logger.warning(f"[{self.name}] {message}")

    def log_error(self, message: str):
        """Log error message with plugin name"""
        logger.error(f"[{self.name}] {message}")


class PluginRegistry:
    """
    Plugin registry and lifecycle manager
    """

    def __init__(self):
        self.plugins: Dict[str, TerraForgePlugin] = {}
        self.hooks: Dict[str, List[Callable]] = {
            PluginHookType.ON_TERRAIN_GENERATED: [],
            PluginHookType.ON_EXPORT: [],
            PluginHookType.ON_PREVIEW: [],
            PluginHookType.ON_CACHE_HIT: [],
            PluginHookType.ON_ELEVATION_ACQUIRED: [],
            PluginHookType.ON_VECTOR_ACQUIRED: [],
            PluginHookType.PRE_PROCESS: [],
            PluginHookType.POST_PROCESS: [],
        }
        logger.info("Plugin registry initialized")

    def register(self, plugin: TerraForgePlugin) -> bool:
        """
        Register a plugin

        Args:
            plugin: Plugin instance

        Returns:
            True if registered successfully
        """
        try:
            if not isinstance(plugin, TerraForgePlugin):
                logger.error(f"Plugin must inherit from TerraForgePlugin: {type(plugin)}")
                return False

            plugin_name = plugin.name

            if plugin_name in self.plugins:
                logger.warning(f"Plugin already registered: {plugin_name}")
                return False

            # Register plugin
            self.plugins[plugin_name] = plugin

            # Register only the hooks this plugin actually overrides.
            for hook_type in self.hooks:
                hook_method = getattr(plugin, hook_type, None)
                if not callable(hook_method):
                    continue

                # In Python 3 an attribute looked up on the class is a plain
                # function with no __func__, so comparing __func__ on both
                # sides raised AttributeError. The broad except below turned
                # that into a silent "registration failed" for every plugin.
                base_method = getattr(TerraForgePlugin, hook_type, None)
                if base_method is None or hook_method.__func__ is not base_method:
                    self.hooks[hook_type].append(hook_method)

            logger.info(f"Registered plugin: {plugin_name} v{plugin.version}")
            return True

        except Exception as e:
            logger.error(f"Failed to register plugin: {e}", exc_info=True)
            return False

    def unregister(self, plugin_name: str) -> bool:
        """
        Unregister a plugin

        Args:
            plugin_name: Name of plugin to unregister

        Returns:
            True if unregistered successfully
        """
        if plugin_name not in self.plugins:
            return False

        plugin = self.plugins[plugin_name]

        # Remove hooks
        for hook_type, hooks in self.hooks.items():
            hook_method = getattr(plugin, hook_type, None)
            if hook_method in hooks:
                hooks.remove(hook_method)

        # Remove plugin
        del self.plugins[plugin_name]

        logger.info(f"Unregistered plugin: {plugin_name}")
        return True

    def execute_hook(self, hook_type: str, *args, **kwargs) -> Any:
        """
        Execute all plugins registered for a hook

        Args:
            hook_type: Type of hook to execute
            *args, **kwargs: Arguments to pass to hook methods

        Returns:
            Modified data if any plugin returns data, otherwise original
        """
        if hook_type not in self.hooks:
            logger.warning(f"Unknown hook type: {hook_type}")
            return None

        result = None

        for hook_func in self.hooks[hook_type]:
            try:
                plugin_result = hook_func(*args, **kwargs)
                if plugin_result is not None:
                    result = plugin_result
                    # Chain results: output of one plugin becomes input to next
                    if args:
                        args = (result,) + args[1:]
            except Exception as e:
                logger.error(f"Plugin hook failed ({hook_type}): {e}")

        return result

    def load_from_directory(self, plugin_dir: Path) -> int:
        """
        Load all plugins from a directory

        Args:
            plugin_dir: Directory containing plugin files

        Returns:
            Number of plugins loaded
        """
        if not plugin_dir.exists():
            logger.warning(f"Plugin directory does not exist: {plugin_dir}")
            return 0

        loaded_count = 0

        for plugin_file in plugin_dir.glob("*.py"):
            if plugin_file.stem.startswith("_"):
                continue  # Skip private files

            try:
                # Load module
                spec = importlib.util.spec_from_file_location(plugin_file.stem, plugin_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Find TerraForgePlugin subclasses
                    for _name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, TerraForgePlugin) and obj != TerraForgePlugin:
                            # Instantiate and register
                            plugin_instance = obj()
                            if self.register(plugin_instance):
                                loaded_count += 1

            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_file}: {e}")

        logger.info(f"Loaded {loaded_count} plugins from {plugin_dir}")
        return loaded_count

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Get list of all registered plugins"""
        return [plugin.metadata for plugin in self.plugins.values()]

    def get_plugin(self, name: str) -> Optional[TerraForgePlugin]:
        """Get plugin by name"""
        return self.plugins.get(name)

    def enable_plugin(self, name: str) -> bool:
        """Enable a plugin"""
        plugin = self.get_plugin(name)
        if plugin:
            plugin.enabled = True
            return True
        return False

    def disable_plugin(self, name: str) -> bool:
        """Disable a plugin"""
        plugin = self.get_plugin(name)
        if plugin:
            plugin.enabled = False
            return True
        return False


# Global plugin registry
_registry = None


def get_plugin_registry() -> PluginRegistry:
    """Get or create global plugin registry"""
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry


# Example plugin for demonstration
class ExampleTerrainEnhancer(TerraForgePlugin):
    """Example plugin that enhances terrain data"""

    def __init__(self):
        super().__init__()
        self.name = "TerrainEnhancer"
        self.version = "1.0.0"
        self.author = "TerraForge Team"
        self.description = "Enhances terrain data with smoothing and detail"

    def on_terrain_generated(self, terrain_data: Any, metadata: Dict) -> Optional[Any]:
        """Apply terrain enhancements"""
        self.log_info(f"Enhancing terrain for {metadata.get('name', 'unknown')}")

        # Example: Apply smoothing (placeholder)
        # In real plugin, you would process terrain_data here

        return terrain_data  # Return modified data

    def post_process(self, result: Any, metadata: Dict) -> Optional[Any]:
        """Post-process the final result"""
        self.log_info("Post-processing complete")
        return result

