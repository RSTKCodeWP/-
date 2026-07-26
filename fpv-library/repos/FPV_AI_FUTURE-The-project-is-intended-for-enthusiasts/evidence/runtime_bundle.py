"""MVP runtime evidence bundle dry-run for FPV AI Gate-Lock.

The bundle hashes and summarizes the current file-based runtime artifacts. It
is acceptance evidence for a synthetic/offline dry-run only, not field proof and
not permission to run hardware.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

BUNDLE_SCHEMA = "fpv_mvp_runtime_evidence_bundle.v1"
FORBIDDEN_TRUE_FLAGS = (
    "training_launched",
    "cameras_opened",
    "gpio_read",
    "uart_opened",
    "screen_device_opened",
    "systemd_installation_performed",
    "service_started",
    "hardware_test_authorized",
    "flight_commands_published",
)
PASS_REQUIRED_ARTIFACTS = {
    "mission_report",
    "timeline_report",
    "command_cadence_report",
    "protocol_readiness_report",
    "betaflight_rc_control_report",
    "betaflight_fork_contract_report",
    "betaflight_parser_sim_report",
    "betaflight_c_reference_report",
    "betaflight_payload_decoder_contract",
    "betaflight_integration_manifest",
    "betaflight_ai_mode_state_machine",
    "betaflight_mode_manager_c_reference_report",
    "betaflight_fork_unit_tests",
    "betaflight_fork_patch_plan",
    "betaflight_fork_patch_bundle",
    "betaflight_owner_decision_presets",
    "betaflight_owner_decision_intake",
    "betaflight_owner_decision_review",
    "betaflight_owner_target_promotion_gate",
    "betaflight_owner_target_pipeline",
    "betaflight_simulated_target_review",
    "betaflight_target_profile",
    "betaflight_build_hook_mapper",
    "betaflight_target_build_readiness",
    "bench_hil_report",
    "rpi_runtime_readiness_report",
    "launcher_screen_report",
    "open_parameters_owner_action_packet",
    "owner_parameters_completion_report",
    "open_parameters_owner_packet",
    "open_parameters_owner_response",
    "open_parameters_owner_response_application_dry_run",
    "open_parameters_owner_response_approval_gate",
    "open_parameters_owner_response_approval_template",
    "open_parameters_owner_response_apply_plan",
    "open_parameters_owner_response_intake_bridge",
    "open_parameters_owner_response_template",
    "open_parameters_pipeline_preview",
    "open_parameters_register",
    "reacquire_dry_run_report",
}


@dataclass(frozen=True)
class EvidenceArtifactSpec:
    artifact_id: str
    relative_path: str
    role: str
    required: bool = True


ARTIFACT_SPECS = (
    EvidenceArtifactSpec("mission_report", "reports/fpv/mission_dry_run_launcher_events/mission_dry_run_report.json", "mission dry-run summary"),
    EvidenceArtifactSpec("mission_timeline", "reports/fpv/mission_dry_run_launcher_events/mission_timeline.json", "joined mission timeline"),
    EvidenceArtifactSpec("timeline_report", "reports/fpv/mission_dry_run_launcher_events/mission_timeline_report.json", "timeline acceptance summary"),
    EvidenceArtifactSpec("launcher_events", "reports/fpv/launcher_events.synthetic.json", "synthetic launcher event input"),
    EvidenceArtifactSpec("scheduled_command_sequence", "reports/fpv/command_scheduler/scheduled_command_sequence.json", "runtime scheduled commands"),
    EvidenceArtifactSpec("command_cadence_report", "reports/fpv/command_scheduler/command_cadence_report.json", "runtime command cadence acceptance"),
    EvidenceArtifactSpec("protocol_readiness_report", "reports/fpv/protocol_readiness/protocol_readiness_report.json", "scheduled command protocol readiness"),
    EvidenceArtifactSpec("scheduled_transport_frames", "reports/fpv/protocol_readiness/scheduled_transport_frames.json", "scheduled UART frame dry-run bytes"),
    EvidenceArtifactSpec("scheduled_transport_report", "reports/fpv/protocol_readiness/scheduled_transport_dry_run_report.json", "scheduled transport dry-run report"),
    EvidenceArtifactSpec("scheduled_watchdog_report", "reports/fpv/protocol_readiness/scheduled_watchdog_report.json", "scheduled watchdog report"),
    EvidenceArtifactSpec("betaflight_rc_control_sequence", "reports/fpv/betaflight_rc_control/rc_control_sequence.json", "Betaflight virtual receiver roll/pitch/yaw/throttle + AUX1 arm sequence"),
    EvidenceArtifactSpec("betaflight_rc_control_report", "reports/fpv/betaflight_rc_control/rc_control_report.json", "Betaflight AUX1 arm and RC channel dry-run report"),
    EvidenceArtifactSpec("betaflight_fork_contract_report", "reports/fpv/betaflight_fork/fork_interface_contract.json", "Betaflight FPV-AI fork interface contract"),
    EvidenceArtifactSpec("betaflight_fork_c_header", "reports/fpv/betaflight_fork/fpv_ai_uart_contract_v1.h", "generated C header for Betaflight FPV-AI fork"),
    EvidenceArtifactSpec("betaflight_parser_sim_report", "reports/fpv/betaflight_fork/parser_sim_report.json", "Betaflight-side parser simulator report"),
    EvidenceArtifactSpec("betaflight_c_reference_report", "reports/fpv/betaflight_fork/c_reference_report.json", "Betaflight C reference parser report"),
    EvidenceArtifactSpec("betaflight_c_parser", "reports/fpv/betaflight_fork/fpv_ai_uart_parser_v1.c", "Betaflight C reference parser skeleton"),
    EvidenceArtifactSpec("betaflight_c_golden_fixture", "reports/fpv/betaflight_fork/fpv_ai_uart_golden_frames_v1.c", "Betaflight C golden frame fixture"),
    EvidenceArtifactSpec("betaflight_payload_decoder_contract", "reports/fpv/betaflight_fork/payload_decoder_contract.json", "Betaflight payload decoder adapter contract"),
    EvidenceArtifactSpec("betaflight_payload_decoder_adapter", "reports/fpv/betaflight_fork/fpv_ai_payload_decoder_adapter_v1.c", "Betaflight payload decoder adapter skeleton"),
    EvidenceArtifactSpec("betaflight_integration_manifest", "reports/fpv/betaflight_fork/integration_manifest.json", "Betaflight fork integration manifest"),
    EvidenceArtifactSpec("betaflight_ai_mode_state_machine", "reports/fpv/betaflight_fork/ai_mode_state_machine_contract.json", "Betaflight AI mode state-machine contract"),
    EvidenceArtifactSpec("betaflight_mode_manager_c_reference_report", "reports/fpv/betaflight_fork/mode_manager_c_reference_report.json", "Betaflight AI mode manager C reference report"),
    EvidenceArtifactSpec("betaflight_mode_manager_c_header", "reports/fpv/betaflight_fork/fpv_ai_mode_manager_v1.h", "Betaflight AI mode manager C header"),
    EvidenceArtifactSpec("betaflight_mode_manager_c_source", "reports/fpv/betaflight_fork/fpv_ai_mode_manager_v1.c", "Betaflight AI mode manager C source skeleton"),
    EvidenceArtifactSpec("betaflight_mode_manager_c_fixture", "reports/fpv/betaflight_fork/fpv_ai_mode_manager_fixture_v1.c", "Betaflight AI mode manager C fixture"),
    EvidenceArtifactSpec("betaflight_fork_unit_tests", "reports/fpv/betaflight_fork/fork_unit_tests_contract.json", "Betaflight fork-side unit test contract"),
    EvidenceArtifactSpec("betaflight_fork_patch_plan", "reports/fpv/betaflight_fork/fork_patch_plan.json", "Betaflight fork patch plan"),
    EvidenceArtifactSpec("betaflight_fork_patch_bundle", "reports/fpv/betaflight_fork/fork_patch_bundle_manifest.json", "Betaflight fork patch bundle manifest"),
    EvidenceArtifactSpec("betaflight_owner_decision_presets", "reports/fpv/betaflight_fork/owner_decision_presets.json", "Betaflight owner decision preset catalog"),
    EvidenceArtifactSpec("betaflight_owner_decision_intake", "reports/fpv/betaflight_fork/owner_decision_intake.json", "Betaflight owner decision intake"),
    EvidenceArtifactSpec("betaflight_owner_decision_review", "reports/fpv/betaflight_fork/owner_decision_review.json", "Betaflight owner decision review packet"),
    EvidenceArtifactSpec("betaflight_owner_target_promotion_gate", "reports/fpv/betaflight_fork/owner_target_promotion_gate.json", "Betaflight owner target promotion gate"),
    EvidenceArtifactSpec("betaflight_owner_target_pipeline", "reports/fpv/betaflight_fork/owner_target_pipeline.json", "Betaflight owner target pipeline"),
    EvidenceArtifactSpec("betaflight_simulated_target_review", "reports/fpv/betaflight_fork/simulated_target_review.json", "Betaflight simulated target review"),
    EvidenceArtifactSpec("betaflight_target_profile", "reports/fpv/betaflight_fork/target_profile.json", "Betaflight target profile draft"),
    EvidenceArtifactSpec("betaflight_build_hook_mapper", "reports/fpv/betaflight_fork/build_hook_mapper.json", "Betaflight build hook mapper"),
    EvidenceArtifactSpec("betaflight_target_build_readiness", "reports/fpv/betaflight_fork/target_build_readiness.json", "Betaflight target build readiness gate"),
    EvidenceArtifactSpec("bench_hil_report", "reports/fpv/bench_hil/bench_hil_report.json", "bench/HIL dry-run report"),
    EvidenceArtifactSpec("rpi_runtime_readiness_report", "reports/fpv/rpi_runtime/rpi_runtime_readiness_report.json", "Raspberry Pi runtime readiness dry-run"),
    EvidenceArtifactSpec("rpi_runtime_loop_report", "reports/fpv/rpi_runtime/rpi_runtime_loop_report.json", "Raspberry Pi runtime loop dry-run"),
    EvidenceArtifactSpec("rpi_device_adapter_audit", "reports/fpv/rpi_runtime/device_adapter_audit_report.json", "Raspberry Pi device adapter audit"),
    EvidenceArtifactSpec("rpi_service_plan", "reports/fpv/rpi_runtime/rpi_runtime_service_plan.json", "systemd service dry-run plan"),
    EvidenceArtifactSpec("rpi_service_unit", "reports/fpv/rpi_runtime/fpv-ai-gate-lock.service", "systemd service template"),
    EvidenceArtifactSpec("launcher_screen_report", "reports/fpv/launcher_screen/launcher_screen_report.json", "launcher screen/status dry-run"),
    EvidenceArtifactSpec("reacquire_dry_run_report", "reports/fpv/tracking/reacquire_dry_run_report.json", "predictive/reacquire search-window dry-run report"),
    EvidenceArtifactSpec("open_parameters_owner_action_packet", "reports/fpv/evidence_bundle/open_parameters_owner_action_packet.json", "MVP open-parameter owner action packet"),
    EvidenceArtifactSpec("owner_parameters_completion_report", "reports/fpv/evidence_bundle/owner_parameters_completion_report.json", "MVP owner-parameter completion gate"),
    EvidenceArtifactSpec("open_parameters_owner_packet", "reports/fpv/evidence_bundle/open_parameters_owner_packet.json", "MVP open-parameter owner packet"),
    EvidenceArtifactSpec("open_parameters_owner_response", "reports/fpv/evidence_bundle/open_parameters_owner_response.json", "MVP open-parameter owner response review"),
    EvidenceArtifactSpec("open_parameters_owner_response_application_dry_run", "reports/fpv/evidence_bundle/open_parameters_owner_response_application_dry_run.json", "MVP open-parameter owner response application dry-run"),
    EvidenceArtifactSpec("open_parameters_owner_response_approval_gate", "reports/fpv/evidence_bundle/open_parameters_owner_response_approval_gate.json", "MVP open-parameter owner response approval gate"),
    EvidenceArtifactSpec("open_parameters_owner_response_approval_template", "reports/fpv/evidence_bundle/open_parameters_owner_response_approval_template.json", "MVP open-parameter owner response approval template"),
    EvidenceArtifactSpec("open_parameters_owner_response_apply_plan", "reports/fpv/evidence_bundle/open_parameters_owner_response_apply_plan.json", "MVP open-parameter owner response application plan"),
    EvidenceArtifactSpec("open_parameters_owner_response_intake_bridge", "reports/fpv/evidence_bundle/open_parameters_owner_response_intake_bridge.json", "MVP open-parameter owner response to intake bridge"),
    EvidenceArtifactSpec("open_parameters_owner_response_template", "reports/fpv/evidence_bundle/open_parameters_owner_response_template.json", "MVP open-parameter owner response template"),
    EvidenceArtifactSpec("open_parameters_pipeline_preview", "reports/fpv/evidence_bundle/open_parameters_pipeline_preview.json", "MVP open-parameter pipeline preview"),
    EvidenceArtifactSpec("open_parameters_register", "reports/fpv/evidence_bundle/open_parameters_register.json", "MVP open-parameter register"),
)


def build_mvp_runtime_evidence_bundle(*, project_root: Path | None = None) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    artifacts = [_artifact_entry(root, spec) for spec in ARTIFACT_SPECS]
    reports = {entry["artifact_id"]: entry["json_payload"] for entry in artifacts if isinstance(entry.get("json_payload"), dict)}
    checks = _bundle_checks(artifacts, reports)
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    missing_count = sum(1 for entry in artifacts if entry["required"] and not entry["exists"])
    fail_report_count = sum(
        1
        for entry in artifacts
        if entry["artifact_id"] in PASS_REQUIRED_ARTIFACTS and entry["status"] != "PASS"
    )
    acceptance = _acceptance(reports)
    public_artifacts = [_public_artifact_entry(entry) for entry in artifacts]
    return {
        "schema": BUNDLE_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "bundle_type": "synthetic_mvp_runtime_dry_run",
        "summary": {
            "artifact_count": len(artifacts),
            "required_artifact_count": sum(1 for entry in artifacts if entry["required"]),
            "missing_required_artifact_count": missing_count,
            "pass_required_report_count": len(PASS_REQUIRED_ARTIFACTS) - fail_report_count,
            "fail_required_report_count": fail_report_count,
            "manifest_sha256": _manifest_sha256(public_artifacts),
            "field_proof_claimed": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
            "training_launched": False,
        },
        "acceptance": acceptance,
        "checks": checks,
        "artifacts": public_artifacts,
        "safety_boundary": {
            "dry_run_only": True,
            "synthetic_evidence_only": True,
            "field_proof_claimed": False,
            "does_not_launch_training": True,
            "does_not_open_live_cameras": True,
            "does_not_read_gpio": True,
            "does_not_open_uart": True,
            "does_not_open_screen_device": True,
            "does_not_install_systemd_unit": True,
            "does_not_start_service": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
        },
    }


def write_mvp_runtime_evidence_bundle(*, output_json: Path, project_root: Path | None = None) -> dict[str, Any]:
    bundle = build_mvp_runtime_evidence_bundle(project_root=project_root)
    persisted = dict(bundle)
    persisted["bundle_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _artifact_entry(root: Path, spec: EvidenceArtifactSpec) -> dict[str, Any]:
    path = root / spec.relative_path
    exists = path.exists()
    json_payload: dict[str, Any] | None = None
    json_valid = False
    if exists and path.suffix == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                json_payload = payload
                json_valid = True
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            json_payload = None
    return {
        "artifact_id": spec.artifact_id,
        "role": spec.role,
        "path": spec.relative_path,
        "absolute_path": str(path),
        "required": spec.required,
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else 0,
        "sha256": _sha256(path) if exists else "",
        "json_valid": json_valid,
        "schema": str(json_payload.get("schema") or "") if json_payload else "",
        "status": _artifact_status(spec.artifact_id, json_payload, exists),
        "generated_at": str(json_payload.get("generated_at") or "") if json_payload else "",
        "json_payload": json_payload,
    }


def _public_artifact_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "artifact_id": str(entry["artifact_id"]),
        "role": str(entry["role"]),
        "path": str(entry["path"]),
        "required": bool(entry["required"]),
        "exists": bool(entry["exists"]),
        "size_bytes": int(entry["size_bytes"]),
        "sha256": str(entry["sha256"]),
        "json_valid": bool(entry["json_valid"]),
        "schema": str(entry["schema"]),
        "status": str(entry["status"]),
        "generated_at": str(entry["generated_at"]),
    }


def _artifact_status(artifact_id: str, payload: Mapping[str, Any] | None, exists: bool) -> str:
    if not exists:
        return "MISSING"
    if payload is None:
        return "NO_STATUS"
    status = payload.get("status")
    if isinstance(status, str):
        return status
    return "NO_STATUS"


def _bundle_checks(artifacts: list[dict[str, Any]], reports: Mapping[str, Mapping[str, Any]]) -> list[dict[str, str]]:
    missing = [entry["artifact_id"] for entry in artifacts if entry["required"] and not entry["exists"]]
    non_pass = [
        artifact_id
        for artifact_id in sorted(PASS_REQUIRED_ARTIFACTS)
        if str(reports.get(artifact_id, {}).get("status") or "") != "PASS"
    ]
    forbidden_true = _forbidden_true_flags(reports)
    acceptance = _acceptance(reports)
    return [
        _check("required_artifacts_present", not missing, ",".join(missing)),
        _check("required_reports_passed", not non_pass, ",".join(non_pass)),
        _check("mission_complete", acceptance["mission_complete"], "mission report final state"),
        _check("scheduled_commands_ready", acceptance["scheduled_commands_ready"], "command cadence report"),
        _check("protocol_ready", acceptance["protocol_ready"], "protocol readiness report"),
        _check("bench_hil_ready", acceptance["bench_hil_ready"], "bench/HIL report"),
        _check("rpi_runtime_ready", acceptance["rpi_runtime_ready"], "RPi runtime readiness"),
        _check("launcher_screen_ready", acceptance["launcher_screen_ready"], "launcher screen report"),
        _check("forbidden_hardware_flags_clear", not forbidden_true, ",".join(forbidden_true)),
        _check("field_proof_not_claimed", not acceptance["field_proof_claimed"], "synthetic dry-run only"),
    ]


def _acceptance(reports: Mapping[str, Mapping[str, Any]]) -> dict[str, bool]:
    mission = _summary(reports, "mission_report")
    cadence = _summary(reports, "command_cadence_report")
    protocol = _summary(reports, "protocol_readiness_report")
    bench = _summary(reports, "bench_hil_report")
    rpi = _summary(reports, "rpi_runtime_readiness_report")
    screen = _summary(reports, "launcher_screen_report")
    return {
        "mvp_runtime_dry_run_complete": (
            bool(mission.get("mission_complete"))
            and _report_pass(reports, "command_cadence_report")
            and _report_pass(reports, "protocol_readiness_report")
            and _report_pass(reports, "bench_hil_report")
            and _report_pass(reports, "rpi_runtime_readiness_report")
            and _report_pass(reports, "launcher_screen_report")
        ),
        "mission_complete": bool(mission.get("mission_complete")),
        "scheduled_commands_ready": _report_pass(reports, "command_cadence_report")
        and int(cadence.get("stale_gap_count") or 0) == 0
        and int(cadence.get("scheduled_command_count") or 0) > 0,
        "protocol_ready": _report_pass(reports, "protocol_readiness_report")
        and int(protocol.get("rejected_command_count") or 0) == 0
        and int(protocol.get("timeout_count") or 0) == 0,
        "bench_hil_ready": _report_pass(reports, "bench_hil_report")
        and int(bench.get("stale_block_count") or 0) == 0,
        "rpi_runtime_ready": _report_pass(reports, "rpi_runtime_readiness_report")
        and int(rpi.get("live_enabled_adapter_count") or 0) == 0,
        "launcher_screen_ready": _report_pass(reports, "launcher_screen_report")
        and str(screen.get("final_screen_state") or "") == "COMPLETE",
        "field_proof_claimed": False,
        "hardware_test_authorized": False,
        "flight_commands_published": False,
    }


def _summary(reports: Mapping[str, Mapping[str, Any]], artifact_id: str) -> Mapping[str, Any]:
    report = reports.get(artifact_id, {})
    summary = report.get("summary") if isinstance(report, Mapping) else {}
    return summary if isinstance(summary, Mapping) else {}


def _report_pass(reports: Mapping[str, Mapping[str, Any]], artifact_id: str) -> bool:
    return str(reports.get(artifact_id, {}).get("status") or "") == "PASS"


def _forbidden_true_flags(reports: Mapping[str, Mapping[str, Any]]) -> list[str]:
    violations: list[str] = []
    for artifact_id, report in reports.items():
        for location_name, section in (("summary", report.get("summary")), ("safety_boundary", report.get("safety_boundary"))):
            if not isinstance(section, Mapping):
                continue
            for flag in FORBIDDEN_TRUE_FLAGS:
                if section.get(flag) is True:
                    violations.append(f"{artifact_id}.{location_name}.{flag}")
    return sorted(violations)


def _manifest_sha256(artifacts: list[dict[str, Any]]) -> str:
    canonical = json.dumps(artifacts, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
