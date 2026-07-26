"""Contract: every command name the frontend sends must exist in the backend
dispatch table, and every backend dispatch entry should be referenced by the
frontend. This prevents the silent typo class of bug — sending a command name
that doesn't match anything (and the frontend gets no error, the backend just
returns None).

Static analysis only; runs in <1s and adds no runtime overhead.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_INIT = ROOT / "backend" / "commands" / "__init__.py"
FRONTEND_ROOT = ROOT / "src"

_FRONTEND_SUFFIXES = {".svelte", ".ts"}


def _backend_dispatch_keys() -> set[str]:
    src = BACKEND_INIT.read_text(encoding="utf-8")
    m = re.search(r"_DISPATCH\s*=\s*\{(.*?)\n\}", src, re.DOTALL)
    assert m, "_DISPATCH dict not found in backend/commands/__init__.py"
    return set(re.findall(r"""^\s*['"]([a-z_]+)['"]:\s""", m.group(1), re.MULTILINE))


def _iter_frontend_sources() -> list[str]:
    sources: list[str] = []
    for path in FRONTEND_ROOT.rglob("*"):
        if path.suffix not in _FRONTEND_SUFFIXES:
            continue
        if "node_modules" in path.parts:
            continue
        sources.append(path.read_text(encoding="utf-8", errors="ignore"))
    return sources


def _frontend_sendcommand_literals() -> set[str]:
    out: set[str] = set()
    pattern = re.compile(r"sendCommand\(\s*['\"]([a-z_]+)['\"]")
    for src in _iter_frontend_sources():
        out.update(pattern.findall(src))
    return out


# Known orphan sets — each entry is a bug we know about. The assertions below
# require the orphan sets to match these EXACTLY, so new orphans fail loud and
# fixed ones force us to remove the allowlist entry (no silent rot).
KNOWN_FRONTEND_ORPHANS: set[str] = set()
KNOWN_BACKEND_ORPHANS: set[str] = {
    # Dispatch entries with no frontend caller. Kept because either NTRIP-side
    # infrastructure (inject_rtcm), planned UI work (param_load, rally_upload),
    # or sim/headless override (set_vtype) depends on them being available.
    "inject_rtcm",
    "param_load",
    "rally_upload",
    "set_vtype",
}


class TestCommandContract:
    def test_frontend_to_backend_orphans_match_known_set(self):
        """sendCommand('foo') with no backend handler == silent failure.
        Allow only the documented set; any deviation fails CI."""
        dispatch = _backend_dispatch_keys()
        sent = _frontend_sendcommand_literals()
        orphans = sent - dispatch
        new_orphans = orphans - KNOWN_FRONTEND_ORPHANS
        fixed = KNOWN_FRONTEND_ORPHANS - orphans
        assert not new_orphans and not fixed, (
            f"\nFrontend-to-backend command contract drift.\n"
            f"  New unhandled commands (add backend handler or fix typo): {sorted(new_orphans)}\n"
            f"  Now-handled commands (remove from KNOWN_FRONTEND_ORPHANS): {sorted(fixed)}\n"
        )

    def test_backend_to_frontend_orphans_match_known_set(self):
        """Dispatch entry with no frontend caller == dead code or rename
        mismatch. Allow only the documented set; any deviation fails CI."""
        dispatch = _backend_dispatch_keys()
        all_src = "\n".join(_iter_frontend_sources())
        unused = {k for k in dispatch if f"'{k}'" not in all_src and f'"{k}"' not in all_src}
        new_orphans = unused - KNOWN_BACKEND_ORPHANS
        fixed = KNOWN_BACKEND_ORPHANS - unused
        assert not new_orphans and not fixed, (
            f"\nBackend-to-frontend command contract drift.\n"
            f"  New dead dispatch keys (delete handler or wire up frontend): {sorted(new_orphans)}\n"
            f"  Now-used dispatch keys (remove from KNOWN_BACKEND_ORPHANS): {sorted(fixed)}\n"
        )

    def test_dispatch_is_nontrivial(self):
        """Sanity: make sure we actually parsed something."""
        dispatch = _backend_dispatch_keys()
        assert len(dispatch) >= 20, f"Suspiciously few dispatch keys found: {len(dispatch)}"
