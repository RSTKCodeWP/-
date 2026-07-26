"""Test the YOLO-label → original-pixel GroundTruth conversion (Task 2.5.3 eval).

The center-distance matcher needs GT in ORIGINAL-frame pixels; the label file is normalized
cx/cy/w/h. A W/H swap or wrong denominator here would silently shift every GT box and
corrupt the reported recall. Tested on a non-square image so a swap is caught.
"""

import numpy as np
from PIL import Image

from hades.train.eval_arm import load_test_frames


def test_load_test_frames_converts_normalized_to_original_pixels(tmp_path):
    # A 200(H) x 100(W) image (non-square so a W/H swap shows). One box centered, half-size.
    (tmp_path / "images").mkdir()
    (tmp_path / "labels").mkdir()
    Image.fromarray(np.zeros((200, 100, 3), dtype=np.uint8)).save(tmp_path / "images" / "a.png")
    (tmp_path / "labels" / "a.txt").write_text("0 0.5 0.5 0.5 0.5\n")

    frames = load_test_frames(tmp_path)
    assert len(frames) == 1
    gts = frames[0].ground_truths
    assert len(gts) == 1
    # cx=0.5*100=50, w=0.5*100=50 -> x in [25,75]; cy=0.5*200=100, h=0.5*200=100 -> y in [50,150].
    x1, y1, x2, y2 = gts[0].box_xyxy
    assert (x1, x2) == (25.0, 75.0)
    assert (y1, y2) == (50.0, 150.0)


def test_load_test_frames_negative_image_has_no_gt(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "labels").mkdir()
    Image.fromarray(np.zeros((64, 64, 3), dtype=np.uint8)).save(tmp_path / "images" / "b.png")
    (tmp_path / "labels" / "b.txt").write_text("")  # background frame
    frames = load_test_frames(tmp_path)
    assert len(frames) == 1
    assert frames[0].ground_truths == []
