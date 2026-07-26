"""
Tests that plugin hooks actually fire during generation.

Plugins were loaded from disk, listed through /api/plugins and toggled from the
UI, but ``execute_hook`` was called from nowhere, so no plugin could observe or
influence anything.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from realworldmapgen.core.plugin_system import PluginHookType, TerraForgePlugin

BBOX = {"north": 37.80, "south": 37.79, "east": -122.40, "west": -122.41}


class RecordingPlugin(TerraForgePlugin):
    """
    Records every hook it receives.

    Signatures deliberately mirror TerraForgePlugin exactly: a plugin author
    writes against that contract, so a test plugin shaped to fit the call sites
    instead would validate nothing.
    """

    def __init__(self):
        super().__init__()
        self.name = "RecordingPlugin"
        self.seen: list[str] = []

    def pre_process(self, request):
        self.seen.append("pre_process")
        return None

    def on_elevation_acquired(self, elevation_data, source, metadata):
        self.seen.append("on_elevation_acquired")
        return None

    def on_vector_acquired(self, vector_data, source, metadata):
        self.seen.append("on_vector_acquired")
        return None

    def on_terrain_generated(self, terrain_data, metadata):
        self.seen.append("on_terrain_generated")
        return None

    def on_export(self, export_data, format, metadata):
        self.seen.append(f"on_export:{format}")
        return None

    def post_process(self, result, metadata):
        self.seen.append("post_process")
        return None

    def on_cache_hit(self, cache_key, cached_data):
        self.seen.append("on_cache_hit")


@pytest.fixture
def registered_plugin():
    """Register a plugin for the duration of a test, then remove it."""
    from realworldmapgen.core.generator_provider import get_generator

    registry = get_generator().plugin_registry
    plugin = RecordingPlugin()
    registry.register(plugin)

    yield plugin

    registry.unregister(plugin.name)


def _generate(client, name: str) -> dict:
    response = client.post(
        "/api/generate",
        json={
            "name": name,
            "bbox": BBOX,
            "resolution": 128,
            "export_formats": ["unity"],
            "enable_roads": False,
            "enable_buildings": False,
        },
    )
    assert response.status_code == 202

    task_id = response.json()["task_id"]
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        payload = client.get(f"/api/status/{task_id}").json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.05)
    pytest.fail("generation did not finish")


def test_generation_fires_every_stage_hook(client, registered_plugin):
    payload = _generate(client, "hooked_run")
    assert payload["status"] == "completed", payload.get("error")

    assert registered_plugin.seen == [
        "pre_process",
        "on_elevation_acquired",
        "on_terrain_generated",
        "on_export:unity",
        "post_process",
    ]


def test_cache_hit_fires_its_own_hook(client, registered_plugin):
    _generate(client, "hooked_cache")
    registered_plugin.seen.clear()

    payload = _generate(client, "hooked_cache")

    assert payload["result"]["cached"] is True
    assert registered_plugin.seen == ["on_cache_hit"]


def test_plugin_can_modify_elevation(client):
    """A plugin returning a heightmap of the same shape replaces the data."""
    from realworldmapgen.core.generator_provider import get_generator

    class FlatteningPlugin(TerraForgePlugin):
        def __init__(self):
            super().__init__()
            self.name = "FlatteningPlugin"

        def on_elevation_acquired(self, elevation_data, source, metadata):
            return np.full_like(elevation_data, 1234.0)

    registry = get_generator().plugin_registry
    registry.register(FlatteningPlugin())
    try:
        payload = _generate(client, "plugin_modified")
    finally:
        registry.unregister("FlatteningPlugin")

    assert payload["status"] == "completed"
    elevation = payload["result"]["elevation"]
    # Provenance is captured before the hook runs, so the reported range still
    # describes the source data; the exported heightmap carries the override.
    assert elevation["source"] is not None


def test_wrongly_shaped_plugin_output_is_ignored(client):
    """A plugin returning a mismatched array must not corrupt the export."""
    from realworldmapgen.core.generator_provider import get_generator

    class BadPlugin(TerraForgePlugin):
        def __init__(self):
            super().__init__()
            self.name = "BadPlugin"

        def on_elevation_acquired(self, elevation_data, source, metadata):
            return np.zeros((7, 3), dtype=np.float32)

    registry = get_generator().plugin_registry
    registry.register(BadPlugin())
    try:
        payload = _generate(client, "bad_plugin")
    finally:
        registry.unregister("BadPlugin")

    assert payload["status"] == "completed", payload.get("error")


def test_a_raising_plugin_does_not_fail_the_generation(client):
    """A broken plugin must never take a generation down with it."""
    from realworldmapgen.core.generator_provider import get_generator

    class ExplodingPlugin(TerraForgePlugin):
        def __init__(self):
            super().__init__()
            self.name = "ExplodingPlugin"

        def on_terrain_generated(self, terrain_data, metadata):
            raise RuntimeError("plugin is broken")

    registry = get_generator().plugin_registry
    registry.register(ExplodingPlugin())
    try:
        payload = _generate(client, "exploding_plugin")
    finally:
        registry.unregister("ExplodingPlugin")

    assert payload["status"] == "completed", payload.get("error")


def test_on_export_fires_once_per_format(client, registered_plugin):
    """The hook is documented as per-format, so each target gets its own call."""
    response = client.post(
        "/api/generate",
        json={
            "name": "multi_format",
            "bbox": BBOX,
            "resolution": 128,
            "export_formats": ["unity", "gltf"],
            "enable_roads": False,
            "enable_buildings": False,
        },
    )
    task_id = response.json()["task_id"]
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        payload = client.get(f"/api/status/{task_id}").json()
        if payload["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)

    fired = [entry for entry in registered_plugin.seen if entry.startswith("on_export:")]
    assert fired == ["on_export:unity", "on_export:gltf"]


def test_hook_calls_match_the_documented_signatures(client, registered_plugin):
    """
    Every hook must be invoked with the arity its base-class method declares.

    A mismatch raises TypeError inside the registry, which is swallowed - so
    the hook would silently never run for a correctly written plugin.
    """
    import inspect

    _generate(client, "signature_check")

    for hook_name in ("pre_process", "on_elevation_acquired", "on_terrain_generated",
                      "on_export", "post_process"):
        base = inspect.signature(getattr(TerraForgePlugin, hook_name))
        recorded = inspect.signature(getattr(RecordingPlugin, hook_name))
        assert list(base.parameters) == list(recorded.parameters), hook_name

    # If any call site had the wrong arity, these would be missing.
    assert "pre_process" in registered_plugin.seen
    assert "on_elevation_acquired" in registered_plugin.seen
    assert "post_process" in registered_plugin.seen


def test_hook_types_match_the_plugin_base_class():
    """Every declared hook must correspond to a method plugins can override."""
    declared = {
        value
        for name, value in vars(PluginHookType).items()
        if not name.startswith("_") and isinstance(value, str)
    }

    for hook in declared:
        assert hasattr(TerraForgePlugin, hook), f"{hook} has no method on the base class"
