"""Owner-parameter completion report for FPV AI Gate-Lock.

The report summarizes the concrete values still required from the project
owner before the dry-run pipeline can be promoted toward a reviewed hardware
profile. It never invents hardware selections, grants approval, opens live
adapters, or authorizes tests.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

OWNER_PARAMETERS_COMPLETION_SCHEMA = "fpv_owner_parameters_completion_report.v1"
OWNER_RESPONSE_INPUT_SCHEMA = "fpv_mvp_open_parameters_owner_response_input.v1"
OWNER_RESPONSE_REVIEW_SCHEMA = "fpv_mvp_open_parameters_owner_response.v1"
OWNER_ACTION_PACKET_SCHEMA = "fpv_mvp_open_parameters_owner_action_packet.v1"

TARGET_FIELD_SPECS = {
    "betaflight_repo_url": (
        "betaflight_target",
        "Exact Betaflight FPV-AI fork repository URL.",
        "Blocks owner target pipeline and fork application review.",
    ),
    "betaflight_branch": (
        "betaflight_target",
        "Exact branch, tag, or commit for the FPV-AI fork.",
        "Blocks deterministic Betaflight patch/build mapping.",
    ),
    "fc_target": (
        "betaflight_target",
        "Exact Betaflight flight-controller target/board name.",
        "Blocks FC-specific build hooks and UART mapping.",
    ),
    "ai_uart_port": (
        "betaflight_target",
        "Dedicated FC UART used for Raspberry Pi AI commands.",
        "Blocks wiring review and protocol acceptance.",
    ),
    "serial_mode": (
        "betaflight_target",
        "AI command input mode.",
        "Blocks protocol selection if not selected.",
    ),
    "electrical_voltage_level": (
        "betaflight_target",
        "UART voltage/wiring domain, for example 3V3 TTL.",
        "Blocks electrical review.",
    ),
}

NON_TARGET_FIELD_SPECS = {
    "ai_accelerator_exact_model": (
        "rpi_runtime",
        "Exact Raspberry Pi AI accelerator/Hailo module.",
        "Blocks edge runtime benchmark planning.",
    ),
    "rgb_camera_model": (
        "rpi_runtime",
        "Exact RGB camera model.",
        "Blocks live perception adapter selection.",
    ),
    "rgb_lens_exposure_frame_rate": (
        "rpi_runtime",
        "Lens, exposure, shutter, and target frame rate.",
        "Blocks FPV motion-blur and latency review.",
    ),
    "first_flight_speed_limit_mps": (
        "speed_policy",
        "Owner-selected first controlled-flight speed cap.",
        "Blocks first-flight workorder.",
    ),
    "gate_size_dimensions": (
        "gate_target",
        "Gate/ring dimensions or dataset target distribution.",
        "Blocks target geometry and dataset/model acceptance setup.",
    ),
    "hand_release_detection_thresholds": (
        "launcher",
        "Release-detection thresholds for the launch device.",
        "Blocks hand-launch transition review.",
    ),
    "independent_kill_verification": (
        "hardware_safety",
        "Manual independent kill/power-cut verification.",
        "Blocks any real hardware run.",
    ),
    "first_hardware_test_scope": (
        "hardware_safety",
        "Owner-defined scope for the first hardware test.",
        "Blocks no-prop bench authorization.",
    ),
}


def build_owner_parameters_completion_report(
    *,
    owner_response_input: Mapping[str, Any],
    owner_response_review: Mapping[str, Any],
    owner_action_packet: Mapping[str, Any],
    model_candidate_registry: Mapping[str, Any] | None = None,
    edge_model_export_gate: Mapping[str, Any] | None = None,
    rc_control_report: Mapping[str, Any] | None = None,
    owner_response_input_path: Path | str | None = None,
    owner_response_review_path: Path | str | None = None,
    owner_action_packet_path: Path | str | None = None,
    model_candidate_registry_path: Path | str | None = None,
    edge_model_export_gate_path: Path | str | None = None,
    rc_control_report_path: Path | str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    model_registry = model_candidate_registry or {}
    export_gate = edge_model_export_gate or {}
    rc_report = rc_control_report or {}
    target_rows = _field_rows(
        specs=TARGET_FIELD_SPECS,
        response_values=_mapping(owner_response_input.get("target_decision_response")),
        missing_ids=_missing_ids(owner_response_review.get("missing_target_decisions"), "decision_id"),
        group="target_decision_response",
    )
    non_target_rows = _field_rows(
        specs=NON_TARGET_FIELD_SPECS,
        response_values=_mapping(owner_response_input.get("non_target_parameter_response")),
        missing_ids=_missing_ids(owner_response_review.get("missing_non_target_parameters"), "parameter_id"),
        group="non_target_parameter_response",
    )
    all_rows = target_rows + non_target_rows
    checks = _checks(owner_response_input, owner_response_review, owner_action_packet)
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    missing_count = sum(1 for row in all_rows if row["status"] == "OWNER_INPUT_REQUIRED")
    response_summary = _mapping(owner_response_review.get("summary"))
    action_summary = _mapping(owner_action_packet.get("summary"))
    return {
        "schema": OWNER_PARAMETERS_COMPLETION_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "project_root": str(root),
        "completion_state": _completion_state(status, missing_count),
        "source_reports": [
            _source("owner_response_input", owner_response_input, owner_response_input_path, OWNER_RESPONSE_INPUT_SCHEMA),
            _source("owner_response_review", owner_response_review, owner_response_review_path, OWNER_RESPONSE_REVIEW_SCHEMA),
            _source("owner_action_packet", owner_action_packet, owner_action_packet_path, OWNER_ACTION_PACKET_SCHEMA),
            _source("model_candidate_registry", model_registry, model_candidate_registry_path, "model_candidate_registry.v1"),
            _source("edge_model_export_gate", export_gate, edge_model_export_gate_path, "edge_model_export_gate.v1"),
            _source("betaflight_rc_control_report", rc_report, rc_control_report_path, "fpv_betaflight_rc_control_report.v1"),
        ],
        "summary": {
            "owner_response_state": str(owner_response_review.get("response_state") or ""),
            "packet_state": str(owner_action_packet.get("packet_state") or ""),
            "target_required_count": len(target_rows),
            "target_selected_count": sum(1 for row in target_rows if row["status"] == "SELECTED"),
            "target_missing_count": int(response_summary.get("target_missing_count") or 0),
            "non_target_required_count": len(non_target_rows),
            "non_target_answered_count": sum(1 for row in non_target_rows if row["status"] == "SELECTED"),
            "non_target_missing_count": int(response_summary.get("non_target_missing_count") or 0),
            "owner_response_action_count": int(action_summary.get("owner_response_action_count") or 0),
            "total_owner_action_count": int(action_summary.get("total_owner_action_count") or 0),
            "model_adaptation_selected": _model_adaptation_selected(owner_response_input),
            "production_model_accepted": bool(_mapping(model_registry.get("summary")).get("production_model_accepted")),
            "edge_model_export_ready": export_gate.get("export_ready") is True,
            "aux1_arm_dry_run_ready": rc_report.get("status") == "PASS"
            and int(_mapping(rc_report.get("summary")).get("arm_request_frame_count") or 0) > 0,
            "owner_approval_ready": missing_count == 0,
            "hardware_test_authorized": False,
            "no_prop_bench_authorized": False,
            "live_adapters_enabled": False,
            "flight_commands_published": False,
            "training_launched": False,
        },
        "known_project_decisions": _known_project_decisions(owner_response_input),
        "owner_parameter_rows": all_rows,
        "fill_order": _fill_order(all_rows),
        "checks": checks,
        "safety_boundary": {
            "dry_run_only": True,
            "completion_report_only": True,
            "does_not_fill_owner_values": True,
            "does_not_select_hardware_automatically": True,
            "does_not_grant_owner_approval": True,
            "does_not_authorize_hardware_test": True,
            "does_not_authorize_no_prop_bench": True,
            "does_not_open_live_cameras": True,
            "does_not_read_gpio": True,
            "does_not_open_uart": True,
            "does_not_publish_flight_commands": True,
            "does_not_compile_or_flash_betaflight": True,
            "does_not_launch_training": True,
        },
    }


def write_owner_parameters_completion_report(
    *,
    owner_response_input_json: Path,
    owner_response_review_json: Path,
    owner_action_packet_json: Path,
    output_json: Path,
    model_candidate_registry_json: Path | None = None,
    edge_model_export_gate_json: Path | None = None,
    rc_control_report_json: Path | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    report = build_owner_parameters_completion_report(
        owner_response_input=_read_json(owner_response_input_json),
        owner_response_review=_read_json(owner_response_review_json),
        owner_action_packet=_read_json(owner_action_packet_json),
        model_candidate_registry=_read_optional_json(model_candidate_registry_json),
        edge_model_export_gate=_read_optional_json(edge_model_export_gate_json),
        rc_control_report=_read_optional_json(rc_control_report_json),
        owner_response_input_path=owner_response_input_json,
        owner_response_review_path=owner_response_review_json,
        owner_action_packet_path=owner_action_packet_json,
        model_candidate_registry_path=model_candidate_registry_json,
        edge_model_export_gate_path=edge_model_export_gate_json,
        rc_control_report_path=rc_control_report_json,
        project_root=project_root,
    )
    persisted = dict(report)
    persisted["report_path"] = str(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted


def _field_rows(
    *,
    specs: Mapping[str, tuple[str, str, str]],
    response_values: Mapping[str, Any],
    missing_ids: set[str],
    group: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field_id, (category, required_value, blocks) in specs.items():
        value = response_values.get(field_id, "")
        selected = _value_selected(value) and field_id not in missing_ids
        rows.append(
            {
                "field_id": field_id,
                "group": group,
                "category": category,
                "status": "SELECTED" if selected else "OWNER_INPUT_REQUIRED",
                "current_value": value if value is not None else "",
                "required_value": required_value,
                "blocks": blocks,
            }
        )
    return rows


def _fill_order(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    categories = [
        ("betaflight_target", "Betaflight fork, FC target, UART, and voltage"),
        ("rpi_runtime", "Raspberry Pi AI accelerator and camera runtime"),
        ("speed_policy", "First-flight speed limit"),
        ("gate_target", "Gate target and dataset geometry"),
        ("launcher", "Hand-launch detection"),
        ("hardware_safety", "Independent kill and first hardware test scope"),
    ]
    result: list[dict[str, Any]] = []
    for priority, (category, title) in enumerate(categories, start=1):
        missing = [
            str(row["field_id"])
            for row in rows
            if row["category"] == category and row["status"] == "OWNER_INPUT_REQUIRED"
        ]
        result.append(
            {
                "priority": priority,
                "category": category,
                "title": title,
                "status": "OWNER_INPUT_REQUIRED" if missing else "COMPLETE",
                "missing_field_ids": missing,
            }
        )
    return result


def _known_project_decisions(owner_response_input: Mapping[str, Any]) -> list[dict[str, Any]]:
    target = _mapping(owner_response_input.get("target_decision_response"))
    context = _mapping(owner_response_input.get("decision_context"))
    rows = [
        _known("serial_mode", target.get("serial_mode"), "Betaflight command input mode"),
        _known("serial_baud", target.get("serial_baud"), "Dry-run UART baud"),
        _known("command_rate_hz", target.get("command_rate_hz"), "Dry-run AI command rate"),
        _known("speed_mode", target.get("speed_mode"), "Selected speed policy mode"),
        _known("operator_limit_mps", target.get("operator_limit_mps"), "Dry-run operator speed cap"),
    ]
    if _model_adaptation_selected(owner_response_input):
        rows.append(
            {
                "decision_id": str(context.get("decision_id") or ""),
                "value": str(context.get("target_model_family") or ""),
                "detail": "Existing sky-sensing AI/model tooling will be adapted to FPV gate lock.",
            }
        )
    return [row for row in rows if _value_selected(row["value"])]


def _known(decision_id: str, value: Any, detail: str) -> dict[str, Any]:
    return {
        "decision_id": decision_id,
        "value": value if value is not None else "",
        "detail": detail,
    }


def _checks(
    owner_response_input: Mapping[str, Any],
    owner_response_review: Mapping[str, Any],
    owner_action_packet: Mapping[str, Any],
) -> list[dict[str, str]]:
    return [
        _check("owner_response_input_schema_valid", owner_response_input.get("schema") == OWNER_RESPONSE_INPUT_SCHEMA, str(owner_response_input.get("schema") or "")),
        _check("owner_response_review_schema_valid", owner_response_review.get("schema") == OWNER_RESPONSE_REVIEW_SCHEMA, str(owner_response_review.get("schema") or "")),
        _check("owner_response_review_passed", owner_response_review.get("status") == "PASS", str(owner_response_review.get("status") or "")),
        _check("owner_action_packet_schema_valid", owner_action_packet.get("schema") == OWNER_ACTION_PACKET_SCHEMA, str(owner_action_packet.get("schema") or "")),
        _check("owner_action_packet_passed", owner_action_packet.get("status") == "PASS", str(owner_action_packet.get("status") or "")),
        _check("hardware_not_authorized", True, "completion report does not authorize hardware"),
        _check("no_live_adapter_access", True, "file-only completion report"),
    ]


def _completion_state(status: str, missing_count: int) -> str:
    if status != "PASS":
        return "BLOCKED"
    if missing_count:
        return "OWNER_VALUES_REQUIRED"
    return "OWNER_APPROVAL_READY"


def _model_adaptation_selected(owner_response_input: Mapping[str, Any]) -> bool:
    context = _mapping(owner_response_input.get("decision_context"))
    return (
        context.get("decision_id") == "reuse_existing_sky_sensing_ai_for_fpv_gate_lock"
        and context.get("decision_status") == "OWNER_SELECTED_DESIGN_DIRECTION"
    )


def _missing_ids(rows: Any, key: str) -> set[str]:
    if not isinstance(rows, list):
        return set()
    return {
        str(row.get(key) or "")
        for row in rows
        if isinstance(row, Mapping) and row.get(key)
    }


def _source(
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


def _value_selected(value: Any) -> bool:
    if isinstance(value, str):
        normalized = value.strip().upper()
        return bool(normalized) and normalized not in {
            "OWNER_SELECTION_REQUIRED",
            "OWNER_DECISION_REQUIRED",
            "OWNER_INPUT_REQUIRED",
            "TBD",
            "TODO",
            "UNKNOWN",
            "UNSELECTED",
            "NOT_SELECTED",
        }
    return value is not None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    }


def _read_optional_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return _read_json(path)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
