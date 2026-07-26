"""Structured logging setup."""

import logging
import os
import sys

_fmt = logging.Formatter(
    "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(_fmt)

_level_name = os.environ.get("ARGUS_LOG_LEVEL", "INFO").upper()
_level = getattr(logging, _level_name, logging.INFO)

logger = logging.getLogger("gcs")
logger.setLevel(_level)
logger.addHandler(_handler)
logger.propagate = False
