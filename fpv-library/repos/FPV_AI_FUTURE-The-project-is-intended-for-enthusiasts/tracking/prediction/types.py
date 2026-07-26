"""Shared Phase V trajectory prediction data contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SCHEMA_WAYPOINT = "predicted_waypoint.v1"
SCHEMA_HYPOTHESIS = "trajectory_hypothesis.v1"
SCHEMA_PREDICTION = "trajectory_prediction.v1"
SCHEMA_SEARCH_BOX = "search_box.v1"
SCHEMA_LAUNCH_RECOMMENDATION = "launch_recommendation.v1"

Vector3 = tuple[float, float, float]


def vector3(value: Any, *, default: Vector3 = (0.0, 0.0, 0.0)) -> Vector3:
    if not isinstance(value, (list, tuple)):
        return default
    values = list(value)[:3]
    values.extend([0.0] * (3 - len(values)))
    try:
        return (float(values[0]), float(values[1]), float(values[2]))
    except (TypeError, ValueError):
        return default


def add3(left: Vector3, right: Vector3) -> Vector3:
    return (left[0] + right[0], left[1] + right[1], left[2] + right[2])


def scale3(value: Vector3, scale: float) -> Vector3:
    return (value[0] * scale, value[1] * scale, value[2] * scale)


@dataclass(frozen=True)
class PredictedWaypoint:
    t_offset_s: float
    position_enu_m: Vector3
    velocity_enu_mps: Vector3
    cumulative_uncertainty_3sigma_m: float
    schema_version: str = SCHEMA_WAYPOINT

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "t_offset_s": round(self.t_offset_s, 3),
            "position_enu_m": [round(v, 6) for v in self.position_enu_m],
            "velocity_enu_mps": [round(v, 6) for v in self.velocity_enu_mps],
            "cumulative_uncertainty_3sigma_m": round(
                self.cumulative_uncertainty_3sigma_m,
                6,
            ),
        }


@dataclass(frozen=True)
class TrajectoryHypothesis:
    hypothesis_id: str
    weight: float
    motion_model: str
    description: str
    waypoints: tuple[PredictedWaypoint, ...]
    schema_version: str = SCHEMA_HYPOTHESIS

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "hypothesis_id": self.hypothesis_id,
            "weight": round(self.weight, 6),
            "motion_model": self.motion_model,
            "description": self.description,
            "waypoints": [waypoint.to_dict() for waypoint in self.waypoints],
        }


@dataclass(frozen=True)
class TrajectoryPrediction:
    horizon_s: float
    timestep_s: float
    primary_motion_model: str
    waypoints: tuple[PredictedWaypoint, ...]
    multiple_hypotheses: tuple[TrajectoryHypothesis, ...]
    wind_estimate_enu_mps: Vector3
    wind_uncertainty_mps: float
    prediction_confidence: float
    deteriorates_after_s: float
    evidence_class: str = "synthetic_smoke"
    schema_version: str = SCHEMA_PREDICTION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "horizon_s": self.horizon_s,
            "timestep_s": self.timestep_s,
            "primary_motion_model": self.primary_motion_model,
            "waypoints": [waypoint.to_dict() for waypoint in self.waypoints],
            "multiple_hypotheses": [
                hypothesis.to_dict() for hypothesis in self.multiple_hypotheses
            ],
            "wind_estimate_enu_mps": [round(v, 6) for v in self.wind_estimate_enu_mps],
            "wind_uncertainty_mps": round(self.wind_uncertainty_mps, 6),
            "prediction_confidence": round(self.prediction_confidence, 6),
            "deteriorates_after_s": round(self.deteriorates_after_s, 3),
            "evidence_class": self.evidence_class,
            "truth_boundary": {
                "sense_only": True,
                "no_engagement_or_jamming": True,
                "prediction_is_not_field_proof": self.evidence_class != "field_proof_candidate",
            },
        }


def validate_prediction(prediction: TrajectoryPrediction) -> list[str]:
    errors: list[str] = []
    expected = int(prediction.horizon_s / prediction.timestep_s)
    if len(prediction.waypoints) != expected:
        errors.append("waypoint_count")
    if prediction.waypoints and abs(prediction.waypoints[0].t_offset_s) > 0.001:
        errors.append("first_waypoint_time")
    for left, right in zip(prediction.waypoints, prediction.waypoints[1:]):
        dt = right.t_offset_s - left.t_offset_s
        if abs(dt - prediction.timestep_s) > 0.001:
            errors.append("waypoint_timestep")
            break
        if right.cumulative_uncertainty_3sigma_m + 1e-9 < left.cumulative_uncertainty_3sigma_m:
            errors.append("uncertainty_monotonic")
            break
    weight_sum = sum(hypothesis.weight for hypothesis in prediction.multiple_hypotheses)
    if abs(weight_sum - 1.0) > 0.001:
        errors.append("hypothesis_weight_sum")
    return errors
