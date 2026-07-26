"""Unified FPV AI mission timeline logger.

The timeline joins the offline mission artifacts into rows keyed by
``frame_index`` so bench/HIL work can trace every stage deterministically:

``lock -> AI command -> transport frame -> watchdog -> launcher event -> launch state``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

TIMELINE_SCHEMA = "fpv_ai_mission_timeline.v1"
REPORT_SCHEMA = "fpv_ai_mission_timeline_report.v1"


def build_mission_timeline(
    *,
    command_sequence: Mapping[str, Any],
    transport_frames: Mapping[str, Any],
    watchdog_report: Mapping[str, Any],
    launch_report: Mapping[str, Any],
    launcher_event_report: Mapping[str, Any] | None = None,
    source_path: Path | str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    command_rows = _by_frame(command_sequence.get("commands"))
    transport_rows = _by_frame(transport_frames.get("frames"))
    watchdog_rows = _by_frame(watchdog_report.get("events"))
    launcher_rows = _by_frame(launcher_event_report.get("events") if launcher_event_report else None)
    launch_rows = _by_frame(launch_report.get("events"))
    frame_indices = sorted(set(command_rows) | set(transport_rows) | set(watchdog_rows) | set(launcher_rows) | set(launch_rows))
    if not frame_indices:
        raise ValueError("cannot build mission timeline without at least one row")

    rows = [
        _timeline_row(
            frame_index=frame_index,
            command_row=command_rows.get(frame_index),
            transport_row=transport_rows.get(frame_index),
            watchdog_row=watchdog_rows.get(frame_index),
            launcher_row=launcher_rows.get(frame_index),
            launch_row=launch_rows.get(frame_index),
        )
        for frame_index in frame_indices
    ]
    source = "" if source_path is None else str(source_path)
    timeline = {
        "schema": TIMELINE_SCHEMA,
        "generated_at": _utc_now(),
        "source_path": source,
        "row_count": len(rows),
        "rows": rows,
        "safety_boundary": _safety_boundary(),
    }
    report = {
        "schema": REPORT_SCHEMA,
        "status": "PASS",
        "generated_at": _utc_now(),
        "source_path": source,
        "timeline_schema": TIMELINE_SCHEMA,
        "summary": {
            "row_count": len(rows),
            "command_row_count": sum(1 for row in rows if row["command_seen"]),
            "transport_row_count": sum(1 for row in rows if row["transport_seen"]),
            "watchdog_row_count": sum(1 for row in rows if row["watchdog_seen"]),
            "launcher_event_row_count": sum(1 for row in rows if row["launcher_event_seen"]),
            "launch_row_count": sum(1 for row in rows if row["launch_seen"]),
            "first_timestamp_ms": min(int(row["timestamp_ms"]) for row in rows),
            "last_timestamp_ms": max(int(row["timestamp_ms"]) for row in rows),
            "final_launch_state": str(rows[-1]["launch_state"] or ""),
            "mission_complete": rows[-1]["launch_state"] == "COMPLETE",
            "watchdog_rejected_count": sum(1 for row in rows if row["watchdog_ai_control_allowed"] is False),
            "manual_kill_count": sum(1 for row in rows if row["manual_kill"] is True),
            "max_resolved_speed_mps": max(float(row["resolved_speed_mps"] or 0.0) for row in rows),
            "training_launched": False,
            "cameras_opened": False,
            "gpio_read": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "safety_boundary": _safety_boundary(),
    }
    return timeline, report


def write_mission_timeline_outputs(
    *,
    command_sequence: Mapping[str, Any],
    transport_frames: Mapping[str, Any],
    watchdog_report: Mapping[str, Any],
    launch_report: Mapping[str, Any],
    timeline_json: Path,
    report_json: Path,
    launcher_event_report: Mapping[str, Any] | None = None,
    source_path: Path | str | None = None,
) -> dict[str, Any]:
    timeline, report = build_mission_timeline(
        command_sequence=command_sequence,
        transport_frames=transport_frames,
        watchdog_report=watchdog_report,
        launch_report=launch_report,
        launcher_event_report=launcher_event_report,
        source_path=source_path,
    )
    timeline_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    timeline_json.write_text(json.dumps(timeline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    persisted_report = dict(report)
    persisted_report["timeline_path"] = str(timeline_json)
    persisted_report["report_path"] = str(report_json)
    report_json.write_text(json.dumps(persisted_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted_report


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _timeline_row(
    *,
    frame_index: int,
    command_row: Mapping[str, Any] | None,
    transport_row: Mapping[str, Any] | None,
    watchdog_row: Mapping[str, Any] | None,
    launcher_row: Mapping[str, Any] | None,
    launch_row: Mapping[str, Any] | None,
) -> dict[str, Any]:
    lock = _mapping(command_row.get("lock") if command_row else None)
    command = _mapping(command_row.get("command") if command_row else None)
    timestamp_ms = _timestamp_ms(command_row, launch_row, watchdog_row, launcher_row, transport_row)
    return {
        "schema": "fpv_ai_mission_timeline_row.v1",
        "frame_index": frame_index,
        "timestamp_ms": timestamp_ms,
        "command_seen": command_row is not None,
        "transport_seen": transport_row is not None,
        "watchdog_seen": watchdog_row is not None,
        "launcher_event_seen": launcher_row is not None,
        "launch_seen": launch_row is not None,
        "detections_seen": _optional_int(command_row, "detections_seen"),
        "selected_detection": _optional_bool(command_row, "selected_detection"),
        "lock_tracking_state": _optional_str(lock, "tracking_state"),
        "target_locked": _optional_bool(lock, "target_locked"),
        "lock_confidence": _optional_float(lock, "confidence"),
        "lock_recovery_state": _optional_str(lock, "recovery_state"),
        "lock_recommended_action": _optional_str(lock, "recommended_action"),
        "command_sequence_id": _optional_int(command, "sequence_id"),
        "roll_cmd": _optional_float(command, "roll_cmd"),
        "pitch_cmd": _optional_float(command, "pitch_cmd"),
        "yaw_rate_cmd": _optional_float(command, "yaw_rate_cmd"),
        "throttle_cmd": _optional_float(command, "throttle_cmd"),
        "resolved_speed_mps": _optional_float(command, "resolved_speed_mps"),
        "speed_mode": _optional_str(command, "speed_mode"),
        "command_crc32": _optional_str(command, "crc32"),
        "transport_frame_crc32": _optional_str(transport_row, "frame_crc32"),
        "transport_payload_crc32": _optional_str(transport_row, "payload_crc32"),
        "transport_decoded_ok": _optional_bool(transport_row, "decoded_ok"),
        "watchdog_status": _optional_str(watchdog_row, "status"),
        "watchdog_ai_control_allowed": _optional_bool(watchdog_row, "ai_control_allowed"),
        "watchdog_violations": _optional_list(watchdog_row, "violations"),
        "button_pressed": _optional_bool(launch_row, "button_pressed"),
        "throttle_low": _optional_bool(launch_row, "throttle_low"),
        "fc_armed": _optional_bool(launch_row, "fc_armed"),
        "hand_release_detected": _optional_bool(launch_row, "hand_release_detected"),
        "stabilized": _optional_bool(launch_row, "stabilized"),
        "gate_passed": _optional_bool(launch_row, "gate_passed"),
        "manual_kill": _optional_bool(launch_row, "manual_kill"),
        "launch_state": _optional_str(launch_row, "launch_state"),
        "screen_state": _optional_str(launch_row, "screen_state"),
        "arm_request": _optional_bool(launch_row, "arm_request"),
        "throttle_ramp_progress": _optional_float(launch_row, "throttle_ramp_progress"),
        "launch_ai_control_allowed": _optional_bool(launch_row, "ai_control_allowed"),
        "launch_recommended_action": _optional_str(launch_row, "recommended_action"),
        "launcher_event_fields": sorted(_event_fields(launcher_row)),
    }


def _by_frame(rows: Any) -> dict[int, Mapping[str, Any]]:
    if rows is None:
        return {}
    if not isinstance(rows, list):
        raise ValueError("timeline source rows must be a list")
    result: dict[int, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("timeline source row must be an object")
        frame_index = int(row["frame_index"])
        if frame_index in result:
            raise ValueError(f"duplicate frame_index in timeline source: {frame_index}")
        result[frame_index] = row
    return result


def _timestamp_ms(*rows: Mapping[str, Any] | None) -> int:
    for row in rows:
        if row is not None and "timestamp_ms" in row:
            return int(row["timestamp_ms"])
    return 0


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _optional_int(row: Mapping[str, Any] | None, key: str) -> int | None:
    return int(row[key]) if row is not None and row.get(key) is not None else None


def _optional_float(row: Mapping[str, Any] | None, key: str) -> float | None:
    return float(row[key]) if row is not None and row.get(key) is not None else None


def _optional_str(row: Mapping[str, Any] | None, key: str) -> str | None:
    return str(row[key]) if row is not None and row.get(key) is not None else None


def _optional_bool(row: Mapping[str, Any] | None, key: str) -> bool | None:
    return bool(row[key]) if row is not None and row.get(key) is not None else None


def _optional_list(row: Mapping[str, Any] | None, key: str) -> list[str]:
    value = row.get(key) if row is not None else None
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _event_fields(row: Mapping[str, Any] | None) -> list[str]:
    if row is None:
        return []
    return [
        key
        for key in (
            "button_pressed",
            "throttle_low",
            "fc_armed",
            "hand_release_detected",
            "stabilized",
            "gate_passed",
            "manual_kill",
            "watchdog_ok",
        )
        if key in row
    ]


def _safety_boundary() -> dict[str, bool]:
    return {
        "dry_run_only": True,
        "does_not_launch_training": True,
        "does_not_open_live_cameras": True,
        "does_not_read_gpio": True,
        "does_not_open_uart": True,
        "does_not_authorize_hardware_test": True,
        "does_not_publish_flight_commands": True,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
