"""seeker_system — the runnable device program: SeekerSupervisor wired to real perception + Pi hardware.

This is the version-controlled entry point for the whole product (the coherent boot→home→ready→
stabilise→track spine), replacing the ad-hoc script that lived only on the Pi. It composes:

  perception   SeekerGuidancePipeline (the proven detect->track) behind the Perceiver protocol
  gimbal/IMU   seeker_core.pi5_io  (head IMU + 2 servos, with calibration)  -- on the Pi
  body yaw     an injected sender (route to the FC MSP-override yaw channel; default: safe logger)
  annunciator  audible READY/LOCK/FAULT (injected buzzer hook; default: console)

Run modes:
  python3 -m fpv_ai.seeker_system --sim         # mock hardware, synthetic frame -- smoke test anywhere
  python3 -m fpv_ai.seeker_system --calib gimbal_calib.json   # real Pi hardware (IMU/servos/camera)

Body actuation stays DEFAULT-DENY: the supervisor only commands body yaw in TRACK, and even then the
FC's arming + the manual override toggle decide whether it reaches a motor. `--send-yaw` must be given
explicitly to route yaw to the FC; without it, yaw is logged only.
"""
from __future__ import annotations

import argparse
import time
from typing import Callable, Optional

import numpy as np

from fpv.guidance.pipeline import SeekerGuidancePipeline
from fpv.seeker.geometry import ft640_intrinsics
from fpv.fpv_ai.supervisor import (SeekerSupervisor, SupervisorConfig, SupervisorPorts,
                                   SupervisorStatus, SystemState)


class PipelinePerceiver:
    """Adapts SeekerGuidancePipeline to the supervisor's Perceiver protocol (the REAL perception)."""

    def __init__(self, intrinsics=None) -> None:
        self.pipe = SeekerGuidancePipeline(intrinsics=intrinsics or ft640_intrinsics())
        self._t = 0.0

    def designate(self, cx: float, cy: float) -> None:
        self.pipe.designate((cx, cy))

    def locate(self, frame, dt: float):
        # Gimbal-stabilised head -> the image is already inertially steady, so run perception with
        # gyro=0 (the gimbal removed body motion mechanically; no strapdown de-rotation needed here).
        self._t += dt
        out = self.pipe.step(self._t, frame, (0.0, 0.0, 0.0), dt)
        return out.centroid_px, out.tracking_state


def console_annunciator(tone: str) -> None:
    marks = {"ready": "🔔 READY — initialised, gimbal homed, stabilising",
             "lock": "🔒 LOCK", "fault": "⛔ FAULT"}
    print(marks.get(tone, tone), flush=True)


# ── real Pi hardware wiring (lazy imports; Pi-only) ────────────────────────────────────────────────
def build_pi_ports(calib_path: Optional[str], *, send_yaw: Optional[Callable[[float], None]] = None,
                   read_activation: Optional[Callable[[], bool]] = None,
                   fc_port: Optional[str] = None,
                   annunciate: Callable[[str], None] = console_annunciator) -> SupervisorPorts:
    """Assemble SupervisorPorts from the real Pi head hardware (IMU + 2 servos + FT640)."""
    import os
    from seeker_core.pi5_io import (Pi5Config, Pi5Imu, Pi5Camera, load_calibration,
                                    make_i2c_imu_reader, make_pca9685_servo_writer,
                                    pan_pulse_us, tilt_pulse_us)
    # Prefer the CORRECTED calibration (real MPU6500 scales, accel gravity->Z remap, fixed pan limit)
    # found on the real head 2026-07-21; fall back to whatever was given.
    if calib_path is None and os.path.exists("gimbal_calib_fixed.json"):
        calib_path = "gimbal_calib_fixed.json"
    cfg = load_calibration(calib_path) if calib_path else Pi5Config()
    imu = Pi5Imu(cfg, make_i2c_imu_reader())
    write_us = make_pca9685_servo_writer()
    cam = Pi5Camera(cfg)

    # Measure the gyro bias at startup (head still) and subtract it every read — otherwise the rate
    # integrator drifts (measured on hardware). ~1 s of samples.
    import numpy as _np
    _s = [imu.read(time.monotonic_ns()) for _ in range(100)]
    _g = [s.gyro_rps for s in _s if s is not None]
    _bias = tuple(_np.mean(_g, axis=0)) if _g else (0.0, 0.0, 0.0)

    def read_imu():
        s = imu.read(time.monotonic_ns())
        if s is None:
            return None
        g = (s.gyro_rps[0] - _bias[0], s.gyro_rps[1] - _bias[1], s.gyro_rps[2] - _bias[2])
        return (g, s.accel_mps2)

    def read_frame():
        f = cam.read()
        return f.pixels if f is not None else None

    def write_gimbal(pan_rad: float, tilt_rad: float) -> None:
        write_us(cfg.pan_channel, pan_pulse_us(pan_rad, cfg))
        write_us(cfg.tilt_channel, tilt_pulse_us(tilt_rad, cfg))

    # Field: an FC MSP link gives the REAL toggle + body-yaw hooks (un-stubs both). Opened only if a
    # port is given; the FC's own MSP_OVERRIDE mode + arming still gate whether yaw reaches a motor.
    if fc_port is not None and (send_yaw is None or read_activation is None):
        from fpv.fpv_ai.fc_link import FcLink
        fc = FcLink(fc_port)
        read_activation = read_activation or fc.read_activation
        send_yaw = send_yaw or fc.send_body_yaw

    return SupervisorPorts(
        read_imu=read_imu, read_frame=read_frame, write_gimbal=write_gimbal,
        send_body_yaw=(send_yaw or (lambda y: None)),
        annunciate=annunciate, perceiver=PipelinePerceiver(),
        # DEFAULT-DENY: no toggle source given -> Sokol never self-activates. The field build injects
        # the real MSP AUX toggle reader here; without it the supervisor only ever stabilises.
        read_activation=(read_activation or (lambda: False)),
    )


def hardware_gimbal_config(calib_path: Optional[str] = None):
    """GimbalConfig tuned on the REAL head (2026-07-21): gentle gains, accel-leveling (valid after the
    gravity->Z remap in gimbal_calib_fixed.json), and the mechanical limits fed to the controller's
    anti-windup so a saturated/corrupt command can never wind the setpoint past the stops."""
    import os
    from fpv.gimbal.controller import GimbalConfig
    from seeker_core.pi5_io import load_calibration, Pi5Config
    if calib_path is None and os.path.exists("gimbal_calib_fixed.json"):
        calib_path = "gimbal_calib_fixed.json"
    c = load_calibration(calib_path) if calib_path else Pi5Config()
    return GimbalConfig(k_loop=6.0, servo_rate_max_dps=120.0, accel_leveling=True, comp_alpha=0.98,
                        k_bias=1.0, pan_limit_rad=c.pan_limit_rad, tilt_limit_rad=c.tilt_limit_rad)


# ── sim wiring (mock hardware; runs anywhere) ──────────────────────────────────────────────────────
def build_sim_ports(*, warm_target: bool = True,
                    read_activation: Optional[Callable[[], bool]] = None) -> SupervisorPorts:
    """Mock ports with a synthetic thermal frame (optional warm blob near centre) — smoke test off-Pi."""
    def read_frame():
        f = np.full((512, 640), 4096, np.uint16)
        if warm_target:
            f[248:264, 312:328] = 40000          # a warm blob on the boresight (toggle acquires it)
        return f

    return SupervisorPorts(
        read_imu=lambda: ((0.0, 0.0, 0.0), (0.0, 0.0, 9.80665)),
        read_frame=read_frame,
        write_gimbal=lambda p, t: None,
        send_body_yaw=lambda y: None,
        annunciate=console_annunciator,
        perceiver=PipelinePerceiver(),
        read_activation=(read_activation or (lambda: False)),
        now=time.monotonic,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Seeker system — the device supervisor (boot→home→ready→track)")
    ap.add_argument("--sim", action="store_true", help="mock hardware + synthetic frame (runs anywhere)")
    ap.add_argument("--calib", default=None, help="gimbal_calib.json for the real Pi head")
    ap.add_argument("--seconds", type=float, default=None, help="run duration (default: forever)")
    ap.add_argument("--designate", type=float, nargs=2, metavar=("CX", "CY"), default=None,
                    help="auto-designate a target pixel after READY (bench demo)")
    ap.add_argument("--hz", type=float, default=100.0)
    ap.add_argument("--toggle-at", type=float, default=None,
                    help="--sim: flip the activation TOGGLE up this many seconds after start (pilot's switch)")
    ap.add_argument("--fc", default=None,
                    help="FC MSP serial (e.g. /dev/ttyACM0) -> real toggle + body-yaw over MSP_OVERRIDE")
    ap.add_argument("--strapdown", action="store_true",
                    help="Sokol WITHOUT the gimbal (test article): body-fixed camera, no servos/homing/stabilise")
    args = ap.parse_args()

    active = [False]                              # the field TOGGLE state (flipped by --toggle-at in sim)
    t_start = time.monotonic()
    if args.sim:
        ports = build_sim_ports(read_activation=lambda: active[0])
        cfg = SupervisorConfig(loop_hz=args.hz)
    else:
        ports = build_pi_ports(args.calib, fc_port=args.fc)   # --fc wires the real toggle + body-yaw
        cfg = SupervisorConfig(loop_hz=args.hz, gimbal=hardware_gimbal_config(args.calib))
    sup = SeekerSupervisor(ports, cfg)
    designated = False
    last_state = None

    def on_status(st: SupervisorStatus) -> None:
        nonlocal designated, last_state
        if args.toggle_at is not None and not active[0] and time.monotonic() - t_start >= args.toggle_at:
            active[0] = True
            print("  >>> TOGGLE UP (pilot flipped the switch) — Sokol takes over", flush=True)
        if st.state != last_state:
            print(f"[state] {last_state} -> {st.state}  {st.message}", flush=True)
            last_state = st.state
        if args.designate and not designated and st.state == SystemState.READY:
            sup.designate(*args.designate)
            designated = True
        if st.state == SystemState.TRACK:
            print(f"  TRACK  target={st.target_px}  pan={st.pan_rad:+.3f} tilt={st.tilt_rad:+.3f}  "
                  f"body_yaw={st.body_yaw_cmd:+.2f}  λ̇_yaw={st.los_rate_yaw:+.3f}", flush=True)

    sup.run(max_seconds=args.seconds, on_status=on_status)


if __name__ == "__main__":
    main()
