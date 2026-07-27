#!/usr/bin/env python3
"""Download Caddx Ascent .img from official GitHub Releases manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "repos/Caddx-Ascent-Firmware_Release-Caddx-Ascent-Firmware-Release/manifest.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Caddx Ascent firmware images")
    parser.add_argument(
        "device",
        nargs="?",
        help="deviceId (e.g. Ascent_G_Gnd) or 'all'",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="path to manifest.json from Caddx-Ascent-Firmware_Release repo",
    )
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "firmware-images",
        help="output directory",
    )
    args = parser.parse_args()

    if not args.manifest.exists():
        print(f"manifest not found: {args.manifest}")
        print("sync: python3 fpv-library/scripts/sync.py --source CaddxFPV-Tech/Caddx-Ascent-Firmware_Release")
        return 1

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    release = data["releases"][0]
    devices = release["devices"]

    if not args.device:
        print(f"Release {release['tag']} — {release.get('changelogUrl', '')}\n")
        for d in devices:
            f = d["files"][0]
            mb = f["size"] // 1024 // 1024
            print(f"  {d['deviceId']:16} {d['role']:4} chip={d['chip']}  {f['name']}  ({mb} MB)")
        print("\nExample: download_caddx_firmware.py Ascent_G_Gnd")
        return 0

    selected = devices if args.device == "all" else [d for d in devices if d["deviceId"] == args.device]
    if not selected:
        print(f"Unknown deviceId: {args.device}")
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    for d in selected:
        f = d["files"][0]
        dest = args.out / f["name"]
        print(f"Downloading {f['name']} ...")
        urllib.request.urlretrieve(f["url"], dest)
        sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        expected = f.get("sha256", "")
        if expected and sha != expected:
            print(f"SHA256 mismatch: {sha} != {expected}")
            return 1
        print(f"OK {dest} ({dest.stat().st_size} bytes, sha256 verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
