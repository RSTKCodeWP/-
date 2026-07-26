#!/usr/bin/env python3
"""Step 2 (target FC): Flash an ArduPilot .apj onto the connected FC.

Wraps ArduPilot's uploader.py. If uploader.py isn't on disk, downloads it
from the ardupilot repo matching the firmware's git_identity.

Usage:
  ./02_flash_fc.py --port /dev/cu.usbmodem1101 --apj ./clone_source/firmware/arducopter.apj

Requires: curl, /usr/bin/python3 with pymavlink + pyserial.
"""
import argparse, json, os, subprocess, sys, urllib.request

UPLOADER_URL_TEMPLATE = "https://raw.githubusercontent.com/ArduPilot/ardupilot/{ref}/Tools/scripts/uploader.py"

def fetch_uploader(ref, dst):
    url = UPLOADER_URL_TEMPLATE.format(ref=ref)
    print(f"downloading uploader.py from {url}", flush=True)
    urllib.request.urlretrieve(url, dst)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbmodem1101")
    ap.add_argument("--apj", required=True, help="Path to arducopter.apj")
    ap.add_argument("--uploader", default="/tmp/uploader.py",
                    help="Path to ArduPilot uploader.py (downloaded if missing)")
    ap.add_argument("--uploader-ref", default="master",
                    help="ardupilot git ref to fetch uploader.py from (e.g. Copter-4.6.3)")
    args = ap.parse_args()

    if not os.path.exists(args.apj):
        print(f"ERROR: apj not found: {args.apj}", file=sys.stderr); sys.exit(1)

    with open(args.apj) as f:
        meta = json.load(f)
    print(f".apj board_id={meta.get('board_id')} summary={meta.get('summary')} "
          f"git_identity={meta.get('git_identity')} image_size={meta.get('image_size')}", flush=True)

    if not os.path.exists(args.uploader):
        fetch_uploader(args.uploader_ref, args.uploader)

    cmd = ["/usr/bin/python3", args.uploader, "--port", args.port, args.apj]
    print(f"running: {' '.join(cmd)}", flush=True)
    subprocess.check_call(cmd)

if __name__ == "__main__":
    main()
