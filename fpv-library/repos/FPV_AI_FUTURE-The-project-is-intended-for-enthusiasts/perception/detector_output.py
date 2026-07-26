"""Normalize detector outputs into FPV gate-lock evaluation sequences."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fpv_ai.datasets.config import FpvRacingGateConfig, load_fpv_racing_gate_config

CANONICAL_SEQUENCE_SCHEMA = "fpv_gate_detection_sequence.v1"
ADAPTER_REPORT_SCHEMA = "fpv_detector_adapter_report.v1"
SUPPORTED_INPUT_SCHEMAS = {
    CANONICAL_SEQUENCE_SCHEMA,
    "fpv_detector_output_sequence.v1",
    "model_lab_detection_sequence.v1",
    "ultralytics_yolo_detections.v1",
}
DEFAULT_GATE_CLASSES = {"racing_gate", "partial_gate", "false_ring_hard_negative"}


@dataclass(frozen=True)
class DetectorAdapterReport:
    payload: dict[str, Any]

    @property
    def status(self) -> str:
        return str(self.payload["status"])


def adapt_detector_payload(
    payload: dict[str, Any],
    *,
    config: FpvRacingGateConfig | None = None,
    source_path: Path | str | None = None,
) -> tuple[dict[str, Any], DetectorAdapterReport]:
    if not isinstance(payload, dict):
        raise ValueError("detector payload must be a JSON object")
    input_schema = str(payload.get("schema") or "")
    if input_schema and input_schema not in SUPPORTED_INPUT_SCHEMAS:
        raise ValueError(f"unsupported detector output schema: {input_schema}")

    active_config = config or load_fpv_racing_gate_config()
    class_names = _class_names(active_config)
    frames_raw = payload.get("frames")
    if not isinstance(frames_raw, list):
        raise ValueError("detector payload must contain frames list")

    canonical_frames: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    input_detection_count = 0
    output_detection_count = 0
    dropped_detection_count = 0

    for frame_raw in frames_raw:
        frame = _normalize_frame(frame_raw, class_names=class_names)
        input_detection_count += frame["input_detection_count"]
        output_detection_count += len(frame["detections"])
        dropped_detection_count += frame["dropped_detection_count"]
        for detection in frame["detections"]:
            class_counts[str(detection["class_name"])] += 1
        canonical_frames.append(
            {
                "frame_index": frame["frame_index"],
                "timestamp_ms": frame["timestamp_ms"],
                "detections": frame["detections"],
            }
        )

    sequence = {
        "schema": CANONICAL_SEQUENCE_SCHEMA,
        "source_schema": input_schema or "unknown_detector_output",
        "frames": canonical_frames,
    }
    report_payload = {
        "schema": ADAPTER_REPORT_SCHEMA,
        "status": "PASS",
        "generated_at": _utc_now(),
        "source_path": "" if source_path is None else str(source_path),
        "input_schema": input_schema or "unknown_detector_output",
        "output_schema": CANONICAL_SEQUENCE_SCHEMA,
        "config_schema": active_config.schema,
        "summary": {
            "frame_count": len(canonical_frames),
            "input_detection_count": input_detection_count,
            "output_detection_count": output_detection_count,
            "dropped_detection_count": dropped_detection_count,
            "training_launched": False,
            "hardware_test_authorized": False,
        },
        "class_counts": dict(sorted(class_counts.items())),
        "output_write_performed": False,
        "report_write_performed": False,
        "safety_boundary": {
            "sports_gate_only": True,
            "normalizes_detector_outputs_only": True,
            "does_not_launch_training": True,
            "does_not_open_cameras": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
        },
    }
    return sequence, DetectorAdapterReport(report_payload)


def write_adapted_detector_output(
    payload: dict[str, Any],
    *,
    out_json: Path,
    report_json: Path,
    config: FpvRacingGateConfig | None = None,
    source_path: Path | str | None = None,
) -> DetectorAdapterReport:
    sequence, report = adapt_detector_payload(payload, config=config, source_path=source_path)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(sequence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_payload = dict(report.payload)
    report_payload["output_path"] = str(out_json)
    report_payload["report_path"] = str(report_json)
    report_payload["output_write_performed"] = True
    report_payload["report_write_performed"] = True
    report_json.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return DetectorAdapterReport(report_payload)


def build_synthetic_detector_payload() -> dict[str, Any]:
    return {
        "schema": "fpv_detector_output_sequence.v1",
        "frames": [
            {
                "frame_index": 0,
                "timestamp_ms": 0,
                "detections": [
                    {"xyxy": [100, 120, 260, 300], "score": 0.84, "class_name": "racing_gate"},
                    {"xyxy": [10, 10, 40, 40], "score": 0.92, "class_name": "unknown_circle"},
                ],
            },
            {
                "frame_index": 1,
                "timestamp_ms": 33,
                "detections": [{"bbox": [104, 120, 264, 300], "confidence": 0.86, "class_id": 0}],
            },
            {
                "frame_index": 2,
                "timestamp_ms": 66,
                "detections": [{"bbox": [108, 120, 268, 300], "confidence": 0.88, "class": "racing_gate"}],
            },
            {"frame_index": 3, "timestamp_ms": 180, "detections": []},
            {"frame_index": 4, "timestamp_ms": 640, "detections": []},
            {
                "frame_index": 5,
                "timestamp_ms": 760,
                "detections": [{"bbox": [130, 122, 290, 302], "confidence": 0.82, "name": "racing_gate"}],
            },
        ],
    }


def _normalize_frame(frame_raw: Any, *, class_names: dict[int, str]) -> dict[str, Any]:
    if not isinstance(frame_raw, dict):
        raise ValueError("frame rows must be objects")
    detections_raw = frame_raw.get("detections", frame_raw.get("boxes", []))
    if not isinstance(detections_raw, list):
        raise ValueError("frame detections must be a list")
    frame_index = int(frame_raw["frame_index"])
    timestamp_raw = frame_raw.get("timestamp_ms")
    timestamp_ms = frame_index if timestamp_raw is None else int(timestamp_raw)
    detections: list[dict[str, Any]] = []
    dropped = 0
    for detection_raw in detections_raw:
        detection = _normalize_detection(detection_raw, class_names=class_names)
        if detection is None:
            dropped += 1
        else:
            detections.append(detection)
    return {
        "frame_index": frame_index,
        "timestamp_ms": timestamp_ms,
        "detections": detections,
        "input_detection_count": len(detections_raw),
        "dropped_detection_count": dropped,
    }


def _normalize_detection(raw: Any, *, class_names: dict[int, str]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        raise ValueError("detection rows must be objects")
    bbox = _bbox(raw)
    confidence = _confidence(raw)
    class_name = _class_name(raw, class_names)
    if class_name not in DEFAULT_GATE_CLASSES:
        return None
    return {
        "bbox": [round(value, 3) for value in bbox],
        "confidence": round(confidence, 6),
        "class_name": class_name,
    }


def _bbox(raw: dict[str, Any]) -> tuple[float, float, float, float]:
    value = raw.get("bbox", raw.get("xyxy", raw.get("box")))
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("detection bbox/xyxy/box must contain four numbers")
    x1, y1, x2, y2 = (float(item) for item in value)
    if x2 <= x1 or y2 <= y1:
        raise ValueError("detection bbox must have positive width and height")
    return (x1, y1, x2, y2)


def _confidence(raw: dict[str, Any]) -> float:
    value = raw.get("confidence", raw.get("score", raw.get("conf")))
    if value is None:
        raise ValueError("detection confidence/score/conf is required")
    confidence = float(value)
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("detection confidence must be in [0, 1]")
    return confidence


def _class_name(raw: dict[str, Any], class_names: dict[int, str]) -> str:
    for key in ("class_name", "class", "name", "label"):
        value = raw.get(key)
        if isinstance(value, str) and value:
            return value
    class_id = raw.get("class_id", raw.get("cls"))
    if class_id is None:
        return "racing_gate"
    return class_names.get(int(class_id), str(class_id))


def _class_names(config: FpvRacingGateConfig) -> dict[int, str]:
    names = dict(config.dataset.names)
    names.update(config.dataset.optional_future_names)
    return names


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
