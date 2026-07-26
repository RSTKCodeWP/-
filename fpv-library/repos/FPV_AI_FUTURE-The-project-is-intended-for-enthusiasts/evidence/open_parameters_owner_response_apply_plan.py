"""Dry-run application plan for an open-parameter owner response.

The plan describes which canonical Betaflight owner-target artifacts would be
written after explicit owner approval. It never writes the canonical intake,
stage reports, Betaflight files, or any hardware-facing output.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fpv_ai.evidence.open_parameters_owner_response import OPEN_PARAMETERS_OWNER_RESPONSE_SCHEMA
from fpv_ai.evidence.open_parameters_owner_response_intake_bridge import (
    OPEN_PARAMETERS_OWNER_RESPONSE_INTAKE_BRIDGE_SCHEMA,
)
from fpv_ai.evidence.open_parameters_pipeline_preview import OPEN_PARAMETERS_PIPELINE_PREVIEW_SCHEMA

OPEN_PARAMETERS_OWNER_RESPONSE_APPLY_PLAN_SCHEMA = (
    "fpv_mvp_open_parameters_owner_response_apply_plan.v1"
)

CANONICAL_STAGE_WRITES = (
    (
        "owner_decision_intake",
        "reports/fpv/betaflight_fork/owner_decision_intake.json",
        "Canonical Betaflight owner decision intake.",
    ),
    (
        "target_profile",
        "reports/fpv/betaflight_fork/target_profile.json",
        "Canonical owner-selected Betaflight target profile.",
    ),
    (
        "build_hook_mapper",
        "reports/fpv/betaflight_fork/build_hook_mapper.json",
        "Canonical Betaflight build and UART hook mapper.",
    ),
    (
        "owner_decision_review",
        "reports/fpv/betaflight_fork/owner_decision_review.json",
        "Canonical owner decision review packet.",
    ),
    (
        "simulated_target_review",
        "reports/fpv/betaflight_fork/simulated_target_review.json",
        "Simulation-only guardrail review; never a real hardware selection.",
    ),
    (
        "owner_target_promotion_gate",
        "reports/fpv/betaflight_fork/owner_target_promotion_gate.json",
        "Canonical owner target promotion gate.",
    ),
    (
        "owner_target_pipeline",
        "reports/fpv/betaflight_fork/owner_target_pipeline.json",
        "Canonical owner target pipeline aggregate.",
    ),
)


def build_open_parameters_owner_response_apply_plan(
    *,
    open_parameters_owner_response: Mapping[str, Any],
    intake_bridge: Mapping[str, Any],
    pipeline_preview: Mapping[str, Any],
    open_parameters_owner_response_path: Path | str | None = None,
    intake_bridge_path: Path | str | None = None,
    pipeline_preview_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    checks = _checks(
        open_parameters_owner_response=open_parameters_owner_response,
        intake_bridge=intake_bridge,
        pipeline_preview=pipeline_preview,
    )
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    plan_state = _plan_state(status, intake_bridge, pipeline_preview)
    planned_writes = _planned_writes(plan_state, pipeline_preview)
    return {
        "schema": OPEN_PARAMETERS_OWNER_RESPONSE_APPLY_PLAN_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "plan_state": plan_state,
        "source_reports": [
            _source_report(
                "open_parameters_owner_response",
                open_parameters_owner_response,
                open_parameters_owner_response_path,
                OPEN_PARAMETERS_OWNER_RESPONSE_SCHEMA,
            ),
            _source_report(
                "open_parameters_owner_response_intake_bridge",
                intake_bridge,
                intake_bridge_path,
                OPEN_PARAMETERS_OWNER_RESPONSE_INTAKE_BRIDGE_SCHEMA,
            ),
            _source_report(
                "open_parameters_pipeline_preview",
                pipeline_preview,
                pipeline_preview_path,
                OPEN_PARAMETERS_PIPELINE_PREVIEW_SCHEMA,
            ),
        ],
        "summary": _summary_payload(
            open_parameters_owner_response=open_parameters_owner_response,
            intake_bridge=intake_bridge,
            pipeline_preview=pipeline_preview,
            planned_writes=planned_writes,
        ),
        "owner_decision_input_preview": dict(_mapping(intake_bridge.get("owner_decision_input_preview"))),
        "planned_canonical_writes": planned_writes,
        "owner_approval_required": _owner_approval_required(plan_state),
        "blocked_reasons": _blocked_reasons(open_parameters_owner_response, intake_bridge, pipeline_preview),
        "next_actions": _next_actions(plan_state),
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "application_plan_only": True,
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


def write_open_parameters_owner_response_apply_plan(
    *,
    open_parameters_owner_response_json: Path,
    intake_bridge_json: Path,
    pipeline_preview_json: Path,
    output_json: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    report = build_open_parameters_owner_response_apply_plan(
        open_parameters_owner_response=_read_json(open_parameters_owner_response_json),
        intake_bridge=_read_json(intake_bridge_json),
        pipeline_preview=_read_json(pipeline_preview_json),
        open_parameters_owner_response_path=open_parameters_owner_response_json,
        intake_bridge_path=intake_bridge_json,
        pipeline_preview_path=pipeline_preview_json,
        project_root=project_root,
    )
    persisted = dict(report)
    persisted["plan_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _summary_payload(
    *,
    open_parameters_owner_response: Mapping[str, Any],
    intake_bridge: Mapping[str, Any],
    pipeline_preview: Mapping[str, Any],
    planned_writes: list[dict[str, Any]],
) -> dict[str, Any]:
    response_summary = _summary(open_parameters_owner_response)
    bridge_summary = _summary(intake_bridge)
    preview_summary = _summary(pipeline_preview)
    return {
        "source_report_count": 3,
        "owner_response_state": str(open_parameters_owner_response.get("response_state") or ""),
        "bridge_state": str(intake_bridge.get("bridge_state") or ""),
        "pipeline_preview_state": str(pipeline_preview.get("preview_state") or ""),
        "owner_decision_input_ready": response_summary.get("owner_decision_input_ready") is True,
        "all_owner_parameters_answered": response_summary.get("all_owner_parameters_answered") is True,
        "intake_write_ready": bridge_summary.get("intake_write_ready") is True,
        "pipeline_preview_built": preview_summary.get("pipeline_preview_built") is True,
        "promotion_ready": preview_summary.get("promotion_ready") is True,
        "target_missing_count": int(response_summary.get("target_missing_count") or 0),
        "non_target_missing_count": int(response_summary.get("non_target_missing_count") or 0),
        "planned_write_count": len(planned_writes),
        "ready_planned_write_count": sum(1 for row in planned_writes if row["status"] == "READY_FOR_OWNER_APPROVAL"),
        "blocked_planned_write_count": sum(1 for row in planned_writes if row["status"] != "READY_FOR_OWNER_APPROVAL"),
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


def _planned_writes(plan_state: str, pipeline_preview: Mapping[str, Any]) -> list[dict[str, Any]]:
    preview_stage_ids = {
        str(row.get("stage_id") or "")
        for row in _mapping(pipeline_preview.get("pipeline_preview")).get("stage_reports", [])
        if isinstance(row, Mapping)
    }
    full_pipeline_ready = plan_state == "READY_FOR_OWNER_APPROVED_APPLICATION"
    intake_only_ready = plan_state == "READY_FOR_INTAKE_DRAFT"
    rows: list[dict[str, Any]] = []
    for artifact_id, path, detail in CANONICAL_STAGE_WRITES:
        ready = full_pipeline_ready or (intake_only_ready and artifact_id == "owner_decision_intake")
        rows.append(
            {
                "artifact_id": artifact_id,
                "path": path,
                "status": "READY_FOR_OWNER_APPROVAL" if ready else _blocked_write_status(plan_state),
                "source_preview_available": (
                    (artifact_id == "owner_decision_intake" and (full_pipeline_ready or intake_only_ready))
                    or artifact_id == "owner_target_pipeline"
                    or artifact_id in preview_stage_ids
                ),
                "detail": detail,
            }
        )
    return rows


def _blocked_write_status(plan_state: str) -> str:
    if plan_state == "OWNER_RESPONSE_INCOMPLETE":
        return "BLOCKED_OWNER_RESPONSE_INCOMPLETE"
    if plan_state == "READY_FOR_INTAKE_DRAFT":
        return "BLOCKED_PIPELINE_PREVIEW_INCOMPLETE"
    return "BLOCKED"


def _owner_approval_required(plan_state: str) -> list[dict[str, str]]:
    if plan_state == "READY_FOR_OWNER_APPROVED_APPLICATION":
        return [
            _approval("write_owner_decision_intake", "Approve writing canonical Betaflight owner decision intake.", "OWNER_APPROVAL_REQUIRED"),
            _approval("regenerate_owner_target_pipeline", "Approve regenerating canonical owner target pipeline reports.", "OWNER_APPROVAL_REQUIRED"),
        ]
    if plan_state == "READY_FOR_INTAKE_DRAFT":
        return [
            _approval("write_owner_decision_intake", "Approve intake write only after remaining parameters are understood.", "OWNER_APPROVAL_REQUIRED"),
        ]
    return []


def _blocked_reasons(
    open_parameters_owner_response: Mapping[str, Any],
    intake_bridge: Mapping[str, Any],
    pipeline_preview: Mapping[str, Any],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    response_summary = _summary(open_parameters_owner_response)
    if response_summary.get("owner_decision_input_ready") is not True:
        rows.append(
            _blocker(
                "target_decisions_missing",
                f"{int(response_summary.get('target_missing_count') or 0)} target decisions are missing.",
            )
        )
    if response_summary.get("all_owner_parameters_answered") is not True:
        rows.append(
            _blocker(
                "non_target_parameters_missing",
                f"{int(response_summary.get('non_target_missing_count') or 0)} non-target owner parameters are missing.",
            )
        )
    if _summary(intake_bridge).get("intake_write_ready") is not True:
        rows.append(_blocker("intake_candidate_not_ready", "Betaflight intake candidate is not ready."))
    if _summary(pipeline_preview).get("pipeline_preview_built") is not True:
        rows.append(_blocker("pipeline_preview_not_built", "Pipeline preview was not built."))
    return rows


def _checks(
    *,
    open_parameters_owner_response: Mapping[str, Any],
    intake_bridge: Mapping[str, Any],
    pipeline_preview: Mapping[str, Any],
) -> list[dict[str, str]]:
    response_summary = _summary(open_parameters_owner_response)
    bridge_summary = _summary(intake_bridge)
    preview_summary = _summary(pipeline_preview)
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
            "intake_bridge_schema_valid",
            intake_bridge.get("schema") == OPEN_PARAMETERS_OWNER_RESPONSE_INTAKE_BRIDGE_SCHEMA,
            str(intake_bridge.get("schema") or ""),
        ),
        _check("intake_bridge_passed", intake_bridge.get("status") == "PASS", str(intake_bridge.get("status") or "")),
        _check(
            "pipeline_preview_schema_valid",
            pipeline_preview.get("schema") == OPEN_PARAMETERS_PIPELINE_PREVIEW_SCHEMA,
            str(pipeline_preview.get("schema") or ""),
        ),
        _check(
            "pipeline_preview_passed",
            pipeline_preview.get("status") == "PASS",
            str(pipeline_preview.get("status") or ""),
        ),
        _check(
            "bridge_matches_owner_response_state",
            str(bridge_summary.get("owner_response_state") or "")
            == str(open_parameters_owner_response.get("response_state") or ""),
            f"{bridge_summary.get('owner_response_state')} vs {open_parameters_owner_response.get('response_state')}",
        ),
        _check(
            "preview_matches_owner_response_state",
            str(preview_summary.get("owner_response_state") or "")
            == str(open_parameters_owner_response.get("response_state") or ""),
            f"{preview_summary.get('owner_response_state')} vs {open_parameters_owner_response.get('response_state')}",
        ),
        _check(
            "target_missing_count_consistent",
            int(response_summary.get("target_missing_count") or 0)
            == int(bridge_summary.get("missing_owner_decision_count") or 0)
            == int(preview_summary.get("missing_owner_decision_count") or 0),
            "response, bridge, and preview target blockers",
        ),
        _check("no_owner_intake_write", True, "application plan does not write intake"),
        _check("no_stage_report_write", True, "application plan does not write stage reports"),
        _check("no_pipeline_regeneration", True, "application plan does not regenerate pipeline"),
        _check("no_betaflight_repo_modification", True, "application plan only"),
        _check("no_compile_or_flash", True, "compile/flash outside this plan"),
        _check("no_live_uart_access", True, "file-only plan"),
    ]


def _plan_state(
    status: str,
    intake_bridge: Mapping[str, Any],
    pipeline_preview: Mapping[str, Any],
) -> str:
    if status != "PASS":
        return "BLOCKED"
    if intake_bridge.get("bridge_state") == "READY_FOR_PIPELINE_REGENERATION" and (
        pipeline_preview.get("preview_state") == "READY_FOR_PIPELINE_REGENERATION"
    ):
        return "READY_FOR_OWNER_APPROVED_APPLICATION"
    if intake_bridge.get("bridge_state") == "READY_FOR_INTAKE_DRAFT":
        return "READY_FOR_INTAKE_DRAFT"
    if intake_bridge.get("bridge_state") == "OWNER_RESPONSE_INCOMPLETE":
        return "OWNER_RESPONSE_INCOMPLETE"
    return "BLOCKED"


def _next_actions(plan_state: str) -> list[dict[str, str]]:
    if plan_state == "READY_FOR_OWNER_APPROVED_APPLICATION":
        return [
            _action("owner_review_apply_plan", "Review planned canonical writes.", "OWNER_REVIEW"),
            _action("write_owner_decision_intake", "Write canonical intake only after explicit owner approval.", "READY"),
            _action("regenerate_owner_target_pipeline", "Regenerate canonical pipeline after intake write.", "READY"),
        ]
    if plan_state == "READY_FOR_INTAKE_DRAFT":
        return [
            _action("owner_review_intake_candidate", "Review intake candidate before any canonical write.", "OWNER_REVIEW"),
            _action("complete_non_target_parameters", "Fill non-target owner parameters before full pipeline regeneration.", "OWNER_REQUIRED"),
        ]
    if plan_state == "OWNER_RESPONSE_INCOMPLETE":
        return [
            _action("complete_owner_response", "Fill target and non-target owner response fields.", "OWNER_REQUIRED"),
            _action("rerun_owner_response_review", "Re-run response review, bridge, preview, and apply plan.", "OWNER_REQUIRED"),
        ]
    return [_action("fix_source_reports", "Fix source report validation before using this plan.", "BLOCKED")]


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


def _approval(approval_id: str, detail: str, status: str) -> dict[str, str]:
    return {
        "approval_id": approval_id,
        "detail": detail,
        "status": status,
    }


def _blocker(blocker_id: str, detail: str) -> dict[str, str]:
    return {
        "blocker_id": blocker_id,
        "status": "BLOCKED",
        "detail": detail,
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
