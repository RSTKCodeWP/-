"""Camera backends for Pi Zero 2W + Frank-S01 (OV5647 CSI)."""

from __future__ import annotations

import math
import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple

import cv2
import numpy as np

from aerostab.config import CameraConfig


class CameraSource(ABC):
  @abstractmethod
  def start(self) -> None:
      ...

  @abstractmethod
  def read_gray(self) -> Tuple[bool, Optional[np.ndarray]]:
      ...

  @abstractmethod
  def read_bgr(self) -> Tuple[bool, Optional[np.ndarray]]:
      ...

  @abstractmethod
  def stop(self) -> None:
      ...


class SyntheticCamera(CameraSource):
    """Procedural ground texture for simulation and CI."""

    def __init__(self, cfg: CameraConfig):
        self.cfg = cfg
        self._t = 0.0
        self._rng = np.random.default_rng(42)
        self._base = self._make_texture()

    def _make_texture(self) -> np.ndarray:
        h, w = self.cfg.height, self.cfg.width
        noise = self._rng.integers(0, 255, (h * 2, w * 2), dtype=np.uint8)
        noise = cv2.GaussianBlur(noise, (5, 5), 0)
        grid = np.zeros_like(noise)
        step = 32
        grid[::step, :] = 180
        grid[:, ::step] = 180
        tex = cv2.addWeighted(noise, 0.7, grid, 0.3, 0)
        return tex

    def start(self) -> None:
        self._t = 0.0

    def _frame(self) -> np.ndarray:
        self._t += 1.0 / max(self.cfg.fps, 1)
        dx = int(3 * math.sin(self._t * 0.7))
        dy = int(2 * math.cos(self._t * 0.5))
        h, w = self.cfg.height, self.cfg.width
        y0 = self._base.shape[0] // 2 - h // 2 + dy
        x0 = self._base.shape[1] // 2 - w // 2 + dx
        crop = self._base[y0 : y0 + h, x0 : x0 + w].copy()
        return crop

    def read_gray(self) -> Tuple[bool, Optional[np.ndarray]]:
        return True, self._frame()

    def read_bgr(self) -> Tuple[bool, Optional[np.ndarray]]:
        g = self._frame()
        return True, cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)

    def stop(self) -> None:
        pass


class V4L2Camera(CameraSource):
    def __init__(self, cfg: CameraConfig):
        self.cfg = cfg
        self._cap: Optional[cv2.VideoCapture] = None

    def start(self) -> None:
        self._cap = cv2.VideoCapture(self.cfg.device)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open V4L2 device {self.cfg.device}")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.cfg.fps)

    def read_gray(self) -> Tuple[bool, Optional[np.ndarray]]:
        ok, frame = self.read_bgr()
        if not ok or frame is None:
            return False, None
        return True, cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    def read_bgr(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self._cap is None:
            return False, None
        ok, frame = self._cap.read()
        if not ok:
            return False, None
        if self.cfg.rotation_deg:
            rot = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
            frame = cv2.rotate(frame, rot.get(self.cfg.rotation_deg, cv2.ROTATE_180))
        return True, frame

    def stop(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class Picamera2Source(CameraSource):
    """CSI camera (Frank-S01 / OV5647) via libcamera."""

    def __init__(self, cfg: CameraConfig):
        self.cfg = cfg
        self._picam = None

    def start(self) -> None:
        from picamera2 import Picamera2  # type: ignore

        self._picam = Picamera2()
        config = self._picam.create_video_configuration(
            main={"size": (self.cfg.width, self.cfg.height), "format": "RGB888"},
            controls={"FrameRate": self.cfg.fps},
        )
        self._picam.configure(config)
        self._picam.start()
        time.sleep(0.5)

    def read_bgr(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self._picam is None:
            return False, None
        frame = self._picam.capture_array()
        bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        if self.cfg.rotation_deg:
            rot = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
            bgr = cv2.rotate(bgr, rot.get(self.cfg.rotation_deg, cv2.ROTATE_180))
        return True, bgr

    def read_gray(self) -> Tuple[bool, Optional[np.ndarray]]:
        ok, bgr = self.read_bgr()
        if not ok or bgr is None:
            return False, None
        return True, cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    def stop(self) -> None:
        if self._picam is not None:
            self._picam.stop()
            self._picam.close()
            self._picam = None


def create_camera(cfg: CameraConfig, simulate: bool = False) -> CameraSource:
    if simulate:
        return SyntheticCamera(cfg)
    backend = cfg.backend
    if backend == "auto":
        try:
            cam = Picamera2Source(cfg)
            cam.start()
            return cam
        except Exception:
            pass
        cam = V4L2Camera(cfg)
        cam.start()
        return cam
    if backend == "picamera2":
        cam = Picamera2Source(cfg)
        cam.start()
        return cam
    if backend == "v4l2":
        cam = V4L2Camera(cfg)
        cam.start()
        return cam
    if backend == "synthetic":
        cam = SyntheticCamera(cfg)
        cam.start()
        return cam
    raise ValueError(f"Unknown camera backend: {backend}")
