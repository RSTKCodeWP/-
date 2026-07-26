"""Dry-run executor for approved open-parameter owner response application.

The executor proves which canonical Betaflight owner-target payloads can be
assembled after approvals. It records payload hashes and intended paths, but it
does not write canonical files, regenerate reports on disk, modify Betaflight,
open UART, or authorize hardware tests.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fpv_ai.betaflight_link.build_hook_mapper import build_betaflight_build_hook_mapper
from fpv_ai.betaflight_link.fork_patch_bundle import FORK_PATCH_BUNDLE_SCHEMA
from fpv_ai.betaflight_link.owner_decision_intake import (
    OwnerDecisionInput,
    build_betaflight_owner_decision_intake,
)
from fpv_ai.betaflight_link.owner_decision_presets import OWNER_DECISION_PRESETS_SCHEMA
from fpv_ai.betaflight_link.owner_decision_review import build_betaflight_owner_decision_review
from fpv_ai.betaflight_link.owner_target_pipeline import build_betaflight_owner_target_pipeline
from fpv_ai.betaflight_link.owner_target_promotion_gate import (
    build_betaflight_owner_target_promotion_gate,
)
from fpv_ai.betaflight_link.simulated_target_review import build_betaflight_simulated_target_review
from fpv_ai.betaflight_link.target_profile import TargetProfileInput, build_betaflight_target_profile
from fpv_ai.evidence.open_parameters_owner_response_approval_gate import (
    OPEN_PARAMETERS_OWNER_RESPONSE_APPROVAL_GATE_SCHEMA,
)
from fpv_ai.evidence.open_parameters_owner_response_apply_plan import (
    OPEN_PARAMETERS_OWNER_RESPONSE_APPLY_PLAN_SCHEMA,
)

OPEN_PARAMETERS_OWNER_RESPONSE_APPLICATION_DRY_RUN_SCHEMA = (
    "fpv_mvp_open_parameters_owner_response_application_dry_run.v1"
)


def build_open_parameters_owner_response_application_dry_run(
    *,
    approval_gate: Mapping[str, Any],
    apply_plan: Mapping[str, Any],
    owner_decision_presets: Mapping[str, Any],
    patch_bundle_manifest: Mapping[str, Any],
    approval_gate_path: Path | str | None = None,
    apply_plan_path: Path | str | None = None,
    owner_decision_presets_path: Path | str | None = None,
    patch_bundle_manifest_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    approved_payloads = _approved_payloads(
        approval_gate=approval_gate,
        apply_plan=apply_plan,
        owner_decision_presets=owner_decision_presets,
        patch_bundle_manifest=patch_bundle_manifest,
        project_root=root,
    )
    checks = _checks(
        approval_gate=approval_gate,
        apply_plan=apply_plan,
        owner_decision_presets=owner_decision_presets,
        patch_bundle_manifest=patch_bundle_manifest,
        approved_payloads=approved_payloads,
    )
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    execution_state = _execution_state(status, approval_gate)
    return {
        "schema": OPEN_PARAMETERS_OWNER_RESPONSE_APPLICATION_DRY_RUN_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "execution_state": execution_state,
        "source_reports": [
            _source_report(
                "open_parameters_owner_response_approval_gate",
                approval_gate,
                approval_gate_path,
                OPEN_PARAMETERS_OWNER_RESPONSE_APPROVAL_GATE_SCHEMA,
            ),
            _source_report(
                "open_parameters_owner_response_apply_plan",
                apply_plan,
                apply_plan_path,
                OPEN_PARAMETERS_OWNER_RESPONSE_APPLY_PLAN_SCHEMA,
            ),
            _source_report(
                "owner_decision_presets",
                owner_decision_presets,
                owner_decision_presets_path,
                OWNER_DECISION_PRESETS_SCHEMA,
            ),
            _source_report(
                "patch_bundle_manifest",
                patch_bundle_manifest,
                patch_bundle_manifest_path,
                FORK_PATCH_BUNDLE_SCHEMA,
            ),
        ],
        "summary": _summary_payload(approval_gate, approved_payloads, execution_state),
        "approved_write_payloads": approved_payloads,
        "blocked_reasons": _blocked_reasons(approval_gate),
        "next_actions": _next_actions(execution_state),
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "application_dry_run_only": True,
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


def write_open_parameters_owner_response_application_dry_run(
    *,
    approval_gate_json: Path,
    apply_plan_json: Path,
    owner_decision_presets_json: Path,
    patch_bundle_manifest_json: Path,
    output_json: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    report = build_open_parameters_owner_response_application_dry_run(
        approval_gate=_read_json(approval_gate_json),
        apply_plan=_read_json(apply_plan_json),
        owner_decision_presets=_read_json(owner_decision_presets_json),
        patch_bundle_manifest=_read_json(patch_bundle_manifest_json),
        approval_gate_path=approval_gate_json,
        apply_plan_path=apply_plan_json,
        owner_decision_presets_path=owner_decision_presets_json,
        patch_bundle_manifest_path=patch_bundle_manifest_json,
        project_root=project_root,
    )
    persisted = dict(report)
    persisted["application_dry_run_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _approved_payloads(
    *,
    approval_gate: Mapping[str, Any],
    apply_plan: Mapping[str, Any],
    owner_decision_presets: Mapping[str, Any],
    patch_bundle_manifest: Mapping[str, Any],
    project_root: Path,
) -> list[dict[str, Any]]:
    approval_state = str(approval_gate.get("approval_state") or "")
    if approval_state not in {"READY_FOR_INTAKE_APPLICATION", "READY_FOR_CANONICAL_APPLICATION"}:
        return []
    payloads = _build_candidate_payloads(
        apply_plan=apply_plan,
        owner_decision_presets=owner_decision_presets,
        patch_bundle_manifest=patch_bundle_manifest,
        project_root=project_root,
    )
    approved = {
        str(row.get("artifact_id") or ""): row
        for row in approval_gate.get("approved_canonical_writes", [])
        if isinstance(row, Mapping)
    }
    return [
        _payload_row(artifact_id, str(write_row.get("path") or ""), payloads[artifact_id])
        for artifact_id, write_row in approved.items()
        if artifact_id in payloads
    ]


def _build_candidate_payloads(
    *,
    apply_plan: Mapping[str, Any],
    owner_decision_presets: Mapping[str, Any],
    patch_bundle_manifest: Mapping[str, Any],
    project_root: Path,
) -> dict[str, Mapping[str, Any]]:
    decisions = OwnerDecisionInput(**_owner_decision_input(apply_plan))
    intake = build_betaflight_owner_decision_intake(decisions=decisions, project_root=project_root)
    if apply_plan.get("plan_state") == "READY_FOR_INTAKE_DRAFT":
        return {"owner_decision_intake": intake}
    target_profile = build_betaflight_target_profile(
        patch_bundle_manifest=patch_bundle_manifest,
        profile=TargetProfileInput(**intake["target_profile_input"]),
        project_root=project_root,
    )
    mapper = build_betaflight_build_hook_mapper(
        target_profile=target_profile,
        patch_bundle_manifest=patch_bundle_manifest,
        project_root=project_root,
    )
    review = build_betaflight_owner_decision_review(
        owner_decision_presets=owner_decision_presets,
        owner_decision_intake=intake,
        target_profile=target_profile,
        build_hook_mapper=mapper,
        project_root=project_root,
    )
    simulated_review = build_betaflight_simulated_target_review(
        owner_decision_presets=owner_decision_presets,
        patch_bundle_manifest=patch_bundle_manifest,
        project_root=project_root,
    )
    promotion_gate = build_betaflight_owner_target_promotion_gate(
        owner_decision_intake=intake,
        target_profile=target_profile,
        build_hook_mapper=mapper,
        owner_decision_review=review,
        simulated_target_review=simulated_review,
        project_root=project_root,
    )
    pipeline = build_betaflight_owner_target_pipeline(
        owner_decision_presets=owner_decision_presets,
        patch_bundle_manifest=patch_bundle_manifest,
        decisions=decisions,
        project_root=project_root,
    )
    return {
        "owner_decision_intake": intake,
        "target_profile": target_profile,
        "build_hook_mapper": mapper,
        "owner_decision_review": review,
        "simulated_target_review": simulated_review,
        "owner_target_promotion_gate": promotion_gate,
        "owner_target_pipeline": pipeline,
    }


def _summary_payload(
    approval_gate: Mapping[str, Any],
    approved_payloads: list[dict[str, Any]],
    execution_state: str,
) -> dict[str, Any]:
    approval_summary = _summary(approval_gate)
    return {
        "source_report_count": 4,
        "approval_state": str(approval_gate.get("approval_state") or ""),
        "application_ready": approval_summary.get("application_ready") is True,
        "canonical_intake_write_approved": approval_summary.get("canonical_intake_write_approved") is True,
        "pipeline_regeneration_approved": approval_summary.get("pipeline_regeneration_approved") is True,
        "approved_planned_write_count": int(approval_summary.get("approved_planned_write_count") or 0),
        "execution_payload_count": len(approved_payloads),
        "canonical_intake_payload_ready": any(
            row["artifact_id"] == "owner_decision_intake" for row in approved_payloads
        ),
        "pipeline_payloads_ready": execution_state == "READY_TO_APPLY_CANONICAL_PIPELINE",
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


def _checks(
    *,
    approval_gate: Mapping[str, Any],
    apply_plan: Mapping[str, Any],
    owner_decision_presets: Mapping[str, Any],
    patch_bundle_manifest: Mapping[str, Any],
    approved_payloads: list[dict[str, Any]],
) -> list[dict[str, str]]:
    approval_summary = _summary(approval_gate)
    return [
        _check(
            "approval_gate_schema_valid",
            approval_gate.get("schema") == OPEN_PARAMETERS_OWNER_RESPONSE_APPROVAL_GATE_SCHEMA,
            str(approval_gate.get("schema") or ""),
        ),
        _check("approval_gate_passed", approval_gate.get("status") == "PASS", str(approval_gate.get("status") or "")),
        _check(
            "apply_plan_schema_valid",
            apply_plan.get("schema") == OPEN_PARAMETERS_OWNER_RESPONSE_APPLY_PLAN_SCHEMA,
            str(apply_plan.get("schema") or ""),
        ),
        _check("apply_plan_passed", apply_plan.get("status") == "PASS", str(apply_plan.get("status") or "")),
        _check(
            "owner_decision_presets_schema_valid",
            owner_decision_presets.get("schema") == OWNER_DECISION_PRESETS_SCHEMA,
            str(owner_decision_presets.get("schema") or ""),
        ),
        _check(
            "patch_bundle_schema_valid",
            patch_bundle_manifest.get("schema") == FORK_PATCH_BUNDLE_SCHEMA,
            str(patch_bundle_manifest.get("schema") or ""),
        ),
        _check(
            "approved_payload_count_matches_gate",
            len(approved_payloads)
            == int(approval_summary.get("approved_planned_write_count") or 0),
            f"{len(approved_payloads)} vs {approval_summary.get('approved_planned_write_count')}",
        ),
        _check(
            "approved_payloads_passed",
            all(row["status"] == "PASS" for row in approved_payloads),
            "all approved payloads pass",
        ),
        _check("no_owner_intake_write", True, "application dry-run does not write intake"),
        _check("no_stage_report_write", True, "application dry-run does not write stage reports"),
        _check("no_pipeline_regeneration", True, "application dry-run does not regenerate pipeline"),
        _check("no_betaflight_repo_modification", True, "application dry-run only"),
        _check("no_compile_or_flash", True, "compile/flash outside this dry-run"),
        _check("no_live_uart_access", True, "file-only dry-run"),
    ]


def _execution_state(status: str, approval_gate: Mapping[str, Any]) -> str:
    if status != "PASS":
        return "BLOCKED"
    approval_state = str(approval_gate.get("approval_state") or "")
    if approval_state == "READY_FOR_INTAKE_APPLICATION":
        return "READY_TO_APPLY_INTAKE"
    if approval_state == "READY_FOR_CANONICAL_APPLICATION":
        return "READY_TO_APPLY_CANONICAL_PIPELINE"
    return "APPLICATION_BLOCKED"


def _blocked_reasons(approval_gate: Mapping[str, Any]) -> list[dict[str, str]]:
    rows = approval_gate.get("blocked_reasons")
    return [
        {
            "blocker_id": str(row.get("blocker_id") or ""),
            "status": str(row.get("status") or ""),
            "detail": str(row.get("detail") or ""),
        }
        for row in rows
        if isinstance(row, Mapping)
    ] if isinstance(rows, list) else []


def _next_actions(execution_state: str) -> list[dict[str, str]]:
    if execution_state == "READY_TO_APPLY_INTAKE":
        return [
            _action("review_dry_run_payload_hashes", "Review intake payload hash before canonical write.", "OWNER_REVIEW"),
            _action("run_explicit_intake_apply", "Run an explicit apply command to write canonical intake.", "READY"),
        ]
    if execution_state == "READY_TO_APPLY_CANONICAL_PIPELINE":
        return [
            _action("review_dry_run_payload_hashes", "Review all payload hashes before canonical writes.", "OWNER_REVIEW"),
            _action("run_explicit_canonical_apply", "Run an explicit apply command to write canonical pipeline reports.", "READY"),
        ]
    if execution_state == "APPLICATION_BLOCKED":
        return [
            _action("complete_owner_response_and_approval", "Complete owner response and approval gates first.", "OWNER_REQUIRED"),
            _action("rerun_application_dry_run", "Re-run this dry-run after approvals are ready.", "OWNER_REQUIRED"),
        ]
    return [_action("fix_source_reports", "Fix source report validation before application dry-run.", "BLOCKED")]


def _payload_row(artifact_id: str, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    payload_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "artifact_id": artifact_id,
        "path": path,
        "schema": str(payload.get("schema") or ""),
        "status": str(payload.get("status") or ""),
        "state": _payload_state(payload),
        "sha256": hashlib.sha256(payload_bytes).hexdigest(),
        "size_bytes": len(payload_bytes),
        "write_status": "DRY_RUN_READY",
    }


def _payload_state(payload: Mapping[str, Any]) -> str:
    for key in (
        "intake_state",
        "target_state",
        "hook_state",
        "review_state",
        "simulation_state",
        "promotion_state",
        "pipeline_state",
    ):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""


def _owner_decision_input(apply_plan: Mapping[str, Any]) -> dict[str, Any]:
    preview = _mapping(apply_plan.get("owner_decision_input_preview"))
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
