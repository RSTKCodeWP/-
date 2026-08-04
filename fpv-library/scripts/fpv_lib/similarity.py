#!/usr/bin/env python3
"""Build discovery queries from the existing catalog base."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

# Topics too generic to drive similarity search
SKIP_TOPICS = {
    "arduino",
    "c",
    "cpp",
    "docker",
    "firmware",
    "javascript",
    "linux",
    "python",
    "rust",
    "tools",
    "tutorial",
    "web",
    "windows",
    "android",
    "ios",
    "cmake",
    "makefile",
    "github-pages",
    "hacktoberfest",
}

# Name tokens that indicate our domain when repeated across repos
DOMAIN_TOKENS = re.compile(
    r"\b("
    r"fpv|mavlink|msp|osd|wfb|wifibroadcast|openhd|openipc|dronebridge|"
    r"betaflight|inav|ardupilot|elrs|crsf|expresslrs|gcs|vtx|telemetry|"
    r"groundstation|ground-station|videolink|datalink|companion|sitl|"
    r"rotorhazard|walksnail|hdzero|madflight|meshtastic|edgetx|opentx|"
    r"blackbox|pid|flightcontroller|uav|drone|quadcopter|whoop"
    r")\b",
    re.I,
)


def _catalog_entries(catalog: dict[str, Any], *, verdicts: tuple[str, ...] = ("keep", "watch")) -> list[dict]:
    return [e for e in catalog.get("repos", []) if e.get("verdict") in verdicts]


def top_topics(catalog: dict[str, Any], *, limit: int = 25, min_count: int = 2) -> list[str]:
    counts: Counter[str] = Counter()
    for entry in _catalog_entries(catalog):
        for topic in entry.get("topics") or []:
            t = topic.lower().strip()
            if t and t not in SKIP_TOPICS:
                counts[t] += 1
    return [t for t, n in counts.most_common(limit) if n >= min_count]


def top_name_tokens(catalog: dict[str, Any], *, limit: int = 20, min_count: int = 2) -> list[str]:
    counts: Counter[str] = Counter()
    for entry in _catalog_entries(catalog):
        name = entry.get("source", "").split("/", 1)[-1]
        text = f"{name} {entry.get('description') or ''}"
        for match in DOMAIN_TOKENS.finditer(text):
            counts[match.group(1).lower()] += 1
    return [t for t, n in counts.most_common(limit) if n >= min_count]


def owners_from_catalog(catalog: dict[str, Any], *, verdicts: tuple[str, ...] = ("keep", "watch")) -> list[str]:
    owners: set[str] = set()
    for entry in _catalog_entries(catalog, verdicts=verdicts):
        source = entry.get("source", "")
        if "/" in source:
            owners.add(source.split("/", 1)[0])
    return sorted(owners)


def similarity_queries(catalog: dict[str, Any], *, max_queries: int = 15) -> list[str]:
    """GitHub search queries derived from our existing library base."""
    queries: list[str] = []
    seen: set[str] = set()

    def add(q: str) -> None:
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            queries.append(q)

    for topic in top_topics(catalog, limit=20, min_count=2):
        add(f"topic:{topic}")

    for token in top_name_tokens(catalog, limit=15, min_count=2):
        add(f"{token} in:name,description,readme")

    # Cross-pollinate high-value topic pairs seen in keep repos
    topics = top_topics(catalog, limit=8, min_count=3)
    for i, a in enumerate(topics):
        for b in topics[i + 1 : i + 3]:
            add(f"topic:{a} topic:{b}")

    return queries[:max_queries]
