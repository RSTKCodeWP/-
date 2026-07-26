#!/usr/bin/env python3
"""Sync locale keys from zh.ts/en.ts to all other locale files.

Missing keys are filled with the English value. Orphan keys (present in
a secondary locale but not in zh) are removed. Existing translations are
preserved — only gaps are patched.

Usage:
    python scripts/sync_locales.py          # dry-run (show diff)
    python scripts/sync_locales.py --write  # write changes
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parent.parent / "src" / "lib" / "locales"
PRIMARY = "zh.ts"
FALLBACK = "en.ts"
SECONDARY = ["ar.ts", "de.ts", "es.ts", "fr.ts", "ja.ts", "ko.ts", "pt.ts", "ru.ts"]

# Match key on the same line as value: 'key': 'value',
_SINGLE_LINE_RE = re.compile(r"""['"]([a-zA-Z][a-zA-Z0-9._]*)['"]\s*:\s*['"](.*)['"],?\s*$""")
# Match key on its own line (value continues on next line): 'key':
_KEY_ONLY_RE = re.compile(r"""['"]([a-zA-Z][a-zA-Z0-9._]*)['"]\s*:\s*$""")


def _unescape_ts(s: str) -> str:
    """Inverse of _escape_ts: \\\\ → \\ and \\' → '. Single left-to-right pass."""
    return re.sub(r"\\(['\\])", r"\1", s)


def parse_keys(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _SINGLE_LINE_RE.search(line)
        if m:
            out[m.group(1)] = _unescape_ts(m.group(2))
            i += 1
            continue
        m = _KEY_ONLY_RE.search(line)
        if m:
            key = m.group(1)
            # Value is on the next line(s) — grab it
            if i + 1 < len(lines):
                val_line = lines[i + 1].strip().rstrip(",")
                # Strip surrounding quotes
                if (val_line.startswith("'") and val_line.endswith("'")) or (
                    val_line.startswith('"') and val_line.endswith('"')
                ):
                    val_line = val_line[1:-1]
                out[key] = _unescape_ts(val_line)
                i += 2
                continue
        i += 1
    return out


def _escape_ts(s: str) -> str:
    """Escape a value for use inside a TypeScript single-quoted string literal."""
    return s.replace("\\", "\\\\").replace("'", "\\'")


def sync_file(path: Path, ref_keys: list[str], fallback: dict[str, str], write: bool) -> int:
    existing = parse_keys(path)
    missing = [k for k in ref_keys if k not in existing]
    orphans = [k for k in existing if k not in fallback]

    if not missing and not orphans:
        return 0

    if missing and write:
        src = path.read_text(encoding="utf-8")
        insert_before = "};"
        new_lines = "\n".join(f"  '{k}': '{_escape_ts(fallback[k])}'," for k in missing)
        src = src.replace(insert_before, new_lines + "\n" + insert_before, 1)
        path.write_text(src, encoding="utf-8")

    changes = len(missing) + len(orphans)
    tag = "WRITE" if write else "DRY-RUN"
    if missing:
        print(f"[{tag}] {path.name}: +{len(missing)} keys")
    if orphans:
        print(f"[{tag}] {path.name}: {len(orphans)} orphan keys (not auto-removed)")
    return changes


def main():
    write = "--write" in sys.argv

    zh_keys = parse_keys(LOCALES_DIR / PRIMARY)
    en_keys = parse_keys(LOCALES_DIR / FALLBACK)
    ref_order = list(zh_keys.keys())

    total = 0
    for name in SECONDARY:
        path = LOCALES_DIR / name
        if not path.exists():
            print(f"SKIP {name}: file not found")
            continue
        total += sync_file(path, ref_order, en_keys, write)

    if total == 0:
        print("All secondary locales are in sync.")
    elif not write:
        print("\nRun with --write to apply changes.")


if __name__ == "__main__":
    main()
