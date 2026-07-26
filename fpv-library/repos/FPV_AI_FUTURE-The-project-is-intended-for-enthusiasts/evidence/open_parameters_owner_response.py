"""Owner-response review for FPV AI Gate-Lock open parameters.

This module validates a project-owner response against the owner packet. It can
show whether the response is complete enough to regenerate the owner target
pipeline, but it does not write ``owner_decision_intake.json``, select hardware
automatically, or authorize any live adapter or hardware test.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from fpv_ai.betaflight_link.owner_decision_intake import SUPPORTED_SERIAL_MODES
from fpv_ai.evidence.open_parameters_owner_packet import (
    OPEN_PARAMETERS_OWNER_PACKET_SCHEMA,
    TARGET_DECISION_IDS,
)

OPEN_PARAMETERS_OWNER_RESPONSE_SCHEMA = "fpv_mvp_open_parameters_owner_response.v1"


def build_open_parameters_owner_response(
    *,
    open_parameters_owner_packet: Mapping[str, Any],
    owner_response: Mapping[str, Any] | None = None,
    open_parameters_owner_packet_path: Path | str | None = None,
    owner_response_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    response = owner_response or {}
    target_response = _target_decision_response(open_parameters_owner_packet, response)
    required_parameters = _owner_required_parameters(open_parameters_owner_packet)
    required_target_ids = [
        str(row.get("parameter_id") or "")
        for row in required_parameters
        if str(row.get("parameter_id") or "") in TARGET_DECISION_IDS
    ]
    non_target_responses = _non_target_parameter_responses(required_parameters, response)
    missing_target = _missing_target_decisions(required_target_ids, target_response)
    missing_non_target = [
        row for row in non_target_responses if row["status"] == "OWNER_INPUT_REQUIRED"
    ]
    checks = _checks(
        open_parameters_owner_packet=open_parameters_owner_packet,
        target_response=target_response,
        required_target_ids=required_target_ids,
        missing_target=missing_target,
        non_target_responses=non_target_responses,
    )
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    response_state = _response_state(status, missing_target, missing_non_target)
    return {
        "schema": OPEN_PARAMETERS_OWNER_RESPONSE_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "response_state": response_state,
        "source_reports": [
            _source_report(
                "open_parameters_owner_packet",
                open_parameters_owner_packet,
                open_parameters_owner_packet_path,
                OPEN_PARAMETERS_OWNER_PACKET_SCHEMA,
            ),
            _source_report(
                "owner_response_input",
                response,
                owner_response_path,
                str(response.get("schema") or ""),
            ),
        ],
        "summary": {
            "source_report_count": 2,
            "owner_required_count": len(required_parameters),
            "target_required_count": len(required_target_ids),
            "target_selected_count": len(required_target_ids) - len(missing_target),
            "target_missing_count": len(missing_target),
            "non_target_required_count": len(non_target_responses),
            "non_target_answered_count": sum(
                1 for row in non_target_responses if row["status"] == "ANSWERED"
            ),
            "non_target_missing_count": len(missing_non_target),
            "owner_decision_input_ready": not missing_target,
            "all_owner_parameters_answered": not missing_target and not missing_non_target,
            "pipeline_regeneration_ready": response_state == "READY_FOR_PIPELINE_REGENERATION",
            "hardware_test_authorized": False,
            "no_prop_bench_authorized": False,
            "flight_commands_published": False,
            "field_proof_claimed": False,
            "training_launched": False,
        },
        "owner_decision_input_preview": target_response,
        "non_target_parameter_responses": non_target_responses,
        "missing_target_decisions": missing_target,
        "missing_non_target_parameters": [_missing_parameter(row) for row in missing_non_target],
        "next_actions": _next_actions(response_state),
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "owner_response_review_only": True,
            "does_not_select_hardware_automatically": True,
            "does_not_write_owner_decision_intake": True,
            "does_not_regenerate_pipeline": True,
            "does_not_authorize_hardware_test": True,
            "does_not_authorize_no_prop_bench": True,
            "does_not_open_live_cameras": True,
            "does_not_read_gpio": True,
            "does_not_open_uart": True,
            "does_not_start_service": True,
            "does_not_publish_flight_commands": True,
            "does_not_compile_or_flash_betaflight": True,
            "does_not_launch_training": True,
        },
    }


def write_open_parameters_owner_response(
    *,
    open_parameters_owner_packet_json: Path,
    output_json: Path,
    owner_response_json: Path | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    response = _read_json(owner_response_json) if owner_response_json is not None else {}
    report = build_open_parameters_owner_response(
        open_parameters_owner_packet=_read_json(open_parameters_owner_packet_json),
        owner_response=response,
        open_parameters_owner_packet_path=open_parameters_owner_packet_json,
        owner_response_path=owner_response_json,
        project_root=project_root,
    )
    persisted = dict(report)
    persisted["response_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _target_decision_response(
    open_parameters_owner_packet: Mapping[str, Any],
    owner_response: Mapping[str, Any],
) -> dict[str, Any]:
    template = _mapping(open_parameters_owner_packet.get("target_decision_template"))
    response = _mapping(owner_response.get("target_decision_response"))
    merged = {
        "profile_name": str(response.get("profile_name") or template.get("profile_name") or ""),
        "betaflight_repo_url": str(response.get("betaflight_repo_url") or ""),
        "betaflight_branch": str(response.get("betaflight_branch") or ""),
        "fc_target": str(response.get("fc_target") or ""),
        "ai_uart_port": str(response.get("ai_uart_port") or ""),
        "serial_mode": str(response.get("serial_mode") or template.get("serial_mode") or ""),
        "serial_baud": int(response.get("serial_baud") or template.get("serial_baud") or 420000),
        "electrical_voltage_level": str(response.get("electrical_voltage_level") or ""),
        "command_rate_hz": int(response.get("command_rate_hz") or template.get("command_rate_hz") or 20),
        "speed_mode": str(response.get("speed_mode") or template.get("speed_mode") or "RACE_SPEED"),
        "operator_limit_mps": float(
            response.get("operator_limit_mps") or template.get("operator_limit_mps") or 5.0
        ),
    }
    return merged


def _non_target_parameter_responses(
    required_parameters: Sequence[Mapping[str, Any]],
    owner_response: Mapping[str, Any],
) -> list[dict[str, Any]]:
    response_values = _mapping(owner_response.get("non_target_parameter_response"))
    rows: list[dict[str, Any]] = []
    for parameter in required_parameters:
        parameter_id = str(parameter.get("parameter_id") or "")
        if parameter_id in TARGET_DECISION_IDS:
            continue
        response_value = response_values.get(parameter_id, "")
        answered = _value_selected(response_value)
        rows.append(
            {
                "parameter_id": parameter_id,
                "category": str(parameter.get("category") or ""),
                "response_value": response_value if response_value is not None else "",
                "status": "ANSWERED" if answered else "OWNER_INPUT_REQUIRED",
                "detail": str(parameter.get("detail") or ""),
            }
        )
    return rows


def _missing_target_decisions(
    required_target_ids: Sequence[str],
    target_response: Mapping[str, Any],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for decision_id in required_target_ids:
        value = target_response.get(decision_id)
        if _value_selected(value):
            continue
        rows.append(
            {
                "decision_id": decision_id,
                "status": "OWNER_INPUT_REQUIRED",
                "detail": "Owner response must provide this Betaflight target decision.",
            }
        )
    return rows


def _checks(
    *,
    open_parameters_owner_packet: Mapping[str, Any],
    target_response: Mapping[str, Any],
    required_target_ids: Sequence[str],
    missing_target: Sequence[Mapping[str, str]],
    non_target_responses: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    return [
        _check(
            "open_parameters_owner_packet_schema_valid",
            open_parameters_owner_packet.get("schema") == OPEN_PARAMETERS_OWNER_PACKET_SCHEMA,
            str(open_parameters_owner_packet.get("schema") or ""),
        ),
        _check(
            "open_parameters_owner_packet_passed",
            open_parameters_owner_packet.get("status") == "PASS",
            str(open_parameters_owner_packet.get("status") or ""),
        ),
        _check(
            "required_target_decisions_declared",
            len(required_target_ids) == int(_summary(open_parameters_owner_packet).get("target_decision_required_count") or 0),
            str(len(required_target_ids)),
        ),
        _check(
            "target_response_shape_valid",
            set(target_response) == {
                "profile_name",
                "betaflight_repo_url",
                "betaflight_branch",
                "fc_target",
                "ai_uart_port",
                "serial_mode",
                "serial_baud",
                "electrical_voltage_level",
                "command_rate_hz",
                "speed_mode",
                "operator_limit_mps",
            },
            ",".join(sorted(target_response)),
        ),
        _check("serial_mode_supported", str(target_response["serial_mode"]) in SUPPORTED_SERIAL_MODES, str(target_response["serial_mode"])),
        _check("serial_baud_valid", 115200 <= int(target_response["serial_baud"]) <= 1000000, str(target_response["serial_baud"])),
        _check("command_rate_valid", 10 <= int(target_response["command_rate_hz"]) <= 100, str(target_response["command_rate_hz"])),
        _check(
            "operator_limit_valid",
            0.1 <= float(target_response["operator_limit_mps"]) <= 60.0,
            str(target_response["operator_limit_mps"]),
        ),
        _check("missing_target_decisions_recorded", True, str(len(missing_target))),
        _check("non_target_responses_declared", True, str(len(non_target_responses))),
        _check("hardware_not_authorized", True, "owner response review does not authorize hardware"),
        _check("no_live_uart_access", True, "file-only response review"),
    ]


def _next_actions(response_state: str) -> list[dict[str, str]]:
    if response_state == "READY_FOR_PIPELINE_REGENERATION":
        return [
            _action("owner_review_response", "Project owner reviews the response values before writing intake.", "OWNER_REVIEW"),
            _action("write_owner_decision_intake", "Write intake only after explicit owner approval.", "READY"),
            _action("regenerate_owner_target_pipeline", "Regenerate target pipeline after intake is written.", "READY"),
        ]
    if response_state == "OWNER_RESPONSE_INCOMPLETE":
        return [
            _action("fill_missing_target_decisions", "Fill missing Betaflight target decisions.", "OWNER_REQUIRED"),
            _action("fill_missing_open_parameters", "Fill missing non-target owner parameters.", "OWNER_REQUIRED"),
            _action("rerun_owner_response_review", "Re-run this review after the response JSON is updated.", "OWNER_REQUIRED"),
        ]
    return [_action("fix_source_reports", "Fix owner packet or response validation errors.", "BLOCKED")]


def _response_state(
    status: str,
    missing_target: Sequence[Mapping[str, str]],
    missing_non_target: Sequence[Mapping[str, Any]],
) -> str:
    if status != "PASS":
        return "BLOCKED"
    if missing_target or missing_non_target:
        return "OWNER_RESPONSE_INCOMPLETE"
    return "READY_FOR_PIPELINE_REGENERATION"


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


def _owner_required_parameters(open_parameters_owner_packet: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = open_parameters_owner_packet.get("owner_required_parameters")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _missing_parameter(row: Mapping[str, Any]) -> dict[str, str]:
    return {
        "parameter_id": str(row.get("parameter_id") or ""),
        "status": "OWNER_INPUT_REQUIRED",
        "detail": str(row.get("detail") or ""),
    }


def _value_selected(value: Any) -> bool:
    if isinstance(value, str):
        normalized = value.strip().upper()
        return bool(normalized) and normalized not in {
            "OWNER_SELECTION_REQUIRED",
            "OWNER_DECISION_REQUIRED",
            "OWNER_INPUT_REQUIRED",
            "TBD",
            "TODO",
            "UNKNOWN",
            "UNSELECTED",
            "NOT_SELECTED",
        }
    return value is not None


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
