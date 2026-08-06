#!/usr/bin/env python3
"""Scan monorepo folders for library map and registration."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

SKIP_TOP_LEVEL = {
    "fpv-library",
    "docs",
    "logs",
    ".github",
    "node_modules",
    ".venv",
    "__pycache__",
}

OWN_PRODUCTS = {
    "AeroStab": "own-product",
}

ORG_CONTAINERS = {"OpenIPC", "OpenHD", "DroneBridge", "ArduPilot", "ComBatVision"}


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def is_skipped(name: str) -> bool:
    return name in SKIP_TOP_LEVEL or name.startswith(".")


def list_top_level_dirs() -> list[Path]:
    root = workspace_root()
    return sorted(
        [p for p in root.iterdir() if p.is_dir() and not is_skipped(p.name)],
        key=lambda p: p.name.lower(),
    )


def git_remote_source(path: Path) -> str | None:
    if not (path / ".git").exists():
        return None
    try:
        out = subprocess.check_output(
            ["git", "-C", str(path), "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", out)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return None


def meta_source(path: Path) -> str | None:
    meta = path / ".fpv-library.json"
    if not meta.exists():
        return None
    try:
        import json

        data = json.loads(meta.read_text(encoding="utf-8"))
        return data.get("source")
    except (json.JSONDecodeError, OSError):
        return None


def infer_source_from_name(folder_name: str, catalog: dict[str, Any]) -> str | None:
    for entry in catalog.get("repos", []):
        if entry.get("path") == folder_name:
            return entry.get("source")
    token = folder_name.split("-", 1)[0]
    if not token:
        return None
    matches = [
        e
        for e in catalog.get("repos", [])
        if e.get("source", "").split("/")[-1].lower() == token.lower()
    ]
    if len(matches) == 1:
        return matches[0]["source"]
    return None


def folder_kind(name: str, path: Path) -> str:
    if name in OWN_PRODUCTS:
        return OWN_PRODUCTS[name]
    if name in ORG_CONTAINERS:
        return "org-library"
    if (path / ".git").exists() or (workspace_root() / ".gitmodules").exists():
        # submodule child lives under org path
        pass
    if "-" in name and not name[0].islower():
        # RepoName-Description pattern at root
        return "root-mirror"
    return "root-folder"


def list_org_repos(org_path: Path) -> list[Path]:
    if not org_path.is_dir():
        return []
    return sorted([p for p in org_path.iterdir() if p.is_dir() and not p.name.startswith(".")], key=lambda p: p.name.lower())


def is_git_mirror(path: Path) -> bool:
    return path.is_dir() and (path / ".git").exists()
