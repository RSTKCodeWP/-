"""Core module for the rhfest package."""

import os
from pathlib import Path

from checks.manifest import ManifestCheck
from checks.structure import StructureCheck
from const import LOGGER, RHFEST_VERSION
from report import Report


def detect_base_path() -> Path:
    """Automatically detect the correct base path."""
    if os.getenv("GITHUB_WORKSPACE"):
        return Path(os.getenv("GITHUB_WORKSPACE")).resolve()

    # Detect if running inside Docker
    if Path("/.dockerenv").exists():
        return Path("/repo").resolve()

    # Fallback: Running locally, use current working directory
    return Path.cwd().resolve()


def run_rhfest(base_path: str) -> None:
    """Run validation for the manifest.json file.

    Args:
    ----
        base_path: The base path of the repository.

    """
    LOGGER.info(f"🛠️  RHFest version: {RHFEST_VERSION}")
    base_path = Path(base_path).resolve()
    report = Report()

    LOGGER.info("========== Structure Report ==========")
    LOGGER.info("🚦 Start structure validation")
    structure_check = StructureCheck(base_path, report)
    structure_result = structure_check.run()
    report.add(structure_result)
    # Check if the structure check failed
    if structure_result["status"] == "fail":
        report.generate()  # Triggers sys.exit(1)

    LOGGER.info("========== Manifest Report ==========")
    LOGGER.info("🚦 Start manifest.json validation")
    manifest_result = ManifestCheck(structure_check.manifest_path).run()
    report.add(manifest_result)
    report.generate()


if __name__ == "__main__":
    run_rhfest(detect_base_path())
