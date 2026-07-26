#!/usr/bin/env python3
"""Re-triage all catalog entries and write HOOKS.md report."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from discover_keywords import enrich_and_triage, triage_all_pending
from fpv_lib.catalog import library_root, load_catalog, save_catalog
from fpv_lib.triage import triage_entry


def write_hooks_report(catalog: dict) -> Path:
    repos = catalog.get("repos", [])
    interesting = [
        r for r in repos
        if r.get("interesting") and r.get("verdict") in ("keep", "watch")
    ]
    interesting.sort(key=lambda r: (r.get("verdict") != "keep", -(r.get("score") or 0)))

    watch = [r for r in repos if r.get("verdict") == "watch"]
    watch.sort(key=lambda r: -(r.get("score") or 0))

    lines = [
        "# FPV Library — discovery hooks",
        "",
        f"Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Interesting (auto-flagged)",
        "",
        "| Source | Verdict | Score | Categories | Why |",
        "|--------|---------|-------|------------|-----|",
    ]
    for r in interesting[:60]:
        cats = ", ".join(r.get("categories") or [])
        desc = (r.get("description") or "")[:60].replace("|", "/")
        lines.append(
            f"| [{r['source']}](https://github.com/{r['source']}) "
            f"| {r.get('verdict', '?')} | {r.get('score', '-')} "
            f"| {cats} | {desc} |"
        )

    lines += [
        "",
        "## Watch list (weak hook — review manually)",
        "",
        "| Source | Score | Reason |",
        "|--------|-------|--------|",
    ]
    for r in watch[:40]:
        lines.append(
            f"| [{r['source']}](https://github.com/{r['source']}) "
            f"| {r.get('score', '-')} | {r.get('triage_reason', '')} |"
        )

    out = library_root() / "HOOKS.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-triage even reviewed entries")
    args = parser.parse_args()

    catalog = load_catalog()
    if args.force:
        for entry in catalog.get("repos", []):
            entry.pop("triage_at", None)
            if entry.get("legacy"):
                entry.update(triage_entry(entry))
                entry["triage_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            else:
                enrich_and_triage(catalog, entry["source"])
    else:
        triage_all_pending(catalog)

    path = write_hooks_report(catalog)
    save_catalog(catalog)

    keeps = sum(1 for r in catalog["repos"] if r.get("verdict") == "keep")
    watches = sum(1 for r in catalog["repos"] if r.get("verdict") == "watch")
    skips = sum(1 for r in catalog["repos"] if r.get("verdict") == "skip")
    print(f"triage: keep={keeps} watch={watches} skip={skips}")
    print(f"report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
