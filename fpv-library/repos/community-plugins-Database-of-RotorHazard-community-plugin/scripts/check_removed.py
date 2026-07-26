"""Check if a plugin has been listed as removed."""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

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


def check_removed_repository(repo: str, data_file: str) -> None:
    """Check if a plugin has been listed as removed.

    Args:
    ----
        repo (str): Repository name.
        data_file (str): Path to the removed.json file.

    """
    try:
        with Path.open(data_file) as file:
            removed_plugins = json.load(file)

        if repo in removed_plugins:
            LOGGER.warning(f"⚠️ '{repo}' is removed from the RH Community Plugins DB.")
            sys.exit(1)
    except FileNotFoundError:
        LOGGER.exception(f"::error::Could not find {data_file}. Ensure it exists.")
        sys.exit(1)
    except json.JSONDecodeError:
        LOGGER.exception(f"::error::Invalid JSON format in {data_file}")
        sys.exit(1)
    except Exception:
        LOGGER.exception("Unexpected error occurred")
        sys.exit(1)
    else:
        LOGGER.info(f"✅ '{repo}' is not removed from the RH Community Plugins DB.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate repository against removed list."
    )
    parser.add_argument(
        "--data-file",
        required=True,
        help="Path to the short list of removed plugins.",
    )
    args = parser.parse_args()

    repo = os.environ.get("REPOSITORY").lower()
    if not repo:
        LOGGER.error("'REPOSITORY' environment variable is not set or empty.")
        sys.exit(1)

    check_removed_repository(repo, args.data_file)
