"""Observation-only external state contract.

This contract is the machine-readable handoff from the sensing system to
operator, reporting, or lawful external review systems. It carries coordinates
when localization is valid, but it deliberately carries no action command.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence, cast

from cuas.interop.codec.jcs import canonical_json, sha256_hex

SCHEMA_OBSERVATION_STATE = "observation_state.v1"

OPERATOR_DECISIONS = {
    "unreviewed",
    "observe_more",
    "confirmed",
    "rejected",
    "false_alarm",
}

LOCALIZATION_STATUSES = {
    "position_valid",
    "position_degraded",
    "bearing_only",
    "unlocalized",
    "rejected",
}

PROHIBITED_ACTION_FIELDS = {
    "action_command",
    "autonomous_launch",
    "collision_course_guidance",
    "engagement_command",
    "fpv_command",
    "intercept_geometry",
    "launch_command",
    "launch_recommendation",
    "strike_command",
    "target_engagement",
    "terminal_guidance",
    "weapon_release",
}

REQUIRED_FIELDS = (
    "schema_version",
    "observation_state_id",
    "emitted_at_utc",
    "track_id",
    "observed_at_utc",
    "local_frame_id",
    "source_station_ids",
    "operator_decision",
    "target_class",
    "fused_confidence",
    "localization_status",
    "target_state_3d",
    "bearing_rays",
    "trajectory_prediction",
    "evidence_refs",
    "stale_after_utc",
    "safety_mode",
    "safety_boundary",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _deep_copy_dict(payload: Mapping[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(payload, ensure_ascii=False)))


def _deep_copy_list(payload: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [_deep_copy_dict(item) for item in payload]


def _source_station_ids(target_state_3d: Mapping[str, Any]) -> list[str]:
    values = target_state_3d.get("contributing_node_ids")
    if not isinstance(values, list):
        return []
    return sorted({str(item) for item in values if str(item)})


def _operator_decision(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"confirm", "confirmed", "accept", "accepted", "operator_confirmed"}:
        return "confirmed"
    if normalized in {"reject", "rejected", "deny", "denied"}:
        return "rejected"
    if normalized in {"artifact", "false_alarm", "false-positive", "false_positive"}:
        return "false_alarm"
    if normalized in {"uncertain", "needs_more_observation", "observe_more", "review"}:
        return "observe_more"
    return "unreviewed"


def _target_class(value: object) -> str:
    return str(value or "").strip() or "unknown"


def _localization_status_from_target_state(target_state_3d: Mapping[str, Any]) -> str:
    method = str(target_state_3d.get("source_localization_method", "") or "").lower()
    position = target_state_3d.get("position_local_enu_m")
    if method in {"single_node_bearing_ray", "bearing_only", "bearing_only_no_enu_position"}:
        return "bearing_only"
    if not isinstance(position, list) or len(position) < 3:
        return "bearing_only"
    horizontal = str(target_state_3d.get("horizontal_position_quality", "") or "").lower()
    vertical = str(target_state_3d.get("vertical_position_quality", "") or "").lower()
    if horizontal in {"excellent", "good"} and vertical in {"excellent", "good", "marginal", ""}:
        return "position_valid"
    return "position_degraded"


def _bearing_rays_from_measurements(measurements: Sequence[Any]) -> list[dict[str, Any]]:
    rays: list[dict[str, Any]] = []
    for measurement in measurements:
        if isinstance(measurement, Mapping):
            item = measurement
            rays.append({
                "measurement_id": str(item.get("measurement_id", "") or ""),
                "node_id": str(item.get("node_id", "") or ""),
                "sensor_id": str(item.get("sensor_id", "") or ""),
                "modality": str(item.get("modality", "") or ""),
                "frame_id": str(item.get("frame_id", "") or ""),
                "timestamp_global_ns": item.get("timestamp_global_ns"),
                "azimuth_deg": item.get("azimuth_deg"),
                "elevation_deg": item.get("elevation_deg"),
                "az_sigma_deg": item.get("az_sigma_deg"),
                "el_sigma_deg": item.get("el_sigma_deg"),
                "detection_confidence": item.get("detection_confidence"),
            })
            continue
        rays.append({
            "measurement_id": str(getattr(measurement, "measurement_id", "") or ""),
            "node_id": str(getattr(measurement, "node_id", "") or ""),
            "sensor_id": str(getattr(measurement, "sensor_id", "") or ""),
            "modality": str(getattr(measurement, "modality", "") or ""),
            "frame_id": str(getattr(measurement, "frame_id", "") or ""),
            "timestamp_global_ns": int(getattr(measurement, "timestamp_global_ns", 0) or 0),
            "azimuth_deg": float(getattr(measurement, "azimuth_deg", 0.0) or 0.0),
            "elevation_deg": float(getattr(measurement, "elevation_deg", 0.0) or 0.0),
            "az_sigma_deg": float(getattr(measurement, "az_sigma_deg", 0.0) or 0.0),
            "el_sigma_deg": float(getattr(measurement, "el_sigma_deg", 0.0) or 0.0),
            "detection_confidence": float(getattr(measurement, "detection_confidence", 0.0) or 0.0),
        })
    return rays


def _average_confidence_from_measurements(measurements: Sequence[Any]) -> float:
    values: list[float] = []
    for measurement in measurements:
        value = (
            measurement.get("detection_confidence")
            if isinstance(measurement, Mapping)
            else getattr(measurement, "detection_confidence", None)
        )
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if 0.0 <= number <= 1.0:
            values.append(number)
    return round(sum(values) / len(values), 6) if values else 0.0


def _first_frame_id(measurements: Sequence[Any]) -> str:
    for measurement in measurements:
        value = (
            measurement.get("frame_id")
            if isinstance(measurement, Mapping)
            else getattr(measurement, "frame_id", "")
        )
        if str(value or ""):
            return str(value)
    return "unknown_local_frame"


def _prediction_from_snapshot(snapshot: Any) -> dict[str, Any]:
    prediction = getattr(snapshot, "prediction", None)
    if prediction is None:
        return {}
    to_dict = getattr(prediction, "to_dict", None)
    if callable(to_dict):
        result = to_dict()
        return result if isinstance(result, dict) else {}
    return prediction if isinstance(prediction, dict) else {}


def observation_state_from_snapshot(
    snapshot: Any,
    *,
    local_frame_id: str | None = None,
    operator_decision: str = "unreviewed",
    target_class: str = "unknown",
    fused_confidence: float | None = None,
    trajectory_prediction: Mapping[str, Any] | None = None,
    evidence_refs: Sequence[Mapping[str, Any]] = (),
    stale_after_utc: str | None = None,
    observation_state_id: str | None = None,
) -> dict[str, Any]:
    """Build `observation_state.v1` from a live StateFusionSnapshot object."""
    from cuas.fusion.state.runtime import target_state_3d_from_snapshot

    measurements = tuple(getattr(snapshot, "measurements", ()) or ())
    target_state_3d = target_state_3d_from_snapshot(snapshot)
    return build_observation_state(
        track_id=str(getattr(snapshot, "track_id", "") or ""),
        local_frame_id=local_frame_id or _first_frame_id(measurements),
        target_state_3d=target_state_3d,
        operator_decision=_operator_decision(operator_decision),
        target_class=_target_class(target_class),
        fused_confidence=(
            _average_confidence_from_measurements(measurements)
            if fused_confidence is None
            else float(fused_confidence)
        ),
        localization_status=_localization_status_from_target_state(target_state_3d),
        trajectory_prediction=trajectory_prediction or _prediction_from_snapshot(snapshot),
        bearing_rays=_bearing_rays_from_measurements(measurements),
        evidence_refs=evidence_refs,
        stale_after_utc=stale_after_utc,
        observation_state_id=observation_state_id,
    )


def observation_state_from_snapshot_payload(
    snapshot_payload: Mapping[str, Any],
    *,
    local_frame_id: str = "unknown_local_frame",
    operator_decision: str = "unreviewed",
    target_class: str = "unknown",
    fused_confidence: float | None = None,
    bearing_rays: Sequence[Mapping[str, Any]] = (),
    evidence_refs: Sequence[Mapping[str, Any]] = (),
    stale_after_utc: str | None = None,
    observation_state_id: str | None = None,
) -> dict[str, Any]:
    """Build `observation_state.v1` from a serialized state-fusion snapshot."""
    target_state = snapshot_payload.get("target_state_3d")
    if not isinstance(target_state, Mapping):
        raise ValueError("state-fusion snapshot payload requires target_state_3d")
    confidence = fused_confidence
    if confidence is None:
        nees = snapshot_payload.get("nees")
        confidence = 0.0 if isinstance(nees, Mapping) and nees.get("status") == "fail" else 0.5
    return build_observation_state(
        track_id=str(snapshot_payload.get("track_id", "") or ""),
        local_frame_id=local_frame_id,
        target_state_3d=target_state,
        operator_decision=_operator_decision(operator_decision),
        target_class=_target_class(target_class),
        fused_confidence=float(confidence),
        localization_status=_localization_status_from_target_state(target_state),
        trajectory_prediction=(
            snapshot_payload.get("motion_prediction")
            if isinstance(snapshot_payload.get("motion_prediction"), Mapping)
            else {}
        ),
        bearing_rays=bearing_rays,
        evidence_refs=evidence_refs,
        stale_after_utc=stale_after_utc,
        observation_state_id=observation_state_id,
    )


def _track_target_state(track: Mapping[str, Any]) -> dict[str, Any]:
    payload = track.get("last_payload")
    state_context = payload.get("state_fusion_context") if isinstance(payload, Mapping) else None
    target_state = (
        state_context.get("target_state_3d")
        if isinstance(state_context, Mapping)
        else track.get("target_state_3d")
    )
    if isinstance(target_state, Mapping):
        return _deep_copy_dict(target_state)
    position = track.get("position")
    pos = position if isinstance(position, Mapping) else {}
    contributors = track.get("contributors")
    return {
        "schema_version": "target_state_3d.v1",
        "timestamp_utc": str(track.get("updated_at", "") or track.get("timestamp_utc", "") or _utc_now()),
        "position_local_enu_m": None,
        "position_uncertainty_3sigma_m": None,
        "source_localization_method": "bearing_only_no_enu_position",
        "contributing_node_ids": (
            [str(item) for item in contributors]
            if isinstance(contributors, list)
            else []
        ),
        "bearing_deg": pos.get("azimuth_deg"),
        "elevation_deg": pos.get("elevation_deg"),
        "geo_hint_wgs84": {
            "lat": pos.get("lat"),
            "lon": pos.get("lon"),
            "alt_m": pos.get("alt_m"),
        },
        "notes": "operator fleet track has no validated local ENU target_state_3d",
    }


def _track_bearing_rays(track: Mapping[str, Any]) -> list[dict[str, Any]]:
    rays: list[dict[str, Any]] = []
    rows = track.get("provenance")
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        position = row.get("position")
        pos = position if isinstance(position, Mapping) else {}
        azimuth = pos.get("azimuth_deg")
        elevation = pos.get("elevation_deg")
        if azimuth is None and elevation is None:
            continue
        rays.append({
            "event_id": str(row.get("event_id", "") or ""),
            "node_id": str(row.get("node_id", "") or ""),
            "station_id": str(row.get("station_id", "") or ""),
            "timestamp_utc": str(row.get("timestamp_utc", "") or ""),
            "azimuth_deg": azimuth,
            "elevation_deg": elevation,
            "confidence": row.get("confidence"),
        })
    position = track.get("position")
    pos = position if isinstance(position, Mapping) else {}
    if not rays and (pos.get("azimuth_deg") is not None or pos.get("elevation_deg") is not None):
        rays.append({
            "event_id": str(track.get("last_event_id", "") or ""),
            "node_id": str(track.get("node_id", "") or ""),
            "timestamp_utc": str(track.get("updated_at", "") or ""),
            "azimuth_deg": pos.get("azimuth_deg"),
            "elevation_deg": pos.get("elevation_deg"),
            "confidence": track.get("confidence"),
        })
    return rays


def _track_evidence_refs(track: Mapping[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    evidence_rows = track.get("evidence_refs")
    for row in evidence_rows if isinstance(evidence_rows, list) else []:
        if isinstance(row, Mapping):
            refs.append(_deep_copy_dict(row))
    provenance_rows = track.get("provenance")
    for row in provenance_rows if isinstance(provenance_rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        event_id = str(row.get("event_id", "") or "")
        if event_id:
            refs.append({
                "kind": "fleet_event",
                "ref": event_id,
                "station_id": str(row.get("station_id", "") or ""),
            })
    return refs


def observation_state_from_fleet_track(
    track: Mapping[str, Any],
    *,
    local_frame_id: str = "operator_fleet_frame",
    observation_state_id: str | None = None,
) -> dict[str, Any]:
    """Build `observation_state.v1` from an operator fleet global-track row."""
    target_state = _track_target_state(track)
    return build_observation_state(
        track_id=str(track.get("global_track_id", "") or track.get("track_id", "") or ""),
        local_frame_id=str(target_state.get("local_frame_id") or local_frame_id),
        target_state_3d=target_state,
        operator_decision=_operator_decision(str(track.get("decision", "") or "")),
        target_class=_target_class(track.get("classification", "")),
        fused_confidence=float(track.get("confidence") or 0.0),
        localization_status=_localization_status_from_target_state(target_state),
        trajectory_prediction=(
            track.get("prediction")
            if isinstance(track.get("prediction"), Mapping)
            else {}
        ),
        bearing_rays=_track_bearing_rays(track),
        evidence_refs=_track_evidence_refs(track),
        observed_at_utc=str(track.get("updated_at", "") or _utc_now()),
        stale_after_utc=str(track.get("stale_after_utc", "") or track.get("updated_at", "") or _utc_now()),
        source_station_ids=[
            str(item)
            for item in track.get("contributors", [])
            if isinstance(track.get("contributors"), list) and str(item)
        ],
        observation_state_id=observation_state_id,
    )


def build_observation_state(
    *,
    track_id: str,
    local_frame_id: str,
    target_state_3d: Mapping[str, Any],
    operator_decision: str = "unreviewed",
    target_class: str = "unknown",
    fused_confidence: float = 0.0,
    localization_status: str = "unlocalized",
    trajectory_prediction: Mapping[str, Any] | None = None,
    bearing_rays: Sequence[Mapping[str, Any]] = (),
    evidence_refs: Sequence[Mapping[str, Any]] = (),
    observed_at_utc: str | None = None,
    stale_after_utc: str | None = None,
    source_station_ids: Sequence[str] | None = None,
    observation_state_id: str | None = None,
) -> dict[str, Any]:
    """Build an observation-state payload with no action-command fields."""
    observed = observed_at_utc or str(target_state_3d.get("timestamp_utc") or _utc_now())
    sources = list(source_station_ids) if source_station_ids is not None else _source_station_ids(target_state_3d)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_OBSERVATION_STATE,
        "observation_state_id": observation_state_id or str(uuid.uuid4()),
        "emitted_at_utc": _utc_now(),
        "track_id": track_id,
        "observed_at_utc": observed,
        "local_frame_id": local_frame_id,
        "source_station_ids": sorted({str(item) for item in sources if str(item)}),
        "operator_decision": operator_decision,
        "target_class": target_class,
        "fused_confidence": float(fused_confidence),
        "localization_status": localization_status,
        "target_state_3d": _deep_copy_dict(target_state_3d),
        "bearing_rays": _deep_copy_list(bearing_rays),
        "trajectory_prediction": _deep_copy_dict(trajectory_prediction or {}),
        "evidence_refs": _deep_copy_list(evidence_refs),
        "stale_after_utc": stale_after_utc or observed,
        "safety_mode": "observation_only",
        "safety_boundary": {
            "observation_only": True,
            "no_action_command": True,
            "no_launch_command": True,
            "no_intercept_geometry": True,
            "no_collision_course_guidance": True,
            "no_target_engagement": True,
        },
    }
    failures = validate_observation_state_shape(payload)
    if failures:
        raise ValueError("invalid observation_state.v1: " + ", ".join(failures))
    return payload


def observation_state_hash(payload: Mapping[str, Any]) -> str:
    """Return the canonical SHA-256 digest for an observation-state payload."""
    return sha256_hex(payload)


def validate_observation_state_shape(payload: Mapping[str, Any]) -> list[str]:
    """Return validation failures for the observation-only state contract."""
    failures: list[str] = []
    if payload.get("schema_version") != SCHEMA_OBSERVATION_STATE:
        failures.append("schema_version")
    for field in REQUIRED_FIELDS:
        if field not in payload:
            failures.append(f"missing:{field}")
    failures.extend(_prohibited_action_field_failures(payload))
    if payload.get("safety_mode") != "observation_only":
        failures.append("safety_mode_not_observation_only")
    if payload.get("operator_decision") not in OPERATOR_DECISIONS:
        failures.append("operator_decision_invalid")
    if payload.get("localization_status") not in LOCALIZATION_STATUSES:
        failures.append("localization_status_invalid")
    confidence = payload.get("fused_confidence")
    if not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
        failures.append("fused_confidence_invalid")
    if not isinstance(payload.get("target_state_3d"), Mapping):
        failures.append("target_state_3d_not_object")
    if not isinstance(payload.get("bearing_rays"), list):
        failures.append("bearing_rays_not_list")
    if not isinstance(payload.get("trajectory_prediction"), Mapping):
        failures.append("trajectory_prediction_not_object")
    if not isinstance(payload.get("evidence_refs"), list):
        failures.append("evidence_refs_not_list")
    safety = payload.get("safety_boundary")
    if not isinstance(safety, Mapping):
        failures.append("safety_boundary_not_object")
    else:
        for key in (
            "observation_only",
            "no_action_command",
            "no_launch_command",
            "no_intercept_geometry",
            "no_collision_course_guidance",
            "no_target_engagement",
        ):
            if safety.get(key) is not True:
                failures.append(f"safety_boundary_{key}")
    return failures


def _prohibited_action_field_failures(value: Any, path: str = "") -> list[str]:
    failures: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            field_path = key_text if not path else f"{path}.{key_text}"
            if key_text in PROHIBITED_ACTION_FIELDS:
                failures.append(f"prohibited_action_field:{field_path}")
            failures.extend(_prohibited_action_field_failures(nested, field_path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            failures.extend(_prohibited_action_field_failures(nested, f"{path}[{index}]"))
    return failures


@dataclass(frozen=True)
class ObservationState:
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        failures = validate_observation_state_shape(self.payload)
        if failures:
            raise ValueError("invalid observation_state.v1: " + ", ".join(failures))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ObservationState":
        return cls(payload=_deep_copy_dict(payload))

    def to_dict(self) -> dict[str, Any]:
        return _deep_copy_dict(self.payload)

    def to_canonical_json(self) -> str:
        return canonical_json(self.payload)
