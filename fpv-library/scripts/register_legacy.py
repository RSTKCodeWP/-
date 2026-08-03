#!/usr/bin/env python3
"""Register top-level project folders in catalog.json for daily mirror sync."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from fpv_lib.catalog import find_entry, load_catalog, save_catalog, upsert_entry

WORKSPACE = Path(__file__).resolve().parents[2]
SKIP_DIRS = {
    "fpv-library",
    "docs",
    "logs",
    ".github",
    "AeroStab",
    "node_modules",
    ".venv",
    "__pycache__",
}

# Hand-maintained when folder name does not match GitHub source
MANUAL: dict[str, str] = {
    "Steer-iOS-RC-Car-FPV": "johnboiles/Steer",
    "SkySweep32-ESP32-Drone-Detector": "bobberdolle1/SkySweep32",
    "fly-or-no_fly-RaspberryPi-FPV-Flight-Monitor": "skaml2021/fly-or-no_fly",
    "fpv-inventory-Deno-FPV-Parts-Inventory": "FPVibe/fpv-inventory",
    "wfb-ng-WiFi-FPV-Long-Range-Radio-Link": "svpcom/wfb-ng",
    "fpv-boat-RaspberryPi-Quest-VR-RC-Boat": "AlexSchrader/fpv-boat",
    "ardufleetcheck-Python-ArduPilot-Fleet-Check-Skills": "paulnurkkala/ardufleetcheck",
    "hackrf-vtx-elrs-monitor-HackRF-FPV-VTX-ELRS-Monitor": "paulnurkkala/hackrf-vtx-elrs-monitor",
    "GyroChad-Rust-FPV-Drone-AI-Bot": "bobberdolle1/GyroChad",
}


def git_remote_source(path: Path) -> str | None:
    if not (path / ".git").exists():
        return None
    try:
        out = subprocess.check_output(
            ["git", "-C", str(path), "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", out)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return None


def meta_source(path: Path) -> str | None:
    meta = path / ".fpv-library.json"
    if not meta.exists():
        return None
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
        return data.get("source")
    except (json.JSONDecodeError, OSError):
        return None


def main() -> int:
    catalog = load_catalog()
    added = 0

    for item in sorted(WORKSPACE.iterdir()):
        if not item.is_dir() or item.name in SKIP_DIRS or item.name.startswith("."):
            continue

        source = MANUAL.get(item.name) or meta_source(item) or git_remote_source(item)
        if not source:
            print(f"skip (no source): {item.name}")
            continue

        if find_entry(catalog, source):
            entry = find_entry(catalog, source)
            if entry and entry.get("path") != item.name:
                entry["path"] = item.name
            continue

        upsert_entry(
            catalog,
            source=source,
            path=item.name,
            discovered_via="root-register",
            legacy=True,
        )
        entry = find_entry(catalog, source)
        if entry:
            entry["verdict"] = entry.get("verdict") or "keep"
        added += 1
        print(f"registered {source} -> {item.name}")

    save_catalog(catalog)
    print(f"Done. New registrations: {added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
