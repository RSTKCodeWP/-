"""Shared runtime state."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import numpy as np


@dataclass
class RuntimeStatus:
    running: bool = False
    simulate: bool = False
    fps: float = 0.0
    mavlink_connected: bool = False
    mavlink_messages: int = 0
    armed: bool = False
    nav_ready: bool = False
    nav_valid: bool = False
    health_ready: bool = False
    altitude_m: float = 0.0
    vx_m_s: float = 0.0
    vy_m_s: float = 0.0
    x_m: float = 0.0
    y_m: float = 0.0
    yaw_deg: float = 0.0
    quality: float = 0.0
    track_points: int = 0
    gps_fix: int = 0
    gps_sats: int = 0
    fusion_scale: float = 1.0
    mask_fill: float = 0.0
    errors: list = field(default_factory=list)
    config_path: str = ""
    uptime_s: float = 0.0
    start_time: float = field(default_factory=time.monotonic)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "simulate": self.simulate,
            "fps": round(self.fps, 1),
            "mavlink_connected": self.mavlink_connected,
            "mavlink_messages": self.mavlink_messages,
            "armed": self.armed,
            "nav_ready": self.nav_ready,
            "nav_valid": self.nav_valid,
            "health_ready": self.health_ready,
            "altitude_m": round(self.altitude_m, 2),
            "vx_m_s": round(self.vx_m_s, 3),
            "vy_m_s": round(self.vy_m_s, 3),
            "x_m": round(self.x_m, 2),
            "y_m": round(self.y_m, 2),
            "yaw_deg": round(self.yaw_deg, 1),
            "quality": round(self.quality, 2),
            "track_points": self.track_points,
            "gps_fix": self.gps_fix,
            "gps_sats": self.gps_sats,
            "fusion_scale": round(self.fusion_scale, 3),
            "mask_fill": round(self.mask_fill, 2),
            "errors": self.errors[-5:],
            "uptime_s": round(time.monotonic() - self.start_time, 1),
        }


class SharedState:
    def __init__(self):
        self.lock = threading.Lock()
        self.status = RuntimeStatus()
        self._frame_jpeg: Optional[bytes] = None
        self.health: Dict[str, Any] = {"ready": False, "checks": []}

    def update_status(self, **kwargs) -> None:
        with self.lock:
            for k, v in kwargs.items():
                if hasattr(self.status, k):
                    setattr(self.status, k, v)

    def set_health(self, report) -> None:
        with self.lock:
            self.health = report.to_dict()
            self.status.health_ready = report.ready

    def set_frame(self, bgr: np.ndarray, jpeg: bytes) -> None:
        with self.lock:
            self._frame_jpeg = jpeg

    def get_jpeg(self) -> Optional[bytes]:
        with self.lock:
            return self._frame_jpeg

    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            d = self.status.to_dict()
            d["health"] = self.health
            return d
