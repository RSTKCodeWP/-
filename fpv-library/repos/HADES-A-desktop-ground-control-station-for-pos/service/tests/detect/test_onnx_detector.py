"""ONNX/CPU detector backend — the deterministic, CI-runnable seam test (Task 2.4).

Why a SYNTHETIC model here: the real `.onnx` is a ~36 MB gitignored artifact (like the
`.mlpackage`) and producing it needs torch — neither is present on lean CI. So the CI
test builds a tiny hand-authored ONNX graph (a few KB, `onnx.helper`, no weights, no
torch) that emits a CANNED `(1, 84, 8400)` tensor. That can't test detection *accuracy*
— `test_postprocess.py` already covers the decode math offline — but it uniquely proves
the **ORT → decode seam** that nothing else reaches:
  - the float32 NCHW `[0,1]` input is fed under the right input name,
  - ORT's output (name/shape/dtype) flows into `decode_yolo` with no transpose,
  - the box is un-letterboxed back to original pixels.

Real-weights accuracy (tolerance band on `person.jpg`) lives in the `onnx_real`-marked
test below — run manually like the ANE test, after `hades-export-onnx`.
"""

from pathlib import Path

import numpy as np
import onnx
import pytest
from onnx import TensorProto, helper

from hades.detect.detector import Detection, Detector
from hades.detect.onnx_detector import OnnxDetector

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _build_synthetic_yolo_onnx(path: Path, person_cells: list[tuple]) -> None:
    """Write a tiny ONNX model: input `images` (1,3,640,640) -> output `output0`
    (1,84,8400). Output is a Constant independent of the input (so it's deterministic),
    with the named person anchors filled in. The graph still consumes `images` (via a
    no-op Mul by 0 added back) so the input feeding is genuinely exercised.
    """
    raw = np.zeros((1, 84, 8400), dtype=np.float32)
    for col, (cx, cy, w, h, conf) in enumerate(person_cells):
        raw[0, 0, col], raw[0, 1, col], raw[0, 2, col], raw[0, 3, col] = cx, cy, w, h
        raw[0, 4, col] = conf  # row 4 == person

    inp = helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, 640, 640])
    out = helper.make_tensor_value_info("output0", TensorProto.FLOAT, [1, 84, 8400])
    const = helper.make_node(
        "Constant",
        inputs=[],
        outputs=["output0"],
        value=helper.make_tensor(
            "canned", TensorProto.FLOAT, raw.shape, raw.flatten().tolist()
        ),
    )
    # A trivial use of `images` so ORT must actually receive the named input (the seam
    # we're testing) — reduce it to a scalar and discard, keeping `output0` the result.
    used = helper.make_node("ReduceSum", inputs=["images"], outputs=["_unused"], keepdims=0)
    graph = helper.make_graph([const, used], "synthetic_yolo", [inp], [out, helper.make_tensor_value_info("_unused", TensorProto.FLOAT, [])])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    onnx.checker.check_model(model)
    onnx.save(model, str(path))


@pytest.fixture
def synthetic_model(tmp_path):
    # One person at letterbox center (320,320), size 100x200 -> in a 640->640 square
    # frame (scale 1, no pad) original box (270,220,370,420).
    p = tmp_path / "synthetic_yolo.onnx"
    _build_synthetic_yolo_onnx(p, person_cells=[(320, 320, 100, 200, 0.9)])
    return p


def test_onnx_detector_is_a_detector(synthetic_model):
    det = OnnxDetector(synthetic_model, imgsz=640)
    assert isinstance(det, Detector)


def test_onnx_detector_decodes_canned_person(synthetic_model):
    det = OnnxDetector(synthetic_model, imgsz=640, conf_threshold=0.25)
    frame = np.zeros((640, 640, 3), dtype=np.uint8)
    out = det.detect(frame)
    assert len(out) == 1
    d = out[0]
    assert isinstance(d, Detection)
    assert d.cls == "person"
    assert d.conf == pytest.approx(0.9, abs=1e-4)
    assert d.box_xyxy[0] == pytest.approx(270.0, abs=1.0)
    assert d.box_xyxy[2] == pytest.approx(370.0, abs=1.0)


def test_onnx_detector_unletterboxes_on_nonsquare_frame(synthetic_model):
    # Feed a non-square frame; the box must come back in ORIGINAL pixels (the seam that
    # would silently break if the un-letterbox step were skipped on this backend).
    det = OnnxDetector(synthetic_model, imgsz=640, conf_threshold=0.25)
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    out = det.detect(frame)
    assert len(out) == 1
    # letterbox center (320,320) of a 1080x1920 frame (scale 1/3, pad_y=140) maps to
    # original (960, 540).
    cx = (out[0].box_xyxy[0] + out[0].box_xyxy[2]) / 2
    cy = (out[0].box_xyxy[1] + out[0].box_xyxy[3]) / 2
    assert cx == pytest.approx(960.0, abs=2.0)
    assert cy == pytest.approx(540.0, abs=2.0)


def test_onnx_detector_empty_scene_returns_list(tmp_path):
    p = tmp_path / "empty.onnx"
    _build_synthetic_yolo_onnx(p, person_cells=[])  # no person anchors
    det = OnnxDetector(p, imgsz=640, conf_threshold=0.25)
    out = det.detect(np.zeros((640, 640, 3), dtype=np.uint8))
    assert out == []


# ----------------------------------------------------------------------------------
# Gated tier — real exported weights. Run manually (not on CI):
#   uv run --group bench hades-export-onnx --res 640
#   uv run pytest -m onnx_real tests/detect/test_onnx_detector.py
# ----------------------------------------------------------------------------------

MODEL_640_ONNX = Path(__file__).parent.parent.parent / "models" / "yolo11s_640.onnx"


@pytest.mark.onnx_real
def test_real_onnx_detects_person_within_tolerance():
    if not MODEL_640_ONNX.exists():
        pytest.skip(f"missing {MODEL_640_ONNX} — run hades-export-onnx --res 640")
    from PIL import Image

    det = OnnxDetector(MODEL_640_ONNX, imgsz=640, conf_threshold=0.25)
    frame = np.asarray(Image.open(FIXTURES / "person.jpg").convert("RGB"), dtype=np.uint8)
    dets = det.detect(frame)
    assert len(dets) >= 1
    assert all(d.cls == "person" for d in dets)
    assert max(d.conf for d in dets) > 0.5
    h, w = frame.shape[:2]
    for d in dets:
        x_min, y_min, x_max, y_max = d.box_xyxy
        assert 0.0 <= x_min < x_max <= w
        assert 0.0 <= y_min < y_max <= h
