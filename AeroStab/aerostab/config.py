"""Configuration loading."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass
class CameraConfig:
    backend: str = "auto"
    device: int = 0
    width: int = 640
    height: int = 480
    fps: int = 20
    fov_deg: float = 72.4
    rotation_deg: int = 0


@dataclass
class EstimatorConfig:
    algorithm: str = "lucas_kanade"
    max_corners: int = 60
    quality_level: float = 0.02
    min_distance: int = 10
    block_size: int = 7
    win_size: int = 21
    max_level: int = 2
    reset_interval_s: float = 30.0
    velocity_lpf_alpha: float = 0.3
    min_track_points: int = 8


@dataclass
class AltitudeConfig:
    source: str = "mavlink_baro"
    static_m: float = 2.0
    min_m: float = 0.3
    max_m: float = 500.0
    default_m: float = 2.0


@dataclass
class OdometryConfig:
    origin_on_arm: bool = True
    max_speed_m_s: float = 15.0
    position_lpf_alpha: float = 0.2


@dataclass
class MavlinkConfig:
    enabled: bool = True
    port: str = "/dev/serial0"
    baud: int = 230400
    system_id: int = 1
    component_id: int = 197
    target_system: int = 1
    target_component: int = 1
    rate_hz: int = 20
    send_optical_flow: bool = True
    send_vision_position: bool = True
    home_lat: float = 0.0
    home_lon: float = 0.0
    home_alt_m: float = 0.0


@dataclass
class WebConfig:
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8080
    mjpeg_quality: int = 70


@dataclass
class RuntimeConfig:
    control_hz: int = 50
    simulate: bool = False
    log_csv: bool = True
    log_dir: str = "/var/log/aerostab"


@dataclass
class AppConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    estimator: EstimatorConfig = field(default_factory=EstimatorConfig)
    altitude: AltitudeConfig = field(default_factory=AltitudeConfig)
    odometry: OdometryConfig = field(default_factory=OdometryConfig)
    mavlink: MavlinkConfig = field(default_factory=MavlinkConfig)
    web: WebConfig = field(default_factory=WebConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)


def _merge_dataclass(cls, data: Dict[str, Any]):
    if not data:
        return cls()
    valid = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    return cls(**{k: v for k, v in data.items() if k in valid})


def load_config(path: Optional[str] = None) -> AppConfig:
    if path is None:
        path = str(Path(__file__).resolve().parents[1] / "config" / "default.yaml")
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return AppConfig(
        camera=_merge_dataclass(CameraConfig, raw.get("camera", {})),
        estimator=_merge_dataclass(EstimatorConfig, raw.get("estimator", {})),
        altitude=_merge_dataclass(AltitudeConfig, raw.get("altitude", {})),
        odometry=_merge_dataclass(OdometryConfig, raw.get("odometry", {})),
        mavlink=_merge_dataclass(MavlinkConfig, raw.get("mavlink", {})),
        web=_merge_dataclass(WebConfig, raw.get("web", {})),
        runtime=_merge_dataclass(RuntimeConfig, raw.get("runtime", {})),
    )
