"""Centralized configuration — all tunable constants in one place."""

from __future__ import annotations

import asyncio
import os
import re
from functools import partial
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
VERSION = re.search(r'^version = "([^"]+)"', (ROOT_DIR / "pyproject.toml").read_text(), re.MULTILINE).group(1)


async def aio(fn, *args):
    """Run a blocking function in the default executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(fn, *args) if args else fn)


def _env(key: str, default, cast=None):
    val = os.environ.get(key)
    if val is None:
        return default
    cast_fn = cast or type(default)
    try:
        return cast_fn(val)
    except (ValueError, TypeError):
        # Bad env var (e.g. ARGUS_PORT=abc) used to crash at module import
        # before logging was configured, leaving the operator with a bare
        # traceback. Fall back to the default and log a warning so the
        # process still starts.
        import logging

        logging.getLogger("gcs").warning(
            "Invalid value for %s=%r; falling back to default %r",
            key,
            val,
            default,
        )
        return default


class Config:
    HOST: str = _env("ARGUS_HOST", "127.0.0.1")
    PORT: int = _env("ARGUS_PORT", 8100)

    # Connection
    TCP_CONNECT_TIMEOUT: float = 5.0
    TCP_READ_TIMEOUT: float = 0.1
    UDP_READ_TIMEOUT: float = 0.1
    SERIAL_READ_TIMEOUT: float = 0.1
    SERIAL_BAUD: int = 57600

    # Heartbeat / link management
    HEARTBEAT_INTERVAL: float = 0.5
    LINK_LOST_TIMEOUT: float = 5.0
    RECONNECT_DELAY: float = 3.0
    MAIN_LOOP_SLEEP: float = 0.02

    # WebSocket push rates
    WS_PUSH_INTERVAL_CONNECTED: float = 0.2
    WS_PUSH_INTERVAL_IDLE: float = 1.0

    # Logging
    LOG_WRITE_INTERVAL: float = 0.25
    LOG_DIR: Path = ROOT_DIR / "logs"

    # Tile cache
    TILE_CACHE_MAX: int = 50000
    TILE_DOWNLOAD_TIMEOUT: float = 10.0

    # SRTM terrain
    SRTM_CACHE_MAX: int = 500
    SRTM_DOWNLOAD_TIMEOUT: float = 10.0
    SRTM_FILE_MAX: int = 30 * 1024 * 1024  # 30 MB

    # Firmware
    FIRMWARE_MAX_SIZE: int = 50 * 1024 * 1024  # 50 MB
    FIRMWARE_HTML_MAX: int = 1024 * 1024  # 1 MB
    FIRMWARE_LIST_TIMEOUT: float = 10.0
    FIRMWARE_DOWNLOAD_TIMEOUT: float = 60.0

    # Param metadata
    PARAM_CACHE_TTL: int = 86400 * 7
    PARAM_DOWNLOAD_TIMEOUT: float = 15.0
    PARAM_FETCH_TIMEOUT: float = 60.0
    # If no PARAM_VALUE has been seen for this many seconds during a fetch,
    # but total_count > received, assume packet loss and start re-requesting
    # missing indices individually via PARAM_REQUEST_READ (msg 20).
    PARAM_GAP_FILL_DELAY: float = 2.0

    # Mission
    MISSION_START_DELAY: float = 0.3
    MISSION_DL_TIMEOUT: float = 30.0
    STREAM_REQUEST_SPACING: float = 0.01
    PARAM_LOAD_SPACING: float = 0.02

    # Git version
    GIT_HASH_TIMEOUT: float = 2.0

    # Validation
    VALID_BAUD_RATES: tuple = (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600)
    VALID_PROTOCOLS: tuple = ("auto", "standard", "pllink")
    VIDEO_URL_MAX_LEN: int = 2048


cfg = Config()

if not 1 <= cfg.PORT <= 65535:
    import logging

    logging.getLogger("gcs").warning(
        "ARGUS_PORT=%d out of range 1-65535; using default 8100",
        cfg.PORT,
    )
    cfg.PORT = 8100
