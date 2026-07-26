#!/usr/bin/env python3
"""Classify discovered repos: useful hook, watch, or noise."""

from __future__ import annotations

import re
from typing import Any

# Category tags for curated browsing
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("gcs", [r"\bgcs\b", r"ground\s*control", r"mission\s*control", r"qgroundcontrol"]),
    ("link", [r"wfb", r"wifibroadcast", r"openhd", r"dronebridge", r"video\s*link", r"datalink", r"lte", r"gprs"]),
    ("fiber", [r"fiber", r"optical", r"оптоволок", r"tether"]),
    ("osd", [r"\bosd\b", r"msp", r"displayport", r"overlay"]),
    ("fc", [r"betaflight", r"\binav\b", r"ardupilot", r"flight\s*controller", r"blackbox", r"pid\s*tun"]),
    ("elrs", [r"expresslrs", r"\belrs\b", r"\bcrsf\b", r"crossfire"]),
    ("openipc", [r"openipc", r"majestic", r"rtsp", r"pixelpilot"]),
    ("goggles", [r"goggles", r"wtfos", r"dji\s*fpv", r"moonlight"]),
    ("tools", [r"inventory", r"configurator", r"simulator", r"\bsitl\b", r"lap\s*timer", r"race\s*timing"]),
    ("detection", [r"detector", r"anti[- ]?drone", r"scanner", r"remote\s*id"]),
    ("ai", [r"\bai\b", r"llm", r"vision", r"yolo", r"detection"]),
]

# Hard noise — skip even if score is high
NOISE_PATTERNS: list[str] = [
    r"github\.io\b",
    r"\bhomepage\b",
    r"\bpersonal\s+website\b",
    r"\bportfolio\b",
    r"\bcourse\b.*\b20\d{2}\b",
    r"\bhomework\b",
    r"\bassignment\b",
    r"\bleetcode\b",
    r"\bneetcode\b",
    r"\bconfig\s+files\s+for\s+my\s+github\s+profile\b",
    r"orgtestcodacy",
    r"\.github$",
    r"\bdotfiles\b",
    r"\blanding\s+page\b",
    r"three\.js.*landing",
    r"\bgun\s+fpv\b",
    r"\bfpv\s+gun\b",
    r"\bshopify\b",
    r"\be-?commerce\b",
    r"/\.github$",
    r"^[^/]+/\.github$",
    r"\bmail\s*bot\b",
    r"\btemporary\s+mail\b",
    r"\buserbot\b",
    r"\bcrypto\s+bot\b",
    r"\btarkov\b",
    r"\bpechkin\b",
]

# Strong keep signals — project is clearly on-topic
KEEP_PATTERNS: list[str] = [
    r"\bfpv\b",
    r"betaflight",
    r"\binav\b",
    r"ardupilot",
    r"openipc",
    r"wfb",
    r"wifibroadcast",
    r"openhd",
    r"dronebridge",
    r"expresslrs",
    r"\belrs\b",
    r"rotorhazard",
    r"mavlink",
    r"ground\s*control",
    r"\bgcs\b",
    r"msp.*osd",
    r"fiber.*drone",
    r"optical.*fiber",
    r"video\s*link",
    r"telemetry.*drone",
    r"fpv.*ground",
    r"whoop",
    r"blackbox",
    r"\bvtx\b",
    r"wtfos",
    r"pixelpilot",
    r"madflight",
]


def _text(entry: dict[str, Any]) -> str:
    parts = [
        entry.get("source") or "",
        entry.get("description") or "",
        " ".join(entry.get("topics") or []),
    ]
    return " ".join(parts).lower()


def classify_categories(text: str) -> list[str]:
    cats: list[str] = []
    for name, patterns in CATEGORY_RULES:
        if any(re.search(p, text, re.I) for p in patterns):
            cats.append(name)
    return cats or ["other"]


def triage_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Return triage fields: verdict, categories, interesting, reason."""
    text = _text(entry)
    score = float(entry.get("score") or 0)
    stars = int(entry.get("stars") or 0)
    legacy = bool(entry.get("legacy"))
    source = (entry.get("source") or "").lower()

    if source.endswith("/.github") or source.split("/")[-1] == ".github":
        return {
            "verdict": "skip",
            "categories": classify_categories(text),
            "interesting": False,
            "triage_reason": "noise:github-meta",
        }

    fpv_core = bool(
        re.search(
            r"\bfpv\b|betaflight|\binav\b|openipc|wfb|wifibroadcast|openhd|"
            r"dronebridge|expresslrs|\belrs\b|rotorhazard|wtfos|pixelpilot|"
            r"ground\s*control|\bgcs\b|msp.*osd|fiber|blackbox|whoop|\bvtx\b|madflight",
            text,
            re.I,
        )
    )

    # Generic Telegram/mail bots — skip unless clearly FPV/drone related
    if re.search(r"\btelegram[\s-]?bot\b|\buserbot\b", text, re.I) and not fpv_core:
        return {
            "verdict": "skip",
            "categories": classify_categories(text),
            "interesting": False,
            "triage_reason": "noise:telegram-bot",
        }

    for pat in NOISE_PATTERNS:
        if re.search(pat, text, re.I):
            return {
                "verdict": "skip",
                "categories": classify_categories(text),
                "interesting": False,
                "triage_reason": f"noise:{pat}",
            }

    categories = classify_categories(text)
    keep_hits = sum(1 for p in KEEP_PATTERNS if re.search(p, text, re.I))

    # fpv_core already computed above
    if legacy:
        verdict, reason, interesting = "keep", "legacy", True
    elif score >= 5.0 and fpv_core:
        verdict, reason, interesting = "keep", "high-score-fpv", True
    elif keep_hits >= 2 and score >= 3.0 and fpv_core:
        verdict, reason, interesting = "keep", "strong-signals", score >= 4.0 or stars >= 10
    elif score >= 4.0 and fpv_core:
        verdict, reason, interesting = "keep", "hook-reviewed", True
    elif score >= 3.0 and fpv_core and stars >= 5:
        verdict, reason, interesting = "keep", "hook-reviewed", True
    elif score >= 2.5 and fpv_core:
        verdict, reason, interesting = "watch", "weak-hook", stars >= 10
    elif score >= 2.0 and keep_hits >= 1:
        verdict, reason, interesting = "watch", "peripheral", stars >= 20
    else:
        verdict, reason, interesting = "skip", "low-relevance", False

    result: dict[str, Any] = {
        "verdict": verdict,
        "categories": categories,
        "interesting": interesting,
        "triage_reason": reason,
    }

    return result
