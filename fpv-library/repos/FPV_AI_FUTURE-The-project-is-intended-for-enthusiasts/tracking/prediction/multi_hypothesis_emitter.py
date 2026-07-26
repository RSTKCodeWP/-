"""Emit separate trajectory hypotheses instead of hiding ambiguity."""

from __future__ import annotations

import math

from cuas.prediction.imm_blender import MODEL_DESCRIPTIONS
from cuas.prediction.types import PredictedWaypoint, TrajectoryHypothesis, Vector3, add3, scale3
from cuas.prediction.uncertainty_cone import UncertaintyCone
from cuas.prediction.wind_corrector import WindEstimate, apply_wind_correction


def _velocity_for_model(model: str, velocity: Vector3, wind: WindEstimate) -> Vector3:
    if model == "physics_informed":
        return apply_wind_correction(velocity, wind, coupling=0.35)
    if model == "constant_turn":
        return apply_wind_correction(velocity, wind, coupling=0.15)
    return apply_wind_correction(velocity, wind, coupling=0.20)


def waypoints_for_model(
    *,
    position: Vector3,
    velocity: Vector3,
    wind: WindEstimate,
    model: str,
    horizon_s: float,
    timestep_s: float,
    uncertainty: UncertaintyCone,
) -> tuple[PredictedWaypoint, ...]:
    count = int(horizon_s / timestep_s)
    rows: list[PredictedWaypoint] = []
    corrected_velocity = _velocity_for_model(model, velocity, wind)
    for index in range(count):
        t = index * timestep_s
        if model == "constant_turn":
            turn_rate = 0.025
            angle = turn_rate * t
            vx = corrected_velocity[0] * math.cos(angle) - corrected_velocity[1] * math.sin(angle)
            vy = corrected_velocity[0] * math.sin(angle) + corrected_velocity[1] * math.cos(angle)
            model_velocity = (vx, vy, corrected_velocity[2])
        elif model == "physics_informed":
            drag = max(0.65, 1.0 - 0.006 * t)
            model_velocity = scale3(corrected_velocity, drag)
        else:
            model_velocity = corrected_velocity
        rows.append(
            PredictedWaypoint(
                t_offset_s=t,
                position_enu_m=add3(position, scale3(model_velocity, t)),
                velocity_enu_mps=model_velocity,
                cumulative_uncertainty_3sigma_m=uncertainty.uncertainty_3sigma(t),
            )
        )
    return tuple(rows)


def emit_hypotheses(
    *,
    position: Vector3,
    velocity: Vector3,
    wind: WindEstimate,
    active_models: dict[str, float],
    horizon_s: float,
    timestep_s: float,
    uncertainty: UncertaintyCone,
) -> tuple[TrajectoryHypothesis, ...]:
    return tuple(
        TrajectoryHypothesis(
            hypothesis_id=f"hyp_{index + 1:02d}_{model}",
            weight=weight,
            motion_model=model,
            description=MODEL_DESCRIPTIONS.get(model, model),
            waypoints=waypoints_for_model(
                position=position,
                velocity=velocity,
                wind=wind,
                model=model,
                horizon_s=horizon_s,
                timestep_s=timestep_s,
                uncertainty=uncertainty,
            ),
        )
        for index, (model, weight) in enumerate(sorted(active_models.items(), key=lambda item: item[0]))
    )
