"""Configuration loading and persistence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
    show_grid: bool = False


@dataclass
class EstimatorConfig:
    algorithm: str = "lucas_kanade"
    max_corners: int = 60
    quality_level: float = 0.02
    min_distance: int = 10
    block_size: int = 7
    win_size: int = 21
    max_level: int = 2
    reset_interval_s: float = 60.0
    velocity_lpf_alpha: float = 0.3
    min_track_points: int = 8
    use_visual_yaw: bool = False  # FC compass yaw safer for PosHold


@dataclass
class AltitudeConfig:
    source: str = "auto"  # auto | rangefinder | baro_relative | mavlink_baro | static
    static_m: float = 2.0
    min_m: float = 0.3
    max_m: float = 500.0
    default_m: float = 2.0


@dataclass
class OdometryConfig:
    origin_on_arm: bool = True
    max_speed_m_s: float = 15.0
    position_lpf_alpha: float = 0.2
    reset_on_arm: bool = True


@dataclass
class GpsFusionConfig:
    enabled: bool = False
    wait_timeout_s: float = 60.0
    accept_radius_km: float = 50.0
    alignment_distance_m: float = 30.0
    default_lat: float = 0.0
    default_lon: float = 0.0


@dataclass
class QualityConfig:
    min_quality: float = 0.25
    min_fps: float = 8.0
    min_points_to_send: int = 8
    hold_last_on_drop: bool = True
    hold_send_last_pose: bool = True
    nav_valid_warmup_s: float = 2.0


@dataclass
class MaskConfig:
    enabled: bool = True
    cols: int = 16
    rows: int = 12
    path: str = "/etc/aerostab/mask.json"
    max_roi_fill: float = 0.33
    analysis_roi_scale: float = 0.5


@dataclass
class MavlinkConfig:
    enabled: bool = True
    port: str = "auto"
    baud: int = 230400
    system_id: int = 1
    component_id: int = 197
    target_system: int = 1
    target_component: int = 1
    rate_hz: int = 20
    send_optical_flow: bool = False
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
class PmwConfig:
    enabled: bool = False
    backend: str = "auto"
    chip: str = "pmw3901"
    spi_port: int = 0
    spi_cs: int = 1
    spi_cs_gpio: Optional[int] = None
    rotation_deg: int = 0
    blend_weight: float = 0.35


@dataclass
class RtlConfig:
    enabled: bool = True
    min_dist_m: float = 0.25
    max_points: int = 2000
    save_path: str = "/var/log/aerostab/rtl_path.json"


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
    gps_fusion: GpsFusionConfig = field(default_factory=GpsFusionConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    mask: MaskConfig = field(default_factory=MaskConfig)
    mavlink: MavlinkConfig = field(default_factory=MavlinkConfig)
    web: WebConfig = field(default_factory=WebConfig)
    pmw3901: PmwConfig = field(default_factory=PmwConfig)
    rtl: RtlConfig = field(default_factory=RtlConfig)
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
        gps_fusion=_merge_dataclass(GpsFusionConfig, raw.get("gps_fusion", {})),
        quality=_merge_dataclass(QualityConfig, raw.get("quality", {})),
        mask=_merge_dataclass(MaskConfig, raw.get("mask", {})),
        mavlink=_merge_dataclass(MavlinkConfig, raw.get("mavlink", {})),
        web=_merge_dataclass(WebConfig, raw.get("web", {})),
        pmw3901=_merge_dataclass(PmwConfig, raw.get("pmw3901", {})),
        rtl=_merge_dataclass(RtlConfig, raw.get("rtl", {})),
        runtime=_merge_dataclass(RuntimeConfig, raw.get("runtime", {})),
    )


def save_config(config: AppConfig, path: str) -> None:
    data = {
        "camera": asdict(config.camera),
        "estimator": asdict(config.estimator),
        "altitude": asdict(config.altitude),
        "odometry": asdict(config.odometry),
        "gps_fusion": asdict(config.gps_fusion),
        "quality": asdict(config.quality),
        "mask": asdict(config.mask),
        "mavlink": asdict(config.mavlink),
        "web": asdict(config.web),
        "pmw3901": asdict(config.pmw3901),
        "rtl": asdict(config.rtl),
        "runtime": asdict(config.runtime),
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
