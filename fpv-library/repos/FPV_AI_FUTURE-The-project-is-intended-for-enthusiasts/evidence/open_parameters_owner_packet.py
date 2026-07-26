"""Owner-input packet for FPV AI Gate-Lock open parameters.

The packet converts the open-parameter register into a reviewable intake
template. It is deliberately non-authoritative: it does not select hardware,
does not fill values automatically, and does not authorize no-prop or flight
tests.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from fpv_ai.evidence.open_parameters_register import OPEN_PARAMETERS_SCHEMA

OPEN_PARAMETERS_OWNER_PACKET_SCHEMA = "fpv_mvp_open_parameters_owner_packet.v1"

TARGET_DECISION_IDS = (
    "betaflight_repo_url",
    "betaflight_branch",
    "fc_target",
    "ai_uart_port",
    "serial_mode",
    "electrical_voltage_level",
)


def build_open_parameters_owner_packet(
    *,
    open_parameters_register: Mapping[str, Any],
    open_parameters_register_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    parameters = _parameters(open_parameters_register)
    owner_required = [row for row in parameters if row.get("status") == "OWNER_DECISION_REQUIRED"]
    target_required = [row for row in owner_required if str(row.get("parameter_id") or "") in TARGET_DECISION_IDS]
    non_target_required = [row for row in owner_required if str(row.get("parameter_id") or "") not in TARGET_DECISION_IDS]
    template = _target_decision_template(parameters)
    checks = _checks(open_parameters_register, parameters, owner_required, template)
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "schema": OPEN_PARAMETERS_OWNER_PACKET_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "packet_state": _packet_state(status, owner_required),
        "source_reports": [
            _source_report(
                "open_parameters_register",
                open_parameters_register,
                open_parameters_register_path,
                OPEN_PARAMETERS_SCHEMA,
            ),
        ],
        "summary": {
            "source_report_count": 1,
            "parameter_count": len(parameters),
            "owner_required_count": len(owner_required),
            "target_decision_required_count": len(target_required),
            "non_target_owner_required_count": len(non_target_required),
            "template_field_count": len(template),
            "target_selected": _summary(open_parameters_register).get("target_selected") is True,
            "promotion_ready": _summary(open_parameters_register).get("promotion_ready") is True,
            "hardware_test_authorized": False,
            "no_prop_bench_authorized": False,
            "flight_commands_published": False,
            "field_proof_claimed": False,
            "training_launched": False,
        },
        "owner_required_parameters": [_public_parameter(row) for row in owner_required],
        "target_decision_template": template,
        "non_target_owner_parameters": [_public_parameter(row) for row in non_target_required],
        "regeneration_plan": _regeneration_plan(owner_required),
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "owner_packet_only": True,
            "does_not_select_hardware_automatically": True,
            "does_not_write_owner_decision_intake": True,
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


def write_open_parameters_owner_packet(
    *,
    open_parameters_register_json: Path,
    output_json: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    report = build_open_parameters_owner_packet(
        open_parameters_register=_read_json(open_parameters_register_json),
        open_parameters_register_path=open_parameters_register_json,
        project_root=project_root,
    )
    persisted = dict(report)
    persisted["packet_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _target_decision_template(parameters: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = {str(row.get("parameter_id") or ""): row.get("value") for row in parameters}
    return {
        "profile_name": "owner-selected-fpv-ai-target",
        "betaflight_repo_url": "",
        "betaflight_branch": "",
        "fc_target": "",
        "ai_uart_port": "",
        "serial_mode": "OWNER_SELECTION_REQUIRED",
        "serial_baud": int(values.get("serial_baud") or 420000),
        "electrical_voltage_level": "",
        "command_rate_hz": int(values.get("command_rate_hz") or 20),
        "speed_mode": "RACE_SPEED",
        "operator_limit_mps": float(values.get("race_speed_operator_limit_mps") or 5.0),
    }


def _regeneration_plan(owner_required: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    status = "OWNER_REQUIRED" if owner_required else "READY"
    return [
        _plan_step(
            "review_open_parameters",
            "Review owner_required_parameters and fill only project-owner approved values.",
            status,
        ),
        _plan_step(
            "write_owner_decision_intake",
            "Use target_decision_template as the explicit Betaflight owner decision intake source.",
            status,
        ),
        _plan_step(
            "regenerate_owner_target_pipeline",
            "Regenerate owner target pipeline after the owner decision intake is written.",
            status,
        ),
        _plan_step(
            "regenerate_open_parameter_reports",
            "Regenerate open parameter register and owner packet after pipeline review.",
            status,
        ),
    ]


def _checks(
    open_parameters_register: Mapping[str, Any],
    parameters: Sequence[Mapping[str, Any]],
    owner_required: Sequence[Mapping[str, Any]],
    template: Mapping[str, Any],
) -> list[dict[str, str]]:
    summary = _summary(open_parameters_register)
    required_from_summary = int(summary.get("owner_required_count") or 0)
    return [
        _check(
            "open_parameters_register_schema_valid",
            open_parameters_register.get("schema") == OPEN_PARAMETERS_SCHEMA,
            str(open_parameters_register.get("schema") or ""),
        ),
        _check(
            "open_parameters_register_passed",
            open_parameters_register.get("status") == "PASS",
            str(open_parameters_register.get("status") or ""),
        ),
        _check("parameters_declared", bool(parameters), str(len(parameters))),
        _check(
            "owner_required_count_matches_register",
            len(owner_required) == required_from_summary,
            f"{len(owner_required)} vs {required_from_summary}",
        ),
        _check(
            "target_decision_template_fields_declared",
            set(template) == {
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
            ",".join(sorted(template)),
        ),
        _check(
            "target_template_does_not_auto_select_hardware",
            not str(template.get("fc_target") or "").strip()
            and str(template.get("serial_mode") or "") == "OWNER_SELECTION_REQUIRED",
            "owner values remain blank",
        ),
        _check("hardware_not_authorized", True, "owner packet does not authorize hardware"),
        _check("no_prop_bench_not_authorized", True, "owner packet does not authorize no-prop bench"),
        _check("no_live_uart_access", True, "file-only packet"),
    ]


def _packet_state(status: str, owner_required: Sequence[Mapping[str, Any]]) -> str:
    if status != "PASS":
        return "BLOCKED"
    if owner_required:
        return "OWNER_INPUT_REQUIRED"
    return "READY_FOR_OWNER_REVIEW"


def _plan_step(step_id: str, detail: str, status: str) -> dict[str, str]:
    return {
        "step_id": step_id,
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


def _parameters(open_parameters_register: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    parameters = open_parameters_register.get("parameters")
    return [row for row in parameters if isinstance(row, Mapping)] if isinstance(parameters, list) else []


def _public_parameter(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "parameter_id": str(row.get("parameter_id") or ""),
        "category": str(row.get("category") or ""),
        "value": row.get("value", ""),
        "status": str(row.get("status") or ""),
        "detail": str(row.get("detail") or ""),
    }


def _summary(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, Mapping) else {}


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
