#!/usr/bin/env python3
"""Sync tracked repositories from upstream GitHub as full git mirrors."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from fpv_lib.catalog import catalog_path, library_root, load_catalog, now_iso, save_catalog
from fpv_lib.gh import default_branch_sha, GhError, repo_details
from fpv_lib.verify import verify_mirror


META_FILE = ".fpv-library.json"
MIRROR_MODE = "full-git-submodule"


def monorepo_root() -> Path:
    return library_root().parent


def is_in_monorepo() -> bool:
    return (monorepo_root() / ".git").is_dir()


def submodule_paths() -> set[str]:
    root = monorepo_root()
    result = subprocess.run(
        ["git", "config", "--file", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return set()
    paths: set[str] = set()
    for line in result.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            paths.add(parts[1].strip())
    return paths


def is_registered_submodule(rel_path: str) -> bool:
    return rel_path in submodule_paths()


class GitError(RuntimeError):
    pass


def write_meta(dest: Path, entry: dict) -> None:
    """Write sidecar metadata (untracked inside submodules — catalog.json is canonical)."""
    if is_registered_submodule(str(dest.relative_to(monorepo_root()))):
        return
    meta = {
        "source": entry["source"],
        "mirror_mode": MIRROR_MODE,
        "upstream_commit": entry.get("upstream_commit"),
        "upstream_updated": entry.get("upstream_updated"),
        "synced_at": entry.get("synced_at"),
        "discovered_via": entry.get("discovered_via"),
        "score": entry.get("score"),
    }
    (dest / META_FILE).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def is_git_mirror(dest: Path) -> bool:
    git_dir = dest / ".git"
    return dest.is_dir() and git_dir.exists()


def is_mirrored(entry: dict) -> bool:
    dest = library_root().parent / entry["path"]
    return is_git_mirror(dest)


def is_legacy_snapshot(entry: dict) -> bool:
    """Shallow file copy from older sync runs (no .git directory)."""
    dest = library_root().parent / entry["path"]
    return dest.exists() and (dest / META_FILE).exists() and not is_git_mirror(dest)


def run_git(args: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise GitError(detail or f"git {' '.join(args)} failed")
    return result


def ensure_lfs(cwd: Path) -> None:
    if shutil.which("git-lfs") is None:
        return
    run_git(["lfs", "install", "--local"], cwd=cwd, check=False)
    run_git(["lfs", "pull"], cwd=cwd, check=False)


def init_submodules(cwd: Path) -> None:
    run_git(["submodule", "update", "--init", "--recursive"], cwd=cwd, check=False)


def local_head_sha(dest: Path) -> str | None:
    result = run_git(["rev-parse", "HEAD"], cwd=dest, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def clone_full(source: str, dest: Path) -> None:
    url = f"https://github.com/{source}.git"
    rel_path = str(dest.relative_to(monorepo_root()))
    dest.parent.mkdir(parents=True, exist_ok=True)

    if is_in_monorepo() and not is_registered_submodule(rel_path):
        if dest.exists():
            shutil.rmtree(dest)
        subprocess.run(
            ["git", "rm", "-rf", "--cached", rel_path],
            cwd=monorepo_root(),
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "submodule", "add", "--force", url, rel_path],
            cwd=monorepo_root(),
            check=True,
            capture_output=True,
            text=True,
        )
        dest = monorepo_root() / rel_path
    else:
        if dest.exists():
            shutil.rmtree(dest)
        run_git(["clone", url, str(dest)], cwd=dest.parent)

    ensure_lfs(dest)
    init_submodules(dest)


def update_mirror(dest: Path, *, branch: str) -> None:
    run_git(["fetch", "--all", "--tags", "--prune"], cwd=dest)
    run_git(["reset", "--hard", f"origin/{branch}"], cwd=dest)
    run_git(["clean", "-fd"], cwd=dest)
    ensure_lfs(dest)
    init_submodules(dest)


def sync_entry(
    entry: dict,
    *,
    dry_run: bool = False,
    force_reclone: bool = False,
    skip_verify: bool = False,
) -> str:
    source = entry["source"]
    dest = library_root().parent / entry["path"]

    try:
        repo = repo_details(source)
        branch = repo.get("default_branch", "main")
        sha, pushed_at = default_branch_sha(source)
    except GhError as exc:
        return f"error {source}: {exc}"

    legacy = is_legacy_snapshot(entry)
    mirrored = is_mirrored(entry)
    local_sha = local_head_sha(dest) if mirrored else None

    if mirrored and not force_reclone and not legacy:
        if entry.get("upstream_commit") == sha and local_sha == sha:
            if not skip_verify and not dry_run:
                ok, detail = verify_mirror(dest, expected_sha=sha, branch=branch)
                if ok:
                    entry["verified_at"] = now_iso()
                    return f"up-to-date {source} verified"
                # local drift — force refresh
                action = "update"
            elif dry_run:
                return f"up-to-date {source}"
            else:
                return f"up-to-date {source}"
        else:
            action = "update"
    elif legacy or force_reclone:
        action = "reclone"
    elif dest.exists() and not mirrored:
        action = "reclone"
    else:
        action = "clone"

    if dry_run:
        return f"would-{action} {source} -> {sha[:8]}"

    if action in ("clone", "reclone"):
        clone_full(source, dest)
    else:
        update_mirror(dest, branch=branch)

    entry["upstream_commit"] = sha
    entry["upstream_updated"] = pushed_at
    entry["synced_at"] = now_iso()
    write_meta(dest, entry)

    if not skip_verify:
        ok, detail = verify_mirror(dest, expected_sha=sha, branch=branch)
        if not ok:
            raise GitError(f"verify failed: {detail}")
        entry["verified_at"] = now_iso()
        return f"{action}d {source} @ {sha[:8]} verified"

    return f"{action}d {source} @ {sha[:8]}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync FPV library repos as full git mirrors")
    parser.add_argument("--all", action="store_true", help="Sync every catalog entry with a path")
    parser.add_argument("--source", action="append", help="Sync specific owner/repo")
    parser.add_argument("--owner", help="Sync all catalog entries from this GitHub owner/org")
    parser.add_argument("--verdict", default=None, help="Only sync entries with this triage verdict (e.g. keep)")
    parser.add_argument("--max-size-mb", type=int, default=0, help="Skip mirrors larger than this MB (0=no limit)")
    parser.add_argument(
        "--update-only",
        action="store_true",
        help="Only refresh repos already mirrored (full git clone on disk)",
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
    parser.add_argument(
        "--force-reclone",
        action="store_true",
        help="Delete and re-clone even if already mirrored (migrates legacy snapshots)",
    )
    parser.add_argument(
        "--roots-only",
        action="store_true",
        help="Only sync catalog entries at monorepo root (no slash in path)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip post-sync integrity check (not recommended)",
    )
    args = parser.parse_args(argv)

    if not catalog_path().exists():
        print("No catalog.json found. Run discover.py first.", file=sys.stderr)
        return 1

    catalog = load_catalog()
    entries = catalog.get("repos", [])

    if args.source:
        selected = [e for e in entries if e["source"] in args.source]
    elif args.owner:
        owner = args.owner.lower()
        selected = [e for e in entries if e.get("source", "").lower().startswith(f"{owner}/")]
    elif args.all:
        selected = [e for e in entries if e.get("path")]
    else:
        parser.error("Use --all, --source owner/repo, or --owner OrgName")

    if args.verdict:
        selected = [e for e in selected if e.get("verdict") == args.verdict]

    if args.roots_only:
        selected = [e for e in selected if e.get("path") and "/" not in e["path"]]

    if args.update_only:
        selected = [
            e
            for e in selected
            if is_mirrored(e) or is_legacy_snapshot(e) or e.get("synced_at")
        ]

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
    for entry in selected:
        try:
            force = args.force_reclone or is_legacy_snapshot(entry)
            result = sync_entry(
                entry,
                dry_run=args.dry_run,
                force_reclone=force,
                skip_verify=args.skip_verify,
            )
            print(result)
            if result.startswith(
                ("cloned", "updated", "recloned", "would-clone", "would-update", "would-reclone")
            ):
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
