"""Tests for the shared YOLO output decode + NMS (Task 2.3 / 2.4).

This decode is the SINGLE place raw `(1, 84, 8400)` YOLO output becomes `Detection`s,
imported by BOTH the Core ML and ONNX backends — never re-implemented (mirrors the
plan's single-source-of-truth discipline). Pure numpy, so it runs deterministically
on CI without an ANE.
"""

import numpy as np
import pytest

from hades.detect.detector import Detection
from hades.detect.postprocess import decode_yolo, nms_xyxy
from hades.detect.preprocess import letterbox


def _raw_with_one_person(cx, cy, w, h, person_conf, imgsz=640, n_classes=80, n_anchors=8400):
    """Build a (1, 84, 8400) raw output with exactly one high-person anchor."""
    raw = np.zeros((1, 4 + n_classes, n_anchors), dtype=np.float32)
    raw[0, 0, 0] = cx
    raw[0, 1, 0] = cy
    raw[0, 2, 0] = w
    raw[0, 3, 0] = h
    raw[0, 4, 0] = person_conf  # row 4 == COCO class 0 == person
    return raw


def test_decode_single_person_box():
    # A person centered at (320,320) size 100x200 in a 640 letterbox of a 640x640 frame
    # (scale 1, no pad) -> original box (270,220,370,420).
    lb = letterbox(np.zeros((640, 640, 3), dtype=np.uint8), imgsz=640)
    raw = _raw_with_one_person(320, 320, 100, 200, 0.9)
    dets = decode_yolo(raw, lb, conf_threshold=0.25)
    assert len(dets) == 1
    d = dets[0]
    assert d.cls == "person"
    assert d.conf == pytest.approx(0.9, abs=1e-5)
    assert d.box_xyxy[0] == pytest.approx(270.0)
    assert d.box_xyxy[1] == pytest.approx(220.0)
    assert d.box_xyxy[2] == pytest.approx(370.0)
    assert d.box_xyxy[3] == pytest.approx(420.0)


def test_decode_maps_box_back_through_letterbox():
    # Non-square original frame: 1080x1920 -> scale 1/3, pad_y=140 (per preprocess test).
    lb = letterbox(np.zeros((1080, 1920, 3), dtype=np.uint8), imgsz=640)
    # Person centered at original (960,540) -> letterbox center (320, 320).
    raw = _raw_with_one_person(320, 320, 30, 60, 0.8)
    dets = decode_yolo(raw, lb, conf_threshold=0.25)
    assert len(dets) == 1
    cx = (dets[0].box_xyxy[0] + dets[0].box_xyxy[2]) / 2
    cy = (dets[0].box_xyxy[1] + dets[0].box_xyxy[3]) / 2
    assert cx == pytest.approx(960.0, abs=1.0)
    assert cy == pytest.approx(540.0, abs=1.0)


def test_decode_filters_below_threshold():
    lb = letterbox(np.zeros((640, 640, 3), dtype=np.uint8), imgsz=640)
    raw = _raw_with_one_person(320, 320, 100, 200, 0.10)
    assert decode_yolo(raw, lb, conf_threshold=0.25) == []


def test_decode_ignores_non_person_classes():
    # A strong non-person class (row 5 = COCO class 1 = bicycle) must NOT yield a Detection.
    lb = letterbox(np.zeros((640, 640, 3), dtype=np.uint8), imgsz=640)
    raw = np.zeros((1, 84, 8400), dtype=np.float32)
    raw[0, 0, 0], raw[0, 1, 0], raw[0, 2, 0], raw[0, 3, 0] = 320, 320, 50, 50
    raw[0, 5, 0] = 0.99  # class 1, not person
    assert decode_yolo(raw, lb, conf_threshold=0.25) == []


def test_nms_collapses_overlapping_boxes():
    a = Detection(box_xyxy=(100, 100, 200, 300), conf=0.9)
    b = Detection(box_xyxy=(105, 102, 205, 305), conf=0.7)  # ~same person
    c = Detection(box_xyxy=(400, 100, 480, 300), conf=0.8)  # separate person
    kept = nms_xyxy([a, b, c], iou_threshold=0.5)
    assert len(kept) == 2
    assert a in kept and c in kept and b not in kept  # highest-conf survives the overlap


def test_nms_keeps_all_when_no_overlap():
    a = Detection(box_xyxy=(0, 0, 50, 50), conf=0.9)
    b = Detection(box_xyxy=(100, 100, 150, 150), conf=0.8)
    assert len(nms_xyxy([a, b], iou_threshold=0.5)) == 2


def test_decode_runs_nms_on_duplicate_anchors():
    # Two adjacent anchors firing on the same person collapse to one Detection.
    lb = letterbox(np.zeros((640, 640, 3), dtype=np.uint8), imgsz=640)
    raw = np.zeros((1, 84, 8400), dtype=np.float32)
    for i, conf in enumerate((0.9, 0.85)):
        raw[0, 0, i], raw[0, 1, i], raw[0, 2, i], raw[0, 3, i] = 320 + i, 320, 100, 200
        raw[0, 4, i] = conf
    dets = decode_yolo(raw, lb, conf_threshold=0.25, iou_threshold=0.5)
    assert len(dets) == 1
    assert dets[0].conf == pytest.approx(0.9, abs=1e-5)


def test_decode_rejects_transposed_output():
    # C1 (review): a transposed export `(1, 8400, 84)` passes a naive `shape[0]==1`
    # guard but indexing `pred[4]` then reads anchor #4's vector, not the person row —
    # silently yielding an EMPTY map over a scene full of survivors. The decode must
    # REFUSE the wrong orientation loudly, never index into it.
    lb = letterbox(np.zeros((640, 640, 3), dtype=np.uint8), imgsz=640)
    correct = _raw_with_one_person(320, 320, 100, 200, 0.9)  # (1, 84, 8400)
    transposed = np.transpose(correct, (0, 2, 1))  # (1, 8400, 84)
    assert transposed.shape == (1, 8400, 84)
    with pytest.raises(ValueError):
        decode_yolo(transposed, lb, conf_threshold=0.25)


def test_decode_threshold_is_strict_greater_than():
    # Match Ultralytics: a box exactly AT the threshold is dropped (strict >), so the
    # ONNX/CoreML decode never keeps a box the reference implementation discards.
    lb = letterbox(np.zeros((640, 640, 3), dtype=np.uint8), imgsz=640)
    raw = _raw_with_one_person(320, 320, 100, 200, 0.25)
    assert decode_yolo(raw, lb, conf_threshold=0.25) == []  # conf == threshold -> dropped
    raw2 = _raw_with_one_person(320, 320, 100, 200, 0.2501)
    assert len(decode_yolo(raw2, lb, conf_threshold=0.25)) == 1  # just above -> kept


def test_nms_no_nan_on_minimal_area_boxes():
    # I3 (review): the NMS IoU union can hit 0 -> 0/0=nan, and `nan <= thr` is False,
    # silently dropping a box. `Detection` now forbids zero-area, so we exercise the
    # `np.divide` guard with the smallest legal (1px) boxes and assert no NaN is raised.
    a = Detection(box_xyxy=(10.0, 10.0, 11.0, 11.0), conf=0.9)
    b = Detection(box_xyxy=(100.0, 100.0, 101.0, 101.0), conf=0.8)  # disjoint
    with np.errstate(invalid="raise", divide="raise"):
        kept = nms_xyxy([a, b], iou_threshold=0.5)
    assert len(kept) == 2


def test_decode_never_emits_zero_area_box():
    # A box whose pre-clamp extent lands entirely on the letterbox pad must be DROPPED,
    # not emitted as a clamped zero-area sliver (the §3.2 degenerate-coordinate guard).
    lb = letterbox(np.zeros((480, 640, 3), dtype=np.uint8), imgsz=640)  # pad_y=80
    raw = np.zeros((1, 84, 8400), dtype=np.float32)
    # Center the box up in the top pad region (cy small, tiny height) so it clamps flat.
    raw[0, 0, 0], raw[0, 1, 0], raw[0, 2, 0], raw[0, 3, 0] = 320, 2, 40, 2
    raw[0, 4, 0] = 0.9
    for d in decode_yolo(raw, lb, conf_threshold=0.25):
        x0, y0, x1, y1 = d.box_xyxy
        assert x1 > x0 and y1 > y0  # never a zero-area emission
