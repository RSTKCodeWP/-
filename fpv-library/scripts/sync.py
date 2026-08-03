#!/usr/bin/env python3
"""Sync tracked repositories from upstream GitHub."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from fpv_lib.catalog import catalog_path, find_entry, library_root, load_catalog, now_iso, save_catalog
from fpv_lib.gh import default_branch_sha, GhError


META_FILE = ".fpv-library.json"
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".pytest_cache"}


def write_meta(dest: Path, entry: dict) -> None:
    meta = {
        "source": entry["source"],
        "upstream_commit": entry.get("upstream_commit"),
        "upstream_updated": entry.get("upstream_updated"),
        "synced_at": entry.get("synced_at"),
        "discovered_via": entry.get("discovered_via"),
        "score": entry.get("score"),
    }
    (dest / META_FILE).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def is_mirrored(entry: dict) -> bool:
    dest = library_root().parent / entry["path"]
    return dest.exists() and (dest / META_FILE).exists()


def clone_upstream(source: str, dest: Path, *, depth: int = 1) -> None:
    url = f"https://github.com/{source}.git"
    cmd = ["git", "clone"]
    if depth > 0:
        cmd += ["--depth", str(depth)]
    cmd += [url, str(dest)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def sync_entry(entry: dict, *, dry_run: bool = False) -> str:
    source = entry["source"]
    rel_path = entry["path"]
    dest = library_root().parent / rel_path

    try:
        sha, pushed_at = default_branch_sha(source)
    except GhError as exc:
        return f"error {source}: {exc}"

    if entry.get("upstream_commit") == sha and dest.exists() and (dest / META_FILE).exists():
        return f"up-to-date {source}"

    if dry_run:
        return f"would-update {source} -> {sha[:8]}"

    url = f"https://github.com/{source}.git"
    with tempfile.TemporaryDirectory(prefix="fpv-sync-") as tmp:
        clone_dir = Path(tmp) / "repo"
        clone_upstream(source, clone_dir)
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            clone_dir,
            dest,
            symlinks=True,
            ignore_dangling_symlinks=True,
            ignore=shutil.ignore_patterns(*SKIP_DIRS),
            dirs_exist_ok=True,
        )
        git_dir = dest / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir)

    entry["upstream_commit"] = sha
    entry["upstream_updated"] = pushed_at
    entry["synced_at"] = now_iso()
    write_meta(dest, entry)
    return f"updated {source} @ {sha[:8]}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync FPV library repos from GitHub")
    parser.add_argument("--all", action="store_true", help="Sync every catalog entry under fpv-library/repos/")
    parser.add_argument("--source", action="append", help="Sync specific owner/repo")
    parser.add_argument("--verdict", default=None, help="Only sync entries with this triage verdict (e.g. keep)")
    parser.add_argument("--max-size-mb", type=int, default=0, help="Skip mirrors larger than this MB (0=no limit)")
    parser.add_argument(
        "--update-only",
        action="store_true",
        help="Only refresh repos already mirrored (have synced_at or on disk)",
    )
    parser.add_argument(
        "--new-only",
        action="store_true",
        help="Only clone repos not yet mirrored",
    )
    parser.add_argument(
        "--max-per-run",
        type=int,
        default=0,
        help="Limit number of repos processed this run (0=unlimited)",
    )
    parser.add_argument(
        "--sort",
        choices=("score", "small", "added"),
        default="score",
        help="Order for --new-only: score (high first), small (size asc), added (oldest first)",
    )
    parser.add_argument(
        "--save-every",
        type=int,
        default=10,
        help="Save catalog.json every N updates (0=only at end)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not catalog_path().exists():
        print("No catalog.json found. Run discover.py first.", file=sys.stderr)
        return 1

    catalog = load_catalog()
    entries = catalog.get("repos", [])

    if args.source:
        selected = [e for e in entries if e["source"] in args.source]
    elif args.all:
        selected = [e for e in entries if e.get("path")]
    else:
        parser.error("Use --all or --source owner/repo")

    if args.verdict:
        selected = [e for e in selected if e.get("verdict") == args.verdict]

    if args.update_only:
        selected = [e for e in selected if is_mirrored(e) or e.get("synced_at")]

    if args.new_only:
        selected = [e for e in selected if not is_mirrored(e)]

    if args.max_size_mb:
        limit_kb = args.max_size_mb * 1024
        filtered = []
        for e in selected:
            size_kb = int(e.get("size_kb") or 0)
            if size_kb and size_kb > limit_kb:
                print(f"skip-large {e['source']} ({size_kb // 1024} MB)")
                continue
            filtered.append(e)
        selected = filtered

    if args.sort == "score":
        selected.sort(key=lambda e: (-(e.get("score") or 0), e.get("source", "")))
    elif args.sort == "small":
        selected.sort(key=lambda e: (int(e.get("size_kb") or 0), e.get("source", "")))
    elif args.sort == "added":
        selected.sort(key=lambda e: (e.get("added_at") or "", e.get("source", "")))

    if args.max_per_run and len(selected) > args.max_per_run:
        selected = selected[: args.max_per_run]

    if not selected:
        print("No matching catalog entries.")
        return 0

    changed = 0
    errors = 0
    for i, entry in enumerate(selected, 1):
        try:
            result = sync_entry(entry, dry_run=args.dry_run)
            print(result)
            if result.startswith("updated") or result.startswith("would-update"):
                changed += 1
                if args.save_every and changed % args.save_every == 0 and not args.dry_run:
                    save_catalog(catalog)
        except Exception as exc:  # noqa: BLE001 — continue syncing other repos
            errors += 1
            print(f"error {entry['source']}: {exc}", file=sys.stderr)

    if not args.dry_run and changed:
        save_catalog(catalog)
    if errors:
        print(f"finished with {errors} error(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
