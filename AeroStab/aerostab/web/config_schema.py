"""Minimal config fields for the flight UI."""

from __future__ import annotations

from typing import Any, Dict, List

CONFIG_SCHEMA: Dict[str, List[Dict[str, Any]]] = {
    "camera": [
        {"key": "fov_deg", "label": "FOV (°)", "type": "number", "step": 0.1, "hint": "Frank-S01: 72.4"},
        {"key": "rotation_deg", "label": "Поворот (°)", "type": "number", "step": 90},
        {"key": "show_grid", "label": "Сітка 1 м", "type": "checkbox"},
    ],
    "mavlink": [
        {"key": "port", "label": "UART / TCP", "type": "text", "hint": "auto або /dev/serial0"},
        {"key": "baud", "label": "Baud", "type": "number"},
    ],
    "altitude": [
        {"key": "source", "label": "Джерело висоти", "type": "select",
         "options": ["auto", "rangefinder", "baro_relative", "static"]},
        {"key": "default_m", "label": "Default (m)", "type": "number", "step": 0.1},
    ],
}

SECTION_LABELS = {
    "camera": "Камера",
    "mavlink": "MAVLink",
    "altitude": "Висота",
}
