"""Dry-run UART framing for the Betaflight FPV-AI command stream.

This module defines the wire frame contract used between the Raspberry Pi AI
pilot and the future Betaflight FPV-AI fork. It only encodes, decodes, and
audits bytes in memory/files; it does not open serial ports or publish flight
commands.
"""

from __future__ import annotations

import json
import struct
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fpv_ai.betaflight_link.commands import validate_ai_command_payload

FRAME_SCHEMA = "fpv_ai_transport_frame.v1"
FRAMES_SCHEMA = "fpv_ai_transport_frames.v1"
REPORT_SCHEMA = "fpv_ai_transport_dry_run_report.v1"
PROTOCOL = "FPV_AI_UART_FRAME_V1"
MAGIC = b"FPAI"
VERSION = 1

_HEADER = struct.Struct("<4sBH")
_CRC32 = struct.Struct("<I")
_MAX_PAYLOAD_BYTES = 65_535


class TransportFrameError(ValueError):
    """Raised when an FPV-AI transport frame is malformed."""


@dataclass(frozen=True)
class LinkTimingConfig:
    command_timeout_ms: int = 500

    def __post_init__(self) -> None:
        if self.command_timeout_ms <= 0:
            raise ValueError("command_timeout_ms must be positive")


def encode_command_frame(command_payload: Mapping[str, Any]) -> bytes:
    validate_ai_command_payload(command_payload)
    payload_bytes = _canonical_json_bytes(command_payload)
    if len(payload_bytes) > _MAX_PAYLOAD_BYTES:
        raise TransportFrameError("AI command payload is too large for UART frame v1")
    header = _HEADER.pack(MAGIC, VERSION, len(payload_bytes))
    frame_without_crc = header + payload_bytes
    frame_crc = zlib.crc32(frame_without_crc) & 0xFFFFFFFF
    return frame_without_crc + _CRC32.pack(frame_crc)


def decode_command_frame(frame: bytes) -> dict[str, Any]:
    if len(frame) < _HEADER.size + _CRC32.size:
        raise TransportFrameError("frame is shorter than the FPV-AI transport header")
    magic, version, payload_len = _HEADER.unpack(frame[: _HEADER.size])
    if magic != MAGIC:
        raise TransportFrameError("frame magic mismatch")
    if version != VERSION:
        raise TransportFrameError(f"unsupported frame version: {version}")
    expected_len = _HEADER.size + payload_len + _CRC32.size
    if len(frame) != expected_len:
        raise TransportFrameError("frame length does not match payload_len")

    payload_bytes = frame[_HEADER.size : _HEADER.size + payload_len]
    stored_crc = _CRC32.unpack(frame[-_CRC32.size :])[0]
    expected_crc = zlib.crc32(frame[: -_CRC32.size]) & 0xFFFFFFFF
    if stored_crc != expected_crc:
        raise TransportFrameError("frame crc32 mismatch")

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TransportFrameError("frame payload is not valid canonical JSON") from exc
    if not isinstance(payload, dict):
        raise TransportFrameError("frame payload must be a JSON object")
    validate_ai_command_payload(payload)
    return payload


def transport_record_for_command(command_payload: Mapping[str, Any], *, frame_index: int) -> dict[str, Any]:
    if frame_index < 0:
        raise ValueError("frame_index must be non-negative")
    frame = encode_command_frame(command_payload)
    decoded = decode_command_frame(frame)
    frame_crc = _CRC32.unpack(frame[-_CRC32.size :])[0]
    return {
        "schema": FRAME_SCHEMA,
        "protocol": PROTOCOL,
        "magic": MAGIC.decode("ascii"),
        "version": VERSION,
        "frame_index": frame_index,
        "sequence_id": int(decoded["sequence_id"]),
        "timestamp_ms": int(decoded["timestamp_ms"]),
        "payload_len_bytes": len(_canonical_json_bytes(decoded)),
        "payload_crc32": str(decoded["crc32"]),
        "frame_crc32": f"{frame_crc:08x}",
        "wire_hex": frame.hex(),
        "decoded_ok": True,
    }


def run_transport_dry_run(
    command_sequence: Mapping[str, Any],
    *,
    source_path: Path | str | None = None,
    timing: LinkTimingConfig | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    active_timing = timing or LinkTimingConfig()
    commands = command_sequence.get("commands")
    if not isinstance(commands, list) or not commands:
        raise ValueError("command_sequence must contain a non-empty commands list")

    frame_records: list[dict[str, Any]] = []
    errors: list[str] = []
    stale_commands: list[dict[str, int]] = []
    sequence_gaps: list[dict[str, int]] = []
    decoded_count = 0
    max_interval_ms = 0
    previous_timestamp_ms: int | None = None
    previous_sequence_id: int | None = None

    for frame_index, row in enumerate(commands):
        if not isinstance(row, dict) or not isinstance(row.get("command"), dict):
            errors.append(f"frame {frame_index}: missing command payload")
            continue
        command_payload = row["command"]
        try:
            record = transport_record_for_command(command_payload, frame_index=frame_index)
            decoded_count += 1
            frame_records.append(record)
        except (TransportFrameError, ValueError) as exc:
            errors.append(f"frame {frame_index}: {exc}")
            continue

        sequence_id = int(record["sequence_id"])
        timestamp_ms = int(record["timestamp_ms"])
        if previous_sequence_id is not None and sequence_id != previous_sequence_id + 1:
            sequence_gaps.append(
                {
                    "frame_index": frame_index,
                    "previous_sequence_id": previous_sequence_id,
                    "sequence_id": sequence_id,
                }
            )
        if previous_timestamp_ms is not None:
            interval_ms = timestamp_ms - previous_timestamp_ms
            max_interval_ms = max(max_interval_ms, interval_ms)
            if interval_ms < 0:
                errors.append(f"frame {frame_index}: timestamp moved backwards")
            elif interval_ms > active_timing.command_timeout_ms:
                stale_commands.append(
                    {
                        "frame_index": frame_index,
                        "previous_timestamp_ms": previous_timestamp_ms,
                        "timestamp_ms": timestamp_ms,
                        "interval_ms": interval_ms,
                    }
                )
        previous_sequence_id = sequence_id
        previous_timestamp_ms = timestamp_ms

    status = "PASS" if not errors and not stale_commands and not sequence_gaps else "FAIL"
    source = "" if source_path is None else str(source_path)
    frames_payload = {
        "schema": FRAMES_SCHEMA,
        "source_path": source,
        "protocol": PROTOCOL,
        "frame_count": len(frame_records),
        "frames": frame_records,
    }
    report = {
        "schema": REPORT_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "source_path": source,
        "source_schema": str(command_sequence.get("schema") or ""),
        "protocol": PROTOCOL,
        "summary": {
            "command_count": len(commands),
            "framed_command_count": len(frame_records),
            "decoded_command_count": decoded_count,
            "stale_command_count": len(stale_commands),
            "sequence_gap_count": len(sequence_gaps),
            "max_command_interval_ms": max_interval_ms,
            "command_timeout_ms": active_timing.command_timeout_ms,
            "manual_kill_required": True,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "stale_commands": stale_commands,
        "sequence_gaps": sequence_gaps,
        "errors": errors,
        "safety_boundary": {
            "dry_run_only": True,
            "does_not_open_uart": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
            "manual_kill_required_for_real_props": True,
        },
    }
    return frames_payload, report


def write_transport_dry_run_outputs(
    command_sequence: Mapping[str, Any],
    *,
    frames_json: Path,
    report_json: Path,
    source_path: Path | str | None = None,
    timing: LinkTimingConfig | None = None,
) -> dict[str, Any]:
    frames_payload, report = run_transport_dry_run(command_sequence, source_path=source_path, timing=timing)
    frames_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    frames_json.write_text(json.dumps(frames_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    persisted_report = dict(report)
    persisted_report["frames_path"] = str(frames_json)
    persisted_report["report_path"] = str(report_json)
    report_json.write_text(json.dumps(persisted_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted_report


def load_command_sequence(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("command sequence JSON must be an object")
    return payload


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
