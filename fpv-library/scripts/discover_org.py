#!/usr/bin/env python3
"""Discover all repositories from a GitHub org and register them for full git mirroring."""

from __future__ import annotations

import argparse
import sys

from fpv_lib.catalog import find_entry, load_catalog, now_iso, org_repo_path, save_catalog, upsert_entry
from fpv_lib.gh import GhError, list_org_repos
from fpv_lib.scoring import score_repo
from fpv_lib.triage import triage_entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Discover GitHub org repos for library mirroring")
    parser.add_argument("--org", required=True, help="GitHub organization (e.g. OpenIPC)")
    parser.add_argument(
        "--verdict",
        default="keep",
        help="Force triage verdict for all org repos (default: keep)",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.0,
        help="Skip repos below this relevance score (default: 0 = include all)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    catalog = load_catalog()
    try:
        repos = list_org_repos(args.org)
    except GhError as exc:
        print(f"org-error {args.org}: {exc}", file=sys.stderr)
        return 1

    added = 0
    updated = 0
    skipped = 0

    for repo in sorted(repos, key=lambda r: r.get("full_name", "")):
        source = repo["full_name"]
        score = score_repo(repo)
        if score < args.min_score:
            skipped += 1
            continue

        path = org_repo_path(source)
        existing = find_entry(catalog, source)

        if args.dry_run:
            if existing:
                print(f"would-update {source} -> {path}")
            else:
                print(f"would-add {source} -> {path}")
            continue

        upsert_entry(
            catalog,
            source=source,
            path=path,
            description=repo.get("description") or "",
            stars=int(repo.get("stargazers_count") or 0),
            discovered_via=f"org:{args.org}",
            score=score,
            upstream_updated=repo.get("pushed_at") or repo.get("updated_at"),
        )
        entry = find_entry(catalog, source)
        if entry is None:
            continue

        entry["size_kb"] = int(repo.get("size") or 0)
        entry["topics"] = repo.get("topics") or []
        entry["verdict"] = args.verdict
        entry["triage_at"] = now_iso()
        entry.update(triage_entry(entry))

        if existing is None:
            added += 1
            print(f"added {source} -> {path}")
        elif existing.get("path") != path:
            updated += 1
            print(f"repath {source} -> {path}")
        else:
            updated += 1
            print(f"updated {source}")

    if not args.dry_run:
        save_catalog(catalog)

    print(
        f"org:{args.org} total={len(repos)} added={added} updated={updated} skipped={skipped}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
