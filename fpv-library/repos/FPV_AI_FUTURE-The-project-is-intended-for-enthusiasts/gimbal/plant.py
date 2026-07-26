"""2-axis gimbal PLANT for validating the controller: base (airframe) disturbance + servo dynamics.

Per axis (decoupled small-angle): camera_inertial_angle = base_angle + servo_angle. The head IMU (on
the camera) reads the inertial rate = d(camera)/dt — so an airframe rotation (base) shows up in the
gyro exactly as on the real head. The servo tracks the controller's setpoint with a deg/s rate limit +
first-order lag. This is what lets us measure BASE-DISTURBANCE REJECTION honestly, before hardware.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


def _servo(cur: float, setpoint: float, rate_max_dps: float, tau: float, dt: float) -> float:
    """First-order servo toward `setpoint`, capped by a slew-rate limit."""
    move = (setpoint - cur) * (min(1.0, dt / (tau + dt)) if tau > 0 else 1.0)
    rmax = math.radians(rate_max_dps) * dt
    return cur + max(-rmax, min(rmax, move))


@dataclass
class GimbalPlant:
    f_px: float = 730.0
    img_w: int = 640
    img_h: int = 512
    servo_rate_max_dps: float = 500.0
    servo_tau_s: float = 0.01
    gyro_noise_rps: float = 0.0
    gyro_bias_rps: float = 0.0            # constant pitch-gyro bias (what the accel must correct)
    base_yaw: float = 0.0
    base_pitch: float = 0.0
    servo_pan: float = 0.0
    servo_tilt: float = 0.0
    _prev_cam_yaw: float = field(default=0.0, repr=False)
    _prev_cam_pitch: float = field(default=0.0, repr=False)

    def step(self, base_rate_yaw: float, base_rate_pitch: float, target_yaw: float, target_pitch: float,
             pan_setpoint: float, tilt_setpoint: float, dt: float, rng=None) -> dict:
        self.servo_pan = _servo(self.servo_pan, pan_setpoint, self.servo_rate_max_dps, self.servo_tau_s, dt)
        self.servo_tilt = _servo(self.servo_tilt, tilt_setpoint, self.servo_rate_max_dps, self.servo_tau_s, dt)
        self.base_yaw += base_rate_yaw * dt
        self.base_pitch += base_rate_pitch * dt
        cam_yaw = self.base_yaw + self.servo_pan
        cam_pitch = self.base_pitch + self.servo_tilt
        gz = (cam_yaw - self._prev_cam_yaw) / dt              # head gyro = camera inertial rate
        gy = (cam_pitch - self._prev_cam_pitch) / dt
        self._prev_cam_yaw = cam_yaw
        self._prev_cam_pitch = cam_pitch
        gy += self.gyro_bias_rps                              # constant pitch-gyro bias
        if self.gyro_noise_rps and rng is not None:
            gz += rng.normal(0, self.gyro_noise_rps)
            gy += rng.normal(0, self.gyro_noise_rps)
        err_yaw = target_yaw - cam_yaw                        # pointing error → pixel offset
        err_pitch = target_pitch - cam_pitch
        cx = self.img_w / 2.0 + math.tan(err_yaw) * self.f_px
        cy = self.img_h / 2.0 - math.tan(err_pitch) * self.f_px
        in_fov = (0 <= cx < self.img_w) and (0 <= cy < self.img_h)
        centroid: Optional[tuple[float, float]] = (cx, cy) if in_fov else None
        g = 9.81                                              # accel reflects the camera's absolute tilt
        accel = (-g * math.sin(cam_pitch), 0.0, g * math.cos(cam_pitch))
        return dict(gyro=(0.0, gy, gz), accel=accel, centroid=centroid,
                    pointing_err=math.hypot(err_yaw, err_pitch), in_fov=in_fov,
                    cam_yaw=cam_yaw, cam_pitch=cam_pitch)
