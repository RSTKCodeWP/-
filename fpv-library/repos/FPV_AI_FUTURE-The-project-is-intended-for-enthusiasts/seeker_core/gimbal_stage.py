"""seeker_core gimbal stage — adapts the proven fpv.gimbal.GimbalController to the core's GimbalStage.

Physics port (not a rewrite): the gyro-stabilized 2-servo controller (IMU on the head) plugs in as the
core's gimbal stage. Input: the dominant detection centroid + the head IMU. Output: a `GimbalState`
carrying the pan/tilt servo setpoints (for the GIMBAL_AZ/EL actuator channels) and the clean inertial
LOS rate from the head gyro. With this, the seeker head is a single sensor-in → actuator-out module.
"""
from __future__ import annotations

from typing import Optional

from fpv.gimbal.controller import GimbalConfig, GimbalController

from seeker_core.contracts import Detections, GimbalState, ImuSample


def _dominant_centroid(detections: Detections) -> Optional[tuple[float, float]]:
    if not detections.blobs:
        return None
    b = max(detections.blobs, key=lambda bl: (bl.area_px, bl.snr))
    return b.centroid_px


class GimbalControllerStage:
    """Wraps fpv.gimbal.GimbalController. Handles a missing IMU (zero gyro / gravity-down accel)."""

    def __init__(self, cfg: GimbalConfig | None = None) -> None:
        self.ctrl = GimbalController(cfg or GimbalConfig())

    def step(self, detections: Detections, imu: Optional[ImuSample], dt: float) -> GimbalState:
        gyro = imu.gyro_rps if imu is not None else (0.0, 0.0, 0.0)
        accel = imu.accel_mps2 if imu is not None else (0.0, 0.0, 9.81)
        out = self.ctrl.step(gyro, accel, _dominant_centroid(detections), dt)
        return GimbalState(pan_setpoint_rad=out.pan_setpoint_rad, tilt_setpoint_rad=out.tilt_setpoint_rad,
                           los_rate_yaw=out.los_rate_yaw, los_rate_pitch=out.los_rate_pitch,
                           tracking=out.tracking, provenance=detections.provenance)
