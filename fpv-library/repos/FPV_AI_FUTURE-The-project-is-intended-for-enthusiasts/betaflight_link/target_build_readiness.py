"""Dry-run Betaflight target build readiness gate for FPV-AI.

This report ties the current owner-selected Betaflight baseline to the fork
patch bundle, parser contract, AI mode manager, and AUX1 RC-control dry-run.
It records whether a real FC target build can be prepared, but it never applies
patches, compiles, flashes, opens UART, or authorizes hardware work.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from fpv_ai.betaflight_link.fork_patch_bundle import FORK_PATCH_BUNDLE_SCHEMA
from fpv_ai.betaflight_link.fork_unit_tests import FORK_UNIT_TESTS_SCHEMA
from fpv_ai.betaflight_link.mode_manager_c_reference import MODE_MANAGER_C_REFERENCE_SCHEMA
from fpv_ai.betaflight_link.parser_sim import PARSER_SIM_SCHEMA
from fpv_ai.betaflight_link.rc_control import RC_REPORT_SCHEMA

TARGET_BUILD_READINESS_SCHEMA = "fpv_betaflight_target_build_readiness.v1"
OWNER_RESPONSE_INPUT_SCHEMA = "fpv_mvp_open_parameters_owner_response_input.v1"
OWNER_RESPONSE_REVIEW_SCHEMA = "fpv_mvp_open_parameters_owner_response.v1"
OWNER_SELECTION_REQUIRED = "OWNER_SELECTION_REQUIRED"

REQUIRED_TARGET_FIELDS = (
    ("betaflight_repo_url", "Exact Betaflight fork/upstream repository URL."),
    ("betaflight_branch", "Exact branch, tag, or commit for the target build."),
    ("fc_target", "Exact Betaflight flight-controller target/board name."),
    ("ai_uart_port", "Dedicated FC UART used by the Raspberry Pi AI stream."),
    ("serial_mode", "AI command input mode for the fork integration."),
    ("electrical_voltage_level", "UART voltage/wiring domain for electrical review."),
)


def build_betaflight_target_build_readiness(
    *,
    owner_response_input: Mapping[str, Any],
    owner_response_review: Mapping[str, Any],
    patch_bundle_manifest: Mapping[str, Any],
    fork_unit_tests_contract: Mapping[str, Any],
    parser_sim_report: Mapping[str, Any],
    mode_manager_c_reference_report: Mapping[str, Any],
    rc_control_report: Mapping[str, Any],
    owner_response_input_path: Path | str | None = None,
    owner_response_review_path: Path | str | None = None,
    patch_bundle_manifest_path: Path | str | None = None,
    fork_unit_tests_path: Path | str | None = None,
    parser_sim_path: Path | str | None = None,
    mode_manager_c_reference_path: Path | str | None = None,
    rc_control_report_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    target_context = _target_context(owner_response_input, owner_response_review)
    target_fields = _target_fields(target_context)
    missing_fields = [row for row in target_fields if row["status"] == "OWNER_INPUT_REQUIRED"]
    patch_bundle_ready = _report_ready(
        patch_bundle_manifest,
        expected_schema=FORK_PATCH_BUNDLE_SCHEMA,
        state_key="bundle_state",
        expected_state="READY_FOR_FORK_EXPORT_REVIEW",
    )
    fork_unit_tests_ready = _report_ready(
        fork_unit_tests_contract,
        expected_schema=FORK_UNIT_TESTS_SCHEMA,
        state_key="contract_state",
        expected_state="READY_FOR_FORK_TEST_IMPLEMENTATION",
    )
    parser_sim_ready = _parser_sim_ready(parser_sim_report)
    mode_manager_ready = _mode_manager_ready(mode_manager_c_reference_report)
    aux1_arm_ready = _aux1_arm_ready(rc_control_report)
    arm_ack_ready = _arm_ack_ready(rc_control_report)
    heartbeat_watchdog_ready = parser_sim_ready and fork_unit_tests_ready
    target_selected = not missing_fields
    build_command_preview = _build_command_preview(target_context, target_selected)
    planned_steps = _planned_steps(
        target_context=target_context,
        target_selected=target_selected,
        patch_bundle_ready=patch_bundle_ready,
        fork_unit_tests_ready=fork_unit_tests_ready,
        parser_sim_ready=parser_sim_ready,
        mode_manager_ready=mode_manager_ready,
        aux1_arm_ready=aux1_arm_ready,
        arm_ack_ready=arm_ack_ready,
        heartbeat_watchdog_ready=heartbeat_watchdog_ready,
    )
    blocked_reasons = _blocked_reasons(target_fields, target_selected)
    verification_matrix = _verification_matrix(
        patch_bundle_ready=patch_bundle_ready,
        fork_unit_tests_ready=fork_unit_tests_ready,
        parser_sim_ready=parser_sim_ready,
        mode_manager_ready=mode_manager_ready,
        aux1_arm_ready=aux1_arm_ready,
        arm_ack_ready=arm_ack_ready,
        heartbeat_watchdog_ready=heartbeat_watchdog_ready,
        target_selected=target_selected,
    )
    checks = _checks(
        owner_response_input=owner_response_input,
        owner_response_review=owner_response_review,
        patch_bundle_manifest=patch_bundle_manifest,
        fork_unit_tests_contract=fork_unit_tests_contract,
        parser_sim_report=parser_sim_report,
        mode_manager_c_reference_report=mode_manager_c_reference_report,
        rc_control_report=rc_control_report,
        patch_bundle_ready=patch_bundle_ready,
        fork_unit_tests_ready=fork_unit_tests_ready,
        parser_sim_ready=parser_sim_ready,
        mode_manager_ready=mode_manager_ready,
        aux1_arm_ready=aux1_arm_ready,
        arm_ack_ready=arm_ack_ready,
        heartbeat_watchdog_ready=heartbeat_watchdog_ready,
    )
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "schema": TARGET_BUILD_READINESS_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "readiness_state": _readiness_state(status, target_selected),
        "source_reports": [
            _source_report("owner_response_input", owner_response_input, owner_response_input_path, OWNER_RESPONSE_INPUT_SCHEMA),
            _source_report("owner_response_review", owner_response_review, owner_response_review_path, OWNER_RESPONSE_REVIEW_SCHEMA),
            _source_report("patch_bundle_manifest", patch_bundle_manifest, patch_bundle_manifest_path, FORK_PATCH_BUNDLE_SCHEMA),
            _source_report("fork_unit_tests", fork_unit_tests_contract, fork_unit_tests_path, FORK_UNIT_TESTS_SCHEMA),
            _source_report("parser_sim", parser_sim_report, parser_sim_path, PARSER_SIM_SCHEMA),
            _source_report(
                "mode_manager_c_reference",
                mode_manager_c_reference_report,
                mode_manager_c_reference_path,
                MODE_MANAGER_C_REFERENCE_SCHEMA,
            ),
            _source_report("betaflight_rc_control_report", rc_control_report, rc_control_report_path, RC_REPORT_SCHEMA),
        ],
        "target_context": target_context,
        "summary": {
            "source_report_count": 7,
            "required_target_field_count": len(target_fields),
            "selected_target_field_count": sum(1 for row in target_fields if row["status"] == "SELECTED"),
            "missing_target_field_count": len(missing_fields),
            "patch_bundle_ready": patch_bundle_ready,
            "fork_unit_tests_ready": fork_unit_tests_ready,
            "parser_sim_ready": parser_sim_ready,
            "mode_manager_ready": mode_manager_ready,
            "aux1_arm_dry_run_ready": aux1_arm_ready,
            "heartbeat_watchdog_ready": heartbeat_watchdog_ready,
            "arm_ack_dry_run_ready": arm_ack_ready,
            "build_command_preview_ready": target_selected,
            "patch_apply_ready": target_selected and patch_bundle_ready,
            "compile_ready": target_selected and patch_bundle_ready and fork_unit_tests_ready,
            "real_target_build_ready": target_selected
            and patch_bundle_ready
            and fork_unit_tests_ready
            and parser_sim_ready
            and mode_manager_ready
            and aux1_arm_ready
            and heartbeat_watchdog_ready
            and arm_ack_ready,
            "patch_applied": False,
            "betaflight_repo_modified": False,
            "compile_attempted": False,
            "flash_attempted": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "required_target_fields": target_fields,
        "build_command_preview": build_command_preview,
        "planned_steps": planned_steps,
        "blocked_reasons": blocked_reasons,
        "verification_matrix": verification_matrix,
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "readiness_report_only": True,
            "does_not_select_hardware_automatically": True,
            "does_not_modify_betaflight_repo": True,
            "does_not_apply_patch": True,
            "does_not_compile_or_flash_betaflight": True,
            "does_not_execute_c_tests": True,
            "does_not_open_uart": True,
            "does_not_authorize_hardware_test": True,
            "does_not_authorize_no_prop_bench": True,
            "does_not_publish_flight_commands": True,
            "does_not_command_motors_directly": True,
        },
    }


def write_betaflight_target_build_readiness(
    *,
    owner_response_input_json: Path,
    owner_response_review_json: Path,
    patch_bundle_manifest_json: Path,
    fork_unit_tests_json: Path,
    parser_sim_json: Path,
    mode_manager_c_reference_json: Path,
    rc_control_report_json: Path,
    output_json: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    report = build_betaflight_target_build_readiness(
        owner_response_input=_read_json(owner_response_input_json),
        owner_response_review=_read_json(owner_response_review_json),
        patch_bundle_manifest=_read_json(patch_bundle_manifest_json),
        fork_unit_tests_contract=_read_json(fork_unit_tests_json),
        parser_sim_report=_read_json(parser_sim_json),
        mode_manager_c_reference_report=_read_json(mode_manager_c_reference_json),
        rc_control_report=_read_json(rc_control_report_json),
        owner_response_input_path=owner_response_input_json,
        owner_response_review_path=owner_response_review_json,
        patch_bundle_manifest_path=patch_bundle_manifest_json,
        fork_unit_tests_path=fork_unit_tests_json,
        parser_sim_path=parser_sim_json,
        mode_manager_c_reference_path=mode_manager_c_reference_json,
        rc_control_report_path=rc_control_report_json,
        project_root=project_root,
    )
    persisted = dict(report)
    persisted["report_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _target_context(owner_response_input: Mapping[str, Any], owner_response_review: Mapping[str, Any]) -> dict[str, Any]:
    preview = _mapping(owner_response_review.get("owner_decision_input_preview"))
    response = _mapping(owner_response_input.get("target_decision_response"))
    source = preview or response
    return {
        "profile_name": str(source.get("profile_name") or response.get("profile_name") or ""),
        "betaflight_repo_url": str(source.get("betaflight_repo_url") or ""),
        "betaflight_branch": str(source.get("betaflight_branch") or ""),
        "fc_target": str(source.get("fc_target") or ""),
        "ai_uart_port": str(source.get("ai_uart_port") or ""),
        "serial_mode": str(source.get("serial_mode") or ""),
        "serial_baud": int(source.get("serial_baud") or 0),
        "electrical_voltage_level": str(source.get("electrical_voltage_level") or ""),
        "command_rate_hz": int(source.get("command_rate_hz") or 0),
        "speed_mode": str(source.get("speed_mode") or ""),
        "operator_limit_mps": float(source.get("operator_limit_mps") or 0.0),
    }


def _target_fields(target_context: Mapping[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for field_id, detail in REQUIRED_TARGET_FIELDS:
        value = str(target_context.get(field_id) or "")
        rows.append(
            {
                "field_id": field_id,
                "value": value,
                "status": "SELECTED" if _selected(value) else "OWNER_INPUT_REQUIRED",
                "detail": detail,
            }
        )
    return rows


def _build_command_preview(target_context: Mapping[str, Any], target_selected: bool) -> dict[str, str]:
    fc_target = str(target_context.get("fc_target") or "<OWNER_SELECTED_FC_TARGET>")
    return {
        "status": "READY_FOR_MANUAL_REVIEW" if target_selected else "BLOCKED_OWNER_INPUT",
        "checkout_ref": f"{target_context.get('betaflight_repo_url') or '<OWNER_SELECTED_REPO>'}@{target_context.get('betaflight_branch') or '<OWNER_SELECTED_BRANCH>'}",
        "target_build_command": f"make TARGET={fc_target}",
        "unit_test_scope": "Betaflight fork-side tests from fpv_betaflight_fork_unit_tests.v1.",
        "execution_state": "NOT_EXECUTED_DRY_RUN",
    }


def _planned_steps(
    *,
    target_context: Mapping[str, Any],
    target_selected: bool,
    patch_bundle_ready: bool,
    fork_unit_tests_ready: bool,
    parser_sim_ready: bool,
    mode_manager_ready: bool,
    aux1_arm_ready: bool,
    arm_ack_ready: bool,
    heartbeat_watchdog_ready: bool,
) -> list[dict[str, str]]:
    repo_ready = _selected(str(target_context.get("betaflight_repo_url") or ""))
    branch_ready = _selected(str(target_context.get("betaflight_branch") or ""))
    fc_ready = _selected(str(target_context.get("fc_target") or ""))
    uart_ready = _selected(str(target_context.get("ai_uart_port") or ""))
    voltage_ready = _selected(str(target_context.get("electrical_voltage_level") or ""))
    return [
        _step("verify_upstream_baseline", "Verify selected Betaflight repo/branch.", "READY" if repo_ready and branch_ready else "OWNER_INPUT_REQUIRED"),
        _step("owner_select_fc_target", "Select exact FC target/board.", "READY" if fc_ready else "OWNER_INPUT_REQUIRED"),
        _step("owner_select_ai_uart_port", "Select dedicated AI UART on the FC.", "READY" if uart_ready else "OWNER_INPUT_REQUIRED"),
        _step("owner_confirm_voltage", "Confirm UART electrical voltage level.", "READY" if voltage_ready else "OWNER_INPUT_REQUIRED"),
        _step("review_patch_bundle", "Review exported FPV-AI fork patch bundle.", "DRY_RUN_READY" if patch_bundle_ready else "BLOCKED_SOURCE_REPORT"),
        _step(
            "apply_patch_to_fork_checkout",
            "Manual future step: apply reviewed bundle to a fork checkout.",
            "READY_FOR_MANUAL_REVIEW" if target_selected and patch_bundle_ready else "BLOCKED_OWNER_INPUT",
        ),
        _step(
            "generate_target_build_command",
            "Prepare FC target build command preview.",
            "READY_FOR_MANUAL_REVIEW" if target_selected else "BLOCKED_OWNER_INPUT",
        ),
        _step(
            "run_betaflight_build",
            "Manual future step: compile the fork under the selected target.",
            "NOT_EXECUTED_DRY_RUN" if target_selected and fork_unit_tests_ready else "BLOCKED_OWNER_INPUT",
        ),
        _step("verify_ai_uart_parser", "Verify parser CRC, sequence, heartbeat, and timeout contract.", "DRY_RUN_READY" if parser_sim_ready else "BLOCKED_SOURCE_REPORT"),
        _step("verify_mode_manager", "Verify AI prearm/control gate mode manager reference.", "DRY_RUN_READY" if mode_manager_ready else "BLOCKED_SOURCE_REPORT"),
        _step("verify_aux1_arm_mode", "Verify AUX1 arm with throttle-low discipline.", "DRY_RUN_READY" if aux1_arm_ready else "BLOCKED_SOURCE_REPORT"),
        _step("verify_heartbeat_timeout_arm_ack", "Verify heartbeat watchdog and FC armed-ack dry-run evidence.", "DRY_RUN_READY" if heartbeat_watchdog_ready and arm_ack_ready else "BLOCKED_SOURCE_REPORT"),
    ]


def _blocked_reasons(target_fields: Sequence[Mapping[str, str]], target_selected: bool) -> list[dict[str, str]]:
    reasons = [
        {
            "blocker_id": f"{row['field_id']}_not_selected",
            "status": "OWNER_INPUT_REQUIRED",
            "detail": row["detail"],
        }
        for row in target_fields
        if row["status"] == "OWNER_INPUT_REQUIRED"
    ]
    if not target_selected:
        reasons.extend(
            [
                {
                    "blocker_id": "patch_application_blocked_until_target_complete",
                    "status": "BLOCKED_OWNER_INPUT",
                    "detail": "Patch application review needs exact FC target, UART, and voltage values.",
                },
                {
                    "blocker_id": "target_compile_blocked_until_target_complete",
                    "status": "BLOCKED_OWNER_INPUT",
                    "detail": "Target build command and compile review are blocked until owner target fields are complete.",
                },
            ]
        )
    return reasons


def _verification_matrix(
    *,
    patch_bundle_ready: bool,
    fork_unit_tests_ready: bool,
    parser_sim_ready: bool,
    mode_manager_ready: bool,
    aux1_arm_ready: bool,
    arm_ack_ready: bool,
    heartbeat_watchdog_ready: bool,
    target_selected: bool,
) -> list[dict[str, str]]:
    return [
        _verification("patch_bundle_exported", patch_bundle_ready, "Patch bundle files are exported and hash-checked."),
        _verification("fork_unit_tests_declared", fork_unit_tests_ready, "Fork-side parser/decoder/mode-manager tests are declared."),
        _verification("ai_uart_parser_contract", parser_sim_ready, "Parser accepts golden frames and keeps stale/heartbeat checks in contract."),
        _verification("ai_mode_manager_contract", mode_manager_ready, "Mode manager routes AI control through virtual receiver only."),
        _verification("aux1_arm_contract", aux1_arm_ready, "AUX1 arm request is raised only at the AI arm gate with throttle low."),
        _verification("fc_arm_ack_contract", arm_ack_ready, "Dry-run timeline contains FC armed acknowledgement after arm request."),
        _verification("heartbeat_watchdog_contract", heartbeat_watchdog_ready, "Heartbeat and timeout requirements are covered by parser/unit-test contracts."),
        _verification("selected_target_build_context", target_selected, "Real target build context is complete."),
    ]


def _verification(verification_id: str, ready: bool, detail: str) -> dict[str, str]:
    return {
        "verification_id": verification_id,
        "status": "DRY_RUN_READY" if ready else "OWNER_INPUT_REQUIRED",
        "detail": detail,
    }


def _checks(
    *,
    owner_response_input: Mapping[str, Any],
    owner_response_review: Mapping[str, Any],
    patch_bundle_manifest: Mapping[str, Any],
    fork_unit_tests_contract: Mapping[str, Any],
    parser_sim_report: Mapping[str, Any],
    mode_manager_c_reference_report: Mapping[str, Any],
    rc_control_report: Mapping[str, Any],
    patch_bundle_ready: bool,
    fork_unit_tests_ready: bool,
    parser_sim_ready: bool,
    mode_manager_ready: bool,
    aux1_arm_ready: bool,
    arm_ack_ready: bool,
    heartbeat_watchdog_ready: bool,
) -> list[dict[str, str]]:
    review_summary = _mapping(owner_response_review.get("summary"))
    return [
        _check("owner_response_input_schema_valid", owner_response_input.get("schema") == OWNER_RESPONSE_INPUT_SCHEMA, str(owner_response_input.get("schema") or "")),
        _check("owner_response_review_schema_valid", owner_response_review.get("schema") == OWNER_RESPONSE_REVIEW_SCHEMA, str(owner_response_review.get("schema") or "")),
        _check("owner_response_review_passed", owner_response_review.get("status") == "PASS", str(owner_response_review.get("status") or "")),
        _check(
            "target_selection_counts_present",
            int(review_summary.get("target_selected_count") or 0)
            + int(review_summary.get("target_missing_count") or 0)
            == len(REQUIRED_TARGET_FIELDS),
            f"selected={review_summary.get('target_selected_count')},missing={review_summary.get('target_missing_count')}",
        ),
        _check("patch_bundle_ready", patch_bundle_ready, str(patch_bundle_manifest.get("bundle_state") or "")),
        _check("fork_unit_tests_ready", fork_unit_tests_ready, str(fork_unit_tests_contract.get("contract_state") or "")),
        _check("parser_sim_ready", parser_sim_ready, str(_mapping(parser_sim_report.get("summary")).get("accepted_count") or 0)),
        _check("mode_manager_ready", mode_manager_ready, str(mode_manager_c_reference_report.get("status") or "")),
        _check("aux1_arm_dry_run_ready", aux1_arm_ready, str(_mapping(rc_control_report.get("summary")).get("aux1_arm_frame_count") or 0)),
        _check("heartbeat_watchdog_ready", heartbeat_watchdog_ready, "parser sim and fork unit test contract"),
        _check("arm_ack_dry_run_ready", arm_ack_ready, str(_mapping(rc_control_report.get("summary")).get("fc_armed_frame_count") or 0)),
        _check("missing_owner_target_fields_are_blockers_not_failures", True, "owner fields block build readiness but preserve report PASS"),
        _check("no_patch_apply_attempt", True, "readiness report only"),
        _check("no_compile_or_flash", True, "compile/flash outside this dry-run"),
        _check("no_live_uart_access", True, "file-only readiness"),
    ]


def _report_ready(
    report: Mapping[str, Any],
    *,
    expected_schema: str,
    state_key: str,
    expected_state: str,
) -> bool:
    return (
        report.get("schema") == expected_schema
        and report.get("status") == "PASS"
        and report.get(state_key) == expected_state
    )


def _parser_sim_ready(parser_sim_report: Mapping[str, Any]) -> bool:
    summary = _mapping(parser_sim_report.get("summary"))
    return (
        parser_sim_report.get("schema") == PARSER_SIM_SCHEMA
        and parser_sim_report.get("status") == "PASS"
        and int(summary.get("accepted_count") or 0) > 0
        and int(summary.get("rejected_count") or 0) == 0
        and int(summary.get("stale_count") or 0) == 0
        and int(summary.get("kill_required_count") or 0) == 0
    )


def _mode_manager_ready(report: Mapping[str, Any]) -> bool:
    summary = _mapping(report.get("summary"))
    return (
        report.get("schema") == MODE_MANAGER_C_REFERENCE_SCHEMA
        and report.get("status") == "PASS"
        and summary.get("virtual_receiver_route_required") is True
        and summary.get("direct_motor_output_allowed") is False
    )


def _aux1_arm_ready(report: Mapping[str, Any]) -> bool:
    summary = _mapping(report.get("summary"))
    return (
        report.get("schema") == RC_REPORT_SCHEMA
        and report.get("status") == "PASS"
        and int(summary.get("arm_request_frame_count") or 0) > 0
        and int(summary.get("aux1_arm_frame_count") or 0) > 0
        and int(summary.get("throttle_low_arm_violation_count") or 0) == 0
    )


def _arm_ack_ready(report: Mapping[str, Any]) -> bool:
    summary = _mapping(report.get("summary"))
    return report.get("schema") == RC_REPORT_SCHEMA and int(summary.get("fc_armed_frame_count") or 0) > 0


def _readiness_state(status: str, target_selected: bool) -> str:
    if status != "PASS":
        return "BLOCKED_SOURCE_REPORT"
    if target_selected:
        return "READY_FOR_TARGET_BUILD_REVIEW"
    return "TARGET_OWNER_INPUT_REQUIRED"


def _step(step_id: str, detail: str, status: str) -> dict[str, str]:
    return {
        "step_id": step_id,
        "status": status,
        "detail": detail,
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


def _selected(value: str) -> bool:
    return bool(value.strip()) and value != OWNER_SELECTION_REQUIRED


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
