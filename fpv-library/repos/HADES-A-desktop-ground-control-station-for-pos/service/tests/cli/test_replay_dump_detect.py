"""Tests for detection overlay in replay-dump (Task 2.7 — the Phase 2 green criterion).

The observable end state: `replay-dump --detect` runs the detector per frame and draws
boxes on the output. Determinism on CI is via the `StubDetector` (a guaranteed box on any
frame); a real run swaps `--backend onnx|coreml`. The fixture clip has no real people, so
the CI test asserts the box-drawing PATH works (stub box appears), not detection accuracy
— accuracy is the eval harness's job (Task 2.5).
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from hades.cli.main import main
from hades.cli.replay_dump import make_detector, run_replay_dump
from hades.detect.detector import StubDetector

FIXTURES = Path(__file__).parent.parent / "fixtures"
CLIP = FIXTURES / "clip_2s.mp4"
SRT = FIXTURES / "clip_2s.srt"


def test_detect_draws_a_box_on_each_frame(tmp_path):
    # Stub returns a box at a known location; the overlay must paint it.
    detector = StubDetector(box_xyxy=(8.0, 6.0, 40.0, 30.0), conf=0.77)
    n = run_replay_dump(CLIP, SRT, tmp_path, detector=detector)
    assert n == 20
    img = np.asarray(Image.open(tmp_path / "frame_00000.png").convert("RGB"))
    # The box outline color (detection green) should appear somewhere on the box edge.
    # Sample a pixel on the top edge of the stub box (y≈6, x in [8,40]).
    top_edge = img[6, 8:40]
    assert (top_edge[:, 1] > 180).any()  # a bright-green outline pixel on the edge


def test_detect_without_box_matches_no_detection_path(tmp_path):
    # An empty detector (no boxes) must still dump frames; just no box drawn.
    class _Empty(StubDetector):
        def detect(self, frame):
            return []

    n = run_replay_dump(CLIP, SRT, tmp_path, detector=_Empty())
    assert n == 20
    assert len(list(tmp_path.glob("*.png"))) == 20


def test_detect_overlay_differs_from_pose_only(tmp_path):
    # The detect overlay must add pixels beyond the pose-only overlay.
    pose_only = tmp_path / "pose"
    detect = tmp_path / "detect"
    run_replay_dump(CLIP, SRT, pose_only)
    run_replay_dump(CLIP, SRT, detect, detector=StubDetector(box_xyxy=(8, 6, 40, 30), conf=0.5))
    a = np.asarray(Image.open(pose_only / "frame_00000.png").convert("RGB"))
    b = np.asarray(Image.open(detect / "frame_00000.png").convert("RGB"))
    assert not np.array_equal(a, b)


def test_make_detector_stub_default():
    det = make_detector("stub")
    assert isinstance(det, StubDetector)


def test_make_detector_rejects_unknown_backend():
    with pytest.raises(ValueError):
        make_detector("not-a-backend")


def test_make_detector_onnx_requires_model_path():
    # onnx/coreml backends need a model path; without it, a clear error (not a crash later).
    with pytest.raises(ValueError):
        make_detector("onnx", model_path=None)


def test_cli_detect_flag_dispatches(tmp_path):
    rc = main(
        ["replay-dump", str(CLIP), "--telemetry", str(SRT), "--out", str(tmp_path), "--detect"]
    )
    assert rc == 0
    assert len(list(tmp_path.glob("*.png"))) == 20
    # With --detect and the default stub backend, a box is drawn.
    img = np.asarray(Image.open(tmp_path / "frame_00000.png").convert("RGB"))
    assert (img[:, :, 1] > 180).any()  # some bright-green outline present
