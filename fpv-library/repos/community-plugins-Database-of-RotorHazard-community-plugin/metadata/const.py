"""Const for metadata scripts."""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
PLUGIN_LIST_FILE = "plugins.json"
OUTPUT_DIR = "output/plugin"
COMPARE_IGNORE: list[str] = ["last_fetched", "etag_release", "etag_repository"]
EXCLUDED_KEYS: list[str] = []

# Loggin setup
logging.addLevelName(logging.INFO, "")
logging.addLevelName(logging.ERROR, "::error::")
logging.addLevelName(logging.WARNING, "::warning::")
logging.basicConfig(
    level=logging.INFO,
    format=" %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
LOGGER = logging.getLogger(__name__)

# Create output directories
Path(f"{OUTPUT_DIR}/diff").mkdir(parents=True, exist_ok=True)
