"""Visual-servo pilot mapping gate-lock snapshots to bounded AI commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fpv_ai.betaflight_link.commands import AICommand
from fpv_ai.control.speed import SpeedMode, SpeedPolicy


@dataclass(frozen=True)
class PilotConfig:
    frame_width_px: float = 640.0
    frame_height_px: float = 480.0
    yaw_gain: float = 0.75
    roll_gain: float = 0.35
    pitch_gain: float = 0.85
    throttle_base: float = 0.5
    throttle_vertical_gain: float = 0.25
    recovery_pitch_scale: float = 0.5

    def __post_init__(self) -> None:
        if self.frame_width_px <= 0.0 or self.frame_height_px <= 0.0:
            raise ValueError("frame dimensions must be positive")
        if self.throttle_base < 0.0 or self.throttle_base > 1.0:
            raise ValueError("throttle_base must be in [0, 1]")
        if not 0.0 <= self.recovery_pitch_scale <= 1.0:
            raise ValueError("recovery_pitch_scale must be in [0, 1]")


class GateVisualPilot:
    """Convert gate-lock state into pilot-like roll/pitch/yaw/throttle commands."""

    def __init__(self, *, config: PilotConfig | None = None, speed_policy: SpeedPolicy | None = None) -> None:
        self.config = config or PilotConfig()
        self.speed_policy = speed_policy or SpeedPolicy.default()

    def command_from_lock(
        self,
        lock_payload: dict[str, Any],
        *,
        speed_mode: SpeedMode,
        sequence_id: int,
        requested_speed_mps: float | None = None,
    ) -> AICommand:
        state = str(lock_payload["tracking_state"])
        confidence = float(lock_payload["confidence"])
        timestamp_ms = int(lock_payload["frame_timestamp_ms"])
        target_center = _point(lock_payload["gate_center_px"])
        predicted_center = _point(lock_payload["predicted_center_px"])
        control_center = predicted_center if state in {"PREDICTIVE_TRACK", "REACQUIRE"} else target_center

        resolved_speed = self.speed_policy.resolve_speed_mps(
            speed_mode,
            requested_mps=requested_speed_mps,
            target_confidence=confidence,
            tracking_state=state,
        )
        roll_cmd, pitch_cmd, yaw_rate_cmd, throttle_cmd = self._servo_commands(
            center_px=control_center,
            resolved_speed_mps=resolved_speed,
            speed_mode=speed_mode,
            tracking_state=state,
        )
        return AICommand.bounded(
            roll_cmd=roll_cmd,
            pitch_cmd=pitch_cmd,
            yaw_rate_cmd=yaw_rate_cmd,
            throttle_cmd=throttle_cmd,
            target_confidence=confidence,
            target_state=state,
            recovery_state=str(lock_payload["recovery_state"]),
            speed_mode=speed_mode,
            resolved_speed_mps=resolved_speed,
            sequence_id=sequence_id,
            timestamp_ms=timestamp_ms,
        )

    def _servo_commands(
        self,
        *,
        center_px: tuple[float, float],
        resolved_speed_mps: float,
        speed_mode: SpeedMode,
        tracking_state: str,
    ) -> tuple[float, float, float, float]:
        cfg = self.config
        if tracking_state in {"NO_TARGET", "HARD_LOST"}:
            return (0.0, 0.0, 0.0, 0.0)

        error_x = (center_px[0] - cfg.frame_width_px / 2.0) / (cfg.frame_width_px / 2.0)
        error_y = (center_px[1] - cfg.frame_height_px / 2.0) / (cfg.frame_height_px / 2.0)
        speed_profile = self.speed_policy.profile(speed_mode)
        speed_fraction = resolved_speed_mps / max(speed_profile.max_mps, 1e-6)
        pitch_scale = cfg.recovery_pitch_scale if tracking_state in {"DEGRADED", "PREDICTIVE_TRACK", "REACQUIRE"} else 1.0

        roll_cmd = error_x * cfg.roll_gain
        yaw_rate_cmd = error_x * cfg.yaw_gain
        pitch_cmd = speed_fraction * cfg.pitch_gain * pitch_scale
        throttle_cmd = cfg.throttle_base - error_y * cfg.throttle_vertical_gain
        return (
            _clamp(roll_cmd, -1.0, 1.0),
            _clamp(pitch_cmd, -1.0, 1.0),
            _clamp(yaw_rate_cmd, -1.0, 1.0),
            _clamp(throttle_cmd, 0.0, 1.0),
        )


def _point(value: Any) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("point payload must be a list of two numbers")
    return (float(value[0]), float(value[1]))


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)
