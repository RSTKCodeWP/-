"""Betaflight FPV-AI mode state-machine contract.

This module translates the Raspberry Pi launch-state dry-run into the future
Betaflight fork mode contract. It defines when AI commands may be ignored,
prearmed, arm-requested, routed into a virtual receiver, or forced neutral.
It only reads/writes JSON artifacts and never touches a Betaflight checkout,
UART, motors, or hardware.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from fpv_ai.betaflight_link.integration_manifest import INTEGRATION_MANIFEST_SCHEMA
from fpv_ai.betaflight_link.parser_sim import PARSER_SIM_SCHEMA
from fpv_ai.runtime.launch_state import REPORT_SCHEMA as LAUNCH_STATE_SCHEMA

MODE_STATE_SCHEMA = "fpv_betaflight_ai_mode_state_machine.v1"

AI_PREARM_STATES = {"AI_PREARM_READY", "BUTTON_CONFIRMED"}
AI_ARM_REQUEST_STATES = {"AI_ARM_REQUEST"}
AI_CONTROL_STATES = {"THROTTLE_RAMP", "AI_ACTIVE", "GATE_APPROACH", "GATE_PASS"}
AI_WORKFLOW_STATES = AI_PREARM_STATES | AI_ARM_REQUEST_STATES | {
    "ARMED_IDLE",
    "HAND_RELEASE_DETECTED",
    "STABILIZE",
} | AI_CONTROL_STATES
RECOVERY_TARGET_STATES = {"DEGRADED", "PREDICTIVE_TRACK", "REACQUIRE", "HARD_LOST"}
LOCKED_TARGET_STATES = {"LOCKED", "RECOVERED"}

FORK_MODE_BY_LAUNCH_STATE = {
    "DISARMED": "AI_DISABLED",
    "TARGET_SEARCH": "AI_TARGET_SEARCH",
    "TARGET_CANDIDATE": "AI_TARGET_CANDIDATE",
    "TARGET_LOCKED": "AI_TARGET_LOCKED",
    "AI_PREARM_READY": "AI_PREARM",
    "BUTTON_CONFIRMED": "AI_PREARM",
    "AI_ARM_REQUEST": "AI_ARM_REQUEST",
    "ARMED_IDLE": "AI_ARMED_IDLE",
    "HAND_RELEASE_DETECTED": "AI_RELEASE_DETECTED",
    "STABILIZE": "AI_STABILIZE",
    "THROTTLE_RAMP": "AI_THROTTLE_RAMP",
    "AI_ACTIVE": "AI_CONTROL_ACTIVE",
    "GATE_APPROACH": "AI_CONTROL_ACTIVE",
    "GATE_PASS": "AI_GATE_PASS",
    "COMPLETE": "AI_COMPLETE",
    "MANUAL_KILL": "AI_KILL",
}


def build_betaflight_ai_mode_state_machine_contract(
    *,
    launch_report: Mapping[str, Any],
    integration_manifest: Mapping[str, Any],
    parser_sim_report: Mapping[str, Any],
    launch_report_path: Path | str | None = None,
    integration_manifest_path: Path | str | None = None,
    parser_sim_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    integration_ready = _integration_ready(integration_manifest)
    parser_ready = parser_sim_report.get("status") == "PASS"
    launch_events = _launch_events(launch_report)
    mode_events = [
        _mode_event(event, integration_ready=integration_ready, parser_ready=parser_ready)
        for event in launch_events
    ]
    checks = _checks(launch_report, integration_manifest, parser_sim_report, mode_events)
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "schema": MODE_STATE_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "contract_state": "READY_FOR_FORK_UNIT_TESTS" if status == "PASS" else "BLOCKED",
        "source_reports": [
            _source_report("launch_state", launch_report, launch_report_path, LAUNCH_STATE_SCHEMA),
            _source_report(
                "integration_manifest",
                integration_manifest,
                integration_manifest_path,
                INTEGRATION_MANIFEST_SCHEMA,
            ),
            _source_report("parser_sim", parser_sim_report, parser_sim_path, PARSER_SIM_SCHEMA),
        ],
        "summary": {
            "launch_event_count": len(mode_events),
            "ai_mode_event_count": sum(1 for row in mode_events if row["ai_mode"]),
            "ai_prearm_event_count": sum(1 for row in mode_events if row["ai_prearm"]),
            "ai_arm_request_count": sum(1 for row in mode_events if row["ai_arm_request"]),
            "ai_control_active_count": sum(1 for row in mode_events if row["ai_control_active"]),
            "ai_recovery_mode_count": sum(1 for row in mode_events if row["ai_recovery_mode"]),
            "ai_kill_count": sum(1 for row in mode_events if row["ai_kill"]),
            "neutral_output_count": sum(1 for row in mode_events if row["output_action"] == "NEUTRAL_HOLD"),
            "virtual_receiver_route_count": sum(
                1
                for row in mode_events
                if row["output_action"]
                in {"RAMP_LIMITED_VIRTUAL_RECEIVER", "ROUTE_TO_VIRTUAL_RECEIVER"}
            ),
            "control_gate_mismatch_count": len(_control_gate_mismatches(mode_events)),
            "throttle_low_arm_violation_count": len(_arm_throttle_violations(mode_events)),
            "target_lock_prearm_violation_count": len(_prearm_target_lock_violations(mode_events)),
            "integration_manifest_ready": integration_ready,
            "parser_sim_passed": parser_ready,
            "betaflight_repo_modified": False,
            "compile_attempted": False,
            "flash_attempted": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "mode_states": _mode_states(),
        "transition_rules": _transition_rules(),
        "mode_events": mode_events,
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "contract_only": True,
            "does_not_modify_betaflight_repo": True,
            "does_not_compile_or_flash_betaflight": True,
            "does_not_open_uart": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
            "does_not_command_motors_directly": True,
            "owner_defines_first_hardware_test": True,
        },
    }


def write_betaflight_ai_mode_state_machine_contract(
    *,
    launch_report_json: Path,
    integration_manifest_json: Path,
    parser_sim_json: Path,
    output_json: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    contract = build_betaflight_ai_mode_state_machine_contract(
        launch_report=_read_json(launch_report_json),
        integration_manifest=_read_json(integration_manifest_json),
        parser_sim_report=_read_json(parser_sim_json),
        launch_report_path=launch_report_json,
        integration_manifest_path=integration_manifest_json,
        parser_sim_path=parser_sim_json,
        project_root=project_root,
    )
    persisted = dict(contract)
    persisted["contract_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _launch_events(launch_report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = launch_report.get("events")
    if not isinstance(rows, list) or not rows:
        raise ValueError("launch report must contain a non-empty events list")
    if not all(isinstance(row, Mapping) for row in rows):
        raise ValueError("launch report events must be objects")
    return sorted(rows, key=lambda row: int(row.get("frame_index") or 0))


def _mode_event(
    event: Mapping[str, Any],
    *,
    integration_ready: bool,
    parser_ready: bool,
) -> dict[str, Any]:
    launch_state = str(event.get("launch_state") or "")
    target_state = str(event.get("target_state") or "NO_TARGET")
    manual_kill = event.get("manual_kill") is True
    watchdog_ok = event.get("watchdog_ok") is True
    active_sources_ready = integration_ready and parser_ready
    fork_ai_control_allowed = (
        launch_state in AI_CONTROL_STATES
        and active_sources_ready
        and watchdog_ok
        and not manual_kill
    )
    arm_request = launch_state in AI_ARM_REQUEST_STATES
    ai_prearm = launch_state in AI_PREARM_STATES
    ai_recovery_mode = launch_state in AI_CONTROL_STATES and target_state in RECOVERY_TARGET_STATES
    command_acceptance, output_action, reason = _command_decision(
        launch_state=launch_state,
        fork_ai_control_allowed=fork_ai_control_allowed,
        arm_request=arm_request,
        manual_kill=manual_kill,
        watchdog_ok=watchdog_ok,
        active_sources_ready=active_sources_ready,
    )
    return {
        "schema": "fpv_betaflight_ai_mode_event.v1",
        "frame_index": int(event.get("frame_index") or 0),
        "timestamp_ms": int(event.get("timestamp_ms") or 0),
        "launch_state": launch_state,
        "target_state": target_state,
        "fork_mode_state": FORK_MODE_BY_LAUNCH_STATE.get(launch_state, "AI_UNKNOWN"),
        "ai_mode": launch_state in AI_WORKFLOW_STATES,
        "ai_prearm": ai_prearm,
        "ai_arm_request": arm_request,
        "ai_control_active": fork_ai_control_allowed,
        "ai_recovery_mode": ai_recovery_mode,
        "ai_kill": manual_kill,
        "manual_override": manual_kill,
        "watchdog_ok": watchdog_ok,
        "throttle_low": event.get("throttle_low") is True,
        "target_locked": event.get("target_locked") is True or target_state in LOCKED_TARGET_STATES,
        "fc_armed": event.get("fc_armed") is True,
        "hand_release_detected": event.get("hand_release_detected") is True,
        "source_ai_control_allowed": event.get("ai_control_allowed") is True,
        "fork_ai_control_allowed": fork_ai_control_allowed,
        "command_acceptance": command_acceptance,
        "output_action": output_action,
        "reason": reason,
        "sequence_guard_required": launch_state in AI_CONTROL_STATES,
        "stale_timeout_required": launch_state in AI_CONTROL_STATES,
        "direct_motor_output_allowed": False,
        "actual_uart_opened": False,
        "actual_command_published": False,
    }


def _command_decision(
    *,
    launch_state: str,
    fork_ai_control_allowed: bool,
    arm_request: bool,
    manual_kill: bool,
    watchdog_ok: bool,
    active_sources_ready: bool,
) -> tuple[str, str, str]:
    if manual_kill:
        return "KILL_LATCHED", "NEUTRAL_HOLD", "manual kill overrides AI"
    if not watchdog_ok:
        return "REJECT_WATCHDOG", "NEUTRAL_HOLD", "watchdog rejected AI command"
    if not active_sources_ready:
        return "REJECT_SOURCE_NOT_READY", "NEUTRAL_HOLD", "source reports are not ready"
    if arm_request:
        return "REQUEST_ARM", "NEUTRAL_HOLD", "request FC arm with throttle-low discipline"
    if fork_ai_control_allowed:
        if launch_state == "THROTTLE_RAMP":
            return "ACCEPT_AI_COMMAND", "RAMP_LIMITED_VIRTUAL_RECEIVER", "ramp-limited AI control"
        return "ACCEPT_AI_COMMAND", "ROUTE_TO_VIRTUAL_RECEIVER", "AI control active"
    return "IGNORE_NEUTRAL", "NEUTRAL_HOLD", "AI control not active"


def _mode_states() -> list[dict[str, Any]]:
    return [
        _mode_state("AI_DISABLED", "no AI workflow active", False, False),
        _mode_state("AI_TARGET_SEARCH", "target search/lock only, no FC control", False, False),
        _mode_state("AI_TARGET_CANDIDATE", "candidate target, no FC control", False, False),
        _mode_state("AI_TARGET_LOCKED", "confirmed target lock, no FC control", False, False),
        _mode_state("AI_PREARM", "operator-ready prearm state, no FC control", True, False),
        _mode_state("AI_ARM_REQUEST", "single arm request gate, no virtual receiver output", True, False),
        _mode_state("AI_ARMED_IDLE", "FC armed, waiting for hand release", True, False),
        _mode_state("AI_RELEASE_DETECTED", "hand release observed, no command route yet", True, False),
        _mode_state("AI_STABILIZE", "post-release stabilization, no command route yet", True, False),
        _mode_state("AI_THROTTLE_RAMP", "ramp-limited virtual receiver output", True, True),
        _mode_state("AI_CONTROL_ACTIVE", "AI virtual receiver output active", True, True),
        _mode_state("AI_GATE_PASS", "gate pass marking while AI control is still allowed", True, True),
        _mode_state("AI_COMPLETE", "mission complete, return to neutral/owner review", False, False),
        _mode_state("AI_KILL", "manual kill latched, force neutral", False, False),
    ]


def _mode_state(state_id: str, detail: str, ai_mode: bool, control_allowed: bool) -> dict[str, Any]:
    return {
        "state_id": state_id,
        "detail": detail,
        "ai_mode": ai_mode,
        "control_allowed": control_allowed,
        "direct_motor_output_allowed": False,
    }


def _transition_rules() -> list[dict[str, str]]:
    return [
        _rule("target_lock_before_prearm", "AI_PREARM requires a confirmed lock or RECOVERED target state."),
        _rule("operator_button_before_arm_request", "BUTTON_CONFIRMED must precede AI_ARM_REQUEST."),
        _rule("throttle_low_before_arm_request", "AI_ARM_REQUEST is valid only while throttle_low is true."),
        _rule("fc_ack_before_armed_idle", "ARMED_IDLE requires a flight-controller arm acknowledgement."),
        _rule("hand_release_before_stabilize", "STABILIZE follows HAND_RELEASE_DETECTED."),
        _rule("throttle_ramp_before_active", "AI_CONTROL_ACTIVE must follow THROTTLE_RAMP."),
        _rule("control_requires_parser_and_manifest", "AI commands route only if source contracts are PASS."),
        _rule("watchdog_blocks_control", "watchdog_ok=false forces NEUTRAL_HOLD."),
        _rule("manual_kill_forces_neutral", "manual kill latches AI_KILL and overrides AI control."),
        _rule("no_direct_motor_output", "AI mode output maps to virtual receiver, never direct motors."),
    ]


def _checks(
    launch_report: Mapping[str, Any],
    integration_manifest: Mapping[str, Any],
    parser_sim_report: Mapping[str, Any],
    mode_events: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    return [
        _check(
            "launch_report_schema_valid",
            launch_report.get("schema") == LAUNCH_STATE_SCHEMA,
            str(launch_report.get("schema") or ""),
        ),
        _check("launch_report_passed", launch_report.get("status") == "PASS", str(launch_report.get("status") or "")),
        _check(
            "integration_manifest_schema_valid",
            integration_manifest.get("schema") == INTEGRATION_MANIFEST_SCHEMA,
            str(integration_manifest.get("schema") or ""),
        ),
        _check(
            "integration_manifest_ready",
            _integration_ready(integration_manifest),
            str(integration_manifest.get("integration_state") or ""),
        ),
        _check("parser_sim_schema_valid", parser_sim_report.get("schema") == PARSER_SIM_SCHEMA, str(parser_sim_report.get("schema") or "")),
        _check("parser_sim_passed", parser_sim_report.get("status") == "PASS", str(parser_sim_report.get("status") or "")),
        _check("mode_events_present", bool(mode_events), f"events={len(mode_events)}"),
        _check(
            "launch_and_fork_control_gate_match",
            not _control_gate_mismatches(mode_events),
            ",".join(_control_gate_mismatches(mode_events)),
        ),
        _check(
            "no_ai_control_before_throttle_ramp",
            not _control_before_ramp_violations(mode_events),
            ",".join(_control_before_ramp_violations(mode_events)),
        ),
        _check(
            "arm_request_requires_throttle_low",
            not _arm_throttle_violations(mode_events),
            ",".join(_arm_throttle_violations(mode_events)),
        ),
        _check(
            "prearm_requires_target_lock",
            not _prearm_target_lock_violations(mode_events),
            ",".join(_prearm_target_lock_violations(mode_events)),
        ),
        _check("complete_returns_neutral", _complete_returns_neutral(mode_events), "COMPLETE rows neutral"),
        _check("no_direct_motor_output", all(row["direct_motor_output_allowed"] is False for row in mode_events), "virtual receiver only"),
        _check("no_live_uart_access", all(row["actual_uart_opened"] is False for row in mode_events), "file-only contract"),
        _check(
            "no_flight_commands_published",
            all(row["actual_command_published"] is False for row in mode_events),
            "dry-run only",
        ),
    ]


def _source_report(
    report_id: str,
    payload: Mapping[str, Any],
    path: Path | str | None,
    expected_schema: str,
) -> dict[str, str]:
    path_obj = Path(path) if path is not None else None
    return {
        "report_id": report_id,
        "path": "" if path is None else str(path),
        "schema": str(payload.get("schema") or ""),
        "expected_schema": expected_schema,
        "status": str(payload.get("status") or ""),
        "sha256": _sha256(path_obj) if path_obj is not None and path_obj.exists() else "",
    }


def _integration_ready(integration_manifest: Mapping[str, Any]) -> bool:
    return (
        integration_manifest.get("status") == "PASS"
        and integration_manifest.get("integration_state") == "READY_FOR_FORK_REVIEW"
    )


def _control_gate_mismatches(mode_events: Sequence[Mapping[str, Any]]) -> list[str]:
    return [
        str(row["frame_index"])
        for row in mode_events
        if row["source_ai_control_allowed"] != row["fork_ai_control_allowed"]
    ]


def _control_before_ramp_violations(mode_events: Sequence[Mapping[str, Any]]) -> list[str]:
    return [
        str(row["frame_index"])
        for row in mode_events
        if row["fork_ai_control_allowed"] and row["launch_state"] not in AI_CONTROL_STATES
    ]


def _arm_throttle_violations(mode_events: Sequence[Mapping[str, Any]]) -> list[str]:
    return [
        str(row["frame_index"])
        for row in mode_events
        if row["ai_arm_request"] and not row["throttle_low"]
    ]


def _prearm_target_lock_violations(mode_events: Sequence[Mapping[str, Any]]) -> list[str]:
    return [
        str(row["frame_index"])
        for row in mode_events
        if (row["ai_prearm"] or row["ai_arm_request"]) and not row["target_locked"]
    ]


def _complete_returns_neutral(mode_events: Sequence[Mapping[str, Any]]) -> bool:
    return all(
        row["output_action"] == "NEUTRAL_HOLD"
        for row in mode_events
        if row["launch_state"] == "COMPLETE"
    )


def _rule(rule_id: str, detail: str) -> dict[str, str]:
    return {
        "rule_id": rule_id,
        "detail": detail,
        "status": "REQUIRED_FOR_FORK",
    }


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
