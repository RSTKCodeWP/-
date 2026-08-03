"""Config field metadata for settings UI."""

from __future__ import annotations

from typing import Any, Dict, List

# section_id -> list of field descriptors for the web form
CONFIG_SCHEMA: Dict[str, List[Dict[str, Any]]] = {
    "camera": [
        {"key": "backend", "label": "Backend", "type": "select", "options": ["auto", "picamera2", "v4l2", "synthetic"]},
        {"key": "width", "label": "Ширина", "type": "number", "min": 160, "max": 1920},
        {"key": "height", "label": "Висота", "type": "number", "min": 120, "max": 1080},
        {"key": "fps", "label": "FPS", "type": "number", "min": 5, "max": 60},
        {"key": "fov_deg", "label": "FOV (°)", "type": "number", "step": 0.1, "hint": "Frank-S01: 72.4 / 120 / 160"},
        {"key": "rotation_deg", "label": "Поворот (°)", "type": "number", "step": 90},
        {"key": "show_grid", "label": "Сітка 1 м", "type": "checkbox"},
    ],
    "mavlink": [
        {"key": "enabled", "label": "Увімкнено", "type": "checkbox"},
        {"key": "port", "label": "Порт", "type": "text", "hint": "auto або /dev/serial0 або tcp:..."},
        {"key": "baud", "label": "Baud", "type": "number"},
        {"key": "rate_hz", "label": "Частота (Hz)", "type": "number"},
        {"key": "send_vision_position", "label": "VISION_POSITION", "type": "checkbox"},
        {"key": "send_optical_flow", "label": "OPTICAL_FLOW", "type": "checkbox"},
    ],
    "altitude": [
        {"key": "source", "label": "Джерело", "type": "select",
         "options": ["auto", "rangefinder", "baro_relative", "mavlink_baro", "static"]},
        {"key": "static_m", "label": "Статична висота (m)", "type": "number", "step": 0.1},
        {"key": "default_m", "label": "Default (m)", "type": "number", "step": 0.1},
        {"key": "min_m", "label": "Мін (m)", "type": "number", "step": 0.1},
        {"key": "max_m", "label": "Макс (m)", "type": "number"},
    ],
    "quality": [
        {"key": "min_quality", "label": "Мін. якість", "type": "number", "step": 0.05, "min": 0, "max": 1},
        {"key": "min_fps", "label": "Мін. FPS", "type": "number"},
        {"key": "min_points_to_send", "label": "Мін. точок", "type": "number"},
        {"key": "hold_last_on_drop", "label": "HOLD LAST при втраті", "type": "checkbox"},
        {"key": "hold_send_last_pose", "label": "Тримати pose в EKF", "type": "checkbox"},
        {"key": "nav_valid_warmup_s", "label": "Warmup (s)", "type": "number", "step": 0.5},
    ],
    "estimator": [
        {"key": "max_corners", "label": "Max corners", "type": "number"},
        {"key": "min_track_points", "label": "Мін. track points", "type": "number"},
        {"key": "velocity_lpf_alpha", "label": "LPF alpha", "type": "number", "step": 0.05},
        {"key": "reset_interval_s", "label": "Refresh features (s)", "type": "number"},
        {"key": "use_visual_yaw", "label": "Visual yaw", "type": "checkbox"},
    ],
    "odometry": [
        {"key": "reset_on_arm", "label": "Скидати на ARM", "type": "checkbox"},
        {"key": "max_speed_m_s", "label": "Макс швидкість (m/s)", "type": "number"},
    ],
    "gps_fusion": [
        {"key": "enabled", "label": "GPS fusion", "type": "checkbox"},
        {"key": "wait_timeout_s", "label": "Timeout (s)", "type": "number"},
        {"key": "default_lat", "label": "Default lat", "type": "number", "step": 0.0001},
        {"key": "default_lon", "label": "Default lon", "type": "number", "step": 0.0001},
    ],
    "pmw3901": [
        {"key": "enabled", "label": "PMW3901", "type": "checkbox"},
        {"key": "chip", "label": "Чіп", "type": "select", "options": ["pmw3901", "paa5100"]},
        {"key": "blend_weight", "label": "Blend weight", "type": "number", "step": 0.05, "min": 0, "max": 1},
        {"key": "rotation_deg", "label": "Поворот (°)", "type": "number"},
    ],
    "rtl": [
        {"key": "enabled", "label": "RTL запис", "type": "checkbox"},
        {"key": "min_dist_m", "label": "Мін. крок (m)", "type": "number", "step": 0.05},
        {"key": "max_points", "label": "Макс точок", "type": "number"},
    ],
    "runtime": [
        {"key": "control_hz", "label": "Control Hz", "type": "number"},
        {"key": "log_csv", "label": "CSV лог", "type": "checkbox"},
    ],
}

SECTION_LABELS = {
    "camera": "Камера",
    "mavlink": "MAVLink / FC",
    "altitude": "Висота",
    "quality": "Якість / failsafe",
    "estimator": "Optical flow",
    "odometry": "Одометрія",
    "gps_fusion": "GPS fusion",
    "pmw3901": "PMW3901 (SPI)",
    "rtl": "RTL траєкторія",
    "runtime": "Runtime",
}
