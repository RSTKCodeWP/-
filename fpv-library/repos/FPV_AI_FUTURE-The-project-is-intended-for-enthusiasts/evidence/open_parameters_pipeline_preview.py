"""Pipeline preview from an FPV AI Gate-Lock owner response.

The preview consumes the owner response review and, only when that response is
complete, builds the Betaflight owner target pipeline in memory. It does not
write ``owner_decision_intake.json``, stage reports, Betaflight files, or any
hardware-facing output.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fpv_ai.betaflight_link.fork_patch_bundle import FORK_PATCH_BUNDLE_SCHEMA
from fpv_ai.betaflight_link.owner_decision_intake import OwnerDecisionInput
from fpv_ai.betaflight_link.owner_decision_presets import OWNER_DECISION_PRESETS_SCHEMA
from fpv_ai.betaflight_link.owner_target_pipeline import (
    OWNER_TARGET_PIPELINE_SCHEMA,
    build_betaflight_owner_target_pipeline,
)
from fpv_ai.evidence.open_parameters_owner_response import (
    OPEN_PARAMETERS_OWNER_RESPONSE_SCHEMA,
)

OPEN_PARAMETERS_PIPELINE_PREVIEW_SCHEMA = "fpv_mvp_open_parameters_pipeline_preview.v1"


def build_open_parameters_pipeline_preview(
    *,
    open_parameters_owner_response: Mapping[str, Any],
    owner_decision_presets: Mapping[str, Any],
    patch_bundle_manifest: Mapping[str, Any],
    open_parameters_owner_response_path: Path | str | None = None,
    owner_decision_presets_path: Path | str | None = None,
    patch_bundle_manifest_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    response_ready = _summary(open_parameters_owner_response).get("pipeline_regeneration_ready") is True
    preview_pipeline = (
        build_betaflight_owner_target_pipeline(
            owner_decision_presets=owner_decision_presets,
            patch_bundle_manifest=patch_bundle_manifest,
            decisions=OwnerDecisionInput(**_owner_decision_input(open_parameters_owner_response)),
            project_root=root,
        )
        if response_ready
        else None
    )
    checks = _checks(
        open_parameters_owner_response=open_parameters_owner_response,
        owner_decision_presets=owner_decision_presets,
        patch_bundle_manifest=patch_bundle_manifest,
        preview_pipeline=preview_pipeline,
    )
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "schema": OPEN_PARAMETERS_PIPELINE_PREVIEW_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "preview_state": _preview_state(status, open_parameters_owner_response, preview_pipeline),
        "source_reports": [
            _source_report(
                "open_parameters_owner_response",
                open_parameters_owner_response,
                open_parameters_owner_response_path,
                OPEN_PARAMETERS_OWNER_RESPONSE_SCHEMA,
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
        "summary": _summary_payload(open_parameters_owner_response, preview_pipeline),
        "owner_decision_input_preview": _owner_decision_input(open_parameters_owner_response),
        "pipeline_preview": _pipeline_preview_payload(preview_pipeline),
        "next_actions": _next_actions(open_parameters_owner_response, preview_pipeline),
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "preview_only": True,
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


def write_open_parameters_pipeline_preview(
    *,
    open_parameters_owner_response_json: Path,
    owner_decision_presets_json: Path,
    patch_bundle_manifest_json: Path,
    output_json: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    report = build_open_parameters_pipeline_preview(
        open_parameters_owner_response=_read_json(open_parameters_owner_response_json),
        owner_decision_presets=_read_json(owner_decision_presets_json),
        patch_bundle_manifest=_read_json(patch_bundle_manifest_json),
        open_parameters_owner_response_path=open_parameters_owner_response_json,
        owner_decision_presets_path=owner_decision_presets_json,
        patch_bundle_manifest_path=patch_bundle_manifest_json,
        project_root=project_root,
    )
    persisted = dict(report)
    persisted["preview_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _summary_payload(
    open_parameters_owner_response: Mapping[str, Any],
    preview_pipeline: Mapping[str, Any] | None,
) -> dict[str, Any]:
    response_summary = _summary(open_parameters_owner_response)
    pipeline_summary = _summary(preview_pipeline or {})
    return {
        "source_report_count": 3,
        "owner_response_state": str(open_parameters_owner_response.get("response_state") or ""),
        "owner_decision_input_ready": response_summary.get("owner_decision_input_ready") is True,
        "all_owner_parameters_answered": response_summary.get("all_owner_parameters_answered") is True,
        "pipeline_preview_built": preview_pipeline is not None,
        "pipeline_preview_state": str((preview_pipeline or {}).get("pipeline_state") or ""),
        "promotion_state": str(pipeline_summary.get("promotion_state") or ""),
        "target_selected": pipeline_summary.get("target_selected") is True,
        "promotion_ready": pipeline_summary.get("promotion_ready") is True,
        "missing_owner_decision_count": int(pipeline_summary.get("missing_owner_decision_count") or 0)
        if preview_pipeline is not None
        else int(response_summary.get("target_missing_count") or 0),
        "owner_blocker_count": int(pipeline_summary.get("owner_blocker_count") or 0)
        if preview_pipeline is not None
        else int(response_summary.get("target_missing_count") or 0),
        "hardware_test_authorized": False,
        "no_prop_bench_authorized": False,
        "betaflight_repo_modified": False,
        "compile_attempted": False,
        "flash_attempted": False,
        "uart_opened": False,
        "flight_commands_published": False,
    }


def _pipeline_preview_payload(preview_pipeline: Mapping[str, Any] | None) -> dict[str, Any]:
    if preview_pipeline is None:
        return {
            "schema": "",
            "status": "NOT_BUILT",
            "pipeline_state": "OWNER_RESPONSE_INCOMPLETE",
            "summary": {},
            "stage_reports": [],
        }
    return {
        "schema": str(preview_pipeline.get("schema") or ""),
        "status": str(preview_pipeline.get("status") or ""),
        "pipeline_state": str(preview_pipeline.get("pipeline_state") or ""),
        "summary": dict(_summary(preview_pipeline)),
        "stage_reports": [
            {
                "stage_id": str(row.get("stage_id") or ""),
                "schema": str(row.get("schema") or ""),
                "status": str(row.get("status") or ""),
                "state": str(row.get("state") or ""),
            }
            for row in preview_pipeline.get("stage_reports", [])
            if isinstance(row, Mapping)
        ],
    }


def _checks(
    *,
    open_parameters_owner_response: Mapping[str, Any],
    owner_decision_presets: Mapping[str, Any],
    patch_bundle_manifest: Mapping[str, Any],
    preview_pipeline: Mapping[str, Any] | None,
) -> list[dict[str, str]]:
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
            "source_reports_passed",
            owner_decision_presets.get("status") == "PASS"
            and patch_bundle_manifest.get("status") == "PASS",
            "owner presets and patch bundle",
        ),
        _check(
            "pipeline_preview_consistent_with_response",
            (
                _summary(open_parameters_owner_response).get("pipeline_regeneration_ready") is True
                and preview_pipeline is not None
            )
            or (
                _summary(open_parameters_owner_response).get("pipeline_regeneration_ready") is not True
                and preview_pipeline is None
            ),
            str(open_parameters_owner_response.get("response_state") or ""),
        ),
        _check(
            "pipeline_preview_schema_valid",
            preview_pipeline is None or preview_pipeline.get("schema") == OWNER_TARGET_PIPELINE_SCHEMA,
            str((preview_pipeline or {}).get("schema") or "NOT_BUILT"),
        ),
        _check(
            "pipeline_preview_passed_when_built",
            preview_pipeline is None or preview_pipeline.get("status") == "PASS",
            str((preview_pipeline or {}).get("status") or "NOT_BUILT"),
        ),
        _check("no_owner_intake_write", True, "preview does not write intake"),
        _check("no_betaflight_repo_modification", True, "preview only"),
        _check("no_compile_or_flash", True, "compile/flash outside preview"),
        _check("no_live_uart_access", True, "file-only preview"),
    ]


def _preview_state(
    status: str,
    open_parameters_owner_response: Mapping[str, Any],
    preview_pipeline: Mapping[str, Any] | None,
) -> str:
    if status != "PASS":
        return "BLOCKED"
    if open_parameters_owner_response.get("response_state") != "READY_FOR_PIPELINE_REGENERATION":
        return "OWNER_RESPONSE_INCOMPLETE"
    if preview_pipeline is None:
        return "BLOCKED"
    if preview_pipeline.get("pipeline_state") == "READY_FOR_FORK_TARGET_REVIEW":
        return "READY_FOR_PIPELINE_REGENERATION"
    return "PIPELINE_PREVIEW_BLOCKED"


def _next_actions(
    open_parameters_owner_response: Mapping[str, Any],
    preview_pipeline: Mapping[str, Any] | None,
) -> list[dict[str, str]]:
    if open_parameters_owner_response.get("response_state") != "READY_FOR_PIPELINE_REGENERATION":
        return [
            _action("complete_owner_response", "Fill missing target and non-target owner parameters.", "OWNER_REQUIRED"),
            _action("rerun_owner_response_review", "Re-run owner response review with completed values.", "OWNER_REQUIRED"),
        ]
    if preview_pipeline is not None and preview_pipeline.get("pipeline_state") == "READY_FOR_FORK_TARGET_REVIEW":
        return [
            _action("owner_review_pipeline_preview", "Project owner reviews preview before writing canonical intake.", "OWNER_REVIEW"),
            _action("write_owner_decision_intake", "Write canonical intake only after owner approval.", "READY"),
            _action("regenerate_canonical_pipeline", "Regenerate canonical owner target pipeline after intake write.", "READY"),
        ]
    return [_action("inspect_pipeline_preview_blockers", "Inspect generated preview blockers.", "OWNER_REVIEW")]


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
