"""Apply config updates from web UI to live runtime."""

from __future__ import annotations

from dataclasses import fields
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from aerostab.config import AppConfig
    from aerostab.runtime import AeroStabRuntime


def config_to_dict(config: "AppConfig") -> Dict[str, Any]:
    from dataclasses import asdict

    return {
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


def _merge_section(section_obj, data: Dict[str, Any]) -> None:
    valid = {f.name for f in fields(section_obj)}
    for k, v in data.items():
        if k in valid:
            setattr(section_obj, k, v)


def apply_config_patch(config: "AppConfig", patch: Dict[str, Any]) -> list[str]:
    """Merge patch into config. Returns list of sections changed."""
    changed = []
    for section, data in patch.items():
        if not isinstance(data, dict) or not hasattr(config, section):
            continue
        _merge_section(getattr(config, section), data)
        changed.append(section)
    return changed


def apply_runtime_hot_reload(runtime: "AeroStabRuntime", changed: list[str]) -> None:
    """Apply hot-reloadable changes without full restart."""
    with runtime._config_lock:
        if "camera" in changed and runtime._flow:
            runtime._flow.cam = runtime.config.camera
            runtime._flow.set_fov(runtime.config.camera.fov_deg)
        if "mask" in changed:
            runtime.reload_mask()
        if "quality" in changed:
            q = runtime.config.quality
            runtime.shared.update_status(
                min_quality=q.min_quality,
                min_points=q.min_points_to_send,
                min_fps=q.min_fps,
            )
