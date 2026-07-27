#!/usr/bin/env python3
"""Aggressive funnel discovery: broad drone/FPV queries + owner expansion."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from discover import discover_search, expand_owner
from fpv_lib.catalog import load_catalog, save_catalog
from fpv_lib.gh import GhError

QUERIES_FILE = Path(__file__).resolve().parents[1] / "funnel-queries.txt"

# Seed owners — expanded even if search misses them
SEED_OWNERS = [
    "EdgeTX",
    "edgetx",
    "opentx",
    "OpenTX",
    "ExpressLRS",
    "iNavFlight",
    "betaflight",
    "ArduPilot",
    "mavlink",
    "DroneBridge",
    "OpenHD",
    "OpenIPC",
    "fpv-wtf",
    "meshtastic",
    "rotorhazard",
    "hdzero-technologies",
    "HDZeroTech",
    "qqqlab",
    "madflight",
    "rotorflight",
    "KipK",
    "mavlink-router",
    "pymavlink",
    "blheli32",
    "stylesuxx",
    "sunghwan7788",
    "dronetag",
    "bortekv",
    "RSTKCodeWP",
    "CaddxFPV-Tech",
    "umeow0716",
]


def load_queries(path: Path) -> list[str]:
    if not path.exists():
        return []
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def run_with_retry(fn, *args, retries: int = 4, **kwargs):
    delay = 8
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except GhError as exc:
            if "rate limit" in str(exc).lower() and attempt < retries - 1:
                print(f"rate limit, sleep {delay}s ...", flush=True)
                time.sleep(delay)
                delay *= 2
                continue
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Funnel discovery for drone/FPV repos")
    parser.add_argument("--pages", default="1-2")
    parser.add_argument("--min-score", type=float, default=1.8)
    parser.add_argument("--owner-limit", type=int, default=20)
    parser.add_argument("--queries", type=Path, default=QUERIES_FILE)
    parser.add_argument("--no-expand", action="store_true")
    parser.add_argument("--owners-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if "-" in args.pages:
        start, end = args.pages.split("-", 1)
        pages = list(range(int(start), int(end) + 1))
    else:
        pages = [int(args.pages)]

    catalog = load_catalog()
    before = len(catalog.get("repos", []))
    queries = load_queries(args.queries)

    if not args.owners_only:
        for i, query in enumerate(queries, 1):
            print(f"\n[{i}/{len(queries)}] === search: {query!r} ===", flush=True)
            messages = discover_search(
                catalog,
                query,
                pages,
                min_score=args.min_score,
                dry_run=args.dry_run,
                expand_owners=not args.no_expand,
                owner_limit=args.owner_limit,
            )
            for line in messages:
                print(line, flush=True)
            if not args.dry_run:
                save_catalog(catalog)
            time.sleep(1.5)

    for owner in SEED_OWNERS:
        print(f"\n=== seed owner: {owner} ===", flush=True)
        try:
            messages = expand_owner(
                catalog,
                owner,
                min_score=args.min_score,
                dry_run=args.dry_run,
                max_repos=args.owner_limit,
            )
        except GhError as exc:
            print(f"owner-error {owner}: {exc}", flush=True)
            if "rate limit" in str(exc).lower():
                time.sleep(30)
            continue
        for line in messages:
            print(line, flush=True)
        if not args.dry_run:
            save_catalog(catalog)
        time.sleep(1)

    if not args.dry_run:
        save_catalog(catalog)

    after = len(catalog.get("repos", []))
    print(f"\nFUNNEL DONE: {before} -> {after} (+{after - before})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
