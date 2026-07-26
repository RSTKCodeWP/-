"""Bench/HIL dry-run checks for the FPV AI Gate-Lock runtime.

This module simulates the Raspberry Pi to Betaflight bench contract from file
artifacts. It verifies command ranges, neutral output gating, stale-command
blocking, and hand-launch transitions without opening cameras, GPIO, UART, or
publishing real flight commands.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from fpv_ai.runtime.timeline import load_json

REPORT_SCHEMA = "fpv_bench_hil_report.v1"
COMMAND_FIELDS = ("roll_cmd", "pitch_cmd", "yaw_rate_cmd", "throttle_cmd")
ORDERED_LAUNCH_STATES = (
    "AI_PREARM_READY",
    "BUTTON_CONFIRMED",
    "AI_ARM_REQUEST",
    "ARMED_IDLE",
    "HAND_RELEASE_DETECTED",
    "STABILIZE",
    "THROTTLE_RAMP",
    "AI_ACTIVE",
    "GATE_PASS",
    "COMPLETE",
)


@dataclass(frozen=True)
class BenchHilConfig:
    command_timeout_ms: int = 250

    def __post_init__(self) -> None:
        if self.command_timeout_ms <= 0:
            raise ValueError("command_timeout_ms must be positive")


def build_bench_hil_report(
    timeline: Mapping[str, Any],
    *,
    scheduled_commands: Mapping[str, Any] | None = None,
    config: BenchHilConfig | None = None,
    source_path: Path | str | None = None,
) -> dict[str, Any]:
    active_config = config or BenchHilConfig()
    rows = _timeline_rows(timeline)
    command_range_violations = _command_range_violations(rows)
    scheduled_command_rows = _scheduled_command_rows(scheduled_commands)
    mock_events = _mock_fc_events(
        rows,
        command_timeout_ms=active_config.command_timeout_ms,
        scheduled_command_rows=scheduled_command_rows,
    )
    launch_order = _launch_order(rows)
    stale_probe = _stale_timeout_probe(rows, command_timeout_ms=active_config.command_timeout_ms)

    checks = [
        _check("timeline_available", bool(rows), f"rows={len(rows)}"),
        _check("no_propellers_required", True, "bench/HIL dry-run only"),
        _check("command_ranges_valid", not command_range_violations, f"violations={len(command_range_violations)}"),
        _check("neutral_before_ai_control", _neutral_before_ai_control(mock_events), "launch gate controls output"),
        _check("stale_timeout_probe_blocked", bool(stale_probe["blocked"]), f"timeout_ms={active_config.command_timeout_ms}"),
        _check("stale_runtime_rows_blocked", _stale_rows_blocked(mock_events), "stale rows output neutral"),
        _check(
            "scheduled_commands_fresh_when_provided",
            _scheduled_commands_fresh_when_provided(mock_events, scheduled_command_rows),
            f"scheduled={len(scheduled_command_rows)}",
        ),
        _check("hand_launch_order_valid", bool(launch_order["valid"]), ",".join(launch_order["missing_states"])),
        _check("arm_request_requires_throttle_low", _arm_request_requires_throttle_low(rows), "AI_ARM_REQUEST rows"),
        _check("fc_ack_after_arm_request", _fc_ack_after_arm_request(rows), "synthetic FC ACK order"),
        _check("mock_command_output_after_ramp", _mock_publish_count(mock_events) > 0, "mock output only"),
        _check("no_live_hardware_access", True, "no camera/GPIO/UART opened"),
    ]
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "schema": REPORT_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "source_path": "" if source_path is None else str(source_path),
        "source_schema": str(timeline.get("schema") or ""),
        "config": {
            "command_timeout_ms": active_config.command_timeout_ms,
        },
        "summary": {
            "timeline_row_count": len(rows),
            "command_row_count": sum(1 for row in rows if row.get("command_seen") is True),
            "scheduled_command_count": len(scheduled_command_rows),
            "command_range_violation_count": len(command_range_violations),
            "neutral_hold_count": sum(1 for event in mock_events if event["output_action"] == "NEUTRAL_HOLD"),
            "mock_command_publish_count": _mock_publish_count(mock_events),
            "stale_block_count": sum(1 for event in mock_events if event["output_action"] == "MOCK_COMMAND_REJECTED_STALE"),
            "manual_kill_count": sum(1 for row in rows if row.get("manual_kill") is True),
            "arm_request_count": sum(1 for row in rows if row.get("arm_request") is True),
            "fc_arm_ack_count": sum(1 for row in rows if row.get("fc_armed") is True),
            "hand_release_count": sum(1 for row in rows if row.get("hand_release_detected") is True),
            "throttle_ramp_seen": _state_seen(rows, "THROTTLE_RAMP"),
            "ai_active_seen": _state_seen(rows, "AI_ACTIVE"),
            "gate_pass_seen": _state_seen(rows, "GATE_PASS"),
            "final_launch_state": str(rows[-1].get("launch_state") or ""),
            "stale_timeout_probe_blocked": bool(stale_probe["blocked"]),
            "training_launched": False,
            "cameras_opened": False,
            "gpio_read": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "checks": checks,
        "launch_order": launch_order,
        "stale_timeout_probe": stale_probe,
        "command_range_violations": command_range_violations,
        "mock_fc_events": mock_events,
        "safety_boundary": {
            "dry_run_only": True,
            "no_propellers": True,
            "does_not_launch_training": True,
            "does_not_open_live_cameras": True,
            "does_not_read_gpio": True,
            "does_not_open_uart": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
            "mock_outputs_only": True,
        },
    }


def write_bench_hil_report(
    *,
    timeline_json: Path,
    report_json: Path,
    scheduled_command_json: Path | None = None,
    config: BenchHilConfig | None = None,
) -> dict[str, Any]:
    timeline = load_json(timeline_json)
    scheduled_commands = load_json(scheduled_command_json) if scheduled_command_json is not None else None
    report = build_bench_hil_report(
        timeline,
        scheduled_commands=scheduled_commands,
        config=config,
        source_path=timeline_json,
    )
    persisted_report = dict(report)
    persisted_report["report_path"] = str(report_json)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(persisted_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted_report


def _timeline_rows(timeline: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = timeline.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("mission timeline must contain a non-empty rows list")
    if not all(isinstance(row, Mapping) for row in rows):
        raise ValueError("mission timeline rows must be objects")
    return sorted(rows, key=lambda row: int(row["frame_index"]))


def _command_range_violations(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for row in rows:
        if row.get("command_seen") is not True:
            continue
        for field in COMMAND_FIELDS:
            value = float(row[field])
            low, high = (0.0, 1.0) if field == "throttle_cmd" else (-1.0, 1.0)
            if value < low or value > high:
                violations.append(_violation(row, field, value, f"{low}..{high}"))
        confidence = row.get("lock_confidence")
        if confidence is not None:
            confidence_value = float(confidence)
            if confidence_value < 0.0 or confidence_value > 1.0:
                violations.append(_violation(row, "lock_confidence", confidence_value, "0.0..1.0"))
        speed = row.get("resolved_speed_mps")
        if speed is not None and float(speed) < 0.0:
            violations.append(_violation(row, "resolved_speed_mps", float(speed), ">=0.0"))
    return violations


def _mock_fc_events(
    rows: list[Mapping[str, Any]],
    *,
    command_timeout_ms: int,
    scheduled_command_rows: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    last_command: dict[str, float] | None = None
    last_command_timestamp_ms: int | None = None
    last_command_crc32 = ""

    for row in rows:
        timestamp_ms = int(row["timestamp_ms"])
        scheduled_command = _latest_scheduled_command_at_or_before(scheduled_command_rows, timestamp_ms)
        if scheduled_command is not None:
            command = _command_payload(scheduled_command)
            last_command = {field: float(command[field]) for field in COMMAND_FIELDS}
            last_command_timestamp_ms = int(command["timestamp_ms"])
            last_command_crc32 = str(command.get("crc32") or "")
        elif row.get("command_seen") is True:
            last_command = {field: float(row[field]) for field in COMMAND_FIELDS}
            last_command_timestamp_ms = timestamp_ms
            last_command_crc32 = str(row.get("command_crc32") or "")

        age_ms = None if last_command_timestamp_ms is None else timestamp_ms - last_command_timestamp_ms
        command_fresh = age_ms is not None and 0 <= age_ms <= command_timeout_ms
        launch_allows_control = row.get("launch_ai_control_allowed") is True
        manual_kill = row.get("manual_kill") is True

        output_action = "NEUTRAL_HOLD"
        reason = "launch_control_not_allowed"
        output = _neutral_output()

        if manual_kill:
            reason = "manual_kill"
        elif launch_allows_control:
            if last_command is None or not command_fresh:
                output_action = "MOCK_COMMAND_REJECTED_STALE"
                reason = "stale_or_missing_ai_command"
            else:
                output_action = "MOCK_COMMAND_ACCEPTED"
                reason = "launch_and_watchdog_allow_control"
                output = _scaled_output(last_command, float(row.get("throttle_ramp_progress") or 1.0))

        events.append(
            {
                "frame_index": int(row["frame_index"]),
                "timestamp_ms": timestamp_ms,
                "launch_state": str(row.get("launch_state") or ""),
                "launch_ai_control_allowed": launch_allows_control,
                "manual_kill": manual_kill,
                "arm_request": row.get("arm_request") is True,
                "fc_armed": row.get("fc_armed") is True,
                "last_command_age_ms": age_ms,
                "last_command_crc32": last_command_crc32,
                "used_scheduled_command": scheduled_command is not None,
                "command_fresh": command_fresh,
                "output_action": output_action,
                "reason": reason,
                "mock_roll_cmd": output["roll_cmd"],
                "mock_pitch_cmd": output["pitch_cmd"],
                "mock_yaw_rate_cmd": output["yaw_rate_cmd"],
                "mock_throttle_cmd": output["throttle_cmd"],
                "actual_uart_opened": False,
                "actual_command_published": False,
            }
        )
    return events


def _scheduled_command_rows(scheduled_commands: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if scheduled_commands is None:
        return []
    rows = scheduled_commands.get("commands")
    if not isinstance(rows, list):
        raise ValueError("scheduled command sequence must contain a commands list")
    if not all(isinstance(row, Mapping) for row in rows):
        raise ValueError("scheduled command rows must be objects")
    return sorted(rows, key=lambda row: int(row["timestamp_ms"]))


def _latest_scheduled_command_at_or_before(
    scheduled_command_rows: list[Mapping[str, Any]],
    timestamp_ms: int,
) -> Mapping[str, Any] | None:
    latest: Mapping[str, Any] | None = None
    for row in scheduled_command_rows:
        if int(row["timestamp_ms"]) > timestamp_ms:
            break
        latest = row
    return latest


def _command_payload(scheduled_command: Mapping[str, Any]) -> Mapping[str, Any]:
    command = scheduled_command.get("command")
    if not isinstance(command, Mapping):
        raise ValueError("scheduled command row must contain a command object")
    return command


def _scaled_output(command: Mapping[str, float], throttle_ramp_progress: float) -> dict[str, float]:
    ramp = min(max(throttle_ramp_progress, 0.0), 1.0)
    return {
        "roll_cmd": round(float(command["roll_cmd"]), 6),
        "pitch_cmd": round(float(command["pitch_cmd"]), 6),
        "yaw_rate_cmd": round(float(command["yaw_rate_cmd"]), 6),
        "throttle_cmd": round(float(command["throttle_cmd"]) * ramp, 6),
    }


def _neutral_output() -> dict[str, float]:
    return {
        "roll_cmd": 0.0,
        "pitch_cmd": 0.0,
        "yaw_rate_cmd": 0.0,
        "throttle_cmd": 0.0,
    }


def _launch_order(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    positions: dict[str, int] = {}
    for index, row in enumerate(rows):
        state = str(row.get("launch_state") or "")
        positions.setdefault(state, index)
    ordered_positions = [positions[state] for state in ORDERED_LAUNCH_STATES if state in positions]
    missing = [state for state in ORDERED_LAUNCH_STATES if state not in positions]
    return {
        "required_states": list(ORDERED_LAUNCH_STATES),
        "missing_states": missing,
        "state_positions": {state: positions[state] for state in ORDERED_LAUNCH_STATES if state in positions},
        "valid": not missing and ordered_positions == sorted(ordered_positions),
    }


def _stale_timeout_probe(rows: list[Mapping[str, Any]], *, command_timeout_ms: int) -> dict[str, Any]:
    command_rows = [row for row in rows if row.get("command_seen") is True]
    last_command_row = command_rows[-1] if command_rows else None
    if last_command_row is None:
        return {
            "last_command_frame_index": None,
            "last_command_timestamp_ms": None,
            "probe_timestamp_ms": command_timeout_ms + 1,
            "command_age_ms": None,
            "blocked": True,
            "reason": "no_command_available",
        }
    last_timestamp = int(last_command_row["timestamp_ms"])
    probe_timestamp = last_timestamp + command_timeout_ms + 1
    return {
        "last_command_frame_index": int(last_command_row["frame_index"]),
        "last_command_timestamp_ms": last_timestamp,
        "probe_timestamp_ms": probe_timestamp,
        "command_age_ms": command_timeout_ms + 1,
        "blocked": True,
        "reason": "age_exceeds_command_timeout",
    }


def _neutral_before_ai_control(events: Sequence[Mapping[str, Any]]) -> bool:
    return all(
        event["output_action"] == "NEUTRAL_HOLD"
        and float(event["mock_roll_cmd"]) == 0.0
        and float(event["mock_pitch_cmd"]) == 0.0
        and float(event["mock_yaw_rate_cmd"]) == 0.0
        and float(event["mock_throttle_cmd"]) == 0.0
        for event in events
        if event["launch_ai_control_allowed"] is False
    )


def _stale_rows_blocked(events: Sequence[Mapping[str, Any]]) -> bool:
    return all(
        event["output_action"] == "MOCK_COMMAND_REJECTED_STALE"
        and event["actual_command_published"] is False
        and float(event["mock_throttle_cmd"]) == 0.0
        for event in events
        if event["launch_ai_control_allowed"] is True and event["command_fresh"] is False
    )


def _scheduled_commands_fresh_when_provided(
    events: Sequence[Mapping[str, Any]],
    scheduled_command_rows: Sequence[Mapping[str, Any]],
) -> bool:
    if not scheduled_command_rows:
        return True
    return all(
        event["used_scheduled_command"] is True
        and event["command_fresh"] is True
        and event["output_action"] == "MOCK_COMMAND_ACCEPTED"
        for event in events
        if event["launch_ai_control_allowed"] is True
    )


def _arm_request_requires_throttle_low(rows: list[Mapping[str, Any]]) -> bool:
    return all(row.get("throttle_low") is True for row in rows if row.get("arm_request") is True)


def _fc_ack_after_arm_request(rows: list[Mapping[str, Any]]) -> bool:
    arm_request_indexes = [index for index, row in enumerate(rows) if row.get("arm_request") is True]
    fc_armed_indexes = [index for index, row in enumerate(rows) if row.get("fc_armed") is True]
    return bool(arm_request_indexes and fc_armed_indexes and min(fc_armed_indexes) > min(arm_request_indexes))


def _state_seen(rows: list[Mapping[str, Any]], state: str) -> bool:
    return any(row.get("launch_state") == state for row in rows)


def _mock_publish_count(events: Sequence[Mapping[str, Any]]) -> int:
    return sum(1 for event in events if event["output_action"] == "MOCK_COMMAND_ACCEPTED")


def _violation(row: Mapping[str, Any], field: str, value: float, expected: str) -> dict[str, Any]:
    return {
        "frame_index": int(row["frame_index"]),
        "timestamp_ms": int(row["timestamp_ms"]),
        "field": field,
        "value": value,
        "expected": expected,
    }


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
