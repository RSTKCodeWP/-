"""Owner-response input template for FPV AI Gate-Lock open parameters.

The template is a file-only bridge between the owner packet and the owner
response review. It exposes the exact JSON shape the project owner can fill,
but it does not write intake, select hardware, regenerate pipeline reports, or
authorize hardware tests.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from fpv_ai.evidence.open_parameters_owner_packet import (
    OPEN_PARAMETERS_OWNER_PACKET_SCHEMA,
    TARGET_DECISION_IDS,
)

OPEN_PARAMETERS_OWNER_RESPONSE_TEMPLATE_SCHEMA = "fpv_mvp_open_parameters_owner_response_template.v1"
OWNER_RESPONSE_INPUT_SCHEMA = "fpv_mvp_open_parameters_owner_response_input.v1"

TARGET_TEMPLATE_FIELDS = (
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
)


def build_open_parameters_owner_response_template(
    *,
    open_parameters_owner_packet: Mapping[str, Any],
    open_parameters_owner_packet_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    owner_required = _owner_required_parameters(open_parameters_owner_packet)
    target_template = _target_template(open_parameters_owner_packet)
    target_decision_ids = [
        str(row.get("parameter_id") or "")
        for row in owner_required
        if str(row.get("parameter_id") or "") in TARGET_DECISION_IDS
    ]
    non_target_parameters = _non_target_parameters(open_parameters_owner_packet)
    response_input_template = {
        "schema": OWNER_RESPONSE_INPUT_SCHEMA,
        "target_decision_response": target_template,
        "non_target_parameter_response": {
            str(row.get("parameter_id") or ""): "" for row in non_target_parameters
        },
    }
    checks = _checks(
        open_parameters_owner_packet=open_parameters_owner_packet,
        owner_required=owner_required,
        target_template=target_template,
        target_decision_ids=target_decision_ids,
        non_target_parameters=non_target_parameters,
        response_input_template=response_input_template,
    )
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "schema": OPEN_PARAMETERS_OWNER_RESPONSE_TEMPLATE_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "template_state": "OWNER_RESPONSE_TEMPLATE_READY" if status == "PASS" else "BLOCKED",
        "source_reports": [
            _source_report(
                "open_parameters_owner_packet",
                open_parameters_owner_packet,
                open_parameters_owner_packet_path,
                OPEN_PARAMETERS_OWNER_PACKET_SCHEMA,
            ),
        ],
        "summary": {
            "source_report_count": 1,
            "owner_required_count": len(owner_required),
            "target_template_field_count": len(target_template),
            "non_target_template_field_count": len(non_target_parameters),
            "target_decision_required_count": len(target_decision_ids),
            "non_target_owner_required_count": len(non_target_parameters),
            "hardware_test_authorized": False,
            "no_prop_bench_authorized": False,
            "flight_commands_published": False,
            "field_proof_claimed": False,
            "training_launched": False,
        },
        "owner_response_input_template": response_input_template,
        "target_decision_fields": _target_decision_fields(target_template, target_decision_ids),
        "non_target_parameter_fields": _non_target_parameter_fields(non_target_parameters),
        "next_actions": _next_actions(status),
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "owner_response_template_only": True,
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


def write_open_parameters_owner_response_template(
    *,
    open_parameters_owner_packet_json: Path,
    output_json: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    report = build_open_parameters_owner_response_template(
        open_parameters_owner_packet=_read_json(open_parameters_owner_packet_json),
        open_parameters_owner_packet_path=open_parameters_owner_packet_json,
        project_root=project_root,
    )
    persisted = dict(report)
    persisted["template_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _checks(
    *,
    open_parameters_owner_packet: Mapping[str, Any],
    owner_required: Sequence[Mapping[str, Any]],
    target_template: Mapping[str, Any],
    target_decision_ids: Sequence[str],
    non_target_parameters: Sequence[Mapping[str, Any]],
    response_input_template: Mapping[str, Any],
) -> list[dict[str, str]]:
    summary = _summary(open_parameters_owner_packet)
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
            "owner_required_count_matches_packet",
            len(owner_required) == int(summary.get("owner_required_count") or 0),
            f"{len(owner_required)} vs {summary.get('owner_required_count')}",
        ),
        _check(
            "target_decision_template_fields_declared",
            tuple(target_template) == TARGET_TEMPLATE_FIELDS,
            ",".join(target_template),
        ),
        _check(
            "target_template_field_count_matches_packet",
            len(target_template) == int(summary.get("template_field_count") or 0),
            f"{len(target_template)} vs {summary.get('template_field_count')}",
        ),
        _check(
            "target_decision_required_count_matches_packet",
            len(target_decision_ids) == int(summary.get("target_decision_required_count") or 0),
            f"{len(target_decision_ids)} vs {summary.get('target_decision_required_count')}",
        ),
        _check(
            "non_target_template_field_count_matches_packet",
            len(non_target_parameters) == int(summary.get("non_target_owner_required_count") or 0),
            f"{len(non_target_parameters)} vs {summary.get('non_target_owner_required_count')}",
        ),
        _check(
            "response_template_shape_valid",
            set(response_input_template) == {
                "schema",
                "target_decision_response",
                "non_target_parameter_response",
            },
            ",".join(sorted(response_input_template)),
        ),
        _check(
            "response_template_does_not_auto_select_hardware",
            _hardware_fields_blank(target_template),
            "owner hardware target fields remain blank",
        ),
        _check("hardware_not_authorized", True, "owner response template does not authorize hardware"),
        _check("no_owner_intake_write", True, "template does not write intake"),
        _check("no_pipeline_regeneration", True, "template does not regenerate pipeline"),
        _check("no_live_uart_access", True, "file-only template"),
    ]


def _target_decision_fields(
    target_template: Mapping[str, Any],
    target_decision_ids: Sequence[str],
) -> list[dict[str, Any]]:
    required = set(target_decision_ids)
    fields: list[dict[str, Any]] = []
    for field_id in TARGET_TEMPLATE_FIELDS:
        value = target_template.get(field_id, "")
        owner_required = field_id in required
        fields.append(
            {
                "field_id": field_id,
                "value": value,
                "owner_required": owner_required,
                "status": "OWNER_INPUT_REQUIRED" if owner_required else "TEMPLATE_DEFAULT",
                "detail": _target_field_detail(field_id, owner_required),
            }
        )
    return fields


def _non_target_parameter_fields(non_target_parameters: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for parameter in non_target_parameters:
        rows.append(
            {
                "parameter_id": str(parameter.get("parameter_id") or ""),
                "category": str(parameter.get("category") or ""),
                "template_value": "",
                "owner_required": True,
                "status": "OWNER_INPUT_REQUIRED",
                "detail": str(parameter.get("detail") or ""),
            }
        )
    return rows


def _next_actions(status: str) -> list[dict[str, str]]:
    if status != "PASS":
        return [_action("fix_owner_packet", "Fix owner packet before generating a response template.", "BLOCKED")]
    return [
        _action("fill_owner_response_template", "Project owner fills target and non-target response values.", "OWNER_REQUIRED"),
        _action("rerun_owner_response_review", "Run owner response review with the filled response JSON.", "OWNER_REQUIRED"),
        _action("preview_pipeline_regeneration", "Preview pipeline regeneration only after the response is complete.", "OWNER_REQUIRED"),
    ]


def _target_field_detail(field_id: str, owner_required: bool) -> str:
    if owner_required:
        return "Owner must provide this Betaflight target decision."
    return "Template default carried from the owner packet; owner may review before submission."


def _hardware_fields_blank(target_template: Mapping[str, Any]) -> bool:
    return (
        not str(target_template.get("betaflight_repo_url") or "").strip()
        and not str(target_template.get("betaflight_branch") or "").strip()
        and not str(target_template.get("fc_target") or "").strip()
        and not str(target_template.get("ai_uart_port") or "").strip()
        and not str(target_template.get("electrical_voltage_level") or "").strip()
        and str(target_template.get("serial_mode") or "") == "OWNER_SELECTION_REQUIRED"
    )


def _target_template(open_parameters_owner_packet: Mapping[str, Any]) -> dict[str, Any]:
    template = _mapping(open_parameters_owner_packet.get("target_decision_template"))
    return {
        "profile_name": str(template.get("profile_name") or ""),
        "betaflight_repo_url": str(template.get("betaflight_repo_url") or ""),
        "betaflight_branch": str(template.get("betaflight_branch") or ""),
        "fc_target": str(template.get("fc_target") or ""),
        "ai_uart_port": str(template.get("ai_uart_port") or ""),
        "serial_mode": str(template.get("serial_mode") or ""),
        "serial_baud": int(template.get("serial_baud") or 0),
        "electrical_voltage_level": str(template.get("electrical_voltage_level") or ""),
        "command_rate_hz": int(template.get("command_rate_hz") or 0),
        "speed_mode": str(template.get("speed_mode") or ""),
        "operator_limit_mps": float(template.get("operator_limit_mps") or 0.0),
    }


def _owner_required_parameters(open_parameters_owner_packet: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = open_parameters_owner_packet.get("owner_required_parameters")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _non_target_parameters(open_parameters_owner_packet: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = open_parameters_owner_packet.get("non_target_owner_parameters")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _summary(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, Mapping) else {}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _action(action_id: str, detail: str, status: str) -> dict[str, str]:
    return {
        "action_id": action_id,
        "detail": detail,
        "status": status,
    }


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
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
