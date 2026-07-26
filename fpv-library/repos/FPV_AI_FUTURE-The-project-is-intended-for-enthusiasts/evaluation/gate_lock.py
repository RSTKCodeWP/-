"""Evaluate gate-lock/reacquire behavior on detector output sequences."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fpv_ai.datasets.config import FpvRacingGateConfig, load_fpv_racing_gate_config
from fpv_ai.gates.lock import GateDetection, GateLockConfig, GateLockTracker, TrackingState

REPORT_SCHEMA = "fpv_gate_lock_evaluation.v1"
DETECTION_SEQUENCE_SCHEMA = "fpv_gate_detection_sequence.v1"


@dataclass(frozen=True)
class DetectionCandidate:
    bbox: tuple[float, float, float, float]
    confidence: float
    class_name: str = "racing_gate"

    def to_gate_detection(self, timestamp_ms: int) -> GateDetection:
        return GateDetection(
            bbox=self.bbox,
            confidence=self.confidence,
            frame_timestamp_ms=timestamp_ms,
            class_name=self.class_name,
        )


@dataclass(frozen=True)
class EvaluationFrame:
    frame_index: int
    timestamp_ms: int
    detections: tuple[DetectionCandidate, ...] = ()


def load_detection_sequence(path: Path | str) -> list[EvaluationFrame]:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("detection sequence must be a JSON object")
    if payload.get("schema") != DETECTION_SEQUENCE_SCHEMA:
        raise ValueError(f"unsupported detection sequence schema: {payload.get('schema')}")
    frames = payload.get("frames")
    if not isinstance(frames, list):
        raise ValueError("detection sequence frames must be a list")
    return [_parse_frame(row) for row in frames]


def evaluate_gate_lock_sequence(
    frames: list[EvaluationFrame],
    *,
    config: FpvRacingGateConfig | None = None,
    lock_config: GateLockConfig | None = None,
    source_path: Path | str | None = None,
) -> dict[str, Any]:
    if not frames:
        raise ValueError("at least one evaluation frame is required")
    active_config = config or load_fpv_racing_gate_config()
    tracker = GateLockTracker(lock_config or active_config.target_lock)
    timeline: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    state_counts: Counter[str] = Counter()
    previous_state: str | None = None

    for frame in sorted(frames, key=lambda row: row.frame_index):
        detection = select_best_gate_detection(frame)
        snapshot = tracker.update(detection, frame_timestamp_ms=frame.timestamp_ms).to_payload()
        state = str(snapshot["tracking_state"])
        state_counts[state] += 1
        row = {
            "frame_index": frame.frame_index,
            "timestamp_ms": frame.timestamp_ms,
            "detections_seen": len(frame.detections),
            "selected_detection": detection is not None,
            "tracking_state": state,
            "recovery_state": snapshot["recovery_state"],
            "target_locked": snapshot["target_locked"],
            "confidence": snapshot["confidence"],
            "recommended_action": snapshot["recommended_action"],
            "predicted_center_px": snapshot["predicted_center_px"],
        }
        timeline.append(row)
        if previous_state is None or previous_state != state:
            transitions.append(
                {
                    "frame_index": frame.frame_index,
                    "timestamp_ms": frame.timestamp_ms,
                    "from_state": previous_state or "",
                    "to_state": state,
                }
            )
        previous_state = state

    summary = _summary(frames, timeline, transitions, state_counts)
    status = "PASS" if summary["mvp_gate_lock_ready"] else "FAIL"
    return {
        "schema": REPORT_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "source_path": "" if source_path is None else str(source_path),
        "config_schema": active_config.schema,
        "summary": summary,
        "state_counts": dict(sorted(state_counts.items())),
        "transitions": transitions,
        "timeline": timeline,
        "safety_boundary": {
            "sports_gate_only": True,
            "uses_detector_outputs_only": True,
            "does_not_launch_training": True,
            "does_not_open_cameras": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
            "no_abort_decision_emitted": True,
        },
    }


def build_synthetic_reacquire_sequence() -> list[EvaluationFrame]:
    return [
        EvaluationFrame(0, 0, (DetectionCandidate((100.0, 120.0, 260.0, 300.0), 0.84),)),
        EvaluationFrame(1, 33, (DetectionCandidate((104.0, 120.0, 264.0, 300.0), 0.86),)),
        EvaluationFrame(2, 66, (DetectionCandidate((108.0, 120.0, 268.0, 300.0), 0.88),)),
        EvaluationFrame(3, 180, ()),
        EvaluationFrame(4, 640, ()),
        EvaluationFrame(5, 760, (DetectionCandidate((130.0, 122.0, 290.0, 302.0), 0.82),)),
    ]


def _parse_frame(payload: Any) -> EvaluationFrame:
    if not isinstance(payload, dict):
        raise ValueError("frame rows must be objects")
    detections = payload.get("detections", [])
    if not isinstance(detections, list):
        raise ValueError("frame detections must be a list")
    return EvaluationFrame(
        frame_index=int(payload["frame_index"]),
        timestamp_ms=int(payload["timestamp_ms"]),
        detections=tuple(_parse_detection(row) for row in detections),
    )


def _parse_detection(payload: Any) -> DetectionCandidate:
    if not isinstance(payload, dict):
        raise ValueError("detection rows must be objects")
    bbox_raw = payload.get("bbox")
    if not isinstance(bbox_raw, list) or len(bbox_raw) != 4:
        raise ValueError("detection bbox must be a list of four numbers")
    return DetectionCandidate(
        bbox=tuple(float(value) for value in bbox_raw),  # type: ignore[arg-type]
        confidence=float(payload["confidence"]),
        class_name=str(payload.get("class_name") or "racing_gate"),
    )


def select_best_gate_detection(frame: EvaluationFrame) -> GateDetection | None:
    gate_candidates = [
        candidate
        for candidate in frame.detections
        if candidate.class_name in {"racing_gate", "partial_gate"}
    ]
    if not gate_candidates:
        return None
    best = max(gate_candidates, key=lambda row: row.confidence)
    return best.to_gate_detection(frame.timestamp_ms)


def _summary(
    frames: list[EvaluationFrame],
    timeline: list[dict[str, Any]],
    transitions: list[dict[str, Any]],
    state_counts: Counter[str],
) -> dict[str, Any]:
    first_lock = next(
        (row["frame_index"] for row in timeline if row["tracking_state"] in {"LOCKED", "RECOVERED"}),
        None,
    )
    frames_with_detection = sum(1 for frame in frames if frame.detections)
    hard_lost_frames = state_counts.get(TrackingState.HARD_LOST.value, 0)
    locked_or_recovered = state_counts.get(TrackingState.LOCKED.value, 0) + state_counts.get(
        TrackingState.RECOVERED.value,
        0,
    )
    return {
        "frame_count": len(frames),
        "frames_with_detection": frames_with_detection,
        "transition_count": len(transitions),
        "locked_or_recovered_frames": locked_or_recovered,
        "predictive_track_frames": state_counts.get(TrackingState.PREDICTIVE_TRACK.value, 0),
        "reacquire_frames": state_counts.get(TrackingState.REACQUIRE.value, 0),
        "hard_lost_frames": hard_lost_frames,
        "first_lock_frame_index": first_lock,
        "final_state": timeline[-1]["tracking_state"],
        "mvp_gate_lock_ready": first_lock is not None and hard_lost_frames == 0,
        "training_launched": False,
        "hardware_test_authorized": False,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
