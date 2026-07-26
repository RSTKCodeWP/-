"""Scheduled command protocol readiness dry-run for FPV AI Gate-Lock.

This layer verifies that the runtime scheduled command stream can be framed,
decoded, and accepted by the Betaflight-side watchdog contract. It only reads
and writes files; it never opens UART or publishes flight commands.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fpv_ai.betaflight_link.transport import LinkTimingConfig, run_transport_dry_run
from fpv_ai.runtime.watchdog import WatchdogConfig, run_watchdog_audit
from fpv_ai.runtime_rpi.command_scheduler import SCHEDULE_SCHEMA, load_scheduled_command_sequence

REPORT_SCHEMA = "fpv_runtime_protocol_readiness_report.v1"


def build_protocol_readiness_report(
    scheduled_commands: Mapping[str, Any],
    *,
    command_timeout_ms: int = 250,
    source_path: Path | str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    if command_timeout_ms <= 0:
        raise ValueError("command_timeout_ms must be positive")
    if scheduled_commands.get("schema") != SCHEDULE_SCHEMA:
        raise ValueError(f"expected {SCHEDULE_SCHEMA} payload")

    source = "" if source_path is None else str(source_path)
    transport_frames, transport_report = run_transport_dry_run(
        scheduled_commands,
        source_path=source,
        timing=LinkTimingConfig(command_timeout_ms=command_timeout_ms),
    )
    watchdog_report = run_watchdog_audit(
        transport_frames,
        source_path="memory://fpv_runtime_scheduled_transport_frames",
        config=WatchdogConfig(command_timeout_ms=command_timeout_ms),
    )
    readiness_report = _readiness_report(
        scheduled_commands=scheduled_commands,
        transport_frames=transport_frames,
        transport_report=transport_report,
        watchdog_report=watchdog_report,
        command_timeout_ms=command_timeout_ms,
        source_path=source,
    )
    return transport_frames, transport_report, watchdog_report, readiness_report


def write_protocol_readiness_outputs(
    *,
    scheduled_command_json: Path,
    output_dir: Path,
    command_timeout_ms: int = 250,
) -> dict[str, Any]:
    scheduled_commands = load_scheduled_command_sequence(scheduled_command_json)
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_path = output_dir / "scheduled_transport_frames.json"
    transport_report_path = output_dir / "scheduled_transport_dry_run_report.json"
    watchdog_report_path = output_dir / "scheduled_watchdog_report.json"
    readiness_report_path = output_dir / "protocol_readiness_report.json"

    transport_frames, transport_report, watchdog_report, readiness_report = build_protocol_readiness_report(
        scheduled_commands,
        command_timeout_ms=command_timeout_ms,
        source_path=scheduled_command_json,
    )
    persisted_transport_report = dict(transport_report)
    persisted_transport_report["frames_path"] = str(frames_path)
    persisted_transport_report["report_path"] = str(transport_report_path)
    persisted_watchdog_report = dict(watchdog_report)
    persisted_watchdog_report["report_path"] = str(watchdog_report_path)
    persisted_readiness_report = dict(readiness_report)
    persisted_readiness_report["subreports"] = {
        "transport": {
            "schema": str(transport_report.get("schema") or ""),
            "status": str(transport_report.get("status") or ""),
            "report_path": str(transport_report_path),
        },
        "watchdog": {
            "schema": str(watchdog_report.get("schema") or ""),
            "status": str(watchdog_report.get("status") or ""),
            "report_path": str(watchdog_report_path),
        },
    }
    persisted_readiness_report["artifact_paths"] = {
        "scheduled_command_sequence_path": str(scheduled_command_json),
        "transport_frames_path": str(frames_path),
        "transport_report_path": str(transport_report_path),
        "watchdog_report_path": str(watchdog_report_path),
        "readiness_report_path": str(readiness_report_path),
    }

    _write_json(frames_path, transport_frames)
    _write_json(transport_report_path, persisted_transport_report)
    _write_json(watchdog_report_path, persisted_watchdog_report)
    _write_json(readiness_report_path, persisted_readiness_report)
    return persisted_readiness_report


def _readiness_report(
    *,
    scheduled_commands: Mapping[str, Any],
    transport_frames: Mapping[str, Any],
    transport_report: Mapping[str, Any],
    watchdog_report: Mapping[str, Any],
    command_timeout_ms: int,
    source_path: str,
) -> dict[str, Any]:
    scheduled_command_count = int(scheduled_commands.get("scheduled_command_count") or 0)
    transport_summary = _mapping(transport_report["summary"])
    watchdog_summary = _mapping(watchdog_report["summary"])
    checks = [
        _check("scheduled_commands_present", scheduled_command_count > 0, f"commands={scheduled_command_count}"),
        _check("transport_passed", transport_report.get("status") == "PASS", str(transport_report.get("status") or "")),
        _check("watchdog_passed", watchdog_report.get("status") == "PASS", str(watchdog_report.get("status") or "")),
        _check(
            "all_commands_framed",
            int(transport_summary["framed_command_count"]) == scheduled_command_count,
            f"{transport_summary['framed_command_count']}/{scheduled_command_count}",
        ),
        _check(
            "all_frames_decoded",
            int(watchdog_summary["decoded_frame_count"]) == int(transport_frames["frame_count"]),
            f"{watchdog_summary['decoded_frame_count']}/{transport_frames['frame_count']}",
        ),
        _check("no_transport_stale_commands", int(transport_summary["stale_command_count"]) == 0, str(transport_summary["stale_command_count"])),
        _check("no_transport_sequence_gaps", int(transport_summary["sequence_gap_count"]) == 0, str(transport_summary["sequence_gap_count"])),
        _check("no_watchdog_rejections", int(watchdog_summary["rejected_command_count"]) == 0, str(watchdog_summary["rejected_command_count"])),
        _check("heartbeat_accepted", int(watchdog_summary["heartbeat_lost_count"]) == 0, str(watchdog_summary["heartbeat_lost_count"])),
        _check("watchdog_timeout_clear", int(watchdog_summary["timeout_count"]) == 0, str(watchdog_summary["timeout_count"])),
        _check("max_interval_within_timeout", int(watchdog_summary["max_command_interval_ms"]) <= command_timeout_ms, str(watchdog_summary["max_command_interval_ms"])),
        _check("no_live_uart_access", True, "dry-run only"),
    ]
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "schema": REPORT_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "source_path": source_path,
        "source_schema": str(scheduled_commands.get("schema") or ""),
        "protocol": str(transport_report.get("protocol") or ""),
        "summary": {
            "scheduled_command_count": scheduled_command_count,
            "transport_status": str(transport_report.get("status") or ""),
            "watchdog_status": str(watchdog_report.get("status") or ""),
            "transport_frame_count": int(transport_frames["frame_count"]),
            "framed_command_count": int(transport_summary["framed_command_count"]),
            "decoded_frame_count": int(watchdog_summary["decoded_frame_count"]),
            "accepted_command_count": int(watchdog_summary["accepted_command_count"]),
            "rejected_command_count": int(watchdog_summary["rejected_command_count"]),
            "stale_command_count": int(transport_summary["stale_command_count"]),
            "sequence_gap_count": int(transport_summary["sequence_gap_count"]) + int(watchdog_summary["sequence_gap_count"]),
            "heartbeat_lost_count": int(watchdog_summary["heartbeat_lost_count"]),
            "timeout_count": int(watchdog_summary["timeout_count"]),
            "max_command_interval_ms": int(watchdog_summary["max_command_interval_ms"]),
            "command_timeout_ms": command_timeout_ms,
            "training_launched": False,
            "cameras_opened": False,
            "gpio_read": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "checks": checks,
        "subreports": {
            "transport": _subreport_ref(transport_report),
            "watchdog": _subreport_ref(watchdog_report),
        },
        "artifact_paths": {
            "scheduled_command_sequence_path": "",
            "transport_frames_path": "",
            "transport_report_path": "",
            "watchdog_report_path": "",
            "readiness_report_path": "",
        },
        "safety_boundary": {
            "dry_run_only": True,
            "does_not_launch_training": True,
            "does_not_open_live_cameras": True,
            "does_not_read_gpio": True,
            "does_not_open_uart": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
            "protocol_outputs_are_file_only": True,
        },
    }


def _subreport_ref(report: Mapping[str, Any]) -> dict[str, str]:
    return {
        "schema": str(report.get("schema") or ""),
        "status": str(report.get("status") or ""),
        "report_path": str(report.get("report_path") or ""),
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("expected mapping")
    return value


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
