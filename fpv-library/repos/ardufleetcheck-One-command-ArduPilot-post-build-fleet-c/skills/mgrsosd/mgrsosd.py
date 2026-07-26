#!/usr/bin/env python3
"""mgrsosd — push the MGRS OSD layout to whatever FC is plugged in.

Autodetects Betaflight (MSP) vs ArduPilot (MAVLink) and applies the right file
(both resolved under $TTFLEET_ROOT — see package README):
  - BF  → $TTFLEET_ROOT/mgrs update/diff_bf_osd.rtf
  - AP  → $TTFLEET_ROOT/mgrsosd ardupilot elements.param

Usage:
  mgrsosd.py [--file PATH] [--port /dev/...]

Detection order (MAVLink first — ArduPilot USB locks into MSP mode if probed
first, after which MAVLink heartbeats stop streaming):
  1. Open MAVLink at 115200, send GCS heartbeat, wait for AP heartbeat reply.
     If reply → AP path.
  2. Otherwise close MAVLink, MSP probe — if FC_VARIANT == BTFL → BF path.
  3. Else: bail.

BF flow (unchanged from v3):
  1. enter CLI (bare '#'); ensure feature OSD is on
  2. scan `diff` for `set osd_*_pos = <nonzero>` keys, inject `set ... = 0`
     clear lines into the batch so stale elements are zeroed before the new
     layout is applied
  3. paste each .rtf line; stop after `save` (FC reboots)

AP flow:
  1. fetch all OSD* params from the FC (the .param file is a full OSD-namespace
     dump, so EN=0 lines in the file disable elements that aren't part of the
     standard layout — clear + push in one operation)
  2. for every line in the .param file, PARAM_SET if the value differs from the
     FC's current value; verify via the echoed PARAM_VALUE
  3. multi-pass (2) so OSD2_ENABLE etc. can unlock dependent params
"""
import argparse
import glob
import os
import re
import sys
import time
from pathlib import Path

import serial  # pyserial

# Bundled OSD layout files live under TTFLEET_ROOT (see package README). Defaults
# to the original ttfleet layout so an unchanged machine keeps working.
TTFLEET_ROOT = Path(os.environ.get("TTFLEET_ROOT",
                                   str(Path.home() / "Documents" / "ttfleet")))
DEFAULT_BF_RTF = TTFLEET_ROOT / "mgrs update" / "diff_bf_osd.rtf"
DEFAULT_AP_PARAMS = TTFLEET_ROOT / "mgrsosd ardupilot elements.param"


def log(msg):
    print(f"[mgrsosd] {msg}", file=sys.stderr, flush=True)


# ---------- MAVLink probe (AP detection) — try FIRST to avoid MSP-locking AP's USB

def probe_mavlink(port, attempts=3, per_attempt=4.0):
    """Open MAVLink, send our GCS heartbeat, wait for FC heartbeat. Returns True
    if any HEARTBEAT was decoded. Closes the connection cleanly so the caller
    can reopen later. Retries because ArduPilot's USB multiplexer can take a
    moment to switch back from MSP to MAVLink if a prior MSP poll locked it.
    """
    try:
        from pymavlink import mavutil
    except ImportError:
        log("pymavlink not installed — can't probe MAVLink")
        return False
    for attempt in range(1, attempts + 1):
        m = None
        try:
            m = mavutil.mavlink_connection(port, baud=115200,
                                           source_system=255, source_component=190)
            # Send a few GCS heartbeats to nudge AP out of MSP-locked mode and
            # advertise ourselves on this channel.
            for _ in range(4):
                m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,
                                     mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
                time.sleep(0.2)
            hb = m.wait_heartbeat(timeout=per_attempt)
            if hb is not None:
                log(f"MAVLink heartbeat received (attempt {attempt}/{attempts})")
                return True
            log(f"  no heartbeat (attempt {attempt}/{attempts})")
        except Exception as e:
            log(f"  MAVLink probe error (attempt {attempt}/{attempts}): {e}")
        finally:
            if m is not None:
                try:
                    m.close()
                except Exception:
                    pass
            time.sleep(0.3)
    return False


# ---------- MSP variant probe (single shot)

def msp_variant(port, timeout=2.0):
    try:
        s = serial.Serial(port, 115200, timeout=0.5)
        time.sleep(0.3)
        s.reset_input_buffer()
        # MSP v1 request: cmd 2 (MSP_FC_VARIANT), no payload
        body = bytes([0, 2])
        s.write(b"$M<" + body + bytes([0 ^ 2]))
        s.flush()
        buf = bytearray()
        end = time.time() + timeout
        while time.time() < end:
            c = s.read(1)
            if not c:
                continue
            buf.extend(c)
            # look for: $M> <len=4> <cmd=2> <4 bytes payload>
            if len(buf) >= 9 and bytes(buf[:5]) == b"$M>\x04\x02":
                s.close()
                return buf[5:9].decode("ascii", errors="replace")
        s.close()
    except Exception as e:
        log(f"msp_variant probe error on {port}: {e}")
    return None


# ===========================================================================
# Betaflight path (unchanged from v3)
# ===========================================================================

def parse_rtf(path):
    raw = path.read_text()
    m = re.search(r"\\cf0\s+", raw)
    body = raw[m.end():] if m else raw
    out = []
    # Cocoa RTF terminates each logical line with '\' + newline
    for line in body.split("\\\n"):
        line = line.rstrip("\\")
        # strip any leftover RTF control words
        line = re.sub(r"\\[a-zA-Z0-9]+", "", line).strip()
        # also strip trailing '}'
        line = line.rstrip("}").strip()
        if not line:
            continue
        out.append(line)
    return out


def cli_open(port, baud=115200):
    s = serial.Serial(port, baud, timeout=0.5)
    time.sleep(0.3)
    s.reset_input_buffer()
    s.write(b"#")  # bare '#' per memory feedback_bf_cli_entry.md
    s.flush()
    buf = bytearray()
    end = time.time() + 3.0
    while time.time() < end:
        chunk = s.read(256)
        if chunk:
            buf.extend(chunk)
            if b"# " in buf:
                return s
    s.close()
    raise SystemExit(f"[mgrsosd] CLI prompt not seen on {port}")


def cli_send(s, line, timeout=5.0):
    s.reset_input_buffer()
    s.write(line.encode() + b"\r")
    s.flush()
    buf = bytearray()
    end = time.time() + timeout
    while time.time() < end:
        try:
            chunk = s.read(1024)
        except Exception as e:
            log(f"  serial read error on {line!r}: {e}")
            return buf.decode("utf-8", errors="replace")
        if chunk:
            buf.extend(chunk)
            if buf.endswith(b"# "):
                return buf[:-2].decode("utf-8", errors="replace")
    return buf.decode("utf-8", errors="replace")


def push_betaflight(port, rtf_path):
    log(f"Betaflight @ {port}")
    if not rtf_path.exists():
        raise SystemExit(f"[mgrsosd] file not found: {rtf_path}")
    lines = parse_rtf(rtf_path)
    log(f"parsed {len(lines)} CLI lines from {rtf_path.name}")

    s = cli_open(port)
    log("CLI entered")

    feat_out = cli_send(s, "feature")
    has_osd = re.search(r"\bOSD\b(?!\s*=)", feat_out) is not None
    if has_osd:
        log("OSD feature already enabled")
    else:
        log("OSD feature OFF — enabling")
        cli_send(s, "feature OSD")

    # Discover currently-active OSD element positions via `diff`, then inject
    # `set osd_*_pos = 0` lines into the batch so ALL existing elements are
    # cleared before the .rtf re-enables the desired ones.
    log("scanning currently-set OSD elements via `diff` ...")
    diff_out = cli_send(s, "diff", timeout=8.0)
    active_keys = []
    seen = set()
    for L in diff_out.splitlines():
        m = re.match(r"\s*set\s+(osd_\w+_pos)\s*=\s*(\d+)", L)
        if m and int(m.group(2)) != 0 and m.group(1) not in seen:
            active_keys.append(m.group(1))
            seen.add(m.group(1))
    log(f"  found {len(active_keys)} currently-set OSD position(s) to clear")

    if active_keys:
        clear_lines = [f"set {k} = 0" for k in active_keys]
        inject_at = 0
        for i, L in enumerate(lines):
            if L.strip() == "batch start":
                inject_at = i + 1
                break
        lines = lines[:inject_at] + clear_lines + lines[inject_at:]
        log(f"  injected {len(clear_lines)} clear-OSD lines into batch")

    rejected_lines = []
    save_refused = False
    sent = 0
    for line in lines:
        out = cli_send(s, line)
        sent += 1
        if any(marker in out for marker in ("###ERROR IN set", "Invalid name", "INVALID NAME",
                                            "Unknown command", "Bad option")):
            rejected_lines.append(line)
            log(f"  rejected line {sent}: {line!r}")
            log(f"    → {out.strip()[:160]}")
        if line.strip() == "save":
            if "ERRORS WERE DETECTED" in out or "PLEASE FIX ERRORS" in out:
                save_refused = True
                log(f"  save REFUSED after {sent} lines — BF saw {len(rejected_lines)} earlier error(s)")
            else:
                log(f"sent 'save' after {sent} lines — FC rebooting")
            break

    if save_refused and rejected_lines:
        log("retrying paste with rejected lines filtered out ...")
        try:
            s.write(b"exit noreboot\r")
            s.flush()
            time.sleep(0.5)
            s.read(1024)
        except Exception:
            pass
        try:
            s.close()
        except Exception:
            pass
        time.sleep(1.0)
        s = cli_open(port)
        log("CLI re-entered, batch discarded")
        filtered = [L for L in lines if L not in rejected_lines]
        log(f"  re-sending {len(filtered)} lines ({len(rejected_lines)} filtered out)")
        sent2 = 0
        for line in filtered:
            cli_send(s, line)
            sent2 += 1
            if line.strip() == "save":
                log(f"  sent 'save' after {sent2} filtered lines — FC rebooting")
                break

    try:
        s.close()
    except Exception:
        pass


# ===========================================================================
# ArduPilot path (new)
# ===========================================================================

def parse_ap_param_file(path):
    """Parse 'NAME,value' lines (also tolerates whitespace-separated)."""
    params = {}
    for raw_line in Path(path).read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "," in line:
            name, _, value = line.partition(",")
        else:
            parts = line.split()
            if len(parts) < 2:
                continue
            name, value = parts[0], parts[1]
        name = name.strip()
        try:
            params[name] = float(value.strip())
        except ValueError:
            log(f"  skipping unparseable line: {raw_line!r}")
    return params


def _ap_fetch_all_params(m, want_names=None):
    from pymavlink import mavutil  # noqa
    # Probe param_count so we can detect a wedged PARAM_REQUEST_LIST.
    m.mav.param_request_read_send(m.target_system, m.target_component, b'SYSID_THISMAV', -1)
    probe_dl = time.time() + 3
    fc_count = None
    while time.time() < probe_dl:
        msg = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
        if msg is None:
            continue
        pn = msg.param_id
        if isinstance(pn, bytes):
            pn = pn.decode("ascii", errors="ignore").rstrip("\x00")
        if pn == "SYSID_THISMAV":
            fc_count = msg.param_count
            break

    m.mav.param_request_list_send(m.target_system, m.target_component)
    ps, ts, expected, last = {}, {}, fc_count, time.time()
    while True:
        msg = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=2)
        if msg is None:
            if time.time() - last > 5:
                break
            continue
        last = time.time()
        n = msg.param_id
        if isinstance(n, bytes):
            n = n.decode("ascii", errors="ignore").rstrip("\x00")
        ps[n] = msg.param_value
        ts[n] = msg.param_type
        expected = msg.param_count
        if expected and len(ps) >= expected:
            break

    # Bulk LIST is wedged on some AP boards. Recover by reading by name when caller
    # tells us what they need (fast: ~30s for 236 OSD params), else by index (slow: ~4min).
    if expected and len(ps) < expected // 2:
        if want_names:
            log(f"  bulk LIST stalled at {len(ps)}/{expected}; read-by-name fallback for {len(want_names)} names")
            for nm in sorted(want_names):
                m.mav.param_request_read_send(m.target_system, m.target_component, nm.encode(), -1)
                rdl = time.time() + 1.0
                while time.time() < rdl:
                    msg = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.2)
                    if msg is None:
                        continue
                    rn = msg.param_id
                    if isinstance(rn, bytes):
                        rn = rn.decode("ascii", errors="ignore").rstrip("\x00")
                    if rn == nm:
                        ps[rn] = msg.param_value
                        ts[rn] = msg.param_type
                        break
        else:
            log(f"  bulk LIST stalled at {len(ps)}/{expected}; index-enumeration fallback")
            for idx in range(expected):
                m.mav.param_request_read_send(m.target_system, m.target_component, b'', idx)
                rdl = time.time() + 1.0
                while time.time() < rdl:
                    msg = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.2)
                    if msg is None:
                        continue
                    rn = msg.param_id
                    if isinstance(rn, bytes):
                        rn = rn.decode("ascii", errors="ignore").rstrip("\x00")
                    if not rn:
                        continue
                    ps[rn] = msg.param_value
                    ts[rn] = msg.param_type
                    if msg.param_index == idx or msg.param_index == 65535:
                        break
                if (idx + 1) % 200 == 0:
                    log(f"  index {idx+1}/{expected} (collected {len(ps)})")
    return ps, ts


def _ap_set_param(m, name, value, ptype):
    from pymavlink import mavutil
    m.mav.param_set_send(m.target_system, m.target_component, name.encode(), float(value), ptype)
    t0 = time.time()
    while time.time() - t0 < 1.5:
        msg = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
        if msg is None:
            continue
        n = msg.param_id
        if isinstance(n, bytes):
            n = n.decode("ascii", errors="ignore").rstrip("\x00")
        if n == name:
            if ptype == mavutil.mavlink.MAV_PARAM_TYPE_REAL32:
                ok = abs(msg.param_value - value) < 1e-4
            else:
                ok = int(round(msg.param_value)) == int(round(value))
            return ok, msg.param_value
    return False, None


def _ap_match(a, b, ptype):
    from pymavlink import mavutil
    if ptype in (mavutil.mavlink.MAV_PARAM_TYPE_REAL32, mavutil.mavlink.MAV_PARAM_TYPE_REAL64):
        if a == 0 and b == 0:
            return True
        return abs(a - b) / max(abs(a), abs(b), 1e-9) < 1e-5
    return int(round(a)) == int(round(b))


def push_ardupilot(port, param_path):
    try:
        from pymavlink import mavutil
    except ImportError:
        raise SystemExit("[mgrsosd] pymavlink not installed — pip install pymavlink")

    log(f"ArduPilot @ {port}")
    if not param_path.exists():
        raise SystemExit(f"[mgrsosd] file not found: {param_path}")
    target = parse_ap_param_file(param_path)
    osd_target = {k: v for k, v in target.items() if k.startswith("OSD")}
    log(f"parsed {len(osd_target)} OSD params from {param_path.name}")

    m = mavutil.mavlink_connection(port, baud=115200,
                                   source_system=255, source_component=190)
    # Advertise our GCS heartbeat first so AP's USB multiplexer keeps streaming
    # MAVLink (not MSP) on this CDC channel.
    for _ in range(4):
        m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,
                             mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
        time.sleep(0.2)
    log("waiting for heartbeat ...")
    if not m.wait_heartbeat(timeout=10):
        raise SystemExit("[mgrsosd] no MAVLink heartbeat on AP path")
    log(f"connected sys={m.target_system} comp={m.target_component}")

    log("fetching current params ...")
    current, types = _ap_fetch_all_params(m, want_names=set(osd_target.keys()))
    osd_current = {k: v for k, v in current.items() if k.startswith("OSD")}
    log(f"  FC has {len(current)} total params, {len(osd_current)} are OSD*")

    # Print current-state snapshot of just the enable/key positions so the user
    # can eyeball what's being replaced (per feedback_show_state_before_mutating_fc.md).
    enabled_now = [k for k, v in osd_current.items()
                   if k.endswith("_EN") and int(round(v)) == 1]
    log(f"  currently-enabled OSD elements ({len(enabled_now)}): "
        + ", ".join(sorted(enabled_now))[:300])

    missing, failed = [], []
    set_count, already = 0, 0
    PASSES = 2
    for p in range(1, PASSES + 1):
        log(f"=== pass {p} ===")
        changes = 0
        if p > 1:
            current, types = _ap_fetch_all_params(m, want_names=set(osd_target.keys()))
        for name in sorted(osd_target):
            tval = osd_target[name]
            if name not in current:
                if p == PASSES:
                    missing.append(name)
                continue
            ptype = types[name]
            cval = current[name]
            if _ap_match(cval, tval, ptype):
                if p == 1:
                    already += 1
                continue
            ok, reported = _ap_set_param(m, name, tval, ptype)
            if ok:
                current[name] = reported
                set_count += 1
                changes += 1
                if set_count % 25 == 0:
                    log(f"  set {set_count} so far ...")
            elif p == PASSES:
                failed.append(name)
        log(f"  pass {p}: changed {changes}")
        if changes == 0:
            break

    log("=== summary ===")
    log(f"  already matching: {already}")
    log(f"  newly set:        {set_count}")
    log(f"  missing on FC:    {len(missing)}")
    log(f"  failed to set:    {len(failed)}")
    if missing:
        log(f"  missing sample:   {missing[:8]}")
    if failed:
        log(f"  failed sample:    {failed[:8]}")
    log("done — AP params persist immediately, no reboot required")


# ===========================================================================
# main
# ===========================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=None,
                    help="Override layout file (default depends on detected FC: BF→.rtf, AP→.param)")
    ap.add_argument("--port", default=None)
    args = ap.parse_args()

    if args.port:
        port = args.port
    else:
        ports = sorted(glob.glob("/dev/cu.usbmodem*"))
        if not ports:
            raise SystemExit("[mgrsosd] no /dev/cu.usbmodem* — is the FC plugged in?")
        port = ports[0]

    log(f"probing {port} ...")

    # PASSIVE-LISTEN-FIRST (2026-05-20). Sniff for MAVLink stream without
    # sending anything (avoids the MSP-lock failure mode on AP USB CDC).
    # If silent, MSP probe disambiguates BF ('BTFL') from AP-with-DisplayPort
    # ('ARDU'). Last resort: MAVLink heartbeat probe with our own GCS HB.
    def _passive_listen(p, sec=0.6):
        import serial as _ser
        try:
            s = _ser.Serial(p, 115200, timeout=0.1)
            time.sleep(0.05)
            s.reset_input_buffer()
            end = time.time() + sec
            buf = bytearray()
            while time.time() < end:
                c = s.read(4096)
                if c:
                    buf.extend(c)
                    if buf.count(b'\xfd') + buf.count(b'\xfe') >= 2:
                        s.close()
                        return True
            s.close()
            return False
        except Exception:
            return False

    if _passive_listen(port):
        log("passive-listen: MAVLink stream detected -> ArduPilot")
        param_path = Path(args.file) if args.file else DEFAULT_AP_PARAMS
        push_ardupilot(port, param_path)
        log("done")
        return 0

    variant = msp_variant(port)
    if variant == "BTFL":
        rtf_path = Path(args.file) if args.file else DEFAULT_BF_RTF
        push_betaflight(port, rtf_path)
    elif variant == "ARDU":
        time.sleep(0.5)
        param_path = Path(args.file) if args.file else DEFAULT_AP_PARAMS
        push_ardupilot(port, param_path)
    else:
        if probe_mavlink(port, attempts=2, per_attempt=3.0):
            param_path = Path(args.file) if args.file else DEFAULT_AP_PARAMS
            push_ardupilot(port, param_path)
        else:
            raise SystemExit(f"[mgrsosd] couldn't identify FC on {port} — "
                             f"MSP variant={variant!r}, no MAVLink stream")

    log("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
