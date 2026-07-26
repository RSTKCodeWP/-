"""End-to-end offline FPV gate-lock pipeline.

The pipeline converts a canonical gate detection sequence into gate-lock states
and bounded AI commands. It is offline-only: no training, cameras, hardware, or
command publication.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fpv_ai.control.pilot import GateVisualPilot
from fpv_ai.control.speed import SpeedMode
from fpv_ai.datasets.config import FpvRacingGateConfig, load_fpv_racing_gate_config
from fpv_ai.evaluation.gate_lock import EvaluationFrame, select_best_gate_detection
from fpv_ai.gates.lock import GateLockTracker, TrackingState

COMMAND_SEQUENCE_SCHEMA = "fpv_ai_command_sequence.v1"
OFFLINE_PIPELINE_REPORT_SCHEMA = "fpv_offline_pipeline_report.v1"


def run_offline_gate_pipeline(
    frames: list[EvaluationFrame],
    *,
    config: FpvRacingGateConfig | None = None,
    speed_mode: SpeedMode = SpeedMode.RACE_SPEED,
    requested_speed_mps: float | None = None,
    operator_limit_mps: float | None = None,
    source_path: Path | str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not frames:
        raise ValueError("at least one evaluation frame is required")
    active_config = config or load_fpv_racing_gate_config()
    speed_policy = active_config.speed_policy
    if operator_limit_mps is not None:
        speed_policy = speed_policy.with_operator_limit(speed_mode, operator_limit_mps)

    tracker = GateLockTracker(active_config.target_lock)
    pilot = GateVisualPilot(speed_policy=speed_policy)
    command_rows: list[dict[str, Any]] = []
    state_counts: Counter[str] = Counter()
    max_resolved_speed = 0.0

    for sequence_id, frame in enumerate(sorted(frames, key=lambda row: row.frame_index)):
        detection = select_best_gate_detection(frame)
        lock_payload = tracker.update(detection, frame_timestamp_ms=frame.timestamp_ms).to_payload()
        command_payload = pilot.command_from_lock(
            lock_payload,
            speed_mode=speed_mode,
            requested_speed_mps=requested_speed_mps,
            sequence_id=sequence_id,
        ).to_payload()
        state = str(lock_payload["tracking_state"])
        state_counts[state] += 1
        max_resolved_speed = max(max_resolved_speed, float(command_payload["resolved_speed_mps"]))
        command_rows.append(
            {
                "frame_index": frame.frame_index,
                "timestamp_ms": frame.timestamp_ms,
                "detections_seen": len(frame.detections),
                "selected_detection": detection is not None,
                "lock": lock_payload,
                "command": command_payload,
            }
        )

    sequence = {
        "schema": COMMAND_SEQUENCE_SCHEMA,
        "source_path": "" if source_path is None else str(source_path),
        "speed_mode": speed_mode.value,
        "requested_speed_mps": requested_speed_mps,
        "operator_limit_mps": operator_limit_mps,
        "commands": command_rows,
    }
    report = {
        "schema": OFFLINE_PIPELINE_REPORT_SCHEMA,
        "status": "PASS",
        "generated_at": _utc_now(),
        "source_path": "" if source_path is None else str(source_path),
        "config_schema": active_config.schema,
        "summary": {
            "frame_count": len(frames),
            "command_count": len(command_rows),
            "selected_detection_frames": sum(1 for row in command_rows if row["selected_detection"]),
            "locked_or_recovered_frames": state_counts.get(TrackingState.LOCKED.value, 0)
            + state_counts.get(TrackingState.RECOVERED.value, 0),
            "predictive_track_frames": state_counts.get(TrackingState.PREDICTIVE_TRACK.value, 0),
            "reacquire_frames": state_counts.get(TrackingState.REACQUIRE.value, 0),
            "hard_lost_frames": state_counts.get(TrackingState.HARD_LOST.value, 0),
            "max_resolved_speed_mps": round(max_resolved_speed, 3),
            "speed_mode": speed_mode.value,
            "operator_limit_mps": operator_limit_mps,
            "training_launched": False,
            "cameras_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "state_counts": dict(sorted(state_counts.items())),
        "command_sequence_schema": COMMAND_SEQUENCE_SCHEMA,
        "safety_boundary": {
            "offline_only": True,
            "does_not_launch_training": True,
            "does_not_open_live_cameras": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
            "commands_are_file_outputs_only": True,
        },
    }
    return sequence, report


def write_offline_gate_pipeline_outputs(
    frames: list[EvaluationFrame],
    *,
    command_sequence_json: Path,
    report_json: Path,
    config: FpvRacingGateConfig | None = None,
    speed_mode: SpeedMode = SpeedMode.RACE_SPEED,
    requested_speed_mps: float | None = None,
    operator_limit_mps: float | None = None,
    source_path: Path | str | None = None,
) -> dict[str, Any]:
    sequence, report = run_offline_gate_pipeline(
        frames,
        config=config,
        speed_mode=speed_mode,
        requested_speed_mps=requested_speed_mps,
        operator_limit_mps=operator_limit_mps,
        source_path=source_path,
    )
    command_sequence_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    command_sequence_json.write_text(json.dumps(sequence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    persisted_report = dict(report)
    persisted_report["command_sequence_path"] = str(command_sequence_json)
    persisted_report["report_path"] = str(report_json)
    report_json.write_text(json.dumps(persisted_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted_report


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
