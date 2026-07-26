"""Shared release selection helpers."""

from typing import Any


def select_used_ref(releases: list[Any]) -> str:
    """Select the latest stable release, or the latest prerelease as fallback."""
    sorted_releases = sorted(
        releases, key=lambda release: release.created_at, reverse=True
    )
    latest_stable = next(
        (release for release in sorted_releases if not release.prerelease), None
    )
    selected_release = latest_stable or sorted_releases[0]
    return selected_release.tag_name
