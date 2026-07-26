"""Report module for the RH plugin validation action."""

import sys
from pathlib import Path

from const import LOGGER

IGNORED_FOLDERS = {".ruff_cache", ".venv", "__pycache__", ".git", ".github"}


class Report:
    """Validation report class."""

    def __init__(self) -> None:
        """Initialize the report."""
        self.results = []

    def add(self, result: dict[str, str]) -> None:
        """Add a result to the report.

        Args:
        ----
            result (dict): The result to add to the report.

        """
        self.results.append(result)

    def generate(self) -> None:
        """Generate the validation report."""
        passed = [r for r in self.results if r["status"] == "pass"]
        failed = [r for r in self.results if r["status"] == "fail"]

        LOGGER.info("========== Summary ==========")
        LOGGER.info(f"✅ Passed: {len(passed)}")
        LOGGER.info(f"❌ Failed: {len(failed)}")

        # Exit with a non-zero status code if there are failed checks.
        if len(failed) > 0:
            sys.exit(1)
        else:
            sys.exit(0)

    def list_files_in_tree(self, directory: Path, prefix: str = "") -> None:
        """Recursively list files and directories in a tree structure.

        Args:
        ----
            directory: The directory to list files and directories from.
            prefix: The prefix to use for each line in the tree.

        """
        entries = list(directory.iterdir())
        entries.sort()

        for index, entry in enumerate(entries):
            if entry.is_dir() and entry.name in IGNORED_FOLDERS:
                continue

            connector = "└──" if index == len(entries) - 1 else "├──"
            if entry.is_dir():
                LOGGER.info(f"{prefix}{connector} 📁 {entry.name}")
                self.list_files_in_tree(
                    entry, prefix + ("    " if index == len(entries) - 1 else "│   ")
                )
            else:
                LOGGER.info(f"{prefix}{connector} 📄 {entry.name}")
