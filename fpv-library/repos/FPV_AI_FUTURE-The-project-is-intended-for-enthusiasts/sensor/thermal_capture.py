"""Thermal camera capture (Block-3 hardware phase) -- FT640 V2 / analog-CVBS class.

The Foxeer FT640 V2 outputs an ANALOG CVBS (8-bit, AGC) thermal video stream, not USB/Y16.
On the Pi5 it is captured through a CVBS->USB grabber, which presents as a standard V4L2/UVC
device. This module turns that stream into the uint16 frames the S1 detector consumes.

Key consequences of an 8-bit AGC analog source (vs a 16-bit radiometric Boson):
  * No absolute-temperature thresholding -- but the S1 detector already uses a RELATIVE
    (percentile + MAD, top-hat) threshold, which is scale-invariant, so an 8-bit AGC frame
    cast to uint16 works directly. The AGC's per-frame contrast stretch is the one caveat.
  * Wide FOV (FT640 V2 ~48.7x38.6 deg) -> good terminal FOV retention, shorter acquisition
    range. ``ft640_intrinsics()`` carries the correct geometry (not the narrow Boson lens).

The real V4L2 path lazily imports cv2 (OpenCV) and is exercised on the Pi; tests use a
SyntheticSource so the module is verifiable without hardware or cv2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

import numpy as np

from fpv.seeker.geometry import CameraIntrinsics, focal_length_from_hfov


def ft640_intrinsics(width: int = 640, height: int = 512, hfov_deg: float = 48.7) -> CameraIntrinsics:
    """Intrinsics for the FT640 V2 wide FPV thermal lens (HFOV ~48.7 deg)."""
    return CameraIntrinsics(
        f_px=focal_length_from_hfov(hfov_deg, width),
        cx=width / 2.0, cy=height / 2.0, width=width, height=height,
    )


class FrameSource(Protocol):
    def read(self) -> np.ndarray | None: ...
    def close(self) -> None: ...


class SyntheticSource:
    """A deterministic frame source for tests (any HxW uint8/uint16 frames)."""

    def __init__(self, frames: Iterable[np.ndarray]) -> None:
        self._frames = list(frames)
        self._i = 0

    def read(self) -> np.ndarray | None:
        if self._i >= len(self._frames):
            return None
        f = self._frames[self._i]
        self._i += 1
        return f

    def close(self) -> None:
        pass


class V4L2Source:
    """Real V4L2/UVC capture (a CVBS->USB grabber, or any USB thermal cam). cv2 lazy-imported."""

    def __init__(self, device: int | str = 0, *, width: int | None = None,
                 height: int | None = None, fourcc: str | None = None) -> None:
        try:
            import cv2  # type: ignore
        except ImportError as exc:  # pragma: no cover - hardware path
            raise RuntimeError("opencv-python is required for live capture (pip install opencv-python)") from exc
        self._cv2 = cv2
        self._cap = cv2.VideoCapture(device)
        if not self._cap.isOpened():  # pragma: no cover - hardware path
            raise RuntimeError(f"could not open capture device {device!r}")
        # ORDER MATTERS on V4L2 grabbers (e.g. MacroSilicon MS2109): set FOURCC first,
        # else cv2 negotiates the default (YUYV, low-res) and silently ignores the size.
        if fourcc:
            self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
        if width:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height:
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def read(self) -> np.ndarray | None:  # pragma: no cover - hardware path
        ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:  # pragma: no cover - hardware path
        self._cap.release()


@dataclass(frozen=True)
class CaptureConfig:
    roi: tuple[int, int, int, int] | None = None   # (x, y, w, h) active thermal area in the grabbed frame
    deinterlace: bool = False                       # CVBS is interlaced; take even field if True
    invert: bool = False                            # set True for a black-hot palette (hot = dark)
    out_width: int = 640
    out_height: int = 512


class ThermalCapture:
    """Adapts a FrameSource into the uint16 frames the S1 detector expects."""

    def __init__(self, source: FrameSource, config: CaptureConfig | None = None) -> None:
        self.source = source
        self.cfg = config or CaptureConfig()

    def frame_u16(self) -> np.ndarray | None:
        raw = self.source.read()
        if raw is None:
            return None
        g = self._to_gray(raw)
        if self.cfg.roi is not None:
            x, y, w, h = self.cfg.roi
            g = g[y:y + h, x:x + w]
        if self.cfg.deinterlace:
            g = g[::2]                                   # keep even field; halves vertical res
        g = self._resize(g, self.cfg.out_width, self.cfg.out_height)
        if self.cfg.invert:
            g = 255.0 - g.astype(np.float64)             # 8-bit AGC palette flip
        return np.clip(g, 0, 65535).astype(np.uint16)

    @staticmethod
    def _to_gray(raw: np.ndarray) -> np.ndarray:
        if raw.ndim == 3:                                # BGR/YUV from the grabber -> luminance
            return raw.astype(np.float64).mean(axis=2)
        return raw.astype(np.float64)

    def _resize(self, g: np.ndarray, w: int, h: int) -> np.ndarray:
        if g.shape == (h, w):
            return g
        try:
            import cv2  # type: ignore
            return cv2.resize(g, (w, h), interpolation=cv2.INTER_AREA)
        except ImportError:                              # cv2-free nearest-neighbour fallback
            ys = (np.linspace(0, g.shape[0] - 1, h)).astype(int)
            xs = (np.linspace(0, g.shape[1] - 1, w)).astype(int)
            return g[np.ix_(ys, xs)]

    def close(self) -> None:
        self.source.close()
