"""Dry-run Raspberry Pi device adapter contracts for FPV AI Gate-Lock.

The functions here define the hardware-facing adapter plan without opening
cameras, GPIO, UART, or publishing commands. Live adapters stay disabled until
the project owner explicitly authorizes a hardware test outside this software.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fpv_ai.datasets.config import FpvRacingGateConfig, load_fpv_racing_gate_config

ADAPTER_AUDIT_SCHEMA = "fpv_rpi_device_adapter_audit.v1"
DRY_RUN_DISABLED_MODE = "dry_run_disabled"


@dataclass(frozen=True)
class DeviceAdapterContract:
    name: str
    adapter_type: str
    configured_resource: str
    required_for_mvp: bool
    intended_operation: str
    mode: str

    def to_payload(self) -> dict[str, Any]:
        resource_declared = bool(self.configured_resource)
        live_enabled = self.mode != DRY_RUN_DISABLED_MODE
        status = "PASS" if not live_enabled and (resource_declared or not self.required_for_mvp) else "FAIL"
        return {
            "name": self.name,
            "adapter_type": self.adapter_type,
            "configured_resource": self.configured_resource,
            "required_for_mvp": self.required_for_mvp,
            "intended_operation": self.intended_operation,
            "mode": self.mode,
            "status": status,
            "resource_declared": resource_declared,
            "live_enabled": live_enabled,
            "open_attempted": False,
            "read_attempted": False,
            "write_attempted": False,
            "commands_published": False,
        }


def build_device_adapter_audit(
    config: FpvRacingGateConfig,
    *,
    config_path: Path | str | None = None,
) -> dict[str, Any]:
    adapters = [
        DeviceAdapterContract(
            name="rgb_camera",
            adapter_type="camera",
            configured_resource=config.runtime_rpi.rgb_camera_device,
            required_for_mvp=True,
            intended_operation="read RGB frames for gate detection",
            mode=config.runtime_rpi.adapter_mode,
        ),
        DeviceAdapterContract(
            name="thermal_camera",
            adapter_type="camera",
            configured_resource=config.runtime_rpi.thermal_camera_device,
            required_for_mvp=False,
            intended_operation="future optional thermal safety channel",
            mode=config.runtime_rpi.adapter_mode,
        ),
        DeviceAdapterContract(
            name="launcher_button_gpio",
            adapter_type="gpio_input",
            configured_resource=f"GPIO{config.runtime_rpi.launcher_button_gpio}",
            required_for_mvp=True,
            intended_operation="read target-lock/start button state",
            mode=config.runtime_rpi.adapter_mode,
        ),
        DeviceAdapterContract(
            name="manual_kill_gpio",
            adapter_type="gpio_input",
            configured_resource=f"GPIO{config.runtime_rpi.manual_kill_gpio}",
            required_for_mvp=True,
            intended_operation="read independent manual kill switch state",
            mode=config.runtime_rpi.adapter_mode,
        ),
        DeviceAdapterContract(
            name="betaflight_uart",
            adapter_type="uart",
            configured_resource=f"{config.runtime_rpi.uart_device}@{config.runtime_rpi.uart_baud}",
            required_for_mvp=True,
            intended_operation="future virtual receiver command stream",
            mode=config.runtime_rpi.adapter_mode,
        ),
    ]
    adapter_payloads = [adapter.to_payload() for adapter in adapters]
    checks = [
        _check(
            "adapter_mode_dry_run_disabled",
            config.runtime_rpi.adapter_mode == DRY_RUN_DISABLED_MODE,
            config.runtime_rpi.adapter_mode,
        ),
        _check("rgb_camera_resource_declared", bool(config.runtime_rpi.rgb_camera_device), config.runtime_rpi.rgb_camera_device),
        _check("launcher_button_gpio_declared", config.runtime_rpi.launcher_button_gpio >= 0, f"GPIO{config.runtime_rpi.launcher_button_gpio}"),
        _check("manual_kill_gpio_declared", config.runtime_rpi.manual_kill_gpio >= 0, f"GPIO{config.runtime_rpi.manual_kill_gpio}"),
        _check("uart_resource_declared", bool(config.runtime_rpi.uart_device), config.runtime_rpi.uart_device),
        _check("uart_baud_declared", config.runtime_rpi.uart_baud > 0, str(config.runtime_rpi.uart_baud)),
        _check("no_live_adapters_enabled", not any(adapter["live_enabled"] for adapter in adapter_payloads), "dry-run only"),
        _check("no_hardware_open_attempts", True, "audit builds contracts only"),
    ]
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "schema": ADAPTER_AUDIT_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "config_path": "" if config_path is None else str(config_path),
        "adapter_mode": config.runtime_rpi.adapter_mode,
        "summary": {
            "adapter_count": len(adapter_payloads),
            "required_adapter_count": sum(1 for adapter in adapter_payloads if adapter["required_for_mvp"]),
            "live_enabled_adapter_count": sum(1 for adapter in adapter_payloads if adapter["live_enabled"]),
            "hardware_open_attempt_count": 0,
            "hardware_read_attempt_count": 0,
            "hardware_write_attempt_count": 0,
            "training_launched": False,
            "cameras_opened": False,
            "gpio_read": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "checks": checks,
        "adapters": adapter_payloads,
        "safety_boundary": _adapter_safety_boundary(),
    }


def write_device_adapter_audit(
    *,
    config_path: Path,
    report_json: Path,
) -> dict[str, Any]:
    config = load_fpv_racing_gate_config(config_path)
    report = build_device_adapter_audit(config, config_path=config_path)
    persisted_report = dict(report)
    persisted_report["report_path"] = str(report_json)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(persisted_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted_report


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    }


def _adapter_safety_boundary() -> dict[str, bool]:
    return {
        "dry_run_only": True,
        "does_not_launch_training": True,
        "does_not_open_live_cameras": True,
        "does_not_read_gpio": True,
        "does_not_open_uart": True,
        "does_not_authorize_hardware_test": True,
        "does_not_publish_flight_commands": True,
        "live_enable_requires_project_owner": True,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
