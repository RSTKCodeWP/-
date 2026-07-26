"""Bridge an open-parameter owner response to Betaflight intake.

This report proves the file-only transformation from the owner-response review
shape into the Betaflight owner-decision intake shape. It deliberately does not
write the canonical intake, regenerate pipeline stage reports, modify a
Betaflight checkout, or authorize hardware tests.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fpv_ai.betaflight_link.owner_decision_intake import (
    OWNER_DECISION_INTAKE_SCHEMA,
    OwnerDecisionInput,
    build_betaflight_owner_decision_intake,
)
from fpv_ai.evidence.open_parameters_owner_response import OPEN_PARAMETERS_OWNER_RESPONSE_SCHEMA

OPEN_PARAMETERS_OWNER_RESPONSE_INTAKE_BRIDGE_SCHEMA = (
    "fpv_mvp_open_parameters_owner_response_intake_bridge.v1"
)


def build_open_parameters_owner_response_intake_bridge(
    *,
    open_parameters_owner_response: Mapping[str, Any],
    open_parameters_owner_response_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    owner_decision_input = _owner_decision_input(open_parameters_owner_response)
    intake_candidate = build_betaflight_owner_decision_intake(
        decisions=OwnerDecisionInput(**owner_decision_input),
        project_root=root,
    )
    checks = _checks(
        open_parameters_owner_response=open_parameters_owner_response,
        intake_candidate=intake_candidate,
    )
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "schema": OPEN_PARAMETERS_OWNER_RESPONSE_INTAKE_BRIDGE_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "bridge_state": _bridge_state(status, open_parameters_owner_response, intake_candidate),
        "source_reports": [
            _source_report(
                "open_parameters_owner_response",
                open_parameters_owner_response,
                open_parameters_owner_response_path,
                OPEN_PARAMETERS_OWNER_RESPONSE_SCHEMA,
            ),
        ],
        "summary": _summary_payload(open_parameters_owner_response, intake_candidate),
        "owner_decision_input_preview": owner_decision_input,
        "owner_decision_intake_candidate": _intake_candidate_payload(intake_candidate),
        "missing_target_decisions": _missing_target_decisions(open_parameters_owner_response),
        "missing_non_target_parameters": _missing_non_target_parameters(open_parameters_owner_response),
        "next_actions": _next_actions(status, open_parameters_owner_response),
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "bridge_report_only": True,
            "does_not_select_hardware_automatically": True,
            "does_not_write_owner_decision_intake": True,
            "does_not_regenerate_pipeline": True,
            "does_not_write_stage_reports": True,
            "does_not_modify_betaflight_repo": True,
            "does_not_apply_patch": True,
            "does_not_compile_or_flash_betaflight": True,
            "does_not_execute_c_tests": True,
            "does_not_open_uart": True,
            "does_not_authorize_hardware_test": True,
            "does_not_authorize_no_prop_bench": True,
            "does_not_publish_flight_commands": True,
        },
    }


def write_open_parameters_owner_response_intake_bridge(
    *,
    open_parameters_owner_response_json: Path,
    output_json: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    report = build_open_parameters_owner_response_intake_bridge(
        open_parameters_owner_response=_read_json(open_parameters_owner_response_json),
        open_parameters_owner_response_path=open_parameters_owner_response_json,
        project_root=project_root,
    )
    persisted = dict(report)
    persisted["bridge_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _summary_payload(
    open_parameters_owner_response: Mapping[str, Any],
    intake_candidate: Mapping[str, Any],
) -> dict[str, Any]:
    response_summary = _summary(open_parameters_owner_response)
    intake_summary = _summary(intake_candidate)
    return {
        "source_report_count": 1,
        "owner_response_state": str(open_parameters_owner_response.get("response_state") or ""),
        "owner_decision_input_ready": response_summary.get("owner_decision_input_ready") is True,
        "all_owner_parameters_answered": response_summary.get("all_owner_parameters_answered") is True,
        "pipeline_regeneration_ready": response_summary.get("pipeline_regeneration_ready") is True,
        "target_missing_count": int(response_summary.get("target_missing_count") or 0),
        "non_target_missing_count": int(response_summary.get("non_target_missing_count") or 0),
        "intake_candidate_built": True,
        "intake_candidate_state": str(intake_candidate.get("intake_state") or ""),
        "selected_owner_decision_count": int(intake_summary.get("selected_owner_decision_count") or 0),
        "missing_owner_decision_count": int(intake_summary.get("missing_owner_decision_count") or 0),
        "target_profile_ready": intake_summary.get("target_profile_ready") is True,
        "intake_write_ready": response_summary.get("owner_decision_input_ready") is True
        and intake_summary.get("target_profile_ready") is True,
        "canonical_intake_written": False,
        "pipeline_regenerated": False,
        "hardware_test_authorized": False,
        "no_prop_bench_authorized": False,
        "betaflight_repo_modified": False,
        "compile_attempted": False,
        "flash_attempted": False,
        "uart_opened": False,
        "flight_commands_published": False,
    }


def _intake_candidate_payload(intake_candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": str(intake_candidate.get("schema") or ""),
        "status": str(intake_candidate.get("status") or ""),
        "intake_state": str(intake_candidate.get("intake_state") or ""),
        "summary": dict(_summary(intake_candidate)),
        "target_profile_input": dict(_mapping(intake_candidate.get("target_profile_input"))),
        "decisions": [
            {
                "decision_id": str(row.get("decision_id") or ""),
                "value": str(row.get("value") or ""),
                "status": str(row.get("status") or ""),
                "detail": str(row.get("detail") or ""),
            }
            for row in intake_candidate.get("decisions", [])
            if isinstance(row, Mapping)
        ],
    }


def _checks(
    *,
    open_parameters_owner_response: Mapping[str, Any],
    intake_candidate: Mapping[str, Any],
) -> list[dict[str, str]]:
    response_summary = _summary(open_parameters_owner_response)
    intake_summary = _summary(intake_candidate)
    return [
        _check(
            "open_parameters_owner_response_schema_valid",
            open_parameters_owner_response.get("schema") == OPEN_PARAMETERS_OWNER_RESPONSE_SCHEMA,
            str(open_parameters_owner_response.get("schema") or ""),
        ),
        _check(
            "open_parameters_owner_response_passed",
            open_parameters_owner_response.get("status") == "PASS",
            str(open_parameters_owner_response.get("status") or ""),
        ),
        _check(
            "owner_decision_input_preview_declared",
            bool(_mapping(open_parameters_owner_response.get("owner_decision_input_preview"))),
            "owner_decision_input_preview",
        ),
        _check(
            "intake_candidate_schema_valid",
            intake_candidate.get("schema") == OWNER_DECISION_INTAKE_SCHEMA,
            str(intake_candidate.get("schema") or ""),
        ),
        _check(
            "intake_candidate_passed",
            intake_candidate.get("status") == "PASS",
            str(intake_candidate.get("status") or ""),
        ),
        _check(
            "target_missing_count_matches_intake",
            int(response_summary.get("target_missing_count") or 0)
            == int(intake_summary.get("missing_owner_decision_count") or 0),
            f"{response_summary.get('target_missing_count')} vs "
            f"{intake_summary.get('missing_owner_decision_count')}",
        ),
        _check(
            "intake_write_readiness_consistent",
            (response_summary.get("owner_decision_input_ready") is True)
            == (intake_summary.get("target_profile_ready") is True),
            str(response_summary.get("owner_decision_input_ready")),
        ),
        _check("no_owner_intake_write", True, "bridge does not write canonical intake"),
        _check("no_pipeline_regeneration", True, "bridge does not regenerate pipeline"),
        _check("no_betaflight_repo_modification", True, "bridge report only"),
        _check("no_compile_or_flash", True, "compile/flash outside this bridge"),
        _check("no_live_uart_access", True, "file-only bridge"),
    ]


def _bridge_state(
    status: str,
    open_parameters_owner_response: Mapping[str, Any],
    intake_candidate: Mapping[str, Any],
) -> str:
    if status != "PASS":
        return "BLOCKED"
    response_summary = _summary(open_parameters_owner_response)
    intake_summary = _summary(intake_candidate)
    if response_summary.get("owner_decision_input_ready") is not True:
        return "OWNER_RESPONSE_INCOMPLETE"
    if intake_summary.get("target_profile_ready") is not True:
        return "OWNER_RESPONSE_INCOMPLETE"
    if response_summary.get("all_owner_parameters_answered") is not True:
        return "READY_FOR_INTAKE_DRAFT"
    return "READY_FOR_PIPELINE_REGENERATION"


def _next_actions(
    status: str,
    open_parameters_owner_response: Mapping[str, Any],
) -> list[dict[str, str]]:
    if status != "PASS":
        return [_action("fix_owner_response", "Fix owner response validation before bridge use.", "BLOCKED")]
    response_summary = _summary(open_parameters_owner_response)
    if response_summary.get("owner_decision_input_ready") is not True:
        return [
            _action("fill_target_decisions", "Fill missing Betaflight target decisions.", "OWNER_REQUIRED"),
            _action("rerun_owner_response_review", "Re-run owner response review after target values exist.", "OWNER_REQUIRED"),
        ]
    if response_summary.get("all_owner_parameters_answered") is not True:
        return [
            _action("review_intake_candidate", "Review the ready Betaflight intake candidate.", "OWNER_REVIEW"),
            _action("fill_non_target_parameters", "Fill remaining non-target owner parameters.", "OWNER_REQUIRED"),
            _action("rerun_owner_response_review", "Re-run owner response review before full pipeline regeneration.", "OWNER_REQUIRED"),
        ]
    return [
        _action("review_intake_candidate", "Review the ready Betaflight intake candidate.", "OWNER_REVIEW"),
        _action("write_owner_decision_intake", "Write canonical intake only after explicit owner approval.", "READY"),
        _action("regenerate_owner_target_pipeline", "Regenerate target pipeline after intake is written.", "READY"),
    ]


def _owner_decision_input(open_parameters_owner_response: Mapping[str, Any]) -> dict[str, Any]:
    preview = _mapping(open_parameters_owner_response.get("owner_decision_input_preview"))
    return {
        "profile_name": str(preview.get("profile_name") or "owner-selected-fpv-ai-target"),
        "betaflight_repo_url": str(preview.get("betaflight_repo_url") or ""),
        "betaflight_branch": str(preview.get("betaflight_branch") or ""),
        "fc_target": str(preview.get("fc_target") or ""),
        "ai_uart_port": str(preview.get("ai_uart_port") or ""),
        "serial_mode": str(preview.get("serial_mode") or "OWNER_SELECTION_REQUIRED"),
        "serial_baud": int(preview.get("serial_baud") or 420000),
        "electrical_voltage_level": str(preview.get("electrical_voltage_level") or ""),
        "command_rate_hz": int(preview.get("command_rate_hz") or 20),
        "speed_mode": str(preview.get("speed_mode") or "RACE_SPEED"),
        "operator_limit_mps": float(preview.get("operator_limit_mps") or 5.0),
    }


def _missing_target_decisions(open_parameters_owner_response: Mapping[str, Any]) -> list[dict[str, str]]:
    rows = open_parameters_owner_response.get("missing_target_decisions")
    return [_missing_row(row, "decision_id") for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _missing_non_target_parameters(open_parameters_owner_response: Mapping[str, Any]) -> list[dict[str, str]]:
    rows = open_parameters_owner_response.get("missing_non_target_parameters")
    return [_missing_row(row, "parameter_id") for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _missing_row(row: Mapping[str, Any], identifier_key: str) -> dict[str, str]:
    return {
        identifier_key: str(row.get(identifier_key) or ""),
        "status": str(row.get("status") or ""),
        "detail": str(row.get("detail") or ""),
    }


def _action(action_id: str, detail: str, status: str) -> dict[str, str]:
    return {
        "action_id": action_id,
        "detail": detail,
        "status": status,
    }


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


def _summary(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, Mapping) else {}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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
