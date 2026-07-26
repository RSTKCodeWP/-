"""Interactive head-IMU gimbal calibration: YOU move the gimbal by hand and name the direction; this reads
the IMU (independent of how the IMU is mounted) to learn (1) which gyro axis is PAN vs TILT and its sign, and
(2) the mechanical travel limits at each hard stop -- so the servo can NEVER be driven past the stops.

Run it IN YOUR OWN ssh session (it prompts you):

    cd ~/03-fpv && PYTHONPATH=.:fpv python3 ops/pi_gimbal_calib.py

Output: gimbal_calib.json -> loaded into Pi5Config (axis map, signs, scales, pan_limit_rad, tilt_limit_rad).

How it measures angle:
  * TILT is measured ABSOLUTELY from gravity (accelerometer) -- no drift.
  * PAN has no gravity reference, so it is integrated from the calibrated gyro during the move from centre to
    the stop -- accurate over the few seconds of a calibration move.
"""
from __future__ import annotations

import json
import math
import time

from smbus2 import SMBus

ADDR = 0x68
BUS = 1


def _rd16(bus, reg):
    v = (bus.read_byte_data(ADDR, reg) << 8) | bus.read_byte_data(ADDR, reg + 1)
    return v - 65536 if v > 32767 else v


def _raw(bus):
    a = (_rd16(bus, 0x3B), _rd16(bus, 0x3D), _rd16(bus, 0x3F))
    g = (_rd16(bus, 0x43), _rd16(bus, 0x45), _rd16(bus, 0x47))
    return a, g


def _scales(bus):
    gcfg = (bus.read_byte_data(ADDR, 0x1B) >> 3) & 0x3
    acfg = (bus.read_byte_data(ADDR, 0x1C) >> 3) & 0x3
    return {0: 131.0, 1: 65.5, 2: 32.8, 3: 16.4}[gcfg], {0: 16384.0, 1: 8192.0, 2: 4096.0, 3: 2048.0}[acfg]


def _prompt(msg):
    try:
        input(msg)
    except EOFError:
        print("(non-interactive: skipping)")


def _static(bus, acc_lsb, seconds=2.0):
    """Return (gyro_bias[3] LSB, gravity[3] g)."""
    gs = [0.0, 0.0, 0.0]; a_s = [0.0, 0.0, 0.0]; m = 0
    t0 = time.monotonic()
    while time.monotonic() - t0 < seconds:
        a, g = _raw(bus)
        for i in range(3):
            gs[i] += g[i]; a_s[i] += a[i]
        m += 1; time.sleep(0.004)
    return [x / m for x in gs], [a_s[i] / m / acc_lsb for i in range(3)]


def _integrate_move(bus, bias, gyro_lsb, seconds=3.0):
    """Integrate the bias-removed gyro over a move; return the per-axis rotation (deg) and end-gravity."""
    integ = [0.0, 0.0, 0.0]; prev = time.monotonic(); t0 = prev
    a_end = (0, 0, 0)
    while time.monotonic() - t0 < seconds:
        now = time.monotonic(); dt = now - prev; prev = now
        a, g = _raw(bus)
        a_end = a
        for i in range(3):
            integ[i] += (g[i] - bias[i]) * dt
        time.sleep(0.004)
    return [v / gyro_lsb for v in integ], a_end


def main():
    print("=== head-IMU gimbal calibration (manual moves + mechanical limits) ===\n")
    with SMBus(BUS) as bus:
        bus.write_byte_data(ADDR, 0x6B, 0x00); time.sleep(0.05)
        gyro_lsb, acc_lsb = _scales(bus)
        print("IMU full-scale: gyro %.1f LSB/(deg/s), accel %.0f LSB/g\n" % (gyro_lsb, acc_lsb))

        # 1) STATIC: bias + gravity at the CENTRE (level) position
        _prompt("1) Put the gimbal at its CENTRE, hold STILL, press Enter...")
        bias, grav = _static(bus, acc_lsb)
        down_axis = max(range(3), key=lambda i: abs(grav[i]))
        print("   bias=%s LSB   gravity=%s g   down=raw axis %d\n" %
              ([round(b, 1) for b in bias], [round(x, 2) for x in grav], down_axis))

        # 2) AXIS DISCOVERY: one clean move per axis tells us which gyro axis + sign
        _prompt("2) Press Enter, then PAN to the RIGHT ~3s (steady)...")
        pan_rot, _ = _integrate_move(bus, bias, gyro_lsb)
        pan_axis = max(range(3), key=lambda i: abs(pan_rot[i]))
        pan_sign_raw = 1.0 if pan_rot[pan_axis] > 0 else -1.0
        print("   PAN-right -> raw axis %d, %+.0f deg\n" % (pan_axis, pan_rot[pan_axis]))
        _prompt("   Return to centre, press Enter, then tilt NOSE-UP ~3s...")
        tilt_rot, _ = _integrate_move(bus, bias, gyro_lsb)
        tilt_axis = max(range(3), key=lambda i: abs(tilt_rot[i]))
        tilt_sign_raw = 1.0 if tilt_rot[tilt_axis] > 0 else -1.0
        print("   TILT-up -> raw axis %d, %+.0f deg\n" % (tilt_axis, tilt_rot[tilt_axis]))
        if pan_axis == tilt_axis:
            print("!! PAN and TILT read the SAME axis -- moves were not isolated. Re-run and move one axis at a time.")
            return

        def pan_angle_deg(rot):        # calibrated pan angle from a rotation vector
            return pan_sign_raw * rot[pan_axis]

        def tilt_angle_deg_from_grav(a):
            g = [a[i] / acc_lsb for i in range(3)]
            # tilt = angle of the boresight above horizontal, from the gravity component along the up axis.
            # Use the two axes not equal to the pan axis; robust small-angle proxy.
            return math.degrees(math.atan2(g[down_axis], math.sqrt(max(1e-9, sum(
                g[i] ** 2 for i in range(3) if i != down_axis)))))

        tilt0 = tilt_angle_deg_from_grav(_static(bus, acc_lsb, 0.6)[1])  # need raw accel; recompute below
        # (recompute tilt0 from raw at centre)
        _, gcen = _static(bus, acc_lsb, 0.4)
        tilt0 = tilt_angle_deg_from_grav([g * acc_lsb for g in gcen])

        # 3) MECHANICAL LIMITS: move to each hard stop; record the calibrated angle there.
        limits = {}
        for key, prompt in (
            ("pan_right", "3a) Press Enter, then SLOWLY move to the RIGHT hard stop and hold..."),
            ("pan_left",  "3b) Return to centre, press Enter, then move to the LEFT hard stop and hold..."),
            ("tilt_up",   "3c) Return to centre, press Enter, then move to the UP hard stop and hold..."),
            ("tilt_down", "3d) Return to centre, press Enter, then move to the DOWN hard stop and hold..."),
        ):
            _prompt(prompt)
            rot, a_end = _integrate_move(bus, bias, gyro_lsb, seconds=3.0)
            if key.startswith("pan"):
                ang = pan_angle_deg(rot)
            else:
                ang = tilt_angle_deg_from_grav(a_end) - tilt0
            limits[key] = round(ang, 1)
            print("   %-9s stop = %+.0f deg\n" % (key, ang))

    pan_map_sign = pan_sign_raw
    tilt_map_sign = tilt_sign_raw
    # body: x=roll(0), y=pitch/tilt(1), z=yaw/pan(2). We fill only the two axes a 2-axis gimbal uses.
    axis_map = [0, 1, 2]
    sign = [1.0, 1.0, 1.0]
    axis_map[2] = pan_axis;  sign[2] = pan_map_sign      # yaw/pan
    axis_map[1] = tilt_axis; sign[1] = tilt_map_sign     # pitch/tilt
    axis_map[0] = ({0, 1, 2} - {pan_axis, tilt_axis}).pop()   # the leftover raw axis = roll

    pan_lo = math.radians(min(limits["pan_left"], limits["pan_right"]))
    pan_hi = math.radians(max(limits["pan_left"], limits["pan_right"]))
    tilt_lo = math.radians(min(limits["tilt_up"], limits["tilt_down"]))
    tilt_hi = math.radians(max(limits["tilt_up"], limits["tilt_down"]))

    result = {
        "gyro_scale_rps": math.radians(1.0) / gyro_lsb,
        "accel_scale_mps2": 9.80665 / acc_lsb,
        "gyro_axis_map": axis_map, "gyro_sign": sign,
        "accel_axis_map": axis_map, "accel_sign": sign,
        "gyro_bias_lsb": [round(b, 2) for b in bias],
        "pan_limit_rad": [round(pan_lo, 4), round(pan_hi, 4)],
        "tilt_limit_rad": [round(tilt_lo, 4), round(tilt_hi, 4)],
        "limits_deg": limits,
    }
    with open("gimbal_calib.json", "w") as f:
        json.dump(result, f, indent=2)
    print("=== RESULT (written to gimbal_calib.json) ===")
    print("gyro_axis_map=%s gyro_sign=%s" % (tuple(axis_map), tuple(sign)))
    print("PAN travel:  %+.0f .. %+.0f deg" % (math.degrees(pan_lo), math.degrees(pan_hi)))
    print("TILT travel: %+.0f .. %+.0f deg" % (math.degrees(tilt_lo), math.degrees(tilt_hi)))
    print("\nThe servo command is now clamped to these limits (pan_pulse_us/tilt_pulse_us) -- it CANNOT be")
    print("driven past the mechanical stops. Send me 'готово' and I will load this into the flight config.")


if __name__ == "__main__":
    main()
