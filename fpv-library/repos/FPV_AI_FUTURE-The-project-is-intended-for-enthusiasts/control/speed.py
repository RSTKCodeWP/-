"""Configurable speed policy for FPV AI gate approach."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum


class SpeedMode(str, Enum):
    FIXED_SPEED = "FIXED_SPEED"
    ADAPTIVE_SPEED = "ADAPTIVE_SPEED"
    RACE_SPEED = "RACE_SPEED"


@dataclass(frozen=True)
class SpeedProfile:
    mode: SpeedMode
    min_mps: float
    default_mps: float
    max_mps: float
    operator_limit_mps: float
    adjustable_by_operator: bool = True

    def __post_init__(self) -> None:
        if self.min_mps < 0.0:
            raise ValueError("min_mps must be non-negative")
        if not self.min_mps <= self.default_mps <= self.max_mps:
            raise ValueError("speed profile must satisfy min <= default <= max")
        if not self.min_mps <= self.operator_limit_mps <= self.max_mps:
            raise ValueError("operator_limit_mps must be inside profile bounds")

    def with_operator_limit(self, limit_mps: float) -> "SpeedProfile":
        if not self.adjustable_by_operator:
            raise ValueError(f"{self.mode.value} is not operator adjustable")
        return replace(self, operator_limit_mps=_clamp(limit_mps, self.min_mps, self.max_mps))


class SpeedPolicy:
    """Resolve a safe command speed from mode, confidence, and operator limit."""

    def __init__(self, profiles: dict[SpeedMode, SpeedProfile]) -> None:
        missing = [mode.value for mode in SpeedMode if mode not in profiles]
        if missing:
            raise ValueError(f"missing speed profiles: {', '.join(missing)}")
        self._profiles = dict(profiles)

    @classmethod
    def default(cls) -> "SpeedPolicy":
        return cls({
            SpeedMode.FIXED_SPEED: SpeedProfile(
                mode=SpeedMode.FIXED_SPEED,
                min_mps=0.2,
                default_mps=1.5,
                max_mps=4.0,
                operator_limit_mps=1.5,
            ),
            SpeedMode.ADAPTIVE_SPEED: SpeedProfile(
                mode=SpeedMode.ADAPTIVE_SPEED,
                min_mps=0.2,
                default_mps=3.0,
                max_mps=8.0,
                operator_limit_mps=3.0,
            ),
            SpeedMode.RACE_SPEED: SpeedProfile(
                mode=SpeedMode.RACE_SPEED,
                min_mps=0.2,
                default_mps=6.0,
                max_mps=20.0,
                operator_limit_mps=6.0,
            ),
        })

    def profile(self, mode: SpeedMode) -> SpeedProfile:
        return self._profiles[mode]

    def with_operator_limit(self, mode: SpeedMode, limit_mps: float) -> "SpeedPolicy":
        profiles = dict(self._profiles)
        profiles[mode] = profiles[mode].with_operator_limit(limit_mps)
        return SpeedPolicy(profiles)

    def resolve_speed_mps(
        self,
        mode: SpeedMode,
        *,
        requested_mps: float | None = None,
        target_confidence: float = 1.0,
        tracking_state: str = "LOCKED",
        required_g: float | None = None,
        achievable_g: float | None = None,
        g_reserve_frac: float = 0.2,
    ) -> float:
        profile = self._profiles[mode]
        base = profile.default_mps if requested_mps is None else requested_mps
        speed = _clamp(base, profile.min_mps, min(profile.max_mps, profile.operator_limit_mps))
        if mode in {SpeedMode.ADAPTIVE_SPEED, SpeedMode.RACE_SPEED}:
            speed *= _confidence_scale(target_confidence)
        if tracking_state in {"DEGRADED", "PREDICTIVE_TRACK", "REACQUIRE", "HARD_LOST"}:
            speed *= 0.5
        # A3 g-budget coupling: hold a lateral-g RESERVE.  The bearing-rate-null lateral demand
        # scales with closing speed (required_g ~ lambda_dot*Vc*N), so when the demand eats into
        # the reserve we slow down -- a correction then stays inside the envelope instead of
        # saturating the actuator.  Omitting the budget (both None) is a no-op (backward compat).
        speed *= _g_budget_scale(required_g, achievable_g, g_reserve_frac)
        return round(_clamp(speed, profile.min_mps, min(profile.max_mps, profile.operator_limit_mps)), 3)


def _g_budget_scale(
    required_g: float | None,
    achievable_g: float | None,
    reserve_frac: float,
) -> float:
    """Speed multiplier that keeps the lateral-g demand below ``(1-reserve)*achievable``.

    Returns 1.0 when no g-budget is supplied or the demand already fits inside the reserve.
    Otherwise returns ``g_cap / required_g`` (< 1): since the lateral demand is ~linear in
    closing speed, scaling speed by this factor brings the demand to the reserve boundary.
    """
    if required_g is None or achievable_g is None:
        return 1.0
    if not (required_g > 0.0 and achievable_g > 0.0):
        return 1.0
    reserve_frac = _clamp(reserve_frac, 0.0, 0.9)
    g_cap = (1.0 - reserve_frac) * achievable_g
    if required_g <= g_cap:
        return 1.0
    return _clamp(g_cap / required_g, 0.1, 1.0)   # never throttle below 10% of resolved speed


def _confidence_scale(confidence: float) -> float:
    confidence = _clamp(confidence, 0.0, 1.0)
    if confidence >= 0.8:
        return 1.0
    if confidence >= 0.6:
        return 0.8
    if confidence >= 0.4:
        return 0.6
    return 0.4


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)
