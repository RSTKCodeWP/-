"""Pi-5 hardware diagnostic for the interceptor bench. READ-ONLY by default -- probes every subsystem and
prints a PASS/WARN/FAIL table. Never commands flight motors. The gimbal-servo MOTION test is opt-in
(--servos) and moves only the 2 gimbal servos, never anything on the flight-power domain.

    PYTHONPATH=.:fpv python3 ops/pi_diag.py            # passive checks only
    PYTHONPATH=.:fpv python3 ops/pi_diag.py --servos   # + a small gimbal-servo sweep (head must be free to move)
"""
from __future__ import annotations

import sys
import time

RESULTS = []


def _row(name, status, detail=""):
    RESULTS.append((name, status, detail))
    mark = {"PASS": "[ OK ]", "WARN": "[WARN]", "FAIL": "[FAIL]", "SKIP": "[skip]"}[status]
    print("%s  %-26s %s" % (mark, name, detail))


def check_i2c():
    try:
        from smbus2 import SMBus
    except Exception as e:
        _row("I2C bus", "FAIL", "smbus2 missing: %s" % e); return {}
    found = {}
    try:
        with SMBus(1) as bus:
            for addr in (0x40, 0x68, 0x69, 0x70):
                try:
                    bus.read_byte(addr); found[addr] = True
                except Exception:
                    pass
    except Exception as e:
        _row("I2C bus", "FAIL", "bus 1 unreadable: %s" % e); return {}
    _row("I2C bus /dev/i2c-1", "PASS", "responders: " + (", ".join(hex(a) for a in found) or "none"))
    return found


def check_imu(found):
    addr = 0x68 if 0x68 in found else (0x69 if 0x69 in found else None)
    if addr is None:
        _row("Head IMU (MPU 0x68)", "FAIL", "not on the I2C bus"); return
    try:
        from smbus2 import SMBus
        with SMBus(1) as bus:
            who = bus.read_byte_data(addr, 0x75)                    # WHO_AM_I
            bus.write_byte_data(addr, 0x6B, 0x00)                   # wake (clear sleep)
            time.sleep(0.05)

            def rd(reg):
                v = (bus.read_byte_data(addr, reg) << 8) | bus.read_byte_data(addr, reg + 1)
                return v - 65536 if v > 32767 else v
            ax, ay, az = rd(0x3B), rd(0x3D), rd(0x3F)               # accel raw
            gx, gy, gz = rd(0x43), rd(0x45), rd(0x47)               # gyro raw
        amag = (ax * ax + ay * ay + az * az) ** 0.5 / 16384.0       # g at ±2g default
        gmax = max(abs(gx), abs(gy), abs(gz)) / 131.0               # deg/s at ±250 default
        model = {0x68: "MPU-6050", 0x71: "MPU-9250", 0x73: "MPU-9255", 0x70: "MPU-6500"}.get(who, "0x%02x" % who)
        ok = 0.6 < amag < 1.5 and gmax < 50.0                       # ~1g at rest, gyro quiet
        _row("Head IMU (%s)" % model, "PASS" if ok else "WARN",
             "|accel|=%.2fg gyro_max=%.1f deg/s %s" % (amag, gmax, "" if ok else "(still? |accel|~1g, gyro~0 expected)"))
    except Exception as e:
        _row("Head IMU", "FAIL", "%s: %s" % (type(e).__name__, e))


def check_pca9685(found):
    if 0x40 not in found:
        _row("Servo driver (PCA9685)", "FAIL", "0x40 not on the I2C bus"); return
    try:
        from smbus2 import SMBus
        with SMBus(1) as bus:
            mode1 = bus.read_byte_data(0x40, 0x00)                  # MODE1 register responds
        _row("Servo driver (PCA9685 0x40)", "PASS", "MODE1=0x%02x (responds)" % mode1)
    except Exception as e:
        _row("Servo driver (PCA9685)", "FAIL", "%s: %s" % (type(e).__name__, e))


def check_camera():
    # The seeker.service usually holds /dev/video0. Try direct open; if busy, confirm the live stream instead.
    import os
    if not os.path.exists("/dev/video0"):
        _row("Thermal (FT640 grabber)", "FAIL", "/dev/video0 absent"); return
    try:
        import cv2
        cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
        if cap.isOpened():
            ok = False
            for _ in range(10):
                r, f = cap.read()
                if r and f is not None:
                    ok = True
                    _row("Thermal (FT640 grabber)", "PASS" if f.max() > f.min() + 5 else "WARN",
                         "frame %s min/max %d/%d %s" % (f.shape, int(f.min()), int(f.max()),
                                                        "" if f.max() > f.min() + 5 else "(flat -> no CVBS signal?)"))
                    break
            cap.release()
            if ok:
                return
            cap.release()
    except Exception:
        pass
    # busy or failed direct -> check the running service's stream
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:8090/", timeout=4) as r:
            body = r.read(200)
        _row("Thermal (FT640 grabber)", "PASS", "held by seeker.service; live stream on :8090 responds")
    except Exception as e:
        _row("Thermal (FT640 grabber)", "WARN", "/dev/video0 busy and no :8090 stream (%s)" % type(e).__name__)


def _port_holder(port):
    """PID/cmd holding a device, via /proc (no fuser/sudo needed). Returns a short string or None."""
    import glob
    import os
    for fd in glob.glob("/proc/[0-9]*/fd/*"):
        try:
            if os.readlink(fd) == port:
                pid = fd.split("/")[2]
                cmd = open("/proc/%s/comm" % pid).read().strip()
                return "%s (pid %s)" % (cmd, pid)
        except Exception:
            pass
    return None


def check_fc(port="/dev/ttyACM0"):
    import os
    if not os.path.exists(port):
        _row("Flight controller (MSP)", "FAIL", "%s absent" % port); return
    holder = _port_holder(port)
    if holder:
        # opening a 2nd handle on a busy ACM garbles both streams -- do NOT; report the FC as present+owned.
        _row("Flight controller (MSP)", "PASS", "%s present, held by %s (running seeker service)" % (port, holder))
        return
    try:
        from fpv_ai.betaflight_link.serial_link import MspLink
        from fpv_ai.betaflight_link import msp_codec as mc
        from fpv_ai.msp_override_flight import read_rc_channels
        link = MspLink.open_serial(port, baud=115200, hardware_authorized=True)
        try:
            link.request(mc.MSP_API_VERSION); time.sleep(0.1)
            api = None
            for fr in link.poll():
                if fr.function == mc.MSP_API_VERSION and len(fr.payload) >= 3:
                    api = "%d.%d" % (fr.payload[1], fr.payload[2])
            rc = read_rc_channels(link)
        finally:
            link.close()
        if api is None and rc is None:
            _row("Flight controller (MSP)", "WARN", "%s open but no MSP reply (FC on? MSP on this port?)" % port)
            return
        detail = "API %s" % (api or "?")
        if rc is not None:
            aux2 = rc[5] if len(rc) > 5 else None                  # AUX2 = the override toggle
            detail += "  RC[%d ch]" % len(rc)
            if aux2 is not None:
                detail += "  AUX2(toggle)=%dus %s" % (aux2, "HELD" if aux2 >= 1600 else "released")
        else:
            detail += "  (no RC -- transmitter off? that is fine for a bench MSP check)"
        _row("Flight controller (MSP)", "PASS", detail)
    except Exception as e:
        _row("Flight controller (MSP)", "FAIL", "%s: %s" % (type(e).__name__, e))


def check_killmcu():
    import glob
    # The independent kill-MCU is on its OWN serial/RF, not the FC's ACM. Look for a second serial device.
    ports = [p for p in glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*") if p != "/dev/ttyACM0"]
    if ports:
        _row("Kill-MCU (independent)", "PASS", "candidate serial: %s" % ", ".join(ports))
    else:
        _row("Kill-MCU (independent)", "SKIP", "no 2nd serial device (kill-MCU may be on GPIO/RF, not USB)")


def check_flight_stack():
    try:
        from fpv.fpv_ai.flight_head import GimbalFlightHead
        from fpv.fpv_ai.flight_gimbal import FlightGimbalController
        from fpv.guidance.march import MarchTracker
        from fpv.seeker.geometry import ft640_intrinsics
        GimbalFlightHead(intrinsics=ft640_intrinsics(), march=True)
        _row("Flight software", "PASS", "flight_head + flight_gimbal + MARCH construct on the Pi")
    except Exception as e:
        _row("Flight software", "FAIL", "%s: %s" % (type(e).__name__, e))


def servo_sweep():
    """OPT-IN: a small, slow sweep of the 2 gimbal servos to confirm wiring/sign. Head must be free to move."""
    try:
        from seeker_core.pi5_io import make_pca9685_servo_writer, rad_to_pulse_us, Pi5Config
        w = make_pca9685_servo_writer(addr=0x40)
        cfg = Pi5Config()
        print("\n>> gimbal servo sweep (PAN=ch0, TILT=ch1): center -> ±15° -> center")
        import math
        for ch, name in ((0, "PAN"), (1, "TILT")):
            for a_deg in (0, 15, -15, 0):
                w(ch, rad_to_pulse_us(math.radians(a_deg), +1.0, cfg))
                time.sleep(0.4)
            print("   %s swept OK" % name)
        _row("Gimbal servos (motion)", "PASS", "both axes moved -- verify direction visually")
    except Exception as e:
        _row("Gimbal servos (motion)", "FAIL", "%s: %s" % (type(e).__name__, e))


def main():
    print("=== Pi-5 interceptor bench diagnostic (READ-ONLY unless --servos) ===\n")
    found = check_i2c()
    check_imu(found)
    check_pca9685(found)
    check_camera()
    check_fc()
    check_killmcu()
    check_flight_stack()
    if "--servos" in sys.argv:
        servo_sweep()
    n_fail = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    n_warn = sum(1 for _, s, _ in RESULTS if s == "WARN")
    print("\n=== %d checks: %d FAIL, %d WARN ===" % (len(RESULTS), n_fail, n_warn))
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
