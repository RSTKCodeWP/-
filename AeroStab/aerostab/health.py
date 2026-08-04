"""Preflight health checks — gate before PosHold arm."""

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
    heartbeat_age_s: float = 0.0,
    altitude_m: float = 2.0,
    holding: bool = False,
    nav_valid: bool = False,
    altitude_source: str = "",
) -> HealthReport:
    checks: List[CheckResult] = []
    min_q = config.quality.min_quality
    min_pts = config.estimator.min_track_points
    min_fps = config.quality.min_fps

    checks.append(CheckResult("camera", camera_ok or simulate, "frame capture"))
    mav_detail = "FC heartbeat"
    if config.mavlink.enabled and not simulate:
        mav_ok = mavlink_ok and heartbeat_age_s < 3.0
        mav_detail = f"heartbeat age {heartbeat_age_s:.1f}s"
    else:
        mav_ok = True
        mav_detail = "disabled/sim"
    checks.append(CheckResult("mavlink", mav_ok, mav_detail))
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
    checks.append(CheckResult("nav_origin", nav_ready, "origin ready"))
    checks.append(
        CheckResult(
            "mask",
            mask_fill_ratio < config.mask.max_roi_fill,
            f"ROI masked {mask_fill_ratio:.0%} (max {config.mask.max_roi_fill:.0%})",
        )
    )
    checks.append(
        CheckResult("fov", 40 <= config.camera.fov_deg <= 170, f"FOV {config.camera.fov_deg}°")
    )
    alt_ok = config.altitude.min_m <= altitude_m <= config.altitude.max_m
    checks.append(
        CheckResult(
            "altitude",
            alt_ok,
            f"{altitude_m:.2f} m via {altitude_source or config.altitude.source}",
        )
    )
    # Sustained nav for PosHold — holding mid-flight is OK but not "ready to arm"
    checks.append(
        CheckResult(
            "poshold",
            (nav_valid and not holding) or simulate,
            "NAV OK (warmup done)" if nav_valid else ("HOLD LAST" if holding else "waiting for stable track"),
        )
    )

    ready = all(c.ok for c in checks)
    return HealthReport(ready=ready, checks=checks)
