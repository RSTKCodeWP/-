"""
Tests for request models and settings loading.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from realworldmapgen.config import Settings
from realworldmapgen.models import (
    BoundingBox,
    ExportFormat,
    GenerationStatus,
    MapGenerationRequest,
    TaskStatus,
)


# ---------------------------------------------------------------------------
# BoundingBox
# ---------------------------------------------------------------------------
def test_bbox_area_matches_known_extent():
    """One degree square at the equator is roughly 12,300 km²."""
    bbox = BoundingBox(north=0.5, south=-0.5, east=0.5, west=-0.5)
    assert bbox.area_km2() == pytest.approx(12_310, rel=0.01)


def test_bbox_area_shrinks_towards_the_poles():
    equator = BoundingBox(north=0.1, south=0.0, east=0.1, west=0.0)
    arctic = BoundingBox(north=70.1, south=70.0, east=0.1, west=0.0)

    assert arctic.area_km2() < equator.area_km2() / 2


def test_bbox_center():
    bbox = BoundingBox(north=10.0, south=0.0, east=20.0, west=0.0)
    assert bbox.center() == (5.0, 10.0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"north": 0.0, "south": 1.0, "east": 1.0, "west": 0.0},  # north below south
        {"north": 1.0, "south": 1.0, "east": 1.0, "west": 0.0},  # zero height
        {"north": 1.0, "south": 0.0, "east": 0.0, "west": 1.0},  # east below west
        {"north": 91.0, "south": 0.0, "east": 1.0, "west": 0.0},  # latitude overflow
        {"north": 1.0, "south": 0.0, "east": 181.0, "west": 0.0},  # longitude overflow
    ],
)
def test_bbox_rejects_degenerate_geometry(kwargs):
    with pytest.raises(ValidationError):
        BoundingBox(**kwargs)


# ---------------------------------------------------------------------------
# MapGenerationRequest
# ---------------------------------------------------------------------------
def _request(**overrides) -> dict:
    payload = {
        "name": "terrain",
        "bbox": {"north": 1.0, "south": 0.0, "east": 1.0, "west": 0.0},
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("name", ["../etc", "a/b", "a\\b", "", " ", "a" * 65])
def test_request_rejects_unsafe_names(name):
    with pytest.raises(ValidationError):
        MapGenerationRequest(**_request(name=name))


@pytest.mark.parametrize("name", ["terrain", "my_map-2", "Map 01", "a.b"])
def test_request_accepts_reasonable_names(name):
    assert MapGenerationRequest(**_request(name=name)).name == name


def test_request_deduplicates_export_formats():
    request = MapGenerationRequest(
        **_request(export_formats=["unity", "unity", "gltf", "unity"])
    )
    assert request.export_formats == [ExportFormat.UNITY, ExportFormat.GLTF]


def test_request_requires_at_least_one_format():
    with pytest.raises(ValidationError):
        MapGenerationRequest(**_request(export_formats=[]))


@pytest.mark.parametrize("resolution", [0, 32, 9000])
def test_request_rejects_out_of_range_resolution(resolution):
    with pytest.raises(ValidationError):
        MapGenerationRequest(**_request(resolution=resolution))


def test_request_defaults():
    request = MapGenerationRequest(**_request())
    assert request.resolution == 2048
    assert request.export_formats == [ExportFormat.UNREAL5]


# ---------------------------------------------------------------------------
# GenerationStatus
# ---------------------------------------------------------------------------
def test_status_accepts_download_url():
    """download_url used to be assigned to a field that did not exist."""
    status = GenerationStatus(task_id="abc")
    status.download_url = "/api/maps/x/download/zip"
    assert status.download_url.endswith("/zip")


def test_status_warnings_are_deduplicated():
    status = GenerationStatus(task_id="abc")
    status.add_warning("same")
    status.add_warning("same")
    status.add_warning("other")

    assert status.warnings == ["same", "other"]


def test_status_defaults_to_pending():
    assert GenerationStatus(task_id="abc").status == TaskStatus.PENDING


def test_status_serializes_to_plain_json():
    payload = GenerationStatus(task_id="abc").model_dump(mode="json")
    assert payload["status"] == "pending"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def test_settings_ignores_unknown_env_keys(tmp_path, monkeypatch):
    """An .env with extra keys must not prevent startup."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MAX_AREA_KM2=42.5\n"
        "SOME_FUTURE_OPTION=whatever\n"
        "ANOTHER_UNKNOWN=1\n"
    )

    settings = Settings(_env_file=str(env_file))
    assert settings.max_area_km2 == 42.5


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('["a", "b"]', ["a", "b"]),
        ("a,b", ["a", "b"]),
        ("a, b , c", ["a", "b", "c"]),
        ("", []),
    ],
)
def test_settings_parses_list_fields_in_both_notations(tmp_path, raw, expected):
    env_file = tmp_path / ".env"
    env_file.write_text(f"CORS_ORIGINS={raw}\n")

    assert Settings(_env_file=str(env_file)).cors_origins == expected


def test_settings_strips_inline_comments(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("LOG_LEVEL=debug  # verbose\n")

    assert Settings(_env_file=str(env_file)).log_level == "DEBUG"


def test_settings_treats_blank_secrets_as_unset(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENTOPOGRAPHY_API_KEY=\nAZURE_MAPS_SUBSCRIPTION_KEY=   \n")

    settings = Settings(_env_file=str(env_file))
    assert settings.opentopography_api_key is None
    assert settings.azure_maps_key is None


def test_settings_rejects_nonpositive_area(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("MAX_AREA_KM2=0\n")

    with pytest.raises(ValidationError):
        Settings(_env_file=str(env_file))


def test_example_env_file_loads(tmp_path):
    """The shipped .env.example must be a valid configuration."""
    import shutil
    from pathlib import Path

    example = Path(__file__).resolve().parents[1] / ".env.example"
    target = tmp_path / ".env"
    shutil.copy(example, target)

    settings = Settings(_env_file=str(target))
    assert settings.app_name
    assert settings.max_area_km2 > 0


def test_resolved_cors_origins_includes_frontend_url():
    settings = Settings(cors_origins=["http://a"], frontend_url="http://b")
    assert settings.resolved_cors_origins() == ["http://a", "http://b"]
