"""Core ML (ANE) detector test — manual, marked `ane` (excluded on CI; Task 2.3).

Loads the exported `.mlpackage`, runs the detector on a fixture with known people,
and asserts persons are found above threshold with boxes inside the original frame.
Run on an Apple Silicon machine with the `bench` group installed:

    uv run --group bench pytest -m ane tests/detect/test_coreml_detector.py
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from hades.detect.detector import Detection

FIXTURES = Path(__file__).parent.parent / "fixtures"
MODEL_640 = Path(__file__).parent.parent.parent / "models" / "yolo11s_coreml_640.mlpackage"

pytestmark = pytest.mark.ane


def _person_frame() -> np.ndarray:
    return np.asarray(Image.open(FIXTURES / "person.jpg").convert("RGB"), dtype=np.uint8)


@pytest.fixture(scope="module")
def detector():
    if not MODEL_640.exists():
        pytest.skip(f"missing model {MODEL_640} — run hades-export-coreml --res 640")
    from hades.detect.coreml_detector import CoreMLDetector

    return CoreMLDetector(MODEL_640, imgsz=640, conf_threshold=0.25)


def test_detects_person_in_fixture(detector):
    frame = _person_frame()
    dets = detector.detect(frame)
    assert len(dets) >= 1
    assert all(isinstance(d, Detection) for d in dets)
    assert all(d.cls == "person" for d in dets)
    assert max(d.conf for d in dets) > 0.5


def test_boxes_are_inside_original_frame(detector):
    frame = _person_frame()
    h, w = frame.shape[:2]
    for d in detector.detect(frame):
        x_min, y_min, x_max, y_max = d.box_xyxy
        assert 0.0 <= x_min < x_max <= w
        assert 0.0 <= y_min < y_max <= h


def test_returns_detection_list_on_empty_scene(detector):
    # A flat gray frame has no people; detector must return a list (possibly empty),
    # never raise. (Recall-first doctrine: empties are normal, not errors.)
    blank = np.full((480, 640, 3), 128, dtype=np.uint8)
    out = detector.detect(blank)
    assert isinstance(out, list)


def test_implements_detector_interface(detector):
    from hades.detect.detector import Detector

    assert isinstance(detector, Detector)
