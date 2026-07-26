"""Validation functions for plugin metadata."""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .log_buffer import PluginLogBuffer


def validate_manifest_domain(
    domain: str,
    manifest_data: dict[str, Any],
    logger: "PluginLogBuffer",
) -> bool:
    """Validate that the domain in `manifest.json` matches the folder name.

    Args:
    ----
        domain: The plugin domain folder name
        manifest_data: The manifest.json data
        logger: PluginLogBuffer instance for logging

    Returns:
    -------
        bool: True if the domain matches the folder name, False otherwise.

    """
    # Check if the domain in manifest.json matches the folder name
    manifest_domain: str = manifest_data.get("domain")
    if manifest_domain != domain:
        logger.log(
            logging.ERROR,
            f"Domain mismatch: Folder '{domain}' vs Manifest '{manifest_domain}'",
        )
        return False
    # Manifest domain matches the folder name
    logger.log(
        logging.INFO,
        f"✅ Manifest domain validated: '{manifest_domain}' matches domain folder",
    )
    return True


def validate_manifest_version(
    manifest_data: dict[str, Any],
    used_ref: str,
    logger: "PluginLogBuffer",
) -> bool:
    """Validate if version in manifest.json matches the latest stable or prerelease.

    Args:
    ----
        manifest_data: The manifest.json data
        used_ref: The branch/tag name used for fetching metadata
        logger: PluginLogBuffer instance for logging

    Returns:
    -------
        bool: `True` if the version is valid, `False` if there is a mismatch.

    """

    def normalize_version(version: str | None) -> str | None:
        return version.lstrip("v") if version else None

    manifest_version = manifest_data.get("version")
    latest_version = normalize_version(used_ref)

    if manifest_version == latest_version:
        logger.log(
            logging.INFO,
            f"✅ Manifest version validated: '{manifest_version}' "
            f"matches release '{latest_version}'",
        )
        return True

    # Mismatch - version is outdated
    logger.log(
        logging.WARNING,
        f"Manifest version mismatch: '{manifest_version}' "
        f"(manifest) vs '{latest_version}' (release)",
    )
    return False
