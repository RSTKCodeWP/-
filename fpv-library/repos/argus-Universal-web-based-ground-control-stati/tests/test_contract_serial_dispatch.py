"""Contract test: serial dispatch table parity with backend _DISPATCH.

Verifies that every backend command in _DISPATCH is either:
- Present in the frontend _serialDispatch table (transport.ts), OR
- Explicitly listed as a known WS-only command (by design not in serial dispatch)

Also verifies the serial dispatch table has no keys absent from the backend.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Known WS-only commands: these are intentionally NOT in the serial dispatch
# table because they require backend infrastructure (file I/O, multi-step state,
# or backend-specific data access).
_WS_ONLY = {
    "mission_upload",
    "fence_upload",
    "rally_upload",
    "mission_download",
    "set_vtype",
    "switch_vehicle",
    "clear_summary",
    "inspector_toggle",
    "serial_control",
    "inject_rtcm",
    "ntrip_start",
    "ntrip_stop",
    "log_list",
    "log_download",
    "param_load",
    # param_save writes a host-side JSON backup — the serial path can't replicate that.
    # UIs that want FC NVRAM write use param_save_to_flash instead (in _serialDispatch).
    "param_save",
}


def _get_backend_dispatch_keys() -> set[str]:
    """Extract all command keys from backend _DISPATCH dict."""
    from backend.commands import _DISPATCH

    return set(_DISPATCH.keys())


def _get_serial_dispatch_keys() -> set[str]:
    """Parse _serialDispatch keys from src/lib/transport.ts via regex."""
    ts_path = ROOT / "src" / "lib" / "transport.ts"
    source = ts_path.read_text(encoding="utf-8")

    # Find the block starting with `const _serialDispatch` and ending at `};`
    match = re.search(
        r"const _serialDispatch\s*:\s*Record<[^>]+>\s*=\s*\{(.*?)\n\};",
        source,
        re.DOTALL,
    )
    if not match:
        raise RuntimeError("Could not find _serialDispatch block in transport.ts")

    block = match.group(1)
    # Extract all keys: lines like `  key:` (possibly with comments before them)
    keys = re.findall(r"^\s+(\w+)\s*:", block, re.MULTILINE)
    return set(keys)


class TestSerialDispatchParity:
    def test_all_flight_commands_have_serial_handler(self):
        """Every backend command not in WS-only set must be in _serialDispatch."""
        backend_keys = _get_backend_dispatch_keys()
        serial_keys = _get_serial_dispatch_keys()

        missing = (backend_keys - _WS_ONLY) - serial_keys
        assert not missing, (
            "Backend commands missing from _serialDispatch (and not in WS-only list):\n"
            + "\n".join(f"  {k}" for k in sorted(missing))
            + "\nAdd them to _serialDispatch in src/lib/transport.ts or to _WS_ONLY in this test."
        )

    def test_no_extra_serial_commands_beyond_backend(self):
        """No key in _serialDispatch should be completely absent from the backend."""
        backend_keys = _get_backend_dispatch_keys()
        serial_keys = _get_serial_dispatch_keys()

        phantom = serial_keys - backend_keys
        assert not phantom, (
            "Keys in _serialDispatch not found in backend _DISPATCH (possible typo):\n"
            + "\n".join(f"  {k}" for k in sorted(phantom))
        )
