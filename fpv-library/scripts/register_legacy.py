#!/usr/bin/env python3
"""Register top-level project folders in catalog.json for daily mirror sync."""

from __future__ import annotations

import sys
from pathlib import Path

from fpv_lib.catalog import find_entry, load_catalog, now_iso, save_catalog, upsert_entry
from fpv_lib.folders import (
    infer_source_from_name,
    is_skipped,
    list_top_level_dirs,
    meta_source,
    workspace_root,
)
from fpv_lib.folders import git_remote_source

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
    "claude-mgrsosd-Betaflight-OSD-Layout-Claude-Plugin": "paulnurkkala/claude-mgrsosd",
    "claude-osdfont-Betaflight-OSD-Font-Claude-Plugin": "paulnurkkala/claude-osdfont",
    "claude-rctest-Betaflight-RC-Test-Claude-Plugin": "paulnurkkala/claude-rctest",
    "claude-satest-Betaflight-SmartAudio-Claude-Plugin": "paulnurkkala/claude-satest",
    "fpv-tools-Deno-Browser-Betaflight-Utilities": "FPVibe/fpv-tools",
    "fpvibe-github-io-FPVibe-Org-Website": "FPVibe/fpvibe.github.io",
    "FPVibe-github-Org-Profile-Defaults": "FPVibe/.github",
    "flowchart-Node-FPV-Training-Tracker-PWA": "FPVibe/flowchart",
    "docs-FPVibe-Federation-Architecture-Specs": "FPVibe/docs",
    "django-password-reset-Django-Password-Reset-Views": "FPVibe/django-password-reset",
    "Django-Pushbullet-Django-Pushbullet-Integration": "FPVibe/Django-Pushbullet",
    "django-templated-email-Django-Templated-Email": "FPVibe/django-templated-email",
    "commgamers-us-COMMGamers-Website": "RSTKCodeWP/commgamers.us",
    "comm-slackbot-Slack-COMMGamers-Bot": "RSTKCodeWP/comm-slackbot",
    "dronewars2026-HTML-Drone-Wars-2026": "RSTKCodeWP/dronewars2026",
    "leoflight-dual-thrustmasters-Jetson-Dual-Thrustmaster-MAVLink": "RSTKCodeWP/leoflight-dual-thrustmasters",
    "maixcam-servo-control-AI-Ballistic-Servo-MaixCAM": "RSTKCodeWP/maixcam-servo-control",
    "maixcam-wildtrap-AI-Camera-Trap-MaixCAM": "RSTKCodeWP/maixcam-wildtrap",
    "MEANduino-MEAN-Server-Arduino-Data": "RSTKCodeWP/MEANduino",
    "openflash-Rust-NAND-Flash-Programmer": "RSTKCodeWP/openflash",
    "Pico-Nand-Flasher-RaspberryPi-Pico-NAND": "RSTKCodeWP/Pico-Nand-Flasher",
    "RCGroupsScraper-Python-RCGroups-Search-Notifier": "RSTKCodeWP/RCGroupsScraper",
    "sausage-Java-Sausage-App": "RSTKCodeWP/sausage",
    "sedona-trip-planner-Leaflet-Sedona-Trip-Map": "RSTKCodeWP/sedona-trip-planner",
    "stellar-js-Parallax-Scrolling-Library": "RSTKCodeWP/stellar-js",
    "TUCapstone12-TU-Orals-Quiz-Web-App": "RSTKCodeWP/TUCapstone12",
    "unbound-Lua-Universal-DPI-Bypass": "RSTKCodeWP/unbound",
    "uptimerobot-Python-UptimeRobot-API-Wrapper": "RSTKCodeWP/uptimerobot",
    "wordpress-s3-migration-script-WordPress-S3-Migration": "RSTKCodeWP/wordpress-s3-migration-script",
    "wpcustposttype-WordPress-Custom-Post-Types": "RSTKCodeWP/wpcustposttype",
    "zyloweathergetter-JavaScript-Weather-Getter": "RSTKCodeWP/zyloweathergetter",
    "at32f435-rgt7-manual-AT32-Flight-Controller-Manual": "RSTKCodeWP/at32f435-rgt7-manual",
}

SKIP_REGISTER = {"AeroStab", "OpenIPC", "OpenHD", "DroneBridge", "ArduPilot"}


def resolve_source(item: Path, catalog: dict) -> str | None:
    return (
        MANUAL.get(item.name)
        or meta_source(item)
        or git_remote_source(item)
        or infer_source_from_name(item.name, catalog)
    )


def main() -> int:
    catalog = load_catalog()
    added = 0
    updated = 0

    for item in list_top_level_dirs():
        if item.name in SKIP_REGISTER:
            continue

        source = resolve_source(item, catalog)
        if not source:
            print(f"skip (no source): {item.name}")
            continue

        existing = find_entry(catalog, source)
        if existing:
            if existing.get("path") != item.name:
                existing["path"] = item.name
                updated += 1
                print(f"repath {source} -> {item.name}")
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
            entry["verdict"] = "keep"
            entry["registered_at"] = now_iso()
        added += 1
        print(f"registered {source} -> {item.name}")

    save_catalog(catalog)
    print(f"Done. New: {added}, repath: {updated}")

    # Refresh MAP.md when folders are registered
    try:
        from generate_library_map import main as gen_map

        gen_map()
    except Exception as exc:  # noqa: BLE001
        print(f"map warning: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
