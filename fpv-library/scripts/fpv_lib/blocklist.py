#!/usr/bin/env python3
"""Blocklist for repos that must never enter the FPV catalog."""

from __future__ import annotations

from pathlib import Path

_BLOCKLIST_PATH = Path(__file__).resolve().parents[2] / "blocklist.txt"
_exact: set[str] | None = None
_prefixes: list[str] | None = None


def _load() -> None:
    global _exact, _prefixes
    if _exact is not None:
        return
    _exact = set()
    _prefixes = []
    if not _BLOCKLIST_PATH.exists():
        return
    for line in _BLOCKLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key = line.lower()
        if key.endswith("/*"):
            _prefixes.append(key[:-2])
        else:
            _exact.add(key)


def is_blocked(source: str) -> bool:
    _load()
    assert _exact is not None and _prefixes is not None
    key = source.lower()
    if key in _exact:
        return True
    owner = key.split("/", 1)[0]
    return any(key.startswith(p + "/") for p in _prefixes)
