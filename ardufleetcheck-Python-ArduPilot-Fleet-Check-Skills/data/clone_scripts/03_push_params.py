#!/usr/bin/env python3
"""Step 3: Push params from a source dump onto the connected (target) FC.

Reads full_dump.json, PARAM_SETs every mismatched param, reads back for verification,
multi-passes (setting SERIAL*_PROTOCOL or CAN_P*_DRIVER unlocks dependent params,
so we need a second pass), and writes push_report.json.

Usage:
  ./03_push_params.py --port /dev/cu.usbmodem1101 --source ./clone_source/full_dump.json --out ./clone_source

Gotchas (see clone-workflow memory):
  - BARO1_GND_PRESS will "mismatch" — expected, it's a live atmospheric reading.
  - COMPASS_DEV_ID / INS_*_ID only stick when the physical sensor is attached.
  - Some params require a reboot to take effect; run 04_verify_fc.py after.
"""
import json, time, os, argparse
from pymavlink import mavutil

SKIP = {
    "STAT_BOOTCNT", "STAT_FLTTIME", "STAT_RESET", "STAT_RUNTIME",
    "FORMAT_VERSION", "SYSID_SW_MREV", "SYSID_SW_TYPE",
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbmodem1101")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--source", required=True, help="Path to full_dump.json from 01_dump_fc.py")
    ap.add_argument("--out", required=True, help="Directory for target_before.json / target_after.json / push_report.json")
    ap.add_argument("--passes", type=int, default=3)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    with open(args.source) as f:
        src = json.load(f)
    print(f"loaded {len(src)} source params from {args.source}", flush=True)

    m = mavutil.mavlink_connection(args.port, baud=args.baud)
    print("waiting for heartbeat...", flush=True)
    m.wait_heartbeat(timeout=10)
    print(f"connected sys={m.target_system} comp={m.target_component}", flush=True)

    def fetch_all():
        # Probe param_count via single read so we know the target count even if bulk LIST stalls.
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

        m.mav.param_request_list_send(m.target_system, m.target_component)
        ps, ts, expected, last = {}, {}, fc_param_count, time.time()
        while True:
            msg = m.recv_match(type='PARAM_VALUE', blocking=True, timeout=2)
            if msg is None:
                if time.time() - last > 5: break
                continue
            last = time.time()
            n = msg.param_id
            if isinstance(n, bytes):
                n = n.decode('ascii', errors='ignore').rstrip('\x00')
            ps[n] = msg.param_value
            ts[n] = msg.param_type
            expected = msg.param_count
            if expected and len(ps) >= expected: break

        # Fallback: bulk LIST wedged on some AP boards → enumerate by index.
        if expected and len(ps) < expected // 2:
            print(f"  bulk LIST stalled at {len(ps)}/{expected}; index-enumeration fallback", flush=True)
            for idx in range(expected):
                m.mav.param_request_read_send(m.target_system, m.target_component, b'', idx)
                rdl = time.time() + 1.0
                while time.time() < rdl:
                    msg = m.recv_match(type='PARAM_VALUE', blocking=True, timeout=0.2)
                    if msg is None: continue
                    n = msg.param_id
                    if isinstance(n, bytes): n = n.decode('ascii', errors='ignore').rstrip('\x00')
                    if not n: continue
                    ps[n] = msg.param_value
                    ts[n] = msg.param_type
                    if msg.param_index == idx or msg.param_index == 65535:
                        break
                if (idx + 1) % 200 == 0:
                    print(f"  index {idx+1}/{expected} (collected {len(ps)})", flush=True)
        return ps, ts, expected

    def set_param(name, value, ptype):
        m.mav.param_set_send(m.target_system, m.target_component, name.encode(), float(value), ptype)
        t0 = time.time()
        while time.time() - t0 < 1.5:
            msg = m.recv_match(type='PARAM_VALUE', blocking=True, timeout=0.5)
            if msg is None: continue
            n = msg.param_id
            if isinstance(n, bytes):
                n = n.decode('ascii', errors='ignore').rstrip('\x00')
            if n == name:
                ok = (abs(msg.param_value - value) < 1e-4 or
                      (ptype != mavutil.mavlink.MAV_PARAM_TYPE_REAL32 and
                       int(round(msg.param_value)) == int(round(value))))
                return ok, msg.param_value
        return False, None

    def match(a, b, ptype):
        if ptype in (mavutil.mavlink.MAV_PARAM_TYPE_REAL32, mavutil.mavlink.MAV_PARAM_TYPE_REAL64):
            if a == 0 and b == 0: return True
            return abs(a - b) / max(abs(a), abs(b), 1e-9) < 1e-5
        return int(round(a)) == int(round(b))

    print("fetching current target params...", flush=True)
    current, cur_types, _ = fetch_all()
    print(f"target has {len(current)} params", flush=True)
    with open(os.path.join(args.out, "target_before.json"), "w") as f:
        json.dump({n: {"value": v, "type": cur_types[n]} for n,v in current.items()}, f, indent=2, sort_keys=True)

    missing, failed, set_count, already = [], [], 0, 0
    for p in range(1, args.passes + 1):
        print(f"\n=== pass {p} ===", flush=True)
        changes = 0
        if p > 1:
            current, cur_types, _ = fetch_all()
        for name in sorted(src):
            if name in SKIP: continue
            src_val = src[name]["value"]
            if name not in current:
                if p == args.passes: missing.append(name)
                continue
            if match(current[name], src_val, cur_types[name]):
                if p == 1: already += 1
                continue
            ok, reported = set_param(name, src_val, cur_types[name])
            if ok:
                current[name] = reported
                set_count += 1
                changes += 1
                if set_count % 50 == 0:
                    print(f"  set {set_count} so far...", flush=True)
            elif p == args.passes:
                failed.append((name, src_val, reported))
        print(f"pass {p}: changed {changes}", flush=True)
        if changes == 0: break

    print("\nfetching final snapshot...", flush=True)
    final, ftypes, _ = fetch_all()
    with open(os.path.join(args.out, "target_after.json"), "w") as f:
        json.dump({n: {"value": v, "type": ftypes[n]} for n,v in final.items()}, f, indent=2, sort_keys=True)

    diffs = [(n, src[n]["value"], final[n]) for n in sorted(src)
             if n not in SKIP and n in final and not match(final[n], src[n]["value"], ftypes[n])]
    extra = [n for n in final if n not in src and n not in SKIP]

    report = {
        "source_params": len(src), "target_params_after": len(final),
        "already_matching": already, "newly_set": set_count,
        "missing_on_target": missing, "failed_to_set": failed,
        "extra_on_target": extra, "remaining_diffs": diffs,
    }
    with open(os.path.join(args.out, "push_report.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n===== PUSH REPORT =====")
    print(f"  source: {len(src)}  target_after: {len(final)}  already_matching: {already}  newly_set: {set_count}")
    print(f"  missing: {len(missing)}  failed: {len(failed)}  extra: {len(extra)}  remaining_diffs: {len(diffs)}")
    if diffs: print(f"  diff sample: {diffs[:10]}")
    if missing: print(f"  missing sample: {missing[:10]}")
    if failed: print(f"  failed sample: {failed[:10]}")

if __name__ == "__main__":
    main()
