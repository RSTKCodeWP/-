"""Owner decision intake for Betaflight FPV-AI target selection.

This dry-run intake records the decisions the project owner must provide before
the generated FPV-AI fork bundle can be mapped to a real Betaflight target. It
does not select hardware automatically, modify a checkout, compile firmware,
flash hardware, open UART, or authorize any hardware work.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

OWNER_DECISION_INTAKE_SCHEMA = "fpv_betaflight_owner_decision_intake.v1"
OWNER_REQUIRED = "OWNER_SELECTION_REQUIRED"
SUPPORTED_SERIAL_MODES = {
    OWNER_REQUIRED,
    "CRSF_LIKE_VIRTUAL_RECEIVER",
    "MSP_OVERRIDE",
    "FORK_NATIVE_AI_UART",
}


@dataclass(frozen=True)
class OwnerDecisionInput:
    profile_name: str = "owner-selection-required"
    betaflight_repo_url: str = ""
    betaflight_branch: str = ""
    fc_target: str = ""
    ai_uart_port: str = ""
    serial_mode: str = OWNER_REQUIRED
    serial_baud: int = 420000
    electrical_voltage_level: str = ""
    command_rate_hz: int = 20
    speed_mode: str = "RACE_SPEED"
    operator_limit_mps: float = 5.0


def build_betaflight_owner_decision_intake(
    *,
    decisions: OwnerDecisionInput | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    selected_decisions = decisions or OwnerDecisionInput()
    decision_rows = _decision_rows(selected_decisions)
    checks = _checks(selected_decisions, decision_rows)
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    missing_count = sum(1 for row in decision_rows if row["status"] == OWNER_REQUIRED)
    return {
        "schema": OWNER_DECISION_INTAKE_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "intake_state": _intake_state(status, missing_count),
        "source_reports": [],
        "summary": {
            "source_report_count": 0,
            "required_owner_decision_count": len(decision_rows),
            "selected_owner_decision_count": len(decision_rows) - missing_count,
            "missing_owner_decision_count": missing_count,
            "target_profile_ready": missing_count == 0,
            "serial_baud": selected_decisions.serial_baud,
            "command_rate_hz": selected_decisions.command_rate_hz,
            "operator_limit_mps": selected_decisions.operator_limit_mps,
            "patch_applied": False,
            "betaflight_repo_modified": False,
            "compile_attempted": False,
            "flash_attempted": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "decisions": decision_rows,
        "target_profile_input": _target_profile_input_payload(selected_decisions),
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "owner_input_only": True,
            "does_not_select_hardware_automatically": True,
            "does_not_modify_betaflight_repo": True,
            "does_not_apply_patch": True,
            "does_not_compile_or_flash_betaflight": True,
            "does_not_execute_c_tests": True,
            "does_not_open_uart": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
            "does_not_command_motors_directly": True,
        },
    }


def write_betaflight_owner_decision_intake(
    *,
    output_json: Path,
    decisions: OwnerDecisionInput | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    report = build_betaflight_owner_decision_intake(
        decisions=decisions,
        project_root=project_root,
    )
    persisted = dict(report)
    persisted["intake_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def target_profile_input_from_owner_decision_intake(intake: Mapping[str, Any]) -> dict[str, Any]:
    if intake.get("schema") != OWNER_DECISION_INTAKE_SCHEMA:
        raise ValueError(f"expected {OWNER_DECISION_INTAKE_SCHEMA}")
    payload = intake.get("target_profile_input")
    if not isinstance(payload, Mapping):
        raise ValueError("owner decision intake lacks target_profile_input")
    return {
        "profile_name": str(payload.get("profile_name") or "owner-selection-required"),
        "betaflight_repo_url": str(payload.get("betaflight_repo_url") or ""),
        "betaflight_branch": str(payload.get("betaflight_branch") or ""),
        "fc_target": str(payload.get("fc_target") or ""),
        "ai_uart_port": str(payload.get("ai_uart_port") or ""),
        "serial_mode": str(payload.get("serial_mode") or OWNER_REQUIRED),
        "serial_baud": int(payload.get("serial_baud") or 420000),
        "electrical_voltage_level": str(payload.get("electrical_voltage_level") or ""),
        "command_rate_hz": int(payload.get("command_rate_hz") or 20),
        "speed_mode": str(payload.get("speed_mode") or "RACE_SPEED"),
        "operator_limit_mps": float(payload.get("operator_limit_mps") or 5.0),
    }


def _decision_rows(decisions: OwnerDecisionInput) -> list[dict[str, str]]:
    return [
        _decision("betaflight_repo_url", decisions.betaflight_repo_url, "Exact fork repository URL."),
        _decision("betaflight_branch", decisions.betaflight_branch, "Exact fork branch or commit."),
        _decision("fc_target", decisions.fc_target, "Exact Betaflight FC target/board."),
        _decision("ai_uart_port", decisions.ai_uart_port, "Dedicated AI UART port on the FC."),
        _decision("serial_mode", decisions.serial_mode, "AI command input mode."),
        _decision("electrical_voltage_level", decisions.electrical_voltage_level, "UART voltage level and wiring domain."),
    ]


def _decision(decision_id: str, value: str, detail: str) -> dict[str, str]:
    selected = bool(value.strip()) and value != OWNER_REQUIRED
    return {
        "decision_id": decision_id,
        "value": value,
        "status": "SELECTED" if selected else OWNER_REQUIRED,
        "detail": detail,
    }


def _target_profile_input_payload(decisions: OwnerDecisionInput) -> dict[str, Any]:
    return {
        "profile_name": decisions.profile_name,
        "betaflight_repo_url": decisions.betaflight_repo_url,
        "betaflight_branch": decisions.betaflight_branch,
        "fc_target": decisions.fc_target,
        "ai_uart_port": decisions.ai_uart_port,
        "serial_mode": decisions.serial_mode,
        "serial_baud": decisions.serial_baud,
        "electrical_voltage_level": decisions.electrical_voltage_level,
        "command_rate_hz": decisions.command_rate_hz,
        "speed_mode": decisions.speed_mode,
        "operator_limit_mps": decisions.operator_limit_mps,
    }


def _checks(decisions: OwnerDecisionInput, decision_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    missing = [row["decision_id"] for row in decision_rows if row["status"] == OWNER_REQUIRED]
    return [
        _check("required_decisions_declared", len(decision_rows) == 6, str(len(decision_rows))),
        _check("missing_decisions_recorded", True, ",".join(missing)),
        _check("serial_mode_supported", decisions.serial_mode in SUPPORTED_SERIAL_MODES, decisions.serial_mode),
        _check("serial_baud_valid", 115200 <= decisions.serial_baud <= 1000000, str(decisions.serial_baud)),
        _check("command_rate_valid", 10 <= decisions.command_rate_hz <= 100, str(decisions.command_rate_hz)),
        _check("operator_limit_valid", 0.1 <= decisions.operator_limit_mps <= 60.0, str(decisions.operator_limit_mps)),
        _check("no_hardware_auto_selection", True, "owner input required"),
        _check("no_betaflight_repo_modification", True, "intake only"),
        _check("no_compile_or_flash", True, "compile/flash outside this intake"),
        _check("no_live_uart_access", True, "file-only intake"),
    ]


def _intake_state(status: str, missing_count: int) -> str:
    if status != "PASS":
        return "BLOCKED"
    if missing_count:
        return "DRAFT_OWNER_INPUT_REQUIRED"
    return "READY_FOR_TARGET_PROFILE"


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
