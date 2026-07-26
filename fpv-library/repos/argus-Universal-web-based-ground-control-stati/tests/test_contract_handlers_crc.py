"""Contract: every MAVLink msg id we register a handler for must have a CRC
extra entry in _CRC_EXTRA. Without that entry, _parse_mavlink_frame silently
drops the frame and the handler is never called — exactly the silent failure
mode that masked the compass-calibration bug (msg 191/192).

This replaces the previous runtime "fail-loud" warning, which was too noisy
because it also fired for every legitimate ArduPilot message we don't process
(SYSTEM_TIME, RAW_IMU, SCALED_PRESSURE, ...). Static check catches the
dangerous class without per-frame log spam.
"""

from __future__ import annotations

import re
from pathlib import Path

from backend.drone_link import _CRC_EXTRA

ROOT = Path(__file__).resolve().parent.parent
HANDLERS = ROOT / "backend" / "mavlink_handlers.py"


def _registered_handler_ids() -> set[int]:
    src = HANDLERS.read_text(encoding="utf-8")
    # Match `mavlink_dispatch.register(<int>, ...)` calls inside init_handlers
    return {int(m.group(1)) for m in re.finditer(r"mavlink_dispatch\.register\(\s*(\d+)\s*,", src)}


class TestHandlerCrcContract:
    def test_every_handler_has_crc_entry(self):
        handler_ids = _registered_handler_ids()
        crc_ids = set(_CRC_EXTRA.keys())
        missing = handler_ids - crc_ids
        assert not missing, (
            f"\nHandlers registered for msg ids {sorted(missing)} but no "
            f"matching entry in _CRC_EXTRA. The parser drops these frames "
            f"silently, so the handler is dead code until you add the CRC."
        )

    def test_handler_set_is_nontrivial(self):
        ids = _registered_handler_ids()
        assert len(ids) >= 20, f"Suspiciously few handler registrations: {len(ids)}"
