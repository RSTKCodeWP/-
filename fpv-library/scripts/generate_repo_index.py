#!/usr/bin/env python3
"""Generate REPOS.md — full catalog of mirrored projects with size and dates."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "fpv-library" / "catalog.json"
OUTPUT = ROOT / "REPOS.md"

CATEGORY_LABELS = {
    "gcs": "Ground control stations (НСК)",
    "link": "Radio / video link (радіо, WFB, LTE)",
    "fc": "Flight controllers & firmware (FC)",
    "openipc": "OpenIPC / IP camera FPV",
    "osd": "OSD & overlays",
    "elrs": "ELRS / RC link",
    "goggles": "Goggles & VRX",
    "fiber": "Fiber / tether links",
    "detection": "Detection / RF sensing",
    "ai": "AI / vision / assistants",
    "tools": "Tools & utilities",
    "other": "Other / misc",
}

VERDICT_ORDER = {"keep": 0, "watch": 1, "skip": 2}


def human_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    if num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / 1024 / 1024:.1f} MB"
    return f"{num_bytes / 1024 / 1024 / 1024:.2f} GB"


def dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        out = subprocess.check_output(
            ["du", "-sb", str(path)],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return int(out.split()[0])
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        total = 0
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
        return total


def read_meta(path: Path) -> dict:
    meta = path / ".fpv-library.json"
    if meta.exists():
        try:
            return json.loads(meta.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def pick_date(entry: dict, meta: dict, path: Path) -> str:
    for key in ("upstream_updated", "synced_at", "triage_at", "added_at"):
        val = entry.get(key) or meta.get(key)
        if val:
            return str(val)[:10]
    if path.exists():
        return datetime.utcfromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
    return "—"


def short_desc(entry: dict) -> str:
    desc = (entry.get("description") or "").strip()
    if desc:
        return desc.replace("|", "\\|").replace("\n", " ")
    owner, _, name = entry.get("source", "/").partition("/")
    return f"{owner}/{name}" if name else entry.get("source", "")


def primary_category(entry: dict) -> str:
    cats = entry.get("categories") or ["other"]
    for cat in (
        "gcs",
        "link",
        "fc",
        "openipc",
        "goggles",
        "elrs",
        "fiber",
        "osd",
        "ai",
        "tools",
        "detection",
        "other",
    ):
        if cat in cats:
            return cat
    return cats[0] if cats else "other"


def row(entry: dict, size_cache: dict[str, int]) -> dict:
    rel = entry.get("path", "")
    full = ROOT / rel
    meta = read_meta(full)
    size = size_cache.get(rel, 0)
    return {
        "source": entry.get("source", ""),
        "desc": short_desc(entry),
        "path": rel,
        "link": f"[{rel}]({rel}/)" if rel else "—",
        "updated": pick_date(entry, meta, full),
        "size": human_size(size) if size else "—",
        "size_bytes": size,
        "verdict": entry.get("verdict", ""),
        "legacy": bool(entry.get("legacy")),
        "category": primary_category(entry),
        "exists": full.exists(),
    }


def build_size_cache(entries: list[dict]) -> dict[str, int]:
    cache: dict[str, int] = {e.get("path", ""): 0 for e in entries if e.get("path")}

    # fpv-library/repos — one du sweep
    repos_root = ROOT / "fpv-library" / "repos"
    if repos_root.is_dir():
        try:
            out = subprocess.check_output(
                ["du", "-sb", "--", str(repos_root)],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            # du -sb on directory gives total only; scan children
            out = subprocess.check_output(
                ["du", "-sb", *sorted(repos_root.iterdir(), key=lambda p: p.name.lower())],
                stderr=subprocess.DEVNULL,
                text=True,
                errors="replace",
            )
            for line in out.splitlines():
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    size_s, p = parts
                    rel = str(Path(p).relative_to(ROOT))
                    if rel in cache:
                        cache[rel] = int(size_s)
        except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
            pass

    for rel in list(cache.keys()):
        if cache[rel]:
            continue
        full = ROOT / rel
        if full.exists():
            cache[rel] = dir_size(full)
    return cache


def table_rows(rows: list[dict]) -> list[str]:
    lines = [
        "| GitHub | Опис | Тека | Оновлено | Розмір |",
        "|--------|------|------|----------|--------|",
    ]
    for r in rows:
        gh = f"[{r['source']}](https://github.com/{r['source']})" if r["source"] else "—"
        flag = "" if r["exists"] else " ⚠️"
        lines.append(
            f"| {gh} | {r['desc'][:120]} | {r['link']}{flag} | {r['updated']} | {r['size']} |"
        )
    return lines


def generate() -> str:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    entries = catalog.get("repos", [])
    size_cache = build_size_cache(entries)
    rows = [row(e, size_cache) for e in entries]

    total_bytes = sum(r["size_bytes"] for r in rows)
    synced = sum(1 for r in rows if r["exists"])
    keep = sum(1 for r in rows if r["verdict"] == "keep")

    lines = [
        "# Каталог репозиторіїв / Repository index",
        "",
        f"> Автогенерація: `python3 fpv-library/scripts/generate_repo_index.py`  ",
        f"> Оновлено каталогу: **{catalog.get('updated_at', '—')[:10]}**  ",
        f"> Проєктів: **{len(rows)}** · на диску: **{synced}** · `keep`: **{keep}** · сумарно: **{human_size(total_bytes)}**",
        "",
        "## Зміст",
        "",
        "- [Структура репозиторію](docs/STRUCTURE.md)",
        "- [FPV Library](fpv-library/README.md) · [Теми](fpv-library/THEMED.md) · [Hooks](fpv-library/HOOKS.md)",
        "- [Legacy-копії в корені](#legacy-копії-в-корені)",
        "- [Категорії](#за-категоріями)",
        "",
        "## Legacy-копії в корені",
        "",
        "Ручні копії з описовою назвою теки (`RepoName-Короткий-Опис`).",
        "",
    ]

    legacy_rows = sorted(
        [r for r in rows if r["legacy"]],
        key=lambda r: r["path"].lower(),
    )
    lines.extend(table_rows(legacy_rows))
    lines.append("")
    lines.append("## За категоріями")
    lines.append("")

    by_cat: dict[str, list[dict]] = {}
    for r in rows:
        if r["legacy"]:
            continue
        by_cat.setdefault(r["category"], []).append(r)

    for cat in sorted(by_cat.keys(), key=lambda c: (c == "other", c)):
        label = CATEGORY_LABELS.get(cat, cat)
        cat_rows = sorted(
            by_cat[cat],
            key=lambda r: (VERDICT_ORDER.get(r["verdict"], 9), r["source"].lower()),
        )
        lines.append(f"### {label} (`{cat}`) — {len(cat_rows)}")
        lines.append("")
        lines.extend(table_rows(cat_rows))
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "⚠️ — тека відсутня на диску (є в `catalog.json`, ще не синхронізовано або видалено)."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    if not CATALOG.exists():
        print(f"catalog not found: {CATALOG}", file=sys.stderr)
        return 1
    text = generate()
    OUTPUT.write_text(text + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
