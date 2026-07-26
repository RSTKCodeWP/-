"""Letterbox preprocessing matched to the YOLO Core ML / ONNX export.

The export is a **square `imgsz`** YOLO model (bench/export_coreml.py). Its Core ML
input is an `imageType` RGB buffer at `imgsz×imgsz` with the `/255` scale baked into
the model; the ONNX path needs an explicit NCHW float32 `[0,1]` tensor. Both consume
the SAME letterboxed pixels — this module produces them, plus the scale/pad metadata
that lets a detected box be mapped **back to original-frame pixels** before it leaves
the detector (DESIGN.md §3.2: a coordinate must never escape in letterboxed space).

Letterbox geometry follows the Ultralytics default: preserve aspect with a single
isotropic `scale = imgsz / max(H, W)`, center the resized image on an `imgsz²` canvas
filled with `114` gray, scaleup allowed. `scale` and `(pad_x, pad_y)` fully describe
the forward map, so `unletterbox_xy` is its exact inverse.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

#: Ultralytics letterbox pad color (neutral gray) — must match the training/export pad.
PAD_VALUE = 114


@dataclass(frozen=True)
class Letterbox:
    """A letterboxed frame plus the forward-transform parameters.

    The forward map of an original-frame pixel `(x, y)` onto the canvas is
    `(x*scale + pad_x, y*scale + pad_y)`; `unletterbox_xy` inverts it.

    Attributes:
        image: HxWx3 uint8 RGB canvas of size `(imgsz, imgsz)`, pad = 114.
        scale: isotropic resize factor applied to the original frame.
        pad_x: left padding in canvas pixels.
        pad_y: top padding in canvas pixels.
        imgsz: canvas side length.
        orig_w: original frame width (pixels).
        orig_h: original frame height (pixels).
    """

    image: np.ndarray
    scale: float
    pad_x: float
    pad_y: float
    imgsz: int
    orig_w: int
    orig_h: int

    def unletterbox_xy(self, x: float, y: float) -> tuple[float, float]:
        """Map a canvas-space point back to original-frame pixels, clamped to bounds.

        Clamping matters because a box edge can sit on the pad (outside the real
        image); a survivor coordinate must land inside `[0, W]×[0, H]`, never
        negative or past the frame (DESIGN.md §3.2).
        """
        ox = (x - self.pad_x) / self.scale
        oy = (y - self.pad_y) / self.scale
        ox = min(max(ox, 0.0), float(self.orig_w))
        oy = min(max(oy, 0.0), float(self.orig_h))
        return ox, oy


def letterbox(frame: np.ndarray, imgsz: int = 640) -> Letterbox:
    """Letterbox an HxWx3 uint8 RGB frame into a square `imgsz` canvas.

    Returns the canvas plus the scale/pad metadata. Uses bilinear resize to match
    the Ultralytics default.
    """
    if frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError(f"frame must be HxWx3, got shape {frame.shape}")
    if imgsz <= 0:
        raise ValueError(f"imgsz must be positive, got {imgsz}")

    orig_h, orig_w = int(frame.shape[0]), int(frame.shape[1])
    scale = imgsz / max(orig_h, orig_w)
    new_w = round(orig_w * scale)
    new_h = round(orig_h * scale)

    resized = np.asarray(
        Image.fromarray(frame).resize((new_w, new_h), Image.BILINEAR),
        dtype=np.uint8,
    )

    canvas = np.full((imgsz, imgsz, 3), PAD_VALUE, dtype=np.uint8)
    pad_x = (imgsz - new_w) / 2.0
    pad_y = (imgsz - new_h) / 2.0
    # The resized image is painted at an INTEGER top-left offset, and that SAME integer
    # offset (`left`/`top`) is what we store as pad_x/pad_y below — so `unletterbox_xy`
    # inverts the actual paint location exactly. (Do NOT "restore" pad_x/pad_y to the
    # fractional `(imgsz-new)/2`: that would shift every box up to 0.5px off the painted
    # image — the §3.2 coordinate error this module exists to prevent. Review I4.)
    top, left = int(round(pad_y)), int(round(pad_x))
    canvas[top : top + new_h, left : left + new_w] = resized

    return Letterbox(
        image=canvas,
        scale=scale,
        pad_x=float(left),
        pad_y=float(top),
        imgsz=imgsz,
        orig_w=orig_w,
        orig_h=orig_h,
    )


def to_nchw_float(image: np.ndarray) -> np.ndarray:
    """Convert an HxWx3 uint8 RGB canvas to a normalized NCHW float32 `[0,1]` tensor.

    This is the explicit tensor the ONNX backend needs; the Core ML image input has
    this normalization baked in and takes the uint8 image directly.
    """
    chw = np.transpose(image.astype(np.float32) / 255.0, (2, 0, 1))
    return np.ascontiguousarray(chw[np.newaxis, ...], dtype=np.float32)
