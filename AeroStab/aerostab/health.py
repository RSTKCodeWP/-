"""Preflight health checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from aerostab.config import AppConfig


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


@dataclass
class HealthReport:
    ready: bool
    checks: List[CheckResult] = field(default_factory=list)

    def to_dict(self):
        return {
            "ready": self.ready,
            "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in self.checks],
        }


def evaluate(
    config: AppConfig,
    *,
    camera_ok: bool,
    mavlink_ok: bool,
    quality: float,
    track_points: int,
    fps: float,
    nav_ready: bool,
    mask_fill_ratio: float,
    simulate: bool,
) -> HealthReport:
    checks: List[CheckResult] = []
    min_q = config.quality.min_quality
    min_pts = config.estimator.min_track_points
    min_fps = config.quality.min_fps

    checks.append(CheckResult("camera", camera_ok or simulate, "frame capture"))
    checks.append(
        CheckResult(
            "mavlink",
            mavlink_ok or simulate or not config.mavlink.enabled,
            "FC heartbeat" if config.mavlink.enabled else "disabled",
        )
    )
    checks.append(
        CheckResult(
            "tracking",
            quality >= min_q and track_points >= min_pts,
            f"Q={quality:.2f} pts={track_points} (need Q>={min_q}, pts>={min_pts})",
        )
    )
    checks.append(
        CheckResult("framerate", fps >= min_fps or simulate, f"{fps:.1f} fps (need >={min_fps})")
    )
    checks.append(CheckResult("nav_origin", nav_ready, "GPS/home origin for fusion"))
    checks.append(
        CheckResult(
            "mask",
            mask_fill_ratio < config.mask.max_roi_fill,
            f"ROI masked {mask_fill_ratio:.0%} (max {config.mask.max_roi_fill:.0%})",
        )
    )
    checks.append(
        CheckResult(
            "fov",
            40 <= config.camera.fov_deg <= 170,
            f"FOV {config.camera.fov_deg}°",
        )
    )

    ready = all(c.ok for c in checks)
    return HealthReport(ready=ready, checks=checks)
