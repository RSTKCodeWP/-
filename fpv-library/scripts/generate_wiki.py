#!/usr/bin/env python3
"""Build wiki/ exhibition cards from catalog entries that exist on disk."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from fpv_lib.wiki import (  # noqa: E402
    HALLS,
    build_dossier,
    render_alphabet,
    render_hall,
    render_home,
    render_library,
    render_project,
    render_sidebar,
    slug_for,
)

ROOT = SCRIPTS.parents[1]
CATALOG = ROOT / "fpv-library" / "catalog.json"
WIKI = ROOT / "wiki"


def load_entries() -> tuple[list[dict], list[dict]]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows = list(catalog.get("repos") or [])
    by_path: dict[str, dict] = {}
    rank = {"keep": 0, "watch": 1, "skip": 2}
    for entry in rows:
        rel = entry.get("path") or ""
        if not rel:
            continue
        current = by_path.get(rel)
        if current is None or rank.get(entry.get("verdict"), 9) < rank.get(current.get("verdict"), 9):
            by_path[rel] = entry
    selected = list(by_path.values())
    if (ROOT / "AeroStab").is_dir() and "AeroStab" not in by_path:
        selected.append(
            {
                "source": "",
                "path": "AeroStab",
                "verdict": "own",
                "own": True,
                "categories": ["own"],
                "description": "",
                "owner": "RSTKCodeWP",
            }
        )
    return selected, rows


def unique_slug(entry: dict, used: set[str]) -> str:
    base = slug_for(entry.get("source") or "", entry.get("path") or "")
    slug = base
    n = 2
    while slug in used:
        slug = f"{base}-{n}"
        n += 1
    used.add(slug)
    return slug


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def clean_generated(keep: set[Path]) -> None:
    if not WIKI.exists():
        return
    for folder in (WIKI / "projects", WIKI / "halls"):
        if not folder.exists():
            continue
        for path in folder.glob("*.md"):
            if path.resolve() not in keep:
                path.unlink()


def main() -> int:
    if not CATALOG.exists():
        print(f"catalog not found: {CATALOG}", file=sys.stderr)
        return 1
    entries, catalog_rows = load_entries()
    catalog_total = len(catalog_rows)
    present_rows = sum(
        1 for entry in catalog_rows if (ROOT / (entry.get("path") or "")).is_dir()
    )
    used: set[str] = set()
    cards: list[dict] = []
    pages: dict[Path, str] = {}
    for entry in sorted(entries, key=lambda e: (e.get("source") or e.get("path") or "").lower()):
        dossier = build_dossier(entry, ROOT)
        if dossier is None:
            continue
        slug = unique_slug(entry, used)
        dossier_card = {
            "title": dossier["title"],
            "source": dossier["source"],
            "path": dossier["path"],
            "description": dossier["description"],
            "idea": dossier["idea"],
            "hall": dossier["hall"],
            "slug": slug,
            "own": dossier["own"],
        }
        cards.append(dossier_card)
        pages[WIKI / "projects" / f"{slug}.md"] = render_project(dossier, slug)

    by_hall: dict[str, list[dict]] = {hall_id: [] for hall_id in HALLS}
    for card in cards:
        by_hall.setdefault(card["hall"], []).append(card)
    for hall_id, hall_cards in by_hall.items():
        hall_cards.sort(key=lambda c: (c["source"] or c["path"]).lower())
        if not hall_cards:
            continue
        pages[WIKI / "halls" / f"{hall_id}.md"] = render_hall(hall_id, hall_cards)

    hall_counts = [(hall_id, len(by_hall.get(hall_id, []))) for hall_id in HALLS]
    own_count = sum(1 for card in cards if card["own"] or card["hall"] == "own")
    pages[WIKI / "Home.md"] = render_home(
        {
            "catalog": catalog_total,
            "dossiers": len(cards),
            "absent": catalog_total - present_rows,
            "own": own_count,
        },
        hall_counts,
    )
    pages[WIKI / "Alphabet.md"] = render_alphabet(cards)
    pages[WIKI / "Library.md"] = render_library()
    pages[WIKI / "_Sidebar.md"] = render_sidebar(hall_counts)

    keep = {path.resolve() for path in pages}
    clean_generated(keep)
    for path, text in pages.items():
        write(path, text)
    print(f"wrote {len(cards)} project cards in {WIKI}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
