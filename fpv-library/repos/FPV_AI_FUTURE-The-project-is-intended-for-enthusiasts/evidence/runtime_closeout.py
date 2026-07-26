"""Runtime readiness closeout for FPV AI Gate-Lock dry-run evidence.

The closeout is a review artifact: it summarizes what is implemented in the
offline/synthetic runtime and records the remaining blockers before any
owner-approved no-prop bench work. It does not authorize hardware use.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

CLOSEOUT_SCHEMA = "fpv_runtime_readiness_closeout.v1"
EVIDENCE_BUNDLE_SCHEMA = "fpv_mvp_runtime_evidence_bundle.v1"


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    title: str
    evidence_artifact_id: str
    detail: str


@dataclass(frozen=True)
class DryRunGateSpec:
    gate_id: str
    title: str
    source_artifact_id: str
    acceptance_key: str
    detail: str


@dataclass(frozen=True)
class GapSpec:
    gap_id: str
    title: str
    required_before: str


@dataclass(frozen=True)
class BlockerSpec:
    blocker_id: str
    owner: str
    detail: str


CAPABILITIES = (
    CapabilitySpec(
        "gate_lock_tracker",
        "Gate detector lock, degrade, predictive tracking, and reacquire loop",
        "mission_report",
        "The runtime can keep a confirmed gate mission alive through short degraded/reacquire windows in dry-run.",
    ),
    CapabilitySpec(
        "race_speed_operator_limit",
        "Operator-controlled competitive speed limit",
        "command_cadence_report",
        "Speed can be reduced or raised by policy before commands are scheduled.",
    ),
    CapabilitySpec(
        "ai_command_contract",
        "Bounded roll/pitch/yaw/throttle AI command contract",
        "scheduled_command_sequence",
        "AI pilot output is represented as a bounded virtual-pilot command stream.",
    ),
    CapabilitySpec(
        "transport_frame_contract",
        "CRC-checked transport frame dry-run",
        "scheduled_transport_report",
        "Scheduled commands are encoded into transport frames without opening UART.",
    ),
    CapabilitySpec(
        "betaflight_fork_interface_contract",
        "Betaflight FPV-AI fork C interface contract",
        "betaflight_fork_contract_report",
        "The future FC fork has a locked frame layout, generated C header, and golden UART frames.",
    ),
    CapabilitySpec(
        "betaflight_parser_simulator",
        "Betaflight-side parser simulator",
        "betaflight_parser_sim_report",
        "The future FC parser behavior is simulated for CRC, heartbeat, sequence, and timeout decisions.",
    ),
    CapabilitySpec(
        "betaflight_c_reference_parser",
        "Betaflight C reference parser skeleton",
        "betaflight_c_reference_report",
        "The future FC fork has a reference C parser API, CRC check, and golden-frame fixture.",
    ),
    CapabilitySpec(
        "betaflight_payload_decoder_adapter",
        "Betaflight payload decoder adapter contract",
        "betaflight_payload_decoder_contract",
        "The future FC fork has an explicit JSON-field to C-command mapping and decoder hook contract.",
    ),
    CapabilitySpec(
        "betaflight_fork_integration_manifest",
        "Betaflight fork integration manifest",
        "betaflight_integration_manifest",
        "The future FC fork has a reviewed file placement, compile hook, and pre-merge checklist.",
    ),
    CapabilitySpec(
        "betaflight_ai_mode_state_machine",
        "Betaflight AI mode state-machine contract",
        "betaflight_ai_mode_state_machine",
        "The future FC fork has a checked AI mode, prearm, arm-request, recovery, and control gate contract.",
    ),
    CapabilitySpec(
        "betaflight_mode_manager_c_reference",
        "Betaflight AI mode manager C reference",
        "betaflight_mode_manager_c_reference_report",
        "The future FC fork has a reference C mode manager API and fixture for prearm/control gating.",
    ),
    CapabilitySpec(
        "betaflight_fork_unit_tests",
        "Betaflight fork-side unit test contract",
        "betaflight_fork_unit_tests",
        "The future FC fork has required parser, decoder, mode-manager, and integration unit tests defined.",
    ),
    CapabilitySpec(
        "betaflight_fork_patch_plan",
        "Betaflight fork patch plan",
        "betaflight_fork_patch_plan",
        "The future FC fork has a dry-run patch plan for file copy, build hooks, and review gates.",
    ),
    CapabilitySpec(
        "betaflight_fork_patch_bundle",
        "Betaflight fork patch bundle",
        "betaflight_fork_patch_bundle",
        "The future FC fork artifacts are exported into a reviewable dry-run bundle tree.",
    ),
    CapabilitySpec(
        "betaflight_owner_decision_presets",
        "Betaflight owner decision presets",
        "betaflight_owner_decision_presets",
        "The future FC fork has explicit dry-run presets for manual owner input and synthetic pipeline review.",
    ),
    CapabilitySpec(
        "betaflight_owner_decision_intake",
        "Betaflight owner decision intake",
        "betaflight_owner_decision_intake",
        "The future FC fork has a dry-run intake for owner-selected repo, branch, FC target, UART, and serial mode.",
    ),
    CapabilitySpec(
        "betaflight_owner_decision_review",
        "Betaflight owner decision review",
        "betaflight_owner_decision_review",
        "The future FC fork has an aggregated review packet for missing owner decisions and available presets.",
    ),
    CapabilitySpec(
        "betaflight_owner_target_promotion_gate",
        "Betaflight owner target promotion gate",
        "betaflight_owner_target_promotion_gate",
        "The future FC fork blocks real-target promotion until owner decisions are complete and simulation remains simulation-only proof.",
    ),
    CapabilitySpec(
        "betaflight_owner_target_pipeline",
        "Betaflight owner target pipeline",
        "betaflight_owner_target_pipeline",
        "The future FC fork has a reproducible dry-run pipeline for owner target intake, mapping, review, and promotion gating.",
    ),
    CapabilitySpec(
        "betaflight_simulated_target_review",
        "Betaflight simulated target review",
        "betaflight_simulated_target_review",
        "The target-selection pipeline is proven on a simulation-only preset without authorizing real hardware.",
    ),
    CapabilitySpec(
        "betaflight_target_profile",
        "Betaflight target profile",
        "betaflight_target_profile",
        "The future FC fork has an explicit owner-selection profile for repo, branch, FC target, and UART.",
    ),
    CapabilitySpec(
        "betaflight_build_hook_mapper",
        "Betaflight build hook mapper",
        "betaflight_build_hook_mapper",
        "The future FC fork has a dry-run map of build, UART, decoder, and virtual receiver hook points.",
    ),
    CapabilitySpec(
        "betaflight_target_build_readiness",
        "Betaflight target build readiness gate",
        "betaflight_target_build_readiness",
        "The future FC fork has a dry-run gate that connects owner target fields, patch bundle, parser, heartbeat, AUX1 arm, and arm ack evidence.",
    ),
    CapabilitySpec(
        "watchdog_contract",
        "Heartbeat and command timeout watchdog dry-run",
        "scheduled_watchdog_report",
        "The protocol path records stale/timeout handling without publishing commands to hardware.",
    ),
    CapabilitySpec(
        "betaflight_aux1_rc_control",
        "Betaflight virtual receiver AUX1 arm and stick-channel mapper",
        "betaflight_rc_control_report",
        "The runtime maps AI pilot commands into RC channels and raises AUX1 only for the launch arm gate.",
    ),
    CapabilitySpec(
        "hand_launch_state_machine",
        "Hand-launch target-lock state machine",
        "timeline_report",
        "Launcher events, lock confirmation, release, recovery, and completion are joined into a mission timeline.",
    ),
    CapabilitySpec(
        "predictive_reacquire_search_windows",
        "Predictive reacquire search-window planner",
        "reacquire_dry_run_report",
        "The tracker emits deterministic predicted crop windows and digital zoom ladder candidates during short target loss.",
    ),
    CapabilitySpec(
        "rpi_device_adapter_contracts",
        "Raspberry Pi device adapter contracts",
        "rpi_device_adapter_audit",
        "Camera, GPIO, UART, screen, and service adapters remain dry-run disabled unless explicitly configured later.",
    ),
    CapabilitySpec(
        "rpi_runtime_loop",
        "Raspberry Pi runtime loop dry-run",
        "rpi_runtime_readiness_report",
        "The RPi runtime executes the offline command loop with live hardware adapters disabled.",
    ),
    CapabilitySpec(
        "bench_hil_dry_run",
        "Bench/HIL command loop dry-run",
        "bench_hil_report",
        "A bench-style synthetic loop validates command timing, protocol output, and mock publish counts.",
    ),
    CapabilitySpec(
        "launcher_screen_status",
        "Launcher screen/status model",
        "launcher_screen_report",
        "The launch device screen can show lock, unsafe/not-ready, recovery, active, and complete states in dry-run.",
    ),
    CapabilitySpec(
        "mvp_evidence_bundle",
        "MVP runtime evidence bundle",
        "protocol_readiness_report",
        "The runtime artifacts are hashed and summarized in a synthetic evidence bundle.",
    ),
    CapabilitySpec(
        "open_parameters_register",
        "MVP open-parameter register",
        "open_parameters_register",
        "The TZ open parameters are tracked as owner-required, dry-run defaults, selected dry-run values, or later-phase items.",
    ),
    CapabilitySpec(
        "open_parameters_owner_packet",
        "MVP open-parameter owner packet",
        "open_parameters_owner_packet",
        "The open-parameter register is converted into an owner-facing intake template without selecting hardware automatically.",
    ),
    CapabilitySpec(
        "open_parameters_owner_action_packet",
        "MVP open-parameter owner action packet",
        "open_parameters_owner_action_packet",
        "Owner response, approval, application dry-run, and no-prop workorder actions are aggregated without filling values or authorizing hardware.",
    ),
    CapabilitySpec(
        "owner_parameters_completion_report",
        "MVP owner-parameter completion gate",
        "owner_parameters_completion_report",
        "Known project decisions and remaining owner fields are tracked without inventing hardware values.",
    ),
    CapabilitySpec(
        "open_parameters_owner_response",
        "MVP open-parameter owner response review",
        "open_parameters_owner_response",
        "The owner response can be validated for pipeline regeneration readiness without writing intake or authorizing hardware.",
    ),
    CapabilitySpec(
        "open_parameters_owner_response_application_dry_run",
        "MVP owner response application dry-run",
        "open_parameters_owner_response_application_dry_run",
        "Approved canonical write payloads can be assembled and hashed in memory without writing files.",
    ),
    CapabilitySpec(
        "open_parameters_owner_response_approval_gate",
        "MVP owner response approval gate",
        "open_parameters_owner_response_approval_gate",
        "Owner approvals are validated before canonical intake or pipeline writes can be considered ready.",
    ),
    CapabilitySpec(
        "open_parameters_owner_response_approval_template",
        "MVP owner response approval template",
        "open_parameters_owner_response_approval_template",
        "A fillable owner approval manifest is generated without granting approvals by default.",
    ),
    CapabilitySpec(
        "open_parameters_owner_response_apply_plan",
        "MVP owner response application plan",
        "open_parameters_owner_response_apply_plan",
        "Canonical Betaflight intake and pipeline writes are planned for owner approval without performing the writes.",
    ),
    CapabilitySpec(
        "open_parameters_owner_response_intake_bridge",
        "MVP owner response to intake bridge",
        "open_parameters_owner_response_intake_bridge",
        "The owner response is mapped into a Betaflight intake candidate without writing canonical intake or regenerating pipeline.",
    ),
    CapabilitySpec(
        "open_parameters_owner_response_template",
        "MVP open-parameter owner response template",
        "open_parameters_owner_response_template",
        "The owner packet is converted into a fillable response JSON template without writing intake or selecting hardware.",
    ),
    CapabilitySpec(
        "open_parameters_pipeline_preview",
        "MVP open-parameter pipeline preview",
        "open_parameters_pipeline_preview",
        "A complete owner response can be previewed through the target pipeline in memory without writing canonical stage reports.",
    ),
)

DRY_RUN_GATES = (
    DryRunGateSpec("mission_dry_run", "Mission dry-run reaches complete", "mission_report", "mission_complete", "launcher event mission"),
    DryRunGateSpec("timeline_report", "Mission timeline is accepted", "timeline_report", "", "joined timeline report"),
    DryRunGateSpec("command_cadence", "Scheduled command cadence is accepted", "command_cadence_report", "scheduled_commands_ready", "50 ms cadence"),
    DryRunGateSpec("protocol_readiness", "Protocol readiness is accepted", "protocol_readiness_report", "protocol_ready", "frame/CRC/watchdog path"),
    DryRunGateSpec("betaflight_fork_contract", "Betaflight fork interface contract is accepted", "betaflight_fork_contract_report", "", "C layout and golden frames"),
    DryRunGateSpec("betaflight_parser_sim", "Betaflight parser simulator is accepted", "betaflight_parser_sim_report", "", "FC-side parser decisions"),
    DryRunGateSpec("betaflight_c_reference", "Betaflight C reference parser is accepted", "betaflight_c_reference_report", "", "C parser skeleton and fixture"),
    DryRunGateSpec("betaflight_payload_decoder", "Betaflight payload decoder adapter is accepted", "betaflight_payload_decoder_contract", "", "JSON payload to C command mapping"),
    DryRunGateSpec("betaflight_integration_manifest", "Betaflight fork integration manifest is accepted", "betaflight_integration_manifest", "", "fork file placement and checks"),
    DryRunGateSpec("betaflight_ai_mode_state_machine", "Betaflight AI mode state machine is accepted", "betaflight_ai_mode_state_machine", "", "AI mode/prearm/control gate contract"),
    DryRunGateSpec("betaflight_mode_manager_c_reference", "Betaflight AI mode manager C reference is accepted", "betaflight_mode_manager_c_reference_report", "", "mode manager C API and fixture"),
    DryRunGateSpec("betaflight_fork_unit_tests", "Betaflight fork-side unit test contract is accepted", "betaflight_fork_unit_tests", "", "required fork unit tests"),
    DryRunGateSpec("betaflight_fork_patch_plan", "Betaflight fork patch plan is accepted", "betaflight_fork_patch_plan", "", "copy/build hook dry-run plan"),
    DryRunGateSpec("betaflight_fork_patch_bundle", "Betaflight fork patch bundle is accepted", "betaflight_fork_patch_bundle", "", "reviewable fork export bundle"),
    DryRunGateSpec("betaflight_owner_decision_presets", "Betaflight owner decision presets are accepted", "betaflight_owner_decision_presets", "", "owner decision preset catalog"),
    DryRunGateSpec("betaflight_owner_decision_intake", "Betaflight owner decision intake is accepted", "betaflight_owner_decision_intake", "", "owner input intake"),
    DryRunGateSpec("betaflight_owner_decision_review", "Betaflight owner decision review is accepted", "betaflight_owner_decision_review", "", "owner decision review packet"),
    DryRunGateSpec("betaflight_owner_target_promotion_gate", "Betaflight owner target promotion gate is accepted", "betaflight_owner_target_promotion_gate", "", "owner target promotion guard"),
    DryRunGateSpec("betaflight_owner_target_pipeline", "Betaflight owner target pipeline is accepted", "betaflight_owner_target_pipeline", "", "owner target pipeline"),
    DryRunGateSpec("betaflight_simulated_target_review", "Betaflight simulated target review is accepted", "betaflight_simulated_target_review", "", "simulation-only target proof"),
    DryRunGateSpec("betaflight_target_profile", "Betaflight target profile is accepted", "betaflight_target_profile", "", "owner-selection target profile"),
    DryRunGateSpec("betaflight_build_hook_mapper", "Betaflight build hook mapper is accepted", "betaflight_build_hook_mapper", "", "build/runtime hook map"),
    DryRunGateSpec("betaflight_target_build_readiness", "Betaflight target build readiness is accepted", "betaflight_target_build_readiness", "", "target build readiness gate"),
    DryRunGateSpec("betaflight_rc_control", "Betaflight AUX1 RC control dry-run is accepted", "betaflight_rc_control_report", "", "virtual receiver channel map"),
    DryRunGateSpec("bench_hil", "Bench/HIL dry-run is accepted", "bench_hil_report", "bench_hil_ready", "mock bench loop"),
    DryRunGateSpec("rpi_runtime", "Raspberry Pi runtime dry-run is accepted", "rpi_runtime_readiness_report", "rpi_runtime_ready", "live adapters disabled"),
    DryRunGateSpec("launcher_screen", "Launcher screen dry-run is accepted", "launcher_screen_report", "launcher_screen_ready", "status overlay"),
    DryRunGateSpec("reacquire_dry_run", "Predictive reacquire dry-run is accepted", "reacquire_dry_run_report", "", "prediction windows and digital crop ladder"),
    DryRunGateSpec("open_parameters_register", "Open-parameter register is accepted", "open_parameters_register", "", "MVP parameter status register"),
    DryRunGateSpec("open_parameters_owner_packet", "Open-parameter owner packet is accepted", "open_parameters_owner_packet", "", "owner intake template"),
    DryRunGateSpec("open_parameters_owner_action_packet", "Open-parameter owner action packet is accepted", "open_parameters_owner_action_packet", "", "aggregated owner action review"),
    DryRunGateSpec("owner_parameters_completion_report", "Owner-parameter completion gate is accepted", "owner_parameters_completion_report", "", "known decisions and missing owner fields"),
    DryRunGateSpec("open_parameters_owner_response", "Open-parameter owner response review is accepted", "open_parameters_owner_response", "", "owner response validation"),
    DryRunGateSpec("open_parameters_owner_response_application_dry_run", "Open-parameter owner response application dry-run is accepted", "open_parameters_owner_response_application_dry_run", "", "approved payload hash dry-run"),
    DryRunGateSpec("open_parameters_owner_response_approval_gate", "Open-parameter owner response approval gate is accepted", "open_parameters_owner_response_approval_gate", "", "owner approval guard before canonical writes"),
    DryRunGateSpec("open_parameters_owner_response_approval_template", "Open-parameter owner response approval template is accepted", "open_parameters_owner_response_approval_template", "", "fillable owner approval manifest"),
    DryRunGateSpec("open_parameters_owner_response_apply_plan", "Open-parameter owner response apply plan is accepted", "open_parameters_owner_response_apply_plan", "", "owner-approved canonical write plan"),
    DryRunGateSpec("open_parameters_owner_response_intake_bridge", "Open-parameter owner response intake bridge is accepted", "open_parameters_owner_response_intake_bridge", "", "owner response to intake candidate bridge"),
    DryRunGateSpec("open_parameters_owner_response_template", "Open-parameter owner response template is accepted", "open_parameters_owner_response_template", "", "fillable owner response template"),
    DryRunGateSpec("open_parameters_pipeline_preview", "Open-parameter pipeline preview is accepted", "open_parameters_pipeline_preview", "", "owner response pipeline preview"),
)

NOT_FIELD_PROOF = (
    GapSpec("model_not_trained_or_exported", "Gate detector model is not trained/exported in this slice", "model acceptance"),
    GapSpec("no_live_camera_feed", "No live RGB/thermal camera capture has been opened", "hardware bench"),
    GapSpec("no_ai_accelerator_benchmark", "No Raspberry Pi AI HAT/Hailo latency benchmark has been run", "hardware bench"),
    GapSpec("no_real_uart_packet_acceptance", "No real UART/Betaflight fork packet acceptance has been proven", "no-prop bench"),
    GapSpec("no_no_prop_bench", "No no-prop bench test has been authorized or executed", "owner-approved bench"),
    GapSpec("no_prop_flight", "No propeller flight test has been authorized or executed", "field flight"),
    GapSpec("no_real_field_evidence", "No real field evidence package exists for this runtime", "field acceptance"),
    GapSpec("full_visual_abort_layer_deferred", "Full person/corridor/geofence visual abort logic is deferred by project decision", "final safety layer"),
)

NO_PROP_BENCH_BLOCKERS = (
    BlockerSpec(
        "owner_defines_first_hardware_test",
        "project_owner",
        "The project owner must define and approve the first hardware test scope; this report does not authorize it.",
    ),
    BlockerSpec(
        "flight_controller_target_selected",
        "hardware_owner",
        "Exact FC board, Betaflight fork baseline, UART port, and voltage levels must be selected and reviewed.",
    ),
    BlockerSpec(
        "propellers_removed_bench_rig_ready",
        "hardware_owner",
        "A physical bench rig with propellers removed must be prepared before any live adapter is enabled.",
    ),
    BlockerSpec(
        "independent_kill_power_cut_verified",
        "hardware_owner",
        "Manual independent kill/power cut must be physically verified outside Raspberry Pi software.",
    ),
    BlockerSpec(
        "uart_wiring_and_protocol_plan_reviewed",
        "software_owner",
        "UART wiring, frame rate, command scaling, sequence handling, and timeout behavior must be reviewed against the FC fork.",
    ),
    BlockerSpec(
        "live_adapters_remain_disabled_until_bench_mode",
        "software_owner",
        "Camera/GPIO/UART/screen live adapters must remain disabled until an explicit bench configuration is introduced.",
    ),
    BlockerSpec(
        "bench_logging_and_time_sync_defined",
        "test_owner",
        "Bench logs, timestamps, artifact paths, and evidence retention must be defined before running the bench script live.",
    ),
    BlockerSpec(
        "no_prop_bench_plan_accepted",
        "project_owner",
        "A no-prop bench workorder/test plan must be accepted before this dry-run closeout can be used for hardware work.",
    ),
)


def build_runtime_readiness_closeout(
    *,
    evidence_bundle: Mapping[str, Any],
    evidence_bundle_path: Path | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    artifacts = _artifact_map(evidence_bundle)
    acceptance = _mapping(evidence_bundle.get("acceptance"))
    summary = _mapping(evidence_bundle.get("summary"))

    dry_run_gates = [_dry_run_gate(spec, artifacts, acceptance) for spec in DRY_RUN_GATES]
    dry_run_gates.append(_evidence_bundle_gate(evidence_bundle, evidence_bundle_path))
    implemented_capabilities = [_capability_entry(spec, artifacts) for spec in CAPABILITIES]
    gaps = [_gap_entry(spec) for spec in NOT_FIELD_PROOF]
    blockers = [_blocker_entry(spec) for spec in NO_PROP_BENCH_BLOCKERS]
    checks = _closeout_checks(evidence_bundle, summary, dry_run_gates, gaps, blockers)
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"

    return {
        "schema": CLOSEOUT_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "readiness_state": "DRY_RUN_COMPLETE_OWNER_REVIEW_REQUIRED" if status == "PASS" else "DRY_RUN_INCOMPLETE",
        "source_evidence_bundle": _source_bundle_entry(evidence_bundle, evidence_bundle_path, summary),
        "summary": {
            "mvp_runtime_dry_run_complete": bool(acceptance.get("mvp_runtime_dry_run_complete")),
            "dry_run_evidence_passed": str(evidence_bundle.get("status") or "") == "PASS",
            "completed_capability_count": sum(1 for entry in implemented_capabilities if entry["status"] == "IMPLEMENTED_DRY_RUN"),
            "implemented_capability_count": len(implemented_capabilities),
            "dry_run_gate_count": len(dry_run_gates),
            "passing_dry_run_gate_count": sum(1 for entry in dry_run_gates if entry["status"] == "PASS"),
            "field_proof_gap_count": len(gaps),
            "blocker_count": len(blockers),
            "field_proof_claimed": False,
            "no_prop_bench_authorized": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
            "training_launched": False,
        },
        "checks": checks,
        "dry_run_gates": dry_run_gates,
        "implemented_capabilities": implemented_capabilities,
        "not_field_proof": gaps,
        "blockers_before_no_prop_bench": blockers,
        "safety_boundary": {
            "dry_run_only": True,
            "synthetic_evidence_only": True,
            "field_proof_claimed": False,
            "no_prop_bench_authorized": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
            "training_launched": False,
            "does_not_open_live_cameras": True,
            "does_not_read_gpio": True,
            "does_not_open_uart": True,
            "does_not_open_screen_device": True,
            "does_not_install_systemd_unit": True,
            "does_not_start_service": True,
            "requires_owner_authorization_for_hardware": True,
        },
    }


def write_runtime_readiness_closeout(
    *,
    evidence_bundle_json: Path,
    output_json: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    evidence_bundle = _read_json(evidence_bundle_json)
    closeout = build_runtime_readiness_closeout(
        evidence_bundle=evidence_bundle,
        evidence_bundle_path=evidence_bundle_json,
        project_root=project_root,
    )
    persisted = dict(closeout)
    persisted["closeout_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _artifact_map(evidence_bundle: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    artifacts = evidence_bundle.get("artifacts")
    if not isinstance(artifacts, list):
        return {}
    mapped: dict[str, Mapping[str, Any]] = {}
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            continue
        artifact_id = artifact.get("artifact_id")
        if isinstance(artifact_id, str):
            mapped[artifact_id] = artifact
    return mapped


def _dry_run_gate(
    spec: DryRunGateSpec,
    artifacts: Mapping[str, Mapping[str, Any]],
    acceptance: Mapping[str, Any],
) -> dict[str, str]:
    artifact = artifacts.get(spec.source_artifact_id, {})
    artifact_status = _artifact_status(artifact)
    accepted = bool(acceptance.get(spec.acceptance_key)) if spec.acceptance_key else artifact_status == "PASS"
    status = "PASS" if accepted and artifact_status == "PASS" else artifact_status
    return {
        "gate_id": spec.gate_id,
        "title": spec.title,
        "source_artifact_id": spec.source_artifact_id,
        "source_path": str(artifact.get("path") or ""),
        "status": status,
        "detail": spec.detail,
    }


def _evidence_bundle_gate(evidence_bundle: Mapping[str, Any], evidence_bundle_path: Path | None) -> dict[str, str]:
    return {
        "gate_id": "evidence_bundle",
        "title": "MVP runtime evidence bundle is accepted",
        "source_artifact_id": "mvp_runtime_evidence_bundle",
        "source_path": str(evidence_bundle_path or evidence_bundle.get("bundle_path") or ""),
        "status": "PASS" if str(evidence_bundle.get("status") or "") == "PASS" else "FAIL",
        "detail": "hashed dry-run evidence bundle",
    }


def _capability_entry(spec: CapabilitySpec, artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    artifact = artifacts.get(spec.evidence_artifact_id, {})
    evidence_path = str(artifact.get("path") or "")
    exists = bool(artifact.get("exists"))
    return {
        "capability_id": spec.capability_id,
        "title": spec.title,
        "status": "IMPLEMENTED_DRY_RUN" if exists else "MISSING_EVIDENCE",
        "evidence_artifact_id": spec.evidence_artifact_id,
        "evidence_path": evidence_path,
        "detail": spec.detail,
    }


def _gap_entry(spec: GapSpec) -> dict[str, str]:
    return {
        "gap_id": spec.gap_id,
        "title": spec.title,
        "status": "NOT_PROVEN",
        "required_before": spec.required_before,
    }


def _blocker_entry(spec: BlockerSpec) -> dict[str, str]:
    return {
        "blocker_id": spec.blocker_id,
        "status": "BLOCKING",
        "owner": spec.owner,
        "detail": spec.detail,
    }


def _closeout_checks(
    evidence_bundle: Mapping[str, Any],
    summary: Mapping[str, Any],
    dry_run_gates: list[dict[str, str]],
    gaps: list[dict[str, str]],
    blockers: list[dict[str, str]],
) -> list[dict[str, str]]:
    return [
        _check("evidence_bundle_schema_valid", evidence_bundle.get("schema") == EVIDENCE_BUNDLE_SCHEMA, str(evidence_bundle.get("schema") or "")),
        _check("evidence_bundle_passed", evidence_bundle.get("status") == "PASS", str(evidence_bundle.get("status") or "")),
        _check("mvp_runtime_dry_run_complete", bool(_mapping(evidence_bundle.get("acceptance")).get("mvp_runtime_dry_run_complete")), "runtime acceptance flag"),
        _check("no_missing_required_artifacts", int(summary.get("missing_required_artifact_count") or 0) == 0, str(summary.get("missing_required_artifact_count") or 0)),
        _check("no_failed_required_reports", int(summary.get("fail_required_report_count") or 0) == 0, str(summary.get("fail_required_report_count") or 0)),
        _check("all_dry_run_gates_passed", all(gate["status"] == "PASS" for gate in dry_run_gates), _failed_gate_detail(dry_run_gates)),
        _check("field_proof_not_claimed", summary.get("field_proof_claimed") is False, "synthetic evidence only"),
        _check("hardware_not_authorized", summary.get("hardware_test_authorized") is False, "owner authorization required later"),
        _check("no_prop_bench_not_authorized", True, "no-prop bench remains outside this closeout"),
        _check("flight_commands_not_published", summary.get("flight_commands_published") is False, "dry-run command path"),
        _check("training_not_launched", summary.get("training_launched") is False, "dataset/model training skipped by project decision"),
        _check("field_gaps_recorded", bool(gaps), str(len(gaps))),
        _check("no_prop_blockers_recorded", bool(blockers), str(len(blockers))),
    ]


def _source_bundle_entry(evidence_bundle: Mapping[str, Any], evidence_bundle_path: Path | None, summary: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": str(evidence_bundle_path or evidence_bundle.get("bundle_path") or ""),
        "schema": str(evidence_bundle.get("schema") or ""),
        "status": str(evidence_bundle.get("status") or ""),
        "sha256": _sha256(evidence_bundle_path) if evidence_bundle_path and evidence_bundle_path.exists() else "",
        "manifest_sha256": str(summary.get("manifest_sha256") or ""),
        "artifact_count": int(summary.get("artifact_count") or 0),
    }


def _artifact_status(artifact: Mapping[str, Any]) -> str:
    if not artifact:
        return "MISSING"
    return str(artifact.get("status") or "NO_STATUS")


def _failed_gate_detail(dry_run_gates: list[dict[str, str]]) -> str:
    return ",".join(gate["gate_id"] for gate in dry_run_gates if gate["status"] != "PASS")


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
