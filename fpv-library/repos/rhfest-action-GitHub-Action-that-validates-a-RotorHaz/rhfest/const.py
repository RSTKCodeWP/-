"""Const values for rhfest."""

import logging
import os
import sys
from typing import Final

PLUGIN_DIR: Final[str] = "custom_plugins"
MANIFEST_FILE: Final[str] = "manifest.json"
RHFEST_VERSION = os.getenv("RHFEST_VERSION", "dev")

# Manifest checks
PYPI_PACKAGE_REGEX = (
    r"^[a-zA-Z0-9.-]+"  # Package name
    r"(?:\s*(~=|==|!=|<=|>=|<|>|===)\s*\d+(?:\.\d+)*(\.\*)?)?$"  # Optional versie-spec
)
GIT_URL_REGEX = r"^git\+https://[^\s]+$"
VERSION_REGEX = r"^\d+\.\d+\.\d+(-[a-zA-Z]+(\.\d+)?)?$"

# Logging setup
logging.addLevelName(logging.INFO, "")
logging.addLevelName(logging.ERROR, "::error::")
logging.addLevelName(logging.WARNING, "::warning::")
logging.basicConfig(
    level=logging.INFO,
    format=" %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
LOGGER = logging.getLogger(__name__)
