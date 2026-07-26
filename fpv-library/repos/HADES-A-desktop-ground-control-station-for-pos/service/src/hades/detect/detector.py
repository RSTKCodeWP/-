"""Detector interface and the `Detection` value object.

A `Detector` is a **stateless** `frame -> list[Detection]` (DESIGN.md §1): it
knows nothing about time, tracks, or survivors — just boxes in one image. The
Core ML weights behind it are swappable; the interface is not. Tracking,
confirmation, and localization are downstream and stateful.

`Detection` is the cross-module box contract. Per DESIGN.md §3.2:

- `box_xyxy = (x_min, y_min, x_max, y_max)` is in **pixels of the original
  (pre-letterbox) frame**. Any letterbox/scale applied for inference is undone
  *inside* the detector before a pixel leaves it — a coordinate that escapes in
  letterboxed space is the named §3.2 footgun.
- Image axes are origin top-left, **+x right / +y down** (OpenCV convention).
- `cls` is `"person"` — v1 is single-class (CLAUDE.md detection line); the field
  exists so the contract is explicit, not so the system is multi-class.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Detection:
    """One detected box in original-frame pixels (DESIGN.md §3.2).

    Attributes:
        box_xyxy: (x_min, y_min, x_max, y_max) pixels, pre-letterbox frame.
        conf: detection confidence in [0, 1].
        cls: object class; always "person" in v1 (single-class).
    """

    box_xyxy: tuple[float, float, float, float]
    conf: float
    cls: str = "person"

    def __post_init__(self) -> None:
        x_min, y_min, x_max, y_max = self.box_xyxy
        # Reject an inverted OR zero-area box at the boundary rather than letting a
        # mirrored axis (the §3.2 bug class) or a degenerate sliver — whose "center" is a
        # useless point on a line — flow silently downstream into a survivor coordinate.
        if x_max <= x_min or y_max <= y_min:
            raise ValueError(
                f"box_xyxy must be ordered with positive area "
                f"(x_min<x_max, y_min<y_max): {self.box_xyxy}"
            )
        if not (0.0 <= self.conf <= 1.0):
            raise ValueError(f"conf must be in [0, 1]: {self.conf}")


class Detector(ABC):
    """Stateless `frame -> list[Detection]`. Core ML / ONNX impls swap behind this."""

    @abstractmethod
    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Detect persons in one HxWx3 uint8 RGB frame; boxes in original pixels."""
        raise NotImplementedError


class StubDetector(Detector):
    """Returns a single fixed box regardless of input.

    A test/scaffold detector so the pipeline and the observable CLI can run
    before the Core ML / ONNX backends exist. Stateless by construction.
    """

    def __init__(
        self,
        box_xyxy: tuple[float, float, float, float] = (10.0, 10.0, 50.0, 90.0),
        conf: float = 0.5,
    ):
        # Validate eagerly so a bad stub box fails at construction, not mid-run.
        self._detection = Detection(box_xyxy=box_xyxy, conf=conf, cls="person")

    def detect(self, frame: np.ndarray) -> list[Detection]:
        return [self._detection]
