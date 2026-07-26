#!/usr/bin/env python3
"""Catalog persistence for tracked FPV repositories."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CATALOG_VERSION = 1


def library_root() -> Path:
    return Path(__file__).resolve().parents[2]


def catalog_path() -> Path:
    return library_root() / "catalog.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(source: str, description: str | None = None) -> str:
    owner, _, name = source.partition("/")
    hint = description or name
    hint = re.sub(r"[^a-zA-Z0-9]+", "-", hint)[:40].strip("-")
    base = re.sub(r"[^a-zA-Z0-9._-]+", "-", name)
    if hint and hint.lower() not in base.lower():
        return f"{base}-{hint}"
    return base


def default_repo_path(source: str, description: str | None = None) -> str:
    slug = slugify(source, description)
    return f"fpv-library/repos/{slug}"


def load_catalog() -> dict[str, Any]:
    path = catalog_path()
    if not path.exists():
        return {
            "version": CATALOG_VERSION,
            "updated_at": now_iso(),
            "repos": [],
            "search_queries": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_catalog(catalog: dict[str, Any]) -> None:
    catalog["version"] = CATALOG_VERSION
    catalog["updated_at"] = now_iso()
    catalog_path().write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def find_entry(catalog: dict[str, Any], source: str) -> dict[str, Any] | None:
    for entry in catalog.get("repos", []):
        if entry.get("source", "").lower() == source.lower():
            return entry
    return None


def upsert_entry(
    catalog: dict[str, Any],
    *,
    source: str,
    path: str | None = None,
    description: str | None = None,
    stars: int | None = None,
    discovered_via: str | None = None,
    score: float | None = None,
    upstream_commit: str | None = None,
    upstream_updated: str | None = None,
    legacy: bool = False,
) -> dict[str, Any]:
    entry = find_entry(catalog, source)
    if entry is None:
        entry = {
            "source": source,
            "path": path or default_repo_path(source, description),
            "added_at": now_iso(),
            "discovered_via": discovered_via or "manual",
        }
        catalog.setdefault("repos", []).append(entry)

    if path:
        entry["path"] = path
    if description is not None:
        entry["description"] = description
    if stars is not None:
        entry["stars"] = stars
    if discovered_via:
        entry["discovered_via"] = discovered_via
    if score is not None:
        entry["score"] = score
    if upstream_commit:
        entry["upstream_commit"] = upstream_commit
    if upstream_updated:
        entry["upstream_updated"] = upstream_updated
    if legacy:
        entry["legacy"] = True

    entry["owner"] = source.split("/")[0]
    return entry
