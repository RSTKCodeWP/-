"""Tests for the per-source class-map builder in merge_datasets (Task 2.5.1).

This is the cluster-side merge's load-bearing decision: turn each source data.yaml's class
NAMES into a `{index → person|DROP}` map. The collision guard must hold here too — a
VisDrone vehicle must become DROP, never person; a genuinely unexpected class must raise.
(The file-walking parts need real staged data and run on the cluster; this pure builder
does not.)
"""

import pytest

from hades.train.dataset import DROP, ClassMap
from hades.train.merge_datasets import _resolve_image, _source_class_map


def test_sard_single_human_class_maps_to_person():
    cmap = _source_class_map(["human"], is_visdrone=False)
    assert isinstance(cmap, ClassMap)
    assert cmap.resolve(0) == "person"


def test_heridal_person_class_maps_to_person():
    cmap = _source_class_map(["person"], is_visdrone=False)
    assert cmap.resolve(0) == "person"


def test_person_dataset_with_vehicle_class_raises():
    # A "person" dataset is single-class; an unexpected vehicle name is a staging error.
    with pytest.raises(ValueError):
        _source_class_map(["person", "car"], is_visdrone=False)


def test_visdrone_map_persons_and_drops_vehicles():
    names = [
        "pedestrian", "people", "bicycle", "car", "van",
        "truck", "tricycle", "awning-tricycle", "bus", "motor",
    ]
    cmap = _source_class_map(names, is_visdrone=True)
    assert cmap.resolve(0) == "person"  # pedestrian
    assert cmap.resolve(1) == "person"  # people
    assert cmap.resolve(3) == DROP  # car
    assert cmap.resolve(9) == DROP  # motor


def test_visdrone_ignore_region_drops():
    cmap = _source_class_map(["ignored regions", "pedestrian"], is_visdrone=True)
    assert cmap.resolve(0) == DROP
    assert cmap.resolve(1) == "person"


def test_resolve_image_is_case_insensitive(tmp_path):
    # HERIDAL test images are `.JPG` (uppercase) on the case-sensitive cluster FS — a
    # lowercase-only lookup silently skips EVERY test image -> empty held-out split.
    (tmp_path / "shot.JPG").write_bytes(b"x")
    assert _resolve_image(tmp_path, "shot") == tmp_path / "shot.JPG"


def test_resolve_image_finds_lowercase_too(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "b.png").write_bytes(b"x")
    assert _resolve_image(tmp_path, "a") == tmp_path / "a.jpg"
    assert _resolve_image(tmp_path, "b") == tmp_path / "b.png"


def test_resolve_image_missing_returns_none(tmp_path):
    assert _resolve_image(tmp_path, "nope") is None
