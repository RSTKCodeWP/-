"""Gimbal controller tests: it REJECTS base disturbance and TRACKS a moving target (IMU on the head).

This is the honest measurement that was missing: does a gyro-stabilised 2-servo gimbal keep the target
centred while the airframe yanks? Compared against open-loop (no control) to prove the rejection.
"""
from __future__ import annotations

import math

import numpy as np

from fpv.gimbal.controller import GimbalConfig, GimbalController
from fpv.gimbal.plant import GimbalPlant


def _run(base_rate_yaw, base_rate_pitch, target_yaw, target_pitch, *, control=True,
         dt=1 / 500, T=2.0, cfg=None, plant_kwargs=None, seed=0):
    ctrl = GimbalController(cfg)
    plant = GimbalPlant(**(plant_kwargs or {}))
    rng = np.random.default_rng(seed)
    obs = plant.step(0, 0, target_yaw(0), target_pitch(0), 0, 0, dt, rng)
    errs, infov = [], []
    n = int(T / dt)
    for i in range(n):
        t = i * dt
        if control:
            out = ctrl.step(obs["gyro"], obs["accel"], obs["centroid"], dt)
            pan_sp, tilt_sp = out.pan_setpoint_rad, out.tilt_setpoint_rad
        else:
            pan_sp = tilt_sp = 0.0
        obs = plant.step(base_rate_yaw(t), base_rate_pitch(t), target_yaw(t), target_pitch(t),
                         pan_sp, tilt_sp, dt, rng)
        if t > 0.3:                                   # let the loop settle before scoring
            errs.append(obs["pointing_err"])
            infov.append(1.0 if obs["in_fov"] else 0.0)
    return dict(max_err_deg=math.degrees(max(errs)), rms_err_deg=math.degrees(float(np.sqrt(np.mean(np.square(errs))))),
                in_fov=float(np.mean(infov)))


def test_rejects_base_disturbance():
    """Aggressive airframe yaw/pitch motion (excursion beyond the FOV), target fixed at boresight."""
    byaw = lambda t: 5.0 * math.sin(2 * math.pi * 0.8 * t)     # ±57° excursion -> out of FOV open-loop
    bpit = lambda t: 3.0 * math.sin(2 * math.pi * 0.6 * t)
    zero = lambda t: 0.0
    open_loop = _run(byaw, bpit, zero, zero, control=False)
    closed = _run(byaw, bpit, zero, zero, control=True)
    assert open_loop["in_fov"] < 0.5, "sanity: uncontrolled head should lose the target"
    assert closed["in_fov"] > 0.99, f"controlled head must hold the target, in_fov={closed['in_fov']}"
    assert closed["max_err_deg"] < open_loop["max_err_deg"] / 5.0, \
        f"rejection weak: closed {closed['max_err_deg']:.2f}° vs open {open_loop['max_err_deg']:.2f}°"
    print(f"\n[gimbal] base-disturbance rejection: open-loop max {open_loop['max_err_deg']:.1f}° -> "
          f"closed {closed['max_err_deg']:.2f}° (rms {closed['rms_err_deg']:.2f}°), in_fov {closed['in_fov']*100:.0f}%")


def test_tracks_moving_target():
    """No base motion, target slews across; the gimbal must centre it and keep it in FOV."""
    zero = lambda t: 0.0
    tyaw = lambda t: math.radians(15.0) * math.sin(2 * math.pi * 0.5 * t)   # ±15° target weave
    r = _run(zero, zero, tyaw, zero, control=True)
    assert r["in_fov"] > 0.99 and r["rms_err_deg"] < 6.0, r
    print(f"\n[gimbal] tracking a ±15° weaving target: rms err {r['rms_err_deg']:.2f}°, in_fov {r['in_fov']*100:.0f}%")


def test_accel_corrects_los_rate_bias():
    """A pitch-gyro bias offsets the reported LOS rate (= a steering bias for guidance). The accel
    reference (IMU on the head) estimates and removes the bias, cleaning the LOS rate."""
    from fpv.gimbal.controller import GimbalConfig
    rate = 0.05                                          # true target pitch rate (rad/s)

    def los_rate_bias(leveling: bool) -> float:
        ctrl = GimbalController(GimbalConfig(accel_leveling=leveling))
        plant = GimbalPlant(gyro_bias_rps=0.02)          # 0.02 rad/s pitch-gyro bias
        rng = np.random.default_rng(0)
        dt = 1 / 500
        tp = lambda t: rate * t
        obs = plant.step(0, 0, 0.0, tp(0.0), 0, 0, dt, rng)
        errs = []
        for i in range(int(3.0 / dt)):
            t = i * dt
            out = ctrl.step(obs["gyro"], obs["accel"], obs["centroid"], dt)
            obs = plant.step(0, 0, 0.0, tp(t), out.pan_setpoint_rad, out.tilt_setpoint_rad, dt, rng)
            if t > 1.0 and obs["in_fov"]:
                errs.append(out.los_rate_pitch - rate)   # reported LOS rate vs the true target rate
        return abs(float(np.mean(errs)))

    off, on = los_rate_bias(False), los_rate_bias(True)
    assert on < off / 3.0 and on < 0.005, f"accel should clean the LOS-rate bias: on {on:.4f} vs off {off:.4f}"
    print(f"\n[gimbal] LOS-rate bias from a 0.02 rad/s gyro bias: no-accel {off:.4f} -> accel-leveled {on:.4f} rad/s")


def test_combined_shake_and_maneuver_with_noise():
    """Base shake + maneuvering target + gyro noise + servo lag — still holds the target."""
    byaw = lambda t: 2.5 * math.sin(2 * math.pi * 4.0 * t)
    bpit = lambda t: 1.5 * math.sin(2 * math.pi * 3.0 * t + 1.0)
    tyaw = lambda t: math.radians(10.0) * math.sin(2 * math.pi * 0.8 * t)
    zero = lambda t: 0.0
    r = _run(byaw, bpit, tyaw, zero, control=True,
             plant_kwargs=dict(servo_tau_s=0.015, servo_rate_max_dps=400.0, gyro_noise_rps=0.01))
    assert r["in_fov"] > 0.98, f"lost the target under combined load: {r}"
    print(f"\n[gimbal] shake+maneuver+noise: rms err {r['rms_err_deg']:.2f}°, max {r['max_err_deg']:.2f}°, "
          f"in_fov {r['in_fov']*100:.0f}%")
