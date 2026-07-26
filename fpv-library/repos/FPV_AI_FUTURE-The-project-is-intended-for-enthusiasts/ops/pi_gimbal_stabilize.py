"""pi_gimbal_stabilize -- TX-12 toggle turns ON automatic gimbal stabilization (and target tracking if a
frame source is present). The IMU is on the head, so the head gyro IS the camera's inertial rate: with no
target the controller drives that rate to zero -> the camera holds its inertial pointing while the base
moves (pure stabilization). With a target it slews the boresight onto the centroid.

Loads gimbal_calib.json (from ops/pi_gimbal_autocal.py): correct IMU axes/signs, the servo channels, and the
mechanical travel LIMITS -- so a servo command is clamped and can NEVER be driven past its stop.

SAFETY: drives ONLY the 2 gimbal servos. Never flight motors, never arming. The FC serial is READ-ONLY here
(only MSP_RC, to read the toggle) -- nothing is ever written to the FC. Props OFF for bench work.

    cd ~/03-fpv && PYTHONPATH=.:fpv python3 ops/pi_gimbal_stabilize.py \
        [--calib gimbal_calib.json] [--fc /dev/ttyACM0] [--channel-index 11] \
        [--stream http://127.0.0.1:8090/s.mjpg]   # omit --stream for pure stabilization (no tracking)

    --fc none        run always-ON (no toggle) -- for testing stabilization on its own
"""
from __future__ import annotations

import argparse
import os
import time


def main() -> None:  # pragma: no cover -- hardware bench/flight only
    ap = argparse.ArgumentParser(description="TX-12 gimbal stabilization / tracking (2 servos only)")
    ap.add_argument("--calib", default="gimbal_calib.json")
    ap.add_argument("--fc", default="/dev/ttyACM0", help="FC MSP serial for the toggle, or 'none' for always-ON")
    ap.add_argument("--channel-index", type=int, default=11, help="MSP_RC index of the toggle (ch12 == 11)")
    ap.add_argument("--stream", default="", help="MJPEG stream for target tracking (omit = pure stabilize)")
    ap.add_argument("--hz", type=float, default=100.0)
    ap.add_argument("--rc-hz", type=float, default=20.0, help="how often to poll the toggle over MSP")
    args = ap.parse_args()

    from fpv.gimbal.controller import GimbalConfig, GimbalController
    from fpv.fpv_ai.tx_activation import TxActivation
    from seeker_core.pi5_io import (
        Pi5Config, Pi5Imu, load_calibration, make_i2c_imu_reader, make_pca9685_servo_writer,
        pan_pulse_us, tilt_pulse_us,
    )

    cfg = load_calibration(args.calib) if os.path.exists(args.calib) else Pi5Config()
    if os.path.exists(args.calib):
        print("calibration loaded: pan=ch%d tilt=ch%d  pan_limit=%s tilt_limit=%s" % (
            cfg.pan_channel, cfg.tilt_channel, cfg.pan_limit_rad, cfg.tilt_limit_rad))
    else:
        print("!! no %s -- running on Pi5Config DEFAULTS (channels 0/1, NO travel limits). Calibrate first."
              % args.calib)

    imu = Pi5Imu(cfg, make_i2c_imu_reader(addr=0x68))
    write = make_pca9685_servo_writer(addr=0x40)
    ctrl = GimbalController(GimbalConfig())
    act = TxActivation(channel_index=args.channel_index)

    # optional FC toggle
    link = None
    read_rc = None
    if args.fc.lower() != "none":
        try:
            from fpv_ai.betaflight_link.serial_link import MspLink
            from fpv_ai.msp_override_flight import read_rc_channels
            link = MspLink.open(args.fc)
            read_rc = read_rc_channels
            print("toggle: MSP_RC channel index %d on %s (>=1600us == ON)" % (args.channel_index, args.fc))
        except Exception as e:
            print("!! could not open FC %s for the toggle (%s). Is seeker.service holding it? "
                  "Falling back to always-ON." % (args.fc, e))
    if link is None:
        print("toggle: NONE -> always ON")

    # optional camera for tracking
    cap = pipe = None
    if args.stream:
        try:
            import cv2
            from fpv.guidance.pipeline import SeekerGuidancePipeline
            from fpv.seeker.geometry import ft640_intrinsics
            cap = cv2.VideoCapture(args.stream)
            pipe = SeekerGuidancePipeline(intrinsics=ft640_intrinsics(), full_ego_compensation=True)
            print("tracking: %s" % args.stream)
        except Exception as e:
            print("!! tracking disabled (%s) -- pure stabilization" % e)
            cap = pipe = None
    else:
        print("tracking: OFF -> pure stabilization (hold inertial)")

    def centroid():
        if cap is None or pipe is None:
            return None
        try:
            import numpy as np
            ok, f = cap.read()
            if not ok or f is None:
                return None
            if f.ndim == 3:
                import cv2
                f = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
            if not getattr(pipe, "_designated", False):
                h, w = f.shape
                pipe.designate((w / 2.0, h / 2.0))
                pipe._designated = True
            out = pipe.step(time.monotonic(), (f.astype(np.uint16) << 6) + 4096, (0.0, 0.0, 0.0), 0.02)
            return out.centroid_px if out.centroid_px and "LOCK" in out.tracking_state else None
        except Exception:
            return None

    dt = 1.0 / args.hz
    rc_period = 1.0 / max(1.0, args.rc_hz)
    rc = None
    last_rc = 0.0
    last_log = 0.0
    print("\nrunning. flip TX-12 to activate. Ctrl-C to stop.\n")
    try:
        while True:
            t = time.monotonic()
            if link is not None and read_rc is not None and t - last_rc >= rc_period:
                rc = read_rc(link)
                last_rc = t
            on = act.update(rc) if link is not None else True

            try:
                s = imu.read(time.monotonic_ns())
                gyro = s.gyro_rps if s else (0.0, 0.0, 0.0)
                accel = s.accel_mps2 if s else (0.0, 0.0, 9.81)
            except OSError:
                time.sleep(dt); continue                     # transient I2C glitch -> skip this tick

            out = ctrl.step(gyro, accel, centroid() if on else None, dt)
            try:
                if on:
                    # anti-windup: clamp the controller's own setpoint to the mechanical travel, so a sustained
                    # base rotation can't wind the integrator past the stop and lag the reversal.
                    if cfg.pan_limit_rad is not None:
                        ctrl.pan = max(cfg.pan_limit_rad[0], min(cfg.pan_limit_rad[1], ctrl.pan))
                    if cfg.tilt_limit_rad is not None:
                        ctrl.tilt = max(cfg.tilt_limit_rad[0], min(cfg.tilt_limit_rad[1], ctrl.tilt))
                    write(cfg.pan_channel, pan_pulse_us(ctrl.pan, cfg))
                    write(cfg.tilt_channel, tilt_pulse_us(ctrl.tilt, cfg))
                else:
                    ctrl.pan = ctrl.tilt = 0.0                # reset integrators so it starts clean next ON
                    write(cfg.pan_channel, pan_pulse_us(0.0, cfg))
                    write(cfg.tilt_channel, tilt_pulse_us(0.0, cfg))
            except OSError:
                pass                                          # transient I2C glitch on the write -> next tick

            if t - last_log >= 0.5:
                import math
                print("%s pan=%+5.1f tilt=%+5.1f deg  gyro(p,y)=%+5.1f,%+5.1f dps  %s" % (
                    "ON " if on else "off", math.degrees(ctrl.pan),
                    math.degrees(ctrl.tilt), math.degrees(out.los_rate_pitch),
                    math.degrees(out.los_rate_yaw), "TRACK" if out.tracking else "hold"))
                last_log = t
            time.sleep(max(0.0, dt - (time.monotonic() - t)))
    except KeyboardInterrupt:
        pass
    finally:
        try:
            write(cfg.pan_channel, pan_pulse_us(0.0, cfg))
            write(cfg.tilt_channel, tilt_pulse_us(0.0, cfg))
        except OSError:
            pass
        if cap is not None:
            cap.release()
        print("\nstopped, servos centered.")


if __name__ == "__main__":  # pragma: no cover
    main()
