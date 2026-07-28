from __future__ import annotations

import cv2
import numpy as np


def draw_hud(
    frame: np.ndarray,
    fps: float,
    frame_index: int,
    detections_count: int,
    model_name: str,
) -> np.ndarray:
    """Draw a small flight-style heads-up display on an annotated frame."""
    overlay = frame.copy()
    h, w = overlay.shape[:2]
    _ = h
    panel_h = 82
    cv2.rectangle(overlay, (0, 0), (w, panel_h), (0, 0, 0), thickness=-1)
    alpha = 0.45
    frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

    lines = [
        f"FPV YOLO Detection | Model: {model_name}",
        f"FPS: {fps:5.1f} | Frame: {frame_index} | Detections: {detections_count}",
    ]
    y = 28
    for line in lines:
        cv2.putText(
            frame,
            line,
            (14, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.68,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        y += 32
    return frame
