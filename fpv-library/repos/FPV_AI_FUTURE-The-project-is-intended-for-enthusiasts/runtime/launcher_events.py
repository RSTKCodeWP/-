"""Launcher event inputs for FPV AI hand-launch dry-runs.

This layer turns a file-backed launcher/flight-controller event sequence into
``LaunchInputFrame`` rows. It lets the mission dry-run use reproducible button,
arm-ack, hand-release, stabilized, and gate-pass events without GPIO, UART, or
real hardware.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fpv_ai.runtime.launch_state import LaunchInputFrame, launch_inputs_from_command_sequence

SEQUENCE_SCHEMA = "fpv_ai_launcher_event_sequence.v1"
REPORT_SCHEMA = "fpv_ai_launcher_event_report.v1"


@dataclass(frozen=True)
class LauncherEventFrame:
    frame_index: int
    timestamp_ms: int
    button_pressed: bool | None = None
    throttle_low: bool | None = None
    fc_armed: bool | None = None
    hand_release_detected: bool | None = None
    stabilized: bool | None = None
    gate_passed: bool | None = None
    manual_kill: bool | None = None
    watchdog_ok: bool | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if self.frame_index < 0:
            raise ValueError("frame_index must be non-negative")
        if self.timestamp_ms < 0:
            raise ValueError("timestamp_ms must be non-negative")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "LauncherEventFrame":
        return cls(
            frame_index=int(payload["frame_index"]),
            timestamp_ms=int(payload["timestamp_ms"]),
            button_pressed=_optional_bool(payload, "button_pressed"),
            throttle_low=_optional_bool(payload, "throttle_low"),
            fc_armed=_optional_bool(payload, "fc_armed"),
            hand_release_detected=_optional_bool(payload, "hand_release_detected"),
            stabilized=_optional_bool(payload, "stabilized"),
            gate_passed=_optional_bool(payload, "gate_passed"),
            manual_kill=_optional_bool(payload, "manual_kill"),
            watchdog_ok=_optional_bool(payload, "watchdog_ok"),
            note=str(payload.get("note") or ""),
        )

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "frame_index": self.frame_index,
            "timestamp_ms": self.timestamp_ms,
        }
        for field in (
            "button_pressed",
            "throttle_low",
            "fc_armed",
            "hand_release_detected",
            "stabilized",
            "gate_passed",
            "manual_kill",
            "watchdog_ok",
        ):
            value = getattr(self, field)
            if value is not None:
                payload[field] = value
        if self.note:
            payload["note"] = self.note
        return payload


def load_launcher_event_sequence(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("launcher event sequence JSON must be an object")
    return payload


def parse_launcher_event_sequence(payload: Mapping[str, Any]) -> list[LauncherEventFrame]:
    if payload.get("schema") != SEQUENCE_SCHEMA:
        raise ValueError(f"expected {SEQUENCE_SCHEMA} payload")
    events_payload = payload.get("events")
    if not isinstance(events_payload, list):
        raise ValueError("launcher event sequence must contain an events list")
    events = [
        LauncherEventFrame.from_payload(event)
        for event in events_payload
        if isinstance(event, Mapping)
    ]
    if len(events) != len(events_payload):
        raise ValueError("all launcher events must be objects")
    frame_indices = [event.frame_index for event in events]
    if len(set(frame_indices)) != len(frame_indices):
        raise ValueError("launcher event frame_index values must be unique")
    return sorted(events, key=lambda item: item.frame_index)


def build_launcher_event_report(payload: Mapping[str, Any], *, source_path: Path | str | None = None) -> dict[str, Any]:
    events = parse_launcher_event_sequence(payload)
    return {
        "schema": REPORT_SCHEMA,
        "status": "PASS",
        "generated_at": _utc_now(),
        "source_path": "" if source_path is None else str(source_path),
        "source_schema": str(payload.get("schema") or ""),
        "summary": {
            "event_count": len(events),
            "first_frame_index": events[0].frame_index if events else None,
            "last_frame_index": events[-1].frame_index if events else None,
            "button_pressed_count": sum(1 for event in events if event.button_pressed is True),
            "fc_armed_count": sum(1 for event in events if event.fc_armed is True),
            "hand_release_count": sum(1 for event in events if event.hand_release_detected is True),
            "stabilized_count": sum(1 for event in events if event.stabilized is True),
            "gate_passed_count": sum(1 for event in events if event.gate_passed is True),
            "manual_kill_count": sum(1 for event in events if event.manual_kill is True),
            "watchdog_not_ok_count": sum(1 for event in events if event.watchdog_ok is False),
            "training_launched": False,
            "cameras_opened": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "events": [event.to_payload() for event in events],
        "safety_boundary": {
            "file_input_only": True,
            "does_not_read_gpio": True,
            "does_not_open_uart": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
        },
    }


def write_launcher_event_report(
    payload: Mapping[str, Any],
    *,
    report_json: Path,
    source_path: Path | str | None = None,
) -> dict[str, Any]:
    report = build_launcher_event_report(payload, source_path=source_path)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    persisted_report = dict(report)
    persisted_report["report_path"] = str(report_json)
    report_json.write_text(json.dumps(persisted_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted_report


def launch_inputs_from_command_sequence_and_events(
    command_sequence: Mapping[str, Any],
    event_sequence: Mapping[str, Any],
) -> list[LaunchInputFrame]:
    base_frames = launch_inputs_from_command_sequence(command_sequence)
    events = parse_launcher_event_sequence(event_sequence)
    base_by_index = {frame.frame_index: frame for frame in base_frames}
    event_by_index = {event.frame_index: event for event in events}
    frame_indices = sorted(set(base_by_index).union(event_by_index))
    if not frame_indices:
        raise ValueError("at least one launch input frame is required")

    current_target_state = "NO_TARGET"
    current_target_locked = False
    throttle_low = True
    fc_armed = False
    stabilized = False
    watchdog_ok = True
    merged: list[LaunchInputFrame] = []

    for frame_index in frame_indices:
        base = base_by_index.get(frame_index)
        event = event_by_index.get(frame_index)
        if base is not None:
            current_target_state = base.target_state
            current_target_locked = base.target_locked
        if event is not None and event.throttle_low is not None:
            throttle_low = event.throttle_low
        if event is not None and event.fc_armed is not None:
            fc_armed = event.fc_armed
        if event is not None and event.stabilized is not None:
            stabilized = event.stabilized
        if event is not None and event.watchdog_ok is not None:
            watchdog_ok = event.watchdog_ok

        timestamp_ms = _timestamp_for_frame(frame_index, base, event, merged)
        merged.append(
            LaunchInputFrame(
                frame_index=frame_index,
                timestamp_ms=timestamp_ms,
                target_state=current_target_state,
                target_locked=current_target_locked,
                button_pressed=bool(event.button_pressed) if event else False,
                throttle_low=throttle_low,
                fc_armed=fc_armed,
                hand_release_detected=bool(event.hand_release_detected) if event else False,
                stabilized=stabilized,
                gate_passed=bool(event.gate_passed) if event else False,
                manual_kill=bool(event.manual_kill) if event else False,
                watchdog_ok=watchdog_ok,
            )
        )
    return merged


def build_synthetic_launcher_event_sequence(*, start_frame_index: int = 6, start_timestamp_ms: int = 793) -> dict[str, Any]:
    """Build a launcher event sequence that completes the current offline lock smoke."""

    def event(offset: int, dt_ms: int, **fields: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "frame_index": start_frame_index + offset,
            "timestamp_ms": start_timestamp_ms + dt_ms,
        }
        payload.update(fields)
        return payload

    return {
        "schema": SEQUENCE_SCHEMA,
        "source": "synthetic://fpv_launcher_events",
        "events": [
            event(0, 0),
            event(1, 33, button_pressed=True),
            event(2, 66),
            event(3, 99, fc_armed=True),
            event(4, 132, hand_release_detected=True),
            event(5, 165),
            event(6, 198, stabilized=True),
            event(7, 298),
            event(8, 432),
            event(9, 465),
            event(10, 498, gate_passed=True),
            event(11, 531),
        ],
    }


def _timestamp_for_frame(
    frame_index: int,
    base: LaunchInputFrame | None,
    event: LauncherEventFrame | None,
    merged: list[LaunchInputFrame],
) -> int:
    if event is not None:
        return event.timestamp_ms
    if base is not None:
        return base.timestamp_ms
    if merged:
        return merged[-1].timestamp_ms + 33
    return frame_index * 33


def _optional_bool(payload: Mapping[str, Any], key: str) -> bool | None:
    if key not in payload:
        return None
    value = payload[key]
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be boolean when present")
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
