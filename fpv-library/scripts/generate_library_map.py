#!/usr/bin/env python3
"""Generate MAP.md — navigation tree of every folder in the monorepo."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fpv_lib.folders import (
    ORG_CONTAINERS,
    infer_source_from_name,
    is_git_mirror,
    list_org_repos,
    list_top_level_dirs,
    meta_source,
    workspace_root,
)
from fpv_lib.folders import git_remote_source as folder_git_remote

ROOT = workspace_root()
CATALOG = ROOT / "fpv-library" / "catalog.json"
OUTPUT = ROOT / "MAP.md"
REPOS_INDEX = ROOT / "REPOS.md"


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
        out = subprocess.check_output(["du", "-sb", str(path)], stderr=subprocess.DEVNULL, text=True)
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


def catalog_by_path(catalog: dict) -> dict[str, dict]:
    return {e.get("path", ""): e for e in catalog.get("repos", []) if e.get("path")}


def folder_row(
    name: str,
    path: Path,
    catalog: dict,
    by_path: dict[str, dict],
) -> dict:
    rel = str(path.relative_to(ROOT)) if path != ROOT else name
    entry = by_path.get(rel) or by_path.get(name)
    source = (
        (entry or {}).get("source")
        or meta_source(path)
        or folder_git_remote(path)
        or infer_source_from_name(name, catalog)
    )
    return {
        "name": name,
        "path": rel,
        "link": f"[{rel}]({rel}/)",
        "source": source or "—",
        "gh": f"[{source}](https://github.com/{source})" if source and source != "—" else "—",
        "mirror": "✅ git" if is_git_mirror(path) else "📁 files",
        "verified": (entry or {}).get("verified_at", "")[:10] or "—",
        "size": human_size(dir_size(path)),
        "verdict": (entry or {}).get("verdict", "—"),
    }


def mermaid_section(rows: list[dict], org_children: dict[str, list[str]]) -> list[str]:
    lines = ["```mermaid", "flowchart TB"]
    lines.append('  root["RSTKCodeWP / monorepo"]')
    lines.append("  root --> fpvlib[fpv-library/]")
    lines.append("  root --> docs[docs/]")
    lines.append("  root --> repos[REPOS.md index]")

    for r in rows:
        if r["name"] in ("fpv-library", "docs"):
            continue
        node_id = re.sub(r"[^a-zA-Z0-9_]", "_", r["name"])[:40]
        label = r["name"].replace('"', "'")
        if r["name"] in ORG_CONTAINERS:
            lines.append(f'  root --> {node_id}["{label}/ org"]')
            for child in org_children.get(r["name"], [])[:12]:
                cid = re.sub(r"[^a-zA-Z0-9_]", "_", f"{r['name']}_{child}")[:50]
                lines.append(f'  {node_id} --> {cid}["{child}"]')
            extra = len(org_children.get(r["name"], [])) - 12
            if extra > 0:
                lines.append(f'  {node_id} --> {node_id}x["+{extra} more…"]')
        elif r.get("kind") == "own-product":
            lines.append(f'  root --> {node_id}["{label} ★ own"]')
        else:
            short = label[:28] + ("…" if len(label) > 28 else "")
            lines.append(f'  root --> {node_id}["{short}"]')

    lines.append("```")
    return lines


def table(headers: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(row) + " |")
    return out


def generate() -> str:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8")) if CATALOG.exists() else {"repos": []}
    by_path = catalog_by_path(catalog)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    top_dirs = list_top_level_dirs()
    root_rows: list[dict] = []
    org_children: dict[str, list[str]] = {}

    for p in top_dirs:
        row = folder_row(p.name, p, catalog, by_path)
        if p.name == "AeroStab":
            row["kind"] = "own-product"
        elif p.name in ORG_CONTAINERS:
            row["kind"] = "org-library"
            org_children[p.name] = [c.name for c in list_org_repos(p)]
        else:
            row["kind"] = "root-mirror"
        root_rows.append(row)

    fpv_repos = ROOT / "fpv-library" / "repos"
    fpv_count = len(list(fpv_repos.iterdir())) if fpv_repos.is_dir() else 0
    git_mirrors = sum(1 for r in root_rows if r["mirror"] == "✅ git")
    git_mirrors += sum(len(list_org_repos(ROOT / n)) for n in ORG_CONTAINERS if (ROOT / n).is_dir())
    for child in fpv_repos.iterdir() if fpv_repos.is_dir() else []:
        if is_git_mirror(child):
            git_mirrors += 1

    lines = [
        "# Карта монорепозиторію / Library Map",
        "",
        f"> **Автогенерація:** `python3 fpv-library/scripts/generate_library_map.py`  ",
        f"> **Оновлено:** {now}  ",
        f"> **Повний каталог:** [REPOS.md](REPOS.md) ({len(catalog.get('repos', []))} записів)",
        "",
        "## Огляд",
        "",
        "| Метрика | Значення |",
        "|---------|----------|",
        f"| Тек у корені | **{len(root_rows)}** |",
        f"| fpv-library/repos | **{fpv_count}** |",
        f"| Повні git-копії (submodule) | **{git_mirrors}** |",
        f"| Org-бібліотеки | {', '.join(sorted(ORG_CONTAINERS))} |",
        "",
        "## Дерево (корінь)",
        "",
    ]
    lines.extend(mermaid_section(root_rows, org_children))
    lines.extend(
        [
            "",
            "## Власні проєкти",
            "",
        ]
    )
    own = [r for r in root_rows if r.get("kind") == "own-product"]
    lines.extend(
        table(
            ["Тека", "Опис", "Розмір"],
            [[r["link"], "Власна розробка (не mirror)", r["size"]] for r in own],
        )
    )

    lines.extend(["", "## Org-бібліотеки (повні git-копії)", ""])
    for org in sorted(ORG_CONTAINERS):
        org_path = ROOT / org
        if not org_path.is_dir():
            continue
        children = list_org_repos(org_path)
        lines.append(f"### `{org}/` — {len(children)} репо")
        lines.append("")
        if children:
            lines.extend(
                table(
                    ["Репо", "GitHub", "Mirror", "Verified", "Розмір"],
                    [
                        [
                            f"[{c.name}]({org}/{c.name}/)",
                            f"[{org}/{c.name}](https://github.com/{org}/{c.name})",
                            "✅ git" if is_git_mirror(c) else "📁",
                            (by_path.get(f"{org}/{c.name}") or {}).get("verified_at", "—")[:10] or "—",
                            human_size(dir_size(c)),
                        ]
                        for c in children
                    ],
                )
            )
        else:
            lines.append("_Ще немає склонованих репо — CI додає поступово._")
        lines.append("")

    lines.extend(["## Корінь — дзеркала та теки", ""])
    legacy = [r for r in root_rows if r.get("kind") == "root-mirror"]
    lines.extend(
        table(
            ["Тека", "GitHub", "Mirror", "Verified", "Розмір"],
            [
                [r["link"], r["gh"], r["mirror"], r["verified"], r["size"]]
                for r in legacy
            ],
        )
    )

    lines.extend(
        [
            "",
            "## fpv-library/",
            "",
            "| Шлях | Опис |",
            "|------|------|",
            "| [fpv-library/](fpv-library/) | Каталог, скрипти, CI mirror |",
            f"| [fpv-library/repos/](fpv-library/repos/) | **{fpv_count}** дзеркал з GitHub |",
            "| [catalog.json](fpv-library/catalog.json) | Маніфест усіх проєктів |",
            "| [MIRROR.md](fpv-library/MIRROR.md) | Політика повного клону |",
            "",
            "Детальний список усіх `fpv-library/repos/*` → **[REPOS.md](REPOS.md)**.",
            "",
            "## Службові теки",
            "",
            "| Тека | Призначення |",
            "|------|-------------|",
            "| [docs/](docs/) | Документація, STRUCTURE, MIRROR_POLICY |",
            "| [.github/workflows/](.github/workflows/) | CI: discover, sync, карта |",
            "",
            "---",
            "",
            "Карта оновлюється автоматично при додаванні нової теки (CI + `register_legacy.py`).",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    text = generate()
    OUTPUT.write_text(text + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
