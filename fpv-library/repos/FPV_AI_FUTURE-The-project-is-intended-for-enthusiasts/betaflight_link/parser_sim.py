"""Betaflight-side parser simulator for FPV-AI UART frames.

The simulator mirrors the checks a future Betaflight FPV-AI fork must perform:
frame decode, CRC validation, heartbeat, monotonic sequence, and command
timeout. It reads/writes files only and never opens UART or publishes commands.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from fpv_ai.betaflight_link.fork_contract import CONTRACT_SCHEMA
from fpv_ai.betaflight_link.transport import FRAMES_SCHEMA, PROTOCOL, TransportFrameError, decode_command_frame

PARSER_SIM_SCHEMA = "fpv_betaflight_parser_sim_report.v1"
DECISION_ACCEPT = "ACCEPT"
DECISION_REJECT = "REJECT"
DECISION_STALE = "STALE"
DECISION_KILL_REQUIRED = "KILL_REQUIRED"


@dataclass(frozen=True)
class ParserSimConfig:
    command_timeout_ms: int = 250

    def __post_init__(self) -> None:
        if self.command_timeout_ms <= 0:
            raise ValueError("command_timeout_ms must be positive")


def build_betaflight_parser_sim_report(
    frame_source: Mapping[str, Any],
    *,
    source_path: Path | str | None = None,
    config: ParserSimConfig | None = None,
) -> dict[str, Any]:
    active_config = config or ParserSimConfig()
    source = "" if source_path is None else str(source_path)
    frame_records = _extract_frame_records(frame_source)
    decisions = _simulate_frames(frame_records, command_timeout_ms=active_config.command_timeout_ms)
    summary = _summary(decisions, command_timeout_ms=active_config.command_timeout_ms)
    checks = _checks(frame_source, frame_records, summary)
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "schema": PARSER_SIM_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "source_path": source,
        "source_schema": str(frame_source.get("schema") or ""),
        "protocol": str(frame_source.get("protocol") or PROTOCOL),
        "summary": summary,
        "checks": checks,
        "parser_decisions": decisions,
        "safety_boundary": {
            "dry_run_only": True,
            "simulator_only": True,
            "does_not_open_uart": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
            "manual_kill_required_for_real_props": True,
        },
    }


def write_betaflight_parser_sim_report(
    *,
    frame_source_json: Path,
    output_json: Path,
    command_timeout_ms: int = 250,
) -> dict[str, Any]:
    frame_source = _read_json(frame_source_json)
    report = build_betaflight_parser_sim_report(
        frame_source,
        source_path=frame_source_json,
        config=ParserSimConfig(command_timeout_ms=command_timeout_ms),
    )
    persisted = dict(report)
    persisted["report_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _extract_frame_records(frame_source: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    source_schema = frame_source.get("schema")
    if source_schema == CONTRACT_SCHEMA:
        frames = frame_source.get("golden_frames")
    elif source_schema == FRAMES_SCHEMA:
        frames = frame_source.get("frames")
    else:
        frames = []
    return [frame for frame in frames if isinstance(frame, Mapping)] if isinstance(frames, list) else []


def _simulate_frames(
    frame_records: list[Mapping[str, Any]],
    *,
    command_timeout_ms: int,
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    previous_sequence_id: int | None = None
    previous_timestamp_ms: int | None = None

    for parser_index, frame_record in enumerate(frame_records):
        wire_hex = frame_record.get("wire_hex")
        frame_index = int(frame_record.get("frame_index") or parser_index)
        if not isinstance(wire_hex, str):
            decisions.append(_decision(parser_index, frame_index, DECISION_REJECT, "missing_wire_hex"))
            continue
        try:
            payload = decode_command_frame(bytes.fromhex(wire_hex))
        except (ValueError, TransportFrameError) as exc:
            decisions.append(_decision(parser_index, frame_index, DECISION_REJECT, str(exc)))
            continue

        sequence_id = int(payload["sequence_id"])
        timestamp_ms = int(payload["timestamp_ms"])
        reason = ""
        decision = DECISION_ACCEPT
        interval_ms = 0

        if not bool(payload["heartbeat"]):
            decision = DECISION_KILL_REQUIRED
            reason = "heartbeat_false"
        elif previous_sequence_id is not None and sequence_id <= previous_sequence_id:
            decision = DECISION_REJECT
            reason = "stale_or_repeated_sequence"
        elif previous_sequence_id is not None and sequence_id != previous_sequence_id + 1:
            decision = DECISION_REJECT
            reason = "sequence_gap"
        elif previous_timestamp_ms is not None:
            interval_ms = timestamp_ms - previous_timestamp_ms
            if interval_ms < 0:
                decision = DECISION_REJECT
                reason = "timestamp_backwards"
            elif interval_ms > command_timeout_ms:
                decision = DECISION_STALE
                reason = "command_timeout"

        if decision == DECISION_ACCEPT:
            previous_sequence_id = sequence_id
            previous_timestamp_ms = timestamp_ms

        decisions.append(
            _decision(
                parser_index,
                frame_index,
                decision,
                reason,
                sequence_id=sequence_id,
                timestamp_ms=timestamp_ms,
                interval_ms=interval_ms,
                heartbeat=bool(payload["heartbeat"]),
                target_state=str(payload["target_state"]),
                speed_mode=str(payload["speed_mode"]),
            )
        )

    return decisions


def _summary(decisions: Sequence[Mapping[str, Any]], *, command_timeout_ms: int) -> dict[str, Any]:
    counts = {decision: 0 for decision in _decision_values()}
    max_interval_ms = 0
    heartbeat_lost_count = 0
    sequence_gap_count = 0
    timeout_count = 0
    crc_error_count = 0
    for row in decisions:
        decision = str(row.get("decision") or DECISION_REJECT)
        counts[decision] = counts.get(decision, 0) + 1
        max_interval_ms = max(max_interval_ms, int(row.get("interval_ms") or 0))
        reason = str(row.get("reason") or "")
        if reason == "heartbeat_false":
            heartbeat_lost_count += 1
        if reason in {"sequence_gap", "stale_or_repeated_sequence"}:
            sequence_gap_count += 1
        if reason == "command_timeout":
            timeout_count += 1
        if "crc32 mismatch" in reason:
            crc_error_count += 1
    return {
        "frame_count": len(decisions),
        "accepted_count": counts[DECISION_ACCEPT],
        "rejected_count": counts[DECISION_REJECT],
        "stale_count": counts[DECISION_STALE],
        "kill_required_count": counts[DECISION_KILL_REQUIRED],
        "heartbeat_lost_count": heartbeat_lost_count,
        "sequence_gap_count": sequence_gap_count,
        "timeout_count": timeout_count,
        "crc_error_count": crc_error_count,
        "max_interval_ms": max_interval_ms,
        "command_timeout_ms": command_timeout_ms,
        "uart_opened": False,
        "hardware_test_authorized": False,
        "flight_commands_published": False,
    }


def _checks(
    frame_source: Mapping[str, Any],
    frame_records: list[Mapping[str, Any]],
    summary: Mapping[str, Any],
) -> list[dict[str, str]]:
    return [
        _check(
            "source_schema_supported",
            frame_source.get("schema") in {CONTRACT_SCHEMA, FRAMES_SCHEMA},
            str(frame_source.get("schema") or ""),
        ),
        _check("protocol_matches", str(frame_source.get("protocol") or PROTOCOL) == PROTOCOL, str(frame_source.get("protocol") or "")),
        _check("frames_present", bool(frame_records), str(len(frame_records))),
        _check("all_frames_accepted", int(summary["accepted_count"]) == int(summary["frame_count"]), str(summary["accepted_count"])),
        _check("no_rejections", int(summary["rejected_count"]) == 0, str(summary["rejected_count"])),
        _check("no_stale_commands", int(summary["stale_count"]) == 0, str(summary["stale_count"])),
        _check("no_kill_required", int(summary["kill_required_count"]) == 0, str(summary["kill_required_count"])),
        _check("no_heartbeat_loss", int(summary["heartbeat_lost_count"]) == 0, str(summary["heartbeat_lost_count"])),
        _check("no_sequence_gaps", int(summary["sequence_gap_count"]) == 0, str(summary["sequence_gap_count"])),
        _check("no_crc_errors", int(summary["crc_error_count"]) == 0, str(summary["crc_error_count"])),
        _check("no_live_uart_access", True, "simulator only"),
    ]


def _decision(
    parser_index: int,
    frame_index: int,
    decision: str,
    reason: str,
    *,
    sequence_id: int = 0,
    timestamp_ms: int = 0,
    interval_ms: int = 0,
    heartbeat: bool = False,
    target_state: str = "",
    speed_mode: str = "",
) -> dict[str, Any]:
    return {
        "parser_index": parser_index,
        "frame_index": frame_index,
        "sequence_id": sequence_id,
        "timestamp_ms": timestamp_ms,
        "interval_ms": interval_ms,
        "heartbeat": heartbeat,
        "target_state": target_state,
        "speed_mode": speed_mode,
        "decision": decision,
        "reason": reason,
    }


def _decision_values() -> tuple[str, str, str, str]:
    return (DECISION_ACCEPT, DECISION_REJECT, DECISION_STALE, DECISION_KILL_REQUIRED)


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    }


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
