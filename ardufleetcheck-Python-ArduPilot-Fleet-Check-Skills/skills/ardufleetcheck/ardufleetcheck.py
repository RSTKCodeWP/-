#!/usr/bin/env python3
"""ardufleetcheck — run the full AP fleet pipeline in one shot.

Stages:
  1. /arduflash       — dump → pick .apj → flash → restore params → cal verify
  2. /mgrsosd         — push the AP MGRS OSD param block
  3. /osdfont clarity — set OSD font to Clarity (AP ROMFS path)
  4. /satest          — VTX sanity test (R1→R2→R1 via PARAM_SET)
  5. /rctest          — RC input check (RC_CHANNELS + SYS_STATUS RC bit)

Sub-skills autodetect AP vs BF, but where they accept an explicit firmware
flag we pass `ardupilot` for safety. No 10 s BF boot-quiet between stages —
AP doesn't reboot per stage.

Two-call workflow (mirrors /arduflash):
  - First call without --apj: /arduflash exits code 10 after enumerating
    .apj candidates. ardufleetcheck propagates that exit code so Claude can
    AskUserQuestion, then re-run with --apj <path>.
  - With --apj: full 5-stage run end-to-end.

Skip individual stages with --skip a,b,c (names: arduflash,mgrsosd,osdfont,satest,rctest).
"""
import argparse
import glob
import subprocess
import sys
import time
from pathlib import Path

PY = "/usr/bin/python3"
SKILLS = Path.home() / ".claude" / "skills"


def log(msg):
    print(f"[ardufleetcheck] {msg}", flush=True)


def banner(name):
    print(f"\n{'=' * 60}", flush=True)
    log(f"=== {name} ===")
    print(f"{'=' * 60}", flush=True)


def preflight_port_check():
    """Confirm FC enumerated + no other tool holds the port. Mirrors /fleetcheck."""
    ports = glob.glob("/dev/cu.usbmodem*")
    if not ports:
        log("ABORT: no /dev/cu.usbmodem* enumerated — is the AP drone plugged in?")
        return False
    for p in ports:
        out = subprocess.run(["lsof", p], capture_output=True, text=True).stdout
        if out.strip():
            owner = out.strip().splitlines()[-1].split()[0]
            log(f"ABORT: {p} is held by {owner!r}. Close MissionPlanner/QGC/Pilot 2 first.")
            return False
    return True


def stage_argv(name, args):
    """Return the argv (after python interpreter) for a given stage."""
    if name == "arduflash":
        argv = [str(SKILLS / "arduflash" / "arduflash.py")]
        if args.apj:
            argv += ["--apj", args.apj]
        return argv
    if name == "mgrsosd":
        return [str(SKILLS / "mgrsosd" / "mgrsosd.py")]
    if name == "osdfont":
        return [str(SKILLS / "osdfont" / "osdfont.py"), args.font]
    if name == "satest":
        # explicit --firmware ardupilot per user's "indicate this is AP" instruction
        return [str(SKILLS / "satest" / "satest.py"), "--firmware", "ardupilot"]
    if name == "rctest":
        return [str(SKILLS / "rctest" / "rctest.py"), "--force-ap"]
    if name == "canarm":
        return [str(SKILLS / "canarm" / "canarm.py")]
    if name == "loadmission":
        return [str(SKILLS / "loadmission" / "loadmission.py"),
                "--plan", args.mission_plan]
    raise ValueError(f"unknown stage: {name}")


STAGES = ["arduflash", "mgrsosd", "osdfont", "satest", "rctest", "canarm", "loadmission"]


def main():
    ap = argparse.ArgumentParser(
        description="Run /arduflash + /mgrsosd + /osdfont + /satest + /rctest in order on the AP drone.",
    )
    ap.add_argument("--apj", default=None,
                    help="Path to the .apj firmware. If omitted, stage 1 (/arduflash) "
                         "will enumerate candidates and exit with code 10 so the operator "
                         "can pick one. Re-run with --apj <chosen> to continue.")
    ap.add_argument("--font", default="clarity",
                    help="OSD font passed to /osdfont (default: clarity)")
    ap.add_argument("--mission-plan", default=None,
                    help="Path to QGC .plan to upload via /loadmission. "
                         "If omitted, the /loadmission stage auto-skips "
                         "(missions are per-deployment, not per-fleet-check).")
    ap.add_argument("--skip", default="",
                    help="Comma-separated stage names to skip (e.g. 'arduflash' if already flashed).")
    args = ap.parse_args()

    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    unknown_skips = skip - set(STAGES)
    if unknown_skips:
        log(f"ABORT: unknown --skip name(s): {sorted(unknown_skips)}. "
            f"Valid: {STAGES}")
        return 2

    if not preflight_port_check():
        return 3

    results = []
    t0 = time.time()
    for name in STAGES:
        if name in skip:
            log(f"--skip {name}, moving on")
            results.append((name, "skipped"))
            continue

        # /loadmission is opt-in via --mission-plan. If no path was given,
        # silently skip the stage — missions are per-deployment, not part of
        # the standard post-build check.
        if name == "loadmission" and not args.mission_plan:
            log(f"no --mission-plan; skipping /loadmission")
            results.append((name, "skipped"))
            continue

        banner(name)
        argv = stage_argv(name, args)
        rc = subprocess.call([PY] + argv)
        results.append((name, rc))

        # /arduflash exits with code 10 when no --apj was provided (picker stage).
        # That's not a failure — it's a "needs operator pick" signal. Propagate
        # immediately so Claude can run AskUserQuestion and re-invoke us.
        if name == "arduflash" and rc == 10:
            print()
            log("=" * 60)
            log("/arduflash needs an .apj pick — see stage 3 enumeration above.")
            log("Re-run with --apj <chosen-path> to continue through the rest of "
                "the pipeline (mgrsosd → osdfont → satest → rctest).")
            return 10

        # Hard-stop on /arduflash failure (no point doing OSD/VTX/RC after a
        # broken flash — the FC may be in bootloader or running stale firmware).
        if name == "arduflash" and rc != 0:
            log(f"/arduflash failed (rc={rc}). Aborting before downstream stages.")
            break

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    log(f"DONE in {elapsed:.1f}s")
    worst = 0
    for name, rc in results:
        if rc == "skipped":
            mark = "SKIP"
        elif rc == 0:
            mark = "PASS"
        else:
            mark = f"FAIL (rc={rc})"
            worst = max(worst, rc if isinstance(rc, int) else 1)
        print(f"  {mark:14s}  /{name}")
    return worst


if __name__ == "__main__":
    sys.exit(main())
