from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class InferenceConfig:
    model: str = "yolo11n.pt"
    source: str = "0"
    imgsz: int = 640
    conf: float = 0.35
    iou: float = 0.45
    device: str | None = None
    half: bool = False
    classes: list[int] | None = None
    show: bool = False
    output: str | None = None
    save_csv: str | None = None
    save_json: str | None = None
    max_frames: int | None = None


def load_yaml_config(path: str | Path) -> dict[str, Any]:
    """Load a YAML configuration file."""
    with Path(path).open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}, got {type(data).__name__}")
    return data
