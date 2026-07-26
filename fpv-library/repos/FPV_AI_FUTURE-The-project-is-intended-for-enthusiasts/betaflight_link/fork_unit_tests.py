"""Fork-side unit test contract for Betaflight FPV-AI C artifacts.

The report defines the unit tests the future Betaflight fork must run for the
UART parser, payload decoder hooks, and AI mode manager. It is a manifest only:
no Betaflight checkout is modified, no C test is compiled, and no hardware or
UART is touched.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from fpv_ai.betaflight_link.c_reference import C_REFERENCE_SCHEMA
from fpv_ai.betaflight_link.integration_manifest import INTEGRATION_MANIFEST_SCHEMA
from fpv_ai.betaflight_link.mode_manager_c_reference import MODE_MANAGER_C_REFERENCE_SCHEMA
from fpv_ai.betaflight_link.parser_sim import PARSER_SIM_SCHEMA
from fpv_ai.betaflight_link.payload_decoder import PAYLOAD_DECODER_SCHEMA

FORK_UNIT_TESTS_SCHEMA = "fpv_betaflight_fork_unit_tests.v1"

PARSER_SOURCE = "src/main/fpv_ai/fpv_ai_uart_parser_v1.c"
PAYLOAD_DECODER_SOURCE = "src/main/fpv_ai/fpv_ai_payload_decoder_adapter_v1.c"
MODE_MANAGER_SOURCE = "src/main/fpv_ai/fpv_ai_mode_manager_v1.c"
UART_FIXTURE = "test/unit/fpv_ai_uart_golden_frames_v1.c"
MODE_MANAGER_FIXTURE = "test/unit/fpv_ai_mode_manager_fixture_v1.c"


@dataclass(frozen=True)
class UnitTestSpec:
    test_id: str
    group_id: str
    target_source: str
    fixture_source: str
    requirement: str
    expected_result: str


UNIT_TEST_SPECS = (
    UnitTestSpec(
        "parser_golden_frames_accept",
        "uart_parser",
        PARSER_SOURCE,
        UART_FIXTURE,
        "All generated golden UART frames parse as FPV_AI_PARSE_ACCEPT.",
        "ACCEPT for every golden frame",
    ),
    UnitTestSpec(
        "parser_crc_corruption_rejects",
        "uart_parser",
        PARSER_SOURCE,
        UART_FIXTURE,
        "A one-byte CRC corruption is rejected.",
        "FPV_AI_PARSE_REJECT_CRC",
    ),
    UnitTestSpec(
        "parser_heartbeat_false_kill_required",
        "uart_parser",
        PARSER_SOURCE,
        UART_FIXTURE,
        "heartbeat=false does not route stale AI control.",
        "FPV_AI_PARSE_KILL_REQUIRED",
    ),
    UnitTestSpec(
        "parser_sequence_gap_rejects",
        "uart_parser",
        PARSER_SOURCE,
        UART_FIXTURE,
        "Repeated, skipped, or backwards sequence ids are rejected.",
        "FPV_AI_PARSE_REJECT_SEQUENCE",
    ),
    UnitTestSpec(
        "parser_timeout_marks_stale",
        "uart_parser",
        PARSER_SOURCE,
        UART_FIXTURE,
        "Command interval over the configured timeout is stale.",
        "FPV_AI_PARSE_STALE",
    ),
    UnitTestSpec(
        "parser_missing_payload_decoder_requires_hook",
        "uart_parser",
        PARSER_SOURCE,
        UART_FIXTURE,
        "Parser refuses to accept payloads when the decoder hook is missing.",
        "FPV_AI_PARSE_NEED_PAYLOAD_DECODER",
    ),
    UnitTestSpec(
        "payload_decoder_all_command_fields_mapped",
        "payload_decoder",
        PAYLOAD_DECODER_SOURCE,
        UART_FIXTURE,
        "Fork JSON hooks fill all required decoded command fields.",
        "12 canonical fields mapped",
    ),
    UnitTestSpec(
        "payload_decoder_race_speed_enum_maps",
        "payload_decoder",
        PAYLOAD_DECODER_SOURCE,
        UART_FIXTURE,
        "RACE_SPEED JSON payload maps to the C speed enum.",
        "FPV_AI_SPEED_RACE",
    ),
    UnitTestSpec(
        "payload_decoder_recovery_target_enum_maps",
        "payload_decoder",
        PAYLOAD_DECODER_SOURCE,
        UART_FIXTURE,
        "Recovery target states map into C target enums.",
        "PREDICTIVE_TRACK/REACQUIRE/RECOVERED accepted",
    ),
    UnitTestSpec(
        "payload_decoder_range_checks_reject_invalid",
        "payload_decoder",
        PAYLOAD_DECODER_SOURCE,
        UART_FIXTURE,
        "Out-of-range roll/pitch/yaw/throttle/confidence values are rejected.",
        "decode_payload returns false",
    ),
    UnitTestSpec(
        "mode_manager_fixture_rows_match_contract",
        "ai_mode_manager",
        MODE_MANAGER_SOURCE,
        MODE_MANAGER_FIXTURE,
        "Generated mode manager fixture rows match the mode contract.",
        "all fixture rows match expected actions",
    ),
    UnitTestSpec(
        "mode_manager_prearm_requires_target_lock",
        "ai_mode_manager",
        MODE_MANAGER_SOURCE,
        MODE_MANAGER_FIXTURE,
        "AI_PREARM cannot advance without target lock or recovered target.",
        "neutral hold before target lock",
    ),
    UnitTestSpec(
        "mode_manager_arm_request_requires_throttle_low",
        "ai_mode_manager",
        MODE_MANAGER_SOURCE,
        MODE_MANAGER_FIXTURE,
        "AI_ARM_REQUEST must keep throttle-low discipline.",
        "no arm request without throttle_low",
    ),
    UnitTestSpec(
        "mode_manager_throttle_ramp_routes_virtual_receiver",
        "ai_mode_manager",
        MODE_MANAGER_SOURCE,
        MODE_MANAGER_FIXTURE,
        "THROTTLE_RAMP routes only ramp-limited virtual receiver output.",
        "FPV_AI_MODE_OUTPUT_RAMP_LIMITED_VIRTUAL_RECEIVER",
    ),
    UnitTestSpec(
        "mode_manager_active_routes_virtual_receiver",
        "ai_mode_manager",
        MODE_MANAGER_SOURCE,
        MODE_MANAGER_FIXTURE,
        "AI_ACTIVE/GATE_APPROACH routes to virtual receiver.",
        "FPV_AI_MODE_OUTPUT_ROUTE_TO_VIRTUAL_RECEIVER",
    ),
    UnitTestSpec(
        "mode_manager_manual_kill_neutral",
        "ai_mode_manager",
        MODE_MANAGER_SOURCE,
        MODE_MANAGER_FIXTURE,
        "Manual kill latches neutral output and blocks AI control.",
        "FPV_AI_MODE_CMD_KILL_LATCHED",
    ),
    UnitTestSpec(
        "integration_all_firmware_sources_declared",
        "fork_integration",
        "src/main/fpv_ai",
        "",
        "Parser, payload decoder, and mode manager sources are in the fork compile plan.",
        "3 FPV-AI firmware sources declared",
    ),
    UnitTestSpec(
        "integration_no_direct_motor_output",
        "fork_integration",
        MODE_MANAGER_SOURCE,
        MODE_MANAGER_FIXTURE,
        "FPV-AI code never writes motors directly.",
        "virtual receiver path only",
    ),
    UnitTestSpec(
        "integration_tests_do_not_open_live_uart",
        "fork_integration",
        "test/unit",
        "",
        "Unit tests remain firmware-local and do not open live UART/hardware.",
        "no live UART or hardware access",
    ),
)


def build_betaflight_fork_unit_test_contract(
    *,
    integration_manifest: Mapping[str, Any],
    parser_sim_report: Mapping[str, Any],
    c_reference_report: Mapping[str, Any],
    payload_decoder_contract: Mapping[str, Any],
    mode_manager_c_reference_report: Mapping[str, Any],
    integration_manifest_path: Path | str | None = None,
    parser_sim_path: Path | str | None = None,
    c_reference_path: Path | str | None = None,
    payload_decoder_path: Path | str | None = None,
    mode_manager_c_reference_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    source_reports = [
        _source_report(
            "integration_manifest",
            integration_manifest,
            integration_manifest_path,
            INTEGRATION_MANIFEST_SCHEMA,
        ),
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
    test_groups = _test_groups()
    unit_tests = [_unit_test_entry(spec) for spec in UNIT_TEST_SPECS]
    checks = _checks(
        source_reports,
        integration_manifest,
        parser_sim_report,
        c_reference_report,
        payload_decoder_contract,
        mode_manager_c_reference_report,
        unit_tests,
    )
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "schema": FORK_UNIT_TESTS_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "contract_state": "READY_FOR_FORK_TEST_IMPLEMENTATION" if status == "PASS" else "BLOCKED",
        "source_reports": source_reports,
        "summary": {
            "test_group_count": len(test_groups),
            "unit_test_count": len(unit_tests),
            "required_unit_test_count": sum(1 for row in unit_tests if row["required_for_merge"]),
            "parser_test_count": _group_count(unit_tests, "uart_parser"),
            "payload_decoder_test_count": _group_count(unit_tests, "payload_decoder"),
            "mode_manager_test_count": _group_count(unit_tests, "ai_mode_manager"),
            "integration_test_count": _group_count(unit_tests, "fork_integration"),
            "firmware_source_count": len(_firmware_sources(integration_manifest)),
            "test_fixture_count": len(_test_sources(integration_manifest)),
            "tests_executed_in_manifest": False,
            "betaflight_repo_modified": False,
            "compile_attempted": False,
            "flash_attempted": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "test_groups": test_groups,
        "unit_tests": unit_tests,
        "acceptance_matrix": _acceptance_matrix(integration_manifest),
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "contract_only": True,
            "does_not_modify_betaflight_repo": True,
            "does_not_compile_or_flash_betaflight": True,
            "does_not_execute_c_tests": True,
            "does_not_open_uart": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
            "does_not_command_motors_directly": True,
        },
    }


def write_betaflight_fork_unit_test_contract(
    *,
    integration_manifest_json: Path,
    parser_sim_json: Path,
    c_reference_json: Path,
    payload_decoder_json: Path,
    mode_manager_c_reference_json: Path,
    output_json: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    contract = build_betaflight_fork_unit_test_contract(
        integration_manifest=_read_json(integration_manifest_json),
        parser_sim_report=_read_json(parser_sim_json),
        c_reference_report=_read_json(c_reference_json),
        payload_decoder_contract=_read_json(payload_decoder_json),
        mode_manager_c_reference_report=_read_json(mode_manager_c_reference_json),
        integration_manifest_path=integration_manifest_json,
        parser_sim_path=parser_sim_json,
        c_reference_path=c_reference_json,
        payload_decoder_path=payload_decoder_json,
        mode_manager_c_reference_path=mode_manager_c_reference_json,
        project_root=project_root,
    )
    persisted = dict(contract)
    persisted["contract_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _test_groups() -> list[dict[str, str]]:
    return [
        _group("uart_parser", "UART parser CRC, heartbeat, sequence, and timeout behavior."),
        _group("payload_decoder", "Payload JSON hook mapping into decoded C command fields."),
        _group("ai_mode_manager", "AI mode/prearm/arm/control gate behavior."),
        _group("fork_integration", "Compile-plan, fixture, and safety-boundary integration tests."),
    ]


def _unit_test_entry(spec: UnitTestSpec) -> dict[str, Any]:
    return {
        "test_id": spec.test_id,
        "group_id": spec.group_id,
        "target_source": spec.target_source,
        "fixture_source": spec.fixture_source,
        "requirement": spec.requirement,
        "expected_result": spec.expected_result,
        "required_for_merge": True,
        "execution_state": "NOT_RUN_IN_MANIFEST",
    }


def _acceptance_matrix(integration_manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    firmware_sources = set(_firmware_sources(integration_manifest))
    test_sources = set(_test_sources(integration_manifest))
    return [
        _matrix_row("uart_parser_source", PARSER_SOURCE in firmware_sources, PARSER_SOURCE),
        _matrix_row("payload_decoder_source", PAYLOAD_DECODER_SOURCE in firmware_sources, PAYLOAD_DECODER_SOURCE),
        _matrix_row("mode_manager_source", MODE_MANAGER_SOURCE in firmware_sources, MODE_MANAGER_SOURCE),
        _matrix_row("uart_golden_fixture", UART_FIXTURE in test_sources, UART_FIXTURE),
        _matrix_row("mode_manager_fixture", MODE_MANAGER_FIXTURE in test_sources, MODE_MANAGER_FIXTURE),
    ]


def _checks(
    source_reports: list[dict[str, str]],
    integration_manifest: Mapping[str, Any],
    parser_sim_report: Mapping[str, Any],
    c_reference_report: Mapping[str, Any],
    payload_decoder_contract: Mapping[str, Any],
    mode_manager_c_reference_report: Mapping[str, Any],
    unit_tests: list[dict[str, Any]],
) -> list[dict[str, str]]:
    parser_summary = _mapping(parser_sim_report.get("summary"))
    payload_summary = _mapping(payload_decoder_contract.get("summary"))
    mode_summary = _mapping(mode_manager_c_reference_report.get("summary"))
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
            "integration_manifest_ready",
            integration_manifest.get("integration_state") == "READY_FOR_FORK_REVIEW",
            str(integration_manifest.get("integration_state") or ""),
        ),
        _check("all_required_sources_declared", _required_sources_declared(integration_manifest), "parser,decoder,mode manager"),
        _check("all_required_fixtures_declared", _required_fixtures_declared(integration_manifest), "UART and mode fixtures"),
        _check(
            "parser_sim_accepts_golden_frames",
            int(parser_summary.get("accepted_count") or 0)
            == int(parser_summary.get("frame_count") or -1),
            str(parser_summary.get("accepted_count") or 0),
        ),
        _check(
            "c_reference_generated",
            int(_mapping(c_reference_report.get("summary")).get("artifact_count") or 0) >= 3,
            str(_mapping(c_reference_report.get("summary")).get("artifact_count") or 0),
        ),
        _check(
            "payload_decoder_maps_all_fields",
            int(payload_summary.get("field_mapping_count") or 0) == 12,
            str(payload_summary.get("field_mapping_count") or 0),
        ),
        _check(
            "mode_manager_reference_ready",
            mode_summary.get("direct_motor_output_allowed") is False
            and int(mode_summary.get("mode_event_count") or 0) > 0,
            str(mode_summary.get("mode_event_count") or 0),
        ),
        _check("unit_tests_cover_parser", _group_count(unit_tests, "uart_parser") >= 6, "parser tests"),
        _check("unit_tests_cover_payload_decoder", _group_count(unit_tests, "payload_decoder") >= 4, "payload tests"),
        _check("unit_tests_cover_mode_manager", _group_count(unit_tests, "ai_mode_manager") >= 6, "mode tests"),
        _check("unit_tests_cover_integration", _group_count(unit_tests, "fork_integration") >= 3, "integration tests"),
        _check("tests_not_executed_here", all(row["execution_state"] == "NOT_RUN_IN_MANIFEST" for row in unit_tests), "contract only"),
        _check("no_live_uart_access", True, "file-only manifest"),
        _check("no_compile_or_flash", True, "compile/flash outside this contract"),
    ]


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


def _required_sources_declared(integration_manifest: Mapping[str, Any]) -> bool:
    sources = set(_firmware_sources(integration_manifest))
    return {PARSER_SOURCE, PAYLOAD_DECODER_SOURCE, MODE_MANAGER_SOURCE}.issubset(sources)


def _required_fixtures_declared(integration_manifest: Mapping[str, Any]) -> bool:
    sources = set(_test_sources(integration_manifest))
    return {UART_FIXTURE, MODE_MANAGER_FIXTURE}.issubset(sources)


def _firmware_sources(integration_manifest: Mapping[str, Any]) -> list[str]:
    return _compile_plan_list(integration_manifest, "firmware_sources")


def _test_sources(integration_manifest: Mapping[str, Any]) -> list[str]:
    return _compile_plan_list(integration_manifest, "test_sources")


def _compile_plan_list(integration_manifest: Mapping[str, Any], key: str) -> list[str]:
    compile_plan = integration_manifest.get("compile_plan")
    if not isinstance(compile_plan, Mapping):
        return []
    rows = compile_plan.get(key)
    return [str(row) for row in rows if isinstance(row, str)] if isinstance(rows, list) else []


def _group_count(unit_tests: Sequence[Mapping[str, Any]], group_id: str) -> int:
    return sum(1 for row in unit_tests if row.get("group_id") == group_id)


def _group(group_id: str, detail: str) -> dict[str, str]:
    return {
        "group_id": group_id,
        "detail": detail,
        "execution_state": "NOT_RUN_IN_MANIFEST",
    }


def _matrix_row(item_id: str, present: bool, source_path: str) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "source_path": source_path,
        "present_in_integration_manifest": present,
        "required_for_fork_tests": True,
    }


def _failed_sources(source_reports: list[dict[str, str]], *, key: str) -> str:
    if key == "schema":
        return ",".join(row["report_id"] for row in source_reports if row["schema"] != row["expected_schema"])
    return ",".join(row["report_id"] for row in source_reports if row[key] != "PASS")


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
