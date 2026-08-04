#!/usr/bin/env python3
"""Discover FPV-related GitHub repositories and update catalog.json."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from fpv_lib.catalog import default_repo_path, find_entry, load_catalog, org_repo_path, save_catalog, upsert_entry
from fpv_lib.gh import GhError, is_github_org, list_owner_repos, search_repos
from fpv_lib.scoring import is_candidate, score_repo
from fpv_lib.triage import triage_entry
from fpv_lib.blocklist import is_blocked


def parse_pages(pages: list[int] | None, pages_range: str | None) -> list[int]:
    if pages:
        return pages
    if pages_range:
        if "-" in pages_range:
            start_s, end_s = pages_range.split("-", 1)
            return list(range(int(start_s), int(end_s) + 1))
        return [int(pages_range)]
    return [4]


def record_search(catalog: dict[str, Any], query: str, pages: list[int]) -> None:
    catalog.setdefault("search_queries", [])
    catalog["search_queries"].append({"query": query, "pages": pages})


def add_repo(
    catalog: dict[str, Any],
    repo: dict[str, Any],
    *,
    discovered_via: str,
    min_score: float,
    dry_run: bool,
    path: str | None = None,
) -> str | None:
    source = repo["full_name"]
    if is_blocked(source):
        return None
    score = score_repo(repo)
    if score < min_score:
        return None
    if find_entry(catalog, source):
        return f"exists {source}"
    if dry_run:
        return f"would-add {source} (score={score})"
    upsert_entry(
        catalog,
        source=source,
        path=path or default_repo_path(source, repo.get("description")),
        description=repo.get("description") or "",
        stars=int(repo.get("stargazers_count") or 0),
        discovered_via=discovered_via,
        score=score,
        upstream_updated=repo.get("pushed_at") or repo.get("updated_at"),
    )
    entry = find_entry(catalog, source)
    if entry:
        entry["size_kb"] = int(repo.get("size") or 0)
        entry["topics"] = repo.get("topics") or []
        entry.update(triage_entry(entry))
        from fpv_lib.catalog import now_iso

        entry["triage_at"] = now_iso()
    return f"added {source} (score={score}, {entry.get('verdict', '?') if entry else '?'})"


def expand_owner(
    catalog: dict[str, Any],
    owner: str,
    *,
    min_score: float,
    dry_run: bool,
    max_repos: int,
) -> list[str]:
    messages: list[str] = []
    try:
        repos = list_owner_repos(owner)
    except GhError as exc:
        messages.append(f"owner-error {owner}: {exc}")
        return messages

    ranked = sorted(repos, key=score_repo, reverse=True)
    use_org_paths = is_github_org(owner)
    added = 0
    for repo in ranked:
        if max_repos > 0 and added >= max_repos:
            break
        if not is_candidate(repo, min_score=min_score):
            continue
        result = add_repo(
            catalog,
            repo,
            discovered_via=f"owner:{owner}",
            min_score=min_score,
            dry_run=dry_run,
            path=org_repo_path(repo["full_name"]) if use_org_paths else None,
        )
        if result and result.startswith(("added", "would-add")):
            added += 1
            messages.append(result)
    return messages


def discover_search(
    catalog: dict[str, Any],
    query: str,
    pages: list[int],
    *,
    min_score: float,
    dry_run: bool,
    expand_owners: bool,
    owner_limit: int,
) -> list[str]:
    messages: list[str] = []
    owners_seen: set[str] = set()

    for page in pages:
        try:
            items = search_repos(query, page=page)
        except GhError as exc:
            messages.append(f"search-error page {page}: {exc}")
            continue
        messages.append(f"search page {page}: {len(items)} results")
        for repo in items:
            result = add_repo(
                catalog,
                repo,
                discovered_via=f"search:{query}:p{page}",
                min_score=min_score,
                dry_run=dry_run,
            )
            if result:
                messages.append(result)
            owners_seen.add(repo["owner"]["login"])

    if expand_owners:
        for owner in sorted(owners_seen):
            messages.extend(
                expand_owner(
                    catalog,
                    owner,
                    min_score=min_score,
                    dry_run=dry_run,
                    max_repos=owner_limit,
                )
            )
    return messages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Discover FPV repos on GitHub")
    parser.add_argument("--search", default="Fpv", help="GitHub search query")
    parser.add_argument("--page", type=int, action="append", dest="pages", help="Search page")
    parser.add_argument("--pages", dest="pages_range", help="Page range e.g. 1-5 or single page")
    parser.add_argument("--min-score", type=float, default=2.0)
    parser.add_argument("--expand-owners", action="store_true")
    parser.add_argument("--owner-limit", type=int, default=5, help="Max repos per owner on expand")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    pages = parse_pages(args.pages, args.pages_range)
    catalog = load_catalog()
    messages = discover_search(
        catalog,
        args.search,
        pages,
        min_score=args.min_score,
        dry_run=args.dry_run,
        expand_owners=args.expand_owners,
        owner_limit=args.owner_limit,
    )
    for line in messages:
        print(line)

    if not args.dry_run:
        record_search(catalog, args.search, pages)
        save_catalog(catalog)
        print(f"catalog: {len(catalog.get('repos', []))} repos tracked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
