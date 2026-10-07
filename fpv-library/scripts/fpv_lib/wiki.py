"""Exhibition dossiers built only from files that already exist.

Nothing in a card is paraphrased into new technical steps. Missing sections
stay missing and say so.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path

MISSING = "У джерелах цього репозиторію цього немає."

HALLS: dict[str, dict[str, str]] = {
    "own": {
        "title": "Власна розробка",
        "lead": (
            "Проєкти, які живуть у цьому монорепозиторії як розробка, "
            "а не як дзеркало чужого GitHub."
        ),
    },
    "gcs": {
        "title": "Наземні станції",
        "lead": (
            "Програми, через які оператор дивиться телеметрію, карту й відео "
            "і віддає команди борту."
        ),
    },
    "link": {
        "title": "Радіо і відеолінк",
        "lead": "Канали, якими відео, керування і телеметрія ходять між бортом і землею.",
    },
    "radio": {
        "title": "Радіо",
        "lead": "Радіотракт, SDR і супутні засоби, окремо від відеолінка як продукту.",
    },
    "elrs": {
        "title": "ELRS і RC-лінк",
        "lead": "Відкриті радіокерування: ExpressLRS, Crossfire-мости, джойстики в RC.",
    },
    "openipc": {
        "title": "OpenIPC",
        "lead": "IP-камера як FPV: прошивки, стрімери, конфігуратори й наземні клієнти OpenIPC.",
    },
    "fiber": {
        "title": "Оптика і трос",
        "lead": "Лінії, де радіо замінює або дублює оптичне волокно чи силовий трос.",
    },
    "bridge": {
        "title": "Мости і ретранслятори",
        "lead": "Проксі, форвардери і ретранслятори між протоколами або сегментами мережі.",
    },
    "fc": {
        "title": "Польотні контролери і прошивки",
        "lead": "Прошивки і інструменти польотних контролерів: Betaflight, INAV, ArduPilot та поруч.",
    },
    "osd": {
        "title": "OSD",
        "lead": "Накладання телеметрії на відео: шрифти, протоколи OSD, оверлеї.",
    },
    "goggles": {
        "title": "Окуляри і VRX",
        "lead": "Наземні приймачі відео, окуляри і протоколи VRX.",
    },
    "detection": {
        "title": "Виявлення",
        "lead": "Пасивне або активне виявлення дронів і радіосигналів.",
    },
    "ai": {
        "title": "Зір і алгоритми",
        "lead": "Комп'ютерний зір, моделі і допоміжні алгоритми навколо польоту.",
    },
    "tools": {
        "title": "Інструменти",
        "lead": "Утиліти, конфігуратори, бібліотеки і супровід, які не є самим літаком.",
    },
    "other": {
        "title": "Інше",
        "lead": "Те, що каталог не поклав у жодну вужчу тему. Картка все одно з тих самих джерел.",
    },
}

HALL_PRIORITY = (
    "gcs",
    "link",
    "radio",
    "fc",
    "openipc",
    "goggles",
    "elrs",
    "fiber",
    "bridge",
    "osd",
    "ai",
    "tools",
    "detection",
    "other",
)

AUDIENCE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Оператор наземної станції",
        ("ground control", "ground station", "qgroundcontrol", "mission planner", "наземн"),
    ),
    (
        "Пілот, якому потрібні окуляри, VTX або OSD",
        ("goggles", "vtx", "vrx", "osd", "окуляр"),
    ),
    (
        "Розробник польотного контролера",
        ("betaflight", "inav", "ardupilot", "flight controller", "польотн"),
    ),
    (
        "Інженер радіолінка",
        ("expresslrs", "elrs", "wfb-ng", "wifi broadcast", "crossfire", "mavlink"),
    ),
    (
        "Дослідник протоколів і прошивок",
        ("reverse engineering", "exploit", "firmware extract", "реверс"),
    ),
    (
        "Розробник відеотракту",
        ("h.264", "h.265", "h264", "h265", "gstreamer", "rtsp", "openipc"),
    ),
    (
        "Майстерня обладнання",
        ("kicad", "schematic", "pcb", "гербер"),
    ),
)

EXT_NAMES = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".hpp": "C++",
    ".rs": "Rust",
    ".go": "Go",
    ".java": "Java",
    ".kt": "Kotlin",
    ".lua": "Lua",
    ".swift": "Swift",
    ".ino": "Arduino",
    ".md": "Markdown",
    ".json": "JSON",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".toml": "TOML",
    ".sh": "shell",
    ".html": "HTML",
    ".css": "CSS",
    ".vue": "Vue",
}

STACK_FILES = {
    "package.json": "Node.js (package.json)",
    "Cargo.toml": "Rust (Cargo.toml)",
    "platformio.ini": "PlatformIO (platformio.ini)",
    "requirements.txt": "Python (requirements.txt)",
    "pyproject.toml": "Python (pyproject.toml)",
    "go.mod": "Go (go.mod)",
    "CMakeLists.txt": "CMake",
    "Makefile": "Make",
    "deno.json": "Deno",
    "pom.xml": "Maven",
    "build.gradle": "Gradle",
    "Package.swift": "Swift Package",
    "pubspec.yaml": "Flutter/Dart",
}

GENERIC_TITLES = {
    "features",
    "show help",
    "overview",
    "introduction",
    "about",
    "readme",
    "usage",
    "documentation",
}

# Used only when the catalog left the project in `other`.
# Matched against title, description, and folder path — not the whole README.
REHOME: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("detection", ("детектор", "detector", "drone detect")),
    ("goggles", ("goggle", "окуляр", "vrx")),
    ("osd", ("osd",)),
    ("elrs", ("expresslrs", "elrs")),
    ("fiber", ("fiber optic", "fibre optic", "оптоволок")),
    ("openipc", ("openipc",)),
    ("gcs", ("ground station", "ground control", "qgroundcontrol")),
    ("fc", ("betaflight", "inav", "ardupilot", "flight controller", "польотн")),
    ("link", ("wifi broadcast", "wfb-ng", "wfb ng", "video link")),
    ("radio", ("hackrf", "video transmitter", "radio system")),
    ("ai", ("yolo", "computer vision", "optical flow")),
    ("tools", ("configurator", "installer")),
)

SKIP_WALK = {
    ".git",
    "node_modules",
    ".pio",
    "build",
    "dist",
    "__pycache__",
    ".venv",
    "venv",
    "vendor",
    "target",
}

HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*```")
LICENSE_MARKERS = (
    ("GPL-3.0", ("gnu general public license", "gpl-3", "gpl v3", "gplv3")),
    ("GPL-2.0", ("gpl-2", "gpl v2", "gplv2", "version 2")),
    ("MIT", ("mit license", "permission is hereby granted")),
    ("Apache-2.0", ("apache license",)),
    ("BSD", ("bsd license", "redistribution and use")),
    ("LGPL", ("lesser general public license", "lgpl")),
    ("MPL-2.0", ("mozilla public license",)),
    ("Unlicense", ("unlicense",)),
    ("CC", ("creative commons",)),
)

SECTION_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction",
        re.compile(
            r"(install|installation|usage|getting started|quick\s*start|"
            r"how to|запуск|встановлен|використан|збірк|інструкц|"
            r"установ|использован|сборк|инструкц|"
            r"(^| )build($| )|(^| )setup($| ))",
            re.I,
        ),
    ),
    (
        "requirements",
        re.compile(
            r"(requirements|prerequisites|dependencies|потрібн|залежност|требован|зависимост)",
            re.I,
        ),
    ),
    (
        "features",
        re.compile(r"(features|можливост|функці|capabilities|возможност|функци)", re.I),
    ),
    (
        "how",
        re.compile(
            r"(architecture|how it works|how this works|принцип|як це прац|як влашт|архитектур)",
            re.I,
        ),
    ),
    ("audience", re.compile(r"(audience|for whom|who is this|для кого)", re.I)),
    ("license", re.compile(r"(license|ліценз|licence)", re.I)),
    ("about", re.compile(r"(about|introduction|overview|what is|що це|опис|ідея)", re.I)),
)


def primary_category(categories: list[str] | None) -> str:
    cats = categories or ["other"]
    for cat in HALL_PRIORITY:
        if cat in cats:
            return cat
    return cats[0] if cats[0] in HALLS else "other"


def slug_for(source: str, path: str) -> str:
    raw = source.replace("/", "__") if source else path.replace("/", "__")
    raw = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-._")
    return (raw or "project")[:96]


def _read_cap(path: Path, limit: int = 200_000) -> str:
    try:
        data = path.read_bytes()[:limit]
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def _is_noise_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if s.startswith("<!--") or s.startswith("[!["):
        return True
    if re.fullmatch(
        r"(?:\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)\s*|!\[[^\]]*\]\([^)]*\)\s*)+",
        s,
    ):
        return True
    plain = re.sub(r"<[^>]+>", "", s).strip()
    if re.search(r"<img\b", s, re.I) and len(plain) < 12:
        return True
    return False


def clean_readme(text: str) -> str:
    kept = [line for line in text.splitlines() if not _is_noise_line(line)]
    return "\n".join(kept).strip()


def _marker(blob: str, key: str) -> bool:
    if len(key) <= 4:
        return re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", blob) is not None
    return key in blob


def exhibition_hall(entry: dict, title: str, idea: str) -> tuple[str, str]:
    """Return hall id and, when catalog said other, the word that moved it."""
    if entry.get("own"):
        return "own", ""
    categories = [c for c in (entry.get("categories") or []) if isinstance(c, str)]
    primary = primary_category(categories)
    if primary != "other":
        return primary, ""
    blob = " ".join(
        (
            title,
            entry.get("description") or "",
            entry.get("path") or "",
            idea[:500],
        )
    ).lower()
    for hall, keys in REHOME:
        for key in keys:
            if _marker(blob, key):
                return hall, key
    return "other", ""


def split_sections(text: str) -> tuple[str, list[tuple[int, str, str]]]:
    preamble: list[str] = []
    sections: list[tuple[int, str, str]] = []
    current: tuple[int, str] | None = None
    buf: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            buf.append(line)
            continue
        if in_fence:
            buf.append(line)
            continue
        match = HEADING_RE.match(line)
        if match:
            if current is None:
                preamble = buf
            else:
                sections.append((current[0], current[1], "\n".join(buf).strip()))
            current = (len(match.group(1)), match.group(2).strip())
            buf = []
        else:
            buf.append(line)
    if current is None:
        preamble = buf
    else:
        sections.append((current[0], current[1], "\n".join(buf).strip()))
    return "\n".join(preamble).strip(), sections


def classify_heading(title: str) -> str | None:
    if re.search(r"\b(status|badge|changelog|license)\b", title, re.I) and re.search(
        r"\b(build|setup)\b", title, re.I
    ):
        return None
    for kind, pattern in SECTION_RULES:
        if pattern.search(title):
            return kind
    return None


def prose_paragraphs(body: str, max_chars: int = 900) -> str:
    parts: list[str] = []
    chunk: list[str] = []
    in_fence = False
    for line in body.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        stripped = line.strip()
        if not stripped:
            if chunk:
                parts.append(" ".join(chunk))
                chunk = []
            if sum(len(p) for p in parts) >= max_chars:
                break
            continue
        if stripped.startswith(("|", "!", "<", "- ", "* ", "+ ")):
            continue
        if stripped in {"---", "***", "___"}:
            continue
        if re.fullmatch(r"(\[[^\]]+\]\([^)]+\)\s*\|?\s*)+", stripped):
            continue
        chunk.append(stripped)
    if chunk and sum(len(p) for p in parts) < max_chars:
        parts.append(" ".join(chunk))
    text = "\n\n".join(p for p in parts if p).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "…"
    return text


def bullet_items(body: str, limit: int = 12) -> list[str]:
    items: list[str] = []
    in_fence = False
    for line in body.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = re.match(r"\s*[-*+]\s+(.+)", line)
        if not match:
            continue
        item = re.sub(r"\s+", " ", match.group(1)).strip()
        if item:
            items.append(item[:240])
        if len(items) >= limit:
            break
    return items


def clip_block(text: str, max_lines: int = 80, max_chars: int = 5000) -> tuple[str, bool]:
    lines = text.splitlines()
    clipped = False
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        clipped = True
    body = "\n".join(lines).strip()
    if len(body) > max_chars:
        body = body[:max_chars].rstrip()
        clipped = True
    if body.count("```") % 2 == 1:
        body += "\n```"
        clipped = True
    return body, clipped


def find_readme(path: Path) -> Path | None:
    for name in (
        "README.md",
        "Readme.md",
        "readme.md",
        "README.MD",
        "README.rst",
        "README.txt",
        "README",
    ):
        candidate = path / name
        if candidate.is_file():
            return candidate
    return None


def parse_readme(text: str) -> dict:
    cleaned = clean_readme(text)
    preamble, sections = split_sections(cleaned)
    title = ""
    buckets: dict[str, list[str]] = {
        "instruction": [],
        "requirements": [],
        "features": [],
        "how": [],
        "audience": [],
        "license": [],
        "about": [],
    }
    feature_bullets: list[str] = []
    h1_body = ""
    for level, heading, body in sections:
        if level == 1 and not title:
            title = heading.strip(" *_")
            h1_body = body
            continue
        kind = classify_heading(heading)
        if not kind:
            continue
        if kind == "features":
            feature_bullets.extend(bullet_items(body))
        block, clipped = clip_block(body)
        if not block:
            continue
        piece = f"### {heading}\n\n{block}"
        if clipped:
            piece += "\n\n_Далі в README є ще текст. Тут лишається виставковий уривок._"
        buckets[kind].append(piece)
    idea = prose_paragraphs(h1_body) or prose_paragraphs(preamble)
    if not idea:
        for piece in buckets["about"]:
            idea = prose_paragraphs(piece)
            if idea:
                break
    return {
        "title": title,
        "idea": idea,
        "buckets": buckets,
        "feature_bullets": feature_bullets[:12],
    }


def audience_from_text(text: str) -> list[tuple[str, str]]:
    hay = text.lower()
    found: list[tuple[str, str]] = []
    for label, keys in AUDIENCE_RULES:
        for key in keys:
            if key in hay:
                found.append((label, key))
                break
    return found


def detect_license(path: Path, readme_text: str) -> str:
    blob = readme_text[:4000].lower()
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md", "license"):
        lic = path / name
        if lic.is_file():
            blob = (_read_cap(lic, 4000) + "\n" + blob).lower()
            break
    for label, markers in LICENSE_MARKERS:
        if any(marker in blob for marker in markers):
            return label
    return ""


def scan_tree(path: Path, max_files: int = 2000, max_depth: int = 3) -> dict:
    top: list[str] = []
    try:
        children = sorted(path.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        children = []
    for child in children:
        if child.name in SKIP_WALK or child.name.startswith("."):
            continue
        top.append(child.name + ("/" if child.is_dir() else ""))
        if len(top) >= 24:
            break
    exts: Counter[str] = Counter()
    seen = 0
    truncated = False
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [d for d in dirnames if d not in SKIP_WALK and not d.startswith(".")]
        depth = len(Path(dirpath).relative_to(path).parts)
        if depth >= max_depth:
            dirnames.clear()
        for filename in filenames:
            seen += 1
            if seen > max_files:
                truncated = True
                break
            suffix = Path(filename).suffix.lower() or "(без суфікса)"
            exts[suffix] += 1
        if truncated:
            break
    languages: Counter[str] = Counter()
    for ext, count in exts.items():
        languages[EXT_NAMES.get(ext, ext)] += count
    return {
        "top": top,
        "languages": languages.most_common(6),
        "files_seen": seen if not truncated else max_files,
        "truncated": truncated,
    }


def manifest_facts(path: Path) -> list[str]:
    facts: list[str] = []
    stacks = [label for name, label in STACK_FILES.items() if (path / name).is_file()]
    if stacks:
        facts.append("Маніфести збірки: " + ", ".join(stacks) + ".")

    package = path / "package.json"
    if package.is_file():
        try:
            data = json.loads(_read_cap(package, 300_000) or "{}")
        except json.JSONDecodeError:
            data = {}
        if isinstance(data, dict):
            scripts = data.get("scripts")
            if isinstance(scripts, dict) and scripts:
                names = ", ".join(f"`{name}`" for name in list(scripts)[:12])
                facts.append(f"npm-скрипти в package.json: {names}.")
            deps = data.get("dependencies")
            if isinstance(deps, dict) and deps:
                names = ", ".join(f"`{name}`" for name in list(deps)[:12])
                extra = f" і ще {len(deps) - 12}" if len(deps) > 12 else ""
                facts.append(f"dependencies: {names}{extra}.")

    req = path / "requirements.txt"
    if req.is_file():
        pkgs = []
        for line in _read_cap(req, 20_000).splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "-")):
                continue
            pkgs.append(line.split()[0][:80])
            if len(pkgs) >= 15:
                break
        if pkgs:
            facts.append("requirements.txt: " + ", ".join(f"`{p}`" for p in pkgs) + ".")

    pio = path / "platformio.ini"
    if pio.is_file():
        envs = re.findall(r"(?m)^\[env:([^\]]+)\]", _read_cap(pio, 80_000))
        if envs:
            shown = ", ".join(f"`{name}`" for name in envs[:8])
            facts.append(f"PlatformIO env: {shown}.")

    cargo = path / "Cargo.toml"
    if cargo.is_file():
        match = re.search(r'(?m)^name\s*=\s*"([^"]+)"', _read_cap(cargo, 20_000))
        if match:
            facts.append(f"Cargo package: `{match.group(1)}`.")

    pyproject = path / "pyproject.toml"
    if pyproject.is_file():
        match = re.search(r'(?m)^name\s*=\s*"([^"]+)"', _read_cap(pyproject, 40_000))
        if match:
            facts.append(f"pyproject name: `{match.group(1)}`.")
    return facts


def local_doc_paths(path: Path) -> list[str]:
    found: list[str] = []
    docs = path / "docs"
    if docs.is_dir():
        for item in sorted(docs.glob("*.md"))[:12]:
            found.append(str(item.relative_to(path)).replace("\\", "/"))
    for name in ("FLIGHT.md", "CONTRIBUTING.md", "INSTALL.md"):
        if (path / name).is_file():
            found.append(name)
    return found


def build_dossier(entry: dict, root: Path) -> dict | None:
    rel = entry.get("path") or ""
    full = root / rel
    if not full.is_dir():
        return None
    readme_path = find_readme(full)
    readme_text = _read_cap(readme_path, 120_000) if readme_path else ""
    parsed = parse_readme(readme_text) if readme_text else {
        "title": "",
        "idea": "",
        "buckets": {k: [] for k in (
            "instruction", "requirements", "features", "how", "audience", "license", "about",
        )},
        "feature_bullets": [],
    }
    description = re.sub(r"\s+", " ", (entry.get("description") or "")).strip()
    categories = [c for c in (entry.get("categories") or []) if isinstance(c, str)]
    title = parsed["title"] or (entry.get("source") or rel or "Проєкт")
    if title.strip(" *_").lower() in GENERIC_TITLES and entry.get("source"):
        title = entry["source"]
    hall, hall_marker = exhibition_hall(entry, title, parsed["idea"])
    topics = entry.get("topics") if isinstance(entry.get("topics"), list) else []
    topic_text = " ".join(str(t) for t in topics)
    evidence_blob = " ".join(
        (
            description,
            topic_text,
            parsed["title"],
            parsed["idea"],
            " ".join(parsed["feature_bullets"]),
        )
    )
    tree = scan_tree(full)
    docs = local_doc_paths(full)
    return {
        "title": title[:120],
        "source": entry.get("source") or "",
        "path": rel,
        "verdict": entry.get("verdict") or "",
        "own": bool(entry.get("own")),
        "stars": entry.get("stars"),
        "updated": str(entry.get("upstream_updated") or entry.get("synced_at") or "")[:10],
        "categories": categories,
        "hall": hall,
        "hall_marker": hall_marker,
        "description": description,
        "idea": parsed["idea"],
        "topics": [str(t) for t in topics[:12]],
        "audiences": audience_from_text(evidence_blob),
        "audience_section": parsed["buckets"]["audience"],
        "feature_bullets": parsed["feature_bullets"],
        "how_section": parsed["buckets"]["how"],
        "requirements_section": parsed["buckets"]["requirements"],
        "instruction_section": parsed["buckets"]["instruction"],
        "license": detect_license(full, readme_text),
        "manifests": manifest_facts(full),
        "tree": tree,
        "docs": docs,
        "readme_name": readme_path.name if readme_path else "",
    }


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip() or "—"


def plain_cell(value: str, limit: int = 180) -> str:
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"[|*_`>#]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit] or "—"


def retarget_links(text: str, rel: str) -> str:
    """Point README-relative links at the project tree, not at wiki/projects/."""

    def repl(match: re.Match[str]) -> str:
        label, dest = match.group(1), match.group(2).strip()
        if dest.startswith(("#", "http://", "https://", "mailto:")):
            return match.group(0)
        dest = dest.split()[0].strip("<>")
        if dest.startswith("/"):
            return match.group(0)
        while dest.startswith("./"):
            dest = dest[2:]
        return f"[{label}](../../{rel}/{dest})"

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", repl, text)


def _linked(sections: list[str], rel: str) -> list[str]:
    return [retarget_links(piece, rel) for piece in sections]


def render_project(dossier: dict, page_slug: str) -> str:
    source = dossier["source"]
    gh = f"[{source}](https://github.com/{source})" if source else "немає upstream (власна тека)"
    cats = ", ".join(f"`{c}`" for c in dossier["categories"]) or "—"
    hall = HALLS.get(dossier["hall"], HALLS["other"])
    rel = dossier["path"]
    lines = [
        f"# {dossier['title']}",
        "",
        f"> Картка виставки. Зал: [{hall['title']}](../halls/{dossier['hall']}.md).",
        "",
    ]
    if dossier.get("hall_marker"):
        lines.extend([
            f"Каталог тримає категорію `other`. Зал «{hall['title']}» поставлено, "
            f"бо в назві, описі або шляху є «{dossier['hall_marker']}».",
            "",
        ])
    verdict = dossier["verdict"] or ("own" if dossier["own"] else "")
    stars = dossier["stars"]
    stars_cell = _cell("" if stars in (None, "") else str(stars))
    passport = [
        ("Джерело", gh),
        ("Локальна тека", "`" + dossier["path"] + "`"),
        ("У бібліотеці", _cell(verdict)),
        ("Категорії каталогу", cats),
        ("Зірки (каталог)", stars_cell),
        ("Оновлено upstream", _cell(dossier["updated"])),
        ("Ліцензія (з файлу LICENSE або згадки)", _cell(dossier["license"])),
    ]
    lines.extend(["## Паспорт", "", "| Поле | Значення |", "|------|----------|"])
    for label, value in passport:
        lines.append(f"| {label} | {value} |")
    lines.extend(["", "## Ідея", ""])
    if dossier["idea"]:
        lines.append(dossier["idea"])
        lines.append("")
        lines.append(f"_З {dossier['readme_name'] or 'README'}, без переказу._")
    elif dossier["description"]:
        lines.append(dossier["description"])
        lines.append("")
        lines.append("_З поля description у catalog.json. Окремого вступу в README немає._")
    else:
        lines.append(MISSING)
    lines.extend(["", "## Для чого", ""])
    if dossier["description"]:
        lines.append(dossier["description"])
        lines.append("")
        lines.append("_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._")
    elif dossier["idea"]:
        lines.append(dossier["idea"].split("\n\n", 1)[0])
        lines.append("")
        lines.append("_Окремого опису в каталозі немає. Це перший абзац README._")
    else:
        lines.append(MISSING)

    lines.extend(["", "## Для кого", ""])
    if dossier["audience_section"]:
        lines.append("README має прямий розділ про аудиторію:")
        lines.append("")
        lines.extend(_linked(dossier["audience_section"], rel))
        lines.append("")
    if dossier["audiences"]:
        lines.append("Маркери в описі, темах і вступі (не здогадка понад текст):")
        lines.append("")
        for label, key in dossier["audiences"]:
            lines.append(f"- {label} — у тексті є «{key}».")
        lines.append("")
    elif not dossier["audience_section"]:
        lines.append(
            "Аудиторія прямо не названа, і в описі немає маркерів "
            "(GCS, OSD, ELRS, прошивка, OpenIPC, KiCad)."
        )
    if dossier["topics"]:
        lines.append("")
        lines.append("Теми GitHub: " + ", ".join(f"`{t}`" for t in dossier["topics"]) + ".")

    lines.extend(["", "## Функція", ""])
    if dossier["feature_bullets"]:
        lines.append("Список із розділу features / можливості в README:")
        lines.append("")
        for item in dossier["feature_bullets"]:
            lines.append(f"- {item}")
    else:
        lines.append("Окремого списку функцій у README немає.")
        if dossier["description"]:
            lines.append("")
            lines.append(f"Єдине формулювання функції, яке є в каталозі: {dossier['description']}")

    lines.extend(["", "## Як влаштовано", ""])
    tree = dossier["tree"]
    if tree["top"]:
        lines.append("Корінь теки (без прихованих і без `node_modules` / `.git`):")
        lines.append("")
        for name in tree["top"]:
            lines.append(f"- `{name}`")
        lines.append("")
    if tree["languages"]:
        lang = ", ".join(f"{name} ({count})" for name, count in tree["languages"])
        scope = "обрізано після 2000 файлів" if tree["truncated"] else f"{tree['files_seen']} файлів"
        lines.append(f"Типи файлів за вибіркою ({scope}, глибина до 3): {lang}.")
        lines.append("")
    if dossier["how_section"]:
        lines.append("Фрагмент README про будову:")
        lines.append("")
        lines.extend(_linked(dossier["how_section"], rel))
    if not tree["top"] and not dossier["how_section"]:
        lines.append(MISSING)

    lines.extend(["", "## Що треба", ""])
    wrote_need = False
    if dossier["requirements_section"]:
        lines.extend(_linked(dossier["requirements_section"], rel))
        lines.append("")
        wrote_need = True
    if dossier["manifests"]:
        for fact in dossier["manifests"]:
            lines.append(f"- {fact}")
        wrote_need = True
    if not wrote_need:
        lines.append(MISSING)

    lines.extend(["", "## Інструкція", ""])
    if dossier["instruction_section"]:
        lines.append(
            "Нижче скопійовані розділи README про встановлення, збірку або запуск. "
            "Команди не доповнювались."
        )
        lines.append("")
        lines.extend(_linked(dossier["instruction_section"], rel))
    else:
        lines.append(
            "Окремого розділу Install, Usage, Build або «Інструкція» в README немає. "
            "Команди запуску сюди не додавались."
        )

    if dossier["docs"]:
        lines.extend(["", "## Супутні документи в теці", ""])
        for doc in dossier["docs"]:
            lines.append(f"- [`{doc}`](../../{dossier['path']}/{doc})")

    lines.extend(["", "## З чого зібрана картка", ""])
    bits = ["`catalog.json`"]
    if dossier["readme_name"]:
        bits.append(f"`{dossier['path']}/{dossier['readme_name']}`")
    bits.append("маніфести збірки в корені теки, якщо вони є")
    lines.append(", ".join(bits) + ".")
    lines.append("")
    lines.append(f"Сторінка: `wiki/projects/{page_slug}.md`.")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_hall(hall_id: str, cards: list[dict]) -> str:
    hall = HALLS[hall_id]
    lines = [
        f"# {hall['title']}",
        "",
        hall["lead"],
        "",
        f"Карток у залі: **{len(cards)}**.",
        "",
        "Кожна картка тримає ідею, навіщо проєкт, для кого, функцію, будову, що треба і інструкцію — лише з файлів репозиторію.",
        "",
        "| Проєкт | Для чого (з каталогу або README) | Тека |",
        "|--------|----------------------------------|------|",
    ]
    for card in cards:
        purpose = plain_cell(card["description"] or card["idea"] or "—")
        lines.append(
            f"| [{card['title']}](../projects/{card['slug']}.md) | {purpose} | `{card['path']}` |"
        )
    lines.append("")
    lines.append("[На головну виставки](../Home.md)")
    lines.append("")
    return "\n".join(lines)


def render_home(stats: dict, halls: list[tuple[str, int]]) -> str:
    lines = [
        "# Виставкова вікі бібліотеки",
        "",
        "Це читальний зал поверх складу. Теки на диску лишаються дзеркалами: "
        "їхні шляхи оновлює синхронізація, тому їх не перейменовували.",
        "",
        "Склад виглядав як звалище, бо назва теки — це `репозиторій` плюс шматок опису з GitHub. "
        "Експозиція інша: один шаблон картки на кожен проєкт, який реально лежить у дереві.",
        "",
        "## Масштаб",
        "",
        "| | |",
        "|--|--|",
        f"| Записів у каталозі | **{stats['catalog']}** |",
        f"| Тек на диску з карткою | **{stats['dossiers']}** |",
        f"| У каталозі без локальної копії | **{stats['absent']}** |",
        f"| Власна розробка | **{stats['own']}** |",
        "",
        "Решта каталогу без файлів не отримує вигадану інструкцію. Сирий реєстр: [REPOS.md](../REPOS.md).",
        "",
        "## Як читати картку",
        "",
        "| Розділ | Звідки береться |",
        "|--------|-----------------|",
        "| Ідея | Перші абзаци README |",
        "| Для чого | Поле description каталогу |",
        "| Для кого | Прямий розділ README або маркер у тексті (GCS, ELRS, прошивка…). Поруч слово, яке спрацювало |",
        "| Функція | Маркований список features, якщо він є |",
        "| Як влаштовано | Склад кореня і типи файлів, пораховані по теці |",
        "| Що треба | Розділ requirements і маніфести (`package.json`, `platformio.ini`, `requirements.txt`, …) |",
        "| Інструкція | Розділи Install / Usage / Build, скопійовані з README |",
        "",
        "Порожнє місце в картці означає, що в джерелі цього немає.",
        "",
        "Якщо каталог лишив проєкт у `other`, зал може змінитися за словом у назві, описі або шляху "
        "(детектор, VRX, WiFi Broadcast). Це слово написане на картці.",
        "",
        "## Зали",
        "",
        "| Зал | Карток |",
        "|-----|--------|",
    ]
    for hall_id, count in halls:
        if count <= 0:
            continue
        lines.append(f"| [{HALLS[hall_id]['title']}](halls/{hall_id}.md) | {count} |")
    lines.extend([
        "",
        "## Покажчики",
        "",
        "- [Алфавіт карток](Alphabet.md)",
        "- [Як влаштована сама бібліотека](Library.md)",
        "- [Карта тек](../MAP.md)",
        "- [Повний реєстр, включно з тим, чого ще немає на диску](../REPOS.md)",
        "",
        "## Оновити експозицію",
        "",
        "```bash",
        "python3 fpv-library/scripts/generate_wiki.py",
        "```",
        "",
        "Скрипт переписує `wiki/` з каталогу і локальних тек. Текст карток він не вигадує.",
        "",
    ])
    return "\n".join(lines)


def render_alphabet(cards: list[dict]) -> str:
    groups: dict[str, list[dict]] = {}
    for card in cards:
        key = (card["source"] or card["path"] or "?").lstrip().upper()[:1]
        if not key.isalpha():
            key = "#"
        groups.setdefault(key, []).append(card)
    lines = [
        "# Алфавіт карток",
        "",
        "Індекс локальних тек, які мають виставкову картку.",
        "",
    ]
    for key in sorted(groups):
        lines.append(f"## {key}")
        lines.append("")
        for card in groups[key]:
            label = card["source"] or card["path"]
            lines.append(f"- [{label}](projects/{card['slug']}.md) — `{card['path']}`")
        lines.append("")
    return "\n".join(lines)


def render_library() -> str:
    return """# Як влаштована бібліотека

Ця сторінка про сам монорепозиторій, не про окремий дзеркальний проєкт.

## Ідея

Тримати поруч каталог відкритих FPV і drone репозиторіїв, їхні локальні дзеркала і одну власну розробку, щоб по них можна було ходити як по читальному залу, а не як по теках з обрізаними іменами.

## Для чого

Щоб щоденний discover і sync не лишали після себе лише `catalog.json` і список у `REPOS.md`. Реєстр лишається реєстром. Вікі — шар, який людина читає.

## Для кого

Для того, хто відкриває це дерево і хоче зрозуміти, що в теці лежить, навіщо воно upstream і чи є там інструкція. Не для польоту і не замість документації конкретного проєкту.

## Функція

- Каталог `fpv-library/catalog.json` пам'ятає джерело, шлях, вердикт, категорії, опис.
- `fpv-library/repos/` і окремі теки в корені — локальні копії.
- `wiki/` — картки лише для тек, які є на диску.
- `REPOS.md` — повний реєстр, включно з тим, що ще не скачане.

## Як

```text
GitHub search / keywords / themes
        → catalog.json (keep / watch / skip)
        → sync у локальну теку
        → generate_wiki.py читає README і маніфести
        → wiki/Home.md і картка на проєкт
```

Вердикт `skip` у каталозі не ховає теку, якщо вона вже лежить на диску: картка все одно будується, а в паспорті видно вердикт.

## Що треба

Python 3 і дерево репозиторію. Окремих пакетів генератор вікі не ставить. Мережа для перезбірки карток не потрібна.

## Інструкція

```bash
python3 fpv-library/scripts/generate_wiki.py
python3 -m unittest fpv-library/scripts/test_wiki.py
```

Оновити реєстр і карту тек (окремо від вікі):

```bash
python3 fpv-library/scripts/generate_repo_index.py
python3 fpv-library/scripts/generate_library_map.py
```

Дзеркала підтягує `fpv-library/scripts/sync.py`. Вікі після цього варто зібрати знову: інакше нові теки лишаться без картки.

## Чого генератор не робить

Не перейменовує дзеркала. Не дописує команди, яких немає в README. Не заповнює «для кого», якщо в тексті немає маркера.
"""


def render_sidebar(halls: list[tuple[str, int]]) -> str:
    lines = [
        "# Зміст",
        "",
        "- [Виставка](Home.md)",
        "- [Як влаштована бібліотека](Library.md)",
        "- [Алфавіт](Alphabet.md)",
        "",
        "## Зали",
        "",
    ]
    for hall_id, count in halls:
        if count <= 0:
            continue
        lines.append(f"- [{HALLS[hall_id]['title']}](halls/{hall_id}.md) ({count})")
    lines.append("")
    return "\n".join(lines)
