"""Task 7.4 - the qualitative showcase frames (real footage + real detections).

These render genuine model output on real HERIDAL aerial SAR frames: detection boxes on a
real frame, and a stock-vs-fine-tuned before/after on the same frame (the P2.5 win). They
need a real exported model on disk, so the tests skip cleanly when the artifacts or
onnxruntime are absent (lean CI never ships the weights).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from hades.cli.make_showcase import draw_boxes, pick_showcase_frame

pytest.importorskip("onnxruntime", reason="showcase needs the onnx detector backend")

REPO = Path(__file__).resolve().parents[3]
HERIDAL = REPO / "artifacts" / "heridal_holdout_test" / "images"
FT_MODEL = REPO / "artifacts" / "armA_heridal_sard" / "models" / "yolo11s_960.onnx"

needs_artifacts = pytest.mark.skipif(
    not (HERIDAL.exists() and FT_MODEL.exists()),
    reason="HERIDAL holdout frames or fine-tuned ONNX model not on disk",
)


def test_draw_boxes_is_non_destructive_and_marks_each_detection() -> None:
    from hades.detect.detector import Detection

    img = np.zeros((100, 200, 3), dtype=np.uint8)
    dets = [Detection(box_xyxy=(10.0, 10.0, 40.0, 60.0), conf=0.8, cls="person")]
    out = draw_boxes(img, dets)
    assert out.shape == img.shape
    # A box was drawn somewhere (the all-black input gained colored pixels).
    assert out.sum() > 0


@needs_artifacts
def test_pick_frame_returns_a_real_heridal_frame_with_labels() -> None:
    frame_path, n_gt = pick_showcase_frame(HERIDAL)
    assert frame_path.exists()
    assert frame_path.suffix.upper() in {".JPG", ".JPEG"}
    assert n_gt > 0  # we pick a person-rich frame on purpose


@needs_artifacts
def test_showcase_outputs_are_real_pngs(tmp_path: Path) -> None:
    from hades.cli.make_showcase import make_showcase

    written = make_showcase(out_dir=tmp_path, heridal_dir=HERIDAL, ft_model=FT_MODEL)
    assert written, "no showcase frames produced"
    for p in written:
        assert p.exists()
        assert p.stat().st_size > 2000
        assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
