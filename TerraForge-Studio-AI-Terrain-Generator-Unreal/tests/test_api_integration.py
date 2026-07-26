"""
TerraForge Studio - API integration tests.

The application is driven in-process via ``TestClient``; no server needs to be
running and no external service is contacted.
"""

from __future__ import annotations

import time

import pytest


# ---------------------------------------------------------------------------
# Discovery endpoints
# ---------------------------------------------------------------------------
def test_api_root(client):
    response = client.get("/api")
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "TerraForge Studio"
    assert "version" in data
    assert "/api/generate" in data["endpoints"].values()


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "data_sources" in data
    assert isinstance(data["data_sources"]["available"], list)


def test_sources(client):
    response = client.get("/api/sources")
    assert response.status_code == 200

    data = response.json()
    assert {"elevation", "imagery", "vector"} <= set(data)
    # SRTM is the key-free source and must never claim to need credentials.
    assert data["elevation"]["srtm"]["requires_api_key"] is False


def test_formats(client):
    response = client.get("/api/formats")
    assert response.status_code == 200

    formats = response.json()["formats"]
    assert {"unreal5", "unity", "gltf", "geotiff"} <= set(formats)
    assert formats["unreal5"]["valid_resolutions"] == [1009, 2017, 4033, 8129]


# ---------------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------------
def test_generate_rejects_missing_bbox(client):
    response = client.post("/api/generate", json={"name": "test", "resolution": 512})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "bbox",
    [
        {"north": 37.79, "south": 37.80, "east": -122.40, "west": -122.41},  # inverted lat
        {"north": 37.80, "south": 37.79, "east": -122.41, "west": -122.40},  # inverted lon
        {"north": 37.80, "south": 37.80, "east": -122.40, "west": -122.41},  # zero height
        {"north": 95.0, "south": 37.79, "east": -122.40, "west": -122.41},  # out of range
    ],
)
def test_generate_rejects_invalid_bbox(client, bbox):
    response = client.post("/api/generate", json={"name": "test", "bbox": bbox})
    assert response.status_code == 422


@pytest.mark.parametrize("name", ["../escape", "with/slash", "", "a" * 65])
def test_generate_rejects_unsafe_names(client, sample_bbox, name):
    response = client.post("/api/generate", json={"name": name, "bbox": sample_bbox})
    assert response.status_code == 422


def test_generate_rejects_oversized_area(client):
    huge_bbox = {"north": 40.0, "south": 37.0, "east": -120.0, "west": -123.0}
    response = client.post("/api/generate", json={"name": "huge", "bbox": huge_bbox})

    assert response.status_code == 400
    assert "too large" in response.json()["detail"].lower()


@pytest.mark.parametrize("resolution", [32, 16384])
def test_generate_rejects_out_of_range_resolution(client, sample_bbox, resolution):
    response = client.post(
        "/api/generate",
        json={"name": "res", "bbox": sample_bbox, "resolution": resolution},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Generation lifecycle
# ---------------------------------------------------------------------------
def _wait_for_task(client, task_id: str, timeout: float = 60.0) -> dict:
    """Poll a task until it reaches a terminal state."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/status/{task_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.1)

    pytest.fail(f"Task {task_id} did not finish within {timeout}s")


def test_generate_accepts_valid_request(client, sample_bbox):
    response = client.post(
        "/api/generate",
        json={
            "name": "valid_request",
            "bbox": sample_bbox,
            "resolution": 128,
            "export_formats": ["unity"],
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert data["task_id"]
    assert data["status"] in {"pending", "processing", "completed"}


def test_generation_completes_and_reports_provenance(client, sample_bbox):
    """A full run must finish and state where its elevation came from."""
    response = client.post(
        "/api/generate",
        json={
            "name": "provenance_run",
            "bbox": sample_bbox,
            "resolution": 128,
            "export_formats": ["unity"],
            "enable_roads": False,
            "enable_buildings": False,
        },
    )
    assert response.status_code == 202

    final = _wait_for_task(client, response.json()["task_id"])
    assert final["status"] == "completed", final.get("error")

    result = final["result"]
    assert result["terrain_name"] == "provenance_run"
    assert result["resolution"] == 128

    # Real sources are disabled in tests, so this run must be flagged synthetic
    # and must carry a warning saying so.
    assert result["elevation"]["synthetic"] is True
    assert any("procedurally generated" in warning for warning in final["warnings"])

    unity_export = next(e for e in result["exports"] if e["format"] == "unity")
    assert unity_export["success"] is True
    assert unity_export["files"]


def test_status_404_for_unknown_task(client):
    response = client.get("/api/status/does-not-exist")
    assert response.status_code == 404


def test_list_tasks(client, sample_bbox):
    """/api/tasks used to raise a TypeError by awaiting a plain list."""
    client.post(
        "/api/generate",
        json={"name": "listed_task", "bbox": sample_bbox, "resolution": 128},
    )

    response = client.get("/api/tasks")
    assert response.status_code == 200

    data = response.json()
    assert data["count"] == len(data["tasks"])
    assert any(task["task_id"] for task in data["tasks"])


# ---------------------------------------------------------------------------
# Maps and downloads
# ---------------------------------------------------------------------------
def test_list_maps(client):
    response = client.get("/api/maps")
    assert response.status_code == 200
    assert isinstance(response.json()["maps"], list)


@pytest.mark.parametrize("map_name", ["..", "../..", "does_not_exist"])
def test_download_rejects_traversal_and_missing_maps(client, map_name):
    response = client.get(f"/api/maps/{map_name}/download/heightmap")
    assert response.status_code in {400, 404}


def test_download_zip_roundtrip(client, sample_bbox, output_dir):
    """Generate a terrain, then download it as a zip archive."""
    response = client.post(
        "/api/generate",
        json={
            "name": "zip_target",
            "bbox": sample_bbox,
            "resolution": 128,
            "export_formats": ["unity"],
            "enable_roads": False,
            "enable_buildings": False,
        },
    )
    final = _wait_for_task(client, response.json()["task_id"])
    assert final["status"] == "completed", final.get("error")

    download = client.get("/api/maps/zip_target/download/zip")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    assert download.content[:2] == b"PK"  # zip magic number


def test_download_rejects_unknown_file_type(client, sample_bbox):
    response = client.post(
        "/api/generate",
        json={"name": "filetype_target", "bbox": sample_bbox, "resolution": 128},
    )
    _wait_for_task(client, response.json()["task_id"])

    bad = client.get("/api/maps/filetype_target/download/not_a_file_type")
    assert bad.status_code == 400
