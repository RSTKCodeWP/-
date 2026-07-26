"""Betaflight fork integration manifest for FPV-AI artifacts.

The manifest turns the generated C/reference artifacts into an actionable fork
integration plan: which files to copy, which hooks to implement, and which
checks must pass before any no-prop bench work. It does not modify or build a
Betaflight checkout.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fpv_ai.betaflight_link.c_reference import C_REFERENCE_SCHEMA
from fpv_ai.betaflight_link.fork_contract import CONTRACT_SCHEMA
from fpv_ai.betaflight_link.parser_sim import PARSER_SIM_SCHEMA
from fpv_ai.betaflight_link.payload_decoder import PAYLOAD_DECODER_SCHEMA

INTEGRATION_MANIFEST_SCHEMA = "fpv_betaflight_fork_integration_manifest.v1"
MODE_MANAGER_C_REFERENCE_SCHEMA = "fpv_betaflight_mode_manager_c_reference_report.v1"


@dataclass(frozen=True)
class IntegrationFileSpec:
    artifact_id: str
    role: str
    target_path: str
    build_role: str
    required_for_firmware_build: bool


INTEGRATION_FILES = (
    IntegrationFileSpec(
        "c_header",
        "shared FPV-AI UART contract header",
        "src/main/fpv_ai/fpv_ai_uart_contract_v1.h",
        "header",
        True,
    ),
    IntegrationFileSpec(
        "c_parser",
        "frame parser, CRC, sequence, heartbeat, and timeout reference",
        "src/main/fpv_ai/fpv_ai_uart_parser_v1.c",
        "firmware_source",
        True,
    ),
    IntegrationFileSpec(
        "c_payload_decoder_adapter",
        "JSON payload decoder adapter with fork-provided tokenizer hooks",
        "src/main/fpv_ai/fpv_ai_payload_decoder_adapter_v1.c",
        "firmware_source",
        True,
    ),
    IntegrationFileSpec(
        "c_mode_manager_header",
        "AI mode/prearm/control gate manager header",
        "src/main/fpv_ai/fpv_ai_mode_manager_v1.h",
        "header",
        True,
    ),
    IntegrationFileSpec(
        "c_mode_manager_source",
        "AI mode/prearm/control gate manager reference",
        "src/main/fpv_ai/fpv_ai_mode_manager_v1.c",
        "firmware_source",
        True,
    ),
    IntegrationFileSpec(
        "golden_fixture",
        "golden UART frame fixture for fork-side unit tests",
        "test/unit/fpv_ai_uart_golden_frames_v1.c",
        "test_fixture",
        False,
    ),
    IntegrationFileSpec(
        "c_mode_manager_fixture",
        "AI mode manager fixture for fork-side unit tests",
        "test/unit/fpv_ai_mode_manager_fixture_v1.c",
        "test_fixture",
        False,
    ),
)


def build_betaflight_fork_integration_manifest(
    *,
    fork_contract: Mapping[str, Any],
    parser_sim_report: Mapping[str, Any],
    c_reference_report: Mapping[str, Any],
    payload_decoder_contract: Mapping[str, Any],
    mode_manager_c_reference_report: Mapping[str, Any],
    fork_contract_path: Path | str | None = None,
    parser_sim_path: Path | str | None = None,
    c_reference_path: Path | str | None = None,
    payload_decoder_path: Path | str | None = None,
    mode_manager_c_reference_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    source_reports = [
        _source_report("fork_contract", fork_contract, fork_contract_path, CONTRACT_SCHEMA),
        _source_report("parser_sim", parser_sim_report, parser_sim_path, PARSER_SIM_SCHEMA),
        _source_report("c_reference", c_reference_report, c_reference_path, C_REFERENCE_SCHEMA),
        _source_report(
            "payload_decoder",
            payload_decoder_contract,
            payload_decoder_path,
            PAYLOAD_DECODER_SCHEMA,
        ),
        _source_report(
            "mode_manager_c_reference",
            mode_manager_c_reference_report,
            mode_manager_c_reference_path,
            MODE_MANAGER_C_REFERENCE_SCHEMA,
        ),
    ]
    integration_files = _integration_files(
        c_reference_report,
        payload_decoder_contract,
        mode_manager_c_reference_report,
    )
    checks = _checks(source_reports, integration_files, parser_sim_report)
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "schema": INTEGRATION_MANIFEST_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "integration_state": "READY_FOR_FORK_REVIEW" if status == "PASS" else "SOURCE_NOT_READY",
        "source_reports": source_reports,
        "summary": {
            "source_report_count": len(source_reports),
            "integration_file_count": len(integration_files),
            "firmware_source_count": sum(1 for row in integration_files if row["build_role"] == "firmware_source"),
            "required_hook_count": len(_required_json_hooks()),
            "pre_merge_check_count": len(_pre_merge_checks()),
            "blocker_count": len(_blockers()),
            "betaflight_repo_modified": False,
            "compile_attempted": False,
            "flash_attempted": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "integration_files": integration_files,
        "compile_plan": {
            "target_module_dir": "src/main/fpv_ai",
            "include_dirs": ["src/main/fpv_ai"],
            "firmware_sources": [
                row["target_path"]
                for row in integration_files
                if row["build_role"] == "firmware_source"
            ],
            "test_sources": [
                row["target_path"]
                for row in integration_files
                if row["build_role"] == "test_fixture"
            ],
            "required_defines": ["FPV_AI_UART_VERSION=1", "FPV_AI_JSON_STRING_MAX=32"],
            "required_json_hooks": _required_json_hooks(),
            "public_api_symbols": _public_api_symbols(),
        },
        "integration_points": _integration_points(),
        "pre_merge_checks": _pre_merge_checks(),
        "blockers_before_fork_merge": _blockers(),
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "manifest_only": True,
            "does_not_modify_betaflight_repo": True,
            "does_not_compile_or_flash_betaflight": True,
            "does_not_open_uart": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
            "owner_defines_first_hardware_test": True,
        },
    }


def write_betaflight_fork_integration_manifest(
    *,
    fork_contract_json: Path,
    parser_sim_json: Path,
    c_reference_json: Path,
    payload_decoder_json: Path,
    mode_manager_c_reference_json: Path,
    output_json: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    manifest = build_betaflight_fork_integration_manifest(
        fork_contract=_read_json(fork_contract_json),
        parser_sim_report=_read_json(parser_sim_json),
        c_reference_report=_read_json(c_reference_json),
        payload_decoder_contract=_read_json(payload_decoder_json),
        mode_manager_c_reference_report=_read_json(mode_manager_c_reference_json),
        fork_contract_path=fork_contract_json,
        parser_sim_path=parser_sim_json,
        c_reference_path=c_reference_json,
        payload_decoder_path=payload_decoder_json,
        mode_manager_c_reference_path=mode_manager_c_reference_json,
        project_root=project_root,
    )
    persisted = dict(manifest)
    persisted["manifest_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _integration_files(
    c_reference_report: Mapping[str, Any],
    payload_decoder_contract: Mapping[str, Any],
    mode_manager_c_reference_report: Mapping[str, Any],
) -> list[dict[str, Any]]:
    artifact_by_id = _artifact_map(c_reference_report)
    artifact_by_id.update(_artifact_map(payload_decoder_contract))
    artifact_by_id.update(_artifact_map(mode_manager_c_reference_report))
    files: list[dict[str, Any]] = []
    for spec in INTEGRATION_FILES:
        artifact = artifact_by_id.get(spec.artifact_id, {})
        files.append({
            "artifact_id": spec.artifact_id,
            "role": spec.role,
            "source_path": str(artifact.get("path") or ""),
            "target_path": spec.target_path,
            "build_role": spec.build_role,
            "required_for_firmware_build": spec.required_for_firmware_build,
            "sha256": str(artifact.get("sha256") or ""),
            "size_bytes": int(artifact.get("size_bytes") or 0),
        })
    return files


def _source_report(
    report_id: str,
    payload: Mapping[str, Any],
    path: Path | str | None,
    expected_schema: str,
) -> dict[str, str]:
    path_obj = Path(path) if path is not None else None
    return {
        "report_id": report_id,
        "path": "" if path is None else str(path),
        "schema": str(payload.get("schema") or ""),
        "expected_schema": expected_schema,
        "status": str(payload.get("status") or ""),
        "sha256": _sha256(path_obj) if path_obj is not None and path_obj.exists() else "",
    }


def _checks(
    source_reports: list[dict[str, str]],
    integration_files: list[dict[str, Any]],
    parser_sim_report: Mapping[str, Any],
) -> list[dict[str, str]]:
    parser_summary = _mapping(parser_sim_report.get("summary"))
    return [
        _check(
            "source_report_schemas_match",
            all(row["schema"] == row["expected_schema"] for row in source_reports),
            _failed_sources(source_reports, key="schema"),
        ),
        _check(
            "source_reports_passed",
            all(row["status"] == "PASS" for row in source_reports),
            _failed_sources(source_reports, key="status"),
        ),
        _check(
            "integration_files_have_sources",
            all(row["source_path"] for row in integration_files),
            _missing_files(integration_files),
        ),
        _check(
            "integration_files_have_hashes",
            all(row["sha256"] for row in integration_files),
            _missing_hashes(integration_files),
        ),
        _check(
            "firmware_sources_declared",
            any(row["build_role"] == "firmware_source" for row in integration_files),
            "firmware source rows",
        ),
        _check("json_hooks_declared", len(_required_json_hooks()) == 4, "float,u32,bool,string"),
        _check(
            "parser_sim_accepts_golden_frames",
            int(parser_summary.get("accepted_count") or 0)
            == int(parser_summary.get("frame_count") or -1),
            str(parser_summary.get("accepted_count") or 0),
        ),
        _check(
            "no_parser_rejections",
            int(parser_summary.get("rejected_count") or 0) == 0,
            str(parser_summary.get("rejected_count") or 0),
        ),
        _check(
            "no_parser_stale_or_kill",
            int(parser_summary.get("stale_count") or 0) == 0
            and int(parser_summary.get("kill_required_count") or 0) == 0,
            "stale/kill counts",
        ),
        _check("no_betaflight_repo_modification", True, "manifest only"),
        _check("no_compile_or_flash", True, "compile/flash outside this manifest"),
        _check("no_live_uart_access", True, "file-only manifest"),
    ]


def _required_json_hooks() -> list[dict[str, str]]:
    return [
        _hook("fpv_ai_json_get_float_v1", "bool(const uint8_t*, uint16_t, const char*, float*)"),
        _hook("fpv_ai_json_get_u32_v1", "bool(const uint8_t*, uint16_t, const char*, uint32_t*)"),
        _hook("fpv_ai_json_get_bool_v1", "bool(const uint8_t*, uint16_t, const char*, bool*)"),
        _hook("fpv_ai_json_get_string_v1", "bool(const uint8_t*, uint16_t, const char*, char*, uint16_t)"),
    ]


def _public_api_symbols() -> list[dict[str, str]]:
    return [
        _symbol("fpv_ai_parse_frame_v1", "frame validation and command acceptance"),
        _symbol("fpv_ai_decode_payload_json_v1", "payload JSON to decoded command mapping"),
        _symbol("fpv_ai_crc32_v1", "wire-frame CRC32"),
        _symbol("fpv_ai_parser_state_v1_t", "sequence and timeout parser state"),
        _symbol("fpv_ai_command_decoded_v1_t", "decoded virtual-pilot command"),
        _symbol("fpv_ai_mode_manager_update_v1", "AI mode/prearm/control gate decision"),
        _symbol("fpv_ai_mode_output_neutral_v1", "neutral hold output helper"),
    ]


def _integration_points() -> list[dict[str, str]]:
    return [
        _integration_point(
            "uart_frame_buffer",
            "AI UART RX buffers a complete FPAI frame before calling fpv_ai_parse_frame_v1.",
        ),
        _integration_point(
            "virtual_receiver_input",
            "On FPV_AI_PARSE_ACCEPT, map roll/pitch/yaw_rate/throttle into the AI virtual receiver path.",
        ),
        _integration_point(
            "ai_mode_guard",
            "AI commands are gated through fpv_ai_mode_manager_update_v1 before virtual receiver output.",
        ),
        _integration_point(
            "ai_mode_arm_manager",
            "AI_ARM_REQUEST is separated from control output and must keep throttle-low discipline.",
        ),
        _integration_point(
            "timeout_reject_path",
            "On STALE, REJECT, or KILL_REQUIRED, do not reuse the last AI command.",
        ),
        _integration_point(
            "low_level_stack_preserved",
            "The fork must preserve gyro, filters, PID, mixer, ESC output, and Betaflight motor timing.",
        ),
    ]


def _pre_merge_checks() -> list[dict[str, str]]:
    return [
        _pre_merge_check("golden_frames_accept", "All generated golden frames parse as ACCEPT in fork tests."),
        _pre_merge_check("crc_corruption_rejects", "A one-byte CRC corruption returns FPV_AI_PARSE_REJECT_CRC."),
        _pre_merge_check("heartbeat_false_kill", "heartbeat=false returns FPV_AI_PARSE_KILL_REQUIRED."),
        _pre_merge_check("sequence_gap_rejects", "Repeated, skipped, or backwards sequence is rejected."),
        _pre_merge_check("timeout_stale", "Command interval over timeout returns FPV_AI_PARSE_STALE."),
        _pre_merge_check("no_direct_motor_output", "AI parser output never writes motors directly."),
        _pre_merge_check("json_hook_tests", "Fork tokenizer hooks fill all 12 required command fields."),
        _pre_merge_check("mode_manager_fixture", "Generated mode manager fixture matches expected fork mode actions."),
        _pre_merge_check("mode_manager_no_motor_write", "Mode manager output routes to virtual receiver and never motors."),
    ]


def _blockers() -> list[dict[str, str]]:
    return [
        _blocker("betaflight_fork_repo_not_selected", "Exact Betaflight fork repository and branch are not selected."),
        _blocker("json_tokenizer_not_implemented", "Fork-side JSON getter hooks are declared but not implemented here."),
        _blocker("mode_manager_not_integrated", "AI mode manager C reference has not been integrated into a real FC target."),
        _blocker("fc_uart_driver_not_integrated", "AI UART RX buffering is not integrated into a real FC target."),
        _blocker("betaflight_build_not_run", "Generated C files have not been compiled inside Betaflight."),
        _blocker("no_prop_bench_not_authorized", "No no-prop bench is authorized by this manifest."),
    ]


def _artifact_map(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    artifacts = report.get("artifacts")
    mapped: dict[str, Mapping[str, Any]] = {}
    if not isinstance(artifacts, list):
        return mapped
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            continue
        artifact_id = artifact.get("artifact_id")
        if isinstance(artifact_id, str):
            mapped[artifact_id] = artifact
    return mapped


def _hook(name: str, signature: str) -> dict[str, str]:
    return {
        "name": name,
        "signature": signature,
        "status": "REQUIRED_NOT_IMPLEMENTED_IN_MANIFEST",
    }


def _symbol(name: str, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "detail": detail,
    }


def _integration_point(point_id: str, detail: str) -> dict[str, str]:
    return {
        "point_id": point_id,
        "detail": detail,
    }


def _pre_merge_check(check_id: str, detail: str) -> dict[str, str]:
    return {
        "check_id": check_id,
        "status": "REQUIRED_NOT_RUN_IN_MANIFEST",
        "detail": detail,
    }


def _blocker(blocker_id: str, detail: str) -> dict[str, str]:
    return {
        "blocker_id": blocker_id,
        "status": "BLOCKING",
        "detail": detail,
    }


def _failed_sources(source_reports: list[dict[str, str]], *, key: str) -> str:
    if key == "schema":
        return ",".join(row["report_id"] for row in source_reports if row["schema"] != row["expected_schema"])
    return ",".join(row["report_id"] for row in source_reports if row[key] != "PASS")


def _missing_files(integration_files: list[dict[str, Any]]) -> str:
    return ",".join(row["artifact_id"] for row in integration_files if not row["source_path"])


def _missing_hashes(integration_files: list[dict[str, Any]]) -> str:
    return ",".join(row["artifact_id"] for row in integration_files if not row["sha256"])


def _mapping(value: object) -> Mapping[str, Any]:
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
