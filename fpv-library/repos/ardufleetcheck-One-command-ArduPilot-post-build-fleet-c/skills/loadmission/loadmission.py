#!/usr/bin/env python3
"""loadmission — upload a QGC .plan mission to a connected ArduPilot drone.

Two-call workflow (mirrors /arduflash):
  - First call (no --plan): lists .plan files in
    ~/Documents/QGroundControl/Missions sorted newest-first, then exits 10 so
    Claude can call AskUserQuestion to pick.
  - With --plan PATH: parses the file, clears the existing mission, uploads
    via MISSION_COUNT + MISSION_REQUEST_INT + MISSION_ITEM_INT exchange,
    waits for MISSION_ACK.

Reads QGC .plan format (JSON):
  mission.items[].command  — MAV_CMD enum
  mission.items[].frame    — MAV_FRAME
  mission.items[].params   — [p1, p2, p3, p4, lat°, lon°, alt_m]
  mission.items[].autoContinue
  mission.items[].doJumpId — used as MISSION_ITEM_INT.seq

ArduPilot-only by design — pymavlink mission protocol works on AP. BF doesn't
support waypoint missions.

Exit codes:
  0 = uploaded successfully (MISSION_ACK accepted)
  1 = no port found
  2 = no heartbeat / unsupported firmware
  3 = no .plan files / file not found / parse error
  4 = upload failed (timeout, rejected, or no ACK)
  5 = stage 3 — no .apj candidates
  10 = needs --plan pick (enumeration printed; re-run with --plan PATH)
"""
import argparse
import glob
import json
import os
import sys
import time
from pathlib import Path

MISSIONS_DIR = Path.home() / "Documents" / "QGroundControl" / "Missions"


def log(msg):
    print(f"[loadmission] {msg}", flush=True)


def find_port(port_override=None):
    if port_override:
        return port_override
    ports = sorted(glob.glob("/dev/cu.usbmodem*"))
    if ports:
        return ports[0]
    dongle = "/dev/cu.usbserial-0001"
    if os.path.exists(dongle):
        return dongle
    return None


def list_missions(directory):
    """Return [(path, mtime, basename)] sorted newest-first."""
    plans = list(Path(directory).glob("*.plan"))
    plans.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [(p, p.stat().st_mtime, p.name) for p in plans]


def parse_plan(path):
    """Parse a QGC .plan file. Returns list of (cmd, frame, p1, p2, p3, p4, lat, lon, alt, autocontinue)."""
    with open(path) as f:
        data = json.load(f)
    if data.get("fileType") != "Plan":
        raise ValueError(f"not a QGC plan (fileType={data.get('fileType')!r})")
    mission = data.get("mission", {})
    items = mission.get("items", [])
    parsed = []
    for i, item in enumerate(items):
        if item.get("type") != "SimpleItem":
            raise ValueError(f"item {i}: only SimpleItem supported (got {item.get('type')!r})")
        params = item.get("params", [])
        if len(params) != 7:
            raise ValueError(f"item {i}: expected 7 params, got {len(params)}")
        cmd = int(item["command"])
        frame = int(item["frame"])
        p1, p2, p3, p4 = params[0:4]
        lat, lon, alt = params[4], params[5], params[6]
        autocont = 1 if item.get("autoContinue", True) else 0
        parsed.append((cmd, frame, p1, p2, p3, p4, lat, lon, alt, autocont))
    return parsed, mission


def upload_mission(port, baud, items, source_path):
    """Upload mission items to AP via MAVLink mission protocol.

    Returns True on success, False on failure (with reason logged).
    """
    try:
        from pymavlink import mavutil
    except ImportError:
        log("ABORT: pymavlink not installed")
        return False

    log(f"connecting to {port} @ {baud} ...")
    m = mavutil.mavlink_connection(port, baud=baud,
                                   source_system=255, source_component=190)
    # Heartbeats so AP keeps MAVLink lane open
    for _ in range(4):
        m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,
                             mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
        time.sleep(0.2)

    hb = m.wait_heartbeat(timeout=5)
    if hb is None:
        log("ABORT: no MAVLink heartbeat")
        return False
    log(f"connected sys={m.target_system} comp={m.target_component}")

    if hb.autopilot != mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA:
        log(f"ABORT: not ArduPilot (autopilot={hb.autopilot}); /loadmission is AP-only")
        return False

    # Clear existing mission first.
    log("clearing existing mission ...")
    m.mav.mission_clear_all_send(m.target_system, m.target_component,
                                 mavutil.mavlink.MAV_MISSION_TYPE_MISSION)
    # Wait briefly for ACK
    dl = time.time() + 3
    while time.time() < dl:
        msg = m.recv_match(type='MISSION_ACK', blocking=True, timeout=0.5)
        if msg and getattr(msg, 'mission_type', 0) == mavutil.mavlink.MAV_MISSION_TYPE_MISSION:
            log(f"  clear ACK: type={msg.type}")
            break

    n = len(items)
    log(f"uploading {n} mission items ...")

    # Announce count and serve item requests.
    # Be tolerant: AP requests by seq, we serve. Retry COUNT once if no request arrives.
    sent_seqs = set()

    def send_count():
        m.mav.mission_count_send(m.target_system, m.target_component, n,
                                 mavutil.mavlink.MAV_MISSION_TYPE_MISSION)

    send_count()
    last_count_t = time.time()
    last_request_t = time.time()
    final_ack = None

    while True:
        msg = m.recv_match(blocking=True, timeout=0.5)
        now = time.time()

        # Re-send COUNT if AP hasn't requested anything in 2s and we haven't finished
        if msg is None:
            if not sent_seqs and (now - last_count_t) > 2.0:
                log("  no MISSION_REQUEST yet, re-sending COUNT ...")
                send_count()
                last_count_t = now
            if (now - last_request_t) > 8.0:
                log("ABORT: AP stopped requesting items (timeout)")
                return False
            continue

        t = msg.get_type()
        if t in ('MISSION_REQUEST_INT', 'MISSION_REQUEST'):
            seq = msg.seq
            if seq >= n:
                log(f"  AP requested out-of-range seq {seq} (have {n}); ignoring")
                continue
            item = items[seq]
            cmd, frame, p1, p2, p3, p4, lat, lon, alt, autocont = item
            # Lat/lon as int32 * 1e7 for MISSION_ITEM_INT
            lat_i = int(round(lat * 1e7))
            lon_i = int(round(lon * 1e7))
            m.mav.mission_item_int_send(
                m.target_system, m.target_component,
                seq,
                frame,
                cmd,
                0,             # current
                autocont,      # autocontinue
                p1, p2, p3, p4,
                lat_i, lon_i, float(alt),
                mavutil.mavlink.MAV_MISSION_TYPE_MISSION,
            )
            sent_seqs.add(seq)
            last_request_t = now
            if (seq + 1) % 10 == 0 or seq + 1 == n:
                log(f"  sent {seq + 1}/{n}")
        elif t == 'MISSION_ACK':
            mt = getattr(msg, 'mission_type', 0)
            if mt != mavutil.mavlink.MAV_MISSION_TYPE_MISSION:
                continue
            final_ack = msg
            break
        # ignore other messages

    # Decode ACK
    ACK_NAMES = {
        0: 'ACCEPTED', 1: 'ERROR', 2: 'UNSUPPORTED_FRAME', 3: 'UNSUPPORTED',
        4: 'NO_SPACE', 5: 'INVALID', 6: 'INVALID_PARAM1', 7: 'INVALID_PARAM2',
        8: 'INVALID_PARAM3', 9: 'INVALID_PARAM4', 10: 'INVALID_PARAM5_X',
        11: 'INVALID_PARAM6_Y', 12: 'INVALID_PARAM7', 13: 'INVALID_SEQUENCE',
        14: 'DENIED', 15: 'OPERATION_CANCELLED',
    }
    name = ACK_NAMES.get(final_ack.type, f'type={final_ack.type}')
    log(f"MISSION_ACK: {name}")
    if final_ack.type == 0:
        log(f"SUCCESS — {n} items uploaded from {Path(source_path).name}")
        return True
    log(f"FAIL — AP rejected with {name}")
    return False


def main():
    ap = argparse.ArgumentParser(description="Upload a QGC .plan mission to ArduPilot.")
    ap.add_argument("--plan", help="Path to the .plan file to upload. If omitted, "
                                   "lists available missions and exits 10.")
    ap.add_argument("--port", help="MAVLink port (auto if omitted)")
    ap.add_argument("--baud", type=int, help="Baud (auto by port if omitted)")
    ap.add_argument("--missions-dir", default=str(MISSIONS_DIR),
                    help=f"Mission folder (default: {MISSIONS_DIR})")
    args = ap.parse_args()

    if not args.plan:
        # Enumerate
        missions = list_missions(args.missions_dir)
        if not missions:
            log(f"ABORT: no .plan files in {args.missions_dir}")
            return 3
        print()
        log(f"found {len(missions)} .plan file(s) in {args.missions_dir} "
            f"(newest first):")
        for i, (p, mtime, name) in enumerate(missions, 1):
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
            print(f"  {i}) {name}  (modified {ts})")
        print()
        log("RE-RUN with --plan <path> to upload.")
        return 10

    plan_path = Path(args.plan)
    if not plan_path.exists():
        log(f"ABORT: plan not found: {plan_path}")
        return 3
    try:
        items, mission_meta = parse_plan(plan_path)
    except Exception as e:
        log(f"ABORT: parse error in {plan_path.name}: {e}")
        return 3
    log(f"parsed {plan_path.name}: {len(items)} mission items")
    # Quick summary of commands
    from collections import Counter
    cmd_names = {
        16: 'WAYPOINT', 17: 'LOITER_UNLIM', 18: 'LOITER_TURNS', 19: 'LOITER_TIME',
        20: 'RTL', 21: 'LAND', 22: 'TAKEOFF', 82: 'SPLINE_WAYPOINT',
        83: 'ALTITUDE_WAIT', 84: 'VTOL_TAKEOFF', 85: 'VTOL_LAND',
        93: 'DELAY', 112: 'CONDITION_DELAY', 113: 'CONDITION_CHANGE_ALT',
        114: 'CONDITION_DISTANCE', 115: 'CONDITION_YAW',
        177: 'DO_JUMP', 178: 'DO_CHANGE_SPEED', 179: 'DO_SET_HOME',
        183: 'DO_SET_SERVO', 184: 'DO_REPEAT_SERVO', 201: 'DO_SET_ROI',
        203: 'DO_DIGICAM_CONTROL', 206: 'DO_SET_CAM_TRIGG_DIST',
        212: 'DO_MOUNT_CONTROL', 530: 'DO_GIMBAL_MANAGER_PITCHYAW',
    }
    summary = Counter(it[0] for it in items)
    summary_str = ", ".join(f"{cmd_names.get(c, f'cmd{c}')}×{n}"
                            for c, n in summary.most_common())
    log(f"  contains: {summary_str}")

    port = find_port(args.port)
    if port is None:
        log("ABORT: no MAVLink port found")
        return 1
    baud = args.baud
    if baud is None:
        baud = 460800 if "usbserial" in port else 115200

    ok = upload_mission(port, baud, items, plan_path)
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())
