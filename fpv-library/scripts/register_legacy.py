#!/usr/bin/env python3
"""Register legacy top-level example mirrors in catalog.json."""

from __future__ import annotations

import sys
from pathlib import Path

from fpv_lib.catalog import load_catalog, save_catalog, upsert_entry

# Hand-maintained map of example copies already at repo root
LEGACY: list[dict[str, str]] = [
    {"source": "johnboiles/Steer", "path": "Steer-iOS-RC-Car-FPV"},
    {"source": "bobberdolle1/SkySweep32", "path": "SkySweep32-ESP32-Drone-Detector"},
    {"source": "skaml2021/fly-or-no_fly", "path": "fly-or-no_fly-RaspberryPi-FPV-Flight-Monitor"},
    {"source": "FPVibe/fpv-inventory", "path": "fpv-inventory-Deno-FPV-Parts-Inventory"},
    {"source": "svpcom/wfb-ng", "path": "wfb-ng-WiFi-FPV-Long-Range-Radio-Link"},
    {"source": "AlexSchrader/fpv-boat", "path": "fpv-boat-RaspberryPi-Quest-VR-RC-Boat"},
]


def main() -> int:
    catalog = load_catalog()
    for item in LEGACY:
        upsert_entry(
            catalog,
            source=item["source"],
            path=item["path"],
            discovered_via="legacy-example",
            legacy=True,
        )
    save_catalog(catalog)
    print(f"Registered {len(LEGACY)} legacy example repos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
