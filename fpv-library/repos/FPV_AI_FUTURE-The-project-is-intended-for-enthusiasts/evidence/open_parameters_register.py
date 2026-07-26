"""Open-parameter register for the FPV AI Gate-Lock MVP.

The register turns the open-parameter section of the TZ into a machine-readable
dry-run artifact. It records which values are only defaults, which values are
selected for synthetic review, which values are deferred, and which values still
require project-owner or hardware-owner decisions.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fpv_ai.control.speed import SpeedMode
from fpv_ai.datasets.config import CONFIG_SCHEMA, FpvRacingGateConfig, load_fpv_racing_gate_config

OPEN_PARAMETERS_SCHEMA = "fpv_mvp_open_parameters_register.v1"
OWNER_INTAKE_SCHEMA = "fpv_betaflight_owner_decision_intake.v1"
OWNER_TARGET_PIPELINE_SCHEMA = "fpv_betaflight_owner_target_pipeline.v1"


def build_open_parameters_register(
    *,
    fpv_config: FpvRacingGateConfig,
    owner_decision_intake: Mapping[str, Any],
    owner_target_pipeline: Mapping[str, Any],
    fpv_config_path: Path | str | None = None,
    owner_decision_intake_path: Path | str | None = None,
    owner_target_pipeline_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    parameters = _parameters(
        fpv_config=fpv_config,
        owner_decision_intake=owner_decision_intake,
        owner_target_pipeline=owner_target_pipeline,
    )
    checks = _checks(
        fpv_config=fpv_config,
        owner_decision_intake=owner_decision_intake,
        owner_target_pipeline=owner_target_pipeline,
        parameters=parameters,
    )
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    owner_required_count = _status_count(parameters, "OWNER_DECISION_REQUIRED")
    return {
        "schema": OPEN_PARAMETERS_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "register_state": _register_state(status, owner_required_count),
        "source_reports": [
            _source_report("fpv_racing_gate_config", fpv_config.schema, "PASS", fpv_config_path, CONFIG_SCHEMA),
            _source_report(
                "owner_decision_intake",
                str(owner_decision_intake.get("schema") or ""),
                str(owner_decision_intake.get("status") or ""),
                owner_decision_intake_path,
                OWNER_INTAKE_SCHEMA,
            ),
            _source_report(
                "owner_target_pipeline",
                str(owner_target_pipeline.get("schema") or ""),
                str(owner_target_pipeline.get("status") or ""),
                owner_target_pipeline_path,
                OWNER_TARGET_PIPELINE_SCHEMA,
            ),
        ],
        "summary": {
            "source_report_count": 3,
            "parameter_count": len(parameters),
            "owner_required_count": owner_required_count,
            "dry_run_default_count": _status_count(parameters, "DRY_RUN_DEFAULT"),
            "selected_for_dry_run_count": _status_count(parameters, "SELECTED_FOR_DRY_RUN"),
            "deferred_later_phase_count": _status_count(parameters, "DEFERRED_LATER_PHASE"),
            "target_selected": _summary(owner_target_pipeline).get("target_selected") is True,
            "promotion_ready": _summary(owner_target_pipeline).get("promotion_ready") is True,
            "hardware_test_authorized": False,
            "no_prop_bench_authorized": False,
            "flight_commands_published": False,
            "field_proof_claimed": False,
            "training_launched": False,
        },
        "parameters": parameters,
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "register_only": True,
            "does_not_select_hardware_automatically": True,
            "does_not_authorize_hardware_test": True,
            "does_not_authorize_no_prop_bench": True,
            "does_not_open_live_cameras": True,
            "does_not_read_gpio": True,
            "does_not_open_uart": True,
            "does_not_start_service": True,
            "does_not_publish_flight_commands": True,
            "does_not_compile_or_flash_betaflight": True,
            "does_not_launch_training": True,
        },
    }


def write_open_parameters_register(
    *,
    fpv_config_yaml: Path,
    owner_decision_intake_json: Path,
    owner_target_pipeline_json: Path,
    output_json: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    report = build_open_parameters_register(
        fpv_config=load_fpv_racing_gate_config(fpv_config_yaml),
        owner_decision_intake=_read_json(owner_decision_intake_json),
        owner_target_pipeline=_read_json(owner_target_pipeline_json),
        fpv_config_path=fpv_config_yaml,
        owner_decision_intake_path=owner_decision_intake_json,
        owner_target_pipeline_path=owner_target_pipeline_json,
        project_root=project_root,
    )
    persisted = dict(report)
    persisted["register_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _parameters(
    *,
    fpv_config: FpvRacingGateConfig,
    owner_decision_intake: Mapping[str, Any],
    owner_target_pipeline: Mapping[str, Any],
) -> list[dict[str, Any]]:
    target_input = _mapping(owner_decision_intake.get("target_profile_input"))
    target_lock = fpv_config.target_lock
    race_profile = fpv_config.speed_policy.profile(SpeedMode.RACE_SPEED)
    return [
        _owner_value("betaflight_repo_url", "betaflight", target_input, "Betaflight fork repository URL."),
        _owner_value("betaflight_branch", "betaflight", target_input, "Betaflight fork branch or commit."),
        _owner_value("fc_target", "betaflight", target_input, "Exact flight-controller target/board."),
        _owner_value("ai_uart_port", "betaflight", target_input, "Dedicated AI UART port on the FC."),
        _owner_value("serial_mode", "betaflight", target_input, "AI command input mode."),
        _owner_value("electrical_voltage_level", "betaflight", target_input, "UART voltage and wiring domain."),
        _parameter(
            "serial_baud",
            "protocol",
            target_input.get("serial_baud"),
            "DRY_RUN_DEFAULT",
            "UART baud is set for dry-run and must be reviewed against the selected FC.",
        ),
        _parameter(
            "command_rate_hz",
            "protocol",
            target_input.get("command_rate_hz"),
            "DRY_RUN_DEFAULT",
            "AI command frequency is set for dry-run and must be reviewed on the selected FC.",
        ),
        _parameter(
            "ai_accelerator_exact_model",
            "rpi_runtime",
            fpv_config.runtime_rpi.ai_accelerator,
            "OWNER_DECISION_REQUIRED",
            "Exact Raspberry Pi AI HAT/Hailo module must be selected and benchmarked.",
        ),
        _parameter(
            "rgb_camera_model",
            "rpi_runtime",
            f"{fpv_config.runtime_rpi.primary_camera}:{fpv_config.runtime_rpi.rgb_camera_device}",
            "OWNER_DECISION_REQUIRED",
            "Exact RGB camera model must be selected.",
        ),
        _parameter(
            "rgb_lens_exposure_frame_rate",
            "rpi_runtime",
            "",
            "OWNER_DECISION_REQUIRED",
            "Lens, exposure, and camera frame rate must be selected for gate tracking.",
        ),
        _parameter(
            "thermal_camera_model",
            "rpi_runtime",
            fpv_config.runtime_rpi.thermal_camera_device,
            "DEFERRED_LATER_PHASE",
            "Thermal camera is optional/future for MVP gate detection.",
        ),
        _parameter(
            "lock_confidence_threshold",
            "target_lock",
            target_lock.confidence_threshold,
            "DRY_RUN_DEFAULT",
            "Gate lock threshold is configured for dry-run video/runtime tests.",
        ),
        _parameter(
            "stable_frame_count",
            "target_lock",
            target_lock.stable_frame_count,
            "DRY_RUN_DEFAULT",
            "Temporal lock stability frame count is configured for dry-run tests.",
        ),
        _parameter(
            "predictive_track_duration_ms",
            "target_lock",
            target_lock.predictive_track_ms,
            "DRY_RUN_DEFAULT",
            "Predictive tracking duration is configured for dry-run recovery tests.",
        ),
        _parameter(
            "reacquire_search_window_ms",
            "target_lock",
            target_lock.reacquire_track_ms,
            "DRY_RUN_DEFAULT",
            "Reacquire search window is configured for dry-run recovery tests.",
        ),
        _parameter(
            "race_speed_operator_limit_mps",
            "speed",
            target_input.get("operator_limit_mps", race_profile.operator_limit_mps),
            "SELECTED_FOR_DRY_RUN",
            "Race-speed operator limit is selected for dry-run/workorder review only.",
        ),
        _parameter(
            "first_flight_speed_limit_mps",
            "speed",
            race_profile.operator_limit_mps,
            "OWNER_DECISION_REQUIRED",
            "First controlled-flight speed limit remains a project-owner decision.",
        ),
        _parameter(
            "gate_size_dimensions",
            "gate_target",
            "",
            "OWNER_DECISION_REQUIRED",
            "Gate/ring size or dataset target distribution must be selected for model and pass-through review.",
        ),
        _parameter(
            "hand_release_detection_thresholds",
            "launch",
            "",
            "OWNER_DECISION_REQUIRED",
            "Hand-release detection thresholds must be defined before no-prop/flight review.",
        ),
        _parameter(
            "independent_kill_verification",
            "hardware_safety",
            "",
            "OWNER_DECISION_REQUIRED",
            "Manual independent kill/power cut must be physically verified outside Raspberry Pi software.",
        ),
        _parameter(
            "first_hardware_test_scope",
            "hardware_safety",
            "",
            "OWNER_DECISION_REQUIRED",
            "Project owner must define what the first hardware test may and may not do.",
        ),
        _parameter(
            "packet_format_contract",
            "protocol",
            "fpv_ai_command/fork_interface_contract_v1",
            "SELECTED_FOR_DRY_RUN",
            "Packet/frame contract is selected for dry-run protocol review only.",
        ),
    ]


def _checks(
    *,
    fpv_config: FpvRacingGateConfig,
    owner_decision_intake: Mapping[str, Any],
    owner_target_pipeline: Mapping[str, Any],
    parameters: list[dict[str, Any]],
) -> list[dict[str, str]]:
    pipeline_summary = _summary(owner_target_pipeline)
    statuses = {str(row["status"]) for row in parameters}
    return [
        _check("fpv_config_schema_valid", fpv_config.schema == CONFIG_SCHEMA, fpv_config.schema),
        _check(
            "owner_decision_intake_schema_valid",
            owner_decision_intake.get("schema") == OWNER_INTAKE_SCHEMA,
            str(owner_decision_intake.get("schema") or ""),
        ),
        _check(
            "owner_target_pipeline_schema_valid",
            owner_target_pipeline.get("schema") == OWNER_TARGET_PIPELINE_SCHEMA,
            str(owner_target_pipeline.get("schema") or ""),
        ),
        _check(
            "source_reports_passed",
            owner_decision_intake.get("status") == "PASS"
            and owner_target_pipeline.get("status") == "PASS",
            "owner intake and pipeline",
        ),
        _check(
            "parameters_declared",
            len(parameters) >= 20,
            str(len(parameters)),
        ),
        _check(
            "owner_required_parameters_remain_visible",
            "OWNER_DECISION_REQUIRED" in statuses,
            str(_status_count(parameters, "OWNER_DECISION_REQUIRED")),
        ),
        _check(
            "simulation_not_used_for_real_target",
            pipeline_summary.get("simulation_used_for_real_target") is False,
            "owner target pipeline",
        ),
        _check(
            "hardware_not_authorized",
            True,
            "register does not authorize hardware",
        ),
        _check(
            "no_prop_bench_not_authorized",
            True,
            "register does not authorize no-prop bench",
        ),
        _check(
            "field_proof_not_claimed",
            True,
            "register is not field proof",
        ),
        _check("register_does_not_authorize_hardware", True, "open-parameter register only"),
        _check("no_live_uart_access", True, "file-only register"),
    ]


def _owner_value(
    parameter_id: str,
    category: str,
    target_input: Mapping[str, Any],
    detail: str,
) -> dict[str, Any]:
    value = target_input.get(parameter_id)
    selected = isinstance(value, str) and bool(value.strip()) and value != "OWNER_SELECTION_REQUIRED"
    return _parameter(
        parameter_id,
        category,
        value,
        "SELECTED_FOR_DRY_RUN" if selected else "OWNER_DECISION_REQUIRED",
        detail,
    )


def _parameter(
    parameter_id: str,
    category: str,
    value: Any,
    status: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "parameter_id": parameter_id,
        "category": category,
        "value": "" if value is None else value,
        "status": status,
        "detail": detail,
    }


def _register_state(status: str, owner_required_count: int) -> str:
    if status != "PASS":
        return "BLOCKED"
    if owner_required_count:
        return "OWNER_PARAMETERS_REQUIRED"
    return "READY_FOR_OWNER_REVIEW"


def _status_count(parameters: list[dict[str, Any]], status: str) -> int:
    return sum(1 for row in parameters if row["status"] == status)


def _source_report(
    report_id: str,
    schema: str,
    status: str,
    path: Path | str | None,
    expected_schema: str,
) -> dict[str, str]:
    path_obj = Path(path) if path is not None else None
    return {
        "report_id": report_id,
        "path": "" if path is None else str(path),
        "schema": schema,
        "expected_schema": expected_schema,
        "status": status,
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
