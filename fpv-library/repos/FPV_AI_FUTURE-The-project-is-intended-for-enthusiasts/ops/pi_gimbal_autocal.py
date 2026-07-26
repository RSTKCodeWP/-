"""AUTONOMOUS gimbal calibration: the script drives the 2 gimbal servos itself (slowly) and reads the head
IMU to work out everything -- which servo channel is PAN vs TILT, which gyro axis each is, the signs, the
mechanical travel limits, and (implicitly) that the servos actually move the head -- with no hand moving.
Writes gimbal_calib.json (including pan_channel/tilt_channel), which load_calibration() loads straight in.

Channel-order agnostic: pass the two servo channels; the script decides which is PAN (yaw: does NOT change
the gravity vector) and which is TILT (pitch: DOES tilt the head against gravity), from the head IMU itself.

Safe: it moves ONLY the 2 gimbal servos (never motors), in small slow steps, and STOPS pushing an axis the
instant the head stops rotating (a mechanical stop) -- it never forces against a stop. If commanding a servo
does not move the head (the IMU sees nothing), it aborts and says so (a servo power/wiring problem).

I2C is read as a single 14-byte burst with retries -- far more robust than many byte reads under servo noise.

    cd ~/03-fpv && PYTHONPATH=.:fpv python3 ops/pi_gimbal_autocal.py --channels 14,15
"""
from __future__ import annotations

import argparse
import json
import math
import time

from smbus2 import SMBus

from seeker_core.pi5_io import make_pca9685_servo_writer

ADDR = 0x68
BUS = 1
CENTER_US = 1500.0
HARD_MIN_US = 1050.0            # conservative soft bounds; we stop earlier when the head stalls
HARD_MAX_US = 1950.0
RAMP_US_S = 80.0               # continuous, smooth pulse ramp rate (us/s) -- no stop-start stiction
STALL_DPS = 1.5               # gyro rate below this (deg/s) while ramping = not moving
STALL_HOLD_S = 0.4            # sustained low-rate this long = a mechanical stop
MIN_TRAVEL_US = 60.0          # never call a stall before at least this much command travel
BACKOFF_US = 25.0            # sit this far INSIDE the stop (don't hold against it)


def _reg(bus, reg):
    """Single config-register read with retries."""
    for _ in range(8):
        try:
            return bus.read_byte_data(ADDR, reg)
        except OSError:
            time.sleep(0.003)
    return bus.read_byte_data(ADDR, reg)


def _wake(bus):
    """Wake and set full-scale to +-2000 dps / +-16 g -- the SAME range seeker_core.make_i2c_imu_reader uses
    in flight, so the gyro_scale_rps this calibration writes matches what the flight loop reads."""
    for _ in range(8):
        try:
            bus.write_byte_data(ADDR, 0x6B, 0x00)      # PWR_MGMT_1: wake
            bus.write_byte_data(ADDR, 0x1B, 0x18)      # GYRO_CONFIG  = +-2000 dps
            bus.write_byte_data(ADDR, 0x1C, 0x18)      # ACCEL_CONFIG = +-16 g
            time.sleep(0.02)
            return
        except OSError:
            time.sleep(0.003)
    bus.write_byte_data(ADDR, 0x6B, 0x00)


def _read_imu(bus):
    """One burst read of accel+gyro (14 bytes from 0x3B) with retries. A single SMBus transaction is far more
    reliable than 12 byte reads under servo-motor bus noise. Returns (accel3, gyro3) raw counts."""
    last = None
    for _ in range(12):
        try:
            d = bus.read_i2c_block_data(ADDR, 0x3B, 14)

            def s16(hi):
                v = (d[hi] << 8) | d[hi + 1]
                return v - 65536 if v > 32767 else v

            return (s16(0), s16(2), s16(4)), (s16(8), s16(10), s16(12))
        except OSError as e:
            last = e
            time.sleep(0.004)
    raise IOError("IMU burst read failed after retries: %s" % last)


def _gyro(bus):
    return _read_imu(bus)[1]


def _grav(bus, acc_lsb, n=20):
    s = [0.0, 0.0, 0.0]
    for _ in range(n):
        a, _g = _read_imu(bus)
        for i in range(3):
            s[i] += a[i]
        time.sleep(0.003)
    return [s[i] / n / acc_lsb for i in range(3)]


def _scales(bus):
    g = (_reg(bus, 0x1B) >> 3) & 0x3
    a = (_reg(bus, 0x1C) >> 3) & 0x3
    return {0: 131.0, 1: 65.5, 2: 32.8, 3: 16.4}[g], {0: 16384.0, 1: 8192.0, 2: 4096.0, 3: 2048.0}[a]


def _bias(bus, seconds=1.5):
    s = [0.0, 0.0, 0.0]; n = 0; t0 = time.monotonic()
    while time.monotonic() - t0 < seconds:
        g = _gyro(bus)
        for i in range(3):
            s[i] += g[i]
        n += 1; time.sleep(0.004)
    return [x / n for x in s]


def _rotate_window(bus, bias, gyro_lsb, seconds):
    """Integrate bias-removed gyro over `seconds`; return per-axis rotation (deg)."""
    integ = [0.0, 0.0, 0.0]; prev = time.monotonic(); t0 = prev
    while time.monotonic() - t0 < seconds:
        now = time.monotonic(); dt = now - prev; prev = now
        g = _gyro(bus)
        for i in range(3):
            integ[i] += (g[i] - bias[i]) * dt
        time.sleep(0.003)
    return [v / gyro_lsb for v in integ]


class Servo:
    def __init__(self, write, ch):
        self.write = write; self.ch = ch; self.us = CENTER_US
    def go(self, us):
        self.us = max(HARD_MIN_US, min(HARD_MAX_US, us))
        for _ in range(4):
            try:
                self.write(self.ch, self.us); return
            except OSError:
                time.sleep(0.003)
        self.write(self.ch, self.us)


def sweep_limit(bus, servo, bias, gyro_lsb, axis, direction):
    """Ramp the servo SMOOTHLY outward until the head stops rotating (a mechanical stop), detected by the
    gyro rate falling to ~0 while the pulse is still advancing. Returns (limit_pulse_us, swept_angle_deg).
    Continuous ramp avoids per-step stiction (tiny steps against gravity don't move a servo -> false stall)."""
    servo.go(CENTER_US); time.sleep(0.6)
    us = CENTER_US; angle = 0.0; low_t = 0.0
    prev = time.monotonic()
    while HARD_MIN_US < us < HARD_MAX_US:
        now = time.monotonic(); dt = now - prev; prev = now
        if dt > 0.1:
            dt = 0.02
        us += direction * RAMP_US_S * dt
        servo.go(us)
        rate = (_gyro(bus)[axis] - bias[axis]) / gyro_lsb
        angle += rate * dt
        if abs(rate) < STALL_DPS:
            low_t += dt
            if low_t > STALL_HOLD_S and abs(us - CENTER_US) > MIN_TRAVEL_US:
                us -= direction * BACKOFF_US                  # sit just inside the stop
                break
        else:
            low_t = 0.0
        time.sleep(0.015)
    servo.go(max(HARD_MIN_US, min(HARD_MAX_US, us)))
    return servo.us, angle


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channels", default="14,15", help="the two gimbal servo PCA9685 channels")
    args = ap.parse_args()
    ch_a, ch_b = (int(x) for x in args.channels.split(","))

    print("=== AUTONOMOUS gimbal calibration (channels %d, %d) ===\n" % (ch_a, ch_b))
    write = make_pca9685_servo_writer(addr=0x40)
    srv = {ch_a: Servo(write, ch_a), ch_b: Servo(write, ch_b)}

    def recenter():
        for s in srv.values():
            s.go(CENTER_US)

    recenter(); time.sleep(0.6)

    try:
        with SMBus(BUS) as bus:
            _wake(bus); time.sleep(0.05)
            gyro_lsb, acc_lsb = _scales(bus)
            print("IMU: gyro %.1f LSB/(deg/s), accel %.0f LSB/g" % (gyro_lsb, acc_lsb))
            bias = _bias(bus)
            print("gyro bias: %s LSB\n" % [round(b, 1) for b in bias])

            def probe(ch):
                """+180us on this channel; return (gyro_axis, signed_rot_deg, gravity_change_g)."""
                s = srv[ch]
                s.go(CENTER_US); time.sleep(0.5); _rotate_window(bus, bias, gyro_lsb, 0.2)
                g0 = _grav(bus, acc_lsb)
                s.go(CENTER_US + 180); rot = _rotate_window(bus, bias, gyro_lsb, 0.9)
                g1 = _grav(bus, acc_lsb)
                s.go(CENTER_US); time.sleep(0.5)
                ax = max(range(3), key=lambda i: abs(rot[i]))
                gd = math.sqrt(sum((g1[i] - g0[i]) ** 2 for i in range(3)))
                print("ch%d +180us -> raw gyro axis %d %+.1f deg, gravity change %.2f g" % (ch, ax, rot[ax], gd))
                return ax, rot[ax], gd

            a_ax, a_rot, a_gd = probe(ch_a)
            b_ax, b_rot, b_gd = probe(ch_b)

            if max(abs(a_rot), abs(b_rot)) < 2.0:
                print("\n*** ABORT: commanding the servos did NOT move the head (max %.1f deg). ***"
                      % max(abs(a_rot), abs(b_rot)))
                print("PWM is correct, so this is HARDWARE: servo V+ power, the channels, or a jammed head.")
                recenter(); return
            if a_ax == b_ax:
                print("\n!! both channels moved the SAME gyro axis -- not a 2-axis gimbal setup. Aborting.")
                recenter(); return

            # TILT (pitch) tilts the head against gravity; PAN (yaw) does not.
            if a_gd >= b_gd:
                tilt_ch, tilt_axis, tilt_rot = ch_a, a_ax, a_rot
                pan_ch, pan_axis, pan_rot = ch_b, b_ax, b_rot
            else:
                tilt_ch, tilt_axis, tilt_rot = ch_b, b_ax, b_rot
                pan_ch, pan_axis, pan_rot = ch_a, a_ax, a_rot
            pan_sign = 1.0 if pan_rot > 0 else -1.0
            tilt_sign = 1.0 if tilt_rot > 0 else -1.0
            print("\n-> PAN  = channel %d, raw axis %d (sign %+d)" % (pan_ch, pan_axis, pan_sign))
            print("-> TILT = channel %d, raw axis %d (sign %+d)\n" % (tilt_ch, tilt_axis, tilt_sign))

            print("finding limits (driving to each stop, slowly)...")
            pr_us, pr_deg = sweep_limit(bus, srv[pan_ch], bias, gyro_lsb, pan_axis, +1)
            print("  pan  right stop: %.0f us, %+.1f deg" % (pr_us, pr_deg * pan_sign))
            pl_us, pl_deg = sweep_limit(bus, srv[pan_ch], bias, gyro_lsb, pan_axis, -1)
            print("  pan  left  stop: %.0f us, %+.1f deg" % (pl_us, pl_deg * pan_sign))
            tu_us, tu_deg = sweep_limit(bus, srv[tilt_ch], bias, gyro_lsb, tilt_axis, +1)
            print("  tilt up    stop: %.0f us, %+.1f deg" % (tu_us, tu_deg * tilt_sign))
            td_us, td_deg = sweep_limit(bus, srv[tilt_ch], bias, gyro_lsb, tilt_axis, -1)
            print("  tilt down  stop: %.0f us, %+.1f deg" % (td_us, td_deg * tilt_sign))
            recenter()
    except IOError as e:
        recenter()
        print("\n*** I2C read failed repeatedly: %s" % e)
        print("The bus is flaky. Physical fixes: shorter I2C leads, stronger pull-ups (2.2-4.7k to 3.3V), a")
        print("common solid ground between Pi/PCA9685/IMU, and route the IMU wires away from the servo leads.")
        return

    pan_deg = (pl_deg * pan_sign, pr_deg * pan_sign)
    tilt_deg = (td_deg * tilt_sign, tu_deg * tilt_sign)

    def _upr(us_a, us_b, deg_a, deg_b):        # servo pulse-per-radian from a measured sweep
        d = abs(deg_a - deg_b)
        return abs(us_a - us_b) / math.radians(d) if d > 5.0 else None
    _upr_vals = [v for v in (_upr(pr_us, pl_us, pr_deg, pl_deg), _upr(tu_us, td_us, tu_deg, td_deg)) if v]
    servo_upr = round(sum(_upr_vals) / len(_upr_vals), 1) if _upr_vals else None

    axis_map = [0, 1, 2]; sign = [1.0, 1.0, 1.0]
    axis_map[2] = pan_axis; sign[2] = pan_sign
    axis_map[1] = tilt_axis; sign[1] = tilt_sign
    axis_map[0] = ({0, 1, 2} - {pan_axis, tilt_axis}).pop()

    result = {
        "gyro_scale_rps": math.radians(1.0) / gyro_lsb,
        "accel_scale_mps2": 9.80665 / acc_lsb,
        "gyro_axis_map": axis_map, "gyro_sign": sign,
        "accel_axis_map": axis_map, "accel_sign": sign,
        "gyro_bias_lsb": [round(b, 2) for b in bias],
        "pan_channel": pan_ch, "tilt_channel": tilt_ch,
        "pan_sign": pan_sign, "tilt_sign": tilt_sign,
        "pan_limit_rad": [round(math.radians(min(pan_deg)), 4), round(math.radians(max(pan_deg)), 4)],
        "tilt_limit_rad": [round(math.radians(min(tilt_deg)), 4), round(math.radians(max(tilt_deg)), 4)],
        "servo_us_center": CENTER_US,
        **({"servo_us_per_rad": servo_upr} if servo_upr else {}),
        "pan_us_limit": [round(min(pl_us, pr_us), 1), round(max(pl_us, pr_us), 1)],
        "tilt_us_limit": [round(min(td_us, tu_us), 1), round(max(td_us, tu_us), 1)],
        "limits_deg": {"pan": [round(min(pan_deg), 1), round(max(pan_deg), 1)],
                       "tilt": [round(min(tilt_deg), 1), round(max(tilt_deg), 1)]},
    }
    with open("gimbal_calib.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\n=== RESULT (gimbal_calib.json) ===")
    print("PAN  ch%d axis %d sign %+d   travel %+.0f..%+.0f deg   pulse %.0f..%.0f us" % (
        pan_ch, pan_axis, pan_sign, min(pan_deg), max(pan_deg), min(pl_us, pr_us), max(pl_us, pr_us)))
    print("TILT ch%d axis %d sign %+d   travel %+.0f..%+.0f deg   pulse %.0f..%.0f us" % (
        tilt_ch, tilt_axis, tilt_sign, min(tilt_deg), max(tilt_deg), min(td_us, tu_us), max(td_us, tu_us)))


if __name__ == "__main__":
    main()
