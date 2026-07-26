"""Launcher screen/status dry-run for FPV AI Gate-Lock.

This module turns mission timeline and protocol readiness artifacts into the
operator-facing launcher screen contract. It does not open a display, GPIO, a
camera, or UART; it only writes file artifacts for review and tests.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from fpv_ai.runtime.timeline import load_json

REPORT_SCHEMA = "fpv_launcher_screen_report.v1"
SCREEN_STATES = {
    "NO TARGET",
    "CANDIDATE",
    "LOCKED",
    "READY TO LAUNCH",
    "AI ACTIVE",
    "DEGRADED",
    "REACQUIRE",
    "RECOVERED",
    "COMPLETE",
    "MANUAL KILL",
}


def build_launcher_screen_report(
    timeline: Mapping[str, Any],
    *,
    protocol_readiness: Mapping[str, Any] | None = None,
    source_path: Path | str | None = None,
    protocol_source_path: Path | str | None = None,
) -> dict[str, Any]:
    rows = _timeline_rows(timeline)
    protocol_health = _protocol_health(protocol_readiness)
    frames = [_screen_frame(row, protocol_health=protocol_health) for row in rows]
    checks = [
        _check("timeline_available", bool(frames), f"rows={len(frames)}"),
        _check("screen_states_valid", all(frame["screen_state"] in SCREEN_STATES for frame in frames), "allowed TZ states"),
        _check("button_action_defined", all(bool(frame["button_action"]) for frame in frames), "one-button contract"),
        _check("protocol_health_available", protocol_health["status"] != "UNKNOWN", protocol_health["status"]),
        _check("protocol_health_not_degraded", protocol_health["status"] != "DEGRADED", protocol_health["detail"]),
        _check("no_live_screen_access", True, "file-output launcher screen only"),
    ]
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    state_counts = _state_counts(frames)
    return {
        "schema": REPORT_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "source_path": "" if source_path is None else str(source_path),
        "source_schema": str(timeline.get("schema") or ""),
        "protocol_source_path": "" if protocol_source_path is None else str(protocol_source_path),
        "protocol_health": protocol_health,
        "summary": {
            "frame_count": len(frames),
            "final_screen_state": str(frames[-1]["screen_state"]),
            "final_button_action": str(frames[-1]["button_action"]),
            "locked_frame_count": state_counts.get("LOCKED", 0),
            "ready_to_launch_frame_count": state_counts.get("READY TO LAUNCH", 0),
            "ai_active_frame_count": state_counts.get("AI ACTIVE", 0),
            "recovery_frame_count": state_counts.get("DEGRADED", 0) + state_counts.get("REACQUIRE", 0) + state_counts.get("RECOVERED", 0),
            "complete_frame_count": state_counts.get("COMPLETE", 0),
            "manual_kill_frame_count": state_counts.get("MANUAL KILL", 0),
            "button_enabled_count": sum(1 for frame in frames if frame["button_enabled"]),
            "protocol_status": protocol_health["status"],
            "training_launched": False,
            "cameras_opened": False,
            "gpio_read": False,
            "uart_opened": False,
            "screen_device_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "screen_state_counts": state_counts,
        "checks": checks,
        "frames": frames,
        "safety_boundary": {
            "dry_run_only": True,
            "does_not_launch_training": True,
            "does_not_open_live_cameras": True,
            "does_not_read_gpio": True,
            "does_not_open_uart": True,
            "does_not_open_screen_device": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
            "screen_outputs_are_file_only": True,
        },
    }


def write_launcher_screen_report(
    *,
    timeline_json: Path,
    report_json: Path,
    protocol_readiness_json: Path | None = None,
) -> dict[str, Any]:
    timeline = load_json(timeline_json)
    protocol_readiness = load_json(protocol_readiness_json) if protocol_readiness_json is not None else None
    report = build_launcher_screen_report(
        timeline,
        protocol_readiness=protocol_readiness,
        source_path=timeline_json,
        protocol_source_path=protocol_readiness_json,
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


def _screen_frame(row: Mapping[str, Any], *, protocol_health: Mapping[str, str]) -> dict[str, Any]:
    screen_state = _screen_state(row)
    button_action, button_enabled = _button_contract(row, screen_state)
    warning = _warning(row, protocol_health)
    return {
        "schema": "fpv_launcher_screen_frame.v1",
        "frame_index": int(row["frame_index"]),
        "timestamp_ms": int(row["timestamp_ms"]),
        "screen_state": screen_state,
        "primary_status": _primary_status(screen_state),
        "secondary_status": _secondary_status(row, protocol_health),
        "button_action": button_action,
        "button_enabled": button_enabled,
        "target_state": _optional_str(row, "lock_tracking_state"),
        "target_confidence": _optional_float(row, "lock_confidence"),
        "target_locked": _optional_bool(row, "target_locked"),
        "launch_state": _optional_str(row, "launch_state"),
        "protocol_health": protocol_health["status"],
        "protocol_detail": protocol_health["detail"],
        "ai_control_allowed": _optional_bool(row, "launch_ai_control_allowed"),
        "arm_request": _optional_bool(row, "arm_request"),
        "throttle_ramp_progress": _optional_float(row, "throttle_ramp_progress"),
        "manual_kill": _optional_bool(row, "manual_kill"),
        "warning": warning,
        "screen_device_opened": False,
        "gpio_read": False,
    }


def _screen_state(row: Mapping[str, Any]) -> str:
    if row.get("manual_kill") is True or row.get("launch_state") == "MANUAL_KILL":
        return "MANUAL KILL"
    if row.get("launch_state") in {"GATE_PASS", "COMPLETE"}:
        return "COMPLETE"

    tracking_state = str(row.get("lock_tracking_state") or "")
    if tracking_state == "DEGRADED":
        return "DEGRADED"
    if tracking_state in {"PREDICTIVE_TRACK", "REACQUIRE", "HARD_LOST"}:
        return "REACQUIRE"
    if tracking_state == "RECOVERED":
        return "RECOVERED"

    launch_state = str(row.get("launch_state") or "")
    if launch_state in {"AI_PREARM_READY", "BUTTON_CONFIRMED", "AI_ARM_REQUEST", "ARMED_IDLE"}:
        return "READY TO LAUNCH"
    if launch_state in {"HAND_RELEASE_DETECTED", "STABILIZE", "THROTTLE_RAMP", "AI_ACTIVE", "GATE_APPROACH"}:
        return "AI ACTIVE"
    if row.get("target_locked") is True or tracking_state == "LOCKED":
        return "LOCKED"
    if tracking_state == "CANDIDATE" or launch_state == "TARGET_CANDIDATE":
        return "CANDIDATE"
    return "NO TARGET"


def _button_contract(row: Mapping[str, Any], screen_state: str) -> tuple[str, bool]:
    launch_state = str(row.get("launch_state") or "")
    if screen_state == "MANUAL KILL":
        return "MANUAL_KILL_LATCHED", False
    if screen_state == "COMPLETE":
        return "MISSION_COMPLETE", False
    if launch_state == "AI_PREARM_READY":
        return "CONFIRM_AI_LAUNCH", True
    if launch_state == "BUTTON_CONFIRMED":
        return "WAIT_ARM_REQUEST", False
    if launch_state == "AI_ARM_REQUEST":
        return "WAIT_FC_ARM_ACK", False
    if launch_state == "ARMED_IDLE":
        return "WAIT_HAND_RELEASE", False
    if screen_state == "NO TARGET":
        return "REQUEST_TARGET_LOCK", True
    if screen_state in {"CANDIDATE", "DEGRADED", "REACQUIRE"}:
        return "WAIT_FOR_LOCK", False
    if screen_state in {"LOCKED", "RECOVERED"}:
        return "WAIT_READY_TO_LAUNCH", False
    if screen_state == "AI ACTIVE":
        return "MONITOR_AI_ACTIVE", False
    return "NO_ACTION", False


def _protocol_health(protocol_readiness: Mapping[str, Any] | None) -> dict[str, str]:
    if protocol_readiness is None:
        return {
            "status": "UNKNOWN",
            "detail": "protocol readiness report not provided",
        }
    summary = protocol_readiness.get("summary")
    if not isinstance(summary, Mapping):
        return {
            "status": "DEGRADED",
            "detail": "protocol readiness summary missing",
        }
    rejected = int(summary.get("rejected_command_count") or 0)
    stale = int(summary.get("stale_command_count") or 0)
    timeout = int(summary.get("timeout_count") or 0)
    heartbeat_lost = int(summary.get("heartbeat_lost_count") or 0)
    status = "PASS" if protocol_readiness.get("status") == "PASS" and rejected == stale == timeout == heartbeat_lost == 0 else "DEGRADED"
    return {
        "status": status,
        "detail": (
            f"transport={summary.get('transport_status')}; watchdog={summary.get('watchdog_status')}; "
            f"accepted={summary.get('accepted_command_count')}; rejected={rejected}; stale={stale}; "
            f"timeout={timeout}; heartbeat_lost={heartbeat_lost}"
        ),
    }


def _primary_status(screen_state: str) -> str:
    mapping = {
        "NO TARGET": "No racing gate lock",
        "CANDIDATE": "Candidate gate visible",
        "LOCKED": "Gate locked",
        "READY TO LAUNCH": "Ready for operator confirmation",
        "AI ACTIVE": "AI control active",
        "DEGRADED": "Lock confidence degraded",
        "REACQUIRE": "Predictive reacquire",
        "RECOVERED": "Gate recovered",
        "COMPLETE": "Gate pass complete",
        "MANUAL KILL": "Manual kill active",
    }
    return mapping[screen_state]


def _secondary_status(row: Mapping[str, Any], protocol_health: Mapping[str, str]) -> str:
    launch_state = str(row.get("launch_state") or "UNKNOWN")
    confidence = row.get("lock_confidence")
    confidence_text = "n/a" if confidence is None else f"{float(confidence):.2f}"
    return f"launch={launch_state}; confidence={confidence_text}; protocol={protocol_health['status']}"


def _warning(row: Mapping[str, Any], protocol_health: Mapping[str, str]) -> str:
    if protocol_health["status"] == "DEGRADED":
        return "PROTOCOL DEGRADED"
    if protocol_health["status"] == "UNKNOWN":
        return "PROTOCOL UNKNOWN"
    if row.get("manual_kill") is True:
        return "MANUAL KILL"
    if row.get("lock_tracking_state") in {"PREDICTIVE_TRACK", "REACQUIRE", "HARD_LOST"}:
        return "TARGET REACQUIRE"
    return ""


def _state_counts(frames: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {state: 0 for state in sorted(SCREEN_STATES)}
    for frame in frames:
        state = str(frame["screen_state"])
        counts[state] = counts.get(state, 0) + 1
    return counts


def _optional_str(row: Mapping[str, Any], key: str) -> str | None:
    value = row.get(key)
    return None if value is None else str(value)


def _optional_float(row: Mapping[str, Any], key: str) -> float | None:
    value = row.get(key)
    return None if value is None else float(value)


def _optional_bool(row: Mapping[str, Any], key: str) -> bool | None:
    value = row.get(key)
    return None if value is None else bool(value)


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
