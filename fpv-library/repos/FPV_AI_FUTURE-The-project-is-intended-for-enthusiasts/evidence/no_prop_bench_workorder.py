"""No-prop bench workorder draft for FPV AI Gate-Lock.

This module turns the runtime dry-run closeout into a reviewable bench plan. It
does not enable adapters, open hardware, authorize tests, or claim field proof.
The first hardware test remains a project-owner decision.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fpv_ai.control.speed import SpeedMode, SpeedPolicy

WORKORDER_SCHEMA = "fpv_no_prop_bench_workorder.v1"
CLOSEOUT_SCHEMA = "fpv_runtime_readiness_closeout.v1"


@dataclass(frozen=True)
class BenchPhaseSpec:
    phase_id: str
    title: str
    status: str
    detail: str
    hardware_access_allowed: bool = False


@dataclass(frozen=True)
class OwnerDecisionSpec:
    decision_id: str
    owner: str
    detail: str


@dataclass(frozen=True)
class PreconditionSpec:
    precondition_id: str
    owner: str
    detail: str


BENCH_PHASES = (
    BenchPhaseSpec(
        "owner_scope_review",
        "Project owner defines first hardware test scope",
        "OWNER_DECISION_REQUIRED",
        "No bench action starts until the project owner defines the scope and envelope.",
    ),
    BenchPhaseSpec(
        "physical_no_prop_prep",
        "Prepare no-prop bench rig",
        "PLANNED_NOT_STARTED",
        "Propellers must be removed; frame, power, and independent cut-off are checked.",
    ),
    BenchPhaseSpec(
        "repeat_software_dry_run",
        "Repeat current runtime dry-run evidence",
        "PLANNED_NOT_STARTED",
        "Regenerate mission, protocol, RPi runtime, launcher, bundle, and closeout reports.",
    ),
    BenchPhaseSpec(
        "bench_configuration_review",
        "Review explicit bench configuration",
        "BLOCKED_BY_OWNER_AUTHORIZATION",
        "Live adapters remain disabled until a separate bench configuration is reviewed.",
    ),
    BenchPhaseSpec(
        "fc_uart_no_prop_packet_acceptance",
        "Flight-controller UART packet acceptance with no propellers",
        "BLOCKED_BY_OWNER_AUTHORIZATION",
        "Only after owner approval: verify frame decode, sequence, heartbeat, and timeout.",
    ),
    BenchPhaseSpec(
        "bench_evidence_closeout",
        "Preserve no-prop bench evidence",
        "PLANNED_NOT_STARTED",
        "Write logs, hashes, operator notes, and acceptance/failure reasons after bench.",
    ),
)

OWNER_DECISIONS = (
    OwnerDecisionSpec(
        "first_hardware_test_scope",
        "project_owner",
        "Define exactly what the first hardware test may and may not do.",
    ),
    OwnerDecisionSpec(
        "speed_envelope",
        "project_owner",
        "Select speed mode and operator limit for the bench; software only records the limit.",
    ),
    OwnerDecisionSpec(
        "flight_controller_target",
        "hardware_owner",
        "Select FC board, Betaflight FPV-AI fork baseline, UART port, and voltage levels.",
    ),
    OwnerDecisionSpec(
        "kill_power_cut_acceptance",
        "hardware_owner",
        "Confirm independent kill/power cut outside Raspberry Pi software.",
    ),
    OwnerDecisionSpec(
        "logging_and_evidence_retention",
        "test_owner",
        "Choose log path, time source, evidence retention, and review owner.",
    ),
)

PRECONDITIONS = (
    PreconditionSpec(
        "propellers_removed",
        "hardware_owner",
        "All propellers are removed before any powered bench interaction.",
    ),
    PreconditionSpec(
        "independent_kill_verified",
        "hardware_owner",
        "Manual kill/power cut is physically tested before live adapters are enabled.",
    ),
    PreconditionSpec(
        "uart_voltage_reviewed",
        "hardware_owner",
        "UART voltage levels, ground, connector, and port role are reviewed.",
    ),
    PreconditionSpec(
        "bench_config_reviewed",
        "software_owner",
        "A separate bench config explicitly enables only the intended live adapter.",
    ),
    PreconditionSpec(
        "operator_present",
        "project_owner",
        "Operator is present and can stop the test immediately.",
    ),
    PreconditionSpec(
        "logs_ready",
        "test_owner",
        "Command, heartbeat, FC response, and launcher status logs have a write target.",
    ),
)


def build_no_prop_bench_workorder(
    *,
    readiness_closeout: Mapping[str, Any],
    readiness_closeout_path: Path | None = None,
    project_root: Path | None = None,
    speed_mode: SpeedMode = SpeedMode.FIXED_SPEED,
    operator_limit_mps: float | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    speed_envelope = _speed_envelope(speed_mode, operator_limit_mps)
    blockers = _imported_blockers(readiness_closeout)
    phases = [_phase_entry(phase) for phase in BENCH_PHASES]
    decisions = [_owner_decision_entry(decision) for decision in OWNER_DECISIONS]
    preconditions = [_precondition_entry(precondition) for precondition in PRECONDITIONS]
    checks = _workorder_checks(readiness_closeout, speed_envelope, blockers)
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"

    return {
        "schema": WORKORDER_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "workorder_state": "DRAFT_OWNER_REVIEW_REQUIRED" if status == "PASS" else "SOURCE_NOT_READY",
        "source_readiness_closeout": _source_closeout_entry(readiness_closeout, readiness_closeout_path),
        "summary": {
            "project_owner_defines_first_hardware_test": True,
            "no_prop_bench_authorized": False,
            "hardware_test_authorized": False,
            "live_adapters_enabled": False,
            "flight_commands_published": False,
            "field_proof_claimed": False,
            "training_launched": False,
            "phase_count": len(phases),
            "owner_decision_count": len(decisions),
            "required_precondition_count": len(preconditions),
            "imported_blocker_count": len(blockers),
            "selected_speed_mode": speed_envelope["mode"],
            "operator_limit_mps": speed_envelope["operator_limit_mps"],
        },
        "speed_envelope": speed_envelope,
        "checks": checks,
        "bench_phases": phases,
        "owner_decisions_required": decisions,
        "required_preconditions": preconditions,
        "imported_blockers": blockers,
        "safety_boundary": {
            "dry_run_only": True,
            "workorder_only": True,
            "no_prop_bench_authorized": False,
            "hardware_test_authorized": False,
            "project_owner_defines_first_hardware_test": True,
            "propellers_must_be_removed": True,
            "does_not_open_live_cameras": True,
            "does_not_read_gpio": True,
            "does_not_open_uart": True,
            "does_not_start_service": True,
            "does_not_publish_flight_commands": True,
            "does_not_launch_training": True,
        },
    }


def write_no_prop_bench_workorder(
    *,
    readiness_closeout_json: Path,
    output_json: Path,
    project_root: Path | None = None,
    speed_mode: SpeedMode = SpeedMode.FIXED_SPEED,
    operator_limit_mps: float | None = None,
) -> dict[str, Any]:
    readiness_closeout = _read_json(readiness_closeout_json)
    workorder = build_no_prop_bench_workorder(
        readiness_closeout=readiness_closeout,
        readiness_closeout_path=readiness_closeout_json,
        project_root=project_root,
        speed_mode=speed_mode,
        operator_limit_mps=operator_limit_mps,
    )
    persisted = dict(workorder)
    persisted["workorder_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _speed_envelope(speed_mode: SpeedMode, operator_limit_mps: float | None) -> dict[str, Any]:
    policy = SpeedPolicy.default()
    profile = policy.profile(speed_mode)
    if operator_limit_mps is not None:
        policy = policy.with_operator_limit(speed_mode, operator_limit_mps)
        profile = policy.profile(speed_mode)
    return {
        "mode": speed_mode.value,
        "min_mps": profile.min_mps,
        "default_mps": profile.default_mps,
        "max_mps": profile.max_mps,
        "operator_limit_mps": profile.operator_limit_mps,
        "resolved_locked_speed_mps": policy.resolve_speed_mps(
            speed_mode,
            requested_mps=profile.default_mps,
            target_confidence=1.0,
            tracking_state="LOCKED",
        ),
        "resolved_reacquire_speed_mps": policy.resolve_speed_mps(
            speed_mode,
            requested_mps=profile.default_mps,
            target_confidence=0.5,
            tracking_state="REACQUIRE",
        ),
        "operator_adjustable": profile.adjustable_by_operator,
        "owner_authorization_required_for_hardware": True,
    }


def _workorder_checks(
    readiness_closeout: Mapping[str, Any],
    speed_envelope: Mapping[str, Any],
    blockers: list[dict[str, str]],
) -> list[dict[str, str]]:
    summary = _mapping(readiness_closeout.get("summary"))
    safety = _mapping(readiness_closeout.get("safety_boundary"))
    return [
        _check("source_closeout_schema_valid", readiness_closeout.get("schema") == CLOSEOUT_SCHEMA, str(readiness_closeout.get("schema") or "")),
        _check("source_closeout_passed", readiness_closeout.get("status") == "PASS", str(readiness_closeout.get("status") or "")),
        _check("source_closeout_hardware_not_authorized", summary.get("hardware_test_authorized") is False, "source closeout"),
        _check("source_closeout_no_prop_not_authorized", summary.get("no_prop_bench_authorized") is False, "source closeout"),
        _check("source_closeout_field_proof_not_claimed", summary.get("field_proof_claimed") is False, "source closeout"),
        _check("source_closeout_no_live_hardware", safety.get("does_not_open_uart") is True, "source safety boundary"),
        _check("owner_scope_required", True, "project owner defines the first hardware test"),
        _check("workorder_does_not_authorize_hardware", True, "draft plan only"),
        _check("live_adapters_disabled_in_plan", True, "no adapter enable in this workorder"),
        _check("propellers_removed_required", True, "no-prop bench precondition"),
        _check(
            "operator_speed_limit_inside_profile",
            float(speed_envelope["min_mps"])
            <= float(speed_envelope["operator_limit_mps"])
            <= float(speed_envelope["max_mps"]),
            str(speed_envelope["operator_limit_mps"]),
        ),
        _check("closeout_blockers_imported", bool(blockers), str(len(blockers))),
    ]


def _source_closeout_entry(
    readiness_closeout: Mapping[str, Any],
    readiness_closeout_path: Path | None,
) -> dict[str, Any]:
    summary = _mapping(readiness_closeout.get("summary"))
    return {
        "path": str(readiness_closeout_path or readiness_closeout.get("closeout_path") or ""),
        "schema": str(readiness_closeout.get("schema") or ""),
        "status": str(readiness_closeout.get("status") or ""),
        "sha256": _sha256(readiness_closeout_path)
        if readiness_closeout_path and readiness_closeout_path.exists()
        else "",
        "readiness_state": str(readiness_closeout.get("readiness_state") or ""),
        "dry_run_gate_count": int(summary.get("dry_run_gate_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
    }


def _imported_blockers(readiness_closeout: Mapping[str, Any]) -> list[dict[str, str]]:
    blockers = readiness_closeout.get("blockers_before_no_prop_bench")
    if not isinstance(blockers, list):
        return []
    imported: list[dict[str, str]] = []
    for blocker in blockers:
        if not isinstance(blocker, Mapping):
            continue
        imported.append({
            "blocker_id": str(blocker.get("blocker_id") or ""),
            "status": str(blocker.get("status") or "BLOCKING"),
            "owner": str(blocker.get("owner") or ""),
            "detail": str(blocker.get("detail") or ""),
        })
    return imported


def _phase_entry(phase: BenchPhaseSpec) -> dict[str, Any]:
    return {
        "phase_id": phase.phase_id,
        "title": phase.title,
        "status": phase.status,
        "detail": phase.detail,
        "hardware_access_allowed": phase.hardware_access_allowed,
    }


def _owner_decision_entry(decision: OwnerDecisionSpec) -> dict[str, str]:
    return {
        "decision_id": decision.decision_id,
        "status": "REQUIRED_NOT_PROVIDED",
        "owner": decision.owner,
        "detail": decision.detail,
    }


def _precondition_entry(precondition: PreconditionSpec) -> dict[str, str]:
    return {
        "precondition_id": precondition.precondition_id,
        "status": "REQUIRED_NOT_SATISFIED",
        "owner": precondition.owner,
        "detail": precondition.detail,
    }


def _mapping(value: object) -> Mapping[str, Any]:
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
