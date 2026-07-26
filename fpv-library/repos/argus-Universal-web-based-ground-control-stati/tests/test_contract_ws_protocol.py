"""Contract: backend _build_state() keys & types must match frontend DroneState.

If the backend adds/removes a field in the WS push dict, this test fails until
the TypeScript interface is updated to match (or vice versa). Catches silent
drift between the two sides of the WebSocket protocol.

The type-check layer (test_backend_types_match_frontend) maps TypeScript type
annotations to Python type predicates and validates every value in the real
_build_state() output.  If the backend sends a string where the frontend
expects a number (or vice versa), the test catches it.
"""

from __future__ import annotations

import re
from pathlib import Path

from backend.drone_link import DroneLink

ROOT = Path(__file__).resolve().parent.parent
TYPES_TS = ROOT / "src" / "lib" / "types.ts"

# ---------------------------------------------------------------------------
# TypeScript -> Python type mapping
# ---------------------------------------------------------------------------

# A "type predicate" is a callable (value) -> bool that returns True when
# the Python value is compatible with the declared TypeScript type.

_TS_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "number": (int, float),
    "string": (str,),
    "boolean": (bool,),
}


def _py_type_ok(ts_type: str, value: object) -> bool:
    """Return True when *value*'s Python type is compatible with *ts_type*.

    Handles:
    - primitives: number, string, boolean
    - arrays: number[], string[], [number, string][], { ... }[]
    - nullable: FlightSummary | null
    - literal strings: 'state'
    """
    ts_type = ts_type.strip()

    # Nullable union: "X | null"
    if "| null" in ts_type or "null |" in ts_type:
        if value is None:
            return True
        inner = ts_type.replace("| null", "").replace("null |", "").strip()
        return _py_type_ok(inner, value)

    # Literal string: 'state'
    if ts_type.startswith("'") and ts_type.endswith("'"):
        return isinstance(value, str) and value == ts_type.strip("'")

    # Typed arrays: number[], string[], [number, string][]
    if ts_type.endswith("[]"):
        if not isinstance(value, list):
            return False
        inner = ts_type[:-2].strip()
        # Tuple array like [number, string][]
        if inner.startswith("[") and inner.endswith("]"):
            return all(isinstance(item, (list, tuple)) for item in value)
        # Object array like { ... } — inline object types
        if inner.endswith("}") or inner.startswith("{"):
            return all(isinstance(item, dict) for item in value)
        # Primitive arrays like number[], string[]
        py_types = _TS_TYPE_MAP.get(inner)
        if py_types:
            return all(isinstance(item, py_types) for item in value)
        return True  # unknown inner type — skip element validation

    # Named reference type (e.g. FlightSummary) — should be a dict
    if ts_type[0].isupper():
        return isinstance(value, dict)

    # Primitive
    py_types = _TS_TYPE_MAP.get(ts_type)
    if py_types:
        # bool is a subclass of int in Python; TypeScript "number" should
        # NOT accept a Python bool.
        if ts_type == "number" and isinstance(value, bool):
            return False
        return isinstance(value, py_types)

    return True  # unknown type — pass silently


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _backend_state_keys() -> set[str]:
    """Get all keys from a real _build_state() call."""
    link = DroneLink()
    state = link._build_state()
    return set(state.keys())


def _parse_dronestate_block() -> str:
    """Return the raw text between the braces of DroneState { ... }."""
    src = TYPES_TS.read_text(encoding="utf-8")
    start = src.index("export interface DroneState")
    brace_start = src.index("{", start)
    depth, pos = 1, brace_start + 1
    while depth > 0 and pos < len(src):
        if src[pos] == "{":
            depth += 1
        elif src[pos] == "}":
            depth -= 1
        pos += 1
    return src[brace_start + 1 : pos - 1]


def _frontend_state_fields() -> set[str]:
    """Parse DroneState interface field *names* from types.ts.

    Kept for backward compatibility with test_unit_thread_safety which
    imports this function.
    """
    return set(_frontend_state_field_types().keys())


def _frontend_state_field_types() -> dict[str, str]:
    """Parse DroneState interface field names AND TypeScript types.

    Returns {field_name: ts_type_string}.  For inline object types
    (e.g. ``vehicles: { ... }[]``) the type is collapsed to ``object[]``.
    """
    block = _parse_dronestate_block()
    fields: dict[str, str] = {}
    d = 0
    pending_name: str | None = None
    pending_open: int = 0
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("*"):
            continue

        # If we're inside an inline object block, track depth to find the close.
        if pending_name is not None:
            pending_open += stripped.count("{") - stripped.count("}")
            if pending_open <= 0:
                # Capture trailing [] after closing brace
                after_brace = stripped[stripped.rfind("}") + 1 :].rstrip(";").strip()
                fields[pending_name] = "object" + after_brace
                pending_name = None
            continue

        if d == 0:
            m = re.match(r"(\w+)\??\s*:\s*(.+)", stripped)
            if m:
                name = m.group(1)
                rest = m.group(2).rstrip(";").strip()
                if "{" in rest:
                    # Inline object type — track depth across lines
                    open_count = rest.count("{") - rest.count("}")
                    if open_count <= 0:
                        # Single-line inline object (unlikely but safe)
                        after_brace = rest[rest.rfind("}") + 1 :].rstrip(";").strip()
                        fields[name] = "object" + after_brace
                    else:
                        pending_name = name
                        pending_open = open_count
                        continue  # don't update d — we're tracking separately
                else:
                    fields[name] = rest
        d += stripped.count("{") - stripped.count("}")
    return fields


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWsProtocolContract:
    def test_backend_keys_match_frontend_fields(self):
        """Every key in _build_state() should have a field in DroneState."""
        backend = _backend_state_keys()
        frontend = _frontend_state_fields()
        # 'type' is a discriminator, always present in both
        only_backend = backend - frontend
        only_frontend = frontend - backend
        assert not only_backend, (
            "\nBackend pushes keys that DroneState does not declare:\n"
            + "\n".join(f"  {k}" for k in sorted(only_backend))
            + "\n\nAdd these fields to src/lib/types.ts DroneState interface."
        )
        assert not only_frontend, (
            "\nDroneState declares fields that backend never pushes:\n"
            + "\n".join(f"  {k}" for k in sorted(only_frontend))
            + "\n\nRemove these fields from src/lib/types.ts or add them to _build_state()."
        )

    def test_backend_types_match_frontend(self):
        """Every value in _build_state() must have the correct Python type
        for the TypeScript type declared in DroneState."""
        link = DroneLink()
        state = link._build_state()
        ts_types = _frontend_state_field_types()

        mismatches: list[str] = []
        for key, ts_type in ts_types.items():
            if key not in state:
                continue  # key-existence is covered by test_backend_keys_match
            value = state[key]
            if not _py_type_ok(ts_type, value):
                mismatches.append(
                    f"  {key}: expected TS '{ts_type}' "
                    f"but got Python {type(value).__name__} = {value!r}"
                )

        assert not mismatches, (
            "\nBackend _build_state() values have wrong types for DroneState:\n"
            + "\n".join(mismatches)
            + "\n\nFix the backend to return the correct Python type, "
            "or update types.ts if the frontend type is wrong."
        )
