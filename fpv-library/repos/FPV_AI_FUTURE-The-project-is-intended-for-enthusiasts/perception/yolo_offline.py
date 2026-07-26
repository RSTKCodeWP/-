"""Offline YOLO inference wrapper for FPV racing-gate detections.

This module only handles file-based/offline sources. It does not open live
cameras, launch training, or claim model acceptance.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fpv_ai.datasets.config import FpvRacingGateConfig, load_fpv_racing_gate_config
from fpv_ai.perception.detector_output import adapt_detector_payload, write_adapted_detector_output

RAW_YOLO_SCHEMA = "ultralytics_yolo_detections.v1"
YOLO_OFFLINE_REPORT_SCHEMA = "fpv_yolo_offline_inference_report.v1"


def run_yolo_offline_predict(
    *,
    weights_path: Path,
    source_path: Path,
    confidence_threshold: float = 0.25,
    max_frames: int | None = None,
) -> dict[str, Any]:
    """Run Ultralytics YOLO on a file/directory/video source and return raw frames."""

    if not source_path.exists():
        raise FileNotFoundError(f"offline source does not exist: {source_path}")
    if _looks_like_live_camera_source(source_path):
        raise ValueError("live camera sources are not allowed in offline YOLO wrapper")
    try:
        from ultralytics import YOLO  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover - depends on optional runtime package
        raise RuntimeError("ultralytics is required for YOLO offline inference") from exc

    model = YOLO(str(weights_path))
    results = model.predict(
        source=str(source_path),
        conf=confidence_threshold,
        stream=True,
        verbose=False,
    )
    return yolo_results_to_detector_payload(
        results,
        confidence_threshold=confidence_threshold,
        max_frames=max_frames,
        source_path=source_path,
    )


def yolo_results_to_detector_payload(
    results: Iterable[Any],
    *,
    confidence_threshold: float = 0.25,
    max_frames: int | None = None,
    source_path: Path | str | None = None,
) -> dict[str, Any]:
    if not 0.0 <= confidence_threshold <= 1.0:
        raise ValueError("confidence_threshold must be in [0, 1]")
    frames: list[dict[str, Any]] = []
    raw_detection_count = 0
    accepted_detection_count = 0
    for frame_index, result in enumerate(results):
        if max_frames is not None and frame_index >= max_frames:
            break
        detections = []
        names = _result_names(result)
        for row in _detections_from_result(result, names=names):
            raw_detection_count += 1
            if float(row["confidence"]) < confidence_threshold:
                continue
            accepted_detection_count += 1
            detections.append(row)
        frames.append(
            {
                "frame_index": frame_index,
                "timestamp_ms": _timestamp_ms(result, frame_index),
                "frame_source": str(getattr(result, "path", "")),
                "detections": detections,
            }
        )
    return {
        "schema": RAW_YOLO_SCHEMA,
        "source_path": "" if source_path is None else str(source_path),
        "confidence_threshold": confidence_threshold,
        "raw_detection_count": raw_detection_count,
        "accepted_detection_count": accepted_detection_count,
        "frames": frames,
    }


def write_yolo_offline_outputs(
    detector_payload: dict[str, Any],
    *,
    out_json: Path,
    report_json: Path,
    adapter_report_json: Path,
    config: FpvRacingGateConfig | None = None,
    weights_path: Path | str = "",
    source_path: Path | str = "",
    synthetic: bool = False,
) -> dict[str, Any]:
    active_config = config or load_fpv_racing_gate_config()
    adapter_report = write_adapted_detector_output(
        detector_payload,
        out_json=out_json,
        report_json=adapter_report_json,
        config=active_config,
        source_path=source_path,
    )
    sequence, _ = adapt_detector_payload(detector_payload, config=active_config, source_path=source_path)
    report = {
        "schema": YOLO_OFFLINE_REPORT_SCHEMA,
        "status": "PASS",
        "generated_at": _utc_now(),
        "weights_path": str(weights_path),
        "source_path": str(source_path),
        "synthetic": synthetic,
        "config_schema": active_config.schema,
        "summary": {
            "frame_count": len(sequence["frames"]),
            "raw_detection_count": int(detector_payload.get("raw_detection_count", 0)),
            "accepted_detection_count": int(detector_payload.get("accepted_detection_count", 0)),
            "canonical_detection_count": adapter_report.payload["summary"]["output_detection_count"],
            "dropped_detection_count": adapter_report.payload["summary"]["dropped_detection_count"],
            "training_launched": False,
            "cameras_opened": False,
            "hardware_test_authorized": False,
        },
        "canonical_output_path": str(out_json),
        "adapter_report_path": str(adapter_report_json),
        "report_path": str(report_json),
        "safety_boundary": {
            "offline_sources_only": True,
            "does_not_launch_training": True,
            "does_not_open_live_cameras": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
        },
    }
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def build_synthetic_yolo_payload() -> dict[str, Any]:
    return {
        "schema": RAW_YOLO_SCHEMA,
        "source_path": "synthetic://fpv_yolo_offline",
        "confidence_threshold": 0.25,
        "raw_detection_count": 5,
        "accepted_detection_count": 5,
        "frames": [
            {
                "frame_index": 0,
                "timestamp_ms": 0,
                "frame_source": "synthetic://frame/0",
                "detections": [
                    {"bbox": [100, 120, 260, 300], "confidence": 0.84, "class_name": "racing_gate"},
                    {"bbox": [10, 10, 40, 40], "confidence": 0.92, "class_name": "unknown_circle"},
                ],
            },
            {
                "frame_index": 1,
                "timestamp_ms": 33,
                "frame_source": "synthetic://frame/1",
                "detections": [{"bbox": [104, 120, 264, 300], "confidence": 0.86, "class_name": "racing_gate"}],
            },
            {
                "frame_index": 2,
                "timestamp_ms": 66,
                "frame_source": "synthetic://frame/2",
                "detections": [{"bbox": [108, 120, 268, 300], "confidence": 0.88, "class_name": "racing_gate"}],
            },
            {"frame_index": 3, "timestamp_ms": 180, "frame_source": "synthetic://frame/3", "detections": []},
            {"frame_index": 4, "timestamp_ms": 640, "frame_source": "synthetic://frame/4", "detections": []},
            {
                "frame_index": 5,
                "timestamp_ms": 760,
                "frame_source": "synthetic://frame/5",
                "detections": [{"bbox": [130, 122, 290, 302], "confidence": 0.82, "class_name": "racing_gate"}],
            },
        ],
    }


def _detections_from_result(result: Any, *, names: dict[int, str]) -> list[dict[str, Any]]:
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return []
    xyxy_rows = _as_list(getattr(boxes, "xyxy", []))
    confidence_rows = _as_list(getattr(boxes, "conf", []))
    class_rows = _as_list(getattr(boxes, "cls", []))
    detections: list[dict[str, Any]] = []
    for index, bbox_raw in enumerate(xyxy_rows):
        class_id = int(float(class_rows[index])) if index < len(class_rows) else 0
        confidence = float(confidence_rows[index]) if index < len(confidence_rows) else 0.0
        detections.append(
            {
                "bbox": [float(value) for value in _as_list(bbox_raw)],
                "confidence": confidence,
                "class_name": names.get(class_id, str(class_id)),
            }
        )
    return detections


def _result_names(result: Any) -> dict[int, str]:
    names = getattr(result, "names", {})
    if isinstance(names, dict):
        return {int(key): str(value) for key, value in names.items()}
    return {}


def _timestamp_ms(result: Any, frame_index: int) -> int:
    timestamp = getattr(result, "timestamp_ms", None)
    return frame_index * 33 if timestamp is None else int(timestamp)


def _as_list(value: Any) -> list[Any]:
    if hasattr(value, "tolist"):
        converted = value.tolist()
        return converted if isinstance(converted, list) else [converted]
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    try:
        return list(value)
    except TypeError:
        return [value]


def _looks_like_live_camera_source(source_path: Path) -> bool:
    text = str(source_path)
    return text.isdigit() or text.startswith("/dev/video")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
