"""Raspberry Pi runtime planning for FPV AI Gate-Lock."""

from __future__ import annotations

from fpv_ai.runtime_rpi.bench_hil import (
    build_bench_hil_report,
    write_bench_hil_report,
)
from fpv_ai.runtime_rpi.command_scheduler import (
    build_scheduled_command_sequence,
    write_scheduled_command_outputs,
)
from fpv_ai.runtime_rpi.device_adapters import (
    build_device_adapter_audit,
    write_device_adapter_audit,
)
from fpv_ai.runtime_rpi.dry_run import (
    build_rpi_runtime_loop_report,
    render_systemd_unit,
    write_rpi_runtime_dry_run_outputs,
)
from fpv_ai.runtime_rpi.protocol_readiness import (
    build_protocol_readiness_report,
    write_protocol_readiness_outputs,
)

__all__ = [
    "build_bench_hil_report",
    "build_device_adapter_audit",
    "build_protocol_readiness_report",
    "build_rpi_runtime_loop_report",
    "build_scheduled_command_sequence",
    "render_systemd_unit",
    "write_bench_hil_report",
    "write_device_adapter_audit",
    "write_protocol_readiness_outputs",
    "write_rpi_runtime_dry_run_outputs",
    "write_scheduled_command_outputs",
]
