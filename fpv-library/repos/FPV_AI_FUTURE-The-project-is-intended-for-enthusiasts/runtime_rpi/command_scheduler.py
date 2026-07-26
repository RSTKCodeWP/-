"""Runtime command cadence scheduler for FPV AI Gate-Lock dry-runs.

The scheduler refreshes the latest AI pilot intent into fresh command payloads
at a fixed cadence while the launch state allows AI control. It models the
Raspberry Pi runtime loop without opening UART or publishing flight commands.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fpv_ai.betaflight_link.commands import AICommand
from fpv_ai.control.speed import SpeedMode
from fpv_ai.runtime.timeline import load_json

SCHEDULE_SCHEMA = "fpv_runtime_scheduled_command_sequence.v1"
REPORT_SCHEMA = "fpv_runtime_command_cadence_report.v1"
ACTIVE_LAUNCH_STATES = {"THROTTLE_RAMP", "AI_ACTIVE", "GATE_APPROACH", "GATE_PASS"}
COMMAND_FIELDS = ("roll_cmd", "pitch_cmd", "yaw_rate_cmd", "throttle_cmd")


@dataclass(frozen=True)
class CommandSchedulerConfig:
    cadence_ms: int = 50
    command_timeout_ms: int = 250
    target_memory_hold_ms: int = 1500

    def __post_init__(self) -> None:
        if self.cadence_ms <= 0:
            raise ValueError("cadence_ms must be positive")
        if self.command_timeout_ms <= 0:
            raise ValueError("command_timeout_ms must be positive")
        if self.target_memory_hold_ms <= 0:
            raise ValueError("target_memory_hold_ms must be positive")
        if self.cadence_ms > self.command_timeout_ms:
            raise ValueError("cadence_ms must not exceed command_timeout_ms")


def build_scheduled_command_sequence(
    timeline: Mapping[str, Any],
    *,
    config: CommandSchedulerConfig | None = None,
    source_path: Path | str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    active_config = config or CommandSchedulerConfig()
    rows = _timeline_rows(timeline)
    command_templates = _command_templates(rows)
    schedule_timestamps = _schedule_timestamps(rows, cadence_ms=active_config.cadence_ms)
    next_sequence_id = _next_sequence_id(rows)

    scheduled_rows: list[dict[str, Any]] = []
    expired_count = 0
    for schedule_index, timestamp_ms in enumerate(schedule_timestamps):
        state_row = _latest_row_at_or_before(rows, timestamp_ms)
        source_command = _latest_command_at_or_before(command_templates, timestamp_ms)
        if source_command is None:
            expired_count += 1
            continue
        age_ms = timestamp_ms - int(source_command["timestamp_ms"])
        if age_ms > active_config.target_memory_hold_ms:
            expired_count += 1
            continue
        command_payload = _refresh_command_payload(
            source_command,
            sequence_id=next_sequence_id + len(scheduled_rows),
            timestamp_ms=timestamp_ms,
        )
        scheduled_rows.append(
            {
                "schema": "fpv_runtime_scheduled_command.v1",
                "schedule_index": schedule_index,
                "timestamp_ms": timestamp_ms,
                "source_frame_index": int(source_command["frame_index"]),
                "source_timestamp_ms": int(source_command["timestamp_ms"]),
                "source_command_crc32": str(source_command["command_crc32"]),
                "source_command_age_ms": age_ms,
                "launch_state": str(state_row.get("launch_state") or ""),
                "launch_ai_control_allowed": state_row.get("launch_ai_control_allowed") is True,
                "output_action": "REFRESH_ACTIVE_COMMAND",
                "command": command_payload,
            }
        )

    intervals = _intervals([int(row["timestamp_ms"]) for row in scheduled_rows])
    max_interval_ms = max(intervals, default=0)
    source = "" if source_path is None else str(source_path)
    sequence = {
        "schema": SCHEDULE_SCHEMA,
        "source_path": source,
        "source_schema": str(timeline.get("schema") or ""),
        "cadence_ms": active_config.cadence_ms,
        "command_timeout_ms": active_config.command_timeout_ms,
        "target_memory_hold_ms": active_config.target_memory_hold_ms,
        "scheduled_command_count": len(scheduled_rows),
        "commands": scheduled_rows,
        "safety_boundary": _safety_boundary(),
    }
    checks = [
        _check("active_window_present", bool(schedule_timestamps), f"ticks={len(schedule_timestamps)}"),
        _check("commands_scheduled", bool(scheduled_rows), f"commands={len(scheduled_rows)}"),
        _check("cadence_within_timeout", active_config.cadence_ms <= active_config.command_timeout_ms, f"{active_config.cadence_ms}<={active_config.command_timeout_ms}"),
        _check("max_interval_within_timeout", max_interval_ms <= active_config.command_timeout_ms, f"max_interval_ms={max_interval_ms}"),
        _check("target_memory_not_expired", expired_count == 0, f"expired_ticks={expired_count}"),
        _check("no_live_hardware_access", True, "file-output scheduler only"),
    ]
    report = {
        "schema": REPORT_SCHEMA,
        "status": "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL",
        "generated_at": _utc_now(),
        "source_path": source,
        "source_schema": str(timeline.get("schema") or ""),
        "config": {
            "cadence_ms": active_config.cadence_ms,
            "command_timeout_ms": active_config.command_timeout_ms,
            "target_memory_hold_ms": active_config.target_memory_hold_ms,
        },
        "summary": {
            "timeline_row_count": len(rows),
            "active_timeline_row_count": sum(1 for row in rows if _row_allows_ai_control(row)),
            "schedule_tick_count": len(schedule_timestamps),
            "scheduled_command_count": len(scheduled_rows),
            "source_command_count": len(command_templates),
            "expired_target_memory_count": expired_count,
            "max_scheduled_interval_ms": max_interval_ms,
            "stale_gap_count": sum(1 for interval in intervals if interval > active_config.command_timeout_ms),
            "first_scheduled_timestamp_ms": int(scheduled_rows[0]["timestamp_ms"]) if scheduled_rows else None,
            "last_scheduled_timestamp_ms": int(scheduled_rows[-1]["timestamp_ms"]) if scheduled_rows else None,
            "training_launched": False,
            "cameras_opened": False,
            "gpio_read": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "checks": checks,
        "safety_boundary": _safety_boundary(),
    }
    return sequence, report


def write_scheduled_command_outputs(
    *,
    timeline_json: Path,
    sequence_json: Path,
    report_json: Path,
    config: CommandSchedulerConfig | None = None,
) -> dict[str, Any]:
    timeline = load_json(timeline_json)
    sequence, report = build_scheduled_command_sequence(timeline, config=config, source_path=timeline_json)
    sequence_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    sequence_json.write_text(json.dumps(sequence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    persisted_report = dict(report)
    persisted_report["scheduled_command_sequence_path"] = str(sequence_json)
    persisted_report["report_path"] = str(report_json)
    report_json.write_text(json.dumps(persisted_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted_report


def load_scheduled_command_sequence(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    if payload.get("schema") != SCHEDULE_SCHEMA:
        raise ValueError(f"expected {SCHEDULE_SCHEMA} payload")
    return payload


def _timeline_rows(timeline: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = timeline.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("mission timeline must contain a non-empty rows list")
    if not all(isinstance(row, Mapping) for row in rows):
        raise ValueError("mission timeline rows must be objects")
    return sorted(rows, key=lambda row: int(row["timestamp_ms"]))


def _command_templates(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    for row in rows:
        if row.get("command_seen") is not True:
            continue
        templates.append(
            {
                "frame_index": int(row["frame_index"]),
                "timestamp_ms": int(row["timestamp_ms"]),
                "command_crc32": str(row.get("command_crc32") or ""),
                "roll_cmd": float(row["roll_cmd"]),
                "pitch_cmd": float(row["pitch_cmd"]),
                "yaw_rate_cmd": float(row["yaw_rate_cmd"]),
                "throttle_cmd": float(row["throttle_cmd"]),
                "target_confidence": float(row["lock_confidence"]),
                "target_state": str(row.get("lock_tracking_state") or "NO_TARGET"),
                "recovery_state": str(row.get("lock_recovery_state") or "NONE"),
                "speed_mode": str(row.get("speed_mode") or SpeedMode.FIXED_SPEED.value),
                "resolved_speed_mps": float(row.get("resolved_speed_mps") or 0.0),
            }
        )
    return templates


def _schedule_timestamps(rows: list[Mapping[str, Any]], *, cadence_ms: int) -> list[int]:
    active_rows = [row for row in rows if _row_allows_ai_control(row)]
    if not active_rows:
        return []
    first_ms = int(active_rows[0]["timestamp_ms"])
    last_ms = int(active_rows[-1]["timestamp_ms"])
    timestamps = set(range(first_ms, last_ms + 1, cadence_ms))
    timestamps.update(int(row["timestamp_ms"]) for row in active_rows)
    return sorted(timestamps)


def _row_allows_ai_control(row: Mapping[str, Any]) -> bool:
    return row.get("launch_ai_control_allowed") is True and str(row.get("launch_state") or "") in ACTIVE_LAUNCH_STATES


def _latest_row_at_or_before(rows: list[Mapping[str, Any]], timestamp_ms: int) -> Mapping[str, Any]:
    latest = rows[0]
    for row in rows:
        if int(row["timestamp_ms"]) > timestamp_ms:
            break
        latest = row
    return latest


def _latest_command_at_or_before(command_templates: list[dict[str, Any]], timestamp_ms: int) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    for command in command_templates:
        if int(command["timestamp_ms"]) > timestamp_ms:
            break
        latest = command
    return latest


def _refresh_command_payload(source_command: Mapping[str, Any], *, sequence_id: int, timestamp_ms: int) -> dict[str, Any]:
    return AICommand.bounded(
        roll_cmd=float(source_command["roll_cmd"]),
        pitch_cmd=float(source_command["pitch_cmd"]),
        yaw_rate_cmd=float(source_command["yaw_rate_cmd"]),
        throttle_cmd=float(source_command["throttle_cmd"]),
        target_confidence=float(source_command["target_confidence"]),
        target_state=str(source_command["target_state"]),
        recovery_state=str(source_command["recovery_state"]),
        speed_mode=SpeedMode(str(source_command["speed_mode"])),
        resolved_speed_mps=float(source_command["resolved_speed_mps"]),
        sequence_id=sequence_id,
        timestamp_ms=timestamp_ms,
    ).to_payload()


def _next_sequence_id(rows: list[Mapping[str, Any]]) -> int:
    sequence_ids = [
        int(row["command_sequence_id"])
        for row in rows
        if row.get("command_sequence_id") is not None
    ]
    return max(sequence_ids, default=-1) + 1


def _intervals(timestamps: list[int]) -> list[int]:
    return [
        current - previous
        for previous, current in zip(timestamps, timestamps[1:])
    ]


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    }


def _safety_boundary() -> dict[str, bool]:
    return {
        "dry_run_only": True,
        "does_not_launch_training": True,
        "does_not_open_live_cameras": True,
        "does_not_read_gpio": True,
        "does_not_open_uart": True,
        "does_not_authorize_hardware_test": True,
        "does_not_publish_flight_commands": True,
        "commands_are_file_outputs_only": True,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
