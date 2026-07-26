"""Data-log harness tests: round-trip CSV, and characterize() recovers known gyro/servo parameters.

Validates that when the owner logs real hardware in this format, the calibration numbers come back
correctly (so the controller/plant can be tuned from the log).
"""
from __future__ import annotations

import numpy as np

from fpv.gimbal.controller import GimbalConfig, GimbalController
from fpv.gimbal.datalog import GimbalLogger, GimbalLogRecord, characterize, load_csv
from fpv.gimbal.plant import GimbalPlant


def _log_run(target_yaw, target_pitch, *, gyro_bias=0.0, gyro_noise=0.0, servo_rate_dps=500.0,
             control=True, T=1.5, dt=1 / 500) -> GimbalLogger:
    ctrl = GimbalController(GimbalConfig())
    plant = GimbalPlant(gyro_bias_rps=gyro_bias, gyro_noise_rps=gyro_noise, servo_rate_max_dps=servo_rate_dps)
    rng = np.random.default_rng(0)
    log = GimbalLogger()
    obs = plant.step(0, 0, target_yaw(0), target_pitch(0), 0, 0, dt, rng)
    for i in range(int(T / dt)):
        t = i * dt
        out = ctrl.step(obs["gyro"], obs["accel"], obs["centroid"], dt)
        pan_sp, tilt_sp = (out.pan_setpoint_rad, out.tilt_setpoint_rad) if control else (0.0, 0.0)
        obs = plant.step(0, 0, target_yaw(t), target_pitch(t), pan_sp, tilt_sp, dt, rng)
        gx, gy, gz = obs["gyro"]; ax, ay, az = obs["accel"]
        cx, cy = obs["centroid"] if obs["centroid"] else (float("nan"), float("nan"))
        log.add(GimbalLogRecord(t_ns=int(t * 1e9), gx=gx, gy=gy, gz=gz, ax=ax, ay=ay, az=az,
                                pan_cmd=out.pan_setpoint_rad, tilt_cmd=out.tilt_setpoint_rad,
                                pan_fb=plant.servo_pan, tilt_fb=plant.servo_tilt,
                                cx=cx, cy=cy, in_fov=obs["in_fov"]))
    return log


def test_csv_roundtrip(tmp_path):
    log = _log_run(lambda t: 0.0, lambda t: 0.0, T=0.2)
    p = tmp_path / "gimbal.csv"
    log.save_csv(p)
    back = load_csv(p)
    assert len(back) == len(log.records)
    a, b = log.records[5], back[5]
    assert a.t_ns == b.t_ns and abs(a.gx - b.gx) < 1e-9 and abs(a.pan_cmd - b.pan_cmd) < 1e-9


def test_characterize_recovers_gyro_stats():
    """Static hold with a known pitch-gyro bias + noise -> characterize() recovers them."""
    off = lambda t: 1.0                       # target out of FOV; servos NOT driven -> truly static
    log = _log_run(off, off, gyro_bias=0.02, gyro_noise=0.01, control=False, T=2.0)
    c = characterize(log.records)
    assert abs(c["gyro_bias_rps"][1] - 0.02) < 0.008, c        # gy bias ~ 0.02
    assert 0.004 < c["gyro_noise_rps"][1] < 0.03, c            # gy noise ~ 0.01
    print(f"\n[datalog] recovered gyro bias {c['gyro_bias_rps'][1]:+.4f} rps, noise "
          f"{c['gyro_noise_rps'][1]:.4f} rps @ {c['rate_hz']:.0f} Hz")


def test_characterize_recovers_servo_rate():
    """Open-loop servo step (command the servo directly, as on hardware) -> recovered rate ~ limit."""
    plant = GimbalPlant(servo_rate_max_dps=400.0)
    rng = np.random.default_rng(0)
    dt = 1 / 500
    log = GimbalLogger()
    for i in range(int(1.0 / dt)):
        t = i * dt
        sp = 0.5 if t > 0.1 else 0.0                 # direct 0.5 rad (29°) step -> saturates the servo
        obs = plant.step(0, 0, 1.0, 1.0, sp, sp, dt, rng)     # target out of FOV; servo commanded directly
        gx, gy, gz = obs["gyro"]; ax, ay, az = obs["accel"]
        log.add(GimbalLogRecord(t_ns=int(t * 1e9), gx=gx, gy=gy, gz=gz, ax=ax, ay=ay, az=az,
                                pan_cmd=sp, tilt_cmd=sp, pan_fb=plant.servo_pan, tilt_fb=plant.servo_tilt,
                                cx=float("nan"), cy=float("nan"), in_fov=False))
    c = characterize(log.records)
    assert 300.0 < c["servo_pan_rate_max_dps"] < 450.0, c
    print(f"\n[datalog] recovered servo pan max rate {c['servo_pan_rate_max_dps']:.0f} dps "
          f"(plant limit 400), track rms {c.get('servo_pan_track_rms_deg')}°")
