"""2-axis (pan/tilt) gyro-stabilized gimbal controller for the seeker head.

THE CHEAP-GENIUS IDEA: the IMU is on the GIMBAL (the moving head), so the gyro measures the camera's
INERTIAL angular rate directly. That makes base-disturbance rejection almost free — a rate-mode loop
drives the camera's inertial rate to a desired tracking rate, so the airframe's aggressive terminal
rotation (which shows up in the head gyro) is rejected mechanically. And the SAME head gyro IS the
clean inertial LOS rate the guidance needs — no strapdown de-rotation, the gimbal removed the body
motion physically.

Two servos: PAN (yaw, CW/CCW) and TILT (pitch, up/down). No roll axis — a point target is roll-
invariant. Decoupled small-angle control per axis. Portable reference (Python) → Zynq PS / a small MCU.

Loop (per axis):
  desired_rate = k_track · angle(centroid offset from image centre)   # slew boresight onto the target
  servo_rate   = clamp( k_loop · (desired_rate − head_gyro) )         # drive camera inertial rate → desired
The head_gyro term is the whole trick: base motion enters the gyro and is cancelled; with no target the
desired rate is 0, so the head simply holds inertial (pure stabilisation).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GimbalConfig:
    f_px: float = 730.0            # FT640 focal length (px): (512/2)/tan(19.3°) ≈ 730
    img_w: int = 640
    img_h: int = 512
    k_track: float = 12.0          # centroid-offset angle → desired slew rate (1/s)
    k_loop: float = 20.0           # rate-loop gain (drives head gyro → desired rate); higher = stiffer,
                                   # too high + servo lag -> a limit-cycle buzz (tune to the real servo)
    servo_rate_max_dps: float = 500.0
    deadband_px: float = 1.0
    accel_leveling: bool = True    # accel gives an absolute tilt reference -> corrects gyro pitch-bias drift
    comp_alpha: float = 0.995      # complementary weight (gyro vs accel) on the tilt axis
    k_bias: float = 2.0            # gyro pitch-bias learning rate (1/s)
    # ANTI-WINDUP: clamp the integrated servo setpoint to the mechanical travel so a saturated command
    # or a corrupt reference cannot wind the setpoint past the physical stops (measured on real hardware:
    # without this the tilt integrator ran away to -210°). None = no clamp (default; bit-identical).
    pan_limit_rad: "tuple[float, float] | None" = None    # (min, max) mechanical pan travel
    tilt_limit_rad: "tuple[float, float] | None" = None   # (min, max) mechanical tilt travel


@dataclass(frozen=True)
class GimbalOutput:
    pan_setpoint_rad: float        # servo angle setpoints (relative to the base)
    tilt_setpoint_rad: float
    pan_rate_cmd: float            # commanded servo rates (rad/s)
    tilt_rate_cmd: float
    los_rate_yaw: float            # inertial LOS rate for guidance (= head gyro; clean when centred)
    los_rate_pitch: float
    tracking: bool


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


class GimbalController:
    """Rate-mode, gyro-stabilised, centroid-tracking 2-axis gimbal. Deterministic; unit-testable."""

    def __init__(self, cfg: GimbalConfig | None = None) -> None:
        self.cfg = cfg or GimbalConfig()
        self.pan = 0.0
        self.tilt = 0.0
        self._tilt_est = 0.0             # complementary absolute-pitch estimate (accel-referenced)
        self._gy_bias = 0.0             # estimated gyro pitch bias (learned from the accel innovation)

    def step(self, gyro_xyz: tuple[float, float, float], accel_xyz: tuple[float, float, float],
             centroid_px: Optional[tuple[float, float]], dt: float) -> GimbalOutput:
        c = self.cfg
        _, gy, gz = gyro_xyz                 # camera looks +x: gy = pitch rate, gz = yaw rate
        # accel-complementary tilt: correct the gyro pitch bias so it does not drift the held attitude
        # (and cleans the LOS-rate the guidance rides). Yaw has no gravity reference — the tracking loop
        # (target-referenced) corrects yaw drift instead.
        gy_use = gy - self._gy_bias
        if c.accel_leveling:
            ax, _ay, az = accel_xyz
            acc_pitch = math.atan2(-ax, az) if (ax or az) else self._tilt_est
            pred = self._tilt_est + gy_use * dt
            innov = acc_pitch - pred
            self._tilt_est = pred + (1.0 - c.comp_alpha) * innov
            self._gy_bias -= c.k_bias * innov * dt      # nudge bias to null the accel innovation
        if centroid_px is not None:
            ex = centroid_px[0] - c.img_w / 2.0
            ey = centroid_px[1] - c.img_h / 2.0
            if abs(ex) < c.deadband_px:
                ex = 0.0
            if abs(ey) < c.deadband_px:
                ey = 0.0
            des_yaw = c.k_track * math.atan2(ex, c.f_px)      # target right (x+) → pan +
            des_pitch = -c.k_track * math.atan2(ey, c.f_px)   # target down (y+) → tilt −
            tracking = True
        else:
            des_yaw = des_pitch = 0.0                         # no target → hold inertial (stabilise only)
            tracking = False

        rmax = math.radians(c.servo_rate_max_dps)
        pan_rate = _clamp(c.k_loop * (des_yaw - gz), -rmax, rmax)          # reject base + track
        tilt_rate = _clamp(c.k_loop * (des_pitch - gy_use), -rmax, rmax)   # bias-corrected pitch
        self.pan += pan_rate * dt
        self.tilt += tilt_rate * dt
        # anti-windup: never integrate the setpoint past the mechanical travel
        if c.pan_limit_rad is not None:
            self.pan = _clamp(self.pan, c.pan_limit_rad[0], c.pan_limit_rad[1])
        if c.tilt_limit_rad is not None:
            self.tilt = _clamp(self.tilt, c.tilt_limit_rad[0], c.tilt_limit_rad[1])
        # LOS rate for guidance = the head's inertial rate (gyro, bias-corrected on pitch) once centred
        return GimbalOutput(self.pan, self.tilt, pan_rate, tilt_rate, gz, gy_use, tracking)
