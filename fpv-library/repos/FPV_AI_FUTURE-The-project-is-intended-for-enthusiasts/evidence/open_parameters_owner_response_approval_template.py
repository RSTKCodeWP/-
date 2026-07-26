"""Owner approval manifest template for open-parameter application.

The template converts an application plan into a fillable owner approval
manifest. It does not approve anything by default and does not write intake,
pipeline reports, Betaflight files, or hardware-facing outputs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from fpv_ai.evidence.open_parameters_owner_response_approval_gate import (
    OWNER_APPROVAL_MANIFEST_SCHEMA,
)
from fpv_ai.evidence.open_parameters_owner_response_apply_plan import (
    OPEN_PARAMETERS_OWNER_RESPONSE_APPLY_PLAN_SCHEMA,
)

OPEN_PARAMETERS_OWNER_RESPONSE_APPROVAL_TEMPLATE_SCHEMA = (
    "fpv_mvp_open_parameters_owner_response_approval_template.v1"
)


def build_open_parameters_owner_response_approval_template(
    *,
    apply_plan: Mapping[str, Any],
    apply_plan_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    required_approvals = _required_approvals(apply_plan)
    manifest_template = _approval_manifest_template(required_approvals)
    checks = _checks(apply_plan=apply_plan, manifest_template=manifest_template)
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    template_state = _template_state(status, apply_plan, required_approvals)
    return {
        "schema": OPEN_PARAMETERS_OWNER_RESPONSE_APPROVAL_TEMPLATE_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "template_state": template_state,
        "source_reports": [
            _source_report(
                "open_parameters_owner_response_apply_plan",
                apply_plan,
                apply_plan_path,
                OPEN_PARAMETERS_OWNER_RESPONSE_APPLY_PLAN_SCHEMA,
            ),
        ],
        "summary": _summary_payload(apply_plan, required_approvals, template_state),
        "owner_approval_manifest_template": manifest_template,
        "approval_fields": _approval_fields(required_approvals, template_state),
        "planned_write_fields": _planned_write_fields(apply_plan),
        "blocked_reasons": _blocked_reasons(apply_plan, template_state),
        "next_actions": _next_actions(template_state),
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "approval_template_only": True,
            "does_not_grant_owner_approval": True,
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


def write_open_parameters_owner_response_approval_template(
    *,
    apply_plan_json: Path,
    output_json: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    report = build_open_parameters_owner_response_approval_template(
        apply_plan=_read_json(apply_plan_json),
        apply_plan_path=apply_plan_json,
        project_root=project_root,
    )
    persisted = dict(report)
    persisted["template_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _summary_payload(
    apply_plan: Mapping[str, Any],
    required_approvals: Sequence[Mapping[str, str]],
    template_state: str,
) -> dict[str, Any]:
    plan_summary = _summary(apply_plan)
    return {
        "source_report_count": 1,
        "apply_plan_state": str(apply_plan.get("plan_state") or ""),
        "approval_template_ready": template_state == "APPROVAL_TEMPLATE_READY",
        "required_approval_count": len(required_approvals),
        "planned_write_count": int(plan_summary.get("planned_write_count") or 0),
        "ready_planned_write_count": int(plan_summary.get("ready_planned_write_count") or 0),
        "blocked_planned_write_count": int(plan_summary.get("blocked_planned_write_count") or 0),
        "all_approvals_default_to_missing": True,
        "owner_approval_granted": False,
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


def _approval_manifest_template(required_approvals: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    return {
        "schema": OWNER_APPROVAL_MANIFEST_SCHEMA,
        "approvals": [
            {
                "approval_id": str(row.get("approval_id") or ""),
                "approved": None,
                "approved_by": "",
                "approved_at": "",
                "detail": str(row.get("detail") or ""),
            }
            for row in required_approvals
        ],
        "hardware_test_authorized": False,
        "no_prop_bench_authorized": False,
    }


def _approval_fields(
    required_approvals: Sequence[Mapping[str, str]],
    template_state: str,
) -> list[dict[str, str]]:
    status = "OWNER_APPROVAL_REQUIRED" if template_state == "APPROVAL_TEMPLATE_READY" else "BLOCKED"
    return [
        {
            "approval_id": str(row.get("approval_id") or ""),
            "status": status,
            "detail": str(row.get("detail") or ""),
        }
        for row in required_approvals
    ]


def _planned_write_fields(apply_plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "artifact_id": str(row.get("artifact_id") or ""),
            "path": str(row.get("path") or ""),
            "status": str(row.get("status") or ""),
            "source_preview_available": row.get("source_preview_available") is True,
            "detail": str(row.get("detail") or ""),
        }
        for row in _planned_writes(apply_plan)
    ]


def _blocked_reasons(
    apply_plan: Mapping[str, Any],
    template_state: str,
) -> list[dict[str, str]]:
    if template_state == "APPROVAL_TEMPLATE_READY":
        return []
    if template_state == "BLOCKED":
        return [_blocker("apply_plan_failed", "Apply plan validation failed.")]
    if apply_plan.get("plan_state") == "OWNER_RESPONSE_INCOMPLETE":
        return [_blocker("apply_plan_not_ready", "Owner response is incomplete; approvals are not actionable.")]
    return [_blocker("no_required_approvals", "Apply plan has no approval requirements yet.")]


def _checks(
    *,
    apply_plan: Mapping[str, Any],
    manifest_template: Mapping[str, Any],
) -> list[dict[str, str]]:
    return [
        _check(
            "apply_plan_schema_valid",
            apply_plan.get("schema") == OPEN_PARAMETERS_OWNER_RESPONSE_APPLY_PLAN_SCHEMA,
            str(apply_plan.get("schema") or ""),
        ),
        _check("apply_plan_passed", apply_plan.get("status") == "PASS", str(apply_plan.get("status") or "")),
        _check(
            "manifest_template_schema_valid",
            manifest_template.get("schema") == OWNER_APPROVAL_MANIFEST_SCHEMA,
            str(manifest_template.get("schema") or ""),
        ),
        _check(
            "approval_count_matches_apply_plan",
            len(_approval_rows(manifest_template)) == len(_required_approvals(apply_plan)),
            f"{len(_approval_rows(manifest_template))} vs {len(_required_approvals(apply_plan))}",
        ),
        _check(
            "approvals_default_to_missing",
            all(row.get("approved") is None for row in _approval_rows(manifest_template)),
            "approved fields remain null",
        ),
        _check(
            "hardware_not_authorized",
            manifest_template.get("hardware_test_authorized") is False,
            str(manifest_template.get("hardware_test_authorized")),
        ),
        _check(
            "no_prop_bench_not_authorized",
            manifest_template.get("no_prop_bench_authorized") is False,
            str(manifest_template.get("no_prop_bench_authorized")),
        ),
        _check("no_owner_intake_write", True, "approval template does not write intake"),
        _check("no_stage_report_write", True, "approval template does not write stage reports"),
        _check("no_pipeline_regeneration", True, "approval template does not regenerate pipeline"),
        _check("no_betaflight_repo_modification", True, "approval template only"),
        _check("no_live_uart_access", True, "file-only template"),
    ]


def _template_state(
    status: str,
    apply_plan: Mapping[str, Any],
    required_approvals: Sequence[Mapping[str, str]],
) -> str:
    if status != "PASS":
        return "BLOCKED"
    if required_approvals:
        return "APPROVAL_TEMPLATE_READY"
    if apply_plan.get("plan_state") == "OWNER_RESPONSE_INCOMPLETE":
        return "APPLICATION_BLOCKED"
    return "NO_APPROVALS_REQUIRED"


def _next_actions(template_state: str) -> list[dict[str, str]]:
    if template_state == "APPROVAL_TEMPLATE_READY":
        return [
            _action("fill_owner_approval_manifest", "Project owner sets each approved field to true or false.", "OWNER_REQUIRED"),
            _action("rerun_approval_gate", "Run approval gate with the filled owner approval manifest.", "OWNER_REQUIRED"),
        ]
    if template_state == "APPLICATION_BLOCKED":
        return [
            _action("complete_owner_response", "Complete owner response before approvals are actionable.", "OWNER_REQUIRED"),
            _action("rerun_apply_plan", "Re-run apply plan and approval template after owner response is complete.", "OWNER_REQUIRED"),
        ]
    if template_state == "NO_APPROVALS_REQUIRED":
        return [_action("inspect_apply_plan", "Inspect apply plan because no required approvals were produced.", "OWNER_REVIEW")]
    return [_action("fix_apply_plan", "Fix apply plan validation before generating approval template.", "BLOCKED")]


def _required_approvals(apply_plan: Mapping[str, Any]) -> list[Mapping[str, str]]:
    rows = apply_plan.get("owner_approval_required")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _approval_rows(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = manifest.get("approvals")
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
