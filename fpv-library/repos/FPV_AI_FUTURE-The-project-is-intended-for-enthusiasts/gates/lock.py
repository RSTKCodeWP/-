"""Deterministic gate-lock and reacquire state machine for FPV AI MVP."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

SCHEMA = "fpv_gate_lock.v1"


class TrackingState(str, Enum):
    NO_TARGET = "NO_TARGET"
    CANDIDATE = "CANDIDATE"
    LOCKED = "LOCKED"
    DEGRADED = "DEGRADED"
    PREDICTIVE_TRACK = "PREDICTIVE_TRACK"
    REACQUIRE = "REACQUIRE"
    RECOVERED = "RECOVERED"
    HARD_LOST = "HARD_LOST"


@dataclass(frozen=True)
class GateDetection:
    """One detector observation for a sports racing gate."""

    bbox: tuple[float, float, float, float]
    confidence: float
    frame_timestamp_ms: int
    class_name: str = "racing_gate"

    def __post_init__(self) -> None:
        if len(self.bbox) != 4:
            raise ValueError("bbox must contain x1, y1, x2, y2")
        x1, y1, x2, y2 = self.bbox
        if x2 <= x1 or y2 <= y1:
            raise ValueError("bbox must have positive width and height")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if self.frame_timestamp_ms < 0:
            raise ValueError("frame_timestamp_ms must be non-negative")

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @property
    def size(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return (x2 - x1, y2 - y1)


@dataclass(frozen=True)
class GateLockConfig:
    """Thresholds for lock, target memory, and reacquire behavior."""

    confidence_threshold: float = 0.65
    degraded_confidence_threshold: float = 0.35
    stable_frame_count: int = 3
    max_center_jump_px: float = 96.0
    predictive_track_ms: int = 500
    reacquire_track_ms: int = 1500

    def __post_init__(self) -> None:
        if not 0.0 <= self.degraded_confidence_threshold <= self.confidence_threshold <= 1.0:
            raise ValueError("confidence thresholds must satisfy degraded <= lock <= 1")
        if self.stable_frame_count <= 0:
            raise ValueError("stable_frame_count must be positive")
        if self.max_center_jump_px <= 0.0:
            raise ValueError("max_center_jump_px must be positive")
        if self.predictive_track_ms < 0 or self.reacquire_track_ms < self.predictive_track_ms:
            raise ValueError("reacquire_track_ms must be >= predictive_track_ms >= 0")


@dataclass(frozen=True)
class GateLockSnapshot:
    """Versioned gate-lock payload produced by the tracker."""

    target_locked: bool
    gate_bbox: tuple[float, float, float, float]
    gate_center_px: tuple[float, float]
    gate_size_px: tuple[float, float]
    confidence: float
    tracking_state: TrackingState
    recovery_state: TrackingState
    predicted_center_px: tuple[float, float]
    stable_frames: int
    frame_timestamp_ms: int
    recommended_action: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "target_locked": self.target_locked,
            "gate_bbox": [round(value, 3) for value in self.gate_bbox],
            "gate_center_px": [round(value, 3) for value in self.gate_center_px],
            "gate_size_px": [round(value, 3) for value in self.gate_size_px],
            "confidence": round(self.confidence, 6),
            "tracking_state": self.tracking_state.value,
            "recovery_state": self.recovery_state.value,
            "predicted_center_px": [round(value, 3) for value in self.predicted_center_px],
            "stable_frames": self.stable_frames,
            "frame_timestamp_ms": self.frame_timestamp_ms,
            "recommended_action": self.recommended_action,
        }


class GateLockTracker:
    """Small state machine for ring lock, prediction, and reacquire.

    It deliberately does not publish abort/failsafe decisions. Short visual loss
    moves into predictive/reacquire states so a higher layer can keep racing
    behavior separate from later safety policy.
    """

    def __init__(self, config: GateLockConfig | None = None) -> None:
        self.config = config or GateLockConfig()
        self._state = TrackingState.NO_TARGET
        self._stable_frames = 0
        self._last_detection: GateDetection | None = None
        self._previous_detection: GateDetection | None = None
        self._velocity_px_per_ms = (0.0, 0.0)

    def update(self, detection: GateDetection | None, *, frame_timestamp_ms: int | None = None) -> GateLockSnapshot:
        timestamp = self._resolve_timestamp(detection, frame_timestamp_ms)
        if detection is not None and detection.confidence >= self.config.confidence_threshold:
            return self._update_confirmed_detection(detection)
        if detection is not None and detection.confidence >= self.config.degraded_confidence_threshold:
            return self._update_degraded_detection(detection)
        return self._update_missing(timestamp)

    def _update_confirmed_detection(self, detection: GateDetection) -> GateLockSnapshot:
        previous_state = self._state
        if self._last_detection is None or self._is_temporally_stable(detection):
            self._stable_frames += 1
        else:
            self._stable_frames = 1
        self._remember_detection(detection)

        if self._stable_frames >= self.config.stable_frame_count:
            self._state = TrackingState.RECOVERED if previous_state in _RECOVERY_STATES else TrackingState.LOCKED
            action = "TRACK"
            locked = True
        else:
            self._state = TrackingState.CANDIDATE
            action = "HOLD"
            locked = False
        return self._snapshot(
            detection=detection,
            timestamp=detection.frame_timestamp_ms,
            state=self._state,
            recovery_state=TrackingState.NO_TARGET,
            locked=locked,
            action=action,
        )

    def _update_degraded_detection(self, detection: GateDetection) -> GateLockSnapshot:
        self._remember_detection(detection)
        self._state = TrackingState.DEGRADED
        return self._snapshot(
            detection=detection,
            timestamp=detection.frame_timestamp_ms,
            state=TrackingState.DEGRADED,
            recovery_state=TrackingState.DEGRADED,
            locked=False,
            action="PREDICT",
        )

    def _update_missing(self, timestamp: int) -> GateLockSnapshot:
        if self._last_detection is None:
            self._state = TrackingState.NO_TARGET
            self._stable_frames = 0
            return self._empty_snapshot(timestamp, TrackingState.NO_TARGET, "HOLD")

        age_ms = max(0, timestamp - self._last_detection.frame_timestamp_ms)
        if age_ms <= self.config.predictive_track_ms:
            self._state = TrackingState.PREDICTIVE_TRACK
            action = "PREDICT"
        elif age_ms <= self.config.reacquire_track_ms:
            self._state = TrackingState.REACQUIRE
            action = "REACQUIRE"
        else:
            self._state = TrackingState.HARD_LOST
            self._stable_frames = 0
            action = "CONSERVATIVE_RECOVERY"
        return self._snapshot(
            detection=None,
            timestamp=timestamp,
            state=self._state,
            recovery_state=self._state,
            locked=False,
            action=action,
        )

    def _remember_detection(self, detection: GateDetection) -> None:
        if self._last_detection is not None:
            dt = detection.frame_timestamp_ms - self._last_detection.frame_timestamp_ms
            if dt > 0:
                cx, cy = detection.center
                last_cx, last_cy = self._last_detection.center
                self._velocity_px_per_ms = ((cx - last_cx) / dt, (cy - last_cy) / dt)
        self._previous_detection = self._last_detection
        self._last_detection = detection

    def _is_temporally_stable(self, detection: GateDetection) -> bool:
        if self._last_detection is None:
            return True
        cx, cy = detection.center
        last_cx, last_cy = self._last_detection.center
        return abs(cx - last_cx) <= self.config.max_center_jump_px and abs(cy - last_cy) <= self.config.max_center_jump_px

    def _snapshot(
        self,
        *,
        detection: GateDetection | None,
        timestamp: int,
        state: TrackingState,
        recovery_state: TrackingState,
        locked: bool,
        action: str,
    ) -> GateLockSnapshot:
        source = detection or self._last_detection
        if source is None:
            return self._empty_snapshot(timestamp, state, action)
        center = source.center
        size = source.size
        predicted_center = center if detection is not None else self._predict_center(timestamp)
        return GateLockSnapshot(
            target_locked=locked,
            gate_bbox=source.bbox,
            gate_center_px=center,
            gate_size_px=size,
            confidence=source.confidence if detection is not None else _decayed_confidence(source.confidence, timestamp - source.frame_timestamp_ms),
            tracking_state=state,
            recovery_state=recovery_state,
            predicted_center_px=predicted_center,
            stable_frames=self._stable_frames,
            frame_timestamp_ms=timestamp,
            recommended_action=action,
        )

    def _empty_snapshot(self, timestamp: int, state: TrackingState, action: str) -> GateLockSnapshot:
        return GateLockSnapshot(
            target_locked=False,
            gate_bbox=(0.0, 0.0, 0.0, 0.0),
            gate_center_px=(0.0, 0.0),
            gate_size_px=(0.0, 0.0),
            confidence=0.0,
            tracking_state=state,
            recovery_state=state,
            predicted_center_px=(0.0, 0.0),
            stable_frames=self._stable_frames,
            frame_timestamp_ms=timestamp,
            recommended_action=action,
        )

    def _predict_center(self, timestamp: int) -> tuple[float, float]:
        if self._last_detection is None:
            return (0.0, 0.0)
        age_ms = max(0, timestamp - self._last_detection.frame_timestamp_ms)
        center_x, center_y = self._last_detection.center
        vx, vy = self._velocity_px_per_ms
        return (center_x + vx * age_ms, center_y + vy * age_ms)

    @staticmethod
    def _resolve_timestamp(detection: GateDetection | None, frame_timestamp_ms: int | None) -> int:
        if detection is not None:
            return detection.frame_timestamp_ms
        if frame_timestamp_ms is None:
            raise ValueError("frame_timestamp_ms is required when detection is None")
        if frame_timestamp_ms < 0:
            raise ValueError("frame_timestamp_ms must be non-negative")
        return frame_timestamp_ms


def _decayed_confidence(confidence: float, age_ms: int) -> float:
    if age_ms <= 0:
        return confidence
    return max(0.0, confidence * max(0.0, 1.0 - age_ms / 2000.0))


_RECOVERY_STATES = {
    TrackingState.DEGRADED,
    TrackingState.PREDICTIVE_TRACK,
    TrackingState.REACQUIRE,
    TrackingState.HARD_LOST,
}
