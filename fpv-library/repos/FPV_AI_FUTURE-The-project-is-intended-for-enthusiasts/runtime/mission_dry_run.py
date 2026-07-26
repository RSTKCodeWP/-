"""Unified offline mission dry-run for FPV AI Gate-Lock.

This orchestrates the implemented MVP layers:

``detections -> gate lock -> AI commands -> transport frames -> watchdog -> launch state``.

It deliberately remains offline-only: no model training, live cameras, UART, or
hardware authorization.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from fpv_ai.betaflight_link.transport import LinkTimingConfig, run_transport_dry_run
from fpv_ai.control.speed import SpeedMode
from fpv_ai.datasets.config import FpvRacingGateConfig
from fpv_ai.evaluation.gate_lock import EvaluationFrame
from fpv_ai.runtime.launch_state import (
    LaunchConfig,
    build_synthetic_hand_launch_sequence,
    launch_inputs_from_command_sequence,
    run_launch_state_machine,
)
from fpv_ai.runtime.launcher_events import (
    build_launcher_event_report,
    launch_inputs_from_command_sequence_and_events,
)
from fpv_ai.runtime.offline_pipeline import run_offline_gate_pipeline
from fpv_ai.runtime.timeline import build_mission_timeline
from fpv_ai.runtime.watchdog import WatchdogConfig, run_watchdog_audit

REPORT_SCHEMA = "fpv_ai_mission_dry_run_report.v1"


class MissionLaunchMode(str, Enum):
    FROM_COMMANDS = "from_commands"
    SYNTHETIC_LAUNCH = "synthetic_launch"
    LAUNCHER_EVENTS = "launcher_events"


def run_mission_dry_run(
    frames: list[EvaluationFrame],
    *,
    config: FpvRacingGateConfig | None = None,
    speed_mode: SpeedMode = SpeedMode.RACE_SPEED,
    requested_speed_mps: float | None = None,
    operator_limit_mps: float | None = None,
    command_timeout_ms: int = 500,
    throttle_ramp_ms: int = 200,
    launch_mode: MissionLaunchMode | str = MissionLaunchMode.FROM_COMMANDS,
    launcher_events: dict[str, Any] | None = None,
    source_path: Path | str | None = None,
    source_schema: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    active_launch_mode = MissionLaunchMode(launch_mode)
    source = "" if source_path is None else str(source_path)
    sequence, offline_report = run_offline_gate_pipeline(
        frames,
        config=config,
        speed_mode=speed_mode,
        requested_speed_mps=requested_speed_mps,
        operator_limit_mps=operator_limit_mps,
        source_path=source,
    )
    transport_frames, transport_report = run_transport_dry_run(
        sequence,
        source_path="memory://fpv_ai_command_sequence",
        timing=LinkTimingConfig(command_timeout_ms=command_timeout_ms),
    )
    watchdog_report = run_watchdog_audit(
        transport_frames,
        source_path="memory://fpv_ai_transport_frames",
        config=WatchdogConfig(command_timeout_ms=command_timeout_ms),
    )

    if active_launch_mode is MissionLaunchMode.SYNTHETIC_LAUNCH:
        launch_inputs = build_synthetic_hand_launch_sequence()
        launch_source_path = "synthetic://fpv_hand_launch_state_machine"
        launch_source_schema = "fpv_ai_launch_input_sequence.synthetic.v1"
        launcher_event_report = None
    elif active_launch_mode is MissionLaunchMode.LAUNCHER_EVENTS:
        if launcher_events is None:
            raise ValueError("launcher_events payload is required for launcher_events mode")
        launch_inputs = launch_inputs_from_command_sequence_and_events(sequence, launcher_events)
        launch_source_path = "memory://fpv_ai_command_sequence+launcher_events"
        launch_source_schema = str(launcher_events.get("schema") or "")
        launcher_event_report = build_launcher_event_report(launcher_events, source_path="memory://launcher_events")
    else:
        launch_inputs = launch_inputs_from_command_sequence(sequence)
        launch_source_path = "memory://fpv_ai_command_sequence"
        launch_source_schema = str(sequence.get("schema") or "")
        launcher_event_report = None

    launch_report = run_launch_state_machine(
        launch_inputs,
        source_path=launch_source_path,
        source_schema=launch_source_schema,
        config=LaunchConfig(throttle_ramp_ms=throttle_ramp_ms),
    )
    timeline, timeline_report = build_mission_timeline(
        command_sequence=sequence,
        transport_frames=transport_frames,
        watchdog_report=watchdog_report,
        launcher_event_report=launcher_event_report,
        launch_report=launch_report,
        source_path="memory://fpv_mission_dry_run",
    )
    artifacts = {
        "command_sequence": sequence,
        "offline_pipeline_report": offline_report,
        "transport_frames": transport_frames,
        "transport_report": transport_report,
        "watchdog_report": watchdog_report,
        "launch_report": launch_report,
        "launcher_event_report": launcher_event_report,
        "timeline": timeline,
        "timeline_report": timeline_report,
    }
    report = _mission_report(
        artifacts,
        source_path=source,
        source_schema=source_schema,
        launch_mode=active_launch_mode,
        command_timeout_ms=command_timeout_ms,
        throttle_ramp_ms=throttle_ramp_ms,
        launcher_event_report=launcher_event_report,
        timeline_report=timeline_report,
    )
    return artifacts, report


def write_mission_dry_run_outputs(
    frames: list[EvaluationFrame],
    *,
    output_dir: Path,
    config: FpvRacingGateConfig | None = None,
    speed_mode: SpeedMode = SpeedMode.RACE_SPEED,
    requested_speed_mps: float | None = None,
    operator_limit_mps: float | None = None,
    command_timeout_ms: int = 500,
    throttle_ramp_ms: int = 200,
    launch_mode: MissionLaunchMode | str = MissionLaunchMode.FROM_COMMANDS,
    launcher_events: dict[str, Any] | None = None,
    source_path: Path | str | None = None,
    source_schema: str = "",
) -> dict[str, Any]:
    artifacts, report = run_mission_dry_run(
        frames,
        config=config,
        speed_mode=speed_mode,
        requested_speed_mps=requested_speed_mps,
        operator_limit_mps=operator_limit_mps,
        command_timeout_ms=command_timeout_ms,
        throttle_ramp_ms=throttle_ramp_ms,
        launch_mode=launch_mode,
        launcher_events=launcher_events,
        source_path=source_path,
        source_schema=source_schema,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "command_sequence_path": output_dir / "ai_command_sequence.json",
        "offline_pipeline_report_path": output_dir / "offline_pipeline_report.json",
        "transport_frames_path": output_dir / "betaflight_transport_frames.json",
        "transport_report_path": output_dir / "betaflight_transport_dry_run_report.json",
        "watchdog_report_path": output_dir / "runtime_watchdog_report.json",
        "launcher_event_report_path": output_dir / "launcher_event_report.json",
        "launch_report_path": output_dir / "launch_state_machine_report.json",
        "timeline_path": output_dir / "mission_timeline.json",
        "timeline_report_path": output_dir / "mission_timeline_report.json",
        "mission_report_path": output_dir / "mission_dry_run_report.json",
    }

    offline_report = dict(artifacts["offline_pipeline_report"])
    offline_report["command_sequence_path"] = str(paths["command_sequence_path"])
    offline_report["report_path"] = str(paths["offline_pipeline_report_path"])
    transport_report = dict(artifacts["transport_report"])
    transport_report["frames_path"] = str(paths["transport_frames_path"])
    transport_report["report_path"] = str(paths["transport_report_path"])
    watchdog_report = dict(artifacts["watchdog_report"])
    watchdog_report["report_path"] = str(paths["watchdog_report_path"])
    launcher_event_report = artifacts.get("launcher_event_report")
    if launcher_event_report is not None:
        launcher_event_report = dict(launcher_event_report)
        launcher_event_report["report_path"] = str(paths["launcher_event_report_path"])
    launch_report = dict(artifacts["launch_report"])
    launch_report["report_path"] = str(paths["launch_report_path"])
    timeline_report = dict(artifacts["timeline_report"])
    timeline_report["timeline_path"] = str(paths["timeline_path"])
    timeline_report["report_path"] = str(paths["timeline_report_path"])

    _write_json(paths["command_sequence_path"], artifacts["command_sequence"])
    _write_json(paths["offline_pipeline_report_path"], offline_report)
    _write_json(paths["transport_frames_path"], artifacts["transport_frames"])
    _write_json(paths["transport_report_path"], transport_report)
    _write_json(paths["watchdog_report_path"], watchdog_report)
    if launcher_event_report is not None:
        _write_json(paths["launcher_event_report_path"], launcher_event_report)
    _write_json(paths["launch_report_path"], launch_report)
    _write_json(paths["timeline_path"], artifacts["timeline"])
    _write_json(paths["timeline_report_path"], timeline_report)

    persisted_report = dict(report)
    artifact_paths = {key: str(value) for key, value in paths.items()}
    if launcher_event_report is None:
        artifact_paths["launcher_event_report_path"] = ""
    persisted_report["artifact_paths"] = artifact_paths
    persisted_report["subreports"] = _subreport_refs(
        offline_report,
        transport_report,
        watchdog_report,
        launcher_event_report,
        launch_report,
        timeline_report,
    )
    _write_json(paths["mission_report_path"], persisted_report)
    return persisted_report


def _mission_report(
    artifacts: dict[str, Any],
    *,
    source_path: str,
    source_schema: str,
    launch_mode: MissionLaunchMode,
    command_timeout_ms: int,
    throttle_ramp_ms: int,
    launcher_event_report: dict[str, Any] | None,
    timeline_report: dict[str, Any],
) -> dict[str, Any]:
    offline_report = artifacts["offline_pipeline_report"]
    transport_report = artifacts["transport_report"]
    watchdog_report = artifacts["watchdog_report"]
    launch_report = artifacts["launch_report"]
    statuses = [
        str(offline_report["status"]),
        str(transport_report["status"]),
        str(watchdog_report["status"]),
        str(launch_report["status"]),
        str(timeline_report["status"]),
    ]
    status = "PASS" if all(item == "PASS" for item in statuses) else "FAIL"
    return {
        "schema": REPORT_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "source_path": source_path,
        "source_schema": source_schema,
        "launch_mode": launch_mode.value,
        "summary": {
            "offline_pipeline_status": offline_report["status"],
            "transport_status": transport_report["status"],
            "watchdog_status": watchdog_report["status"],
            "launch_status": launch_report["status"],
            "frame_count": offline_report["summary"]["frame_count"],
            "command_count": offline_report["summary"]["command_count"],
            "transport_frame_count": transport_report["summary"]["framed_command_count"],
            "watchdog_accepted_count": watchdog_report["summary"]["accepted_command_count"],
            "watchdog_rejected_count": watchdog_report["summary"]["rejected_command_count"],
            "launcher_event_count": _launcher_event_count(launcher_event_report),
            "timeline_row_count": timeline_report["summary"]["row_count"],
            "launch_final_state": launch_report["summary"]["final_state"],
            "mission_complete": bool(launch_report["summary"]["complete_reached"]),
            "ai_active_reached": bool(launch_report["summary"]["ai_active_reached"]),
            "gate_pass_reached": bool(launch_report["summary"]["gate_pass_reached"]),
            "max_resolved_speed_mps": offline_report["summary"]["max_resolved_speed_mps"],
            "command_timeout_ms": command_timeout_ms,
            "throttle_ramp_ms": throttle_ramp_ms,
            "training_launched": False,
            "cameras_opened": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "subreports": _subreport_refs(
            offline_report,
            transport_report,
            watchdog_report,
            launcher_event_report,
            launch_report,
            timeline_report,
        ),
        "artifact_paths": {
            "command_sequence_path": "",
            "offline_pipeline_report_path": "",
            "transport_frames_path": "",
            "transport_report_path": "",
            "watchdog_report_path": "",
            "launcher_event_report_path": "",
            "launch_report_path": "",
            "timeline_path": "",
            "timeline_report_path": "",
            "mission_report_path": "",
        },
        "safety_boundary": {
            "dry_run_only": True,
            "does_not_launch_training": True,
            "does_not_open_live_cameras": True,
            "does_not_open_uart": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
            "commands_are_file_outputs_only": True,
        },
    }


def _subreport_refs(
    offline_report: dict[str, Any],
    transport_report: dict[str, Any],
    watchdog_report: dict[str, Any],
    launcher_event_report: dict[str, Any] | None,
    launch_report: dict[str, Any],
    timeline_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "offline_pipeline": _subreport_ref(offline_report),
        "transport": _subreport_ref(transport_report),
        "watchdog": _subreport_ref(watchdog_report),
        "launcher_events": _subreport_ref(launcher_event_report),
        "launch": _subreport_ref(launch_report),
        "timeline": _subreport_ref(timeline_report),
    }


def _subreport_ref(report: dict[str, Any] | None) -> dict[str, str]:
    if report is None:
        return {
            "schema": "",
            "status": "SKIPPED",
            "report_path": "",
        }
    return {
        "schema": str(report["schema"]),
        "status": str(report["status"]),
        "report_path": str(report.get("report_path") or ""),
    }


def _launcher_event_count(report: dict[str, Any] | None) -> int:
    if report is None:
        return 0
    return int(report["summary"]["event_count"])


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
