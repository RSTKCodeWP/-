"""Search-box estimation from passive trajectory predictions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cuas.prediction.types import SCHEMA_SEARCH_BOX, TrajectoryPrediction


@dataclass(frozen=True)
class SearchBox:
    estimated_terminal_intercept_time_s: float
    box_center_enu_m: tuple[float, float, float]
    box_extent_3sigma_m: tuple[float, float, float]
    confidence: float
    search_pattern_recommendation: str
    search_dwell_time_s: float
    expected_target_visual_size_pixels: int
    schema_version: str = SCHEMA_SEARCH_BOX

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "estimated_terminal_intercept_time_s": round(self.estimated_terminal_intercept_time_s, 3),
            "box_center_enu_m": [round(value, 6) for value in self.box_center_enu_m],
            "box_extent_3sigma_m": [round(value, 6) for value in self.box_extent_3sigma_m],
            "confidence": round(self.confidence, 6),
            "search_pattern_recommendation": self.search_pattern_recommendation,
            "search_dwell_time_s": round(self.search_dwell_time_s, 3),
            "expected_target_visual_size_pixels": self.expected_target_visual_size_pixels,
            "safety_boundary": {
                "sensor_search_only": True,
                "operator_review_required": True,
            },
        }


def estimate_search_box(
    prediction: TrajectoryPrediction,
    *,
    acquisition_latency_s: float = 5.0,
    search_speed_mps: float = 18.0,
) -> SearchBox:
    if not prediction.waypoints:
        raise ValueError("prediction has no waypoints")
    terminal_time = min(
        prediction.horizon_s - prediction.timestep_s,
        max(0.0, acquisition_latency_s + search_speed_mps * 0.0),
    )
    index = min(
        len(prediction.waypoints) - 1,
        max(0, int(terminal_time / prediction.timestep_s)),
    )
    waypoint = prediction.waypoints[index]
    extent = max(3.0, waypoint.cumulative_uncertainty_3sigma_m)
    pattern = "expanding_spiral" if extent < 80.0 else "lawnmower"
    return SearchBox(
        estimated_terminal_intercept_time_s=waypoint.t_offset_s,
        box_center_enu_m=waypoint.position_enu_m,
        box_extent_3sigma_m=(extent, extent, max(3.0, extent * 0.35)),
        confidence=max(0.0, min(1.0, prediction.prediction_confidence * 0.9)),
        search_pattern_recommendation=pattern,
        search_dwell_time_s=max(5.0, min(30.0, extent / max(1.0, search_speed_mps) * 3.0)),
        expected_target_visual_size_pixels=max(1, int(80.0 / (1.0 + extent / 20.0))),
    )
