"""Owner target promotion gate for the Betaflight FPV-AI fork path.

The promotion gate separates two ideas that must stay distinct:

* the simulation-only target review proves the dry-run plumbing works;
* a real fork target can advance only after owner-selected repo, branch, FC,
  UART, serial mode, and voltage decisions are present.

This report is still file-only. It does not apply patches, modify a Betaflight
checkout, compile firmware, flash hardware, open UART, authorize a bench test,
or publish flight commands.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from fpv_ai.betaflight_link.build_hook_mapper import BUILD_HOOK_MAPPER_SCHEMA
from fpv_ai.betaflight_link.owner_decision_intake import OWNER_DECISION_INTAKE_SCHEMA
from fpv_ai.betaflight_link.owner_decision_review import OWNER_DECISION_REVIEW_SCHEMA
from fpv_ai.betaflight_link.simulated_target_review import SIMULATED_TARGET_REVIEW_SCHEMA
from fpv_ai.betaflight_link.target_profile import TARGET_PROFILE_SCHEMA

OWNER_TARGET_PROMOTION_GATE_SCHEMA = "fpv_betaflight_owner_target_promotion_gate.v1"


def build_betaflight_owner_target_promotion_gate(
    *,
    owner_decision_intake: Mapping[str, Any],
    target_profile: Mapping[str, Any],
    build_hook_mapper: Mapping[str, Any],
    owner_decision_review: Mapping[str, Any],
    simulated_target_review: Mapping[str, Any],
    owner_decision_intake_path: Path | str | None = None,
    target_profile_path: Path | str | None = None,
    build_hook_mapper_path: Path | str | None = None,
    owner_decision_review_path: Path | str | None = None,
    simulated_target_review_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    requirements = _promotion_requirements(
        owner_decision_intake=owner_decision_intake,
        target_profile=target_profile,
        build_hook_mapper=build_hook_mapper,
        owner_decision_review=owner_decision_review,
        simulated_target_review=simulated_target_review,
    )
    blockers = _blockers(requirements)
    checks = _checks(
        owner_decision_intake=owner_decision_intake,
        target_profile=target_profile,
        build_hook_mapper=build_hook_mapper,
        owner_decision_review=owner_decision_review,
        simulated_target_review=simulated_target_review,
    )
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    promotion_state = _promotion_state(status, blockers)
    mapper_summary = _summary(build_hook_mapper)
    intake_summary = _summary(owner_decision_intake)
    target_summary = _summary(target_profile)
    return {
        "schema": OWNER_TARGET_PROMOTION_GATE_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "promotion_state": promotion_state,
        "source_reports": [
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
            _source_report(
                "owner_decision_review",
                owner_decision_review,
                owner_decision_review_path,
                OWNER_DECISION_REVIEW_SCHEMA,
            ),
            _source_report(
                "simulated_target_review",
                simulated_target_review,
                simulated_target_review_path,
                SIMULATED_TARGET_REVIEW_SCHEMA,
            ),
        ],
        "summary": {
            "source_report_count": 5,
            "owner_intake_state": str(owner_decision_intake.get("intake_state") or ""),
            "target_profile_state": str(target_profile.get("target_state") or ""),
            "build_hook_state": str(build_hook_mapper.get("hook_state") or ""),
            "owner_review_state": str(owner_decision_review.get("review_state") or ""),
            "simulated_review_state": str(simulated_target_review.get("simulation_state") or ""),
            "missing_owner_decision_count": _mapping_int(
                intake_summary,
                "missing_owner_decision_count",
            ),
            "owner_blocker_count": _mapping_int(mapper_summary, "owner_blocker_count"),
            "target_selected": target_summary.get("target_selected") is True,
            "simulation_only_proof_available": _simulation_only_proof_available(
                simulated_target_review,
            ),
            "simulation_used_for_real_target": False,
            "promotion_ready": promotion_state == "READY_FOR_FORK_TARGET_REVIEW",
            "artifact_hook_count": _mapping_int(mapper_summary, "artifact_hook_count"),
            "integration_hook_count": _mapping_int(mapper_summary, "integration_hook_count"),
            "patch_applied": False,
            "betaflight_repo_modified": False,
            "compile_attempted": False,
            "flash_attempted": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "promotion_requirements": requirements,
        "blockers": blockers,
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "promotion_gate_only": True,
            "simulation_not_valid_for_real_hardware": True,
            "does_not_use_simulation_as_real_target": True,
            "does_not_select_hardware_automatically": True,
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


def write_betaflight_owner_target_promotion_gate(
    *,
    owner_decision_intake_json: Path,
    target_profile_json: Path,
    build_hook_mapper_json: Path,
    owner_decision_review_json: Path,
    simulated_target_review_json: Path,
    output_json: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    report = build_betaflight_owner_target_promotion_gate(
        owner_decision_intake=_read_json(owner_decision_intake_json),
        target_profile=_read_json(target_profile_json),
        build_hook_mapper=_read_json(build_hook_mapper_json),
        owner_decision_review=_read_json(owner_decision_review_json),
        simulated_target_review=_read_json(simulated_target_review_json),
        owner_decision_intake_path=owner_decision_intake_json,
        target_profile_path=target_profile_json,
        build_hook_mapper_path=build_hook_mapper_json,
        owner_decision_review_path=owner_decision_review_json,
        simulated_target_review_path=simulated_target_review_json,
        project_root=project_root,
    )
    persisted = dict(report)
    persisted["promotion_gate_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _promotion_requirements(
    *,
    owner_decision_intake: Mapping[str, Any],
    target_profile: Mapping[str, Any],
    build_hook_mapper: Mapping[str, Any],
    owner_decision_review: Mapping[str, Any],
    simulated_target_review: Mapping[str, Any],
) -> list[dict[str, str]]:
    intake_summary = _summary(owner_decision_intake)
    target_summary = _summary(target_profile)
    mapper_summary = _summary(build_hook_mapper)
    review_summary = _summary(owner_decision_review)
    return [
        _requirement(
            "owner_decisions_complete",
            (
                owner_decision_intake.get("intake_state") == "READY_FOR_TARGET_PROFILE"
                and _mapping_int(intake_summary, "missing_owner_decision_count") == 0
                and intake_summary.get("target_profile_ready") is True
            ),
            "Owner-selected Betaflight repo, branch, FC target, AI UART, serial mode, and voltage are required.",
        ),
        _requirement(
            "target_profile_ready",
            (
                target_profile.get("target_state") == "READY_FOR_TARGET_REVIEW"
                and _mapping_int(target_summary, "missing_owner_decision_count") == 0
                and target_summary.get("target_selected") is True
            ),
            "Target profile must be ready for fork target review.",
        ),
        _requirement(
            "build_hook_mapper_ready",
            (
                build_hook_mapper.get("hook_state") == "READY_FOR_BUILD_HOOK_REVIEW"
                and _mapping_int(mapper_summary, "owner_blocker_count") == 0
                and mapper_summary.get("target_selected") is True
            ),
            "Build/runtime hook mapper must be ready for target review.",
        ),
        _requirement(
            "owner_decision_review_ready",
            (
                owner_decision_review.get("review_state") == "READY_FOR_TARGET_REVIEW"
                and _mapping_int(review_summary, "missing_owner_decision_count") == 0
                and _mapping_int(review_summary, "owner_blocker_count") == 0
                and review_summary.get("target_selected") is True
            ),
            "Owner decision review packet must have no missing decisions or owner blockers.",
        ),
        _requirement(
            "simulation_not_used_as_real_target",
            _simulation_safety_ok(simulated_target_review),
            "Simulation-only proof must remain marked as not valid for real hardware.",
        ),
    ]


def _checks(
    *,
    owner_decision_intake: Mapping[str, Any],
    target_profile: Mapping[str, Any],
    build_hook_mapper: Mapping[str, Any],
    owner_decision_review: Mapping[str, Any],
    simulated_target_review: Mapping[str, Any],
) -> list[dict[str, str]]:
    return [
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
        _check(
            "owner_decision_review_schema_valid",
            owner_decision_review.get("schema") == OWNER_DECISION_REVIEW_SCHEMA,
            str(owner_decision_review.get("schema") or ""),
        ),
        _check(
            "simulated_target_review_schema_valid",
            simulated_target_review.get("schema") == SIMULATED_TARGET_REVIEW_SCHEMA,
            str(simulated_target_review.get("schema") or ""),
        ),
        _check(
            "source_reports_passed",
            _all_status_pass(
                owner_decision_intake,
                target_profile,
                build_hook_mapper,
                owner_decision_review,
                simulated_target_review,
            ),
            "source reports",
        ),
        _check(
            "simulated_review_is_simulation_only",
            _summary(simulated_target_review).get("simulation_only") is True,
            "simulation-only review",
        ),
        _check(
            "simulated_review_not_real_hardware_authorized",
            _summary(simulated_target_review).get("real_hardware_authorized") is False,
            "not real hardware authorized",
        ),
        _check(
            "simulated_review_not_valid_for_real_hardware",
            _safety(simulated_target_review).get("not_valid_for_real_hardware") is True,
            "simulation proof remains separate from real target readiness",
        ),
        _check("simulation_not_used_for_real_target", True, "promotion gate never consumes simulation as owner selection"),
        _check("no_betaflight_repo_modification", True, "promotion gate only"),
        _check("no_patch_apply_attempt", True, "patch application outside this gate"),
        _check("no_compile_or_flash", True, "compile/flash outside this gate"),
        _check("no_live_uart_access", True, "file-only gate"),
    ]


def _promotion_state(status: str, blockers: Sequence[Mapping[str, str]]) -> str:
    if status != "PASS":
        return "BLOCKED"
    if blockers:
        return "BLOCKED_OWNER_DECISION_REQUIRED"
    return "READY_FOR_FORK_TARGET_REVIEW"


def _requirement(requirement_id: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "requirement_id": requirement_id,
        "status": "SATISFIED" if passed else "BLOCKING",
        "detail": detail,
    }


def _blockers(requirements: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "blocker_id": str(row.get("requirement_id") or ""),
            "status": "BLOCKING",
            "detail": str(row.get("detail") or ""),
        }
        for row in requirements
        if row.get("status") == "BLOCKING"
    ]


def _simulation_only_proof_available(simulated_target_review: Mapping[str, Any]) -> bool:
    return simulated_target_review.get("status") == "PASS" and _simulation_safety_ok(simulated_target_review)


def _simulation_safety_ok(simulated_target_review: Mapping[str, Any]) -> bool:
    summary = _summary(simulated_target_review)
    safety = _safety(simulated_target_review)
    return (
        simulated_target_review.get("schema") == SIMULATED_TARGET_REVIEW_SCHEMA
        and simulated_target_review.get("status") == "PASS"
        and summary.get("simulation_only") is True
        and summary.get("real_hardware_authorized") is False
        and safety.get("simulation_only") is True
        and safety.get("not_valid_for_real_hardware") is True
        and safety.get("does_not_authorize_hardware_test") is True
    )


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


def _safety(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    safety = payload.get("safety_boundary")
    return safety if isinstance(safety, Mapping) else {}


def _mapping_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
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
