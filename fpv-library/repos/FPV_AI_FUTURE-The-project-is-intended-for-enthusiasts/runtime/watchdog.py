"""Runtime watchdog audit for FPV-AI transport frames.

The watchdog models the Betaflight-side AI command guard: frames are decoded
from wire bytes, then heartbeat, timestamps, and sequence continuity are
checked. This is an offline audit only; it never opens UART or publishes flight
commands.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from fpv_ai.betaflight_link.transport import PROTOCOL, TransportFrameError, decode_command_frame

REPORT_SCHEMA = "fpv_ai_watchdog_report.v1"


class WatchdogStatus(str, Enum):
    ACCEPTED = "AI_COMMAND_ACCEPTED"
    INVALID_FRAME = "AI_COMMAND_INVALID"
    HEARTBEAT_LOST = "AI_HEARTBEAT_LOST"
    COMMAND_TIMEOUT = "AI_COMMAND_TIMEOUT"
    SEQUENCE_GAP = "AI_SEQUENCE_GAP"
    TIMESTAMP_ROLLBACK = "AI_TIMESTAMP_ROLLBACK"


@dataclass(frozen=True)
class WatchdogConfig:
    command_timeout_ms: int = 500
    require_heartbeat: bool = True
    require_monotonic_sequence: bool = True

    def __post_init__(self) -> None:
        if self.command_timeout_ms <= 0:
            raise ValueError("command_timeout_ms must be positive")


def run_watchdog_audit(
    transport_frames: Mapping[str, Any],
    *,
    source_path: Path | str | None = None,
    config: WatchdogConfig | None = None,
) -> dict[str, Any]:
    active_config = config or WatchdogConfig()
    frames = transport_frames.get("frames")
    if not isinstance(frames, list):
        raise ValueError("transport frames payload must contain a frames list")

    events: list[dict[str, Any]] = []
    previous_sequence_id: int | None = None
    previous_timestamp_ms: int | None = None
    max_interval_ms = 0

    for fallback_index, frame_record in enumerate(frames):
        event, previous_sequence_id, previous_timestamp_ms, max_interval_ms = _audit_frame(
            frame_record,
            fallback_index=fallback_index,
            previous_sequence_id=previous_sequence_id,
            previous_timestamp_ms=previous_timestamp_ms,
            max_interval_ms=max_interval_ms,
            config=active_config,
        )
        events.append(event)

    counts = _count_events(events)
    rejected_count = sum(1 for event in events if not event["ai_control_allowed"])
    status = "PASS" if rejected_count == 0 else "FAIL"
    source = "" if source_path is None else str(source_path)
    return {
        "schema": REPORT_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "source_path": source,
        "source_schema": str(transport_frames.get("schema") or ""),
        "protocol": str(transport_frames.get("protocol") or PROTOCOL),
        "summary": {
            "frame_count": len(frames),
            "decoded_frame_count": sum(1 for event in events if event["decoded_ok"]),
            "accepted_command_count": counts[WatchdogStatus.ACCEPTED.value],
            "rejected_command_count": rejected_count,
            "invalid_frame_count": counts[WatchdogStatus.INVALID_FRAME.value],
            "heartbeat_lost_count": counts[WatchdogStatus.HEARTBEAT_LOST.value],
            "timeout_count": counts[WatchdogStatus.COMMAND_TIMEOUT.value],
            "sequence_gap_count": counts[WatchdogStatus.SEQUENCE_GAP.value],
            "timestamp_rollback_count": counts[WatchdogStatus.TIMESTAMP_ROLLBACK.value],
            "max_command_interval_ms": max_interval_ms,
            "command_timeout_ms": active_config.command_timeout_ms,
            "require_heartbeat": active_config.require_heartbeat,
            "require_monotonic_sequence": active_config.require_monotonic_sequence,
            "manual_kill_required": True,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "events": events,
        "safety_boundary": {
            "offline_only": True,
            "does_not_open_uart": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
            "manual_kill_required_for_real_props": True,
        },
    }


def write_watchdog_audit_output(
    transport_frames: Mapping[str, Any],
    *,
    report_json: Path,
    source_path: Path | str | None = None,
    config: WatchdogConfig | None = None,
) -> dict[str, Any]:
    report = run_watchdog_audit(transport_frames, source_path=source_path, config=config)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    persisted_report = dict(report)
    persisted_report["report_path"] = str(report_json)
    report_json.write_text(json.dumps(persisted_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted_report


def load_transport_frames(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("transport frames JSON must be an object")
    return payload


def _audit_frame(
    frame_record: Any,
    *,
    fallback_index: int,
    previous_sequence_id: int | None,
    previous_timestamp_ms: int | None,
    max_interval_ms: int,
    config: WatchdogConfig,
) -> tuple[dict[str, Any], int | None, int | None, int]:
    frame_index = fallback_index
    frame_crc32 = ""
    if isinstance(frame_record, Mapping):
        frame_index = int(frame_record.get("frame_index", fallback_index))
        frame_crc32 = str(frame_record.get("frame_crc32") or "")
        wire_hex = frame_record.get("wire_hex")
    else:
        wire_hex = None

    violations: list[str] = []
    decoded_ok = False
    sequence_id: int | None = None
    timestamp_ms: int | None = None
    heartbeat: bool | None = None
    interval_ms: int | None = None

    try:
        if not isinstance(wire_hex, str):
            raise TransportFrameError("missing wire_hex")
        command = decode_command_frame(bytes.fromhex(wire_hex))
        decoded_ok = True
        sequence_id = int(command["sequence_id"])
        timestamp_ms = int(command["timestamp_ms"])
        heartbeat = bool(command["heartbeat"])
    except (TransportFrameError, ValueError) as exc:
        violations.append(f"{WatchdogStatus.INVALID_FRAME.value}:{exc}")
        status = WatchdogStatus.INVALID_FRAME.value
        return (
            _event(
                frame_index=frame_index,
                frame_crc32=frame_crc32,
                status=status,
                decoded_ok=decoded_ok,
                sequence_id=sequence_id,
                timestamp_ms=timestamp_ms,
                heartbeat=heartbeat,
                interval_ms=interval_ms,
                violations=violations,
            ),
            previous_sequence_id,
            previous_timestamp_ms,
            max_interval_ms,
        )

    if config.require_heartbeat and heartbeat is not True:
        violations.append(WatchdogStatus.HEARTBEAT_LOST.value)
    if previous_sequence_id is not None and config.require_monotonic_sequence and sequence_id != previous_sequence_id + 1:
        violations.append(WatchdogStatus.SEQUENCE_GAP.value)
    if previous_timestamp_ms is not None:
        interval_ms = timestamp_ms - previous_timestamp_ms
        if interval_ms < 0:
            violations.append(WatchdogStatus.TIMESTAMP_ROLLBACK.value)
        else:
            max_interval_ms = max(max_interval_ms, interval_ms)
            if interval_ms > config.command_timeout_ms:
                violations.append(WatchdogStatus.COMMAND_TIMEOUT.value)

    status = _dominant_status(violations)
    event = _event(
        frame_index=frame_index,
        frame_crc32=frame_crc32,
        status=status,
        decoded_ok=decoded_ok,
        sequence_id=sequence_id,
        timestamp_ms=timestamp_ms,
        heartbeat=heartbeat,
        interval_ms=interval_ms,
        violations=violations,
    )
    if not violations:
        previous_sequence_id = sequence_id
        previous_timestamp_ms = timestamp_ms
    return event, previous_sequence_id, previous_timestamp_ms, max_interval_ms


def _dominant_status(violations: list[str]) -> str:
    if not violations:
        return WatchdogStatus.ACCEPTED.value
    for status in (
        WatchdogStatus.INVALID_FRAME.value,
        WatchdogStatus.HEARTBEAT_LOST.value,
        WatchdogStatus.TIMESTAMP_ROLLBACK.value,
        WatchdogStatus.SEQUENCE_GAP.value,
        WatchdogStatus.COMMAND_TIMEOUT.value,
    ):
        if any(violation.startswith(status) for violation in violations):
            return status
    return violations[0]


def _event(
    *,
    frame_index: int,
    frame_crc32: str,
    status: str,
    decoded_ok: bool,
    sequence_id: int | None,
    timestamp_ms: int | None,
    heartbeat: bool | None,
    interval_ms: int | None,
    violations: list[str],
) -> dict[str, Any]:
    return {
        "frame_index": frame_index,
        "frame_crc32": frame_crc32,
        "decoded_ok": decoded_ok,
        "sequence_id": sequence_id,
        "timestamp_ms": timestamp_ms,
        "heartbeat": heartbeat,
        "interval_ms": interval_ms,
        "status": status,
        "ai_control_allowed": not violations,
        "violations": violations,
        "recommended_action": "ACCEPT_AI_COMMAND" if not violations else "REJECT_AI_COMMAND",
    }


def _count_events(events: list[dict[str, Any]]) -> dict[str, int]:
    counts = {status.value: 0 for status in WatchdogStatus}
    for event in events:
        status = str(event["status"])
        counts[status] = counts.get(status, 0) + 1
    return counts


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
