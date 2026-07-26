"""Bench runner — one orchestrator for the gimbal bench, identical code in SIM and on HARDWARE.

You implement ONE seam, `BenchIO` (read IMU, read the FT640 centroid, write the 2 servos, tick the
clock), for your specific hardware (IMU over SPI/I2C, servos over PWM, centroid from the FT640
detector). `SimBenchIO` here implements the same seam against the gimbal plant, so the whole runner is
proven before you touch hardware. The runner drives the three characterization captures + the closed-
loop stabilization test, all logging the `datalog` CSV format.

    # on hardware:  io = MyHardwareIO(...);  BenchRunner(io, GimbalController()).run_all("bench_logs/")
    # in sim:       python3 -m fpv.gimbal.bench_runner --sim
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional, Protocol

import numpy as np

from fpv.gimbal.controller import GimbalController
from fpv.gimbal.datalog import GimbalLogger, GimbalLogRecord, characterize
from fpv.gimbal.plant import GimbalPlant

_NAN = float("nan")
_Vec3 = tuple[float, float, float]


class BenchIO(Protocol):
    """The single hardware seam. Implement this for your IMU + servos + FT640 centroid + clock."""
    dt: float
    def read_imu(self) -> tuple[_Vec3, _Vec3]: ...          # (gyro rad/s, accel m/s^2), head IMU
    def read_centroid(self) -> Optional[tuple[float, float]]: ...   # FT640 target centroid px, or None
    def write_servo(self, pan_rad: float, tilt_rad: float) -> None: ...
    def servo_feedback(self) -> tuple[float, float]: ...    # (pan, tilt) angle fb rad, or (nan, nan)
    def now_ns(self) -> int: ...
    def tick(self) -> None: ...                             # advance the sim one step / sleep dt on HW


class SimBenchIO:
    """Sim implementation of BenchIO against the gimbal plant (target + base-disturbance functions)."""

    def __init__(self, target_fn=None, base_fn=None, dt: float = 1 / 500, seed: int = 0, **plant_kwargs):
        self.dt = dt
        self.plant = GimbalPlant(**plant_kwargs)
        self.target_fn = target_fn or (lambda t: (0.0, 0.0))
        self.base_fn = base_fn or (lambda t: (0.0, 0.0))
        self.rng = np.random.default_rng(seed)
        self.t = 0.0
        self._pan_sp = 0.0
        self._tilt_sp = 0.0
        self._obs = self._advance()

    def _advance(self) -> dict:
        ty, tp = self.target_fn(self.t)
        by, bp = self.base_fn(self.t)
        return self.plant.step(by, bp, ty, tp, self._pan_sp, self._tilt_sp, self.dt, self.rng)

    def read_imu(self) -> tuple[_Vec3, _Vec3]:
        return self._obs["gyro"], self._obs["accel"]

    def read_centroid(self) -> Optional[tuple[float, float]]:
        return self._obs["centroid"]

    def write_servo(self, pan_rad: float, tilt_rad: float) -> None:
        self._pan_sp, self._tilt_sp = pan_rad, tilt_rad

    def servo_feedback(self) -> tuple[float, float]:
        return self.plant.servo_pan, self.plant.servo_tilt

    def now_ns(self) -> int:
        return int(self.t * 1e9)

    def tick(self) -> None:
        self._obs = self._advance()
        self.t += self.dt


class BenchRunner:
    def __init__(self, io: BenchIO, controller: Optional[GimbalController] = None) -> None:
        self.io = io
        self.controller = controller

    def _record(self, log: GimbalLogger, pan_cmd: float, tilt_cmd: float) -> Optional[tuple[float, float]]:
        (gx, gy, gz), (ax, ay, az) = self.io.read_imu()
        cen = self.io.read_centroid()
        pf, tf = self.io.servo_feedback()
        cx, cy = cen if cen else (_NAN, _NAN)
        log.add(GimbalLogRecord(self.io.now_ns(), gx, gy, gz, ax, ay, az,
                                pan_cmd, tilt_cmd, pf, tf, cx, cy, cen is not None))
        return cen

    def capture_static(self, seconds: float = 15.0) -> GimbalLogger:
        """Servos NOT driven, gimbal still -> gyro bias & noise, centroid jitter on a fixed target."""
        log = GimbalLogger()
        self.io.write_servo(0.0, 0.0)
        for _ in range(int(seconds / self.io.dt)):
            self._record(log, 0.0, 0.0)
            self.io.tick()
        return log

    def capture_servo_step(self, step_rad: float = math.radians(30.0), seconds: float = 1.5) -> GimbalLogger:
        """Direct open-loop servo step -> real servo max slew rate + lag + tracking error."""
        log = GimbalLogger()
        for i in range(int(seconds / self.io.dt)):
            sp = step_rad if i * self.io.dt > 0.1 else 0.0
            self.io.write_servo(sp, sp)
            self._record(log, sp, sp)
            self.io.tick()
        return log

    def run_closed_loop(self, seconds: float = 10.0) -> GimbalLogger:
        """Closed-loop stabilize+track (shake the base by hand on HW) -> stabilization residual."""
        if self.controller is None:
            raise ValueError("run_closed_loop needs a GimbalController")
        log = GimbalLogger()
        for _ in range(int(seconds / self.io.dt)):
            (g, a) = self.io.read_imu()
            cen = self.io.read_centroid()
            out = self.controller.step(g, a, cen, self.io.dt)
            self.io.write_servo(out.pan_setpoint_rad, out.tilt_setpoint_rad)
            self._record(log, out.pan_setpoint_rad, out.tilt_setpoint_rad)
            self.io.tick()
        return log

    def run_all(self, out_dir: str | Path) -> dict:
        """Run the three captures, save CSVs, and return the characterization summary of each."""
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        summary = {}
        for name, log in (("static", self.capture_static()),
                          ("servo_step", self.capture_servo_step())):
            log.save_csv(out / f"{name}.csv")
            summary[name] = characterize(log.records)
        if self.controller is not None:
            log = self.run_closed_loop()
            log.save_csv(out / "closed_loop.csv")
            summary["closed_loop"] = characterize(log.records)
        return summary


def _sim_demo() -> dict:
    shake = lambda t: (5.0 * math.sin(2 * math.pi * 0.8 * t), 3.0 * math.sin(2 * math.pi * 0.6 * t))
    target = lambda t: (math.radians(10.0) * math.sin(2 * math.pi * 0.5 * t), 0.0)
    io = SimBenchIO(target_fn=target, base_fn=shake, gyro_bias_rps=0.02, gyro_noise_rps=0.01,
                    servo_rate_max_dps=400.0, servo_tau_s=0.015)
    return BenchRunner(io, GimbalController()).run_all("/tmp/gimbal_bench")


if __name__ == "__main__":
    import json
    print(json.dumps(_sim_demo(), indent=2, default=str))
