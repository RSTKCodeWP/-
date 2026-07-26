"""Tests for dataset assembly (Task 2.5.1, cycle 2): leakage guard + dataset.yaml.

These functions touch staged files, but the guards they enforce are the load-bearing
ones the ablation depends on (ultraplan): a held-out HERIDAL-test image must never leak
into the merged train set, and the generated `dataset.yaml` must be `nc:1 names:['person']`
or the `PERSON_CLASS_INDEX=0` decode contract breaks. Tested with tiny in-memory arrays +
tmp_path, no real dataset needed.
"""

import numpy as np
import pytest

from hades.train.dataset import (
    assert_no_leakage,
    build_dataset_yaml,
    image_content_hash,
)


def _img(seed: int):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(16, 16, 3), dtype=np.uint8)


# --- assert_no_leakage: exact content-hash overlap (ultraplan P2-h) ----------------


def test_no_leakage_passes_on_disjoint_sets():
    train = {image_content_hash(_img(1)), image_content_hash(_img(2))}
    holdout = {image_content_hash(_img(3))}
    assert_no_leakage(train, holdout)  # no raise


def test_leakage_raises_when_test_image_in_train():
    shared = image_content_hash(_img(42))
    train = {shared, image_content_hash(_img(1))}
    holdout = {shared}
    with pytest.raises(ValueError, match="leak"):
        assert_no_leakage(train, holdout)


# --- build_dataset_yaml: the nc:1 / person contract (ultraplan P1-2) ---------------


def test_build_dataset_yaml_is_single_person_class(tmp_path):
    out = build_dataset_yaml(
        path=tmp_path,
        train="train/images",
        val="val/images",
        test="test/images",
    )
    text = out.read_text()
    assert "nc: 1" in text
    assert "person" in text
    # The absolute root must be pinned (Ultralytics resolves splits relative to it, not CWD).
    assert str(tmp_path) in text
