"""Determine repository changes between plugins.json files."""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from aiogithubapi import GitHubAPI, GitHubException
from dotenv import load_dotenv
from release_selection import select_used_ref

load_dotenv()

# Logging setup (GitHub Actions compatible)
logging.addLevelName(logging.INFO, "")
logging.addLevelName(logging.ERROR, "::error::")
logging.addLevelName(logging.WARNING, "::warning::")
logging.basicConfig(
    level=logging.INFO,
    format=" %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
LOGGER = logging.getLogger(__name__)


def load_repo_list(path: Path) -> set[str]:
    """Load a JSON list of repositories from file.

    Args:
    ----
        path (Path): Path to the JSON file containing a list of repositories.

    Returns:
    -------
        set[str]: A set of repository names.

    """
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            LOGGER.error(f"{path} is not a JSON list.")
            sys.exit(1)
        return set(data)
    except Exception:
        LOGGER.exception(f"Error reading '{path}'")
        sys.exit(1)


async def get_canonical_repo_name(repository: str, token: str) -> str:
    """Get the canonical repository name from GitHub API.

    GitHub URLs are case-insensitive, but we need the exact casing
    for proper categorization on the website.

    Args:
    ----
        repository (str): Repository name in format 'owner/repo'.
        token (str): GitHub token for API access.

    Returns:
    -------
        str: The canonical repository name with correct casing.

    """
    async with GitHubAPI(token) as github:
        try:
            response = await github.repos.get(repository)
            canonical_name = response.data.full_name
            if canonical_name.lower() != repository.lower():
                LOGGER.warning(
                    f"Repository name mismatch! Requested: '{repository}', "
                    f"Canonical: '{canonical_name}'"
                )
        except GitHubException:
            LOGGER.exception(f"Failed to fetch repository info for '{repository}'.")
            sys.exit(1)
        else:
            return canonical_name


def write_github_output(repository: str, action: str, ref: str = "") -> None:
    """Write outputs to GITHUB_OUTPUT for use in workflow."""
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with Path.open(github_output, "a", encoding="utf-8") as ghf:
            print(f"repository={repository}", file=ghf)
            print(f"action={action}", file=ghf)
            print(f"ref={ref}", file=ghf)


async def get_used_ref(repository: str, token: str) -> str:
    """Resolve the release ref that downstream checks should use."""
    async with GitHubAPI(token) as github:
        try:
            response = await github.repos.releases.list(repository)
        except GitHubException:
            LOGGER.exception(f"Failed to fetch releases for '{repository}'.")
            sys.exit(1)

    releases = response.data
    if not releases:
        LOGGER.error(f"No releases found for repository: {repository}")
        sys.exit(1)

    ref = select_used_ref(releases)
    LOGGER.info(f"✅ Selected release ref: {ref}")
    return ref


async def validate_repo_name(repo: str) -> None:
    """Validate repository name against GitHub canonical name.

    Args:
    ----
        repo (str): Repository name to validate.

    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        LOGGER.warning("⚠️ GITHUB_TOKEN not set, skipping canonical name validation")
        return

    canonical_repo = await get_canonical_repo_name(repo, token)
    if canonical_repo != repo:
        LOGGER.error(
            f"❌ Repository name casing mismatch!\n"
            f"   In plugins.json: '{repo}'\n"
            f"   Canonical name:  '{canonical_repo}'\n"
            f"   Please update plugins.json and categories.json to use '{canonical_repo}'"  # noqa: E501
        )
        sys.exit(1)
    LOGGER.info(f"✅ Repository name casing is correct: {canonical_repo}")


async def validate_repo_rename(old_repo: str, new_repo: str) -> bool:
    """Validate whether a removed+added pair is a legitimate repository rename."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        LOGGER.warning("⚠️ GITHUB_TOKEN not set, skipping rename validation")
        return False

    canonical_old_repo = await get_canonical_repo_name(old_repo, token)
    if canonical_old_repo != new_repo:
        return False

    LOGGER.info(f"✅ Repository renamed:\n   Old: '{old_repo}'\n   New: '{new_repo}'")
    await validate_repo_name(new_repo)
    return True


async def handle_repo_rename(old_repo: str, new_repo: str) -> bool:
    """Handle case-only updates and GitHub-confirmed repository renames."""
    if new_repo.lower() == old_repo.lower():
        LOGGER.info(
            f"✅ Repository name casing updated:\n"
            f"   Old: '{old_repo}'\n"
            f"   New: '{new_repo}'"
        )
        await validate_repo_name(new_repo)
        return True

    return await validate_repo_rename(old_repo, new_repo)


async def async_main() -> None:
    """Check for changes in plugins.json files."""
    old_path = Path("plugins_old.json")
    new_path = Path("plugins.json")

    old_repos = load_repo_list(old_path)
    new_repos = load_repo_list(new_path)

    added = list(new_repos - old_repos)
    removed = list(old_repos - new_repos)

    # Check for repository rename (case-only or GitHub-confirmed rename)
    if len(added) == 1 and len(removed) == 1:
        added_repo = added[0]
        removed_repo = removed[0]

        if await handle_repo_rename(removed_repo, added_repo):
            # Don't set any output - this is a rename, not an add/remove
            return

    if len(added) == 1 and len(removed) == 0:
        repo = added[0]
        LOGGER.info(f"✅ One repository added: {repo}")
        await validate_repo_name(repo)
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            LOGGER.error("No GitHub token provided.")
            sys.exit(1)
        ref = await get_used_ref(repo, token)
        write_github_output(repo, "add", ref)
    elif len(added) == 0 and len(removed) == 1:
        repo = removed[0]
        LOGGER.info(f"✅ One repository removed: {repo}")
        write_github_output(repo, "remove")
    elif len(added) == 0 and len(removed) == 0:
        LOGGER.info("No changes to plugins.json detected.")
    else:
        LOGGER.warning("⚠️ PR must add or remove exactly one repository.")
        LOGGER.info(f"Added repositories: {added}")
        LOGGER.info(f"Removed repositories: {removed}")
        LOGGER.info(f"Added count: {len(added)}")
        LOGGER.info(f"Removed count: {len(removed)}")
        sys.exit(1)


def main() -> None:
    """Entry point for the script."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
