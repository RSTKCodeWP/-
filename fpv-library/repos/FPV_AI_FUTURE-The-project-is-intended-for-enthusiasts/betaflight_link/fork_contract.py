"""Betaflight FPV-AI fork interface contract artifacts.

The contract is generated from dry-run transport frames. It defines the C-side
frame header, decoded command field expectations, and golden wire frames for a
future Betaflight fork. It never opens UART or publishes commands.
"""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fpv_ai.betaflight_link.transport import (
    FRAMES_SCHEMA,
    MAGIC,
    PROTOCOL,
    VERSION,
    TransportFrameError,
    decode_command_frame,
)

CONTRACT_SCHEMA = "fpv_betaflight_fork_interface_contract.v1"
HEADER_SIZE_BYTES = 7
CRC_SIZE_BYTES = 4
MAX_PAYLOAD_BYTES = 65_535
_HEADER = struct.Struct("<4sBH")
_CRC32 = struct.Struct("<I")


def build_betaflight_fork_interface_contract(
    transport_frames: Mapping[str, Any],
    *,
    source_path: Path | str | None = None,
    c_header_path: Path | str | None = None,
    c_header_sha256: str = "",
    c_header_size_bytes: int = 0,
    max_golden_frames: int = 3,
) -> dict[str, Any]:
    if max_golden_frames <= 0:
        raise ValueError("max_golden_frames must be positive")
    source = "" if source_path is None else str(source_path)
    frames = transport_frames.get("frames")
    if not isinstance(frames, list):
        frames = []

    golden_frames: list[dict[str, Any]] = []
    errors: list[str] = []
    previous_sequence_id: int | None = None
    for frame_record in frames[:max_golden_frames]:
        if not isinstance(frame_record, Mapping):
            errors.append("frame record is not an object")
            continue
        try:
            golden = _golden_frame(frame_record)
            if previous_sequence_id is not None and golden["sequence_id"] != previous_sequence_id + 1:
                errors.append(
                    f"sequence gap in golden frames: {previous_sequence_id}->{golden['sequence_id']}"
                )
            previous_sequence_id = int(golden["sequence_id"])
            golden_frames.append(golden)
        except (ValueError, TransportFrameError, KeyError) as exc:
            errors.append(f"frame {frame_record.get('frame_index', '?')}: {exc}")

    checks = _checks(transport_frames, golden_frames, errors)
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "schema": CONTRACT_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "source_path": source,
        "source_schema": str(transport_frames.get("schema") or ""),
        "protocol": PROTOCOL,
        "version": VERSION,
        "summary": {
            "source_frame_count": int(transport_frames.get("frame_count") or len(frames)),
            "golden_frame_count": len(golden_frames),
            "header_size_bytes": HEADER_SIZE_BYTES,
            "crc_size_bytes": CRC_SIZE_BYTES,
            "max_payload_bytes": MAX_PAYLOAD_BYTES,
            "json_payload_transport": True,
            "fixed_motor_output": False,
            "c_header_generated": bool(c_header_path),
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "c_layout": {
            "packing": "packed_little_endian",
            "frame_header_c_type": "fpv_ai_uart_frame_header_v1_t",
            "header_fields": _header_fields(),
            "payload_contract": _payload_contract(),
            "trailer_fields": _trailer_fields(),
        },
        "c_header_artifact": {
            "path": "" if c_header_path is None else str(c_header_path),
            "sha256": c_header_sha256,
            "size_bytes": c_header_size_bytes,
        },
        "golden_frames": golden_frames,
        "checks": checks,
        "errors": errors,
        "safety_boundary": {
            "dry_run_only": True,
            "contract_only": True,
            "does_not_open_uart": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
            "betaflight_fork_must_validate_crc": True,
            "betaflight_fork_must_reject_stale_sequence": True,
        },
    }


def write_betaflight_fork_interface_contract(
    *,
    transport_frames_json: Path,
    output_json: Path,
    c_header_path: Path,
    max_golden_frames: int = 3,
) -> dict[str, Any]:
    transport_frames = _read_json(transport_frames_json)
    c_header_path.parent.mkdir(parents=True, exist_ok=True)
    c_header_path.write_text(generate_c_header_text(), encoding="utf-8")
    contract = build_betaflight_fork_interface_contract(
        transport_frames,
        source_path=transport_frames_json,
        c_header_path=c_header_path,
        c_header_sha256=_sha256(c_header_path),
        c_header_size_bytes=c_header_path.stat().st_size,
        max_golden_frames=max_golden_frames,
    )
    persisted = dict(contract)
    persisted["contract_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def generate_c_header_text() -> str:
    return """#ifndef FPV_AI_UART_CONTRACT_V1_H
#define FPV_AI_UART_CONTRACT_V1_H

#include <stdbool.h>
#include <stdint.h>

#define FPV_AI_UART_PROTOCOL_NAME "FPV_AI_UART_FRAME_V1"
#define FPV_AI_UART_MAGIC_0 ((uint8_t)'F')
#define FPV_AI_UART_MAGIC_1 ((uint8_t)'P')
#define FPV_AI_UART_MAGIC_2 ((uint8_t)'A')
#define FPV_AI_UART_MAGIC_3 ((uint8_t)'I')
#define FPV_AI_UART_VERSION 1u
#define FPV_AI_UART_HEADER_BYTES 7u
#define FPV_AI_UART_CRC_BYTES 4u
#define FPV_AI_UART_MAX_PAYLOAD_BYTES 65535u

#if defined(__GNUC__)
#define FPV_AI_PACKED __attribute__((packed))
#else
#define FPV_AI_PACKED
#endif

typedef struct FPV_AI_PACKED {
    uint8_t magic[4];
    uint8_t version;
    uint16_t payload_len_le;
} fpv_ai_uart_frame_header_v1_t;

typedef enum {
    FPV_AI_SPEED_FIXED = 0,
    FPV_AI_SPEED_ADAPTIVE = 1,
    FPV_AI_SPEED_RACE = 2
} fpv_ai_speed_mode_v1_t;

typedef enum {
    FPV_AI_TARGET_UNKNOWN = 0,
    FPV_AI_TARGET_CANDIDATE = 1,
    FPV_AI_TARGET_LOCKED = 2,
    FPV_AI_TARGET_PREDICTIVE_TRACK = 3,
    FPV_AI_TARGET_REACQUIRE = 4,
    FPV_AI_TARGET_RECOVERED = 5,
    FPV_AI_TARGET_HARD_LOST = 6,
    FPV_AI_TARGET_NO_TARGET = 7
} fpv_ai_target_state_v1_t;

typedef struct {
    float roll_cmd;
    float pitch_cmd;
    float yaw_rate_cmd;
    float throttle_cmd;
    float target_confidence;
    float resolved_speed_mps;
    uint32_t sequence_id;
    uint32_t timestamp_ms;
    bool heartbeat;
    fpv_ai_speed_mode_v1_t speed_mode;
    fpv_ai_target_state_v1_t target_state;
    fpv_ai_target_state_v1_t recovery_state;
} fpv_ai_command_decoded_v1_t;

typedef enum {
    FPV_AI_PARSE_ACCEPT = 0,
    FPV_AI_PARSE_REJECT_NULL = 1,
    FPV_AI_PARSE_REJECT_TOO_SHORT = 2,
    FPV_AI_PARSE_REJECT_MAGIC = 3,
    FPV_AI_PARSE_REJECT_VERSION = 4,
    FPV_AI_PARSE_REJECT_LENGTH = 5,
    FPV_AI_PARSE_REJECT_CRC = 6,
    FPV_AI_PARSE_REJECT_PAYLOAD = 7,
    FPV_AI_PARSE_REJECT_SEQUENCE = 8,
    FPV_AI_PARSE_STALE = 9,
    FPV_AI_PARSE_KILL_REQUIRED = 10,
    FPV_AI_PARSE_NEED_PAYLOAD_DECODER = 11
} fpv_ai_parse_status_v1_t;

typedef struct {
    uint32_t last_sequence_id;
    uint32_t last_timestamp_ms;
    uint32_t command_timeout_ms;
    bool has_last_command;
} fpv_ai_parser_state_v1_t;

typedef bool (*fpv_ai_payload_decode_fn_v1_t)(
    const uint8_t *payload,
    uint16_t payload_len,
    fpv_ai_command_decoded_v1_t *out
);

bool fpv_ai_decode_payload_json_v1(
    const uint8_t *payload,
    uint16_t payload_len,
    fpv_ai_command_decoded_v1_t *out
);

uint32_t fpv_ai_crc32_v1(const uint8_t *data, uint32_t len);

fpv_ai_parse_status_v1_t fpv_ai_parse_frame_v1(
    const uint8_t *frame,
    uint32_t frame_len,
    fpv_ai_payload_decode_fn_v1_t decode_payload,
    fpv_ai_parser_state_v1_t *state,
    fpv_ai_command_decoded_v1_t *out
);

#endif
"""


def _golden_frame(frame_record: Mapping[str, Any]) -> dict[str, Any]:
    wire_hex = frame_record.get("wire_hex")
    if not isinstance(wire_hex, str):
        raise ValueError("missing wire_hex")
    frame = bytes.fromhex(wire_hex)
    if len(frame) < HEADER_SIZE_BYTES + CRC_SIZE_BYTES:
        raise ValueError("frame too short")
    magic, version, payload_len = _HEADER.unpack(frame[:HEADER_SIZE_BYTES])
    if magic != MAGIC:
        raise TransportFrameError("magic mismatch")
    if version != VERSION:
        raise TransportFrameError("version mismatch")
    if len(frame) != HEADER_SIZE_BYTES + payload_len + CRC_SIZE_BYTES:
        raise TransportFrameError("payload length mismatch")
    stored_crc = _CRC32.unpack(frame[-CRC_SIZE_BYTES:])[0]
    expected_crc = zlib.crc32(frame[:-CRC_SIZE_BYTES]) & 0xFFFFFFFF
    if stored_crc != expected_crc:
        raise TransportFrameError("frame crc32 mismatch")
    decoded = decode_command_frame(frame)
    return {
        "frame_index": int(frame_record.get("frame_index") or 0),
        "sequence_id": int(decoded["sequence_id"]),
        "timestamp_ms": int(decoded["timestamp_ms"]),
        "wire_hex": wire_hex,
        "frame_len_bytes": len(frame),
        "header_hex": frame[:HEADER_SIZE_BYTES].hex(),
        "payload_len_bytes": payload_len,
        "payload_crc32": str(decoded["crc32"]),
        "frame_crc32": f"{stored_crc:08x}",
        "decoded_command": {
            "roll_cmd": float(decoded["roll_cmd"]),
            "pitch_cmd": float(decoded["pitch_cmd"]),
            "yaw_rate_cmd": float(decoded["yaw_rate_cmd"]),
            "throttle_cmd": float(decoded["throttle_cmd"]),
            "target_confidence": float(decoded["target_confidence"]),
            "resolved_speed_mps": float(decoded["resolved_speed_mps"]),
            "target_state": str(decoded["target_state"]),
            "recovery_state": str(decoded["recovery_state"]),
            "speed_mode": str(decoded["speed_mode"]),
            "heartbeat": bool(decoded["heartbeat"]),
        },
    }


def _checks(
    transport_frames: Mapping[str, Any],
    golden_frames: list[dict[str, Any]],
    errors: list[str],
) -> list[dict[str, str]]:
    return [
        _check("source_schema_valid", transport_frames.get("schema") == FRAMES_SCHEMA, str(transport_frames.get("schema") or "")),
        _check("protocol_matches", transport_frames.get("protocol") == PROTOCOL, str(transport_frames.get("protocol") or "")),
        _check("golden_frames_present", bool(golden_frames), str(len(golden_frames))),
        _check("golden_frames_decode", not errors, ";".join(errors)),
        _check("header_size_locked", HEADER_SIZE_BYTES == _HEADER.size, str(_HEADER.size)),
        _check("crc_size_locked", CRC_SIZE_BYTES == _CRC32.size, str(_CRC32.size)),
        _check("json_payload_contract_declared", True, "canonical JSON payload inside C frame"),
        _check("no_live_uart_access", True, "contract generation is file-only"),
    ]


def _header_fields() -> list[dict[str, Any]]:
    return [
        {
            "name": "magic",
            "c_type": "uint8_t[4]",
            "offset_bytes": 0,
            "size_bytes": 4,
            "endianness": "raw",
            "expected": "FPAI",
        },
        {
            "name": "version",
            "c_type": "uint8_t",
            "offset_bytes": 4,
            "size_bytes": 1,
            "endianness": "raw",
            "expected": str(VERSION),
        },
        {
            "name": "payload_len_le",
            "c_type": "uint16_t",
            "offset_bytes": 5,
            "size_bytes": 2,
            "endianness": "little",
            "expected": "canonical JSON payload byte length",
        },
    ]


def _payload_contract() -> list[dict[str, str]]:
    return [
        _payload_field("roll_cmd", "float", "normalized [-1.0, 1.0]"),
        _payload_field("pitch_cmd", "float", "normalized [-1.0, 1.0]"),
        _payload_field("yaw_rate_cmd", "float", "normalized [-1.0, 1.0]"),
        _payload_field("throttle_cmd", "float", "normalized [0.0, 1.0]"),
        _payload_field("target_confidence", "float", "normalized [0.0, 1.0]"),
        _payload_field("resolved_speed_mps", "float", "operator-limited speed"),
        _payload_field("sequence_id", "uint32_t", "monotonic command sequence"),
        _payload_field("timestamp_ms", "uint32_t", "monotonic command timestamp"),
        _payload_field("heartbeat", "bool", "must be true for accepted AI command"),
        _payload_field("speed_mode", "enum/string", "FIXED_SPEED, ADAPTIVE_SPEED, RACE_SPEED"),
        _payload_field("target_state", "enum/string", "gate tracking state"),
        _payload_field("recovery_state", "enum/string", "reacquire state"),
        _payload_field("crc32", "hex string", "payload CRC32 over canonical JSON without crc32 field"),
    ]


def _trailer_fields() -> list[dict[str, Any]]:
    return [
        {
            "name": "frame_crc32_le",
            "c_type": "uint32_t",
            "offset_bytes": "7 + payload_len",
            "size_bytes": CRC_SIZE_BYTES,
            "endianness": "little",
            "expected": "CRC32(header + payload)",
        }
    ]


def _payload_field(name: str, c_type: str, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "c_type": c_type,
        "detail": detail,
    }


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
