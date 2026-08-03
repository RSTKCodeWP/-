"""Lucas–Kanade optical flow and ground velocity estimation."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

from aerostab.config import CameraConfig, EstimatorConfig


@dataclass
class FlowResult:
    vx_m_s: float
    vy_m_s: float
    quality: float
    n_points: int
    flow_x_px: float
    flow_y_px: float


class OpticalFlowEstimator:
    """
    Down-facing camera optical flow → ground velocity (m/s).
    Axes: x = right, y = forward (camera frame, before FC rotation).
    """

    def __init__(self, cam: CameraConfig, est: EstimatorConfig):
        self.cam = cam
        self.est = est
        self._focal_px = self._focal_length_pixels(cam.width, cam.fov_deg)
        self._prev_gray: Optional[np.ndarray] = None
        self._points: Optional[np.ndarray] = None
        self._last_reset = time.monotonic()
        self._vx_lpf = 0.0
        self._vy_lpf = 0.0
        lk_w = est.win_size
        self._lk_params = dict(
            winSize=(lk_w, lk_w),
            maxLevel=est.max_level,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
        )
        self._feature_params = dict(
            maxCorners=est.max_corners,
            qualityLevel=est.quality_level,
            minDistance=est.min_distance,
            blockSize=est.block_size,
        )

    @staticmethod
    def _focal_length_pixels(width: int, fov_deg: float) -> float:
        return (width / 2.0) / math.tan(math.radians(fov_deg / 2.0))

    def _detect_points(self, gray: np.ndarray) -> np.ndarray:
        pts = cv2.goodFeaturesToTrack(gray, mask=None, **self._feature_params)
        if pts is None:
            return np.empty((0, 1, 2), dtype=np.float32)
        return pts

    def reset(self, gray: np.ndarray) -> None:
        self._prev_gray = gray.copy()
        self._points = self._detect_points(gray)
        self._last_reset = time.monotonic()

    def update(self, gray: np.ndarray, altitude_m: float, dt: float) -> FlowResult:
        if dt <= 0:
            dt = 1e-3
        if self._prev_gray is None:
            self.reset(gray)
            return FlowResult(0, 0, 0, 0, 0, 0)

        if time.monotonic() - self._last_reset > self.est.reset_interval_s:
            self.reset(gray)

        if self._points is None or len(self._points) < self.est.min_track_points:
            self._points = self._detect_points(gray)

        flow_x_px = 0.0
        flow_y_px = 0.0
        n_good = 0

        if self._points is not None and len(self._points) >= self.est.min_track_points:
            next_pts, status, _ = cv2.calcOpticalFlowPyrLK(
                self._prev_gray, gray, self._points, None, **self._lk_params
            )
            if next_pts is not None and status is not None:
                good_old = self._points[status.flatten() == 1]
                good_new = next_pts[status.flatten() == 1]
                if len(good_old) >= self.est.min_track_points:
                    flow = good_new - good_old
                    flow_x_px = float(np.median(flow[:, 0, 0]))
                    flow_y_px = float(np.median(flow[:, 0, 1]))
                    n_good = len(good_old)
                    self._points = good_new.reshape(-1, 1, 2)
                else:
                    self._points = self._detect_points(gray)

        alt = max(altitude_m, self.cam.height / 1000.0)
        # pixels/frame → m/s: (px/focal) * altitude / dt
        vx = (flow_x_px / self._focal_px) * alt / dt
        vy = (flow_y_px / self._focal_px) * alt / dt

        a = self.est.velocity_lpf_alpha
        self._vx_lpf = a * vx + (1 - a) * self._vx_lpf
        self._vy_lpf = a * vy + (1 - a) * self._vy_lpf

        self._prev_gray = gray.copy()

        quality = min(1.0, n_good / max(self.est.max_corners, 1))
        return FlowResult(
            vx_m_s=self._vx_lpf,
            vy_m_s=self._vy_lpf,
            quality=quality,
            n_points=n_good,
            flow_x_px=flow_x_px,
            flow_y_px=flow_y_px,
        )

    def draw_tracks(self, bgr: np.ndarray) -> np.ndarray:
        out = bgr.copy()
        if self._points is not None:
            for p in self._points:
                x, y = int(p[0][0]), int(p[0][1])
                cv2.circle(out, (x, y), 3, (0, 255, 0), -1)
        return out


@dataclass
class OdometryState:
    x_m: float = 0.0
    y_m: float = 0.0
    vx_m_s: float = 0.0
    vy_m_s: float = 0.0
    yaw_rad: float = 0.0
    quality: float = 0.0
    armed: bool = False


class OdometryIntegrator:
    def __init__(self, max_speed: float, position_lpf: float):
        self.max_speed = max_speed
        self.position_lpf = position_lpf
        self.state = OdometryState()
        self._origin_set = False

    def reset_origin(self) -> None:
        self.state.x_m = 0.0
        self.state.y_m = 0.0
        self.state.yaw_rad = 0.0
        self._origin_set = True

    def update(self, flow: FlowResult, dt: float, fc_yaw_rad: Optional[float] = None) -> OdometryState:
        vx = max(-self.max_speed, min(self.max_speed, flow.vx_m_s))
        vy = max(-self.max_speed, min(self.max_speed, flow.vy_m_s))
        self.state.vx_m_s = vx
        self.state.vy_m_s = vy
        self.state.quality = flow.quality

        if fc_yaw_rad is not None:
            self.state.yaw_rad = fc_yaw_rad

        if not self._origin_set:
            self.reset_origin()

        self.state.x_m += vx * dt
        self.state.y_m += vy * dt
        return self.state
