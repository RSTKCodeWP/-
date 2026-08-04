"""Lucas–Kanade optical flow and ground velocity estimation."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

from aerostab.config import CameraConfig, EstimatorConfig
from aerostab.mask import CameraMask


@dataclass
class FlowResult:
    vx_m_s: float
    vy_m_s: float
    quality: float
    n_points: int
    flow_x_px: float
    flow_y_px: float
    yaw_rate_rad_s: float = 0.0


class OpticalFlowEstimator:
    def __init__(
        self,
        cam: CameraConfig,
        est: EstimatorConfig,
        mask: Optional[CameraMask] = None,
        roi_scale: float = 0.5,
    ):
        self.cam = cam
        self.est = est
        self.mask = mask or CameraMask()
        self.roi_scale = roi_scale
        self._focal_px = self._focal_length_pixels(cam.width, cam.fov_deg)
        self._prev_gray: Optional[np.ndarray] = None
        self._points: Optional[np.ndarray] = None
        self._last_reset = time.monotonic()
        self._vx_lpf = 0.0
        self._vy_lpf = 0.0
        self._yaw_lpf = 0.0
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

    def _cv_mask(self, gray: np.ndarray) -> np.ndarray:
        return self.mask.build_opencv_mask(gray.shape[1], gray.shape[0])

    def _detect_points(self, gray: np.ndarray) -> np.ndarray:
        pts = cv2.goodFeaturesToTrack(gray, mask=self._cv_mask(gray), **self._feature_params)
        if pts is None:
            return np.empty((0, 1, 2), dtype=np.float32)
        return pts

    def reset(self, gray: np.ndarray) -> None:
        self._prev_gray = gray.copy()
        self._points = self._detect_points(gray)
        self._last_reset = time.monotonic()

    @staticmethod
    def _estimate_yaw_rate(old_pts: np.ndarray, new_pts: np.ndarray, dt: float) -> float:
        if len(old_pts) < 4 or dt <= 0:
            return 0.0
        cx = float(np.mean(old_pts[:, 0, 0]))
        cy = float(np.mean(old_pts[:, 0, 1]))
        angles = []
        for i in range(len(old_pts)):
            ox = float(old_pts[i, 0, 0] - cx)
            oy = float(old_pts[i, 0, 1] - cy)
            nx = float(new_pts[i, 0, 0] - cx)
            ny = float(new_pts[i, 0, 1] - cy)
            if math.hypot(ox, oy) < 5:
                continue
            a0 = math.atan2(oy, ox)
            a1 = math.atan2(ny, nx)
            da = math.atan2(math.sin(a1 - a0), math.cos(a1 - a0))
            angles.append(da / dt)
        return float(np.median(angles)) if angles else 0.0

    def set_fov(self, fov_deg: float) -> None:
        self.cam.fov_deg = fov_deg
        self._focal_px = self._focal_length_pixels(self.cam.width, fov_deg)

    def soft_refresh_features(self, gray: np.ndarray) -> None:
        """Add features without wiping existing tracks (avoid hover velocity spike)."""
        if self._points is None or len(self._points) < self.est.min_track_points:
            self._points = self._detect_points(gray)
            return
        extra = self._detect_points(gray)
        if extra is None or len(extra) == 0:
            return
        combined = np.vstack([self._points, extra])
        if len(combined) > self.est.max_corners:
            combined = combined[: self.est.max_corners]
        self._points = combined

    def update(self, gray: np.ndarray, altitude_m: float, dt: float) -> FlowResult:
        if dt <= 0:
            dt = 1e-3
        if self._prev_gray is None:
            self.reset(gray)
            return FlowResult(0, 0, 0, 0, 0, 0, 0)

        if time.monotonic() - self._last_reset > self.est.reset_interval_s:
            self.soft_refresh_features(gray)
            self._last_reset = time.monotonic()

        if self._points is None or len(self._points) < self.est.min_track_points:
            self._points = self._detect_points(gray)

        flow_x_px = 0.0
        flow_y_px = 0.0
        yaw_rate = 0.0
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
                    yaw_rate = self._estimate_yaw_rate(good_old, good_new, dt)
                    self._points = good_new.reshape(-1, 1, 2)
                else:
                    self._points = self._detect_points(gray)

        alt = max(altitude_m, 0.3)
        vx = (flow_x_px / self._focal_px) * alt / dt
        vy = (flow_y_px / self._focal_px) * alt / dt

        a = self.est.velocity_lpf_alpha
        self._vx_lpf = a * vx + (1 - a) * self._vx_lpf
        self._vy_lpf = a * vy + (1 - a) * self._vy_lpf
        self._yaw_lpf = 0.2 * yaw_rate + 0.8 * self._yaw_lpf

        self._prev_gray = gray.copy()
        quality = min(1.0, n_good / max(self.est.max_corners, 1))
        return FlowResult(
            vx_m_s=self._vx_lpf,
            vy_m_s=self._vy_lpf,
            quality=quality,
            n_points=n_good,
            flow_x_px=flow_x_px,
            flow_y_px=flow_y_px,
            yaw_rate_rad_s=self._yaw_lpf,
        )

    def draw_tracks(self, bgr: np.ndarray, show_grid: bool = False) -> np.ndarray:
        out = self.mask.draw_overlay(bgr) if any(self.mask.cells) else bgr.copy()
        if show_grid:
            out = self.mask.draw_grid(out)
        if self._points is not None:
            for p in self._points:
                x, y = int(p[0][0]), int(p[0][1])
                cv2.circle(out, (x, y), 3, (0, 255, 0), -1)
        h, w = out.shape[:2]
        roi_w = int(w * self.roi_scale)
        roi_h = int(h * self.roi_scale)
        x0, y0 = (w - roi_w) // 2, (h - roi_h) // 2
        cv2.rectangle(out, (x0, y0), (x0 + roi_w, y0 + roi_h), (255, 200, 0), 1)
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
    nav_valid: bool = False


class OdometryIntegrator:
    def __init__(self, max_speed: float, use_visual_yaw: bool = True):
        self.max_speed = max_speed
        self.use_visual_yaw = use_visual_yaw
        self.state = OdometryState()
        self._origin_set = False
        self._visual_yaw = 0.0

    def reset_origin(self) -> None:
        self.state.x_m = 0.0
        self.state.y_m = 0.0
        self._visual_yaw = self.state.yaw_rad
        self._origin_set = True

    def update(
        self,
        flow: FlowResult,
        dt: float,
        fc_yaw_rad: Optional[float] = None,
        armed: bool = False,
        hold: bool = False,
    ) -> OdometryState:
        if hold:
            self.state.vx_m_s = 0.0
            self.state.vy_m_s = 0.0
            self.state.quality = flow.quality
            self.state.armed = armed
            return self.state

        vx = max(-self.max_speed, min(self.max_speed, flow.vx_m_s))
        vy = max(-self.max_speed, min(self.max_speed, flow.vy_m_s))
        self.state.vx_m_s = vx
        self.state.vy_m_s = vy
        self.state.quality = flow.quality
        self.state.armed = armed

        if self.use_visual_yaw:
            self._visual_yaw += flow.yaw_rate_rad_s * dt
            self.state.yaw_rad = self._visual_yaw
        elif fc_yaw_rad is not None:
            self.state.yaw_rad = fc_yaw_rad

        if not self._origin_set:
            self.reset_origin()

        self.state.x_m += vx * dt
        self.state.y_m += vy * dt
        return self.state
    def set_position(self, x_m: float, y_m: float, vx: float, vy: float) -> None:
        self.state.x_m = x_m
        self.state.y_m = y_m
        self.state.vx_m_s = vx
        self.state.vy_m_s = vy
