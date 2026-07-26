"""Monotonic uncertainty envelope for Phase V prediction."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

SCHEMA_UNCERTAINTY_CONE = "prediction_uncertainty_cone.v1"


@dataclass(frozen=True)
class UncertaintyCone:
    sigma_initial_m: float = 1.5
    model_quality_factor: float = 1.0
    maneuver_factor: float = 1.0
    schema_version: str = SCHEMA_UNCERTAINTY_CONE

    def uncertainty_3sigma(self, t_offset_s: float) -> float:
        t = max(0.0, float(t_offset_s))
        base = max(0.1, self.sigma_initial_m)
        quality = max(0.1, self.model_quality_factor)
        maneuver = max(0.1, self.maneuver_factor)
        sigma = base * math.sqrt(1.0 + t) * quality * maneuver
        return 3.0 * sigma

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "sigma_initial_m": self.sigma_initial_m,
            "model_quality_factor": self.model_quality_factor,
            "maneuver_factor": self.maneuver_factor,
            "formula": "3*sigma_initial*sqrt(1+t)*model_quality_factor*maneuver_factor",
        }
