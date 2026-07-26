"""Manual gimbal servo console — jog the 2 servos, set a ZERO (level) reference, and HOLD from it.

The head has NO position feedback (open-loop servos), so "zero" is whatever pulse you pick as level.
Workflow on the bench:
  1) jog pan/tilt until the camera looks level, then `savezero`
  2) `hold N` — from that zero the gyro-stabilised loop actively counters base motion (the real hold)

Commands (run each as a separate invocation; the current pulse persists in servo_state.json):
  read                       show current pan/tilt pulse (us) + saved zero
  set  pan|tilt  <us>        drive one servo to an absolute pulse
  jog  pan|tilt  <±us>       nudge one servo
  center                     go to the saved zero (or 1500/1500)
  sweep pan|tilt             slow sweep across the servo's travel — DIAGNOSTIC: does it physically move?
  savezero                   save the CURRENT pulses as the level/zero reference
  hold [seconds]             gyro-stabilise around the saved zero (servos hold the head level)

All pulses are clamped to the calibration's mechanical us-limits so a servo is never stalled.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

sys.path[:0] = [".", "fpv"]
import numpy as np
from seeker_core.pi5_io import (load_calibration, make_pca9685_servo_writer, make_i2c_imu_reader,
                                imu_raw_to_si)
from fpv.gimbal.controller import GimbalConfig, GimbalController

CALIB = "gimbal_calib_fixed.json"
STATE = "servo_state.json"


def _cfg():
    import dataclasses
    c = load_calibration(CALIB) if os.path.exists(CALIB) else None
    if c is None:
        raise SystemExit("no %s — run calibration first" % CALIB)
    return dataclasses.replace(c, gyro_scale_rps=math.radians(1.0) / 16.4,
                               accel_scale_mps2=9.80665 / 2048.0)


def _load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return {"pan_us": 1500.0, "tilt_us": 1500.0, "pan_zero": None, "tilt_zero": None}


def _save_state(s):
    json.dump(s, open(STATE, "w"), indent=2)


def _clamp(us, lim):
    lo, hi = min(lim), max(lim)
    return lo if us < lo else hi if us > hi else us


def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]
    c = _cfg()
    write_us = make_pca9685_servo_writer()
    s = _load_state()
    # PHYSICAL servo stops (us) — not Pi5Config fields, so read them from the raw calib json; fall back to a
    # CONSERVATIVE window so a manual jog can never stall a servo against its mechanical stop.
    _raw = json.load(open(CALIB)) if os.path.exists(CALIB) else {}
    plim = tuple(float(x) for x in _raw.get("pan_us_limit", (1400.0, 1600.0)))
    tlim = tuple(float(x) for x in _raw.get("tilt_us_limit", (1200.0, 1560.0)))

    def drive(pan_us, tilt_us):
        pan_us = _clamp(pan_us, plim); tilt_us = _clamp(tilt_us, tlim)
        write_us(c.pan_channel, pan_us); write_us(c.tilt_channel, tilt_us)
        s["pan_us"], s["tilt_us"] = pan_us, tilt_us
        _save_state(s)
        return pan_us, tilt_us

    if cmd == "read":
        print("pan_us=%.0f (ch%d, lim %s)  tilt_us=%.0f (ch%d, lim %s)" % (
            s["pan_us"], c.pan_channel, plim, s["tilt_us"], c.tilt_channel, tlim))
        print("saved zero: pan=%s tilt=%s" % (s["pan_zero"], s["tilt_zero"]))
    elif cmd == "set":
        ax, us = sys.argv[2], float(sys.argv[3])
        p, t = (us, s["tilt_us"]) if ax == "pan" else (s["pan_us"], us)
        pp, tt = drive(p, t)
        print("set %s -> pan_us=%.0f tilt_us=%.0f" % (ax, pp, tt))
    elif cmd == "jog":
        ax, d = sys.argv[2], float(sys.argv[3])
        p, t = (s["pan_us"] + d, s["tilt_us"]) if ax == "pan" else (s["pan_us"], s["tilt_us"] + d)
        pp, tt = drive(p, t)
        print("jog %s %+.0f -> pan_us=%.0f tilt_us=%.0f" % (ax, d, pp, tt))
    elif cmd == "center":
        p = s["pan_zero"] if s["pan_zero"] else 1500.0
        t = s["tilt_zero"] if s["tilt_zero"] else 1500.0
        pp, tt = drive(p, t)
        print("centered -> pan_us=%.0f tilt_us=%.0f" % (pp, tt))
    elif cmd == "sweep":
        ax = sys.argv[2]; lim = plim if ax == "pan" else tlim
        ch = c.pan_channel if ax == "pan" else c.tilt_channel
        print("sweeping %s ch%d across %s — WATCH the servo move" % (ax, ch, lim))
        lo, hi = min(lim), max(lim)
        for u in list(np.linspace(lo, hi, 30)) + list(np.linspace(hi, lo, 30)):
            write_us(ch, float(u)); time.sleep(0.05)
        mid = (lo + hi) / 2.0; write_us(ch, mid)
        if ax == "pan": s["pan_us"] = mid
        else: s["tilt_us"] = mid
        _save_state(s)
        print("sweep done, parked at %.0f" % mid)
    elif cmd == "savezero":
        s["pan_zero"], s["tilt_zero"] = s["pan_us"], s["tilt_us"]
        _save_state(s)
        print("SAVED ZERO: pan=%.0f tilt=%.0f  (this is now level/0; `hold` stabilises around it)" % (
            s["pan_zero"], s["tilt_zero"]))
    elif cmd == "hold":
        secs = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0
        pz = s["pan_zero"] if s["pan_zero"] else s["pan_us"]
        tz = s["tilt_zero"] if s["tilt_zero"] else s["tilt_us"]
        upr = c.servo_us_per_rad
        raw = make_i2c_imu_reader()
        print("HOLD STILL 1.5s (gyro bias)...")
        B = [imu_raw_to_si(raw(), c)[0] for _ in range(150)]
        bias = np.mean(B, 0)
        ctrl = GimbalController(GimbalConfig(k_loop=6.0, servo_rate_max_dps=120.0, accel_leveling=True,
                                             comp_alpha=0.98, k_bias=1.0))
        print("HOLDING %ss around zero (pan=%.0f tilt=%.0f) — SHAKE THE BASE, head should stay level." % (secs, pz, tz))
        t0 = time.monotonic(); last = t0; lastp = 0.0
        while time.monotonic() - t0 < secs:
            now = time.monotonic(); dt = now - last; last = now
            g, a = imu_raw_to_si(raw(), c)
            gc = (g[0] - bias[0], g[1] - bias[1], g[2] - bias[2])
            out = ctrl.step(gc, a, None, max(dt, 1e-4))
            pan_us = _clamp(pz + out.pan_setpoint_rad * c.pan_sign * upr, plim)
            tilt_us = _clamp(tz + out.tilt_setpoint_rad * c.tilt_sign * upr, tlim)
            write_us(c.pan_channel, pan_us); write_us(c.tilt_channel, tilt_us)
            if now - lastp >= 0.5:
                lastp = now
                print("  gy%+6.1f gz%+6.1f dps | pan_us%.0f tilt_us%.0f" % (
                    math.degrees(gc[1]), math.degrees(gc[2]), pan_us, tilt_us))
        write_us(c.pan_channel, pz); write_us(c.tilt_channel, tz)
        s["pan_us"], s["tilt_us"] = pz, tz; _save_state(s)
        print("hold done, parked at zero.")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
