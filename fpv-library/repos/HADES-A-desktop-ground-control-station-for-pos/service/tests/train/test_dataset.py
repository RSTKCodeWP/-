"""Tests for dataset normalization (Task 2.5.1).

The three source datasets (SARD, HERIDAL, VisDrone) are all Roboflow YOLO exports, so
one parser suffices — the real work is the per-source class merge to a single `person`
class and the guards the phase-end adversarial review flagged (ultraplan): class-index
collisions (a VisDrone `car` silently becoming `person`), content-hash test leakage
(Roboflow rehashes filenames so name-based dedup is useless), and tiny-survivor boxes
rounding to zero area. Pure logic + tiny fixtures → runs on CI without the ML stack.
"""

import pytest

from hades.train.dataset import (
    DROP,
    ClassMap,
    LabelLine,
    image_content_hash,
    normalize_label_file,
    parse_yolo_label,
    yolo_line,
)

# --- parse_yolo_label: the one Roboflow-YOLO parser -------------------------------


def test_parse_yolo_label_reads_normalized_boxes():
    # Real SARD shape: "cls cx cy w h" normalized, one line per box.
    text = "0 0.69296875 0.46796875 0.0640625 0.18046875\n"
    lines = parse_yolo_label(text)
    assert len(lines) == 1
    assert lines[0].cls_index == 0
    assert lines[0].cx == pytest.approx(0.69296875)
    assert lines[0].w == pytest.approx(0.0640625)


def test_parse_yolo_label_handles_multibox_and_blank_lines():
    text = "0 0.5 0.08 0.05 0.11\n0 0.98 0.33 0.02 0.2\n\n"
    lines = parse_yolo_label(text)
    assert len(lines) == 2  # blank line ignored


def test_parse_yolo_label_empty_is_negative_image():
    # An empty .txt is a valid background/negative frame, not an error.
    assert parse_yolo_label("") == []


def test_parse_yolo_label_rejects_malformed_line():
    with pytest.raises(ValueError):
        parse_yolo_label("0 0.5 0.5\n")  # too few fields


# --- class merge: the collision guard (ultraplan P2-j) ----------------------------


def test_sard_human_maps_to_person():
    cmap = ClassMap({0: "person"})  # SARD nc:1 names:['human'] -> person
    out = normalize_label_file([LabelLine(0, 0.5, 0.5, 0.1, 0.1)], cmap)
    assert [ln.cls_index for ln in out] == [0]


def test_visdrone_pedestrian_and_people_both_map_to_person():
    # VisDrone: 0=pedestrian, 1=people -> BOTH person; vehicles dropped.
    cmap = ClassMap({0: "person", 1: "person", 2: DROP, 3: DROP})
    lines = [
        LabelLine(0, 0.1, 0.1, 0.05, 0.05),  # pedestrian
        LabelLine(1, 0.2, 0.2, 0.05, 0.05),  # people
        LabelLine(2, 0.3, 0.3, 0.2, 0.2),  # car -> DROP
    ]
    out = normalize_label_file(lines, cmap)
    assert len(out) == 2  # car dropped
    assert all(ln.cls_index == 0 for ln in out)  # all emitted as person==0


def test_unmapped_class_raises_no_silent_passthrough():
    # A source class not in the map must RAISE — never silently become person==0
    # (a VisDrone vehicle leaking into 'person' poisons the model).
    cmap = ClassMap({0: "person"})
    with pytest.raises(ValueError, match="unmapped"):
        normalize_label_file([LabelLine(7, 0.5, 0.5, 0.1, 0.1)], cmap)


# --- yolo_line: tiny-box / positive-area guard (ultraplan P0-5 of dataset) ---------


def test_yolo_line_emits_person_index_zero():
    assert yolo_line(LabelLine(0, 0.5, 0.25, 0.1, 0.2)).startswith("0 ")


def test_yolo_line_rejects_zero_area_box():
    # A survivor box that rounded to zero width must not be silently emitted.
    with pytest.raises(ValueError, match="area"):
        yolo_line(LabelLine(0, 0.5, 0.5, 0.0, 0.1))


def test_yolo_line_rejects_out_of_range():
    with pytest.raises(ValueError):
        yolo_line(LabelLine(0, 1.5, 0.5, 0.1, 0.1))  # cx > 1


# --- content-hash leakage guard (ultraplan P2-h): hash PIXELS, not filenames -------


def test_image_content_hash_is_pixel_based_not_filename():
    import numpy as np

    a = np.zeros((8, 8, 3), dtype=np.uint8)
    b = np.zeros((8, 8, 3), dtype=np.uint8)
    b[0, 0, 0] = 255
    # Identical pixels -> identical hash regardless of any filename; one pixel differs -> differs.
    assert image_content_hash(a) == image_content_hash(a.copy())
    assert image_content_hash(a) != image_content_hash(b)
