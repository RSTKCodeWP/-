"""C reference mode manager for the Betaflight FPV-AI fork.

The generated header/source are firmware-facing scaffolds for the AI mode,
prearm, arm-request, recovery, and virtual-receiver routing contract. They are
written as files only; this module does not compile, flash, open UART, or touch
hardware.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fpv_ai.betaflight_link.mode_state_machine import MODE_STATE_SCHEMA

MODE_MANAGER_C_REFERENCE_SCHEMA = "fpv_betaflight_mode_manager_c_reference_report.v1"

TARGET_PATHS = {
    "c_mode_manager_header": "src/main/fpv_ai/fpv_ai_mode_manager_v1.h",
    "c_mode_manager_source": "src/main/fpv_ai/fpv_ai_mode_manager_v1.c",
    "c_mode_manager_fixture": "test/unit/fpv_ai_mode_manager_fixture_v1.c",
}

LAUNCH_STATE_C = {
    "DISARMED": "FPV_AI_LAUNCH_DISARMED",
    "TARGET_SEARCH": "FPV_AI_LAUNCH_TARGET_SEARCH",
    "TARGET_CANDIDATE": "FPV_AI_LAUNCH_TARGET_CANDIDATE",
    "TARGET_LOCKED": "FPV_AI_LAUNCH_TARGET_LOCKED",
    "AI_PREARM_READY": "FPV_AI_LAUNCH_AI_PREARM_READY",
    "BUTTON_CONFIRMED": "FPV_AI_LAUNCH_BUTTON_CONFIRMED",
    "AI_ARM_REQUEST": "FPV_AI_LAUNCH_AI_ARM_REQUEST",
    "ARMED_IDLE": "FPV_AI_LAUNCH_ARMED_IDLE",
    "HAND_RELEASE_DETECTED": "FPV_AI_LAUNCH_HAND_RELEASE_DETECTED",
    "STABILIZE": "FPV_AI_LAUNCH_STABILIZE",
    "THROTTLE_RAMP": "FPV_AI_LAUNCH_THROTTLE_RAMP",
    "AI_ACTIVE": "FPV_AI_LAUNCH_AI_ACTIVE",
    "GATE_APPROACH": "FPV_AI_LAUNCH_GATE_APPROACH",
    "GATE_PASS": "FPV_AI_LAUNCH_GATE_PASS",
    "COMPLETE": "FPV_AI_LAUNCH_COMPLETE",
    "MANUAL_KILL": "FPV_AI_LAUNCH_MANUAL_KILL",
}

TARGET_STATE_C = {
    "UNKNOWN": "FPV_AI_MODE_TARGET_UNKNOWN",
    "NO_TARGET": "FPV_AI_MODE_TARGET_NO_TARGET",
    "CANDIDATE": "FPV_AI_MODE_TARGET_CANDIDATE",
    "LOCKED": "FPV_AI_MODE_TARGET_LOCKED",
    "DEGRADED": "FPV_AI_MODE_TARGET_DEGRADED",
    "PREDICTIVE_TRACK": "FPV_AI_MODE_TARGET_PREDICTIVE_TRACK",
    "REACQUIRE": "FPV_AI_MODE_TARGET_REACQUIRE",
    "RECOVERED": "FPV_AI_MODE_TARGET_RECOVERED",
    "HARD_LOST": "FPV_AI_MODE_TARGET_HARD_LOST",
}

MODE_STATE_C = {
    "AI_DISABLED": "FPV_AI_MODE_DISABLED",
    "AI_TARGET_SEARCH": "FPV_AI_MODE_TARGET_SEARCH",
    "AI_TARGET_CANDIDATE": "FPV_AI_MODE_TARGET_CANDIDATE",
    "AI_TARGET_LOCKED": "FPV_AI_MODE_TARGET_LOCKED",
    "AI_PREARM": "FPV_AI_MODE_AI_PREARM",
    "AI_ARM_REQUEST": "FPV_AI_MODE_AI_ARM_REQUEST",
    "AI_ARMED_IDLE": "FPV_AI_MODE_AI_ARMED_IDLE",
    "AI_RELEASE_DETECTED": "FPV_AI_MODE_AI_RELEASE_DETECTED",
    "AI_STABILIZE": "FPV_AI_MODE_AI_STABILIZE",
    "AI_THROTTLE_RAMP": "FPV_AI_MODE_AI_THROTTLE_RAMP",
    "AI_CONTROL_ACTIVE": "FPV_AI_MODE_AI_CONTROL_ACTIVE",
    "AI_GATE_PASS": "FPV_AI_MODE_AI_GATE_PASS",
    "AI_COMPLETE": "FPV_AI_MODE_AI_COMPLETE",
    "AI_KILL": "FPV_AI_MODE_AI_KILL",
}

COMMAND_ACTION_C = {
    "IGNORE_NEUTRAL": "FPV_AI_MODE_CMD_IGNORE_NEUTRAL",
    "REQUEST_ARM": "FPV_AI_MODE_CMD_REQUEST_ARM",
    "ACCEPT_AI_COMMAND": "FPV_AI_MODE_CMD_ACCEPT_AI_COMMAND",
    "REJECT_WATCHDOG": "FPV_AI_MODE_CMD_REJECT_WATCHDOG",
    "REJECT_SOURCE_NOT_READY": "FPV_AI_MODE_CMD_REJECT_SOURCE_NOT_READY",
    "KILL_LATCHED": "FPV_AI_MODE_CMD_KILL_LATCHED",
}

OUTPUT_ACTION_C = {
    "NEUTRAL_HOLD": "FPV_AI_MODE_OUTPUT_NEUTRAL_HOLD",
    "RAMP_LIMITED_VIRTUAL_RECEIVER": "FPV_AI_MODE_OUTPUT_RAMP_LIMITED_VIRTUAL_RECEIVER",
    "ROUTE_TO_VIRTUAL_RECEIVER": "FPV_AI_MODE_OUTPUT_ROUTE_TO_VIRTUAL_RECEIVER",
}


def build_betaflight_mode_manager_c_reference_report(
    mode_contract: Mapping[str, Any],
    *,
    mode_contract_path: Path | str | None = None,
    c_header_path: Path | str | None = None,
    c_source_path: Path | str | None = None,
    c_fixture_path: Path | str | None = None,
) -> dict[str, Any]:
    mode_events = _mode_events(mode_contract)
    c_header = generate_mode_manager_header_text()
    c_source = generate_mode_manager_source_text()
    c_fixture = generate_mode_manager_fixture_text(mode_contract)
    artifacts = [
        _artifact_entry("c_mode_manager_header", c_header_path, c_header),
        _artifact_entry("c_mode_manager_source", c_source_path, c_source),
        _artifact_entry("c_mode_manager_fixture", c_fixture_path, c_fixture),
    ]
    checks = _checks(mode_contract, mode_events, c_header, c_source, c_fixture)
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "schema": MODE_MANAGER_C_REFERENCE_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "source_contract": {
            "path": "" if mode_contract_path is None else str(mode_contract_path),
            "schema": str(mode_contract.get("schema") or ""),
            "status": str(mode_contract.get("status") or ""),
            "contract_state": str(mode_contract.get("contract_state") or ""),
            "mode_event_count": len(mode_events),
        },
        "summary": {
            "artifact_count": len(artifacts),
            "mode_event_count": len(mode_events),
            "mode_state_count": len(_mode_states(mode_contract)),
            "transition_rule_count": len(_transition_rules(mode_contract)),
            "c_header_generated": True,
            "c_source_generated": True,
            "c_fixture_generated": True,
            "virtual_receiver_route_required": True,
            "direct_motor_output_allowed": False,
            "compile_attempted": False,
            "flash_attempted": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "api_symbols": _api_symbols(),
        "integration_targets": _integration_targets(artifacts),
        "artifacts": artifacts,
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "reference_code_only": True,
            "does_not_modify_betaflight_repo": True,
            "does_not_compile_or_flash_betaflight": True,
            "does_not_open_uart": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
            "does_not_command_motors_directly": True,
        },
    }


def write_betaflight_mode_manager_c_reference_outputs(
    *,
    mode_contract_json: Path,
    report_json: Path,
    c_header_path: Path,
    c_source_path: Path,
    c_fixture_path: Path,
) -> dict[str, Any]:
    mode_contract = _read_json(mode_contract_json)
    _write_text(c_header_path, generate_mode_manager_header_text())
    _write_text(c_source_path, generate_mode_manager_source_text())
    _write_text(c_fixture_path, generate_mode_manager_fixture_text(mode_contract))
    report = build_betaflight_mode_manager_c_reference_report(
        mode_contract,
        mode_contract_path=mode_contract_json,
        c_header_path=c_header_path,
        c_source_path=c_source_path,
        c_fixture_path=c_fixture_path,
    )
    persisted = dict(report)
    persisted["report_path"] = str(report_json)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def generate_mode_manager_header_text() -> str:
    return """#ifndef FPV_AI_MODE_MANAGER_V1_H
#define FPV_AI_MODE_MANAGER_V1_H

#include <stdbool.h>
#include <stdint.h>

typedef enum {
    FPV_AI_LAUNCH_DISARMED = 0,
    FPV_AI_LAUNCH_TARGET_SEARCH = 1,
    FPV_AI_LAUNCH_TARGET_CANDIDATE = 2,
    FPV_AI_LAUNCH_TARGET_LOCKED = 3,
    FPV_AI_LAUNCH_AI_PREARM_READY = 4,
    FPV_AI_LAUNCH_BUTTON_CONFIRMED = 5,
    FPV_AI_LAUNCH_AI_ARM_REQUEST = 6,
    FPV_AI_LAUNCH_ARMED_IDLE = 7,
    FPV_AI_LAUNCH_HAND_RELEASE_DETECTED = 8,
    FPV_AI_LAUNCH_STABILIZE = 9,
    FPV_AI_LAUNCH_THROTTLE_RAMP = 10,
    FPV_AI_LAUNCH_AI_ACTIVE = 11,
    FPV_AI_LAUNCH_GATE_APPROACH = 12,
    FPV_AI_LAUNCH_GATE_PASS = 13,
    FPV_AI_LAUNCH_COMPLETE = 14,
    FPV_AI_LAUNCH_MANUAL_KILL = 15
} fpv_ai_launch_state_v1_t;

typedef enum {
    FPV_AI_MODE_TARGET_UNKNOWN = 0,
    FPV_AI_MODE_TARGET_NO_TARGET = 1,
    FPV_AI_MODE_TARGET_CANDIDATE = 2,
    FPV_AI_MODE_TARGET_LOCKED = 3,
    FPV_AI_MODE_TARGET_DEGRADED = 4,
    FPV_AI_MODE_TARGET_PREDICTIVE_TRACK = 5,
    FPV_AI_MODE_TARGET_REACQUIRE = 6,
    FPV_AI_MODE_TARGET_RECOVERED = 7,
    FPV_AI_MODE_TARGET_HARD_LOST = 8
} fpv_ai_mode_target_state_v1_t;

typedef enum {
    FPV_AI_MODE_DISABLED = 0,
    FPV_AI_MODE_TARGET_SEARCH = 1,
    FPV_AI_MODE_TARGET_CANDIDATE = 2,
    FPV_AI_MODE_TARGET_LOCKED = 3,
    FPV_AI_MODE_AI_PREARM = 4,
    FPV_AI_MODE_AI_ARM_REQUEST = 5,
    FPV_AI_MODE_AI_ARMED_IDLE = 6,
    FPV_AI_MODE_AI_RELEASE_DETECTED = 7,
    FPV_AI_MODE_AI_STABILIZE = 8,
    FPV_AI_MODE_AI_THROTTLE_RAMP = 9,
    FPV_AI_MODE_AI_CONTROL_ACTIVE = 10,
    FPV_AI_MODE_AI_GATE_PASS = 11,
    FPV_AI_MODE_AI_COMPLETE = 12,
    FPV_AI_MODE_AI_KILL = 13
} fpv_ai_mode_state_v1_t;

typedef enum {
    FPV_AI_MODE_CMD_IGNORE_NEUTRAL = 0,
    FPV_AI_MODE_CMD_REQUEST_ARM = 1,
    FPV_AI_MODE_CMD_ACCEPT_AI_COMMAND = 2,
    FPV_AI_MODE_CMD_REJECT_WATCHDOG = 3,
    FPV_AI_MODE_CMD_REJECT_SOURCE_NOT_READY = 4,
    FPV_AI_MODE_CMD_KILL_LATCHED = 5
} fpv_ai_mode_command_action_v1_t;

typedef enum {
    FPV_AI_MODE_OUTPUT_NEUTRAL_HOLD = 0,
    FPV_AI_MODE_OUTPUT_RAMP_LIMITED_VIRTUAL_RECEIVER = 1,
    FPV_AI_MODE_OUTPUT_ROUTE_TO_VIRTUAL_RECEIVER = 2
} fpv_ai_mode_output_action_v1_t;

typedef struct {
    fpv_ai_launch_state_v1_t launch_state;
    fpv_ai_mode_target_state_v1_t target_state;
    bool integration_ready;
    bool parser_ready;
    bool watchdog_ok;
    bool manual_kill;
    bool target_locked;
    bool throttle_low;
    bool fc_armed;
    bool hand_release_detected;
    bool source_ai_control_allowed;
} fpv_ai_mode_input_v1_t;

typedef struct {
    fpv_ai_mode_state_v1_t mode_state;
    fpv_ai_mode_command_action_v1_t command_action;
    fpv_ai_mode_output_action_v1_t output_action;
    bool ai_mode;
    bool ai_prearm;
    bool ai_arm_request;
    bool ai_control_active;
    bool ai_recovery_mode;
    bool ai_kill;
    bool fork_ai_control_allowed;
    bool route_to_virtual_receiver;
    bool direct_motor_output_allowed;
} fpv_ai_mode_output_v1_t;

void fpv_ai_mode_output_neutral_v1(fpv_ai_mode_output_v1_t *out);

bool fpv_ai_mode_manager_update_v1(
    const fpv_ai_mode_input_v1_t *input,
    fpv_ai_mode_output_v1_t *out
);

#endif
"""


def generate_mode_manager_source_text() -> str:
    return """#include "fpv_ai_mode_manager_v1.h"

static bool fpv_ai_mode_is_prearm_state_v1(fpv_ai_launch_state_v1_t state)
{
    return state == FPV_AI_LAUNCH_AI_PREARM_READY ||
        state == FPV_AI_LAUNCH_BUTTON_CONFIRMED;
}

static bool fpv_ai_mode_is_control_state_v1(fpv_ai_launch_state_v1_t state)
{
    return state == FPV_AI_LAUNCH_THROTTLE_RAMP ||
        state == FPV_AI_LAUNCH_AI_ACTIVE ||
        state == FPV_AI_LAUNCH_GATE_APPROACH ||
        state == FPV_AI_LAUNCH_GATE_PASS;
}

static bool fpv_ai_mode_is_workflow_state_v1(fpv_ai_launch_state_v1_t state)
{
    return fpv_ai_mode_is_prearm_state_v1(state) ||
        state == FPV_AI_LAUNCH_AI_ARM_REQUEST ||
        state == FPV_AI_LAUNCH_ARMED_IDLE ||
        state == FPV_AI_LAUNCH_HAND_RELEASE_DETECTED ||
        state == FPV_AI_LAUNCH_STABILIZE ||
        fpv_ai_mode_is_control_state_v1(state);
}

static bool fpv_ai_mode_target_recovery_v1(fpv_ai_mode_target_state_v1_t target_state)
{
    return target_state == FPV_AI_MODE_TARGET_DEGRADED ||
        target_state == FPV_AI_MODE_TARGET_PREDICTIVE_TRACK ||
        target_state == FPV_AI_MODE_TARGET_REACQUIRE ||
        target_state == FPV_AI_MODE_TARGET_HARD_LOST;
}

static fpv_ai_mode_state_v1_t fpv_ai_mode_state_from_launch_v1(
    fpv_ai_launch_state_v1_t launch_state
)
{
    switch (launch_state) {
    case FPV_AI_LAUNCH_DISARMED:
        return FPV_AI_MODE_DISABLED;
    case FPV_AI_LAUNCH_TARGET_SEARCH:
        return FPV_AI_MODE_TARGET_SEARCH;
    case FPV_AI_LAUNCH_TARGET_CANDIDATE:
        return FPV_AI_MODE_TARGET_CANDIDATE;
    case FPV_AI_LAUNCH_TARGET_LOCKED:
        return FPV_AI_MODE_TARGET_LOCKED;
    case FPV_AI_LAUNCH_AI_PREARM_READY:
    case FPV_AI_LAUNCH_BUTTON_CONFIRMED:
        return FPV_AI_MODE_AI_PREARM;
    case FPV_AI_LAUNCH_AI_ARM_REQUEST:
        return FPV_AI_MODE_AI_ARM_REQUEST;
    case FPV_AI_LAUNCH_ARMED_IDLE:
        return FPV_AI_MODE_AI_ARMED_IDLE;
    case FPV_AI_LAUNCH_HAND_RELEASE_DETECTED:
        return FPV_AI_MODE_AI_RELEASE_DETECTED;
    case FPV_AI_LAUNCH_STABILIZE:
        return FPV_AI_MODE_AI_STABILIZE;
    case FPV_AI_LAUNCH_THROTTLE_RAMP:
        return FPV_AI_MODE_AI_THROTTLE_RAMP;
    case FPV_AI_LAUNCH_AI_ACTIVE:
    case FPV_AI_LAUNCH_GATE_APPROACH:
        return FPV_AI_MODE_AI_CONTROL_ACTIVE;
    case FPV_AI_LAUNCH_GATE_PASS:
        return FPV_AI_MODE_AI_GATE_PASS;
    case FPV_AI_LAUNCH_COMPLETE:
        return FPV_AI_MODE_AI_COMPLETE;
    case FPV_AI_LAUNCH_MANUAL_KILL:
        return FPV_AI_MODE_AI_KILL;
    }
    return FPV_AI_MODE_DISABLED;
}

void fpv_ai_mode_output_neutral_v1(fpv_ai_mode_output_v1_t *out)
{
    if (out == 0) {
        return;
    }

    out->mode_state = FPV_AI_MODE_DISABLED;
    out->command_action = FPV_AI_MODE_CMD_IGNORE_NEUTRAL;
    out->output_action = FPV_AI_MODE_OUTPUT_NEUTRAL_HOLD;
    out->ai_mode = false;
    out->ai_prearm = false;
    out->ai_arm_request = false;
    out->ai_control_active = false;
    out->ai_recovery_mode = false;
    out->ai_kill = false;
    out->fork_ai_control_allowed = false;
    out->route_to_virtual_receiver = false;
    out->direct_motor_output_allowed = false;
}

bool fpv_ai_mode_manager_update_v1(
    const fpv_ai_mode_input_v1_t *input,
    fpv_ai_mode_output_v1_t *out
)
{
    const bool active_sources_ready =
        input != 0 && input->integration_ready && input->parser_ready;

    if (input == 0 || out == 0) {
        return false;
    }

    fpv_ai_mode_output_neutral_v1(out);
    out->mode_state = fpv_ai_mode_state_from_launch_v1(input->launch_state);
    out->ai_mode = fpv_ai_mode_is_workflow_state_v1(input->launch_state);
    out->ai_prearm = fpv_ai_mode_is_prearm_state_v1(input->launch_state);
    out->ai_arm_request = input->launch_state == FPV_AI_LAUNCH_AI_ARM_REQUEST;
    out->ai_recovery_mode =
        fpv_ai_mode_is_control_state_v1(input->launch_state) &&
        fpv_ai_mode_target_recovery_v1(input->target_state);
    out->ai_kill = input->manual_kill || input->launch_state == FPV_AI_LAUNCH_MANUAL_KILL;
    out->fork_ai_control_allowed =
        fpv_ai_mode_is_control_state_v1(input->launch_state) &&
        active_sources_ready &&
        input->watchdog_ok &&
        !input->manual_kill;

    if (out->ai_kill) {
        out->command_action = FPV_AI_MODE_CMD_KILL_LATCHED;
        out->output_action = FPV_AI_MODE_OUTPUT_NEUTRAL_HOLD;
    } else if (!input->watchdog_ok) {
        out->command_action = FPV_AI_MODE_CMD_REJECT_WATCHDOG;
        out->output_action = FPV_AI_MODE_OUTPUT_NEUTRAL_HOLD;
    } else if (!active_sources_ready) {
        out->command_action = FPV_AI_MODE_CMD_REJECT_SOURCE_NOT_READY;
        out->output_action = FPV_AI_MODE_OUTPUT_NEUTRAL_HOLD;
    } else if (out->ai_arm_request) {
        if (input->throttle_low && input->target_locked) {
            out->command_action = FPV_AI_MODE_CMD_REQUEST_ARM;
        } else {
            out->command_action = FPV_AI_MODE_CMD_IGNORE_NEUTRAL;
        }
        out->output_action = FPV_AI_MODE_OUTPUT_NEUTRAL_HOLD;
    } else if (out->fork_ai_control_allowed) {
        out->command_action = FPV_AI_MODE_CMD_ACCEPT_AI_COMMAND;
        out->output_action =
            input->launch_state == FPV_AI_LAUNCH_THROTTLE_RAMP ?
            FPV_AI_MODE_OUTPUT_RAMP_LIMITED_VIRTUAL_RECEIVER :
            FPV_AI_MODE_OUTPUT_ROUTE_TO_VIRTUAL_RECEIVER;
    } else {
        out->command_action = FPV_AI_MODE_CMD_IGNORE_NEUTRAL;
        out->output_action = FPV_AI_MODE_OUTPUT_NEUTRAL_HOLD;
    }

    out->ai_control_active = out->fork_ai_control_allowed;
    out->route_to_virtual_receiver =
        out->output_action == FPV_AI_MODE_OUTPUT_RAMP_LIMITED_VIRTUAL_RECEIVER ||
        out->output_action == FPV_AI_MODE_OUTPUT_ROUTE_TO_VIRTUAL_RECEIVER;
    out->direct_motor_output_allowed = false;
    return true;
}
"""


def generate_mode_manager_fixture_text(mode_contract: Mapping[str, Any]) -> str:
    rows = _mode_events(mode_contract)
    lines = [
        '#include "fpv_ai_mode_manager_v1.h"',
        "",
        "typedef struct {",
        "    uint32_t frame_index;",
        "    uint32_t timestamp_ms;",
        "    fpv_ai_launch_state_v1_t launch_state;",
        "    fpv_ai_mode_target_state_v1_t target_state;",
        "    bool watchdog_ok;",
        "    bool throttle_low;",
        "    bool target_locked;",
        "    bool source_ai_control_allowed;",
        "    fpv_ai_mode_state_v1_t expected_mode_state;",
        "    fpv_ai_mode_command_action_v1_t expected_command_action;",
        "    fpv_ai_mode_output_action_v1_t expected_output_action;",
        "} fpv_ai_mode_fixture_row_v1_t;",
        "",
        "const fpv_ai_mode_fixture_row_v1_t fpv_ai_mode_fixture_rows_v1[] = {",
    ]
    for row in rows:
        lines.append(
            "    {"
            f"{int(row['frame_index'])}u, "
            f"{int(row['timestamp_ms'])}u, "
            f"{_c_launch_state(row)}, "
            f"{_c_target_state(row)}, "
            f"{_c_bool(row.get('watchdog_ok'))}, "
            f"{_c_bool(row.get('throttle_low'))}, "
            f"{_c_bool(row.get('target_locked'))}, "
            f"{_c_bool(row.get('source_ai_control_allowed'))}, "
            f"{_c_mode_state(row)}, "
            f"{_c_command_action(row)}, "
            f"{_c_output_action(row)}"
            "},"
        )
    lines.extend([
        "};",
        "",
        f"const uint32_t fpv_ai_mode_fixture_row_count_v1 = {len(rows)}u;",
        "",
    ])
    return "\n".join(lines)


def _checks(
    mode_contract: Mapping[str, Any],
    mode_events: list[Mapping[str, Any]],
    c_header: str,
    c_source: str,
    c_fixture: str,
) -> list[dict[str, str]]:
    required_header_tokens = (
        "fpv_ai_mode_input_v1_t",
        "fpv_ai_mode_output_v1_t",
        "fpv_ai_mode_manager_update_v1",
        "FPV_AI_MODE_AI_PREARM",
        "FPV_AI_MODE_OUTPUT_ROUTE_TO_VIRTUAL_RECEIVER",
    )
    required_source_tokens = (
        "input->throttle_low",
        "input->target_locked",
        "input->watchdog_ok",
        "FPV_AI_MODE_CMD_REQUEST_ARM",
        "FPV_AI_MODE_OUTPUT_RAMP_LIMITED_VIRTUAL_RECEIVER",
        "out->direct_motor_output_allowed = false",
    )
    return [
        _check("source_contract_schema_valid", mode_contract.get("schema") == MODE_STATE_SCHEMA, str(mode_contract.get("schema") or "")),
        _check("source_contract_passed", mode_contract.get("status") == "PASS", str(mode_contract.get("status") or "")),
        _check("source_contract_ready", mode_contract.get("contract_state") == "READY_FOR_FORK_UNIT_TESTS", str(mode_contract.get("contract_state") or "")),
        _check("mode_events_present", bool(mode_events), str(len(mode_events))),
        _check("header_exports_mode_manager_api", all(token in c_header for token in required_header_tokens), ",".join(required_header_tokens)),
        _check("source_enforces_mode_rules", all(token in c_source for token in required_source_tokens), ",".join(required_source_tokens)),
        _check("fixture_contains_all_mode_events", c_fixture.count("},") == len(mode_events), str(len(mode_events))),
        _check("fixture_exports_count", "fpv_ai_mode_fixture_row_count_v1" in c_fixture, "fixture count symbol"),
        _check("no_direct_motor_output", "direct_motor_output_allowed = false" in c_source, "virtual receiver only"),
        _check("no_live_uart_access", True, "reference code generation only"),
    ]


def _api_symbols() -> list[dict[str, str]]:
    return [
        _api_symbol("fpv_ai_launch_state_v1_t", "C enum", "launch workflow input state"),
        _api_symbol("fpv_ai_mode_target_state_v1_t", "C enum", "target/recovery input state"),
        _api_symbol("fpv_ai_mode_state_v1_t", "C enum", "Betaflight AI mode state"),
        _api_symbol("fpv_ai_mode_input_v1_t", "C struct", "mode manager input contract"),
        _api_symbol("fpv_ai_mode_output_v1_t", "C struct", "mode manager output contract"),
        _api_symbol("fpv_ai_mode_output_neutral_v1", "function", "force neutral output"),
        _api_symbol("fpv_ai_mode_manager_update_v1", "function", "AI mode decision function"),
    ]


def _integration_targets(artifacts: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "artifact_id": str(artifact["artifact_id"]),
            "source_path": str(artifact["path"]),
            "target_path": TARGET_PATHS[str(artifact["artifact_id"])],
        }
        for artifact in artifacts
    ]


def _artifact_entry(artifact_id: str, path: Path | str | None, text: str) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "path": "" if path is None else str(path),
        "sha256": _text_sha256(text),
        "size_bytes": len(text.encode("utf-8")),
    }


def _mode_events(mode_contract: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = mode_contract.get("mode_events")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _mode_states(mode_contract: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = mode_contract.get("mode_states")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _transition_rules(mode_contract: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = mode_contract.get("transition_rules")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _c_launch_state(row: Mapping[str, Any]) -> str:
    return LAUNCH_STATE_C.get(str(row.get("launch_state") or ""), "FPV_AI_LAUNCH_DISARMED")


def _c_target_state(row: Mapping[str, Any]) -> str:
    return TARGET_STATE_C.get(str(row.get("target_state") or ""), "FPV_AI_MODE_TARGET_UNKNOWN")


def _c_mode_state(row: Mapping[str, Any]) -> str:
    return MODE_STATE_C.get(str(row.get("fork_mode_state") or ""), "FPV_AI_MODE_DISABLED")


def _c_command_action(row: Mapping[str, Any]) -> str:
    return COMMAND_ACTION_C.get(str(row.get("command_acceptance") or ""), "FPV_AI_MODE_CMD_IGNORE_NEUTRAL")


def _c_output_action(row: Mapping[str, Any]) -> str:
    return OUTPUT_ACTION_C.get(str(row.get("output_action") or ""), "FPV_AI_MODE_OUTPUT_NEUTRAL_HOLD")


def _c_bool(value: object) -> str:
    return "true" if value is True else "false"


def _api_symbol(name: str, kind: str, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "kind": kind,
        "detail": detail,
    }


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    }


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
