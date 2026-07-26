"""
Tests that fetched vector features actually reach the user.

No exporter reads ``TerrainData.roads`` or ``.buildings``, so without an
explicit write step the features would be downloaded and silently dropped.
These tests cover the write step and the summary reported to API clients.
"""

from __future__ import annotations

import json

import pytest

from realworldmapgen.core.terrain_generator import TerraForgeGenerator

ROAD = {
    "type": "Feature",
    "geometry": {"type": "LineString", "coordinates": [[-122.4, 37.8], [-122.39, 37.81]]},
    "properties": {"type": "road", "osm_id": "1", "name": "Main St"},
}
BUILDING = {
    "type": "Feature",
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[-122.4, 37.8], [-122.4, 37.81], [-122.39, 37.81], [-122.4, 37.8]]],
    },
    "properties": {"type": "building", "osm_id": "2"},
}
LANDUSE = {
    "type": "Feature",
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[-122.4, 37.8], [-122.4, 37.81], [-122.39, 37.81], [-122.4, 37.8]]],
    },
    "properties": {"type": "landuse", "osm_id": "3"},
}


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------
def test_features_are_grouped_by_type():
    organized = TerraForgeGenerator._organize_vector_data(
        {"features": [ROAD, BUILDING, LANDUSE]}
    )

    assert len(organized["roads"]) == 1
    assert len(organized["buildings"]) == 1
    assert len(organized["landuse"]) == 1


def test_unknown_feature_types_are_dropped():
    organized = TerraForgeGenerator._organize_vector_data(
        {"features": [{"properties": {"type": "mystery"}}]}
    )

    assert all(not bucket for bucket in organized.values())


def test_missing_features_key_is_tolerated():
    organized = TerraForgeGenerator._organize_vector_data({})
    assert all(not bucket for bucket in organized.values())


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------
def test_vectors_are_written_as_geojson(tmp_path):
    organized = TerraForgeGenerator._organize_vector_data(
        {"features": [ROAD, BUILDING, LANDUSE]}
    )

    summary = TerraForgeGenerator._write_vectors("overpass", organized, tmp_path)

    written = tmp_path / "vectors.geojson"
    assert written.exists()
    assert summary.path == str(written)

    payload = json.loads(written.read_text())
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 3


def test_summary_counts_each_category(tmp_path):
    organized = TerraForgeGenerator._organize_vector_data(
        {"features": [ROAD, ROAD, BUILDING, LANDUSE]}
    )

    summary = TerraForgeGenerator._write_vectors("overpass", organized, tmp_path)

    assert summary.source == "overpass"
    assert summary.roads == 2
    assert summary.buildings == 1
    assert summary.landuse == 1
    assert summary.total == 4


def test_no_file_is_written_without_features(tmp_path):
    organized = TerraForgeGenerator._organize_vector_data({"features": []})

    summary = TerraForgeGenerator._write_vectors("overpass", organized, tmp_path)

    assert summary.path is None
    assert summary.total == 0
    assert not (tmp_path / "vectors.geojson").exists()


def test_write_failure_is_not_fatal(tmp_path, monkeypatch):
    """A read-only output directory must not fail the whole generation."""
    organized = TerraForgeGenerator._organize_vector_data({"features": [ROAD]})

    def deny(*args, **kwargs):
        raise OSError("read-only file system")

    monkeypatch.setattr("pathlib.Path.write_text", deny)

    summary = TerraForgeGenerator._write_vectors("overpass", organized, tmp_path)

    assert summary.path is None
    assert summary.roads == 1


def test_written_geojson_is_valid_for_consumers(tmp_path):
    """Output must load in any GeoJSON reader: closed rings, lon/lat order."""
    organized = TerraForgeGenerator._organize_vector_data({"features": [ROAD, BUILDING]})
    TerraForgeGenerator._write_vectors("overpass", organized, tmp_path)

    payload = json.loads((tmp_path / "vectors.geojson").read_text())

    for feature in payload["features"]:
        geometry = feature["geometry"]
        assert geometry["type"] in {"LineString", "Polygon"}
        if geometry["type"] == "Polygon":
            ring = geometry["coordinates"][0]
            assert ring[0] == ring[-1]
            assert len(ring) >= 4
        else:
            assert len(geometry["coordinates"]) >= 2

        for lon, lat in _positions(geometry):
            assert -180 <= lon <= 180
            assert -90 <= lat <= 90


def _positions(geometry):
    if geometry["type"] == "LineString":
        return geometry["coordinates"]
    return geometry["coordinates"][0]


# ---------------------------------------------------------------------------
# Reported through the API
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_generation_reports_vectors_and_writes_the_file(client, sample_bbox, monkeypatch):
    """A full run surfaces the vector summary in the task result."""
    import time

    from realworldmapgen.core.generator_provider import get_generator

    generator = get_generator()

    async def fake_vectors(bbox, request):
        return "overpass", TerraForgeGenerator._organize_vector_data(
            {"features": [ROAD, BUILDING]}
        )

    monkeypatch.setattr(generator, "_get_vector_data", fake_vectors)

    response = client.post(
        "/api/generate",
        json={
            "name": "with_vectors",
            "bbox": sample_bbox,
            "resolution": 128,
            "export_formats": ["unity"],
            "enable_roads": True,
            "enable_buildings": True,
        },
    )
    assert response.status_code == 202

    task_id = response.json()["task_id"]
    deadline = time.monotonic() + 60
    payload = None
    while time.monotonic() < deadline:
        payload = client.get(f"/api/status/{task_id}").json()
        if payload["status"] in {"completed", "failed"}:
            break
        time.sleep(0.1)

    assert payload is not None and payload["status"] == "completed", payload
    vectors = payload["result"]["vectors"]
    assert vectors["source"] == "overpass"
    assert vectors["roads"] == 1
    assert vectors["buildings"] == 1

    from pathlib import Path

    assert Path(vectors["path"]).exists()
