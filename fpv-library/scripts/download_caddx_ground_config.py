#!/usr/bin/env python3
"""Download Caddx Ground Configuration Windows releases from official GitHub."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "manifests/Caddx_Ground_Configuration_Release.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download Caddx Ground Configuration (Windows) from GitHub Releases"
    )
    parser.add_argument(
        "asset",
        nargs="?",
        help="asset id: setup, portable, full, delta — or 'all' for latest release",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="path to Caddx_Ground_Configuration_Release manifest",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="release tag (default: latest in manifest, e.g. v0.3.3)",
    )
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "ground-config",
        help="output directory",
    )
    args = parser.parse_args()

    if not args.manifest.exists():
        print(f"manifest not found: {args.manifest}")
        return 1

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    releases = data["releases"]
    release = next((r for r in releases if r["tag"] == args.tag), releases[0])

    if not args.asset:
        print(f"Release {release['tag']} ({release['releaseDate']})")
        print(release.get("notes", ""))
        print(f"Changelog: {release.get('changelogUrl', '')}\n")
        for a in release["assets"]:
            mb = a["size"] // 1024 // 1024
            print(f"  {a['id']:10} {a['kind']:12} {a['name']}  ({mb} MB)")
        print("\nExample: download_caddx_ground_config.py setup")
        return 0

    selected = (
        release["assets"]
        if args.asset == "all"
        else [a for a in release["assets"] if a["id"] == args.asset]
    )
    if not selected:
        print(f"Unknown asset id: {args.asset}")
        print("Available:", ", ".join(a["id"] for a in release["assets"]))
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    for a in selected:
        dest = args.out / a["name"]
        print(f"Downloading {a['name']} ...")
        urllib.request.urlretrieve(a["url"], dest)
        sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        expected = a.get("sha256", "")
        if expected and sha != expected:
            print(f"SHA256 mismatch: {sha} != {expected}")
            return 1
        print(f"OK {dest} ({dest.stat().st_size} bytes, sha256 verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
