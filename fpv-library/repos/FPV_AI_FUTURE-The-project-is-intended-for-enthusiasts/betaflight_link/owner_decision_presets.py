"""Dry-run owner decision preset catalog for Betaflight FPV-AI target selection.

The catalog provides repeatable presets for filling owner decision intake. It
does not select real hardware automatically and does not authorize hardware
tests. Simulation presets are explicitly marked as not valid for real hardware.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fpv_ai.betaflight_link.owner_decision_intake import (
    OWNER_REQUIRED,
    SUPPORTED_SERIAL_MODES,
    OwnerDecisionInput,
)

OWNER_DECISION_PRESETS_SCHEMA = "fpv_betaflight_owner_decision_presets.v1"
DEFAULT_PRESET_ID = "manual_owner_selection_required"


@dataclass(frozen=True)
class OwnerDecisionPreset:
    preset_id: str
    title: str
    role: str
    detail: str
    decisions: OwnerDecisionInput
    simulation_only: bool = False
    owner_authorized_for_real_hardware: bool = False


PRESETS = (
    OwnerDecisionPreset(
        preset_id=DEFAULT_PRESET_ID,
        title="Manual owner selection required",
        role="manual_owner_selection",
        detail="Leaves repo, branch, FC target, UART, serial mode, and voltage for explicit owner input.",
        decisions=OwnerDecisionInput(),
    ),
    OwnerDecisionPreset(
        preset_id="fork_native_ai_uart_template",
        title="Fork-native AI UART template",
        role="owner_fill_template",
        detail="Keeps hardware fields empty while preselecting the intended native AI UART command mode.",
        decisions=OwnerDecisionInput(
            profile_name="fork-native-ai-uart-template",
            serial_mode="FORK_NATIVE_AI_UART",
        ),
    ),
    OwnerDecisionPreset(
        preset_id="simulated_fork_review_profile",
        title="Simulated fork review profile",
        role="synthetic_pipeline_review",
        detail="Synthetic profile for exercising the dry-run pipeline. Not valid for real hardware.",
        decisions=OwnerDecisionInput(
            profile_name="simulated-fork-review",
            betaflight_repo_url="https://example.invalid/betaflight-fork.git",
            betaflight_branch="fpv-ai-gate-lock",
            fc_target="SIMULATED_FC_TARGET",
            ai_uart_port="SIM_UART",
            serial_mode="FORK_NATIVE_AI_UART",
            serial_baud=420000,
            electrical_voltage_level="SIMULATED_3V3_TTL",
            command_rate_hz=20,
            speed_mode="RACE_SPEED",
            operator_limit_mps=5.0,
        ),
        simulation_only=True,
    ),
)


def build_betaflight_owner_decision_presets(*, project_root: Path | None = None) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    preset_rows = [_preset_entry(preset) for preset in PRESETS]
    checks = _checks(preset_rows)
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "schema": OWNER_DECISION_PRESETS_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "catalog_state": "READY_FOR_OWNER_SELECTION" if status == "PASS" else "BLOCKED",
        "source_reports": [],
        "summary": {
            "source_report_count": 0,
            "preset_count": len(preset_rows),
            "default_preset_id": DEFAULT_PRESET_ID,
            "target_ready_preset_count": sum(1 for row in preset_rows if row["target_profile_ready"]),
            "simulation_only_preset_count": sum(1 for row in preset_rows if row["simulation_only"]),
            "real_hardware_authorized_preset_count": sum(
                1 for row in preset_rows if row["owner_authorized_for_real_hardware"]
            ),
            "patch_applied": False,
            "betaflight_repo_modified": False,
            "compile_attempted": False,
            "flash_attempted": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "presets": preset_rows,
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "catalog_only": True,
            "does_not_select_hardware_automatically": True,
            "does_not_authorize_real_hardware_presets": True,
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


def write_betaflight_owner_decision_presets(
    *,
    output_json: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    report = build_betaflight_owner_decision_presets(project_root=project_root)
    persisted = dict(report)
    persisted["catalog_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def owner_decision_input_from_preset(catalog: Mapping[str, Any], preset_id: str) -> dict[str, Any]:
    if catalog.get("schema") != OWNER_DECISION_PRESETS_SCHEMA:
        raise ValueError(f"expected {OWNER_DECISION_PRESETS_SCHEMA}")
    presets = catalog.get("presets")
    if not isinstance(presets, list):
        raise ValueError("preset catalog lacks presets")
    for row in presets:
        if isinstance(row, Mapping) and row.get("preset_id") == preset_id:
            payload = row.get("target_profile_input")
            if not isinstance(payload, Mapping):
                raise ValueError(f"preset lacks target_profile_input: {preset_id}")
            return _target_profile_input_from_mapping(payload)
    raise ValueError(f"unknown owner decision preset: {preset_id}")


def built_in_owner_decision_input_from_preset(preset_id: str) -> dict[str, Any]:
    return owner_decision_input_from_preset(build_betaflight_owner_decision_presets(), preset_id)


def _preset_entry(preset: OwnerDecisionPreset) -> dict[str, Any]:
    decision_rows = _decision_rows(preset.decisions)
    missing_count = sum(1 for row in decision_rows if row["status"] == OWNER_REQUIRED)
    return {
        "preset_id": preset.preset_id,
        "title": preset.title,
        "role": preset.role,
        "detail": preset.detail,
        "simulation_only": preset.simulation_only,
        "owner_authorized_for_real_hardware": preset.owner_authorized_for_real_hardware,
        "target_profile_ready": missing_count == 0,
        "missing_owner_decision_count": missing_count,
        "selected_owner_decision_count": len(decision_rows) - missing_count,
        "decisions": decision_rows,
        "target_profile_input": _target_profile_input_payload(preset.decisions),
        "status": "AVAILABLE",
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


def _target_profile_input_from_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
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


def _checks(preset_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    preset_ids = [str(row["preset_id"]) for row in preset_rows]
    real_hardware_authorized = [
        str(row["preset_id"])
        for row in preset_rows
        if row["owner_authorized_for_real_hardware"] is True
    ]
    unsupported_serial_modes = [
        str(row["preset_id"])
        for row in preset_rows
        if str(row["target_profile_input"]["serial_mode"]) not in SUPPORTED_SERIAL_MODES
    ]
    return [
        _check("presets_declared", len(preset_rows) >= 3, str(len(preset_rows))),
        _check("default_preset_present", DEFAULT_PRESET_ID in preset_ids, DEFAULT_PRESET_ID),
        _check("preset_ids_unique", len(preset_ids) == len(set(preset_ids)), ",".join(preset_ids)),
        _check("serial_modes_supported", not unsupported_serial_modes, ",".join(unsupported_serial_modes)),
        _check("no_real_hardware_authorized_presets", not real_hardware_authorized, ",".join(real_hardware_authorized)),
        _check(
            "simulation_presets_not_hardware_authorized",
            all(
                not row["owner_authorized_for_real_hardware"]
                for row in preset_rows
                if row["simulation_only"]
            ),
            "simulation presets stay dry-run only",
        ),
        _check("no_betaflight_repo_modification", True, "catalog only"),
        _check("no_compile_or_flash", True, "compile/flash outside this catalog"),
        _check("no_live_uart_access", True, "file-only catalog"),
    ]


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
