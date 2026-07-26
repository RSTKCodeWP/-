"""Owner approval gate for applying an open-parameter owner response.

The gate validates whether a dry-run application plan has the owner approvals
needed for canonical writes. It never writes intake, regenerates pipeline
reports, modifies Betaflight, opens UART, or authorizes hardware tests.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from fpv_ai.evidence.open_parameters_owner_response_apply_plan import (
    OPEN_PARAMETERS_OWNER_RESPONSE_APPLY_PLAN_SCHEMA,
)

OPEN_PARAMETERS_OWNER_RESPONSE_APPROVAL_GATE_SCHEMA = (
    "fpv_mvp_open_parameters_owner_response_approval_gate.v1"
)
OWNER_APPROVAL_MANIFEST_SCHEMA = "fpv_mvp_owner_approval_manifest.v1"


def build_open_parameters_owner_response_approval_gate(
    *,
    apply_plan: Mapping[str, Any],
    owner_approval: Mapping[str, Any] | None = None,
    apply_plan_path: Path | str | None = None,
    owner_approval_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    approval_input = owner_approval or {}
    required_approvals = _required_approvals(apply_plan)
    approval_decisions = _approval_decisions(required_approvals, approval_input)
    checks = _checks(
        apply_plan=apply_plan,
        owner_approval=approval_input,
        approval_decisions=approval_decisions,
    )
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    approval_state = _approval_state(status, apply_plan, approval_decisions)
    return {
        "schema": OPEN_PARAMETERS_OWNER_RESPONSE_APPROVAL_GATE_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "approval_state": approval_state,
        "source_reports": [
            _source_report(
                "open_parameters_owner_response_apply_plan",
                apply_plan,
                apply_plan_path,
                OPEN_PARAMETERS_OWNER_RESPONSE_APPLY_PLAN_SCHEMA,
            ),
            _source_report(
                "owner_approval_manifest",
                approval_input,
                owner_approval_path,
                OWNER_APPROVAL_MANIFEST_SCHEMA,
            ),
        ],
        "summary": _summary_payload(
            apply_plan=apply_plan,
            approval_decisions=approval_decisions,
            approval_state=approval_state,
        ),
        "approval_decisions": approval_decisions,
        "approved_canonical_writes": _approved_canonical_writes(apply_plan, approval_state),
        "blocked_reasons": _blocked_reasons(apply_plan, approval_decisions),
        "next_actions": _next_actions(approval_state),
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "approval_gate_only": True,
            "does_not_select_hardware_automatically": True,
            "does_not_write_owner_decision_intake": True,
            "does_not_write_stage_reports": True,
            "does_not_regenerate_canonical_pipeline": True,
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


def write_open_parameters_owner_response_approval_gate(
    *,
    apply_plan_json: Path,
    output_json: Path,
    owner_approval_json: Path | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    approval = _read_json(owner_approval_json) if owner_approval_json is not None else None
    report = build_open_parameters_owner_response_approval_gate(
        apply_plan=_read_json(apply_plan_json),
        owner_approval=approval,
        apply_plan_path=apply_plan_json,
        owner_approval_path=owner_approval_json,
        project_root=project_root,
    )
    persisted = dict(report)
    persisted["approval_gate_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _summary_payload(
    *,
    apply_plan: Mapping[str, Any],
    approval_decisions: Sequence[Mapping[str, Any]],
    approval_state: str,
) -> dict[str, Any]:
    apply_summary = _summary(apply_plan)
    planned_writes = _planned_writes(apply_plan)
    approved_write_ids = set(_approved_write_ids(approval_state))
    return {
        "source_report_count": 2,
        "apply_plan_state": str(apply_plan.get("plan_state") or ""),
        "plan_ready_for_owner_application": apply_plan.get("plan_state") == "READY_FOR_OWNER_APPROVED_APPLICATION",
        "intake_draft_ready": apply_plan.get("plan_state") == "READY_FOR_INTAKE_DRAFT",
        "requested_approval_count": len(approval_decisions),
        "approved_approval_count": sum(1 for row in approval_decisions if row["status"] == "APPROVED"),
        "missing_approval_count": sum(1 for row in approval_decisions if row["status"] == "MISSING"),
        "denied_approval_count": sum(1 for row in approval_decisions if row["status"] == "DENIED"),
        "planned_write_count": int(apply_summary.get("planned_write_count") or len(planned_writes)),
        "ready_planned_write_count": int(apply_summary.get("ready_planned_write_count") or 0),
        "approved_planned_write_count": sum(
            1 for row in planned_writes if str(row.get("artifact_id") or "") in approved_write_ids
        ),
        "canonical_intake_write_approved": "owner_decision_intake" in approved_write_ids,
        "pipeline_regeneration_approved": "owner_target_pipeline" in approved_write_ids,
        "application_ready": approval_state in {
            "READY_FOR_INTAKE_APPLICATION",
            "READY_FOR_CANONICAL_APPLICATION",
        },
        "canonical_intake_written": False,
        "stage_reports_written": False,
        "pipeline_regenerated": False,
        "hardware_test_authorized": False,
        "no_prop_bench_authorized": False,
        "betaflight_repo_modified": False,
        "compile_attempted": False,
        "flash_attempted": False,
        "uart_opened": False,
        "flight_commands_published": False,
    }


def _approval_decisions(
    required_approvals: Sequence[Mapping[str, str]],
    owner_approval: Mapping[str, Any],
) -> list[dict[str, Any]]:
    supplied = {
        str(row.get("approval_id") or ""): row
        for row in _approval_rows(owner_approval)
    }
    decisions: list[dict[str, Any]] = []
    for required in required_approvals:
        approval_id = str(required.get("approval_id") or "")
        supplied_row = _mapping(supplied.get(approval_id))
        approved = supplied_row.get("approved")
        if approved is True:
            status = "APPROVED"
        elif approved is False:
            status = "DENIED"
        else:
            status = "MISSING"
        decisions.append(
            {
                "approval_id": approval_id,
                "status": status,
                "approved": approved is True,
                "approved_by": str(supplied_row.get("approved_by") or ""),
                "approved_at": str(supplied_row.get("approved_at") or ""),
                "detail": str(required.get("detail") or supplied_row.get("detail") or ""),
            }
        )
    return decisions


def _approved_canonical_writes(
    apply_plan: Mapping[str, Any],
    approval_state: str,
) -> list[dict[str, Any]]:
    approved_write_ids = set(_approved_write_ids(approval_state))
    return [
        {
            "artifact_id": str(row.get("artifact_id") or ""),
            "path": str(row.get("path") or ""),
            "status": "APPROVED_FOR_APPLICATION",
            "detail": str(row.get("detail") or ""),
        }
        for row in _planned_writes(apply_plan)
        if str(row.get("artifact_id") or "") in approved_write_ids
    ]


def _blocked_reasons(
    apply_plan: Mapping[str, Any],
    approval_decisions: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if apply_plan.get("plan_state") == "OWNER_RESPONSE_INCOMPLETE":
        rows.append(_blocker("apply_plan_not_ready", "Owner response is incomplete; approvals are not actionable."))
    if apply_plan.get("plan_state") == "BLOCKED":
        rows.append(_blocker("apply_plan_blocked", "Application plan is blocked."))
    missing = [row for row in approval_decisions if row["status"] == "MISSING"]
    denied = [row for row in approval_decisions if row["status"] == "DENIED"]
    if missing:
        rows.append(_blocker("owner_approval_missing", f"{len(missing)} required approvals are missing."))
    if denied:
        rows.append(_blocker("owner_approval_denied", f"{len(denied)} required approvals are denied."))
    return rows


def _checks(
    *,
    apply_plan: Mapping[str, Any],
    owner_approval: Mapping[str, Any],
    approval_decisions: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    return [
        _check(
            "apply_plan_schema_valid",
            apply_plan.get("schema") == OPEN_PARAMETERS_OWNER_RESPONSE_APPLY_PLAN_SCHEMA,
            str(apply_plan.get("schema") or ""),
        ),
        _check("apply_plan_passed", apply_plan.get("status") == "PASS", str(apply_plan.get("status") or "")),
        _check(
            "owner_approval_manifest_optional_or_schema_valid",
            not owner_approval
            or owner_approval.get("schema") == OWNER_APPROVAL_MANIFEST_SCHEMA,
            str(owner_approval.get("schema") or "NO_APPROVAL_MANIFEST"),
        ),
        _check(
            "approval_count_matches_plan",
            len(approval_decisions) == len(_required_approvals(apply_plan)),
            f"{len(approval_decisions)} vs {len(_required_approvals(apply_plan))}",
        ),
        _check(
            "hardware_not_authorized_by_approval_manifest",
            owner_approval.get("hardware_test_authorized") is not True,
            str(owner_approval.get("hardware_test_authorized", False)),
        ),
        _check(
            "no_prop_bench_not_authorized_by_approval_manifest",
            owner_approval.get("no_prop_bench_authorized") is not True,
            str(owner_approval.get("no_prop_bench_authorized", False)),
        ),
        _check("no_owner_intake_write", True, "approval gate does not write intake"),
        _check("no_stage_report_write", True, "approval gate does not write stage reports"),
        _check("no_pipeline_regeneration", True, "approval gate does not regenerate pipeline"),
        _check("no_betaflight_repo_modification", True, "approval gate only"),
        _check("no_compile_or_flash", True, "compile/flash outside this gate"),
        _check("no_live_uart_access", True, "file-only gate"),
    ]


def _approval_state(
    status: str,
    apply_plan: Mapping[str, Any],
    approval_decisions: Sequence[Mapping[str, Any]],
) -> str:
    if status != "PASS":
        return "BLOCKED"
    plan_state = str(apply_plan.get("plan_state") or "")
    if plan_state == "OWNER_RESPONSE_INCOMPLETE":
        return "APPLICATION_BLOCKED"
    if plan_state == "BLOCKED":
        return "BLOCKED"
    if any(row["status"] == "DENIED" for row in approval_decisions):
        return "OWNER_APPROVAL_DENIED"
    if any(row["status"] == "MISSING" for row in approval_decisions):
        return "OWNER_APPROVAL_REQUIRED"
    if plan_state == "READY_FOR_INTAKE_DRAFT":
        return "READY_FOR_INTAKE_APPLICATION"
    if plan_state == "READY_FOR_OWNER_APPROVED_APPLICATION":
        return "READY_FOR_CANONICAL_APPLICATION"
    return "BLOCKED"


def _next_actions(approval_state: str) -> list[dict[str, str]]:
    if approval_state == "APPLICATION_BLOCKED":
        return [
            _action("complete_owner_response", "Fill owner response fields before approvals are actionable.", "OWNER_REQUIRED"),
            _action("rerun_apply_plan", "Re-run bridge, preview, apply plan, and approval gate.", "OWNER_REQUIRED"),
        ]
    if approval_state == "OWNER_APPROVAL_REQUIRED":
        return [
            _action("review_required_approvals", "Project owner reviews required approval manifest entries.", "OWNER_REVIEW"),
            _action("rerun_approval_gate", "Re-run this gate with an owner approval manifest.", "OWNER_REQUIRED"),
        ]
    if approval_state == "OWNER_APPROVAL_DENIED":
        return [_action("resolve_denied_approvals", "Resolve denied owner approvals before canonical application.", "OWNER_REQUIRED")]
    if approval_state == "READY_FOR_INTAKE_APPLICATION":
        return [_action("write_owner_decision_intake", "Canonical intake may be written by an explicit apply command.", "READY")]
    if approval_state == "READY_FOR_CANONICAL_APPLICATION":
        return [
            _action("write_owner_decision_intake", "Canonical intake may be written by an explicit apply command.", "READY"),
            _action("regenerate_owner_target_pipeline", "Canonical pipeline may be regenerated by an explicit apply command.", "READY"),
        ]
    return [_action("fix_source_reports", "Fix source validation before approval gate can pass.", "BLOCKED")]


def _approved_write_ids(approval_state: str) -> tuple[str, ...]:
    if approval_state == "READY_FOR_INTAKE_APPLICATION":
        return ("owner_decision_intake",)
    if approval_state == "READY_FOR_CANONICAL_APPLICATION":
        return (
            "owner_decision_intake",
            "target_profile",
            "build_hook_mapper",
            "owner_decision_review",
            "simulated_target_review",
            "owner_target_promotion_gate",
            "owner_target_pipeline",
        )
    return ()


def _required_approvals(apply_plan: Mapping[str, Any]) -> list[Mapping[str, str]]:
    rows = apply_plan.get("owner_approval_required")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _approval_rows(owner_approval: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = owner_approval.get("approvals")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _planned_writes(apply_plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = apply_plan.get("planned_canonical_writes")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


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


def _blocker(blocker_id: str, detail: str) -> dict[str, str]:
    return {
        "blocker_id": blocker_id,
        "status": "BLOCKED",
        "detail": detail,
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


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
