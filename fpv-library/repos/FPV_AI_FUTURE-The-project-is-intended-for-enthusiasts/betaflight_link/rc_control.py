"""Betaflight virtual receiver channel mapping for FPV AI Gate-Lock.

This module turns the mission timeline into dry-run RC channel intents for a
future Betaflight FPV-AI integration. It models roll/pitch/yaw/throttle plus
AUX1 arming, but never opens UART or publishes commands to hardware.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from fpv_ai.runtime.timeline import load_json

RC_SEQUENCE_SCHEMA = "fpv_betaflight_rc_control_sequence.v1"
RC_REPORT_SCHEMA = "fpv_betaflight_rc_control_report.v1"

AUX1_ARM_STATES = {
    "AI_ARM_REQUEST",
    "ARMED_IDLE",
    "HAND_RELEASE_DETECTED",
    "STABILIZE",
    "THROTTLE_RAMP",
    "AI_ACTIVE",
    "GATE_APPROACH",
    "GATE_PASS",
    "COMPLETE",
}
AI_STICK_STATES = {"THROTTLE_RAMP", "AI_ACTIVE", "GATE_APPROACH", "GATE_PASS"}


@dataclass(frozen=True)
class BetaflightRcControlConfig:
    channel_min_us: int = 1000
    channel_mid_us: int = 1500
    channel_max_us: int = 2000
    throttle_min_us: int = 1000
    throttle_max_us: int = 2000
    aux1_disarm_us: int = 1000
    aux1_arm_us: int = 2000
    aux1_channel_name: str = "AUX1"
    target_memory_hold_ms: int = 1500

    def __post_init__(self) -> None:
        if not self.channel_min_us < self.channel_mid_us < self.channel_max_us:
            raise ValueError("channel min/mid/max must be ordered")
        if self.throttle_min_us >= self.throttle_max_us:
            raise ValueError("throttle_min_us must be below throttle_max_us")
        if self.aux1_disarm_us >= self.aux1_arm_us:
            raise ValueError("aux1_disarm_us must be below aux1_arm_us")
        if not self.aux1_channel_name:
            raise ValueError("aux1_channel_name must be non-empty")
        if self.target_memory_hold_ms <= 0:
            raise ValueError("target_memory_hold_ms must be positive")

    def to_payload(self) -> dict[str, Any]:
        return {
            "channel_min_us": self.channel_min_us,
            "channel_mid_us": self.channel_mid_us,
            "channel_max_us": self.channel_max_us,
            "throttle_min_us": self.throttle_min_us,
            "throttle_max_us": self.throttle_max_us,
            "aux1_disarm_us": self.aux1_disarm_us,
            "aux1_arm_us": self.aux1_arm_us,
            "aux1_channel_name": self.aux1_channel_name,
            "target_memory_hold_ms": self.target_memory_hold_ms,
        }


def build_betaflight_rc_control_outputs(
    timeline: Mapping[str, Any],
    *,
    config: BetaflightRcControlConfig | None = None,
    source_path: Path | str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    active_config = config or BetaflightRcControlConfig()
    rows = _timeline_rows(timeline)
    frames: list[dict[str, Any]] = []
    latest_command: dict[str, Any] | None = None
    for frame_number, row in enumerate(rows):
        command = _command_template(row)
        if command is not None:
            latest_command = command
        frames.append(
            _rc_frame(
                row,
                frame_number=frame_number,
                command=latest_command,
                config=active_config,
            )
        )
    checks = _checks(timeline, frames, active_config)
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    source = "" if source_path is None else str(source_path)
    sequence = {
        "schema": RC_SEQUENCE_SCHEMA,
        "generated_at": _utc_now(),
        "source_path": source,
        "source_schema": str(timeline.get("schema") or ""),
        "control_mode": "BETAFLIGHT_VIRTUAL_RECEIVER_AUX1_ARM",
        "config": active_config.to_payload(),
        "frame_count": len(frames),
        "frames": frames,
        "safety_boundary": _safety_boundary(),
    }
    report = {
        "schema": RC_REPORT_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "source_path": source,
        "source_schema": str(timeline.get("schema") or ""),
        "summary": _summary(frames, active_config),
        "checks": checks,
        "safety_boundary": _safety_boundary(),
    }
    return sequence, report


def write_betaflight_rc_control_outputs(
    *,
    timeline_json: Path,
    sequence_json: Path,
    report_json: Path,
    config: BetaflightRcControlConfig | None = None,
) -> dict[str, Any]:
    timeline = load_json(timeline_json)
    sequence, report = build_betaflight_rc_control_outputs(
        timeline,
        config=config,
        source_path=timeline_json,
    )
    sequence_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    sequence_json.write_text(json.dumps(sequence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    persisted_report = dict(report)
    persisted_report["sequence_path"] = str(sequence_json)
    persisted_report["report_path"] = str(report_json)
    report_json.write_text(json.dumps(persisted_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted_report


def _timeline_rows(timeline: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = timeline.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("mission timeline must contain a non-empty rows list")
    if not all(isinstance(row, Mapping) for row in rows):
        raise ValueError("mission timeline rows must be objects")
    return sorted(rows, key=lambda row: int(row["timestamp_ms"]))


def _rc_frame(
    row: Mapping[str, Any],
    *,
    frame_number: int,
    command: Mapping[str, Any] | None,
    config: BetaflightRcControlConfig,
) -> dict[str, Any]:
    launch_state = str(row.get("launch_state") or "")
    manual_kill = row.get("manual_kill") is True
    arm_request = row.get("arm_request") is True
    fc_armed = row.get("fc_armed") is True
    throttle_low = row.get("throttle_low") is True
    timestamp_ms = int(row["timestamp_ms"])
    source_command_age_ms = (
        timestamp_ms - int(command["timestamp_ms"])
        if command is not None
        else None
    )
    command_memory_valid = (
        command is not None
        and source_command_age_ms is not None
        and 0 <= source_command_age_ms <= config.target_memory_hold_ms
    )
    watchdog_allowed = (
        command_memory_valid
        and command is not None
        and command.get("watchdog_ai_control_allowed") is True
    )
    launch_allowed = row.get("launch_ai_control_allowed") is True
    ai_control_allowed = (
        not manual_kill
        and watchdog_allowed
        and launch_allowed
        and launch_state in AI_STICK_STATES
    )
    aux1_arm = not manual_kill and (arm_request or fc_armed or launch_state in AUX1_ARM_STATES)

    command_source = command or {}
    roll_cmd = _optional_float(command_source, "roll_cmd", default=0.0)
    pitch_cmd = _optional_float(command_source, "pitch_cmd", default=0.0)
    yaw_rate_cmd = _optional_float(command_source, "yaw_rate_cmd", default=0.0)
    throttle_cmd = _optional_float(command_source, "throttle_cmd", default=0.0)
    throttle_ramp_progress = _optional_float(row, "throttle_ramp_progress", default=0.0)

    if not ai_control_allowed:
        roll_out = pitch_out = yaw_out = throttle_out = 0.0
    else:
        roll_out = roll_cmd
        pitch_out = pitch_cmd
        yaw_out = yaw_rate_cmd
        throttle_out = throttle_cmd
        if launch_state == "THROTTLE_RAMP":
            throttle_out *= _clamp(throttle_ramp_progress, 0.0, 1.0)

    channels = {
        "roll_us": _stick_us(roll_out, config),
        "pitch_us": _stick_us(pitch_out, config),
        "yaw_us": _stick_us(yaw_out, config),
        "throttle_us": _throttle_us(throttle_out, config),
        "aux1_us": config.aux1_arm_us if aux1_arm else config.aux1_disarm_us,
    }
    arm_throttle_low_ok = (
        not arm_request
        or (
            throttle_low
            and channels["throttle_us"] == config.throttle_min_us
        )
    )
    return {
        "schema": "fpv_betaflight_rc_control_frame.v1",
        "frame_number": frame_number,
        "frame_index": int(row["frame_index"]),
        "timestamp_ms": timestamp_ms,
        "source_command_frame_index": int(command["frame_index"]) if command is not None else None,
        "source_command_age_ms": source_command_age_ms,
        "command_memory_valid": command_memory_valid,
        "launch_state": launch_state,
        "watchdog_ai_control_allowed": watchdog_allowed,
        "launch_ai_control_allowed": launch_allowed,
        "ai_control_allowed": ai_control_allowed,
        "arm_request": arm_request,
        "fc_armed": fc_armed,
        "manual_kill": manual_kill,
        "throttle_low": throttle_low,
        "aux1_arm": aux1_arm,
        "arm_aux_channel": config.aux1_channel_name,
        "arm_throttle_low_ok": arm_throttle_low_ok,
        "output_action": _output_action(
            launch_state=launch_state,
            manual_kill=manual_kill,
            arm_request=arm_request,
            aux1_arm=aux1_arm,
            ai_control_allowed=ai_control_allowed,
        ),
        "normalized_input": {
            "roll_cmd": round(roll_cmd, 6),
            "pitch_cmd": round(pitch_cmd, 6),
            "yaw_rate_cmd": round(yaw_rate_cmd, 6),
            "throttle_cmd": round(throttle_cmd, 6),
            "throttle_ramp_progress": round(throttle_ramp_progress, 3),
        },
        "normalized_output": {
            "roll_cmd": round(roll_out, 6),
            "pitch_cmd": round(pitch_out, 6),
            "yaw_rate_cmd": round(yaw_out, 6),
            "throttle_cmd": round(throttle_out, 6),
        },
        "channels": channels,
    }


def _output_action(
    *,
    launch_state: str,
    manual_kill: bool,
    arm_request: bool,
    aux1_arm: bool,
    ai_control_allowed: bool,
) -> str:
    if manual_kill:
        return "MANUAL_KILL_AUX1_LOW"
    if arm_request:
        return "AUX1_ARM_REQUEST_THROTTLE_LOW"
    if ai_control_allowed and launch_state == "THROTTLE_RAMP":
        return "AI_CONTROL_THROTTLE_RAMP"
    if ai_control_allowed:
        return "AI_CONTROL_ACTIVE"
    if aux1_arm:
        return "AUX1_ARM_HOLD_NEUTRAL_STICKS"
    return "AUX1_LOW_NEUTRAL_STICKS"


def _summary(
    frames: Sequence[Mapping[str, Any]],
    config: BetaflightRcControlConfig,
) -> dict[str, Any]:
    arm_request_frames = [frame for frame in frames if frame["arm_request"] is True]
    aux1_arm_frames = [frame for frame in frames if frame["aux1_arm"] is True]
    manual_kill_frames = [frame for frame in frames if frame["manual_kill"] is True]
    throttle_low_violations = [
        frame
        for frame in arm_request_frames
        if frame["arm_throttle_low_ok"] is not True
    ]
    manual_kill_aux_high = [
        frame
        for frame in manual_kill_frames
        if int(_channels(frame)["aux1_us"]) != config.aux1_disarm_us
    ]
    expired_command_memory = [
        frame
        for frame in frames
        if frame["launch_ai_control_allowed"] is True and frame["command_memory_valid"] is False
    ]
    return {
        "timeline_row_count": len(frames),
        "rc_frame_count": len(frames),
        "arm_aux_channel": config.aux1_channel_name,
        "arm_request_frame_count": len(arm_request_frames),
        "aux1_arm_frame_count": len(aux1_arm_frames),
        "fc_armed_frame_count": sum(1 for frame in frames if frame["fc_armed"] is True),
        "ai_control_frame_count": sum(1 for frame in frames if frame["ai_control_allowed"] is True),
        "throttle_ramp_frame_count": sum(1 for frame in frames if frame["launch_state"] == "THROTTLE_RAMP"),
        "manual_kill_frame_count": len(manual_kill_frames),
        "throttle_low_arm_violation_count": len(throttle_low_violations),
        "manual_kill_aux_high_count": len(manual_kill_aux_high),
        "expired_command_memory_count": len(expired_command_memory),
        "aux1_disarm_us": config.aux1_disarm_us,
        "aux1_arm_us": config.aux1_arm_us,
        "min_throttle_us": min(int(_channels(frame)["throttle_us"]) for frame in frames),
        "max_throttle_us": max(int(_channels(frame)["throttle_us"]) for frame in frames),
        "training_launched": False,
        "cameras_opened": False,
        "gpio_read": False,
        "uart_opened": False,
        "hardware_test_authorized": False,
        "flight_commands_published": False,
    }


def _checks(
    timeline: Mapping[str, Any],
    frames: Sequence[Mapping[str, Any]],
    config: BetaflightRcControlConfig,
) -> list[dict[str, str]]:
    summary = _summary(frames, config)
    return [
        _check("timeline_schema_valid", timeline.get("schema") == "fpv_ai_mission_timeline.v1", str(timeline.get("schema") or "")),
        _check("rc_frames_present", bool(frames), str(len(frames))),
        _check("aux1_channel_declared", config.aux1_channel_name == "AUX1", config.aux1_channel_name),
        _check("arm_request_seen", int(summary["arm_request_frame_count"]) > 0, str(summary["arm_request_frame_count"])),
        _check("aux1_arm_output_seen", int(summary["aux1_arm_frame_count"]) > 0, str(summary["aux1_arm_frame_count"])),
        _check(
            "arm_request_requires_throttle_low",
            int(summary["throttle_low_arm_violation_count"]) == 0,
            str(summary["throttle_low_arm_violation_count"]),
        ),
        _check(
            "manual_kill_forces_aux1_low",
            int(summary["manual_kill_aux_high_count"]) == 0,
            str(summary["manual_kill_aux_high_count"]),
        ),
        _check("ai_control_frames_present", int(summary["ai_control_frame_count"]) > 0, str(summary["ai_control_frame_count"])),
        _check(
            "active_frames_have_command_memory",
            int(summary["expired_command_memory_count"]) == 0,
            str(summary["expired_command_memory_count"]),
        ),
        _check("no_live_hardware_access", True, "file-output RC control dry-run only"),
    ]


def _command_template(row: Mapping[str, Any]) -> dict[str, Any] | None:
    if row.get("command_seen") is not True:
        return None
    return {
        "frame_index": int(row["frame_index"]),
        "timestamp_ms": int(row["timestamp_ms"]),
        "watchdog_ai_control_allowed": row.get("watchdog_ai_control_allowed") is True,
        "roll_cmd": _optional_float(row, "roll_cmd", default=0.0),
        "pitch_cmd": _optional_float(row, "pitch_cmd", default=0.0),
        "yaw_rate_cmd": _optional_float(row, "yaw_rate_cmd", default=0.0),
        "throttle_cmd": _optional_float(row, "throttle_cmd", default=0.0),
    }


def _channels(frame: Mapping[str, Any]) -> Mapping[str, Any]:
    channels = frame.get("channels")
    return channels if isinstance(channels, Mapping) else {}


def _optional_float(row: Mapping[str, Any], key: str, *, default: float) -> float:
    value = row.get(key)
    return default if value is None else float(value)


def _stick_us(value: float, config: BetaflightRcControlConfig) -> int:
    half_range = (config.channel_max_us - config.channel_min_us) / 2.0
    return int(round(config.channel_mid_us + _clamp(value, -1.0, 1.0) * half_range))


def _throttle_us(value: float, config: BetaflightRcControlConfig) -> int:
    span = config.throttle_max_us - config.throttle_min_us
    return int(round(config.throttle_min_us + _clamp(value, 0.0, 1.0) * span))


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    }


def _safety_boundary() -> dict[str, bool]:
    return {
        "dry_run_only": True,
        "file_output_only": True,
        "does_not_launch_training": True,
        "does_not_open_live_cameras": True,
        "does_not_read_gpio": True,
        "does_not_open_uart": True,
        "does_not_authorize_hardware_test": True,
        "does_not_publish_flight_commands": True,
        "does_not_command_motors_directly": True,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
