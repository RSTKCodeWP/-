"""Video-file frame source -- run the real seeker pipeline on a recorded thermal clip.

Feeds frames from any container OpenCV can read (mp4/avi/mov/...) into the bench. ``ThermalCapture``
downstream converts each frame to luminance and resizes it to the pipeline resolution, so a colour-
mapped (white-hot / iron) 8-bit clip works as-is; use the bench ``invert`` control for black-hot.

This is the seam for REAL data: point it at a recorded FLIR/thermal clip of a winged UAV and the
same seeker we test in sim runs on it, unchanged.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


class VideoFileFrameSource:
    """A ``FrameSource`` that replays frames from a video file (optionally looping)."""

    def __init__(self, path: str | Path, *, loop: bool = True) -> None:
        import cv2

        self.path = str(path)
        if not Path(self.path).exists():
            raise FileNotFoundError(f"video not found: {self.path}")
        self._cap = cv2.VideoCapture(self.path)
        if not self._cap.isOpened():
            raise RuntimeError(f"OpenCV could not open video: {self.path}")
        self._loop = loop
        self.frame_count = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = float(self._cap.get(cv2.CAP_PROP_FPS)) or 30.0
        self._i = 0

    def read(self) -> np.ndarray | None:
        import cv2

        ok, frame = self._cap.read()
        if not ok:
            if self._loop:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)   # rewind and keep streaming
                ok, frame = self._cap.read()
            if not ok:
                return None
        self._i += 1
        return frame                                        # BGR uint8; ThermalCapture -> gray + resize

    def close(self) -> None:
        try:
            self._cap.release()
        except Exception:
            pass
