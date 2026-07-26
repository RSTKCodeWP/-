"""Raspberry Pi runtime dry-run/service planning for FPV AI Gate-Lock.

This module does not open cameras, GPIO, UART, or install/start services. It
turns current mission dry-run artifacts into runtime readiness evidence and a
systemd unit template for later review.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fpv_ai.datasets.config import FpvRacingGateConfig, load_fpv_racing_gate_config
from fpv_ai.runtime.timeline import load_json
from fpv_ai.runtime_rpi.device_adapters import build_device_adapter_audit

READINESS_SCHEMA = "fpv_rpi_runtime_readiness_report.v1"
LOOP_SCHEMA = "fpv_rpi_runtime_loop_report.v1"
SERVICE_PLAN_SCHEMA = "fpv_rpi_runtime_service_plan.v1"


def write_rpi_runtime_dry_run_outputs(
    *,
    config_path: Path,
    mission_output_dir: Path,
    output_dir: Path,
    max_iterations: int | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = project_root or Path.cwd()
    config = load_fpv_racing_gate_config(config_path)
    timeline_path = mission_output_dir / "mission_timeline.json"
    timeline = load_json(timeline_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    loop_report_path = output_dir / "rpi_runtime_loop_report.json"
    service_plan_path = output_dir / "rpi_runtime_service_plan.json"
    device_adapter_audit_path = output_dir / "device_adapter_audit_report.json"
    unit_template_path = output_dir / "fpv-ai-gate-lock.service"
    readiness_report_path = output_dir / "rpi_runtime_readiness_report.json"

    loop_report = build_rpi_runtime_loop_report(
        timeline=timeline,
        max_iterations=max_iterations,
        source_path=timeline_path,
    )
    unit_text = render_systemd_unit(
        project_root=root,
        config_path=config_path,
        mission_output_dir=mission_output_dir,
        output_dir=output_dir,
    )
    unit_template_path.write_text(unit_text, encoding="utf-8")
    service_plan = build_service_plan(
        config=config,
        unit_text=unit_text,
        unit_template_path=unit_template_path,
        project_root=root,
        config_path=config_path,
        mission_output_dir=mission_output_dir,
        output_dir=output_dir,
    )
    device_adapter_audit = build_device_adapter_audit(config, config_path=config_path)
    readiness_report = build_readiness_report(
        config=config,
        config_path=config_path,
        mission_output_dir=mission_output_dir,
        timeline_path=timeline_path,
        loop_report=loop_report,
        service_plan=service_plan,
        device_adapter_audit=device_adapter_audit,
        service_plan_path=service_plan_path,
        device_adapter_audit_path=device_adapter_audit_path,
        unit_template_path=unit_template_path,
        loop_report_path=loop_report_path,
        report_path=readiness_report_path,
    )

    _write_json(loop_report_path, loop_report)
    _write_json(service_plan_path, service_plan)
    _write_json(device_adapter_audit_path, device_adapter_audit)
    _write_json(readiness_report_path, readiness_report)
    return readiness_report


def build_rpi_runtime_loop_report(
    *,
    timeline: Mapping[str, Any],
    max_iterations: int | None = None,
    source_path: Path | str | None = None,
) -> dict[str, Any]:
    rows = timeline.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("mission timeline must contain non-empty rows")
    selected_rows = rows[:max_iterations] if max_iterations is not None else rows
    loop_rows = [_loop_row(index, row) for index, row in enumerate(selected_rows)]
    source = "" if source_path is None else str(source_path)
    return {
        "schema": LOOP_SCHEMA,
        "status": "PASS",
        "generated_at": _utc_now(),
        "source_path": source,
        "source_schema": str(timeline.get("schema") or ""),
        "summary": {
            "iteration_count": len(loop_rows),
            "timeline_row_count": len(rows),
            "max_iterations": max_iterations,
            "ai_control_allowed_count": sum(1 for row in loop_rows if row["ai_control_allowed"]),
            "watchdog_rejected_count": sum(1 for row in loop_rows if row["watchdog_status"] not in {"", "AI_COMMAND_ACCEPTED"}),
            "manual_kill_count": sum(1 for row in loop_rows if row["manual_kill"] is True),
            "final_launch_state": str(loop_rows[-1]["launch_state"] or ""),
            "mission_complete": loop_rows[-1]["launch_state"] == "COMPLETE",
            "training_launched": False,
            "cameras_opened": False,
            "gpio_read": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "iterations": loop_rows,
        "safety_boundary": _runtime_safety_boundary(),
    }


def build_service_plan(
    *,
    config: FpvRacingGateConfig,
    unit_text: str,
    unit_template_path: Path,
    project_root: Path,
    config_path: Path,
    mission_output_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    return {
        "schema": SERVICE_PLAN_SCHEMA,
        "status": "PASS",
        "generated_at": _utc_now(),
        "service_name": "fpv-ai-gate-lock.service",
        "runtime_domain": config.domain,
        "unit_template_path": str(unit_template_path),
        "unit_sha256": hashlib.sha256(unit_text.encode("utf-8")).hexdigest(),
        "working_directory": str(project_root),
        "exec_start": _exec_start(project_root, config_path, mission_output_dir, output_dir),
        "environment": {
            "FPV_AI_DRY_RUN": "1",
            "FPV_AI_NO_CAMERA": "1",
            "FPV_AI_NO_UART": "1",
            "FPV_AI_NO_GPIO": "1",
        },
        "systemd_installation_performed": False,
        "service_started": False,
        "service_enabled": False,
        "requires_manual_review_before_install": True,
        "hardware_test_authorized": False,
        "safety_boundary": _runtime_safety_boundary(),
    }


def build_readiness_report(
    *,
    config: FpvRacingGateConfig,
    config_path: Path,
    mission_output_dir: Path,
    timeline_path: Path,
    loop_report: Mapping[str, Any],
    service_plan: Mapping[str, Any],
    device_adapter_audit: Mapping[str, Any],
    service_plan_path: Path,
    device_adapter_audit_path: Path,
    unit_template_path: Path,
    loop_report_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    checks = [
        _check("config_loaded", True, str(config_path)),
        _check("runtime_rpi_config_present", bool(config.runtime_rpi.primary_camera), config.runtime_rpi.primary_camera),
        _check("primary_camera_declared", config.runtime_rpi.primary_camera == "rgb", config.runtime_rpi.primary_camera),
        _check("ai_accelerator_declared", bool(config.runtime_rpi.ai_accelerator), config.runtime_rpi.ai_accelerator),
        _check("command_transport_declared", bool(config.runtime_rpi.command_transport), config.runtime_rpi.command_transport),
        _check("stale_command_timeout_configured", config.runtime_rpi.stale_ai_command_timeout_ms > 0, str(config.runtime_rpi.stale_ai_command_timeout_ms)),
        _check("logging_required", config.runtime_rpi.log_frames_commands_and_states, "log_frames_commands_and_states"),
        _check("software_does_not_authorize_hardware", config.hardware_authority.software_does_not_authorize_hardware_tests, "hardware_authority"),
        _check("manual_kill_required", config.minimum_hardware_protection.manual_kill_switch_required, "minimum_hardware_protection"),
        _check("stale_command_protection_required", config.minimum_hardware_protection.stale_command_protection_required, "minimum_hardware_protection"),
        _check("mission_timeline_available", timeline_path.exists(), str(timeline_path)),
        _check("runtime_loop_passed", loop_report.get("status") == "PASS", str(loop_report_path)),
        _check("systemd_unit_template_generated", service_plan.get("status") == "PASS", str(unit_template_path)),
        _check("device_adapter_audit_passed", device_adapter_audit.get("status") == "PASS", str(device_adapter_audit_path)),
        _check(
            "device_adapters_live_disabled",
            int(device_adapter_audit["summary"]["live_enabled_adapter_count"]) == 0,
            "dry-run only",
        ),
        _check("systemd_not_installed", service_plan.get("systemd_installation_performed") is False, "dry-run only"),
    ]
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "schema": READINESS_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "config_path": str(config_path),
        "mission_output_dir": str(mission_output_dir),
        "runtime": {
            "primary_camera": config.runtime_rpi.primary_camera,
            "secondary_camera": config.runtime_rpi.secondary_camera,
            "ai_accelerator": config.runtime_rpi.ai_accelerator,
            "command_transport": config.runtime_rpi.command_transport,
            "stale_ai_command_timeout_ms": config.runtime_rpi.stale_ai_command_timeout_ms,
            "log_frames_commands_and_states": config.runtime_rpi.log_frames_commands_and_states,
        },
        "summary": {
            "check_count": len(checks),
            "passed_check_count": sum(1 for check in checks if check["status"] == "PASS"),
            "failed_check_count": sum(1 for check in checks if check["status"] == "FAIL"),
            "loop_iteration_count": int(loop_report["summary"]["iteration_count"]),
            "loop_final_launch_state": str(loop_report["summary"]["final_launch_state"]),
            "mission_complete": bool(loop_report["summary"]["mission_complete"]),
            "device_adapter_count": int(device_adapter_audit["summary"]["adapter_count"]),
            "live_enabled_adapter_count": int(device_adapter_audit["summary"]["live_enabled_adapter_count"]),
            "systemd_installation_performed": False,
            "service_started": False,
            "training_launched": False,
            "cameras_opened": False,
            "gpio_read": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "checks": checks,
        "artifact_paths": {
            "loop_report_path": str(loop_report_path),
            "service_plan_path": str(service_plan_path),
            "device_adapter_audit_path": str(device_adapter_audit_path),
            "unit_template_path": str(unit_template_path),
            "readiness_report_path": str(report_path),
        },
        "safety_boundary": _runtime_safety_boundary(),
    }


def render_systemd_unit(
    *,
    project_root: Path,
    config_path: Path,
    mission_output_dir: Path,
    output_dir: Path,
) -> str:
    exec_start = _exec_start(project_root, config_path, mission_output_dir, output_dir)
    return "\n".join(
        [
            "[Unit]",
            "Description=FPV AI Gate-Lock runtime dry-run",
            "After=network-online.target",
            "Wants=network-online.target",
            "",
            "[Service]",
            "Type=oneshot",
            f"WorkingDirectory={_unit_quote(project_root)}",
            "Environment=FPV_AI_DRY_RUN=1",
            "Environment=FPV_AI_NO_CAMERA=1",
            "Environment=FPV_AI_NO_UART=1",
            "Environment=FPV_AI_NO_GPIO=1",
            f"ExecStart={exec_start}",
            "NoNewPrivileges=true",
            "PrivateTmp=true",
            "ProtectSystem=strict",
            "ProtectHome=true",
            f"ReadWritePaths={_unit_quote(output_dir)}",
            "",
            "[Install]",
            "WantedBy=multi-user.target",
            "",
        ]
    )


def _loop_row(iteration_index: int, row: Any) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise ValueError("timeline row must be a mapping")
    watchdog_allowed = row.get("watchdog_ai_control_allowed") is True
    launch_allowed = row.get("launch_ai_control_allowed") is True
    return {
        "iteration_index": iteration_index,
        "frame_index": int(row["frame_index"]),
        "timestamp_ms": int(row["timestamp_ms"]),
        "lock_tracking_state": str(row.get("lock_tracking_state") or ""),
        "launch_state": str(row.get("launch_state") or ""),
        "watchdog_status": str(row.get("watchdog_status") or ""),
        "ai_control_allowed": watchdog_allowed and launch_allowed,
        "command_crc32": str(row.get("command_crc32") or ""),
        "transport_frame_crc32": str(row.get("transport_frame_crc32") or ""),
        "manual_kill": bool(row.get("manual_kill", False)),
        "recommended_action": str(row.get("launch_recommended_action") or ""),
    }


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    }


def _exec_start(project_root: Path, config_path: Path, mission_output_dir: Path, output_dir: Path) -> str:
    return (
        f"{_unit_quote(project_root / '.venv/bin/python')} "
        f"{_unit_quote(project_root / 'scripts/fpv_rpi_runtime_dry_run.py')} "
        f"--config {_unit_quote(config_path)} "
        f"--mission-output-dir {_unit_quote(mission_output_dir)} "
        f"--output-dir {_unit_quote(output_dir)} --quiet"
    )


def _unit_quote(path: Path) -> str:
    value = str(path)
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _runtime_safety_boundary() -> dict[str, bool]:
    return {
        "dry_run_only": True,
        "does_not_launch_training": True,
        "does_not_open_live_cameras": True,
        "does_not_read_gpio": True,
        "does_not_open_uart": True,
        "does_not_install_systemd_unit": True,
        "does_not_start_service": True,
        "does_not_authorize_hardware_test": True,
        "does_not_publish_flight_commands": True,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
