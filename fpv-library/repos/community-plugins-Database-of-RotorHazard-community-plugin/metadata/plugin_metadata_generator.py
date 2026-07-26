"""Generate metadata for each RotorHazard community plugin."""

import base64
import json
import logging
from datetime import UTC, datetime
from typing import Any

from aiogithubapi import (
    GitHubAPI,
    GitHubException,
    GitHubNotFoundException,
    GitHubRatelimitException,
)
from const import EXCLUDED_KEYS
from generator import (
    PluginLogBuffer,
    get_release_asset_info,
    validate_manifest_domain,
    validate_manifest_version,
)


class PluginMetadataGenerator:
    """Generate metadata for each RotorHazard community plugin."""

    def __init__(self, repo: str) -> None:
        """Initialize the plugin metadata generator."""
        self.repo = repo  # Full repository name (e.g., "owner/repo_name")
        self.original_repo = repo  # Store the original repository name
        self.domain = None  # Plugin domain folder
        self.metadata = {}
        self.manifest_data = {}
        self.repo_metadata = {}
        self.etag_repository = None
        self.etag_release = None
        self.releases = []
        self.logger = PluginLogBuffer(repo)

    def log(self, message: str, level: int = logging.INFO) -> None:
        """Log a message with the specified level, buffering it for later."""
        self.logger.log(level, message)

    @property
    def latest_stable(self) -> str | None:
        """Return the latest stable release."""
        return next((r.tag_name for r in self.releases if not r.prerelease), None)

    @property
    def latest_prerelease(self) -> str | None:
        """Return the latest pre-release."""
        return next((r.tag_name for r in self.releases if r.prerelease), None)

    @property
    def used_ref(self) -> str:
        """Return the branch/tag name used for fetching metadata.

        Prefer the latest stable release; only fall back to a prerelease if no
        stable release exists.
        """
        return (
            self.latest_stable
            or self.latest_prerelease
            or self.repo_metadata.default_branch
        )

    async def fetch_repository_info(self, github: GitHubAPI) -> bool:
        """Fetch and store repository metadata from GitHub.

        Args:
        ----
            github: GitHubAPI instance.

        Returns:
        -------
            bool: True if the repository data is fetched successfully, False otherwise.

        """
        self.log("🔎 Fetching repository metadata...")
        try:
            repo_response = await github.repos.get(self.repo)
            self.repo = repo_response.data.full_name
            self.repo_metadata = repo_response.data
        except GitHubRatelimitException:
            self.log(
                "GitHub API rate limit exceeded. Please retry later.", logging.ERROR
            )
            return False
        except GitHubNotFoundException:
            self.log("Repository not found on GitHub.", logging.ERROR)
            return False
        except GitHubException:
            self.log("Failed to retrieve repository information.", logging.ERROR)
            return False
        self.etag_repository = repo_response.etag
        return True

    async def fetch_github_releases(self, github: GitHubAPI) -> bool:
        """Fetch the latest stable and prerelease versions from GitHub.

        Args:
        ----
            github: GitHubAPI instance.

        Returns:
        -------
            bool: True if the releases are fetched successfully, False otherwise.

        """
        self.log("🔎 Fetching GitHub releases...")
        try:
            releases = await github.repos.releases.list(self.repo)
            if releases.etag:
                self.etag_release = releases.etag
            if not releases.data:
                self.log("No releases found.", logging.WARNING)
                return False

            # Ensure releases are sorted by creation date (newest first)
            self.releases = sorted(
                releases.data, key=lambda r: r.created_at, reverse=True
            )
        except GitHubException:
            self.log("Error occurred while fetching releases.", logging.ERROR)
            return False

        # Log the latest stable and prerelease versions
        message = f"ℹ️  Latest stable release: {self.latest_stable}"  # noqa: RUF001
        if self.latest_prerelease:
            message += f", Latest pre-release: {self.latest_prerelease}"
        self.log(message)
        return True

    async def fetch_manifest_file(self, github: GitHubAPI) -> bool:
        """Fetch the manifest file from the repository.

        Args:
        ----
            github: GitHubAPI instance.

        Returns:
        -------
            bool: True if the manifest file is fetched successfully, False otherwise.

        """
        manifest_path = f"custom_plugins/{self.domain}/manifest.json"
        self.log(f"🔎 Fetching plugin domain folder (branch: {self.used_ref})")
        try:
            response = await github.repos.contents.get(
                self.repo, f"{manifest_path}?ref={self.used_ref}"
            )
            content = base64.b64decode(response.data.content).decode("utf-8")
            self.manifest_data = json.loads(content)
            self.log(f"✅ Successfully fetched manifest.json (branch: {self.used_ref})")
        except (GitHubNotFoundException, json.JSONDecodeError, GitHubException):
            self.log(
                f"Failed to fetch `{manifest_path}` from {self.used_ref}.",
                logging.ERROR,
            )
            return False
        return True

    async def validate_plugin_repository(self, github: GitHubAPI) -> bool:
        """Fetch the plugin domain folder and validate the repository structure.

        Args:
        ----
            github: GitHubAPI instance.

        Returns:
        -------
            bool: True if the plugin domain is fetched successfully, False otherwise.

        """
        try:
            self.log(f"🔎 Fetching plugin domain folder (branch: {self.used_ref})")
            response = await github.repos.contents.get(
                self.repo, f"?ref={self.used_ref}"
            )

            # Check for `custom_plugins/` folder
            custom_plugins_folder = next(
                (
                    item
                    for item in response.data
                    if item.name == "custom_plugins" and item.type == "dir"
                ),
                None,
            )
            if not custom_plugins_folder:
                self.log("Missing `custom_plugins/` folder.", logging.ERROR)
                return False

            # Fetch the contens of the `custom_plugins/` folder
            folder_response = await github.repos.contents.get(
                self.repo, f"custom_plugins?ref={self.used_ref}"
            )
            subfolders = [item for item in folder_response.data if item.type == "dir"]

            # Ensure there is exactly one domain folder
            if len(subfolders) != 1:
                self.log(
                    "Expected one domain folder in "
                    f"`custom_plugins/`, found: {len(subfolders)}.",
                    logging.ERROR,
                )
                return False

            self.domain = subfolders[0].name
        except GitHubNotFoundException:
            self.log("Repository not found.", logging.WARNING)
            return False
        except GitHubException:
            self.log("Error fetching plugin domain.", logging.ERROR)
            return False
        self.log(f"ℹ️  Plugin domain folder: `{self.domain}` (branch: {self.used_ref})")  # noqa: RUF001
        return True

    async def fetch_metadata(self, github: GitHubAPI) -> dict | None:  # noqa: PLR0911
        """Fetch and update the plugin's metadata.

        Args:
        ----
            github: GitHubAPI instance.

        Returns:
        -------
            dict | None: The plugin's metadata if successful,
                if None plugin will be skipped.

        """
        try:
            repo_fetched = await self.fetch_repository_info(github)
            if not repo_fetched:
                self.log("Skipping due to missing repository data.", logging.ERROR)
                return None

            # Check if the repository is archived
            if self.repo_metadata.archived:
                self.log(
                    "Repository is archived. Skipping metadata generation.",
                    logging.WARNING,
                )
                return {self.repo: {"archived": True}}

            # Check if the repository has been renamed
            full_name = self.repo_metadata.full_name
            if full_name != self.original_repo:
                self.log(
                    f"Repository renamed from '{self.original_repo}' to '{full_name}'",
                    logging.WARNING,
                )

            # Fetch plugin domain and validate repository structure
            if not await self.fetch_github_releases(github):
                return None
            # Fetch plugin domain and validate repository structure
            if not await self.validate_plugin_repository(github):
                return None
            # Fetch manifest file and validate domain
            if not await self.fetch_manifest_file(github):
                return None
            # Validate domain and manifest version
            if not validate_manifest_domain(
                self.domain, self.manifest_data, self.logger
            ):
                return None
            # Validate manifest version against github releases
            if not validate_manifest_version(
                self.manifest_data, self.used_ref, self.logger
            ):
                return None

            self.metadata = {
                "etag_release": self.etag_release,
                "etag_repository": self.etag_repository,
                "last_fetched": datetime.now(UTC).isoformat(),
                "last_updated": self.repo_metadata.updated_at,
                "last_version": self.latest_stable,
                "open_issues": self.repo_metadata.open_issues_count,
                "repository": self.repo,
                "stargazers_count": self.repo_metadata.stargazers_count,
                "watchers_count": self.repo_metadata.watchers_count,
                "forks_count": self.repo_metadata.forks_count,
                "topics": self.repo_metadata.topics,
                "used_ref": self.used_ref,
            }

            # Add releases metadata
            self.metadata = {
                "releases": await self._build_releases_metadata(github),
                **self.metadata,
            }

            # Add prerelease version if available
            if self.latest_prerelease:
                self.metadata["last_prerelease"] = self.latest_prerelease
            self.metadata = dict(sorted(self.metadata.items()))

            # Add manifest-specific metadata
            self.metadata = {
                "manifest": {
                    **{
                        key: value
                        for key, value in self.manifest_data.items()
                        if key not in EXCLUDED_KEYS
                    },
                },
                **self.metadata,
            }
        except GitHubException:
            self.log("An error occurred during metadata generation.", logging.ERROR)
            return None

        self.log("🎉 Metadata successfully generated.")
        return {self.repo_metadata.id: self.metadata}

    async def _build_releases_metadata(self, github: GitHubAPI) -> list[dict[str, Any]]:
        """Build metadata for the latest releases, including asset digests."""
        releases_metadata: list[dict[str, Any]] = []
        zip_filename = self.manifest_data.get("zip_filename")
        for release in self.releases[:5]:
            release_entry: dict[str, Any] = {
                "tag_name": release.tag_name,
                "published_at": release.published_at,
                "prerelease": release.prerelease,
            }

            assets: list[dict[str, Any]] = []
            seen_assets: set[str] = set()

            for asset in getattr(release, "assets", []):
                asset_name = getattr(asset, "name", None)
                if not asset_name or asset_name in seen_assets:
                    continue

                seen_assets.add(asset_name)
                asset_info = await get_release_asset_info(
                    github, release, asset_name, self.logger
                )
                if asset_info:
                    assets.append(asset_info)

            if assets:
                release_entry["assets"] = assets

            if (
                zip_filename
                and zip_filename not in seen_assets
                and release.tag_name == self.used_ref
            ):
                self.log(
                    "Manifest `zip_filename` "
                    f"'{zip_filename}' was not found in release "
                    f"{release.tag_name}.",
                    logging.WARNING,
                )

            releases_metadata.append(release_entry)

        return releases_metadata
