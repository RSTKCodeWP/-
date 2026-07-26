"""Safety-clamped launch recommendation contract for Phase V."""

from __future__ import annotations

from typing import Any

from cuas.prediction.search_box_estimator import SearchBox
from cuas.prediction.types import SCHEMA_LAUNCH_RECOMMENDATION, TrajectoryPrediction


def disabled_launch_recommendation(
    prediction: TrajectoryPrediction,
    search_box: SearchBox,
    *,
    reason: str = "sense_only_project_boundary",
) -> dict[str, Any]:
    """Return schema-compatible disabled recommendation without intercept parameters."""
    return {
        "schema_version": SCHEMA_LAUNCH_RECOMMENDATION,
        "status": "DISABLED",
        "recommendation_kind": "sensor_search_only",
        "reason": reason,
        "recommended_launch_window_s": None,
        "recommended_climb_altitude_agl_m": None,
        "recommended_initial_heading_deg": None,
        "recommended_initial_climb_rate_mps": None,
        "recommended_cruise_speed_mps": None,
        "estimated_time_to_intercept_s": None,
        "estimated_intercept_position_enu_m": None,
        "estimated_intercept_geometry": "not_computed_sense_only",
        "estimated_closing_velocity_mps": None,
        "fuel_required_estimate_pct": None,
        "abort_after_s_if_no_acquisition": search_box.search_dwell_time_s,
        "max_safe_intercept_altitude_agl_m": None,
        "deconfliction_passing_aircraft_ids": [],
        "weather_acceptable": None,
        "weather_constraints": ["not_evaluated_for_launch"],
        "allowed_next_action": "operator_review_sensor_search_box",
        "prohibited_actions": [
            "autonomous_launch",
            "intercept_geometry",
            "collision_course_guidance",
            "jamming",
            "spoofing",
            "target_engagement",
        ],
        "source_prediction_schema": prediction.schema_version,
        "source_search_box_schema": search_box.schema_version,
    }
