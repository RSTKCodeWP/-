"""Sorts a JSON file."""

import argparse
import difflib
import json
import logging
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


def sort_json(
    file_path: Path,
    check_only: bool = False,  # noqa: FBT001, FBT002
    show_diff: bool = False,  # noqa: FBT001, FBT002
) -> bool:
    """Check if a JSON file is sorted or sort it.

    Args:
    ----
        file_path (Path): Path to the JSON file.
        check_only (bool): Check if the file is sorted only.

    Returns:
    -------
        bool: True if the file is sorted, False otherwise.

    """
    try:
        with Path.open(file_path) as file:
            data = json.load(file)

        # Check if on list or dict
        if isinstance(data, list):
            sorted_data = sorted(
                data,
                key=lambda x: x.casefold() if isinstance(x, str) else json.dumps(x),
            )
        elif isinstance(data, dict):
            sorted_data = {k: data[k] for k in sorted(data, key=str.casefold)}
        else:
            LOGGER.warning(
                f"⚠️ Invalid format in {file_path}: Only lists and dicts are supported."
            )
            return False

        # Write the sorted data back to the file
        if data != sorted_data:
            if check_only:
                LOGGER.error(f"❌ {file_path} is not sorted.")
                if show_diff:
                    original = json.dumps(data, indent=2).splitlines()
                    new = json.dumps(sorted_data, indent=2).splitlines()
                    diff = difflib.unified_diff(
                        original,
                        new,
                        fromfile=f"{file_path} (original)",
                        tofile=f"{file_path} (sorted)",
                        lineterm="",
                    )
                    diff_output = "\n".join(diff)
                    if diff_output.strip():
                        LOGGER.info(f"🔍 Diff for {file_path}\n{diff_output}\n")
                return False
            with Path.open(file_path, "w") as file:
                json.dump(sorted_data, file, indent=2)
                file.write("\n")  # Add newline at the end of the file
            LOGGER.info(f"🧹 {file_path} has been sorted.")
            return True
    except json.JSONDecodeError:
        LOGGER.exception(f"❌ Invalid JSON in {file_path}")
        return False
    except Exception:
        LOGGER.exception(f"❌ Could not process {file_path}")
        return False
    else:
        LOGGER.info(f"✅ {file_path} is already sorted.")
        return True


def main() -> None:
    """Fetch arguments and process JSON files."""
    parser = argparse.ArgumentParser(description="Sort JSON files.")
    parser.add_argument("files", nargs="+", help="JSON files to process")
    parser.add_argument(
        "--check", action="store_true", help="Check if files are sorted"
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Show diff when files are not sorted (only with --check)",
    )
    args = parser.parse_args()

    all_sorted = True

    for file in args.files:
        file_path = Path(file)
        if not file_path.exists():
            LOGGER.error(f"❌ File not found: {file}")
            all_sorted = False
            continue

        result = sort_json(file_path, check_only=args.check, show_diff=args.diff)
        if not result:
            all_sorted = False

    if not all_sorted:
        sys.exit(1)


if __name__ == "__main__":
    main()
