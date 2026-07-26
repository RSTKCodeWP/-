#!/usr/bin/env python3
"""Step 1: Dump everything from the SOURCE FC.

Produces in the output dir:
  - full_dump.params  (ArduPilot-style name,value CSV)
  - full_dump.json    (name -> {value, type})
  - fc_info.json      (banner, AUTOPILOT_VERSION, mission/fence/rally counts)
  - mission.json      (if any mission items present)

Usage:
  ./01_dump_fc.py --port /dev/cu.usbmodem1101 --out ./clone_source
"""
import json, time, os, argparse
from pymavlink import mavutil

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbmodem1101")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--out", required=True, help="Output directory for dump files")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    m = mavutil.mavlink_connection(args.port, baud=args.baud)
    print("waiting for heartbeat...", flush=True)
    hb = m.wait_heartbeat(timeout=10)
    print(f"heartbeat: sys={m.target_system} comp={m.target_component} type={hb.type} autopilot={hb.autopilot}", flush=True)

    info = {
        "heartbeat": {
            "type": hb.type, "autopilot": hb.autopilot,
            "base_mode": hb.base_mode, "custom_mode": hb.custom_mode,
            "system_status": hb.system_status, "mavlink_version": hb.mavlink_version,
        },
        "target_system": m.target_system,
        "target_component": m.target_component,
    }

    print("requesting AUTOPILOT_VERSION...", flush=True)
    m.mav.command_long_send(m.target_system, m.target_component,
        mavutil.mavlink.MAV_CMD_REQUEST_AUTOPILOT_CAPABILITIES, 0, 1, 0, 0, 0, 0, 0, 0)
    msg = m.recv_match(type='AUTOPILOT_VERSION', blocking=True, timeout=5)
    if msg:
        v = msg.flight_sw_version
        info["autopilot_version"] = {
            "capabilities": msg.capabilities,
            "flight_sw_version": v,
            "flight_sw_version_decoded": f"{(v>>24)&0xff}.{(v>>16)&0xff}.{(v>>8)&0xff}.{v&0xff}",
            "board_version": msg.board_version,
            "vendor_id": msg.vendor_id, "product_id": msg.product_id,
            "uid": msg.uid,
            "uid2": bytes(msg.uid2).hex() if hasattr(msg, 'uid2') else None,
        }
        print(f"  flight_sw: {info['autopilot_version']['flight_sw_version_decoded']}", flush=True)

    print("requesting banner...", flush=True)
    m.mav.command_long_send(m.target_system, m.target_component,
        mavutil.mavlink.MAV_CMD_DO_SEND_BANNER, 0, 0,0,0,0,0,0,0)
    banner = []
    t0 = time.time()
    while time.time() - t0 < 3:
        msg = m.recv_match(type='STATUSTEXT', blocking=True, timeout=1)
        if msg:
            banner.append(msg.text)
            print(f"  banner: {msg.text}", flush=True)
    info["banner"] = banner

    print("dumping params...", flush=True)
    # Probe param_count via a single known-good read first (cheap, ~50 ms).
    # If bulk LIST stalls later, we already know the target count for index-enum fallback.
    m.mav.param_request_read_send(m.target_system, m.target_component, b'SYSID_THISMAV', -1)
    probe_deadline = time.time() + 3
    fc_param_count = None
    while time.time() < probe_deadline:
        msg = m.recv_match(type='PARAM_VALUE', blocking=True, timeout=0.5)
        if msg is None: continue
        pn = msg.param_id
        if isinstance(pn, bytes): pn = pn.decode('ascii', errors='ignore').rstrip('\x00')
        if pn == 'SYSID_THISMAV':
            fc_param_count = msg.param_count
            break
    if fc_param_count:
        print(f"  FC reports param_count={fc_param_count}", flush=True)

    m.mav.param_request_list_send(m.target_system, m.target_component)
    params, types = {}, {}
    expected, last = fc_param_count, time.time()
    while True:
        msg = m.recv_match(type='PARAM_VALUE', blocking=True, timeout=2)
        if msg is None:
            if time.time() - last > 5: break
            continue
        last = time.time()
        name = msg.param_id
        if isinstance(name, bytes):
            name = name.decode('ascii', errors='ignore').rstrip('\x00')
        params[name] = msg.param_value
        types[name] = msg.param_type
        expected = msg.param_count
        if len(params) % 100 == 0:
            print(f"  {len(params)}/{expected}", flush=True)
        if expected and len(params) >= expected:
            break
    print(f"got {len(params)} params (expected {expected})", flush=True)

    # Fallback: if bulk LIST stalled (<50% of expected), enumerate by param_index.
    # Some AP boards have a wedged param-streamer where PARAM_REQUEST_LIST yields
    # nothing but PARAM_REQUEST_READ works fine. Recover by walking indices 0..N-1.
    if expected and len(params) < expected // 2:
        print(f"  bulk LIST stalled at {len(params)}/{expected}; falling back to index enumeration", flush=True)
        for idx in range(expected):
            m.mav.param_request_read_send(m.target_system, m.target_component, b'', idx)
            rdl = time.time() + 1.0
            while time.time() < rdl:
                msg = m.recv_match(type='PARAM_VALUE', blocking=True, timeout=0.2)
                if msg is None: continue
                n = msg.param_id
                if isinstance(n, bytes): n = n.decode('ascii', errors='ignore').rstrip('\x00')
                if not n: continue
                params[n] = msg.param_value
                types[n] = msg.param_type
                if msg.param_index == idx or msg.param_index == 65535:
                    break
            if (idx + 1) % 100 == 0:
                print(f"  index {idx+1}/{expected} (collected {len(params)})", flush=True)
        print(f"got {len(params)} params after index fallback (expected {expected})", flush=True)
    info["param_count"] = len(params)
    info["param_count_expected"] = expected

    with open(os.path.join(args.out, "full_dump.params"), "w") as f:
        for name in sorted(params):
            v, t = params[name], types[name]
            if t in (mavutil.mavlink.MAV_PARAM_TYPE_UINT8, mavutil.mavlink.MAV_PARAM_TYPE_INT8,
                    mavutil.mavlink.MAV_PARAM_TYPE_UINT16, mavutil.mavlink.MAV_PARAM_TYPE_INT16,
                    mavutil.mavlink.MAV_PARAM_TYPE_UINT32, mavutil.mavlink.MAV_PARAM_TYPE_INT32):
                f.write(f"{name},{int(round(v))}\n")
            else:
                f.write(f"{name},{v:.9g}\n")
    with open(os.path.join(args.out, "full_dump.json"), "w") as f:
        json.dump({n: {"value": v, "type": types[n]} for n,v in params.items()}, f, indent=2, sort_keys=True)

    for mtype, label in [
        (mavutil.mavlink.MAV_MISSION_TYPE_MISSION, "mission"),
        (mavutil.mavlink.MAV_MISSION_TYPE_FENCE, "fence"),
        (mavutil.mavlink.MAV_MISSION_TYPE_RALLY, "rally"),
    ]:
        try:
            m.mav.mission_request_list_send(m.target_system, m.target_component, mtype)
            msg = m.recv_match(type='MISSION_COUNT', blocking=True, timeout=3)
            count = msg.count if msg else None
            info[f"{label}_count"] = count
            print(f"{label} count: {count}", flush=True)
            if label == "mission" and count:
                items = []
                for i in range(count):
                    m.mav.mission_request_int_send(m.target_system, m.target_component, i, mtype)
                    im = m.recv_match(type=['MISSION_ITEM_INT','MISSION_ITEM'], blocking=True, timeout=2)
                    if im: items.append(im.to_dict())
                with open(os.path.join(args.out, "mission.json"), "w") as f:
                    json.dump(items, f, indent=2, default=str)
        except Exception as e:
            print(f"  {label} dump failed: {e}", flush=True)

    with open(os.path.join(args.out, "fc_info.json"), "w") as f:
        json.dump(info, f, indent=2, default=str)
    print(f"\nwrote dump to {args.out}", flush=True)

if __name__ == "__main__":
    main()
