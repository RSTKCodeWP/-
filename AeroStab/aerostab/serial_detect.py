"""Discover UART / TCP endpoints for MAVLink companion link."""

from __future__ import annotations

import glob
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

CANDIDATES = (
    "/dev/serial0",
    "/dev/ttyAMA0",
    "/dev/ttyS0",
    "/dev/ttyUSB0",
    "/dev/ttyACM0",
)


def list_serial_candidates() -> List[str]:
    found: List[str] = []
    for path in CANDIDATES:
        if Path(path).exists():
            found.append(path)
    # Extra USB serial devices
    for path in sorted(glob.glob("/dev/ttyUSB*")) + sorted(glob.glob("/dev/ttyACM*")):
        if path not in found:
            found.append(path)
    return found


def resolve_mavlink_port(configured: str) -> str:
    """Resolve ``auto`` / empty to first existing serial device; pass TCP/UDP through."""
    port = (configured or "").strip()
    if not port or port.lower() == "auto":
        cands = list_serial_candidates()
        if not cands:
            logger.warning("No serial devices found; falling back to /dev/serial0")
            return "/dev/serial0"
        logger.info("MAVLink auto-selected %s (from %s)", cands[0], cands)
        return cands[0]
    if port.startswith(("tcp:", "tcpin:", "udp:", "udpin:")):
        return port
    if not Path(port).exists() and not port.startswith("/dev/"):
        # Allow relative weirdness to pass through for tests
        return port
    if port.startswith("/dev/") and not Path(port).exists():
        cands = list_serial_candidates()
        if cands:
            logger.warning("%s missing — using %s", port, cands[0])
            return cands[0]
    return port
