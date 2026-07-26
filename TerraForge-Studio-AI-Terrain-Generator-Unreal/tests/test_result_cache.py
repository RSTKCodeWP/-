"""
Tests for the terrain result cache.

The cache had six API endpoints, a wired UI panel and three documented
settings, but nothing ever called ``store_result`` - so it was permanently
empty and ``GenerationResult.cached`` was always False.
"""

from __future__ import annotations

import time

import pytest

from realworldmapgen.core.cache_manager import TerrainCacheManager
from realworldmapgen.core.terrain_generator import TerraForgeGenerator
from realworldmapgen.models import MapGenerationRequest

BBOX = {"north": 37.80, "south": 37.79, "east": -122.40, "west": -122.41}


def _request(**overrides) -> MapGenerationRequest:
    payload = {"name": "terrain", "bbox": BBOX, "resolution": 128}
    payload.update(overrides)
    return MapGenerationRequest(**payload)


@pytest.fixture
def manager(tmp_path) -> TerrainCacheManager:
    return TerrainCacheManager(tmp_path / "cache")


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------
def test_identical_requests_share_a_key(manager, monkeypatch):
    generator = TerraForgeGenerator.__new__(TerraForgeGenerator)
    generator.cache_manager = manager

    assert generator._cache_key(_request()) == generator._cache_key(_request())


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "other"},
        {"resolution": 256},
        {"export_formats": ["gltf"]},
        {"elevation_source": "srtm"},
        {"enable_roads": False},
        {"enable_weightmaps": False},
        {"bbox": {"north": 37.81, "south": 37.79, "east": -122.40, "west": -122.41}},
    ],
)
def test_anything_affecting_output_changes_the_key(manager, overrides):
    generator = TerraForgeGenerator.__new__(TerraForgeGenerator)
    generator.cache_manager = manager

    assert generator._cache_key(_request()) != generator._cache_key(_request(**overrides))


def test_name_is_part_of_the_key(manager):
    """
    Output files are named after the terrain, so two names cannot share an
    entry without producing files whose names disagree with the request.
    """
    generator = TerraForgeGenerator.__new__(TerraForgeGenerator)
    generator.cache_manager = manager

    assert generator._cache_key(_request(name="a")) != generator._cache_key(_request(name="b"))


# ---------------------------------------------------------------------------
# Store and restore
# ---------------------------------------------------------------------------
def test_store_then_restore_round_trip(manager, tmp_path):
    source = tmp_path / "output" / "terrain"
    (source / "unity").mkdir(parents=True)
    (source / "unity" / "heightmap.raw").write_bytes(b"heights")
    (source / "thumbnail.png").write_bytes(b"png")

    assert manager.store_result("key-1", source) is True

    destination = tmp_path / "restored"
    assert manager.restore_result("key-1", destination) is True
    assert (destination / "unity" / "heightmap.raw").read_bytes() == b"heights"
    assert (destination / "thumbnail.png").exists()


def test_restore_reports_a_miss_for_an_unknown_key(manager, tmp_path):
    assert manager.restore_result("never-stored", tmp_path / "out") is False


def test_restore_replaces_existing_contents(manager, tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    (source / "good.txt").write_text("cached")
    manager.store_result("key-2", source)

    destination = tmp_path / "dst"
    destination.mkdir()
    (destination / "stale.txt").write_text("leftover")

    assert manager.restore_result("key-2", destination) is True
    assert (destination / "good.txt").read_text() == "cached"
    assert not (destination / "stale.txt").exists()


def test_expired_entries_are_a_miss(manager, tmp_path):
    from datetime import datetime, timedelta

    source = tmp_path / "src"
    source.mkdir()
    (source / "f.txt").write_text("x")
    manager.store_result("key-3", source)

    entry = manager.metadata["entries"]["key-3"]
    entry["created"] = (datetime.now() - timedelta(days=999)).isoformat()

    assert manager.get_cached_result("key-3") is None


def test_entry_missing_from_disk_is_a_miss(manager, tmp_path):
    import shutil

    source = tmp_path / "src"
    source.mkdir()
    (source / "f.txt").write_text("x")
    manager.store_result("key-4", source)

    shutil.rmtree(manager.metadata["entries"]["key-4"]["path"])

    assert manager.get_cached_result("key-4") is None
    # The dangling metadata entry is cleaned up rather than left behind.
    assert "key-4" not in manager.metadata["entries"]


def test_configured_limits_are_applied(tmp_path):
    from realworldmapgen.core.cache_manager import get_cache_manager

    get_cache_manager.cache_clear()
    manager = get_cache_manager(str(tmp_path / "c"), 2.5, 7)

    assert manager.max_cache_size == pytest.approx(2.5 * 1024**3)
    assert manager.max_age.days == 7


# ---------------------------------------------------------------------------
# Through the API
# ---------------------------------------------------------------------------
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


def test_second_identical_request_is_served_from_cache(client):
    first = _generate(client, "cached_run")
    assert first["status"] == "completed", first.get("error")
    assert first["result"]["cached"] is False

    second = _generate(client, "cached_run")
    assert second["status"] == "completed"
    assert second["result"]["cached"] is True


def test_cached_result_still_has_its_files_on_disk(client):
    from pathlib import Path

    _generate(client, "cached_files")
    second = _generate(client, "cached_files")

    assert second["result"]["cached"] is True
    for export in second["result"]["exports"]:
        for path in export["files"].values():
            assert Path(path).exists(), f"{path} missing after cache restore"


def test_cache_manifest_is_not_shipped_to_users(client):
    import io
    import zipfile

    _generate(client, "manifest_check")
    _generate(client, "manifest_check")

    download = client.get("/api/maps/manifest_check/download/zip")
    names = zipfile.ZipFile(io.BytesIO(download.content)).namelist()

    assert not any("cache_result" in name for name in names)


def test_cache_stats_endpoint_reflects_stored_entries(client):
    _generate(client, "stats_check")

    stats = client.get("/api/cache/stats").json()
    assert stats["total_entries"] >= 1


def test_a_corrupt_entry_falls_back_to_regenerating(client, monkeypatch):
    """A damaged cache entry must never surface broken output."""
    from realworldmapgen.core.generator_provider import get_generator

    _generate(client, "corrupt_entry")

    generator = get_generator()

    def broken_restore(cache_key, destination):
        destination.mkdir(parents=True, exist_ok=True)
        # Restored, but the manifest is absent - the entry is unusable.
        return True

    monkeypatch.setattr(generator.cache_manager, "restore_result", broken_restore)

    payload = _generate(client, "corrupt_entry")
    assert payload["status"] == "completed"
    assert payload["result"]["cached"] is False


# ---------------------------------------------------------------------------
# Batch progress
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_batch_jobs_report_real_progress():
    """
    Queue jobs must reflect generation progress.

    update_job_progress was never called, so /api/batch/jobs and the queue UI
    showed a progress bar permanently stuck at 0%.
    """
    from realworldmapgen.core.generator_provider import get_generator
    from realworldmapgen.core.queue_manager import queue_manager

    generator = get_generator()
    seen: list[float] = []

    async def observer(progress: float, step: str) -> None:
        seen.append(progress)

    request = MapGenerationRequest(
        name="progress_run",
        bbox=BBOX,
        resolution=128,
        export_formats=["unity"],
        enable_roads=False,
        enable_buildings=False,
    )

    status = await generator.generate_terrain(request, on_progress=observer)
    assert status.status == "completed", status.error

    # Let the fire-and-forget observer tasks run.
    import asyncio

    await asyncio.sleep(0)

    assert seen, "no progress was reported"
    assert max(seen) == 100.0
    assert seen == sorted(seen), "progress must not go backwards"

    queue_manager.jobs.clear()


@pytest.mark.asyncio
async def test_a_failing_observer_does_not_break_generation():
    from realworldmapgen.core.generator_provider import get_generator

    async def broken_observer(progress: float, step: str) -> None:
        raise RuntimeError("observer is broken")

    request = MapGenerationRequest(
        name="broken_observer",
        bbox=BBOX,
        resolution=128,
        export_formats=["unity"],
        enable_roads=False,
        enable_buildings=False,
    )

    status = await get_generator().generate_terrain(request, on_progress=broken_observer)
    assert status.status == "completed", status.error
