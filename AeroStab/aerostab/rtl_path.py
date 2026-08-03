"""RTL / SmartRTL path recording while armed."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class PathPoint:
    t: float
    x_m: float
    y_m: float
    alt_m: float

    def to_dict(self) -> dict:
        return {
            "t": round(self.t, 3),
            "x": round(self.x_m, 3),
            "y": round(self.y_m, 3),
            "alt": round(self.alt_m, 2),
        }


@dataclass
class RtlPathRecorder:
    enabled: bool = True
    min_dist_m: float = 0.25
    max_points: int = 2000
    save_path: str = "/var/log/aerostab/rtl_path.json"

    _points: List[PathPoint] = field(default_factory=list, init=False)
    _recording: bool = field(default=False, init=False)
    _flight_start: float = field(default=0.0, init=False)
    _last_xy: Optional[Tuple[float, float]] = field(default=None, init=False)

    def on_arm(self, armed: bool) -> None:
        if armed and not self._recording:
            self._points.clear()
            self._last_xy = None
            self._flight_start = time.time()
            self._recording = True
        elif not armed and self._recording:
            self._recording = False
            self._persist()

    def sample(self, x_m: float, y_m: float, alt_m: float, nav_valid: bool) -> None:
        if not self.enabled or not self._recording or not nav_valid:
            return
        if self._last_xy is not None:
            dx = x_m - self._last_xy[0]
            dy = y_m - self._last_xy[1]
            if dx * dx + dy * dy < self.min_dist_m * self.min_dist_m:
                return
        if len(self._points) >= self.max_points:
            self._points.pop(0)
        self._points.append(PathPoint(time.time() - self._flight_start, x_m, y_m, alt_m))
        self._last_xy = (x_m, y_m)

    def path_length_m(self) -> float:
        if len(self._points) < 2:
            return 0.0
        total = 0.0
        for a, b in zip(self._points, self._points[1:]):
            total += ((b.x_m - a.x_m) ** 2 + (b.y_m - a.y_m) ** 2) ** 0.5
        return total

    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def point_count(self) -> int:
        return len(self._points)

    def home_offset_m(self) -> Tuple[float, float]:
        if not self._points:
            return 0.0, 0.0
        last = self._points[-1]
        return last.x_m, last.y_m

    def to_dict(self) -> dict:
        return {
            "recording": self._recording,
            "points": len(self._points),
            "length_m": round(self.path_length_m(), 2),
            "home_x_m": round(self.home_offset_m()[0], 2),
            "home_y_m": round(self.home_offset_m()[1], 2),
            "path": [p.to_dict() for p in self._points],
        }

    def _persist(self) -> None:
        if not self._points:
            return
        path = Path(self.save_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            path = Path("logs") / "rtl_path.json"
            path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f)
