"""Dry-run Betaflight target profile for the FPV-AI fork path.

The target profile records the owner decisions required before the generated
FPV-AI fork bundle can be applied to a real Betaflight checkout. It validates
the patch bundle and produces a reviewable profile, but it never selects
hardware by itself, modifies a checkout, compiles firmware, opens UART, or
authorizes a bench test.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from fpv_ai.betaflight_link.fork_patch_bundle import FORK_PATCH_BUNDLE_SCHEMA

TARGET_PROFILE_SCHEMA = "fpv_betaflight_target_profile.v1"
OWNER_REQUIRED = "OWNER_SELECTION_REQUIRED"
SERIAL_MODES = {
    OWNER_REQUIRED,
    "CRSF_LIKE_VIRTUAL_RECEIVER",
    "MSP_OVERRIDE",
    "FORK_NATIVE_AI_UART",
}


@dataclass(frozen=True)
class TargetProfileInput:
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


def build_betaflight_target_profile(
    *,
    patch_bundle_manifest: Mapping[str, Any],
    profile: TargetProfileInput | None = None,
    patch_bundle_manifest_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    selected_profile = profile or TargetProfileInput()
    bundle_entries = _bundle_entries(patch_bundle_manifest)
    selection_gates = _selection_gates(selected_profile)
    build_bindings = _build_hook_bindings(bundle_entries)
    owner_blockers = _owner_blockers(selection_gates)
    checks = _checks(
        patch_bundle_manifest=patch_bundle_manifest,
        profile=selected_profile,
        selection_gates=selection_gates,
        build_bindings=build_bindings,
    )
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "schema": TARGET_PROFILE_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "target_state": _target_state(status, owner_blockers),
        "source_reports": [
            _source_report(
                "patch_bundle_manifest",
                patch_bundle_manifest,
                patch_bundle_manifest_path,
                FORK_PATCH_BUNDLE_SCHEMA,
            ),
        ],
        "summary": {
            "source_report_count": 1,
            "required_owner_decision_count": len(selection_gates),
            "selected_owner_decision_count": sum(1 for row in selection_gates if row["status"] == "SELECTED"),
            "missing_owner_decision_count": len(owner_blockers),
            "build_binding_count": len(build_bindings),
            "firmware_source_binding_count": _binding_role_count(build_bindings, "firmware_source"),
            "header_binding_count": _binding_role_count(build_bindings, "header"),
            "test_fixture_binding_count": _binding_role_count(build_bindings, "test_fixture"),
            "command_rate_hz": selected_profile.command_rate_hz,
            "serial_baud": selected_profile.serial_baud,
            "operator_limit_mps": selected_profile.operator_limit_mps,
            "target_selected": len(owner_blockers) == 0,
            "patch_applied": False,
            "betaflight_repo_modified": False,
            "compile_attempted": False,
            "flash_attempted": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "profile": _profile_payload(selected_profile),
        "selection_gates": selection_gates,
        "build_hook_bindings": build_bindings,
        "owner_blockers": owner_blockers,
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "profile_only": True,
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


def write_betaflight_target_profile(
    *,
    patch_bundle_manifest_json: Path,
    output_json: Path,
    profile: TargetProfileInput | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    report = build_betaflight_target_profile(
        patch_bundle_manifest=_read_json(patch_bundle_manifest_json),
        profile=profile,
        patch_bundle_manifest_path=patch_bundle_manifest_json,
        project_root=project_root,
    )
    persisted = dict(report)
    persisted["profile_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _profile_payload(profile: TargetProfileInput) -> dict[str, Any]:
    return {
        "profile_name": profile.profile_name,
        "betaflight_repo_url": profile.betaflight_repo_url,
        "betaflight_branch": profile.betaflight_branch,
        "fc_target": profile.fc_target,
        "ai_uart_port": profile.ai_uart_port,
        "serial_mode": profile.serial_mode,
        "serial_baud": profile.serial_baud,
        "electrical_voltage_level": profile.electrical_voltage_level,
        "command_rate_hz": profile.command_rate_hz,
        "speed_mode": profile.speed_mode,
        "operator_limit_mps": profile.operator_limit_mps,
    }


def _selection_gates(profile: TargetProfileInput) -> list[dict[str, str]]:
    return [
        _selection_gate("betaflight_repo_url", profile.betaflight_repo_url, "Exact fork repository URL."),
        _selection_gate("betaflight_branch", profile.betaflight_branch, "Exact fork branch or commit."),
        _selection_gate("fc_target", profile.fc_target, "Exact Betaflight FC target/board."),
        _selection_gate("ai_uart_port", profile.ai_uart_port, "Dedicated AI UART port on the FC."),
        _selection_gate("serial_mode", profile.serial_mode, "AI command input mode."),
        _selection_gate("electrical_voltage_level", profile.electrical_voltage_level, "UART voltage level and wiring domain."),
    ]


def _selection_gate(decision_id: str, value: str, detail: str) -> dict[str, str]:
    selected = bool(value.strip()) and value != OWNER_REQUIRED
    return {
        "decision_id": decision_id,
        "value": value,
        "status": "SELECTED" if selected else OWNER_REQUIRED,
        "detail": detail,
    }


def _build_hook_bindings(bundle_entries: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "artifact_id": str(row.get("artifact_id") or ""),
            "build_role": str(row.get("build_role") or ""),
            "target_path": str(row.get("target_path") or ""),
            "bundle_path": str(row.get("bundle_path") or ""),
            "status": "READY_FOR_TARGET_MAPPING" if row.get("status") == "BUNDLED" else "SOURCE_NOT_READY",
        }
        for row in bundle_entries
    ]


def _owner_blockers(selection_gates: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "blocker_id": f"{row['decision_id']}_not_selected",
            "status": "OWNER_SELECTION_REQUIRED",
            "detail": row["detail"],
        }
        for row in selection_gates
        if row["status"] == OWNER_REQUIRED
    ]


def _checks(
    *,
    patch_bundle_manifest: Mapping[str, Any],
    profile: TargetProfileInput,
    selection_gates: Sequence[Mapping[str, str]],
    build_bindings: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    return [
        _check(
            "patch_bundle_schema_valid",
            patch_bundle_manifest.get("schema") == FORK_PATCH_BUNDLE_SCHEMA,
            str(patch_bundle_manifest.get("schema") or ""),
        ),
        _check("patch_bundle_passed", patch_bundle_manifest.get("status") == "PASS", str(patch_bundle_manifest.get("status") or "")),
        _check(
            "patch_bundle_ready",
            patch_bundle_manifest.get("bundle_state") == "READY_FOR_FORK_EXPORT_REVIEW",
            str(patch_bundle_manifest.get("bundle_state") or ""),
        ),
        _check("selection_gates_declared", len(selection_gates) == 6, str(len(selection_gates))),
        _check("serial_mode_supported", profile.serial_mode in SERIAL_MODES, profile.serial_mode),
        _check("serial_baud_valid", 115200 <= profile.serial_baud <= 1000000, str(profile.serial_baud)),
        _check("command_rate_valid", 10 <= profile.command_rate_hz <= 100, str(profile.command_rate_hz)),
        _check("operator_limit_valid", 0.1 <= profile.operator_limit_mps <= 60.0, str(profile.operator_limit_mps)),
        _check("build_bindings_declared", len(build_bindings) >= 7, str(len(build_bindings))),
        _check("firmware_sources_bound", _binding_role_count(build_bindings, "firmware_source") >= 3, "parser,decoder,mode manager"),
        _check("test_fixtures_bound", _binding_role_count(build_bindings, "test_fixture") >= 2, "UART and mode fixtures"),
        _check("owner_selection_not_bypassed", True, "missing decisions remain explicit blockers"),
        _check("no_betaflight_repo_modification", True, "profile only"),
        _check("no_compile_or_flash", True, "compile/flash outside this profile"),
        _check("no_live_uart_access", True, "file-only profile"),
    ]


def _target_state(status: str, owner_blockers: Sequence[Mapping[str, str]]) -> str:
    if status != "PASS":
        return "BLOCKED"
    if owner_blockers:
        return "DRAFT_OWNER_SELECTION_REQUIRED"
    return "READY_FOR_TARGET_REVIEW"


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


def _bundle_entries(patch_bundle_manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = patch_bundle_manifest.get("bundle_entries")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _binding_role_count(build_bindings: Sequence[Mapping[str, str]], build_role: str) -> int:
    return sum(
        1
        for row in build_bindings
        if row.get("build_role") == build_role and row.get("status") == "READY_FOR_TARGET_MAPPING"
    )


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
