#!/usr/bin/env python3
"""canarm — ArduPilot arm-readiness probe.

Asks the FC "would you arm right now?" and reports the answer.

Method:
  1. Connect via MAVLink to the first /dev/cu.usbmodem* (auto-baud:
     usbmodem*=115200, usbserial-0001=460800 for the RC-MAVLink dongle).
  2. Send MAV_CMD_RUN_PREARM_CHECKS (cmd 401) to force AP to run the full
     pre-arm suite immediately.
  3. Listen ~3 s and collect:
     - HEARTBEAT.system_status (MAV_STATE_STANDBY=3 means ready to arm)
     - SYS_STATUS.onboard_control_sensors_health bit 13 (MAV_SYS_STATUS_PREARM_CHECK,
       value 0x2000) — set when AP's pre-arm has passed
     - STATUSTEXT messages, especially those starting with "PreArm:" which are
       the human-readable failure reasons AP emits while pre-arm is failing.
  4. Verdict:
     * READY  → PREARM_CHECK bit set AND system_status==STANDBY AND no PreArm: messages
     * NOT READY → list the PreArm: reasons we collected.

Notes:
  - This is a passive observer except for the one explicit RUN_PREARM_CHECKS
    command. No params modified, no reboot, no side effects.
  - Doesn't actually arm the drone (would be unsafe + would fail without RC).
  - AP base_mode SAFETY_ARMED bit = whether the FC is *currently* armed; we
    surface that too but it's not the same as "would arm if asked."
"""
import argparse
import glob
import sys
import time


def log(msg):
    print(f"[canarm] {msg}", flush=True)


def find_port(port_override=None):
    if port_override:
        return port_override
    ports = sorted(glob.glob("/dev/cu.usbmodem*"))
    if ports:
        return ports[0]
    dongle = "/dev/cu.usbserial-0001"
    import os
    if os.path.exists(dongle):
        return dongle
    return None


def main():
    ap = argparse.ArgumentParser(description="ArduPilot arm-readiness probe.")
    ap.add_argument("--port", help="MAVLink port (auto if omitted)")
    ap.add_argument("--baud", type=int, help="Baud (auto by port if omitted)")
    ap.add_argument("--duration", type=float, default=3.0,
                    help="Seconds to collect STATUSTEXT/SYS_STATUS after RUN_PREARM_CHECKS (default 3)")
    args = ap.parse_args()

    port = find_port(args.port)
    if port is None:
        log("ABORT: no /dev/cu.usbmodem* or RC-MAVLink dongle found")
        return 1

    baud = args.baud
    if baud is None:
        baud = 460800 if "usbserial" in port else 115200

    log(f"port: {port} @ {baud}")

    try:
        from pymavlink import mavutil
    except ImportError:
        log("ABORT: pymavlink not installed (pip install pymavlink)")
        return 2

    m = mavutil.mavlink_connection(port, baud=baud,
                                   source_system=255, source_component=190)
    # Send some GCS heartbeats so AP keeps MAVLink lane open on USB CDC
    for _ in range(4):
        m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,
                             mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
        time.sleep(0.2)

    log("waiting for heartbeat (up to 5 s) ...")
    hb = m.wait_heartbeat(timeout=5)
    if hb is None:
        log("ABORT: no MAVLink heartbeat — is this an AP drone, port correct?")
        return 2

    log(f"connected sys={m.target_system} comp={m.target_component} "
        f"autopilot={hb.autopilot} type={hb.type}")

    # MAV_STATE strings
    MAV_STATE_NAMES = {
        0: "UNINIT", 1: "BOOT", 2: "CALIBRATING", 3: "STANDBY",
        4: "ACTIVE", 5: "CRITICAL", 6: "EMERGENCY", 7: "POWEROFF",
        8: "FLIGHT_TERMINATION",
    }

    # MAV_SYS_STATUS_SENSOR bit for the prearm aggregate (bit 13)
    PREARM_BIT = 0x2000  # MAV_SYS_STATUS_PREARM_CHECK

    armed_now = bool(hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    log(f"currently armed: {'YES' if armed_now else 'no'}  "
        f"(base_mode={hb.base_mode}, system_status={MAV_STATE_NAMES.get(hb.system_status, hb.system_status)})")

    # Fire RUN_PREARM_CHECKS (cmd 401) — tells AP to re-run the prearm suite NOW
    log("sending MAV_CMD_RUN_PREARM_CHECKS (401) ...")
    m.mav.command_long_send(
        m.target_system, m.target_component,
        401,  # MAV_CMD_RUN_PREARM_CHECKS
        0,    # confirmation
        0, 0, 0, 0, 0, 0, 0,
    )

    log(f"collecting STATUSTEXT + SYS_STATUS for {args.duration:.1f} s ...")

    prearm_msgs = []   # STATUSTEXT lines starting with "PreArm:" or "Arm:"
    other_msgs = []    # other STATUSTEXTs that might hint at issues
    prearm_bit_state = None   # last seen PREARM_CHECK bit (1=passed, 0=failing, None=no SYS_STATUS yet)
    last_sys_status = None
    last_system_status = hb.system_status

    deadline = time.time() + args.duration
    while time.time() < deadline:
        msg = m.recv_match(blocking=True, timeout=0.5)
        if msg is None:
            continue
        t = msg.get_type()
        if t == "STATUSTEXT":
            txt = msg.text
            if isinstance(txt, bytes):
                txt = txt.decode("ascii", errors="replace").rstrip("\x00")
            low = txt.lower()
            if low.startswith("prearm") or low.startswith("arm:"):
                if txt not in prearm_msgs:
                    prearm_msgs.append(txt)
            else:
                if txt not in other_msgs:
                    other_msgs.append(txt)
        elif t == "SYS_STATUS":
            last_sys_status = msg
            prearm_bit_state = 1 if (msg.onboard_control_sensors_health & PREARM_BIT) else 0
        elif t == "HEARTBEAT":
            last_system_status = msg.system_status

    # Decode
    print()
    print("=== AP arm-readiness probe ===")
    print(f"  system_status (heartbeat): {MAV_STATE_NAMES.get(last_system_status, last_system_status)}")
    if prearm_bit_state is None:
        print(f"  PREARM_CHECK sensor bit  : <no SYS_STATUS received>")
    else:
        print(f"  PREARM_CHECK sensor bit  : {'SET (passed)' if prearm_bit_state else 'CLEAR (failing)'}")

    if last_sys_status is not None:
        # Decode the most important "would block arming" sensor bits
        SENSORS = [
            (0x00000020, "GPS"),
            (0x00000004, "MAG"),
            (0x00000008, "ABS_PRESSURE (baro)"),
            (0x00000040, "OPTICAL_FLOW"),
            (0x00000080, "VISION_POSITION"),
            (0x00000100, "LASER_POSITION"),
            (0x00000400, "ANGULAR_RATE_CONTROL"),
            (0x00010000, "Z_ALTITUDE_CONTROL"),
            (0x00020000, "XY_POSITION_CONTROL"),
            (0x00040000, "MOTOR_OUTPUTS"),
            (0x00080000, "RC_RECEIVER"),
            (0x00100000, "3D_GYRO_2"),
            (0x00200000, "3D_ACCEL_2"),
            (0x00400000, "3D_MAG_2"),
            (0x00800000, "GEOFENCE"),
            (0x01000000, "AHRS"),
            (0x02000000, "TERRAIN"),
            (0x04000000, "REVERSE_MOTOR"),
            (0x08000000, "LOGGING"),
            (0x10000000, "BATTERY"),
        ]
        h = last_sys_status.onboard_control_sensors_health
        e = last_sys_status.onboard_control_sensors_enabled
        unhealthy = [name for bit, name in SENSORS if (e & bit) and not (h & bit)]
        if unhealthy:
            print(f"  unhealthy enabled sensors: {', '.join(unhealthy)}")

    if prearm_msgs:
        print()
        print(f"  PreArm messages ({len(prearm_msgs)}):")
        for m_ in prearm_msgs:
            print(f"    - {m_}")
    if other_msgs:
        # only show STATUSTEXTs that don't look like routine status lines
        interesting = [t for t in other_msgs
                       if not any(k in t.lower() for k in ("apm:", "boot", "armed", "disarmed", "init", "fast sampling", "imu0", "imu1", "frame:", "rcout", "chibios", "v4.6"))]
        if interesting:
            print(f"  other notable STATUSTEXTs ({len(interesting)}):")
            for t in interesting[:10]:
                print(f"    - {t}")

    print()
    print("=== verdict ===")
    ready = (
        prearm_bit_state == 1
        and last_system_status == 3  # MAV_STATE_STANDBY
        and not prearm_msgs
    )
    if armed_now:
        print("  STATE: currently ARMED — arm command is a no-op")
        return 0
    if ready:
        print("  STATE: READY TO ARM  — pre-arm checks pass; AP would accept arm command")
        return 0
    print("  STATE: NOT READY TO ARM")
    if prearm_msgs:
        print("    reasons (from PreArm STATUSTEXT):")
        for m_ in prearm_msgs:
            print(f"      - {m_}")
    elif prearm_bit_state == 0:
        print("    PREARM_CHECK sensor bit is clear but no PreArm STATUSTEXT was received within the window.")
        print("    Re-run with --duration 6 to give AP more time to emit the failure reason.")
    elif last_system_status != 3:
        print(f"    system_status is {MAV_STATE_NAMES.get(last_system_status, last_system_status)} "
              f"(not STANDBY) — AP isn't in a ready state.")
    else:
        print("    Couldn't determine reason. Try --duration 6.")
    return 5


if __name__ == "__main__":
    sys.exit(main())
