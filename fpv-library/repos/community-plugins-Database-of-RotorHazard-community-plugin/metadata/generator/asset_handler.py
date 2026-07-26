"""Asset handling functionality for GitHub release assets."""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aiogithubapi import GitHubAPI

    from .log_buffer import PluginLogBuffer


async def get_release_asset_info(
    github: "GitHubAPI",
    release: Any,
    asset_name: str,
    logger: "PluginLogBuffer",
) -> dict[str, Any] | None:
    """Return comprehensive info for the release asset matching asset_name.

    Args:
    ----
        github: GitHubAPI instance
        release: Release object containing assets
        asset_name: Name of the asset to find
        logger: PluginLogBuffer instance for logging

    Returns:
    -------
        dict[str, Any] | None: Asset information dictionary or None if not found

    """
    asset = next(
        (
            asset
            for asset in getattr(release, "assets", [])
            if getattr(asset, "name", None) == asset_name
        ),
        None,
    )
    if not asset:
        logger.log(
            logging.WARNING,
            f"ℹ️  Asset '{asset_name}' not found in release {release.tag_name}",  # noqa: RUF001
        )
        return None

    # Build asset info dictionary
    asset_info: dict[str, Any] = {"name": asset_name}

    # Add size if available
    size = getattr(asset, "size", None)
    if size is not None:
        asset_info["size"] = size

    # Add download count if available
    download_count = getattr(asset, "download_count", None)
    if download_count is not None:
        asset_info["download_count"] = download_count

    # GitHub API returns digest in format "sha256:HASH"
    digest = getattr(asset, "digest", None)
    if digest is None:
        for attr in ("data", "_raw_data"):
            payload: Any = getattr(asset, attr, None)
            if isinstance(payload, dict):
                digest = payload.get("digest")
                if digest:
                    break
    if digest:
        # Strip the "sha256:" prefix if present
        asset_info["sha256"] = digest.removeprefix("sha256:")

    return asset_info
