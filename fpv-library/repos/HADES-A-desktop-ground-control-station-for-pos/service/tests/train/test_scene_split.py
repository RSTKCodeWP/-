"""Tests for scene-aware HERIDAL re-splitting (Task: fix scene-level test leakage).

The HERIDAL Roboflow export splits by FRAME randomly, so the same flight location (scene
code, e.g. BRK/GRO/ZRI) appears in BOTH train and test — the model sees the same terrain in
training, inflating the anchor HERIDAL-test recall (verified: all 14 test scenes also in
train). The honest fix is to re-split by SCENE so no location spans the boundary. These test
the scene parser + the scene-leakage assertion.
"""

import pytest

from hades.train.scene_split import (
    assert_no_scene_leakage,
    heridal_scene,
    split_scenes,
)


def test_heridal_scene_parses_location_code():
    # {split}_{SCENE}_{NNNN}_JPG.rf.<hash>.JPG
    assert heridal_scene("test_BRK_0004_JPG.rf.xaFIsA3QYHc2lumkxQFI.JPG") == "BRK"
    assert heridal_scene("train_GRO_0007_JPG.rf.abc123.jpg") == "GRO"
    assert heridal_scene("valid_ZRI_0004_JPG.rf.def.JPG") == "ZRI"


def test_heridal_scene_handles_multidigit_and_letters():
    assert heridal_scene("train_SB_1002_JPG.rf.x.JPG") == "SB"
    assert heridal_scene("test_VRD_0150_JPG.rf.y.JPG") == "VRD"


def test_heridal_scene_rejects_unknown_split_token():
    # Guard against a malformed/renamed file silently yielding a wrong scene code — the
    # split token must be one of train/test/valid, and the frame field must be numeric.
    with pytest.raises(ValueError):
        heridal_scene("garbage_BRK_0001_JPG.rf.x.JPG")  # unknown split token


def test_heridal_scene_rejects_nonnumeric_frame():
    with pytest.raises(ValueError):
        heridal_scene("test_BRK_notaframe_JPG.rf.x.JPG")  # frame field not numeric


def test_assert_no_scene_leakage_passes_when_disjoint():
    assert_no_scene_leakage({"BRK", "GRO"}, {"ZRI", "VRD"})  # no raise


def test_assert_no_scene_leakage_raises_on_overlap():
    with pytest.raises(ValueError, match="scene"):
        assert_no_scene_leakage({"BRK", "GRO", "ZRI"}, {"ZRI"})


def test_split_scenes_is_deterministic_and_disjoint():
    scenes = {"BLI", "BRA", "BRK", "BRS", "CAP", "GOR", "GRO", "JAS", "MED", "RAK"}
    train1, test1 = split_scenes(scenes, test_fraction=0.3, seed=0)
    train2, test2 = split_scenes(scenes, test_fraction=0.3, seed=0)
    assert (train1, test1) == (train2, test2)  # deterministic
    assert not (train1 & test1)  # disjoint
    assert train1 | test1 == scenes  # complete
    assert len(test1) >= 1  # non-empty test


def test_split_scenes_holds_out_roughly_the_fraction():
    scenes = {f"S{i:02d}" for i in range(20)}
    train, test = split_scenes(scenes, test_fraction=0.25, seed=0)
    assert 3 <= len(test) <= 7  # ~25% of 20, allow rounding slack
