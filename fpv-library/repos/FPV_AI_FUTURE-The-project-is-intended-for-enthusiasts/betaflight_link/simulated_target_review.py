"""Simulation-only target review for the Betaflight FPV-AI fork path.

This report exercises the owner-decision pipeline with the synthetic
``simulated_fork_review_profile`` preset. It proves the dry-run plumbing can
reach READY_FOR_TARGET_REVIEW when decisions are present, while explicitly
marking the result as simulation-only and not valid for real hardware.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fpv_ai.betaflight_link.build_hook_mapper import (
    BUILD_HOOK_MAPPER_SCHEMA,
    build_betaflight_build_hook_mapper,
)
from fpv_ai.betaflight_link.fork_patch_bundle import FORK_PATCH_BUNDLE_SCHEMA
from fpv_ai.betaflight_link.owner_decision_intake import (
    OWNER_DECISION_INTAKE_SCHEMA,
    OwnerDecisionInput,
    build_betaflight_owner_decision_intake,
)
from fpv_ai.betaflight_link.owner_decision_presets import (
    OWNER_DECISION_PRESETS_SCHEMA,
    owner_decision_input_from_preset,
)
from fpv_ai.betaflight_link.owner_decision_review import (
    OWNER_DECISION_REVIEW_SCHEMA,
    build_betaflight_owner_decision_review,
)
from fpv_ai.betaflight_link.target_profile import (
    TARGET_PROFILE_SCHEMA,
    TargetProfileInput,
    build_betaflight_target_profile,
)

SIMULATED_TARGET_REVIEW_SCHEMA = "fpv_betaflight_simulated_target_review.v1"
SIMULATED_PRESET_ID = "simulated_fork_review_profile"


def build_betaflight_simulated_target_review(
    *,
    owner_decision_presets: Mapping[str, Any],
    patch_bundle_manifest: Mapping[str, Any],
    owner_decision_presets_path: Path | str | None = None,
    patch_bundle_manifest_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    preset_input = owner_decision_input_from_preset(owner_decision_presets, SIMULATED_PRESET_ID)
    intake = build_betaflight_owner_decision_intake(
        decisions=OwnerDecisionInput(**preset_input),
        project_root=root,
    )
    target_profile = build_betaflight_target_profile(
        patch_bundle_manifest=patch_bundle_manifest,
        profile=TargetProfileInput(**preset_input),
        project_root=root,
    )
    mapper = build_betaflight_build_hook_mapper(
        target_profile=target_profile,
        patch_bundle_manifest=patch_bundle_manifest,
        project_root=root,
    )
    review = build_betaflight_owner_decision_review(
        owner_decision_presets=owner_decision_presets,
        owner_decision_intake=intake,
        target_profile=target_profile,
        build_hook_mapper=mapper,
        project_root=root,
    )
    selected_preset = _selected_preset(owner_decision_presets, SIMULATED_PRESET_ID)
    generated_reports = _generated_reports(intake, target_profile, mapper, review)
    checks = _checks(
        owner_decision_presets=owner_decision_presets,
        patch_bundle_manifest=patch_bundle_manifest,
        selected_preset=selected_preset,
        intake=intake,
        target_profile=target_profile,
        mapper=mapper,
        review=review,
    )
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "schema": SIMULATED_TARGET_REVIEW_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "simulation_state": "READY_FOR_SYNTHETIC_TARGET_REVIEW" if status == "PASS" else "BLOCKED",
        "source_reports": [
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
        "summary": {
            "source_report_count": 2,
            "selected_preset_id": SIMULATED_PRESET_ID,
            "simulation_only": True,
            "real_hardware_authorized": False,
            "target_profile_state": str(target_profile.get("target_state") or ""),
            "build_hook_state": str(mapper.get("hook_state") or ""),
            "owner_review_state": str(review.get("review_state") or ""),
            "missing_owner_decision_count": int(_summary(intake).get("missing_owner_decision_count") or 0),
            "owner_blocker_count": int(_summary(mapper).get("owner_blocker_count") or 0),
            "artifact_hook_count": int(_summary(mapper).get("artifact_hook_count") or 0),
            "integration_hook_count": int(_summary(mapper).get("integration_hook_count") or 0),
            "patch_applied": False,
            "betaflight_repo_modified": False,
            "compile_attempted": False,
            "flash_attempted": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "selected_preset": selected_preset,
        "generated_reports": generated_reports,
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "simulation_only": True,
            "not_valid_for_real_hardware": True,
            "review_only": True,
            "does_not_select_hardware_automatically": True,
            "does_not_authorize_real_hardware_presets": True,
            "does_not_modify_betaflight_repo": True,
            "does_not_apply_patch": True,
            "does_not_compile_or_flash_betaflight": True,
            "does_not_execute_c_tests": True,
            "does_not_open_uart": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
            "does_not_command_motors_directly": True,
        },
    }


def write_betaflight_simulated_target_review(
    *,
    owner_decision_presets_json: Path,
    patch_bundle_manifest_json: Path,
    output_json: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    report = build_betaflight_simulated_target_review(
        owner_decision_presets=_read_json(owner_decision_presets_json),
        patch_bundle_manifest=_read_json(patch_bundle_manifest_json),
        owner_decision_presets_path=owner_decision_presets_json,
        patch_bundle_manifest_path=patch_bundle_manifest_json,
        project_root=project_root,
    )
    persisted = dict(report)
    persisted["simulation_review_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _selected_preset(owner_decision_presets: Mapping[str, Any], preset_id: str) -> dict[str, Any]:
    presets = owner_decision_presets.get("presets")
    if not isinstance(presets, list):
        return {}
    for row in presets:
        if isinstance(row, Mapping) and row.get("preset_id") == preset_id:
            return {
                "preset_id": str(row.get("preset_id") or ""),
                "title": str(row.get("title") or ""),
                "role": str(row.get("role") or ""),
                "target_profile_ready": row.get("target_profile_ready") is True,
                "simulation_only": row.get("simulation_only") is True,
                "owner_authorized_for_real_hardware": row.get("owner_authorized_for_real_hardware") is True,
                "missing_owner_decision_count": int(row.get("missing_owner_decision_count") or 0),
            }
    return {}


def _generated_reports(
    intake: Mapping[str, Any],
    target_profile: Mapping[str, Any],
    mapper: Mapping[str, Any],
    review: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return [
        _generated_report("owner_decision_intake", intake, OWNER_DECISION_INTAKE_SCHEMA, "intake_state"),
        _generated_report("target_profile", target_profile, TARGET_PROFILE_SCHEMA, "target_state"),
        _generated_report("build_hook_mapper", mapper, BUILD_HOOK_MAPPER_SCHEMA, "hook_state"),
        _generated_report("owner_decision_review", review, OWNER_DECISION_REVIEW_SCHEMA, "review_state"),
    ]


def _generated_report(
    report_id: str,
    payload: Mapping[str, Any],
    expected_schema: str,
    state_key: str,
) -> dict[str, Any]:
    return {
        "report_id": report_id,
        "schema": str(payload.get("schema") or ""),
        "expected_schema": expected_schema,
        "status": str(payload.get("status") or ""),
        "state": str(payload.get(state_key) or ""),
        "summary": dict(_summary(payload)),
    }


def _checks(
    *,
    owner_decision_presets: Mapping[str, Any],
    patch_bundle_manifest: Mapping[str, Any],
    selected_preset: Mapping[str, Any],
    intake: Mapping[str, Any],
    target_profile: Mapping[str, Any],
    mapper: Mapping[str, Any],
    review: Mapping[str, Any],
) -> list[dict[str, str]]:
    return [
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
        _check("source_reports_passed", _all_status_pass(owner_decision_presets, patch_bundle_manifest), "source reports"),
        _check("simulated_preset_found", selected_preset.get("preset_id") == SIMULATED_PRESET_ID, str(selected_preset.get("preset_id") or "")),
        _check("preset_is_simulation_only", selected_preset.get("simulation_only") is True, "simulation-only preset"),
        _check(
            "preset_not_real_hardware_authorized",
            selected_preset.get("owner_authorized_for_real_hardware") is False,
            "not valid for real hardware",
        ),
        _check("intake_ready", intake.get("intake_state") == "READY_FOR_TARGET_PROFILE", str(intake.get("intake_state") or "")),
        _check(
            "target_profile_ready",
            target_profile.get("target_state") == "READY_FOR_TARGET_REVIEW",
            str(target_profile.get("target_state") or ""),
        ),
        _check(
            "build_hook_mapper_ready",
            mapper.get("hook_state") == "READY_FOR_BUILD_HOOK_REVIEW",
            str(mapper.get("hook_state") or ""),
        ),
        _check("owner_review_ready", review.get("review_state") == "READY_FOR_TARGET_REVIEW", str(review.get("review_state") or "")),
        _check(
            "missing_decisions_zero",
            _summary_int(intake, "missing_owner_decision_count") == 0,
            "owner decisions filled",
        ),
        _check(
            "owner_blockers_zero",
            _summary_int(mapper, "owner_blocker_count") == 0,
            "owner blockers clear",
        ),
        _check("no_betaflight_repo_modification", True, "simulation review only"),
        _check("no_patch_apply_attempt", True, "patch application outside this review"),
        _check("no_compile_or_flash", True, "compile/flash outside this review"),
        _check("no_live_uart_access", True, "file-only review"),
    ]


def _all_status_pass(*reports: Mapping[str, Any]) -> bool:
    return all(report.get("status") == "PASS" for report in reports)


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


def _summary_int(payload: Mapping[str, Any], key: str) -> int:
    value = _summary(payload).get(key)
    return int(value) if isinstance(value, (int, float)) else -1


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
