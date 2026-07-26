#!/usr/bin/env python3
"""Relevance scoring for FPV-related GitHub repositories."""

from __future__ import annotations

import re
from typing import Any

# Strong signals in name/description/topics
KEYWORDS: list[tuple[str, float]] = [
    (r"\bfpv\b", 3.0),
    (r"\bbetaflight\b", 2.5),
    (r"\binav\b", 2.5),
    (r"\bardupilot\b", 2.5),
    (r"\bflight\s*controller\b", 2.0),
    (r"\bblackbox\b", 2.0),
    (r"\bosd\b", 1.8),
    (r"\bvtx\b", 1.8),
    (r"\belrs\b", 1.8),
    (r"\bcrsf\b", 1.5),
    (r"\bmavlink\b", 1.5),
    (r"\bmsp\b", 1.2),
    (r"\bquadcopter\b", 2.0),
    (r"\bdrone\b", 1.5),
    (r"\bwhoop\b", 1.5),
    (r"\brush\b", 1.0),
    (r"\bbrushless\b", 1.2),
    (r"\bopenipc\b", 2.0),
    (r"\bwfb\b", 1.5),
    (r"\bwifibroadcast\b", 2.0),
    (r"\bgcs\b", 1.5),
    (r"\bground\s*control\b", 1.5),
    (r"\brace\s*timing\b", 2.0),
    (r"\brotorhazard\b", 2.5),
    (r"\bwebrtc\b", 1.0),
    (r"\bwebxr\b", 1.2),
    (r"\bsitl\b", 1.5),
    (r"\bpid\s*tun", 1.5),
    (r"\bthrust\s*vector", 1.5),
    (r"\banti[- ]?drone\b", 1.5),
    (r"\buav\b", 1.2),
    (r"\btelemetry\b", 1.0),
    (r"\bvideo\s*encoder\b", 1.5),
    (r"\bexpresslrs\b", 1.8),
]

# Penalize obvious non-library targets
NEGATIVE: list[tuple[str, float]] = [
    (r"\bshopify\b", -2.0),
    (r"\bstore\b", -1.0),
    (r"\bpersonal\s+website\b", -1.5),
    (r"\bhomepage\b", -1.0),
    (r"\bcli\s+dump", -0.5),
    (r"\bwebsite\b", -0.8),
    (r"\b\.github\.io\b", -0.5),
    (r"\bgun\s+fpv\b", -3.0),
]


def _text(repo: dict[str, Any]) -> str:
    parts = [
        repo.get("name") or "",
        repo.get("full_name") or "",
        repo.get("description") or "",
        " ".join(repo.get("topics") or []),
    ]
    return " ".join(parts).lower()


def score_repo(repo: dict[str, Any]) -> float:
    text = _text(repo)
    total = 0.0
    for pattern, weight in KEYWORDS:
        if re.search(pattern, text, re.I):
            total += weight
    for pattern, weight in NEGATIVE:
        if re.search(pattern, text, re.I):
            total += weight

    stars = int(repo.get("stargazers_count") or 0)
    if stars >= 100:
        total += 2.0
    elif stars >= 20:
        total += 1.0
    elif stars >= 5:
        total += 0.5

    if repo.get("fork"):
        total -= 0.5

    size_kb = int(repo.get("size") or 0)
    if size_kb > 500_000:  # very large mirrors
        total -= 1.0

    return round(total, 2)


def is_candidate(repo: dict[str, Any], min_score: float = 2.0) -> bool:
    if repo.get("archived"):
        return False
    if not repo.get("name"):
        return False
    return score_repo(repo) >= min_score
