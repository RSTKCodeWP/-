"""GPS-assisted drift correction for optical odometry."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class GpsFix:
    lat: float
    lon: float
    alt_m: float
    fix_type: int
    satellites: int
    time_monotonic: float


@dataclass
class FusionState:
    enabled: bool
    gps_valid: bool
    origin_set: bool
    scale: float
    yaw_offset_rad: float
    home_lat: float
    home_lon: float
    last_correction_m: float


class GpsFusion:
    def __init__(
        self,
        enabled: bool = True,
        wait_timeout_s: float = 60.0,
        accept_radius_km: float = 50.0,
        alignment_distance_m: float = 30.0,
        default_lat: float = 0.0,
        default_lon: float = 0.0,
    ):
        self.enabled = enabled
        self.wait_timeout_s = wait_timeout_s
        self.accept_radius_km = accept_radius_km
        self.alignment_distance_m = alignment_distance_m
        self.default_lat = default_lat
        self.default_lon = default_lon
        self._start = time.monotonic()
        self._home_lat = default_lat
        self._home_lon = default_lon
        self._origin_set = not enabled
        self._scale = 1.0
        self._yaw_offset = 0.0
        self._path_m = 0.0
        self._aligned = False
        self._last_gps: Optional[GpsFix] = None
        self._last_correction = 0.0

    @staticmethod
    def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        r = 6378137.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * r * math.asin(math.sqrt(a))

    def ingest_gps(self, fix: GpsFix) -> None:
        self._last_gps = fix
        if not self.enabled or fix.fix_type < 2:
            return
        if not self._origin_set:
            dist_km = self.haversine_m(fix.lat, fix.lon, self.default_lat, self.default_lon) / 1000.0
            if dist_km <= self.accept_radius_km or time.monotonic() - self._start > self.wait_timeout_s:
                self._home_lat = fix.lat
                self._home_lon = fix.lon
                self._origin_set = True

    def gps_offset_m(self, fix: GpsFix) -> Tuple[float, float]:
        dy = (fix.lat - self._home_lat) / 180.0 * math.pi * 6378137.0
        dx = (
            (fix.lon - self._home_lon)
            / 180.0
            * math.pi
            * 6378137.0
            * math.cos(math.radians(self._home_lat))
        )
        return dx, dy

    def correct(
        self, x_m: float, y_m: float, vx: float, vy: float, dt: float
    ) -> Tuple[float, float, float, float]:
        if not self.enabled or not self._origin_set or self._last_gps is None:
            return x_m, y_m, vx, vy

        self._path_m += math.hypot(vx, vy) * dt
        opt_x, opt_y = x_m * self._scale, y_m * self._scale

        if self._last_gps.fix_type < 3:
            return opt_x, opt_y, vx * self._scale, vy * self._scale

        gx, gy = self.gps_offset_m(self._last_gps)

        if not self._aligned and self._path_m >= self.alignment_distance_m:
            self._yaw_offset = math.atan2(gy, gx) - math.atan2(opt_y, opt_x)
            self._aligned = True

        if self._aligned:
            cos_o, sin_o = math.cos(self._yaw_offset), math.sin(self._yaw_offset)
            rx = opt_x * cos_o - opt_y * sin_o
            ry = opt_x * sin_o + opt_y * cos_o
            err = math.hypot(gx - rx, gy - ry)
            self._last_correction = err
            if err > 2.0:
                alpha = min(0.12, err / 80.0)
                gx_blend = rx * (1 - alpha) + gx * alpha
                gy_blend = ry * (1 - alpha) + gy * alpha
                opt_x = gx_blend
                opt_y = gy_blend
                ratio = math.hypot(gx, gy) / max(math.hypot(rx, ry), 0.5)
                self._scale = max(0.5, min(2.0, self._scale * (1 + 0.05 * (ratio - 1))))

        return opt_x / self._scale, opt_y / self._scale, vx, vy

    def state(self) -> FusionState:
        return FusionState(
            enabled=self.enabled,
            gps_valid=bool(self._last_gps and self._last_gps.fix_type >= 3),
            origin_set=self._origin_set,
            scale=self._scale,
            yaw_offset_rad=self._yaw_offset,
            home_lat=self._home_lat,
            home_lon=self._home_lon,
            last_correction_m=self._last_correction,
        )

    def nav_ready(self) -> bool:
        if not self.enabled:
            return True
        if self._origin_set:
            return True
        return time.monotonic() - self._start > self.wait_timeout_s
