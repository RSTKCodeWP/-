"""Pi5 hardware implementation of the gimbal `BenchIO` seam — bridges `fpv.gimbal.BenchRunner` (the proven
calibration + closed-loop orchestrator) to the REAL Pi5 head IMU (I2C 0x68) + PCA9685 servos (I2C 0x40),
with an OPTIONAL FT640 centroid source. The same captures that `SimBenchIO` runs in sim now run on hardware.

Dependency direction: seeker_core -> fpv (this implements fpv.gimbal.bench_runner.BenchIO). The module imports
cleanly off-Pi; CONSTRUCTING it touches I2C (needs smbus2 + the IMU/PCA9685 actually wired)."""
from __future__ import annotations

import math
import time
from typing import Callable, Optional

from seeker_core.pi5_io import (Pi5Config, imu_raw_to_si, rad_to_pulse_us,
                                make_i2c_imu_reader, make_pca9685_servo_writer)

_Vec3 = "tuple[float, float, float]"


class Pi5GimbalBenchIO:
    """Real Pi5 seam: head IMU + 2 PCA9685 servos (+ optional centroid). Implements fpv.gimbal BenchIO."""

    def __init__(self, cfg: Optional[Pi5Config] = None, dt: float = 1 / 200,
                 imu_addr: int = 0x68, pca_addr: int = 0x40,
                 centroid_fn: Optional[Callable[[], "Optional[tuple[float, float]]"]] = None) -> None:
        self.cfg = cfg or Pi5Config()
        self.dt = dt
        self._raw_imu = make_i2c_imu_reader(addr=imu_addr)          # wakes MPU, sets ±2000dps/±16g
        self._servo_write = make_pca9685_servo_writer(addr=pca_addr)  # raw smbus2 PWM
        self._centroid_fn = centroid_fn
        self._t0 = time.monotonic()
        self._pan = 0.0
        self._tilt = 0.0
        self.write_servo(0.0, 0.0)                                  # centre both axes on start

    def read_imu(self) -> "tuple[_Vec3, _Vec3]":
        for _ in range(6):                       # I2C is noisy near servos (Errno 121) — retry, don't crash
            try:
                return imu_raw_to_si(self._raw_imu(), self.cfg)
            except OSError:
                time.sleep(0.002)
        return ((0.0, 0.0, 0.0), (0.0, 0.0, 9.80665))

    def read_centroid(self) -> "Optional[tuple[float, float]]":
        return self._centroid_fn() if self._centroid_fn is not None else None

    def write_servo(self, pan_rad: float, tilt_rad: float) -> None:
        self._pan, self._tilt = pan_rad, tilt_rad
        self._w(self.cfg.pan_channel, rad_to_pulse_us(pan_rad, self.cfg.pan_sign, self.cfg))
        self._w(self.cfg.tilt_channel, rad_to_pulse_us(tilt_rad, self.cfg.tilt_sign, self.cfg))

    def _w(self, ch: int, us: float) -> None:
        for _ in range(6):
            try:
                self._servo_write(ch, us); return
            except OSError:
                time.sleep(0.002)

    def servo_feedback(self) -> "tuple[float, float]":
        return (float("nan"), float("nan"))       # DIY hobby servos: no position feedback

    def now_ns(self) -> int:
        return time.monotonic_ns()

    def tick(self) -> None:
        time.sleep(self.dt)                        # real-time pacing on hardware

    def safe(self) -> None:
        """Centre both servos (call on shutdown)."""
        try:
            self.write_servo(0.0, 0.0)
        except Exception:
            pass
