"""Tests for the Phase 1.5 CoreML export helper (offline path logic + guards).

The artifact-naming and input-validation logic is tested without `ultralytics`
installed (heavy import is lazy). The actual export is a `@pytest.mark.ane` smoke
test (manual) since it downloads weights and runs the CoreML converter.
"""

import pytest

from hades.bench.export_coreml import DEFAULT_RESOLUTIONS, artifact_path, export_one


def test_artifact_path_is_named_by_resolution(tmp_path):
    p = artifact_path(tmp_path, 960)
    assert p.name == "yolo11s_coreml_960.mlpackage"
    assert p.parent == tmp_path


def test_artifact_path_distinct_per_resolution(tmp_path):
    names = {artifact_path(tmp_path, r).name for r in DEFAULT_RESOLUTIONS}
    assert len(names) == len(DEFAULT_RESOLUTIONS)  # no collisions


def test_default_resolutions_are_the_spike_set():
    # CLAUDE.md: "a latency spike at {640,960,1280}".
    assert DEFAULT_RESOLUTIONS == (640, 960, 1280)


def test_default_resolutions_are_stride_multiples():
    assert all(r % 32 == 0 for r in DEFAULT_RESOLUTIONS)


def test_export_rejects_non_stride_resolution(tmp_path):
    # 700 is not a multiple of 32; must fail before any heavy import.
    with pytest.raises(ValueError):
        export_one(700, tmp_path)


def test_export_rejects_nonpositive_resolution(tmp_path):
    with pytest.raises(ValueError):
        export_one(0, tmp_path)
