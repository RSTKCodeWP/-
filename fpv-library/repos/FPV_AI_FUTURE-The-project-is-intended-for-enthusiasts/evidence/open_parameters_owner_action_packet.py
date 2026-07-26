"""Owner action packet for FPV AI Gate-Lock open parameters.

The packet aggregates the fillable owner response template, approval template,
application dry-run state, and no-prop bench workorder into one review artifact.
It does not fill owner values, grant approvals, write canonical artifacts,
authorize bench work, open UART, or publish flight commands.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from fpv_ai.evidence.no_prop_bench_workorder import WORKORDER_SCHEMA
from fpv_ai.evidence.open_parameters_owner_response import OPEN_PARAMETERS_OWNER_RESPONSE_SCHEMA
from fpv_ai.evidence.open_parameters_owner_response_application_dry_run import (
    OPEN_PARAMETERS_OWNER_RESPONSE_APPLICATION_DRY_RUN_SCHEMA,
)
from fpv_ai.evidence.open_parameters_owner_response_approval_gate import (
    OPEN_PARAMETERS_OWNER_RESPONSE_APPROVAL_GATE_SCHEMA,
    OWNER_APPROVAL_MANIFEST_SCHEMA,
)
from fpv_ai.evidence.open_parameters_owner_response_approval_template import (
    OPEN_PARAMETERS_OWNER_RESPONSE_APPROVAL_TEMPLATE_SCHEMA,
)
from fpv_ai.evidence.open_parameters_owner_response_template import (
    OPEN_PARAMETERS_OWNER_RESPONSE_TEMPLATE_SCHEMA,
    OWNER_RESPONSE_INPUT_SCHEMA,
)

OPEN_PARAMETERS_OWNER_ACTION_PACKET_SCHEMA = "fpv_mvp_open_parameters_owner_action_packet.v1"


def build_open_parameters_owner_action_packet(
    *,
    owner_response_template: Mapping[str, Any],
    owner_response_review: Mapping[str, Any],
    approval_template: Mapping[str, Any],
    approval_gate: Mapping[str, Any],
    application_dry_run: Mapping[str, Any],
    no_prop_bench_workorder: Mapping[str, Any],
    owner_response_template_path: Path | str | None = None,
    owner_response_review_path: Path | str | None = None,
    approval_template_path: Path | str | None = None,
    approval_gate_path: Path | str | None = None,
    application_dry_run_path: Path | str | None = None,
    no_prop_bench_workorder_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    source_reports = _source_reports(
        owner_response_template=owner_response_template,
        owner_response_review=owner_response_review,
        approval_template=approval_template,
        approval_gate=approval_gate,
        application_dry_run=application_dry_run,
        no_prop_bench_workorder=no_prop_bench_workorder,
        owner_response_template_path=owner_response_template_path,
        owner_response_review_path=owner_response_review_path,
        approval_template_path=approval_template_path,
        approval_gate_path=approval_gate_path,
        application_dry_run_path=application_dry_run_path,
        no_prop_bench_workorder_path=no_prop_bench_workorder_path,
    )
    owner_response_actions = _owner_response_actions(owner_response_review)
    approval_actions = _approval_actions(approval_template)
    hardware_review_actions = _hardware_review_actions(no_prop_bench_workorder)
    blocked_reasons = _blocked_reasons(
        approval_template=approval_template,
        approval_gate=approval_gate,
        application_dry_run=application_dry_run,
        no_prop_bench_workorder=no_prop_bench_workorder,
    )
    checks = _checks(
        source_reports=source_reports,
        owner_response_template=owner_response_template,
        owner_response_review=owner_response_review,
        approval_template=approval_template,
        approval_gate=approval_gate,
        application_dry_run=application_dry_run,
        no_prop_bench_workorder=no_prop_bench_workorder,
        owner_response_actions=owner_response_actions,
        approval_actions=approval_actions,
        hardware_review_actions=hardware_review_actions,
    )
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    packet_state = _packet_state(status, owner_response_review, approval_template, approval_gate, application_dry_run)

    return {
        "schema": OPEN_PARAMETERS_OWNER_ACTION_PACKET_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "packet_state": packet_state,
        "source_reports": source_reports,
        "summary": _summary_payload(
            packet_state=packet_state,
            owner_response_template=owner_response_template,
            owner_response_review=owner_response_review,
            approval_template=approval_template,
            approval_gate=approval_gate,
            application_dry_run=application_dry_run,
            no_prop_bench_workorder=no_prop_bench_workorder,
            owner_response_actions=owner_response_actions,
            approval_actions=approval_actions,
            hardware_review_actions=hardware_review_actions,
        ),
        "fillable_templates": {
            "owner_response_input_template": dict(_mapping(owner_response_template.get("owner_response_input_template"))),
            "owner_approval_manifest_template": dict(
                _mapping(approval_template.get("owner_approval_manifest_template"))
            ),
        },
        "stage_statuses": _stage_statuses(
            owner_response_template=owner_response_template,
            owner_response_review=owner_response_review,
            approval_template=approval_template,
            approval_gate=approval_gate,
            application_dry_run=application_dry_run,
            no_prop_bench_workorder=no_prop_bench_workorder,
            source_reports=source_reports,
        ),
        "owner_response_actions": owner_response_actions,
        "approval_actions": approval_actions,
        "hardware_review_actions": hardware_review_actions,
        "blocked_reasons": blocked_reasons,
        "next_actions": _next_actions(packet_state),
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "owner_action_packet_only": True,
            "does_not_fill_owner_values": True,
            "does_not_grant_owner_approval": True,
            "does_not_write_owner_decision_intake": True,
            "does_not_write_stage_reports": True,
            "does_not_regenerate_canonical_pipeline": True,
            "does_not_modify_betaflight_repo": True,
            "does_not_apply_patch": True,
            "does_not_compile_or_flash_betaflight": True,
            "does_not_execute_c_tests": True,
            "does_not_authorize_hardware_test": True,
            "does_not_authorize_no_prop_bench": True,
            "does_not_open_live_cameras": True,
            "does_not_read_gpio": True,
            "does_not_open_uart": True,
            "does_not_start_service": True,
            "does_not_publish_flight_commands": True,
            "does_not_launch_training": True,
        },
    }


def write_open_parameters_owner_action_packet(
    *,
    owner_response_template_json: Path,
    owner_response_review_json: Path,
    approval_template_json: Path,
    approval_gate_json: Path,
    application_dry_run_json: Path,
    no_prop_bench_workorder_json: Path,
    output_json: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    report = build_open_parameters_owner_action_packet(
        owner_response_template=_read_json(owner_response_template_json),
        owner_response_review=_read_json(owner_response_review_json),
        approval_template=_read_json(approval_template_json),
        approval_gate=_read_json(approval_gate_json),
        application_dry_run=_read_json(application_dry_run_json),
        no_prop_bench_workorder=_read_json(no_prop_bench_workorder_json),
        owner_response_template_path=owner_response_template_json,
        owner_response_review_path=owner_response_review_json,
        approval_template_path=approval_template_json,
        approval_gate_path=approval_gate_json,
        application_dry_run_path=application_dry_run_json,
        no_prop_bench_workorder_path=no_prop_bench_workorder_json,
        project_root=project_root,
    )
    persisted = dict(report)
    persisted["packet_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _summary_payload(
    *,
    packet_state: str,
    owner_response_template: Mapping[str, Any],
    owner_response_review: Mapping[str, Any],
    approval_template: Mapping[str, Any],
    approval_gate: Mapping[str, Any],
    application_dry_run: Mapping[str, Any],
    no_prop_bench_workorder: Mapping[str, Any],
    owner_response_actions: Sequence[Mapping[str, Any]],
    approval_actions: Sequence[Mapping[str, Any]],
    hardware_review_actions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    response_summary = _summary(owner_response_review)
    workorder_summary = _summary(no_prop_bench_workorder)
    application_summary = _summary(application_dry_run)
    return {
        "source_report_count": 6,
        "packet_state": packet_state,
        "owner_response_template_ready": owner_response_template.get("template_state") == "OWNER_RESPONSE_TEMPLATE_READY",
        "owner_response_state": str(owner_response_review.get("response_state") or ""),
        "target_missing_count": int(response_summary.get("target_missing_count") or 0),
        "non_target_missing_count": int(response_summary.get("non_target_missing_count") or 0),
        "owner_response_action_count": len(owner_response_actions),
        "approval_template_state": str(approval_template.get("template_state") or ""),
        "approval_action_count": len(approval_actions),
        "approval_state": str(approval_gate.get("approval_state") or ""),
        "application_execution_state": str(application_dry_run.get("execution_state") or ""),
        "application_payload_count": int(application_summary.get("execution_payload_count") or 0),
        "bench_workorder_state": str(no_prop_bench_workorder.get("workorder_state") or ""),
        "bench_owner_decision_count": int(workorder_summary.get("owner_decision_count") or 0),
        "bench_precondition_count": int(workorder_summary.get("required_precondition_count") or 0),
        "imported_blocker_count": int(workorder_summary.get("imported_blocker_count") or 0),
        "total_owner_action_count": len(owner_response_actions) + len(approval_actions) + len(hardware_review_actions),
        "hardware_test_authorized": False,
        "no_prop_bench_authorized": False,
        "live_adapters_enabled": False,
        "flight_commands_published": False,
        "field_proof_claimed": False,
        "training_launched": False,
    }


def _source_reports(
    *,
    owner_response_template: Mapping[str, Any],
    owner_response_review: Mapping[str, Any],
    approval_template: Mapping[str, Any],
    approval_gate: Mapping[str, Any],
    application_dry_run: Mapping[str, Any],
    no_prop_bench_workorder: Mapping[str, Any],
    owner_response_template_path: Path | str | None,
    owner_response_review_path: Path | str | None,
    approval_template_path: Path | str | None,
    approval_gate_path: Path | str | None,
    application_dry_run_path: Path | str | None,
    no_prop_bench_workorder_path: Path | str | None,
) -> list[dict[str, str]]:
    return [
        _source_report(
            "open_parameters_owner_response_template",
            owner_response_template,
            owner_response_template_path,
            OPEN_PARAMETERS_OWNER_RESPONSE_TEMPLATE_SCHEMA,
        ),
        _source_report(
            "open_parameters_owner_response",
            owner_response_review,
            owner_response_review_path,
            OPEN_PARAMETERS_OWNER_RESPONSE_SCHEMA,
        ),
        _source_report(
            "open_parameters_owner_response_approval_template",
            approval_template,
            approval_template_path,
            OPEN_PARAMETERS_OWNER_RESPONSE_APPROVAL_TEMPLATE_SCHEMA,
        ),
        _source_report(
            "open_parameters_owner_response_approval_gate",
            approval_gate,
            approval_gate_path,
            OPEN_PARAMETERS_OWNER_RESPONSE_APPROVAL_GATE_SCHEMA,
        ),
        _source_report(
            "open_parameters_owner_response_application_dry_run",
            application_dry_run,
            application_dry_run_path,
            OPEN_PARAMETERS_OWNER_RESPONSE_APPLICATION_DRY_RUN_SCHEMA,
        ),
        _source_report(
            "no_prop_bench_workorder",
            no_prop_bench_workorder,
            no_prop_bench_workorder_path,
            WORKORDER_SCHEMA,
        ),
    ]


def _stage_statuses(
    *,
    owner_response_template: Mapping[str, Any],
    owner_response_review: Mapping[str, Any],
    approval_template: Mapping[str, Any],
    approval_gate: Mapping[str, Any],
    application_dry_run: Mapping[str, Any],
    no_prop_bench_workorder: Mapping[str, Any],
    source_reports: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    source_paths = {row["report_id"]: row["path"] for row in source_reports}
    return [
        _stage_status(
            "owner_response_template",
            "open_parameters_owner_response_template",
            owner_response_template,
            "template_state",
            source_paths,
        ),
        _stage_status(
            "owner_response_review",
            "open_parameters_owner_response",
            owner_response_review,
            "response_state",
            source_paths,
        ),
        _stage_status(
            "approval_template",
            "open_parameters_owner_response_approval_template",
            approval_template,
            "template_state",
            source_paths,
        ),
        _stage_status(
            "approval_gate",
            "open_parameters_owner_response_approval_gate",
            approval_gate,
            "approval_state",
            source_paths,
        ),
        _stage_status(
            "application_dry_run",
            "open_parameters_owner_response_application_dry_run",
            application_dry_run,
            "execution_state",
            source_paths,
        ),
        _stage_status(
            "no_prop_bench_workorder",
            "no_prop_bench_workorder",
            no_prop_bench_workorder,
            "workorder_state",
            source_paths,
        ),
    ]


def _stage_status(
    stage_id: str,
    report_id: str,
    payload: Mapping[str, Any],
    state_key: str,
    source_paths: Mapping[str, str],
) -> dict[str, str]:
    return {
        "stage_id": stage_id,
        "report_id": report_id,
        "status": str(payload.get("status") or ""),
        "state": str(payload.get(state_key) or ""),
        "source_path": source_paths.get(report_id, ""),
    }


def _owner_response_actions(owner_response_review: Mapping[str, Any]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for row in _list_mappings(owner_response_review.get("missing_target_decisions")):
        decision_id = str(row.get("decision_id") or "")
        actions.append({
            "action_id": f"fill_target_decision.{decision_id}",
            "field_id": decision_id,
            "status": str(row.get("status") or "OWNER_INPUT_REQUIRED"),
            "owner": "project_owner",
            "source": "open_parameters_owner_response",
            "detail": str(row.get("detail") or ""),
        })
    for row in _list_mappings(owner_response_review.get("missing_non_target_parameters")):
        parameter_id = str(row.get("parameter_id") or "")
        actions.append({
            "action_id": f"fill_open_parameter.{parameter_id}",
            "field_id": parameter_id,
            "status": str(row.get("status") or "OWNER_INPUT_REQUIRED"),
            "owner": "project_owner",
            "source": "open_parameters_owner_response",
            "detail": str(row.get("detail") or ""),
        })
    return actions


def _approval_actions(approval_template: Mapping[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "action_id": f"set_owner_approval.{approval_id}",
            "field_id": approval_id,
            "status": str(row.get("status") or "OWNER_APPROVAL_REQUIRED"),
            "owner": "project_owner",
            "source": "open_parameters_owner_response_approval_template",
            "detail": str(row.get("detail") or ""),
        }
        for row in _list_mappings(approval_template.get("approval_fields"))
        for approval_id in [str(row.get("approval_id") or "")]
    ]


def _hardware_review_actions(no_prop_bench_workorder: Mapping[str, Any]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for row in _list_mappings(no_prop_bench_workorder.get("owner_decisions_required")):
        decision_id = str(row.get("decision_id") or "")
        actions.append({
            "action_id": f"bench_owner_decision.{decision_id}",
            "field_id": decision_id,
            "status": str(row.get("status") or ""),
            "owner": str(row.get("owner") or ""),
            "source": "no_prop_bench_workorder",
            "detail": str(row.get("detail") or ""),
        })
    for row in _list_mappings(no_prop_bench_workorder.get("required_preconditions")):
        precondition_id = str(row.get("precondition_id") or "")
        actions.append({
            "action_id": f"bench_precondition.{precondition_id}",
            "field_id": precondition_id,
            "status": str(row.get("status") or ""),
            "owner": str(row.get("owner") or ""),
            "source": "no_prop_bench_workorder",
            "detail": str(row.get("detail") or ""),
        })
    return actions


def _blocked_reasons(
    *,
    approval_template: Mapping[str, Any],
    approval_gate: Mapping[str, Any],
    application_dry_run: Mapping[str, Any],
    no_prop_bench_workorder: Mapping[str, Any],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    rows.extend(_source_blockers("open_parameters_owner_response_approval_template", approval_template.get("blocked_reasons")))
    rows.extend(_source_blockers("open_parameters_owner_response_approval_gate", approval_gate.get("blocked_reasons")))
    rows.extend(_source_blockers("open_parameters_owner_response_application_dry_run", application_dry_run.get("blocked_reasons")))
    rows.extend(_source_blockers("no_prop_bench_workorder", no_prop_bench_workorder.get("imported_blockers")))
    return rows


def _source_blockers(source: str, raw_rows: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in _list_mappings(raw_rows):
        rows.append({
            "blocker_id": str(row.get("blocker_id") or ""),
            "status": str(row.get("status") or ""),
            "owner": str(row.get("owner") or ""),
            "source": source,
            "detail": str(row.get("detail") or ""),
        })
    return rows


def _checks(
    *,
    source_reports: Sequence[Mapping[str, str]],
    owner_response_template: Mapping[str, Any],
    owner_response_review: Mapping[str, Any],
    approval_template: Mapping[str, Any],
    approval_gate: Mapping[str, Any],
    application_dry_run: Mapping[str, Any],
    no_prop_bench_workorder: Mapping[str, Any],
    owner_response_actions: Sequence[Mapping[str, Any]],
    approval_actions: Sequence[Mapping[str, Any]],
    hardware_review_actions: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    response_summary = _summary(owner_response_review)
    workorder_summary = _summary(no_prop_bench_workorder)
    owner_response_template_payload = _mapping(owner_response_template.get("owner_response_input_template"))
    owner_approval_template_payload = _mapping(approval_template.get("owner_approval_manifest_template"))
    source_status_detail = ",".join(
        row["report_id"] for row in source_reports if row["status"] != "PASS" or row["schema"] != row["expected_schema"]
    )
    return [
        _check("source_report_count_valid", len(source_reports) == 6, str(len(source_reports))),
        _check("source_reports_passed", not source_status_detail, source_status_detail or "all source reports pass"),
        _check(
            "owner_response_input_template_schema_valid",
            owner_response_template_payload.get("schema") == OWNER_RESPONSE_INPUT_SCHEMA,
            str(owner_response_template_payload.get("schema") or ""),
        ),
        _check(
            "owner_approval_manifest_template_schema_valid",
            owner_approval_template_payload.get("schema") == OWNER_APPROVAL_MANIFEST_SCHEMA,
            str(owner_approval_template_payload.get("schema") or ""),
        ),
        _check(
            "owner_response_action_count_matches_missing_fields",
            len(owner_response_actions)
            == int(response_summary.get("target_missing_count") or 0)
            + int(response_summary.get("non_target_missing_count") or 0),
            str(len(owner_response_actions)),
        ),
        _check(
            "approval_action_count_matches_template",
            len(approval_actions) == int(_summary(approval_template).get("required_approval_count") or 0),
            str(len(approval_actions)),
        ),
        _check(
            "hardware_review_action_count_matches_workorder",
            len(hardware_review_actions)
            == int(workorder_summary.get("owner_decision_count") or 0)
            + int(workorder_summary.get("required_precondition_count") or 0),
            str(len(hardware_review_actions)),
        ),
        _check("does_not_fill_owner_values", True, "packet copies fillable templates only"),
        _check("does_not_grant_owner_approval", True, "approval manifest values remain owner-controlled"),
        _check("does_not_authorize_hardware", True, "packet is review-only"),
        _check("no_live_uart_access", True, "file-only action packet"),
        _check(
            "hardware_flags_clear",
            _hardware_flags_clear(
                owner_response_review,
                approval_template,
                approval_gate,
                application_dry_run,
                no_prop_bench_workorder,
            ),
            "source summaries do not authorize hardware or publish flight commands",
        ),
    ]


def _hardware_flags_clear(*payloads: Mapping[str, Any]) -> bool:
    for payload in payloads:
        for section in (_summary(payload), _mapping(payload.get("safety_boundary"))):
            for flag in (
                "hardware_test_authorized",
                "no_prop_bench_authorized",
                "live_adapters_enabled",
                "flight_commands_published",
                "field_proof_claimed",
                "training_launched",
                "uart_opened",
            ):
                if section.get(flag) is True:
                    return False
    return True


def _packet_state(
    status: str,
    owner_response_review: Mapping[str, Any],
    approval_template: Mapping[str, Any],
    approval_gate: Mapping[str, Any],
    application_dry_run: Mapping[str, Any],
) -> str:
    if status != "PASS":
        return "BLOCKED"
    if owner_response_review.get("response_state") == "OWNER_RESPONSE_INCOMPLETE":
        return "OWNER_INPUT_REQUIRED"
    if (
        approval_template.get("template_state") == "APPROVAL_TEMPLATE_READY"
        or approval_gate.get("approval_state") == "OWNER_APPROVAL_REQUIRED"
    ):
        return "OWNER_APPROVAL_REQUIRED"
    if application_dry_run.get("execution_state") in {
        "READY_TO_APPLY_INTAKE",
        "READY_TO_APPLY_CANONICAL_PIPELINE",
    }:
        return "READY_FOR_APPLICATION_DRY_RUN_REVIEW"
    return "OWNER_REVIEW_REQUIRED"


def _next_actions(packet_state: str) -> list[dict[str, str]]:
    if packet_state == "OWNER_INPUT_REQUIRED":
        return [
            _action("fill_owner_response_template", "Project owner fills target decisions and open parameters.", "OWNER_REQUIRED"),
            _action("rerun_owner_response_review", "Re-run owner response review after values are supplied.", "OWNER_REQUIRED"),
            _action("regenerate_owner_action_packet", "Regenerate this packet after response, bridge, plan, approval, and dry-run reports.", "OWNER_REQUIRED"),
        ]
    if packet_state == "OWNER_APPROVAL_REQUIRED":
        return [
            _action("fill_owner_approval_manifest", "Project owner sets each approval to true or false.", "OWNER_REQUIRED"),
            _action("rerun_approval_gate", "Re-run approval gate and application dry-run after approval input.", "OWNER_REQUIRED"),
        ]
    if packet_state == "READY_FOR_APPLICATION_DRY_RUN_REVIEW":
        return [
            _action("review_application_payload_hashes", "Review dry-run payload hashes before any explicit write command.", "OWNER_REVIEW"),
            _action("keep_hardware_disabled", "Hardware and no-prop bench remain unauthorized until separate owner scope.", "OWNER_REVIEW"),
        ]
    if packet_state == "OWNER_REVIEW_REQUIRED":
        return [_action("review_packet", "Review the owner packet state and decide the next owner-controlled step.", "OWNER_REVIEW")]
    return [_action("fix_source_reports", "Fix failed or mismatched source reports before this packet is actionable.", "BLOCKED")]


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


def _action(action_id: str, detail: str, status: str) -> dict[str, str]:
    return {
        "action_id": action_id,
        "detail": detail,
        "status": status,
    }


def _summary(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, Mapping) else {}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list_mappings(value: Any) -> list[Mapping[str, Any]]:
    return [row for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


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
