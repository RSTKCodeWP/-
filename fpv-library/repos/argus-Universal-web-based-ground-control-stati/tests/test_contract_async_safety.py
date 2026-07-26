"""Contract test: no bare blocking calls inside async functions.

Scans all *.py files under backend/ (excluding __pycache__) for async def
functions that contain blocking calls not wrapped in await aio(...) or
asyncio.to_thread(...).

Blocking patterns checked:
  - urlreq.urlopen( / urllib.request.urlopen(
  - shutil.rmtree(
  - sqlite3.connect(
  - time.sleep(   (but NOT await asyncio.sleep())

A line is exempt if:
  - It also contains `await aio(` or `asyncio.to_thread(` on the same line, OR
  - The previous non-blank line contains `await aio(` (multi-line lambda continuation), OR
  - The line is inside a nested sync `def` helper inside the async function.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"

# Blocking call patterns to detect (bare calls inside async def bodies)
_BLOCKING_PATTERNS = [
    re.compile(r"urlreq\.urlopen\("),
    re.compile(r"urllib\.request\.urlopen\("),
    re.compile(r"shutil\.rmtree\("),
    re.compile(r"sqlite3\.connect\("),
    re.compile(r"(?<!asyncio\.)(?<!\.)time\.sleep\("),
    re.compile(r"subprocess\.(?:check_output|check_call|call|run)\("),
]

# Exemption patterns: if ANY of these appear on the same line, the line is safe
_EXEMPT_SAME_LINE = [
    re.compile(r"await\s+aio\("),
    re.compile(r"asyncio\.to_thread\("),
    re.compile(r"await\s+asyncio\.sleep\("),
]

# Exemption patterns for the PREVIOUS non-blank line (multi-line continuations
# like `data = await aio(\n    lambda: urlreq.urlopen(...)`).
_EXEMPT_PREV_LINE = [
    re.compile(r"await\s+aio\("),
    re.compile(r"asyncio\.to_thread\("),
]

# Pattern to detect `async def` lines and capture their indentation
_ASYNC_DEF_RE = re.compile(r"^(\s*)async\s+def\s+\w+")

# Pattern to detect nested sync `def` inside async functions
_SYNC_DEF_RE = re.compile(r"^(\s*)def\s+\w+")


def _is_exempt_same_line(line: str) -> bool:
    """Return True if the line is already wrapped in an approved async pattern."""
    return any(p.search(line) for p in _EXEMPT_SAME_LINE)


def _is_exempt_prev_line(prev_line: str) -> bool:
    """Return True if the previous non-blank line is an approved async wrapper start."""
    return any(p.search(prev_line) for p in _EXEMPT_PREV_LINE)


def _has_blocking_call(line: str) -> str | None:
    """Return the pattern string if a blocking call is found, else None."""
    for p in _BLOCKING_PATTERNS:
        if p.search(line):
            return p.pattern
    return None


def _collect_violations(path: Path) -> list[str]:
    """Scan a single Python file for blocking calls inside async def bodies."""
    source = path.read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()

    violations: list[str] = []

    # State machine tracking:
    # async_indent: indentation of the innermost active `async def`, or None
    # nested_sync_indent: indentation of a nested sync `def` inside async, or None
    # prev_content_line: last non-blank, non-comment line (for multi-line detection)
    async_indent: int | None = None
    nested_sync_indent: int | None = None
    prev_content_line: str = ""

    for lineno, raw_line in enumerate(lines, start=1):
        stripped = raw_line.rstrip()
        stripped_lstrip = stripped.lstrip()

        # Skip blank lines and comment-only lines (they don't affect indent logic)
        if not stripped_lstrip or stripped_lstrip.startswith("#"):
            continue

        current_indent = len(raw_line) - len(raw_line.lstrip())

        # --- Exit async def scope when dedenting back to or past its level ---
        if async_indent is not None and current_indent <= async_indent:
            # Check: is this a new async def at the same level? Detected below.
            # For now just clear and let the re-detection pick it up.
            async_indent = None
            nested_sync_indent = None

        # --- Handle nested sync def exit ---
        if nested_sync_indent is not None:
            # We're tracking a nested sync def. Its body is at depth > nested_sync_indent.
            # We exit the nested def when we return to indent <= nested_sync_indent.
            # BUT: the `def` statement itself is at nested_sync_indent; its body is
            # at nested_sync_indent + 4 (or more). So we need to exit when current
            # indent is <= nested_sync_indent (i.e., a sibling statement in the async fn).
            if current_indent <= nested_sync_indent:
                nested_sync_indent = None

        # --- Detect `async def` statement ---
        m = _ASYNC_DEF_RE.match(raw_line)
        if m:
            async_indent = len(m.group(1))
            nested_sync_indent = None
            prev_content_line = stripped
            continue

        # --- Detect nested sync `def` inside an async function ---
        if async_indent is not None and nested_sync_indent is None:
            m2 = _SYNC_DEF_RE.match(raw_line)
            if m2 and current_indent > async_indent:
                # This is a sync helper defined inside the async function.
                nested_sync_indent = current_indent
                prev_content_line = stripped
                continue

        # --- Check for blocking calls when inside async def, not in nested sync def ---
        if async_indent is not None and nested_sync_indent is None:
            pattern = _has_blocking_call(stripped_lstrip)
            if pattern:
                # Exempt if same line has wrapper
                if _is_exempt_same_line(stripped):
                    prev_content_line = stripped
                    continue
                # Exempt if previous content line starts an `await aio(` call
                # (this line is a continuation / multi-line lambda argument)
                if _is_exempt_prev_line(prev_content_line):
                    prev_content_line = stripped
                    continue
                rel = path.relative_to(ROOT)
                violations.append(
                    f"{rel}:{lineno}: async function contains blocking call ({pattern})"
                )

        prev_content_line = stripped

    return violations


class TestAsyncSafety:
    def test_no_blocking_calls_in_async_functions(self):
        """No bare blocking I/O calls should appear inside async def bodies."""
        all_violations: list[str] = []

        for py_file in sorted(BACKEND_DIR.rglob("*.py")):
            if "__pycache__" in py_file.parts:
                continue
            all_violations.extend(_collect_violations(py_file))

        assert not all_violations, (
            "Blocking calls detected inside async functions:\n"
            + "\n".join(all_violations)
            + "\nWrap them with `await aio(lambda: ...)` or `await asyncio.to_thread(...)`."
        )
