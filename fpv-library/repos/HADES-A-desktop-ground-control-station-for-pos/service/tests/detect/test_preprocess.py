"""Tests for detector preprocessing — letterbox matched to the CoreML/ONNX export (Task 2.2).

The export is a square `imgsz` YOLO model (see bench/export_coreml.py). Its input is
an `imageType` 640x640 RGB buffer with the /255 normalization baked in (verified from
the .mlpackage spec). So preprocessing must:
  - letterbox the original frame into a square `imgsz` canvas (aspect preserved,
    padded with 114 — the Ultralytics default),
  - record the scale + (pad_x, pad_y) so boxes can be mapped BACK to original pixels
    (DESIGN.md §3.2: a coordinate must never leave the detector in letterboxed space),
  - expose a float32 NCHW [0,1] tensor for the ONNX backend (CoreML eats the uint8 image).

These assert the geometry exactly because a wrong pad/scale is the named §3.2 footgun.
"""

import numpy as np
import pytest

from hades.detect.preprocess import Letterbox, letterbox, to_nchw_float


def _frame(h: int, w: int) -> np.ndarray:
    # Distinct per-pixel values so a transpose/flip bug shows up.
    return (np.arange(h * w * 3, dtype=np.uint8).reshape(h, w, 3))


def test_letterbox_output_is_square_imgsz():
    out = letterbox(_frame(48, 64), imgsz=640)
    assert out.image.shape == (640, 640, 3)
    assert out.image.dtype == np.uint8


def test_letterbox_preserves_aspect_with_pad_color_114():
    # 480x640 (HxW) landscape -> scale 1.0 limited by width (640), height 480 -> 480 in 640.
    out = letterbox(_frame(480, 640), imgsz=640)
    assert out.scale == pytest.approx(1.0)
    # Width fills, height is padded top+bottom: (640-480)/2 = 80 each side.
    assert out.pad_x == pytest.approx(0.0)
    assert out.pad_y == pytest.approx(80.0)
    # Padded rows are the fill color 114 in every channel.
    assert (out.image[0] == 114).all()
    assert (out.image[-1] == 114).all()


def test_letterbox_scale_for_larger_image_scales_down():
    # 1080x1920 -> longest side 1920 -> scale 640/1920 = 0.3333...
    out = letterbox(_frame(1080, 1920), imgsz=640)
    assert out.scale == pytest.approx(640.0 / 1920.0)
    # scaled h = 1080*scale = 360, pad_y = (640-360)/2 = 140
    assert out.pad_y == pytest.approx((640 - 360) / 2)
    assert out.pad_x == pytest.approx(0.0)


def test_letterbox_square_image_no_padding():
    out = letterbox(_frame(640, 640), imgsz=640)
    assert out.scale == pytest.approx(1.0)
    assert out.pad_x == pytest.approx(0.0)
    assert out.pad_y == pytest.approx(0.0)


def test_inverse_maps_letterboxed_box_back_to_original_pixels():
    # The round-trip that guards §3.2: a box in letterboxed space -> original pixels.
    out = letterbox(_frame(1080, 1920), imgsz=640)
    # A point at original (x=960, y=540) -> letterboxed (960*scale, 540*scale + pad_y).
    lx = 960 * out.scale + out.pad_x
    ly = 540 * out.scale + out.pad_y
    ox, oy = out.unletterbox_xy(lx, ly)
    assert ox == pytest.approx(960.0)
    assert oy == pytest.approx(540.0)


def test_unletterbox_clamps_to_frame_bounds():
    # A box edge sitting on the pad must clamp to [0, W]/[0, H], not go negative.
    out = letterbox(_frame(480, 640), imgsz=640)  # pad_y=80
    ox, oy = out.unletterbox_xy(0.0, 0.0)  # top-left of canvas, inside pad
    assert ox == pytest.approx(0.0)
    assert oy == pytest.approx(0.0)  # clamped up from a negative pre-clamp value


def test_to_nchw_float_is_normalized_chw_batch():
    out = letterbox(_frame(48, 64), imgsz=640)
    t = to_nchw_float(out.image)
    assert t.shape == (1, 3, 640, 640)
    assert t.dtype == np.float32
    assert 0.0 <= t.min() and t.max() <= 1.0


def test_letterbox_returns_metadata_object():
    out = letterbox(_frame(48, 64), imgsz=640)
    assert isinstance(out, Letterbox)
    assert out.orig_h == 48 and out.orig_w == 64
