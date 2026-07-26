"""Tests for the Detector interface, Detection value object, and StubDetector (Task 2.1)."""

import numpy as np
import pytest

from hades.detect.detector import Detection, Detector, StubDetector


def _frame(w: int = 64, h: int = 48) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def test_detection_holds_box_conf_class():
    det = Detection(box_xyxy=(10.0, 20.0, 30.0, 50.0), conf=0.9, cls="person")
    assert det.box_xyxy == (10.0, 20.0, 30.0, 50.0)
    assert det.conf == 0.9
    assert det.cls == "person"


def test_detection_class_defaults_to_person():
    # v1 is single-class; person is the only class the system emits.
    det = Detection(box_xyxy=(0.0, 0.0, 1.0, 1.0), conf=0.5)
    assert det.cls == "person"


def test_detection_box_is_xyxy_pixel_order():
    # box_xyxy = (x_min, y_min, x_max, y_max) in ORIGINAL-frame pixels (DESIGN.md §3.2).
    det = Detection(box_xyxy=(10.0, 20.0, 30.0, 50.0), conf=0.9)
    x_min, y_min, x_max, y_max = det.box_xyxy
    assert x_max > x_min
    assert y_max > y_min


def test_detection_rejects_inverted_box():
    with pytest.raises(ValueError):
        Detection(box_xyxy=(30.0, 20.0, 10.0, 50.0), conf=0.9)  # x_max < x_min


def test_detection_rejects_zero_area_box():
    # Codex P2: a zero-area box (x_min==x_max) is degenerate — its "center" is a point on
    # a line, useless as a survivor location. Reject it at the boundary, not downstream.
    with pytest.raises(ValueError):
        Detection(box_xyxy=(10.0, 20.0, 10.0, 50.0), conf=0.9)  # zero width
    with pytest.raises(ValueError):
        Detection(box_xyxy=(10.0, 20.0, 30.0, 20.0), conf=0.9)  # zero height


def test_detection_rejects_out_of_range_conf():
    with pytest.raises(ValueError):
        Detection(box_xyxy=(0.0, 0.0, 1.0, 1.0), conf=1.5)


def test_stub_detector_is_a_detector():
    assert issubclass(StubDetector, Detector)


def test_stub_detector_returns_fixed_box():
    det = StubDetector(box_xyxy=(5.0, 6.0, 15.0, 26.0), conf=0.8)
    out = det.detect(_frame())
    assert isinstance(out, list)
    assert len(out) == 1
    assert out[0].box_xyxy == (5.0, 6.0, 15.0, 26.0)
    assert out[0].conf == 0.8
    assert out[0].cls == "person"


def test_stub_detector_is_stateless():
    # Detector is stateless (DESIGN.md §1): same frame in, same result every call.
    det = StubDetector(box_xyxy=(5.0, 6.0, 15.0, 26.0), conf=0.8)
    a = det.detect(_frame())
    b = det.detect(_frame())
    assert a == b


def test_stub_detector_default_box_returns_one_detection():
    out = StubDetector().detect(_frame())
    assert len(out) == 1
    assert out[0].cls == "person"
