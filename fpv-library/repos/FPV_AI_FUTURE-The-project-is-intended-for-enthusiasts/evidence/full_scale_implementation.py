"""Full-scale implementation closeout for FPV AI Gate-Lock.

The closeout aggregates the software dry-run, Betaflight target-build gate,
Raspberry Pi runtime, owner-parameter completion, and no-prop workorder into
one project-level state. It is evidence of implementation scope only: it never
fills owner values, enables live adapters, compiles/flashes Betaflight, opens
UART, authorizes hardware, or claims production model acceptance.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from fpv_ai.betaflight_link.target_build_readiness import TARGET_BUILD_READINESS_SCHEMA
from fpv_ai.evidence.no_prop_bench_workorder import WORKORDER_SCHEMA
from fpv_ai.evidence.owner_parameters_completion import OWNER_PARAMETERS_COMPLETION_SCHEMA
from fpv_ai.evidence.runtime_bundle import BUNDLE_SCHEMA
from fpv_ai.evidence.runtime_closeout import CLOSEOUT_SCHEMA
from fpv_ai.runtime_rpi.dry_run import READINESS_SCHEMA as RPI_READINESS_SCHEMA

FULL_SCALE_IMPLEMENTATION_SCHEMA = "fpv_full_scale_implementation_closeout.v1"


def build_full_scale_implementation_closeout(
    *,
    owner_parameters_completion: Mapping[str, Any],
    target_build_readiness: Mapping[str, Any],
    rpi_runtime_readiness: Mapping[str, Any],
    no_prop_bench_workorder: Mapping[str, Any],
    mvp_runtime_evidence_bundle: Mapping[str, Any],
    runtime_readiness_closeout: Mapping[str, Any],
    owner_parameters_completion_path: Path | str | None = None,
    target_build_readiness_path: Path | str | None = None,
    rpi_runtime_readiness_path: Path | str | None = None,
    no_prop_bench_workorder_path: Path | str | None = None,
    mvp_runtime_evidence_bundle_path: Path | str | None = None,
    runtime_readiness_closeout_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    source_reports = [
        _source_report(
            "owner_parameters_completion",
            owner_parameters_completion,
            owner_parameters_completion_path,
            OWNER_PARAMETERS_COMPLETION_SCHEMA,
        ),
        _source_report(
            "target_build_readiness",
            target_build_readiness,
            target_build_readiness_path,
            TARGET_BUILD_READINESS_SCHEMA,
        ),
        _source_report(
            "rpi_runtime_readiness",
            rpi_runtime_readiness,
            rpi_runtime_readiness_path,
            RPI_READINESS_SCHEMA,
        ),
        _source_report(
            "no_prop_bench_workorder",
            no_prop_bench_workorder,
            no_prop_bench_workorder_path,
            WORKORDER_SCHEMA,
        ),
        _source_report(
            "mvp_runtime_evidence_bundle",
            mvp_runtime_evidence_bundle,
            mvp_runtime_evidence_bundle_path,
            BUNDLE_SCHEMA,
        ),
        _source_report(
            "runtime_readiness_closeout",
            runtime_readiness_closeout,
            runtime_readiness_closeout_path,
            CLOSEOUT_SCHEMA,
        ),
    ]
    owner_summary = _mapping(owner_parameters_completion.get("summary"))
    target_summary = _mapping(target_build_readiness.get("summary"))
    rpi_summary = _mapping(rpi_runtime_readiness.get("summary"))
    workorder_summary = _mapping(no_prop_bench_workorder.get("summary"))
    bundle_summary = _mapping(mvp_runtime_evidence_bundle.get("summary"))
    closeout_summary = _mapping(runtime_readiness_closeout.get("summary"))
    source_ready = all(row["status"] == "PASS" and row["schema"] == row["expected_schema"] for row in source_reports)
    owner_target_missing_count = int(owner_summary.get("target_missing_count") or 0)
    owner_non_target_missing_count = int(owner_summary.get("non_target_missing_count") or 0)
    target_build_real_ready = target_summary.get("real_target_build_ready") is True
    live_adapters_enabled = int(rpi_summary.get("live_enabled_adapter_count") or 0) > 0
    no_prop_authorized = workorder_summary.get("no_prop_bench_authorized") is True
    hardware_authorized = workorder_summary.get("hardware_test_authorized") is True
    production_model_accepted = owner_summary.get("production_model_accepted") is True
    stages = _implementation_stages(
        owner_target_missing_count=owner_target_missing_count,
        owner_non_target_missing_count=owner_non_target_missing_count,
        target_build_real_ready=target_build_real_ready,
        live_adapters_enabled=live_adapters_enabled,
        no_prop_authorized=no_prop_authorized,
        hardware_authorized=hardware_authorized,
        production_model_accepted=production_model_accepted,
        mvp_runtime_complete=bool(closeout_summary.get("mvp_runtime_dry_run_complete")),
    )
    requirements = _button_start_requirements(
        owner_target_missing_count=owner_target_missing_count,
        owner_non_target_missing_count=owner_non_target_missing_count,
        target_build_real_ready=target_build_real_ready,
        live_adapters_enabled=live_adapters_enabled,
        no_prop_authorized=no_prop_authorized,
        hardware_authorized=hardware_authorized,
        production_model_accepted=production_model_accepted,
    )
    blocked_reasons = _blocked_reasons(
        owner_parameters_completion=owner_parameters_completion,
        target_build_readiness=target_build_readiness,
        no_prop_bench_workorder=no_prop_bench_workorder,
        requirements=requirements,
    )
    next_actions = _next_actions(requirements)
    checks = _checks(
        source_reports=source_reports,
        owner_summary=owner_summary,
        target_summary=target_summary,
        rpi_summary=rpi_summary,
        workorder_summary=workorder_summary,
        bundle_summary=bundle_summary,
        closeout_summary=closeout_summary,
    )
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    first_button_start_ready = all(row["status"] == "READY" for row in requirements)
    full_scale_ready = (
        source_ready
        and first_button_start_ready
        and target_build_real_ready
        and live_adapters_enabled
        and no_prop_authorized
        and hardware_authorized
        and production_model_accepted
    )
    return {
        "schema": FULL_SCALE_IMPLEMENTATION_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "full_scale_state": _full_scale_state(
            status=status,
            source_ready=source_ready,
            owner_target_missing_count=owner_target_missing_count,
            owner_non_target_missing_count=owner_non_target_missing_count,
            target_build_real_ready=target_build_real_ready,
            live_adapters_enabled=live_adapters_enabled,
            no_prop_authorized=no_prop_authorized,
            hardware_authorized=hardware_authorized,
            production_model_accepted=production_model_accepted,
        ),
        "source_reports": source_reports,
        "summary": {
            "source_report_count": len(source_reports),
            "software_dry_run_complete": bool(closeout_summary.get("mvp_runtime_dry_run_complete")),
            "dry_run_evidence_passed": mvp_runtime_evidence_bundle.get("status") == "PASS",
            "runtime_capability_count": int(closeout_summary.get("implemented_capability_count") or 0),
            "runtime_dry_run_gate_count": int(closeout_summary.get("dry_run_gate_count") or 0),
            "owner_target_missing_count": owner_target_missing_count,
            "owner_non_target_missing_count": owner_non_target_missing_count,
            "owner_action_count": int(owner_summary.get("total_owner_action_count") or 0),
            "target_build_real_ready": target_build_real_ready,
            "rpi_live_adapters_enabled": live_adapters_enabled,
            "rpi_live_enabled_adapter_count": int(rpi_summary.get("live_enabled_adapter_count") or 0),
            "no_prop_bench_workorder_ready": no_prop_bench_workorder.get("status") == "PASS",
            "no_prop_bench_authorized": False,
            "hardware_test_authorized": False,
            "production_model_accepted": production_model_accepted,
            "edge_model_export_ready": owner_summary.get("edge_model_export_ready") is True,
            "first_button_start_ready": first_button_start_ready,
            "full_scale_ready": full_scale_ready,
            "field_proof_claimed": False,
            "flight_commands_published": False,
            "training_launched": False,
        },
        "implementation_stages": stages,
        "first_button_start_requirements": requirements,
        "blocked_reasons": blocked_reasons,
        "next_actions": next_actions,
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "full_scale_closeout_only": True,
            "does_not_fill_owner_values": True,
            "does_not_select_hardware_automatically": True,
            "does_not_enable_live_adapters": True,
            "does_not_open_live_cameras": True,
            "does_not_read_gpio": True,
            "does_not_open_uart": True,
            "does_not_apply_patch": True,
            "does_not_compile_or_flash_betaflight": True,
            "does_not_authorize_no_prop_bench": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
            "does_not_claim_field_proof": True,
            "does_not_launch_training": True,
        },
    }


def write_full_scale_implementation_closeout(
    *,
    owner_parameters_completion_json: Path,
    target_build_readiness_json: Path,
    rpi_runtime_readiness_json: Path,
    no_prop_bench_workorder_json: Path,
    mvp_runtime_evidence_bundle_json: Path,
    runtime_readiness_closeout_json: Path,
    output_json: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    report = build_full_scale_implementation_closeout(
        owner_parameters_completion=_read_json(owner_parameters_completion_json),
        target_build_readiness=_read_json(target_build_readiness_json),
        rpi_runtime_readiness=_read_json(rpi_runtime_readiness_json),
        no_prop_bench_workorder=_read_json(no_prop_bench_workorder_json),
        mvp_runtime_evidence_bundle=_read_json(mvp_runtime_evidence_bundle_json),
        runtime_readiness_closeout=_read_json(runtime_readiness_closeout_json),
        owner_parameters_completion_path=owner_parameters_completion_json,
        target_build_readiness_path=target_build_readiness_json,
        rpi_runtime_readiness_path=rpi_runtime_readiness_json,
        no_prop_bench_workorder_path=no_prop_bench_workorder_json,
        mvp_runtime_evidence_bundle_path=mvp_runtime_evidence_bundle_json,
        runtime_readiness_closeout_path=runtime_readiness_closeout_json,
        project_root=project_root,
    )
    persisted = dict(report)
    persisted["closeout_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _implementation_stages(
    *,
    owner_target_missing_count: int,
    owner_non_target_missing_count: int,
    target_build_real_ready: bool,
    live_adapters_enabled: bool,
    no_prop_authorized: bool,
    hardware_authorized: bool,
    production_model_accepted: bool,
    mvp_runtime_complete: bool,
) -> list[dict[str, str]]:
    return [
        _stage(
            "software_runtime_dry_run",
            "Synthetic/offline FPV AI runtime and evidence bundle",
            "IMPLEMENTED_DRY_RUN" if mvp_runtime_complete else "BLOCKED_SOURCE_REPORT",
            "Mission, reacquire, command cadence, protocol, RPi runtime, launcher screen, and evidence closeout.",
        ),
        _stage(
            "betaflight_fork_target_build",
            "Betaflight FPV-AI target build preparation",
            "READY_FOR_MANUAL_REVIEW" if target_build_real_ready else "BLOCKED_OWNER_INPUT",
            "Requires exact FC target, AI UART, and voltage before patch/build review.",
        ),
        _stage(
            "rpi_edge_live_runtime",
            "Raspberry Pi live camera/GPIO/UART/screen runtime",
            "READY_FOR_BENCH_CONFIG_REVIEW" if owner_non_target_missing_count == 0 else "BLOCKED_OWNER_INPUT",
            "Live adapters stay disabled until owner hardware fields and bench config are reviewed.",
        ),
        _stage(
            "launcher_button_start_path",
            "Button-confirmed lock and launch state machine",
            "IMPLEMENTED_DRY_RUN",
            "Button-confirmed target lock, AUX1 arm request, armed idle, release, throttle ramp, and AI active are modeled in dry-run.",
        ),
        _stage(
            "fpv_gate_model_acceptance",
            "Production FPV racing gate detector acceptance",
            "READY" if production_model_accepted else "SKIPPED_NOT_ACCEPTED",
            "Dataset/training/export was skipped by project decision; production model remains unaccepted.",
        ),
        _stage(
            "no_prop_bench",
            "No-prop bench workorder",
            "READY" if no_prop_authorized else "DRAFT_OWNER_REVIEW_REQUIRED",
            "No-prop workorder exists, but owner authorization is not granted by software.",
        ),
        _stage(
            "real_button_start",
            "Physical button to AI-controlled FPV start",
            "READY" if hardware_authorized and live_adapters_enabled else "NOT_READY",
            "Requires owner-approved hardware scope, live adapter config, no-prop acceptance, and model/target readiness.",
        ),
    ]


def _button_start_requirements(
    *,
    owner_target_missing_count: int,
    owner_non_target_missing_count: int,
    target_build_real_ready: bool,
    live_adapters_enabled: bool,
    no_prop_authorized: bool,
    hardware_authorized: bool,
    production_model_accepted: bool,
) -> list[dict[str, str]]:
    return [
        _requirement("owner_target_fields_complete", owner_target_missing_count == 0, "FC target, AI UART, voltage, repo, branch, and serial mode."),
        _requirement("owner_hardware_fields_complete", owner_non_target_missing_count == 0, "Camera, accelerator, target/gate dataset spec, speed, release thresholds, kill, and first-test scope."),
        _requirement("target_build_ready", target_build_real_ready, "Betaflight target build readiness gate reports real_target_build_ready."),
        _requirement("live_adapters_enabled_under_bench_config", live_adapters_enabled, "Camera/GPIO/UART/screen adapters are explicitly enabled by a reviewed bench config."),
        _requirement("production_model_accepted_or_owner_experimental_scope", production_model_accepted, "Production FPV gate model is accepted; skipped training keeps this blocked for real flight claims."),
        _requirement("no_prop_bench_authorized", no_prop_authorized, "Project owner authorizes the no-prop bench scope."),
        _requirement("hardware_test_authorized", hardware_authorized, "Project owner authorizes the hardware test; this software never grants it."),
    ]


def _blocked_reasons(
    *,
    owner_parameters_completion: Mapping[str, Any],
    target_build_readiness: Mapping[str, Any],
    no_prop_bench_workorder: Mapping[str, Any],
    requirements: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    blocked = [
        {
            "blocker_id": str(row.get("requirement_id") or ""),
            "status": str(row.get("status") or ""),
            "detail": str(row.get("detail") or ""),
        }
        for row in requirements
        if row.get("status") != "READY"
    ]
    blocked.extend(_source_blockers("owner_parameter", owner_parameters_completion.get("owner_parameter_rows"), "field_id"))
    blocked.extend(_source_blockers("target_build", target_build_readiness.get("blocked_reasons"), "blocker_id"))
    blocked.extend(_source_blockers("no_prop_bench", no_prop_bench_workorder.get("imported_blockers"), "blocker_id"))
    return blocked


def _next_actions(requirements: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    missing = {str(row.get("requirement_id") or "") for row in requirements if row.get("status") != "READY"}
    actions: list[dict[str, str]] = []
    if "owner_target_fields_complete" in missing:
        actions.append(_action("fill_betaflight_target_fields", "Fill fc_target, ai_uart_port, and electrical_voltage_level.", "OWNER_REQUIRED"))
    if "owner_hardware_fields_complete" in missing:
        actions.append(_action("fill_remaining_hardware_fields", "Fill camera, accelerator, target/gate dataset spec, speed, release, kill, and first-test scope fields.", "OWNER_REQUIRED"))
    if "target_build_ready" in missing:
        actions.append(_action("rerun_target_build_readiness", "Regenerate Betaflight target build readiness after owner target fields are complete.", "SOFTWARE_READY_AFTER_OWNER_INPUT"))
    if "production_model_accepted_or_owner_experimental_scope" in missing:
        actions.append(_action("keep_model_status_explicit", "Keep model unaccepted unless owner reopens dataset/training/export or marks an experimental no-flight scope.", "OWNER_REVIEW"))
    if "no_prop_bench_authorized" in missing:
        actions.append(_action("review_no_prop_bench_workorder", "Owner reviews the no-prop bench workorder; software does not authorize it.", "OWNER_REQUIRED"))
    if "hardware_test_authorized" in missing:
        actions.append(_action("keep_hardware_disabled", "Keep live adapters, UART, compile/flash, and hardware tests disabled until explicit owner authorization.", "BLOCKED_UNTIL_OWNER_AUTHORIZATION"))
    return actions


def _checks(
    *,
    source_reports: Sequence[Mapping[str, str]],
    owner_summary: Mapping[str, Any],
    target_summary: Mapping[str, Any],
    rpi_summary: Mapping[str, Any],
    workorder_summary: Mapping[str, Any],
    bundle_summary: Mapping[str, Any],
    closeout_summary: Mapping[str, Any],
) -> list[dict[str, str]]:
    return [
        _check("source_reports_passed", all(row["status"] == "PASS" for row in source_reports), _failed_sources(source_reports)),
        _check("source_schemas_match", all(row["schema"] == row["expected_schema"] for row in source_reports), _failed_schema_sources(source_reports)),
        _check("software_dry_run_complete", bool(closeout_summary.get("mvp_runtime_dry_run_complete")), "runtime closeout"),
        _check("evidence_bundle_passed", int(bundle_summary.get("fail_required_report_count") or 0) == 0, str(bundle_summary.get("fail_required_report_count") or 0)),
        _check("owner_missing_values_recorded", int(owner_summary.get("target_missing_count") or 0) >= 0, str(owner_summary.get("target_missing_count") or 0)),
        _check("target_build_state_recorded", isinstance(target_summary.get("real_target_build_ready"), bool), str(target_summary.get("real_target_build_ready"))),
        _check("rpi_live_adapter_state_recorded", int(rpi_summary.get("live_enabled_adapter_count") or 0) >= 0, str(rpi_summary.get("live_enabled_adapter_count") or 0)),
        _check("no_prop_bench_not_authorized", workorder_summary.get("no_prop_bench_authorized") is False, "owner authorization required"),
        _check("hardware_not_authorized", workorder_summary.get("hardware_test_authorized") is False, "owner authorization required"),
        _check("model_training_not_claimed", owner_summary.get("training_launched") is False, "training skipped"),
        _check("flight_commands_not_published", workorder_summary.get("flight_commands_published") is False, "dry-run only"),
        _check("field_proof_not_claimed", bundle_summary.get("field_proof_claimed") is False, "synthetic evidence only"),
    ]


def _full_scale_state(
    *,
    status: str,
    source_ready: bool,
    owner_target_missing_count: int,
    owner_non_target_missing_count: int,
    target_build_real_ready: bool,
    live_adapters_enabled: bool,
    no_prop_authorized: bool,
    hardware_authorized: bool,
    production_model_accepted: bool,
) -> str:
    if status != "PASS" or not source_ready:
        return "BLOCKED_SOURCE_REPORT"
    if owner_target_missing_count or owner_non_target_missing_count:
        return "SOFTWARE_DRY_RUN_COMPLETE_OWNER_VALUES_REQUIRED"
    if not target_build_real_ready:
        return "READY_FOR_BETAFLIGHT_TARGET_BUILD_REVIEW"
    if not production_model_accepted:
        return "MODEL_ACCEPTANCE_SKIPPED_NOT_FLIGHT_READY"
    if not live_adapters_enabled:
        return "READY_FOR_LIVE_ADAPTER_BENCH_CONFIG_REVIEW"
    if not no_prop_authorized or not hardware_authorized:
        return "READY_FOR_OWNER_APPROVED_NO_PROP_BENCH_REVIEW"
    return "FULL_SCALE_READY_FOR_OWNER_HARDWARE_REVIEW"


def _stage(stage_id: str, title: str, status: str, detail: str) -> dict[str, str]:
    return {
        "stage_id": stage_id,
        "title": title,
        "status": status,
        "detail": detail,
    }


def _requirement(requirement_id: str, ready: bool, detail: str) -> dict[str, str]:
    return {
        "requirement_id": requirement_id,
        "status": "READY" if ready else "BLOCKED",
        "detail": detail,
    }


def _action(action_id: str, detail: str, status: str) -> dict[str, str]:
    return {
        "action_id": action_id,
        "status": status,
        "detail": detail,
    }


def _source_blockers(prefix: str, rows: object, id_key: str) -> list[dict[str, str]]:
    if not isinstance(rows, list):
        return []
    blocked: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        status = str(row.get("status") or "")
        if status in {"SELECTED", "READY", "COMPLETE"}:
            continue
        blocker_id = str(row.get(id_key) or "")
        if not blocker_id:
            continue
        blocked.append(
            {
                "blocker_id": f"{prefix}_{blocker_id}",
                "status": status,
                "detail": str(row.get("detail") or row.get("blocks") or ""),
            }
        )
    return blocked


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


def _failed_sources(source_reports: Sequence[Mapping[str, str]]) -> str:
    return ",".join(row["report_id"] for row in source_reports if row["status"] != "PASS")


def _failed_schema_sources(source_reports: Sequence[Mapping[str, str]]) -> str:
    return ",".join(row["report_id"] for row in source_reports if row["schema"] != row["expected_schema"])


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
