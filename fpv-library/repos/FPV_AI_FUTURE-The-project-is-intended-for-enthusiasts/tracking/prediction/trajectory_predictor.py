"""Passive trajectory prediction engine for Phase V."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cuas.prediction.imm_blender import active_motion_models, normalize_imm_posterior
from cuas.prediction.multi_hypothesis_emitter import emit_hypotheses
from cuas.prediction.types import (
    TrajectoryPrediction,
    Vector3,
    validate_prediction,
    vector3,
)
from cuas.prediction.uncertainty_cone import UncertaintyCone
from cuas.prediction.wind_corrector import WindEstimate


@dataclass(frozen=True)
class TrackKinematics:
    position_enu_m: Vector3
    velocity_enu_mps: Vector3
    observation_count: int
    confidence: float


def _observation_position(row: dict[str, Any]) -> Vector3:
    for key in ("position_enu_m", "position_m", "position", "position_xyz"):
        if key in row:
            return vector3(row.get(key))
    centroid = row.get("centroid_xy")
    if isinstance(centroid, (list, tuple)) and len(centroid) >= 2:
        return (float(centroid[0]), float(centroid[1]), 0.0)
    return (0.0, 0.0, 0.0)


def estimate_track_kinematics(track: dict[str, Any]) -> TrackKinematics:
    observations_raw = track.get("observations")
    observations = [
        row for row in observations_raw
        if isinstance(row, dict)
    ] if isinstance(observations_raw, list) else []
    if len(observations) >= 2:
        rows = sorted(observations, key=lambda row: float(row.get("timestamp", 0.0) or 0.0))
        prev = rows[-2]
        cur = rows[-1]
        p_prev = _observation_position(prev)
        p_cur = _observation_position(cur)
        dt = max(1e-6, float(cur.get("timestamp", 0.0) or 0.0) - float(prev.get("timestamp", 0.0) or 0.0))
        velocity = (
            (p_cur[0] - p_prev[0]) / dt,
            (p_cur[1] - p_prev[1]) / dt,
            (p_cur[2] - p_prev[2]) / dt,
        )
        confidence = float(track.get("confidence", track.get("track_confidence", 0.72)) or 0.72)
        return TrackKinematics(
            position_enu_m=p_cur,
            velocity_enu_mps=velocity,
            observation_count=len(rows),
            confidence=max(0.0, min(1.0, confidence)),
        )
    initial_state = track.get("initial_state")
    if isinstance(initial_state, (list, tuple)) and len(initial_state) >= 6:
        return TrackKinematics(
            position_enu_m=vector3(initial_state[:3]),
            velocity_enu_mps=vector3(initial_state[3:6]),
            observation_count=1,
            confidence=float(track.get("confidence", 0.55) or 0.55),
        )
    return TrackKinematics(
        position_enu_m=vector3(track.get("position_enu_m", (0.0, 0.0, 0.0))),
        velocity_enu_mps=vector3(track.get("velocity_enu_mps", (0.0, 0.0, 0.0))),
        observation_count=0,
        confidence=float(track.get("confidence", 0.35) or 0.35),
    )


class TrajectoryPredictor:
    def predict(
        self,
        track: dict[str, Any],
        wind: WindEstimate,
        *,
        horizon_s: float = 30.0,
        timestep_s: float = 0.1,
    ) -> TrajectoryPrediction:
        if horizon_s <= 0.0:
            raise ValueError("horizon_s must be positive")
        if timestep_s <= 0.0:
            raise ValueError("timestep_s must be positive")
        kinematics = estimate_track_kinematics(track)
        posterior = normalize_imm_posterior(track)
        active = active_motion_models(posterior)
        maneuver_factor = 1.0 + max(0.0, float(track.get("maneuver_score", 0.0) or 0.0))
        model_quality = max(0.75, 1.35 - kinematics.confidence)
        uncertainty = UncertaintyCone(
            sigma_initial_m=max(1.0, wind.uncertainty_mps + 0.25 * max(0, 5 - kinematics.observation_count)),
            model_quality_factor=model_quality,
            maneuver_factor=maneuver_factor,
        )
        hypotheses = emit_hypotheses(
            position=kinematics.position_enu_m,
            velocity=kinematics.velocity_enu_mps,
            wind=wind,
            active_models=active,
            horizon_s=horizon_s,
            timestep_s=timestep_s,
            uncertainty=uncertainty,
        )
        primary = max(hypotheses, key=lambda item: item.weight)
        prediction = TrajectoryPrediction(
            horizon_s=horizon_s,
            timestep_s=timestep_s,
            primary_motion_model=primary.motion_model,
            waypoints=primary.waypoints,
            multiple_hypotheses=hypotheses,
            wind_estimate_enu_mps=wind.vector_enu_mps,
            wind_uncertainty_mps=wind.uncertainty_mps,
            prediction_confidence=max(0.0, min(1.0, kinematics.confidence * (0.75 + 0.25 * wind.confidence))),
            deteriorates_after_s=min(horizon_s, max(5.0, horizon_s * kinematics.confidence)),
            evidence_class=str(track.get("evidence_class", "synthetic_smoke")),
        )
        errors = validate_prediction(prediction)
        if errors:
            raise ValueError(f"invalid trajectory prediction: {errors}")
        return prediction
