"""Contract: every field the backend serializes in DroneLink.get_state() must
also exist in the frontend's DroneState TypeScript interface. Drift here means
the frontend silently ignores a field (after a backend addition) or breaks at
runtime trying to read undefined (after a backend rename/removal).

Pure static analysis — runs in <1s, no Python imports of frontend.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRONE_LINK = ROOT / "backend" / "drone_link.py"
PARAM_MGR = ROOT / "backend" / "param_manager.py"
TYPES_TS = ROOT / "src" / "lib" / "types.ts"


def _build_state_dict_keys() -> set[str]:
    """Parse DroneLink._build_state and return the set of literal string keys
    in the returned dict (plus the keys spread via param_mgr.get_status())."""
    src = DRONE_LINK.read_text(encoding="utf-8")
    tree = ast.parse(src)
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == "_build_state"):
            continue
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Return) or not isinstance(sub.value, ast.Dict):
                continue
            for k in sub.value.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    keys.add(k.value)
            # ** spreads (e.g., **self.param_mgr.get_status()) appear as None
            # keys in ast.Dict — we resolve them separately below.
        break
    return keys


def _param_status_keys() -> set[str]:
    """Parse ParamManager.get_status() — the dict spread into _build_state."""
    src = PARAM_MGR.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == "get_status"):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
                return {k.value for k in sub.value.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    return set()


def _drone_state_interface_keys() -> set[str]:
    """Parse src/lib/types.ts and return the field names declared at the top
    level of the DroneState interface (ignoring nested object-type fields).

    Walks brace depth manually because TypeScript inline types like
    `vehicles: { sysid: number; ... }[]` contain `}` characters that would
    confuse a naive `\\{...\\}` regex match.
    """
    src = TYPES_TS.read_text(encoding="utf-8")
    m = re.search(r"export\s+interface\s+DroneState\s*\{", src)
    assert m, "DroneState interface not found in types.ts"
    i = m.end()
    depth = 1
    body_chars: list[str] = []
    # Tracks brace depth relative to the interface body so we can mark which
    # characters are at the top level (depth == 1) — only those positions
    # contribute a field name.
    top_level: list[bool] = []
    while i < len(src) and depth > 0:
        ch = src[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        body_chars.append(ch)
        top_level.append(depth == 1)
        i += 1
    # Replace non-top-level chars with spaces so the field-name regex
    # cannot match inside a nested object type.
    flat = "".join(c if t else " " for c, t in zip(body_chars, top_level, strict=True))
    return set(re.findall(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\??\s*:", flat, re.MULTILINE))


class TestStateContract:
    def test_backend_fields_match_frontend_interface(self):
        backend = _build_state_dict_keys() | _param_status_keys()
        frontend = _drone_state_interface_keys()
        only_backend = backend - frontend
        only_frontend = frontend - backend
        assert not only_backend and not only_frontend, (
            f"\nState shape drift between backend get_state() and frontend DroneState:\n"
            f"  Only in backend (frontend will ignore): {sorted(only_backend)}\n"
            f"  Only in frontend (will be undefined at runtime): {sorted(only_frontend)}\n"
        )

    def test_field_sets_are_nontrivial(self):
        """Sanity: parsing actually picked up fields, not 0."""
        backend = _build_state_dict_keys()
        frontend = _drone_state_interface_keys()
        assert len(backend) >= 30, f"Backend field count looks broken: {len(backend)}"
        assert len(frontend) >= 30, f"Frontend field count looks broken: {len(frontend)}"
