#!/usr/bin/env python3
"""Run multiple themed GitHub searches and owner expansions for FPV library."""

from __future__ import annotations

import argparse
import sys

from fpv_lib.catalog import load_catalog, save_catalog
from discover import discover_search, expand_owner

# Themed searches for FPV link, GCS, fiber, IP control
SEARCHES = [
    "fpv ground control station",
    "fpv gcs mavlink",
    "fpv fiber optic",
    "optical fiber fpv drone",
    "wifibroadcast fpv",
    "wfb-ng",
    "openipc fpv",
    "fpv video link",
    "expresslrs mavlink",
    "msp displayport osd",
    "fpv repeater",
    "fpv datalink",
    "drone ground station",
    "mavlink fpv",
    "betaflight osd",
    # Round 2 — IP control, LTE, DJI mods, swarm GCS, fiber C-UAV
    "openhd lte mavlink",
    "fpv rtsp ethernet camera",
    "wtfos dji fpv",
    "dji o3 air unit",
    "dji o4 air unit",
    "walksnail avatar",
    "walksnail ascent",
    "rubyfpv digital",
    "runcam wifilink",
    "emax nanohawk fpv",
    "opencv fpv drone",
    "dji vista fpv",
    "avatar hd vtx",
    "elrs wifi joystick",
    "drone swarm ground station",
    "fiber optic drone tether",
    "mavlink osd overlay",
    "fpv ip camera ground station",
    "meshtastic drone telemetry",
    "madflight esp32 fpv",
]

# Owners likely to have related ecosystem repos
OWNERS = [
    "svpcom",
    "OpenIPC",
    "ExperimentalDesignBureau-1571",
    "rubenCodeforges",
    "AlexSchrader",
    "johnboiles",
    "skaml2021",
    "bobberdolle1",
    "paulnurkkala",
    "FPVibe",
    "iNavFlight",
    "RotorHazard",
    "pokrc",
    "ajain189",
    "OpenHD",
    "DroneBridge",
    "betaflight",
    "ArduPilot",
    # Round 2 — ecosystems from themed discovery
    "fpv-wtf",
    "altnautica",
    "skybrush-io",
    "asv-soft",
    "KenLagoni",
    "flyspark015",
    "rmeadomavic",
    "coroiu",
    "ExpressLRS",
    "zenos01",
    "jusstinn",
    "Consti10",
    "Dexon-Drones",
    "iBz-04",
    "kaack",
    "MishkaRogachev",
    "CaddxFPV-Tech",
    "fpv-wtf",
    "RubyFPV",
    "EmaxModel",
    "avsaase",
    "shellixyz",
    "alejopdl",
    "wkumik",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", default="1-2", help="Pages per search query")
    parser.add_argument("--min-score", type=float, default=2.5)
    parser.add_argument("--owner-limit", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if "-" in args.pages:
        start, end = args.pages.split("-", 1)
        pages = list(range(int(start), int(end) + 1))
    else:
        pages = [int(args.pages)]

    catalog = load_catalog()
    before = len(catalog.get("repos", []))

    for query in SEARCHES:
        print(f"\n=== search: {query!r} ===", flush=True)
        for line in discover_search(
            catalog,
            query,
            pages,
            min_score=args.min_score,
            dry_run=args.dry_run,
            expand_owners=False,
            owner_limit=0,
        ):
            print(line, flush=True)

    for owner in OWNERS:
        print(f"\n=== owner: {owner} ===", flush=True)
        for line in expand_owner(
            catalog,
            owner,
            min_score=args.min_score,
            dry_run=args.dry_run,
            max_repos=args.owner_limit,
        ):
            print(line, flush=True)

    if not args.dry_run:
        save_catalog(catalog)

    after = len(catalog.get("repos", []))
    print(f"\nadded {after - before} new repos (total {after})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
