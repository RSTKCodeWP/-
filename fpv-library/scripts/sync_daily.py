#!/usr/bin/env python3
"""Daily mirror orchestrator — update existing + backfill new keep repos."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def run(cmd: list[str]) -> int:
    print("+", " ".join(cmd), flush=True)
    return subprocess.call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily FPV library mirror")
    parser.add_argument("--verdict", default="keep", help="Catalog verdict to mirror (default: keep)")
    parser.add_argument(
        "--backfill-per-run",
        type=int,
        default=25,
        help="Max new repos to clone per run (default: 25)",
    )
    parser.add_argument(
        "--max-size-mb",
        type=int,
        default=800,
        help="Skip cloning repos larger than this MB (0=no limit, default: 800)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sync = [sys.executable, str(SCRIPTS / "sync.py")]
    common = ["--verdict", args.verdict]
    if args.dry_run:
        common.append("--dry-run")

    print("=== Phase 1: update existing mirrors ===")
    rc = run(sync + ["--all", *common, "--update-only"])
    if rc:
        return rc

    print("=== Phase 2: backfill new mirrors ===")
    backfill = sync + [
        "--all",
        *common,
        "--new-only",
        "--max-per-run",
        str(args.backfill_per_run),
        "--sort",
        "score",
    ]
    if args.max_size_mb:
        backfill += ["--max-size-mb", str(args.max_size_mb)]
    rc = run(backfill)
    if rc:
        return rc

    print("=== Phase 3: priority list (force sync) ===")
    priority = SCRIPTS.parent / "priority-sync.txt"
    if priority.exists():
        for line in priority.read_text(encoding="utf-8").splitlines():
            src = line.split("#", 1)[0].strip()
            if not src:
                continue
            run(sync + ["--source", src, *common])

    print("=== Daily mirror done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
