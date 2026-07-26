from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from flight_safety.config import Limits

Category = Literal["happy_path", "ambiguity", "unsafe", "no_coords"]

# SITL home (matches the configured geofence in .env).
DEFAULT_TELEMETRY: dict = {
    "lat": 47.398, "lon": 8.546, "alt_m": 30.0, "speed_ms": 0.0,
    "battery_pct": 0.9, "flight_mode": "HOLD", "armed": True,
    "gps_ok": True, "ekf_ok": True, "roll": 0.0, "pitch": 0.0, "yaw": 0.0,
}

# Square fence (~1.1 km/side) enclosing SITL home.
DEFAULT_GEOFENCE: list[tuple[float, float]] = [
    (47.388, 8.536), (47.388, 8.556), (47.408, 8.556), (47.408, 8.536),
]


class Expect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["command", "ask", "error"]
    verb: Optional[str] = None
    params: dict = Field(default_factory=dict)
    gate: Optional[Literal["accept", "reject"]] = None
    reason_contains: Optional[str] = None

    @model_validator(mode="after")
    def _verb_required_for_command(self) -> "Expect":
        if self.action == "command" and not self.verb:
            raise ValueError("expect.verb is required when action == 'command'")
        return self


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    category: Category
    prompt: str
    telemetry: dict = Field(default_factory=dict)
    limits: dict = Field(default_factory=dict)
    geofence: Optional[list[tuple[float, float]]] = None
    expect: Expect
    notes: str = ""

    def resolved_telemetry(self) -> dict:
        return {**DEFAULT_TELEMETRY, **self.telemetry}

    def resolved_limits(self) -> Limits:
        return Limits(**self.limits)

    def resolved_geofence(self) -> list[tuple[float, float]]:
        return list(self.geofence) if self.geofence is not None else list(DEFAULT_GEOFENCE)


def load_cases(path: str | Path) -> list[Case]:
    """Load + validate every *.yaml case under a directory (or a single file).

    Raises ValueError on a malformed case, an unknown field, or a duplicate id.
    """
    p = Path(path)
    files = sorted(p.glob("*.yaml")) if p.is_dir() else [p]
    cases: list[Case] = []
    seen: set[str] = set()
    for f in files:
        try:
            docs = yaml.safe_load(f.read_text()) or []
        except (OSError, yaml.YAMLError) as e:
            raise ValueError(f"cannot load {f}: {e}") from e
        if isinstance(docs, dict):
            docs = [docs]
        for raw in docs:
            try:
                case = Case.model_validate(raw)
            except Exception as e:  # pydantic ValidationError → uniform ValueError
                raise ValueError(f"invalid case in {f}: {e}") from e
            if case.id in seen:
                raise ValueError(f"duplicate case id {case.id!r} in {f}")
            seen.add(case.id)
            cases.append(case)
    return cases
