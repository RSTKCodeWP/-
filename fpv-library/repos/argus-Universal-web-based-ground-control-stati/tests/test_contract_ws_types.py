"""Contract: every WS message type emitted by the backend has a matching
handler in the frontend ws.ts switch-case.

Catches:
  - Backend adds a new message type but frontend never handles it
    (e.g. param_timeout was missing until the audit caught it)
  - Typos in type strings that silently drop messages

How it works:
  - Scans backend Python files for dict literals with 'type': '<name>'
  - Scans frontend ws.ts for case '<name>' in the message switch
  - Reports any backend types not handled in the frontend
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
WS_TS = ROOT / "src" / "lib" / "ws.ts"

# Types that are intentionally not handled by the main WS switch because
# they are responses to specific requests (sent back to the requesting
# client only, not broadcast) — the frontend handles these inline via
# promise/callback patterns or dedicated message listeners.
EXCLUDED_TYPES = {
    "connect_result",  # handled by sendConnect callback
    "role_update",  # multi-client role negotiation
    "handoff_request",  # pilot handoff protocol
    "handoff_granted",  # pilot handoff protocol
    "handoff_released",  # pilot handoff protocol
}

# Regex: 'type': 'some_type' or "type": "some_type" — captures the type name
_BACKEND_TYPE_RE = re.compile(r"""['"]type['"]\s*:\s*['"]([a-z_]+)['"]""")

# Regex: case 'some_type' — captures the case label
_FRONTEND_CASE_RE = re.compile(r"case\s+'([a-z_]+)'")


def _scan_backend_types() -> set[str]:
    types: set[str] = set()
    for py in BACKEND.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        types.update(_BACKEND_TYPE_RE.findall(text))
    # param_value is an internal type batched into param_batch by ws_manager
    types.discard("param_value")
    return types


def _scan_frontend_cases() -> set[str]:
    text = WS_TS.read_text(encoding="utf-8")
    # Collect both top-level msg.type cases and nested event_type cases
    return set(_FRONTEND_CASE_RE.findall(text))


class TestWSTypeContract:
    def test_backend_types_handled_in_frontend(self):
        backend = _scan_backend_types() - EXCLUDED_TYPES
        frontend = _scan_frontend_cases()
        unhandled = backend - frontend
        assert not unhandled, (
            f"Backend emits WS types not handled in frontend ws.ts: {sorted(unhandled)}\n"
            "Add a case in ws.ts or add to EXCLUDED_TYPES with a comment."
        )

    def test_no_phantom_frontend_cases(self):
        """Frontend handles a type the backend never sends — likely stale."""
        backend = _scan_backend_types()
        frontend = _scan_frontend_cases()
        # event_type sub-cases (armed, disarmed, etc.) are nested inside the
        # 'event' case — they match on event_type, not msg.type, so they won't
        # appear in the backend type scan. Filter them out.
        event_subtypes = {
            "armed",
            "disarmed",
            "connected",
            "disconnected",
            "link_lost",
            "mission_ack_ok",
            "mission_ack_fail",
            "fence_ack_ok",
            "fence_ack_fail",
            "cmd_ack_fail",
            "rtl",
            "unsupported_fc",
        }
        phantom = frontend - backend - event_subtypes - EXCLUDED_TYPES
        assert not phantom, (
            f"Frontend ws.ts handles types never emitted by backend: {sorted(phantom)}\n"
            "Remove the dead case or check the backend scan regex."
        )
