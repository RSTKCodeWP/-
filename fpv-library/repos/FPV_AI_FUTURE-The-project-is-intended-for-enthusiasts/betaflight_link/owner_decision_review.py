"""Owner decision review packet for the Betaflight FPV-AI fork path.

The review packet combines the preset catalog, current owner intake, target
profile, and build hook mapper into one dry-run report. It records what is
still missing before a real FC target can be reviewed, but it does not choose
hardware automatically, modify a checkout, compile firmware, flash hardware,
open UART, or authorize hardware tests.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from fpv_ai.betaflight_link.build_hook_mapper import BUILD_HOOK_MAPPER_SCHEMA
from fpv_ai.betaflight_link.owner_decision_intake import OWNER_DECISION_INTAKE_SCHEMA
from fpv_ai.betaflight_link.owner_decision_presets import OWNER_DECISION_PRESETS_SCHEMA
from fpv_ai.betaflight_link.target_profile import TARGET_PROFILE_SCHEMA

OWNER_DECISION_REVIEW_SCHEMA = "fpv_betaflight_owner_decision_review.v1"


def build_betaflight_owner_decision_review(
    *,
    owner_decision_presets: Mapping[str, Any],
    owner_decision_intake: Mapping[str, Any],
    target_profile: Mapping[str, Any],
    build_hook_mapper: Mapping[str, Any],
    owner_decision_presets_path: Path | str | None = None,
    owner_decision_intake_path: Path | str | None = None,
    target_profile_path: Path | str | None = None,
    build_hook_mapper_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    missing_decisions = _missing_decisions(owner_decision_intake)
    presets = _preset_options(owner_decision_presets)
    next_actions = _next_actions(missing_decisions, presets)
    owner_blockers = _owner_blockers(build_hook_mapper)
    checks = _checks(
        owner_decision_presets=owner_decision_presets,
        owner_decision_intake=owner_decision_intake,
        target_profile=target_profile,
        build_hook_mapper=build_hook_mapper,
        presets=presets,
        missing_decisions=missing_decisions,
        owner_blockers=owner_blockers,
    )
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    target_selected = bool(_summary(target_profile).get("target_selected"))
    mapper_summary = _summary(build_hook_mapper)
    return {
        "schema": OWNER_DECISION_REVIEW_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "review_state": _review_state(status, target_selected),
        "source_reports": [
            _source_report(
                "owner_decision_presets",
                owner_decision_presets,
                owner_decision_presets_path,
                OWNER_DECISION_PRESETS_SCHEMA,
            ),
            _source_report(
                "owner_decision_intake",
                owner_decision_intake,
                owner_decision_intake_path,
                OWNER_DECISION_INTAKE_SCHEMA,
            ),
            _source_report("target_profile", target_profile, target_profile_path, TARGET_PROFILE_SCHEMA),
            _source_report(
                "build_hook_mapper",
                build_hook_mapper,
                build_hook_mapper_path,
                BUILD_HOOK_MAPPER_SCHEMA,
            ),
        ],
        "summary": {
            "source_report_count": 4,
            "available_preset_count": len(presets),
            "simulation_only_preset_count": sum(1 for row in presets if row["simulation_only"]),
            "missing_owner_decision_count": len(missing_decisions),
            "owner_blocker_count": len(owner_blockers),
            "target_selected": target_selected,
            "target_profile_ready": _summary(owner_decision_intake).get("target_profile_ready") is True,
            "artifact_hook_count": int(mapper_summary.get("artifact_hook_count") or 0),
            "integration_hook_count": int(mapper_summary.get("integration_hook_count") or 0),
            "next_action_count": len(next_actions),
            "patch_applied": False,
            "betaflight_repo_modified": False,
            "compile_attempted": False,
            "flash_attempted": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "missing_decisions": missing_decisions,
        "available_presets": presets,
        "owner_blockers": owner_blockers,
        "next_actions": next_actions,
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
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


def write_betaflight_owner_decision_review(
    *,
    owner_decision_presets_json: Path,
    owner_decision_intake_json: Path,
    target_profile_json: Path,
    build_hook_mapper_json: Path,
    output_json: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    report = build_betaflight_owner_decision_review(
        owner_decision_presets=_read_json(owner_decision_presets_json),
        owner_decision_intake=_read_json(owner_decision_intake_json),
        target_profile=_read_json(target_profile_json),
        build_hook_mapper=_read_json(build_hook_mapper_json),
        owner_decision_presets_path=owner_decision_presets_json,
        owner_decision_intake_path=owner_decision_intake_json,
        target_profile_path=target_profile_json,
        build_hook_mapper_path=build_hook_mapper_json,
        project_root=project_root,
    )
    persisted = dict(report)
    persisted["review_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _missing_decisions(owner_decision_intake: Mapping[str, Any]) -> list[dict[str, str]]:
    decisions = owner_decision_intake.get("decisions")
    if not isinstance(decisions, list):
        return []
    rows: list[dict[str, str]] = []
    for row in decisions:
        if not isinstance(row, Mapping) or row.get("status") != "OWNER_SELECTION_REQUIRED":
            continue
        rows.append(
            {
                "decision_id": str(row.get("decision_id") or ""),
                "detail": str(row.get("detail") or ""),
                "status": "OWNER_SELECTION_REQUIRED",
            }
        )
    return rows


def _preset_options(owner_decision_presets: Mapping[str, Any]) -> list[dict[str, Any]]:
    presets = owner_decision_presets.get("presets")
    if not isinstance(presets, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in presets:
        if not isinstance(row, Mapping):
            continue
        rows.append(
            {
                "preset_id": str(row.get("preset_id") or ""),
                "title": str(row.get("title") or ""),
                "role": str(row.get("role") or ""),
                "target_profile_ready": row.get("target_profile_ready") is True,
                "simulation_only": row.get("simulation_only") is True,
                "owner_authorized_for_real_hardware": row.get("owner_authorized_for_real_hardware") is True,
                "missing_owner_decision_count": int(row.get("missing_owner_decision_count") or 0),
                "status": str(row.get("status") or ""),
            }
        )
    return rows


def _owner_blockers(build_hook_mapper: Mapping[str, Any]) -> list[dict[str, str]]:
    blockers = build_hook_mapper.get("owner_blockers")
    if not isinstance(blockers, list):
        return []
    rows: list[dict[str, str]] = []
    for row in blockers:
        if not isinstance(row, Mapping):
            continue
        rows.append(
            {
                "blocker_id": str(row.get("blocker_id") or ""),
                "detail": str(row.get("detail") or ""),
                "status": str(row.get("status") or ""),
            }
        )
    return rows


def _next_actions(
    missing_decisions: Sequence[Mapping[str, str]],
    presets: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    actions = [
        _action(
            "review_missing_owner_decisions",
            "Review the missing Betaflight repo, branch, FC target, UART, serial mode, and voltage fields.",
            "OWNER_REQUIRED",
        ),
        _action(
            "manual_owner_selection",
            "Run fpv_betaflight_owner_decision_intake.py with explicit owner-selected values.",
            "OWNER_REQUIRED",
        ),
        _action(
            "regenerate_target_reports",
            "Regenerate target_profile.json and build_hook_mapper.json after owner decisions are entered.",
            "OWNER_REQUIRED",
        ),
    ]
    if any(row.get("preset_id") == "simulated_fork_review_profile" for row in presets):
        actions.append(
            _action(
                "optional_simulated_pipeline_review",
                "Use preset simulated_fork_review_profile only to verify dry-run plumbing, not real hardware.",
                "DRY_RUN_ONLY",
            )
        )
    if not missing_decisions:
        actions.append(
            _action(
                "ready_for_target_review",
                "Review build/runtime hook mapping for the selected target before any fork patching.",
                "READY",
            )
        )
    return actions


def _checks(
    *,
    owner_decision_presets: Mapping[str, Any],
    owner_decision_intake: Mapping[str, Any],
    target_profile: Mapping[str, Any],
    build_hook_mapper: Mapping[str, Any],
    presets: Sequence[Mapping[str, Any]],
    missing_decisions: Sequence[Mapping[str, str]],
    owner_blockers: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    target_selected = _summary(target_profile).get("target_selected") is True
    return [
        _check(
            "owner_decision_presets_schema_valid",
            owner_decision_presets.get("schema") == OWNER_DECISION_PRESETS_SCHEMA,
            str(owner_decision_presets.get("schema") or ""),
        ),
        _check(
            "owner_decision_intake_schema_valid",
            owner_decision_intake.get("schema") == OWNER_DECISION_INTAKE_SCHEMA,
            str(owner_decision_intake.get("schema") or ""),
        ),
        _check(
            "target_profile_schema_valid",
            target_profile.get("schema") == TARGET_PROFILE_SCHEMA,
            str(target_profile.get("schema") or ""),
        ),
        _check(
            "build_hook_mapper_schema_valid",
            build_hook_mapper.get("schema") == BUILD_HOOK_MAPPER_SCHEMA,
            str(build_hook_mapper.get("schema") or ""),
        ),
        _check("source_reports_passed", _all_source_status_pass(owner_decision_presets, owner_decision_intake, target_profile, build_hook_mapper), "source statuses"),
        _check("presets_available", bool(presets), str(len(presets))),
        _check(
            "owner_blockers_match_missing_decisions",
            (target_selected and not owner_blockers) or (not target_selected and bool(missing_decisions)),
            f"missing={len(missing_decisions)},blockers={len(owner_blockers)}",
        ),
        _check(
            "no_real_hardware_presets_authorized",
            all(row.get("owner_authorized_for_real_hardware") is False for row in presets),
            "preset catalog stays dry-run only",
        ),
        _check("no_betaflight_repo_modification", True, "review only"),
        _check("no_patch_apply_attempt", True, "patch application outside this review"),
        _check("no_compile_or_flash", True, "compile/flash outside this review"),
        _check("no_live_uart_access", True, "file-only review"),
    ]


def _review_state(status: str, target_selected: bool) -> str:
    if status != "PASS":
        return "BLOCKED"
    if target_selected:
        return "READY_FOR_TARGET_REVIEW"
    return "OWNER_DECISION_REQUIRED"


def _all_source_status_pass(*reports: Mapping[str, Any]) -> bool:
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
