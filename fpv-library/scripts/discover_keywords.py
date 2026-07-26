#!/usr/bin/env python3
"""Run rotating keyword searches from keywords.txt and triage new hooks."""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

from discover import discover_search, expand_owner
from fpv_lib.catalog import load_catalog, save_catalog
from fpv_lib.gh import GhError, repo_details
from fpv_lib.triage import triage_entry

KEYWORDS_FILE = Path(__file__).resolve().parents[1] / "keywords.txt"


def load_keywords() -> list[str]:
    if not KEYWORDS_FILE.exists():
        return ["Fpv"]
    lines: list[str] = []
    for line in KEYWORDS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def pick_queries(all_queries: list[str], *, batch_size: int, rotate: bool) -> list[str]:
    if not rotate or batch_size >= len(all_queries):
        return all_queries
    # Stable daily rotation: same day => same batch
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    seed = int(hashlib.sha256(day.encode()).hexdigest(), 16)
    start = seed % len(all_queries)
    selected: list[str] = []
    for i in range(batch_size):
        selected.append(all_queries[(start + i) % len(all_queries)])
    return selected


def enrich_and_triage(catalog: dict, source: str) -> None:
    entry = next((r for r in catalog["repos"] if r["source"].lower() == source.lower()), None)
    if not entry or entry.get("triage_at"):
        return
    try:
        details = repo_details(source)
        entry["size_kb"] = int(details.get("size") or 0)
        entry["topics"] = details.get("topics") or []
        if not entry.get("stars"):
            entry["stars"] = int(details.get("stargazers_count") or 0)
        if not entry.get("description"):
            entry["description"] = details.get("description") or ""
    except GhError:
        pass
    result = triage_entry(entry)
    entry.update(result)
    entry["triage_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def triage_all_pending(catalog: dict) -> int:
    updated = 0
    for entry in catalog.get("repos", []):
        if entry.get("triage_at"):
            continue
        if entry.get("legacy"):
            entry.update(triage_entry(entry))
            entry["triage_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            updated += 1
            continue
        enrich_and_triage(catalog, entry["source"])
        if entry.get("triage_at"):
            updated += 1
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Keyword-based FPV repo discovery")
    parser.add_argument("--pages", default="1", help="Pages per keyword (e.g. 1-2)")
    parser.add_argument("--min-score", type=float, default=2.0)
    parser.add_argument("--batch-size", type=int, default=12, help="Keywords per run when rotating")
    parser.add_argument("--no-rotate", action="store_true", help="Run all keywords")
    parser.add_argument("--expand-owners", action="store_true")
    parser.add_argument("--owner-limit", type=int, default=3)
    parser.add_argument("--triage-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if "-" in args.pages:
        start, end = args.pages.split("-", 1)
        pages = list(range(int(start), int(end) + 1))
    else:
        pages = [int(args.pages)]

    catalog = load_catalog()
    before = len(catalog.get("repos", []))

    if not args.triage_only:
        queries = pick_queries(load_keywords(), batch_size=args.batch_size, rotate=not args.no_rotate)
        print(f"keywords this run ({len(queries)}): {', '.join(queries)}", flush=True)
        owners_seen: set[str] = set()
        for query in queries:
            print(f"\n=== {query!r} ===", flush=True)
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
            # collect owners from latest search results via catalog additions is indirect;
            # re-search for owner expansion on high-value queries only
            if args.expand_owners:
                from fpv_lib.gh import search_repos

                for page in pages:
                    try:
                        for repo in search_repos(query, page=page):
                            owners_seen.add(repo["owner"]["login"])
                    except GhError:
                        pass
        if args.expand_owners:
            for owner in sorted(owners_seen):
                print(f"\n=== owner:{owner} ===", flush=True)
                for line in expand_owner(
                    catalog,
                    owner,
                    min_score=args.min_score,
                    dry_run=args.dry_run,
                    max_repos=args.owner_limit,
                ):
                    print(line, flush=True)

    if not args.dry_run:
        triaged = triage_all_pending(catalog)
        catalog.setdefault("keyword_runs", []).append(
            {
                "at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "batch_size": args.batch_size,
                "triage_updated": triaged,
            }
        )
        save_catalog(catalog)

    after = len(catalog.get("repos", []))
    keeps = sum(1 for r in catalog.get("repos", []) if r.get("verdict") == "keep")
    watches = sum(1 for r in catalog.get("repos", []) if r.get("verdict") == "watch")
    print(f"\nadded {after - before} repos (total {after}) | keep={keeps} watch={watches}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
