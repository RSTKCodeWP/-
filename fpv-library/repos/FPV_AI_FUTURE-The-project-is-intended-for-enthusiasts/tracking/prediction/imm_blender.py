"""IMM posterior normalization for Phase V prediction."""

from __future__ import annotations

from typing import Any

DEFAULT_POSTERIOR = {
    "constant_velocity": 0.62,
    "constant_turn": 0.26,
    "physics_informed": 0.12,
}
MODEL_DESCRIPTIONS = {
    "constant_velocity": "continues current passive velocity estimate",
    "constant_turn": "continues with bounded lateral turn uncertainty",
    "physics_informed": "continues with wind-corrected passive physics drift",
}


def normalize_imm_posterior(track: dict[str, Any]) -> dict[str, float]:
    raw = track.get("imm_posterior") or track.get("model_posterior") or DEFAULT_POSTERIOR
    if not isinstance(raw, dict):
        raw = DEFAULT_POSTERIOR
    posterior: dict[str, float] = {}
    for key, value in raw.items():
        if key not in MODEL_DESCRIPTIONS:
            continue
        try:
            posterior[str(key)] = max(0.0, float(value))
        except (TypeError, ValueError):
            continue
    if not posterior:
        posterior = dict(DEFAULT_POSTERIOR)
    total = sum(posterior.values())
    if total <= 1e-12:
        posterior = dict(DEFAULT_POSTERIOR)
        total = sum(posterior.values())
    return {key: value / total for key, value in posterior.items()}


def active_motion_models(
    posterior: dict[str, float],
    *,
    min_weight: float = 0.15,
) -> dict[str, float]:
    active = {key: value for key, value in posterior.items() if value >= min_weight}
    if not active:
        best = max(posterior.items(), key=lambda item: item[1])
        active = {best[0]: best[1]}
    total = sum(active.values())
    return {key: value / total for key, value in active.items()}
