#!/usr/bin/env python3
"""/arduflash — visual orchestrator: dump → pick .apj → reboot → flash → wait → restore.

Wraps the existing ttfleet/clone_scripts/01_dump_fc.py, 02_flash_fc.py, and
03_push_params.py with stage banners, [OK]/[..]/[FAIL] checkmarks, and a
.apj picker. See ~/.claude/skills/arduflash/SKILL.md.
"""
import argparse
import fnmatch
import glob
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PY = os.environ.get("TTFLEET_PYTHON", "/usr/bin/python3")
# TTFLEET_ROOT holds the bundled data dir (clone_scripts + OSD files) and is
# the default place we look for firmware. Defaults to the original ttfleet
# layout so an unchanged machine keeps working; recipients export TTFLEET_ROOT
# to wherever they unpacked the package's data/ dir.
TTFLEET_ROOT = Path(os.environ.get("TTFLEET_ROOT",
                                   str(Path.home() / "Documents" / "ttfleet")))
CLONE_SCRIPTS = TTFLEET_ROOT / "clone_scripts"
# Dump output goes here per run. Override with TTFLEET_DUMP_ROOT if you want it
# outside the data dir.
DUMP_ROOT = Path(os.environ.get("TTFLEET_DUMP_ROOT",
                                str(TTFLEET_ROOT / "ardupilot dumps")))
# Where the .apj firmware picker searches (recursively). Point this at your
# firmware folder via TTFLEET_FIRMWARE_DIR; defaults to TTFLEET_ROOT.
APJ_SEARCH_ROOT = Path(os.environ.get("TTFLEET_FIRMWARE_DIR", str(TTFLEET_ROOT)))


# ---------- Visual output

def banner(stage_num, total, title):
    bar = "=" * 60
    print(f"\n{bar}", flush=True)
    print(f"=== [{stage_num}/{total}] {title} ===", flush=True)
    print(f"{bar}", flush=True)


def ok(msg):
    print(f"  [OK]   {msg}", flush=True)


def step(msg):
    print(f"  [..]   {msg}", flush=True)


def fail(msg):
    print(f"  [FAIL] {msg}", file=sys.stderr, flush=True)


def info(msg):
    print(f"         {msg}", flush=True)


# ---------- Port autodetect

def find_port():
    """Prefer /dev/cu.usbmodem*, fall back to /dev/cu.usbserial-0001 @ 460800."""
    modems = sorted(glob.glob("/dev/cu.usbmodem*"))
    if modems:
        return modems[0], 115200
    if os.path.exists("/dev/cu.usbserial-0001"):
        return "/dev/cu.usbserial-0001", 460800
    return None, None


def port_is_clean(port):
    """`lsof` returns non-empty if something holds the port. Returns (clean, holder)."""
    out = subprocess.run(["lsof", port], capture_output=True, text=True).stdout
    if not out.strip():
        return True, None
    holder = out.strip().splitlines()[-1].split()[0]
    return False, holder


# ---------- Stage 1: detect + identify

def stage_detect(port, baud):
    banner(1, 8, "Detect FC + confirm ArduPilot")
    clean, holder = port_is_clean(port)
    if not clean:
        fail(f"port {port} held by {holder!r} — close it first")
        return None
    ok(f"port: {port} (baud {baud})")

    # Minimal pymavlink probe: heartbeat + AUTOPILOT_VERSION
    from pymavlink import mavutil
    step("connecting + waiting for heartbeat (10s timeout)...")
    m = mavutil.mavlink_connection(port, baud=baud)
    hb = m.wait_heartbeat(timeout=10)
    if hb is None:
        fail("no heartbeat — is the FC actually ArduPilot?")
        return None
    ok(f"heartbeat: sys={m.target_system} comp={m.target_component} type={hb.type}")

    step("requesting AUTOPILOT_VERSION...")
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_REQUEST_AUTOPILOT_CAPABILITIES,
                            0, 1, 0, 0, 0, 0, 0, 0)
    msg = m.recv_match(type="AUTOPILOT_VERSION", blocking=True, timeout=5)
    info_blob = {"target_system": m.target_system, "target_component": m.target_component}
    if msg:
        v = msg.flight_sw_version
        decoded = f"{(v>>24)&0xff}.{(v>>16)&0xff}.{(v>>8)&0xff}.{v&0xff}"
        board_id = msg.board_version  # this is the .apj `board_id` match key
        ok(f"AUTOPILOT_VERSION: board_id={board_id}  fw={decoded}")
        info_blob.update({"board_id": board_id, "fw": decoded})
    else:
        fail("no AUTOPILOT_VERSION response — board_id check will be skipped")
        info_blob["board_id"] = None

    m.close()
    return info_blob


# ---------- Stage 2: param dump (calls 01_dump_fc.py)

def stage_dump(port, baud, out_dir):
    banner(2, 8, "Dump current params via MAVLink")
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [PY, str(CLONE_SCRIPTS / "01_dump_fc.py"),
           "--port", port, "--baud", str(baud),
           "--out", str(out_dir)]
    step(f"running: 01_dump_fc.py --out '{out_dir.name}'")
    rc = run_streamed(cmd)
    if rc != 0:
        fail(f"01_dump_fc.py exited {rc}")
        return False
    json_path = out_dir / "full_dump.json"
    if not json_path.exists():
        fail(f"expected {json_path} not produced")
        return False
    with open(json_path) as f:
        n = len(json.load(f))
    ok(f"dumped {n} params -> {out_dir / 'full_dump.json'}")
    return True


# ---------- Stage 3: .apj picker + validation

def find_apjs(max_results=20):
    """Return list of (path, mtime) for .apj files under APJ_SEARCH_ROOT, newest first."""
    pattern = str(APJ_SEARCH_ROOT / "**" / "*.apj")
    paths = glob.glob(pattern, recursive=True)
    with_mtime = [(p, os.path.getmtime(p)) for p in paths]
    with_mtime.sort(key=lambda x: -x[1])
    return with_mtime[:max_results]


def stage_pick_apj(connected_board_id):
    banner(3, 8, "Pick firmware (.apj) to flash")
    candidates = find_apjs()
    if not candidates:
        fail(f"no .apj files found anywhere under {APJ_SEARCH_ROOT}")
        return None

    # Print candidates so the user can read them in the Claude conversation,
    # then return the metadata the caller needs to ask via AskUserQuestion.
    info(f"found {len(candidates)} .apj file(s):")
    for i, (path, mtime) in enumerate(candidates, 1):
        t = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        rel = Path(path).relative_to(APJ_SEARCH_ROOT)
        info(f"  {i}) {rel}  (modified {t})")
    return [p for p, _ in candidates]


def validate_apj(apj_path, connected_board_id):
    """Read and print .apj metadata. Returns (ok, meta).

    NOTE: We do NOT try to compare `.apj['board_id']` against the connected FC's
    `AUTOPILOT_VERSION.board_version` — those fields encode different things.
    `.apj['board_id']` is the AP build system's APJ_BOARD_ID (e.g. TBS_LUCID_H7 = 5250).
    `AUTOPILOT_VERSION.board_version` is the running firmware's `AP_HAL_BOARD` value
    which is encoded differently and won't compare cleanly. The authoritative
    cross-board safety check is done by uploader.py at flash time — it reads the
    bootloader's board_id over its own protocol and refuses to flash mismatches.

    So our job here is just: print what we're about to flash for human review."""
    try:
        with open(apj_path) as f:
            meta = json.load(f)
    except Exception as e:
        fail(f"could not read .apj as JSON: {e}")
        return False, None
    ok(f"selected: {Path(apj_path).name}")
    info(f"        .apj board_id={meta.get('board_id')}  git_identity={meta.get('git_identity')!s:.20}")
    info(f"        image_size={meta.get('image_size')}  summary={meta.get('summary')}")
    info(f"        (uploader.py will verify board_id against the bootloader at flash time)")
    return True, meta


# ---------- Stage 4: reboot to bootloader

def stage_reboot_to_bl(port, baud):
    banner(4, 8, "Reboot FC into bootloader")
    from pymavlink import mavutil
    step("connecting briefly to send REBOOT_SHUTDOWN param1=3...")
    m = mavutil.mavlink_connection(port, baud=baud)
    if m.wait_heartbeat(timeout=5) is None:
        fail("lost heartbeat before reboot — FC may already be in bootloader")
        m.close()
        return True  # not fatal; proceed to flash
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN,
                            0, 3, 0, 0, 0, 0, 0, 0)
    ok("MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN param1=3 sent")
    m.close()
    step("waiting up to 8 s for heartbeat to stop...")
    # quick disconnect then poll for absence
    time.sleep(3)
    # We don't strictly need to confirm — uploader.py will handle the bootloader handshake.
    ok("3 s elapsed — uploader.py will take it from here")
    return True


# ---------- Stage 5: flash via 02_flash_fc.py (uploader.py)

def stage_flash(port, apj_path):
    banner(5, 8, "Flash via ArduPilot uploader.py")
    cmd = [PY, str(CLONE_SCRIPTS / "02_flash_fc.py"),
           "--port", port, "--apj", apj_path]
    step(f"running: 02_flash_fc.py (this takes 60-90 s)")
    rc = run_streamed(cmd)
    if rc != 0:
        fail(f"02_flash_fc.py exited {rc}")
        return False
    ok("flash complete")
    return True


# ---------- Stage 6: wait for AP to come back

def stage_wait_resume(port, baud):
    banner(6, 8, "Wait for ArduPilot firmware to come back")
    step("8 s boot quiet (per feedback_bf_boot_cycle_quiet)...")
    time.sleep(8)
    step("polling for heartbeat (up to 30 s)...")
    from pymavlink import mavutil
    # The post-flash port may have a new USB serial path; re-detect.
    deadline = time.time() + 30
    while time.time() < deadline:
        new_port, _ = find_port()
        if not new_port:
            time.sleep(1)
            continue
        try:
            m = mavutil.mavlink_connection(new_port, baud=baud)
            hb = m.wait_heartbeat(timeout=3)
            if hb is not None:
                m.close()
                ok(f"heartbeat resumed on {new_port}: sys={hb.type}")
                return new_port
            m.close()
        except Exception:
            pass
        time.sleep(1)
    fail("AP did not come back within 30 s — manual recovery may be needed")
    return None


# ---------- Stage 7: param restore (calls 03_push_params.py with 3 passes)

def stage_restore(port, baud, out_dir):
    banner(7, 8, "Restore params (3-pass)")
    source = out_dir / "full_dump.json"
    cmd = [PY, str(CLONE_SCRIPTS / "03_push_params.py"),
           "--port", port, "--baud", str(baud),
           "--source", str(source),
           "--out", str(out_dir),
           "--passes", "3"]
    step("running: 03_push_params.py --passes 3")
    rc = run_streamed(cmd)
    if rc != 0:
        fail(f"03_push_params.py exited {rc}")
        return False
    ok("restore complete")
    return True


# ---------- Stage 8: calibration verification
#
# After the 3-pass restore lands, this confirms that the *specifically
# calibration-critical* params actually match the source dump. The 03_push
# report's `remaining_diffs` lumps everything together; this isolates the
# params that, if mismatched, would force the operator to re-do the EKF /
# compass / accel / RC / battery calibration on the bench.
#
# Pattern matching uses fnmatch (shell globs). A param is in a group if it
# matches ANY pattern in that group.

CAL_PARAM_GROUPS = {
    "compass cal":     ["COMPASS_OFS*", "COMPASS_OFS2_*", "COMPASS_OFS3_*",
                        "COMPASS_DIA*", "COMPASS_DIA2_*", "COMPASS_DIA3_*",
                        "COMPASS_ODI*", "COMPASS_ODI2_*", "COMPASS_ODI3_*",
                        "COMPASS_MOT*", "COMPASS_MOT2_*", "COMPASS_MOT3_*",
                        "COMPASS_DEV_ID*", "COMPASS_USE*", "COMPASS_PRIO*_ID",
                        "COMPASS_ORIENT*", "COMPASS_EXTERN*", "COMPASS_SCALE*",
                        "COMPASS_AUTO_ROT"],
    "accel/gyro cal":  ["INS_ACC*OFFS_*", "INS_ACC*SCAL_*",
                        "INS_GYR*OFFS_*", "INS_GYROFFS_*",
                        "INS_ACCOFFS_*", "INS_ACCSCAL_*",
                        "INS_*_ID", "INS_USE*"],
    "board orient":    ["AHRS_ORIENTATION", "AHRS_TRIM_*"],
    "ESC/motor cal":   ["MOT_PWM_MIN", "MOT_PWM_MAX", "MOT_SPIN_MIN",
                        "MOT_SPIN_MAX", "MOT_SPIN_ARM", "MOT_THST_HOVER",
                        "MOT_THST_EXPO"],
    "battery cal":     ["BATT*_VOLT_MULT", "BATT*_AMP_PERVLT",
                        "BATT*_AMP_OFFSET", "BATT*_VOLT_PIN", "BATT*_CURR_PIN",
                        "BATT*_CAPACITY"],
    "RC cal":          ["RC*_MIN", "RC*_MAX", "RC*_TRIM",
                        "RC*_REVERSED", "RC*_DZ"],
    "baro cal":        ["BARO*_GND_TEMP", "BARO*_DEVID", "BARO_PROBE_EXT"],
}

# Params known to differ legitimately on every flash; surface but don't flag as failure
EXPECTED_DIFFER = {"BARO1_GND_PRESS", "BARO2_GND_PRESS", "BARO3_GND_PRESS"}


def _fnmatch_any(name, patterns):
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def _match_value(a, b, ptype):
    """Same tolerance logic as 03_push_params.py match()."""
    # MAV_PARAM_TYPE_REAL32 = 9, REAL64 = 10
    if ptype in (9, 10):
        if a == 0 and b == 0:
            return True
        return abs(a - b) / max(abs(a), abs(b), 1e-9) < 1e-5
    try:
        return int(round(a)) == int(round(b))
    except Exception:
        return a == b


def stage_verify_calibration(out_dir):
    banner(8, 8, "Verify calibration params preserved")
    src_path = out_dir / "full_dump.json"
    after_path = out_dir / "target_after.json"
    if not src_path.exists() or not after_path.exists():
        fail(f"missing source ({src_path.exists()}) or target_after ({after_path.exists()})")
        return False

    with open(src_path) as f:
        src = json.load(f)
    with open(after_path) as f:
        after = json.load(f)

    all_groups_match = True
    expected_diffs_seen = []

    for group, patterns in CAL_PARAM_GROUPS.items():
        cal_names = [n for n in src if _fnmatch_any(n, patterns)]
        if not cal_names:
            continue
        step(f"checking {group} ({len(cal_names)} param(s))")
        matched, diffs, missing = [], [], []
        for name in cal_names:
            src_val = src[name]["value"]
            ptype = src[name].get("type", 9)
            if name not in after:
                missing.append((name, src_val))
                continue
            tgt_val = after[name]["value"]
            if _match_value(src_val, tgt_val, ptype):
                matched.append(name)
            elif name in EXPECTED_DIFFER:
                expected_diffs_seen.append((name, src_val, tgt_val))
                matched.append(name)  # treat as match for group accounting
            else:
                diffs.append((name, src_val, tgt_val))
        total = len(cal_names)
        if not diffs and not missing:
            ok(f"{group}: {len(matched)}/{total} match")
        else:
            all_groups_match = False
            if diffs:
                fail(f"{group}: {len(diffs)} DIFFER (out of {total})")
                for n, sv, tv in diffs[:6]:
                    info(f"    {n}: source={sv}  target={tv}")
                if len(diffs) > 6:
                    info(f"    ... and {len(diffs) - 6} more")
            if missing:
                fail(f"{group}: {len(missing)} MISSING from target (out of {total})")
                for n, sv in missing[:6]:
                    info(f"    {n} (source value {sv})")
                if len(missing) > 6:
                    info(f"    ... and {len(missing) - 6} more")

    if expected_diffs_seen:
        info("")
        info(f"({len(expected_diffs_seen)} expected-differ values skipped: "
             f"{', '.join(n for n, _, _ in expected_diffs_seen[:5])})")

    print()
    if all_groups_match:
        ok("ALL calibration params preserved — no recalibration needed")
    else:
        fail("Some calibration params differ — review above before flying")
        fail("Likely action: recalibrate the affected subsystem(s) on the bench")
    return all_groups_match


# ---------- subprocess helper that streams output indented

def run_streamed(cmd):
    """Run cmd, stream its combined stdout+stderr to ours with `         ` indent."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1)
    for line in proc.stdout:
        print(f"         {line.rstrip()}", flush=True)
    return proc.wait()


# ---------- Final summary

def print_summary(out_dir):
    print(f"\n{'=' * 60}")
    print("=== DONE ===")
    print(f"{'=' * 60}")
    report_path = out_dir / "push_report.json"
    if report_path.exists():
        with open(report_path) as f:
            r = json.load(f)
        print(f"  source params      : {r['source_params']}")
        print(f"  target after flash : {r['target_params_after']}")
        print(f"  already matching   : {r['already_matching']}")
        print(f"  newly set          : {r['newly_set']}")
        print(f"  missing on target  : {len(r['missing_on_target'])}")
        print(f"  failed to set      : {len(r['failed_to_set'])}")
        print(f"  remaining diffs    : {len(r['remaining_diffs'])}")
        if r["remaining_diffs"]:
            diff_names = [d[0] for d in r["remaining_diffs"][:10]]
            print(f"  diff sample        : {diff_names}")
            if "BARO1_GND_PRESS" in diff_names:
                print("    (BARO1_GND_PRESS is expected — live atmospheric reading)")
    print(f"\n  dump folder: {out_dir}")


# ---------- Main

def main():
    ap = argparse.ArgumentParser(description="ArduPilot fleet-flash orchestrator.")
    ap.add_argument("--port", default=None, help="Override port autodetect")
    ap.add_argument("--baud", type=int, default=None, help="Override baud autodetect")
    ap.add_argument("--apj", default=None,
                    help="Skip the interactive picker — use this .apj path")
    args = ap.parse_args()

    # Port
    if args.port:
        port, baud = args.port, args.baud or 115200
    else:
        port, baud = find_port()
        if args.baud:
            baud = args.baud
    if not port:
        fail("no FC port found (/dev/cu.usbmodem* missing, no usbserial-0001)")
        return 1

    # === Stage 1
    info_blob = stage_detect(port, baud)
    if info_blob is None:
        return 2

    # Build per-run output dir
    ts = datetime.now().strftime("%Y-%m-%d-%H%M")
    board_label = str(info_blob.get("board_id") or "unknown")
    out_dir = DUMP_ROOT / f"{ts}-board{board_label}"

    # === Stage 2
    if not stage_dump(port, baud, out_dir):
        return 3

    # === Stage 3: list candidates; caller (Claude) will use AskUserQuestion
    candidates = stage_pick_apj(info_blob.get("board_id"))
    if not candidates:
        return 4

    # If --apj passed, use it; else ask the user via stdin (Claude turn).
    if args.apj:
        apj_path = args.apj
    else:
        # We can't AskUserQuestion from inside the script — print a clear marker
        # and exit so the caller (Claude) can ask the user, then re-invoke with --apj.
        info("")
        info("RE-RUN with --apj <path> to continue past this stage.")
        info(f"available .apj files were enumerated above (1-{len(candidates)}).")
        info(f"dump is saved at: {out_dir}")
        return 10  # signal "need user input"

    ok_validate, meta = validate_apj(apj_path, info_blob.get("board_id"))
    if not ok_validate:
        return 5

    # === Stage 4
    if not stage_reboot_to_bl(port, baud):
        return 6

    # === Stage 5
    if not stage_flash(port, apj_path):
        return 7

    # === Stage 6
    new_port = stage_wait_resume(port, baud)
    if not new_port:
        return 8
    port = new_port

    # === Stage 7
    if not stage_restore(port, baud, out_dir):
        return 9

    # === Stage 8: calibration verification (non-fatal — always report)
    cal_ok = stage_verify_calibration(out_dir)

    print_summary(out_dir)
    return 0 if cal_ok else 11


if __name__ == "__main__":
    sys.exit(main())
