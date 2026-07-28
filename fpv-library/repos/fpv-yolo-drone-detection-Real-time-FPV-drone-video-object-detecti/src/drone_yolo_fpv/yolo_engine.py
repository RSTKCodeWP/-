from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(slots=True)
class DetectionRecord:
    frame_index: int
    class_id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float

    def as_dict(self) -> dict[str, int | float | str]:
        return {
            "frame_index": self.frame_index,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 6),
            "x1": round(self.x1, 2),
            "y1": round(self.y1, 2),
            "x2": round(self.x2, 2),
            "y2": round(self.y2, 2),
        }


class YOLOInferenceEngine:
    """Thin wrapper around Ultralytics YOLO for frame-by-frame OpenCV inference."""

    def __init__(self, model_path: str):
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise ImportError(
                "Ultralytics is not installed. Run `pip install -r requirements.txt`."
            ) from exc

        self.model_path = model_path
        self.model = YOLO(model_path)
        self.names = getattr(self.model, "names", {}) or {}

    def predict_frame(
        self,
        frame: np.ndarray,
        imgsz: int = 640,
        conf: float = 0.35,
        iou: float = 0.45,
        device: str | None = None,
        half: bool = False,
        classes: list[int] | None = None,
    ) -> tuple[Any, float]:
        """Run one YOLO inference pass and return the first Results object plus latency."""
        t0 = time.perf_counter()
        results = self.model.predict(
            source=frame,
            imgsz=imgsz,
            conf=conf,
            iou=iou,
            device=device,
            half=half,
            classes=classes,
            verbose=False,
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return results[0], latency_ms

    def records_from_result(self, result: Any, frame_index: int) -> list[DetectionRecord]:
        """Convert Ultralytics Results boxes to serializable DetectionRecord objects."""
        records: list[DetectionRecord] = []
        boxes = getattr(result, "boxes", None)
        if boxes is None or len(boxes) == 0:
            return records

        for box in boxes:
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
            class_name = str(self.names.get(cls_id, cls_id))
            records.append(
                DetectionRecord(
                    frame_index=frame_index,
                    class_id=cls_id,
                    class_name=class_name,
                    confidence=conf,
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                )
            )
        return records
