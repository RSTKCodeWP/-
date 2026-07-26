"""Test the export-time single-`person`-class assertion (Task 2.5.4, ultraplan P1-3).

The fine-tuned model outputs (1, 5, 8400); `decode_yolo` reads the person score at row
`4 + PERSON_CLASS_INDEX` with `PERSON_CLASS_INDEX = 0`. If an export ever placed person at
a different index (or stayed multi-class), the decode would silently read the wrong score
row. So at export time we assert the model's class names are exactly `{0: 'person'}` — a
pure check on the names dict, testable without the ML stack.
"""

import pytest

from hades.bench.class_assert import assert_single_person_class


def test_accepts_single_person_at_index_zero():
    assert_single_person_class({0: "person"})  # no raise


def test_accepts_case_insensitive_person():
    assert_single_person_class({0: "Person"})


def test_rejects_person_not_at_index_zero():
    # A single class but keyed at index 1 (not 0) — decode_yolo would read the wrong row.
    with pytest.raises(ValueError, match="index 0"):
        assert_single_person_class({1: "person"})


def test_rejects_multiclass():
    with pytest.raises(ValueError, match="single"):
        assert_single_person_class({0: "person", 1: "car"})


def test_rejects_wrong_class_name():
    with pytest.raises(ValueError, match="person"):
        assert_single_person_class({0: "human"})
