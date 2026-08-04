#!/usr/bin/env python3
"""Expand discovery upward (owners/orgs) and outward (similar repos from our base)."""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from datetime import datetime, timezone

from discover import add_repo, discover_search
from discover_org import main as discover_org_main
from fpv_lib.catalog import load_catalog, org_repo_path, save_catalog
from fpv_lib.gh import GhError, is_github_org, list_all_repos_for_owner
from fpv_lib.scoring import score_repo
from fpv_lib.similarity import owners_from_catalog, similarity_queries


def pick_batch(items: list[str], *, batch_size: int, salt: str) -> list[str]:
    if batch_size >= len(items):
        return items
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    seed = int(hashlib.sha256(f"{salt}:{day}".encode()).hexdigest(), 16)
    start = seed % len(items)
    return [items[(start + i) % len(items)] for i in range(batch_size)]


def expand_owner_all(
    catalog: dict,
    owner: str,
    *,
    min_score: float,
    dry_run: bool,
) -> list[str]:
    messages: list[str] = []
    try:
        repos = list_all_repos_for_owner(owner)
    except GhError as exc:
        messages.append(f"owner-error {owner}: {exc}")
        return messages

    use_org_paths = is_github_org(owner)
    for repo in sorted(repos, key=score_repo, reverse=True):
        score = score_repo(repo)
        if score < min_score:
            continue
        result = add_repo(
            catalog,
            repo,
            discovered_via=f"expand-owner:{owner}",
            min_score=min_score,
            dry_run=dry_run,
            path=org_repo_path(repo["full_name"]) if use_org_paths else None,
        )
        if result and result.startswith(("added", "would-add")):
            messages.append(result)
    return messages


def discover_orgs_for_owners(catalog: dict, owners: list[str], *, dry_run: bool) -> list[str]:
    messages: list[str] = []
    for owner in owners:
        if not is_github_org(owner):
            continue
        if dry_run:
            messages.append(f"would-discover-org {owner}")
            continue
        rc = discover_org_main(["--org", owner, "--verdict", "keep", "--min-score", "0"])
        if rc == 0:
            messages.append(f"discover-org {owner}")
        time.sleep(1)
    return messages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Expand discovery from catalog base")
    parser.add_argument("--owner-batch", type=int, default=12, help="Owners to fully expand per run")
    parser.add_argument("--org-batch", type=int, default=5, help="Orgs to register fully per run")
    parser.add_argument("--similar-batch", type=int, default=8, help="Similarity queries per run")
    parser.add_argument("--pages", default="1", help="Search pages per similarity query")
    parser.add_argument("--min-score", type=float, default=1.5, help="Min score for expanded owner repos")
    parser.add_argument("--similar-min-score", type=float, default=2.0, help="Min score for similarity search hits")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if "-" in args.pages:
        start, end = args.pages.split("-", 1)
        pages = list(range(int(start), int(end) + 1))
    else:
        pages = [int(args.pages)]

    catalog = load_catalog()
    before = len(catalog.get("repos", []))
    owners = owners_from_catalog(catalog)

    print(f"=== Phase 1: expand orgs from catalog ({len(owners)} owners) ===", flush=True)
    org_owners = [o for o in pick_batch(owners, batch_size=args.org_batch, salt="orgs") if is_github_org(o)]
    for line in discover_orgs_for_owners(catalog, org_owners, dry_run=args.dry_run):
        print(line, flush=True)
    if not args.dry_run:
        save_catalog(catalog)

    print(f"=== Phase 2: expand all repos from owners (batch {args.owner_batch}) ===", flush=True)
    for owner in pick_batch(owners, batch_size=args.owner_batch, salt="owners"):
        print(f"\n--- owner:{owner} ---", flush=True)
        for line in expand_owner_all(catalog, owner, min_score=args.min_score, dry_run=args.dry_run):
            print(line, flush=True)
        if not args.dry_run:
            save_catalog(catalog)
        time.sleep(1)

    print("=== Phase 3: similarity search from our base ===", flush=True)
    queries = pick_batch(similarity_queries(catalog), batch_size=args.similar_batch, salt="similar")
    print(f"queries: {queries}", flush=True)
    for query in queries:
        print(f"\n--- similar:{query!r} ---", flush=True)
        for line in discover_search(
            catalog,
            query,
            pages,
            min_score=args.similar_min_score,
            dry_run=args.dry_run,
            expand_owners=True,
            owner_limit=0,
        ):
            print(line, flush=True)
        if not args.dry_run:
            save_catalog(catalog)
        time.sleep(1.5)

    if not args.dry_run:
        save_catalog(catalog)

    after = len(catalog.get("repos", []))
    print(f"\nEXPAND DONE: {before} -> {after} (+{after - before})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
