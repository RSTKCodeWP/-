from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2


def ensure_parent(path: str | Path | None) -> None:
    """Create a parent directory for an output path if needed."""
    if path is None:
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def parse_video_source(source: str) -> int | str:
    """Convert webcam index strings like '0' to int, otherwise keep source as str."""
    source = str(source)
    if source.isdigit():
        return int(source)
    return source


def open_capture(source: str) -> cv2.VideoCapture:
    """Open an OpenCV VideoCapture and fail with a readable error."""
    parsed = parse_video_source(source)
    cap = cv2.VideoCapture(parsed)
    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open video source: {source!r}. Check camera index, file path, RTSP URL, or codec support."
        )
    return cap


def get_video_properties(cap: cv2.VideoCapture) -> dict[str, float]:
    """Read common video properties from OpenCV capture."""
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    return {
        "width": float(width or 0),
        "height": float(height or 0),
        "fps": float(fps or 0),
        "frame_count": float(frame_count or 0),
    }


def make_video_writer(
    output_path: str | Path,
    fps: float,
    width: int,
    height: int,
    fourcc: str = "mp4v",
) -> cv2.VideoWriter:
    """Create a cv2.VideoWriter for annotated output video."""
    ensure_parent(output_path)
    safe_fps = fps if fps and fps > 1 else 30.0
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*fourcc),
        safe_fps,
        (int(width), int(height)),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not create video writer: {output_path}")
    return writer


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    """Write pretty JSON to disk."""
    ensure_parent(path)
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
