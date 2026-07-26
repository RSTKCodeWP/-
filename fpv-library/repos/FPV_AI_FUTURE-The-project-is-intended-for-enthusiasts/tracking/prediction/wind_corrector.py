"""Wind extraction and correction for Phase V prediction."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cuas.prediction.types import Vector3, vector3

SCHEMA_WIND_ESTIMATE = "prediction_wind_estimate.v1"


@dataclass(frozen=True)
class WindEstimate:
    vector_enu_mps: Vector3 = (0.0, 0.0, 0.0)
    uncertainty_mps: float = 0.0
    confidence: float = 0.0
    source: str = "default_zero"
    schema_version: str = SCHEMA_WIND_ESTIMATE

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "vector_enu_mps": [round(value, 6) for value in self.vector_enu_mps],
            "uncertainty_mps": round(self.uncertainty_mps, 6),
            "confidence": round(self.confidence, 6),
            "source": self.source,
        }


def _enu_vector_from_azimuth(speed_mps: float, azimuth_deg: float) -> Vector3:
    radians = math.radians(azimuth_deg)
    return (speed_mps * math.sin(radians), speed_mps * math.cos(radians), 0.0)


def _wind_from_speed_direction(
    speed_mps: float,
    direction_deg: float,
    *,
    convention: str = "meteorological_from",
) -> Vector3:
    """Convert speed/direction into ENU, where azimuth 0 deg points north."""
    normalized = convention.casefold().replace("-", "_")
    if normalized in {"meteorological", "meteorological_from", "from"}:
        azimuth_deg = (direction_deg + 180.0) % 360.0
    elif normalized in {"enu_toward", "toward", "azimuth_toward", "course"}:
        azimuth_deg = direction_deg
    else:
        raise ValueError(f"unknown wind direction convention: {convention}")
    return _enu_vector_from_azimuth(speed_mps, azimuth_deg)


def wind_from_payload(payload: dict[str, Any] | None) -> WindEstimate:
    if not isinstance(payload, dict):
        return WindEstimate()
    if "wind_vector_mps" in payload:
        return WindEstimate(
            vector_enu_mps=vector3(payload.get("wind_vector_mps")),
            uncertainty_mps=float(payload.get("wind_uncertainty_mps", 1.0) or 1.0),
            confidence=float(payload.get("confidence", 0.75) or 0.75),
            source=str(payload.get("source", "wind_vector_mps")),
        )
    if "vector_enu_mps" in payload:
        return WindEstimate(
            vector_enu_mps=vector3(payload.get("vector_enu_mps")),
            uncertainty_mps=float(payload.get("uncertainty_mps", 1.0) or 1.0),
            confidence=float(payload.get("confidence", 0.75) or 0.75),
            source=str(payload.get("source", "vector_enu_mps")),
        )
    maybe_forecast = payload.get("forecast")
    source_payload: dict[str, Any] = maybe_forecast if isinstance(maybe_forecast, dict) else payload
    speed = source_payload.get("wind_m_s", source_payload.get("wind_speed_mps", 0.0))
    direction = source_payload.get(
        "wind_direction_toward_deg",
        source_payload.get("wind_direction_deg", source_payload.get("wind_dir_deg", 0.0)),
    )
    convention = (
        "enu_toward"
        if "wind_direction_toward_deg" in source_payload
        else str(source_payload.get("wind_direction_convention", "meteorological_from"))
    )
    try:
        speed_f = float(speed)
        direction_f = float(direction)
        wind_vector = _wind_from_speed_direction(speed_f, direction_f, convention=convention)
    except (TypeError, ValueError):
        return WindEstimate()
    return WindEstimate(
        vector_enu_mps=wind_vector,
        uncertainty_mps=max(0.5, speed_f * 0.25),
        confidence=0.55,
        source=str(source_payload.get("source", "environment_context")),
    )


def load_wind_estimate(path: Path | None) -> WindEstimate:
    if path is None or not path.exists():
        return WindEstimate()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return wind_from_payload(payload if isinstance(payload, dict) else None)


def apply_wind_correction(velocity: Vector3, wind: WindEstimate, *, coupling: float = 0.25) -> Vector3:
    return (
        velocity[0] + wind.vector_enu_mps[0] * coupling,
        velocity[1] + wind.vector_enu_mps[1] * coupling,
        velocity[2] + wind.vector_enu_mps[2] * coupling,
    )
