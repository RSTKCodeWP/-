"""Check if a repository is in categories.json."""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from aiogithubapi import GitHubAPI, GitHubException
from dotenv import load_dotenv

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


def load_json_file(file_path: str) -> list[str] | dict[str, list[str]] | None:
    """Load a JSON file and return the parsed data."""
    try:
        with Path(file_path).open(encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        LOGGER.exception(f"Could not find '{file_path}'. Ensure it exists.")
    except json.JSONDecodeError:
        LOGGER.exception(f"Invalid JSON format in '{file_path}'")
    except Exception:
        LOGGER.exception(f"Unexpected error reading '{file_path}'")
    return None


def load_categories_repositories(categories_file: str) -> set[str] | None:
    """Load and flatten all repository names from categories.json."""
    categories_data = load_json_file(categories_file)
    if not isinstance(categories_data, dict):
        return None

    categorized_repos = set()
    for repos in categories_data.values():
        if isinstance(repos, list):
            categorized_repos.update(repos)
    return categorized_repos


def load_plugins_repositories(plugins_file: str) -> set[str] | None:
    """Load all repository names from plugins.json."""
    plugins_data = load_json_file(plugins_file)
    if not isinstance(plugins_data, list):
        return None
    return set(plugins_data)


def check_repository_in_categories(repo: str, action: str, categories_file: str) -> int:
    """Check if a repository is in categories.json.

    Args:
    ----
        repo (str): Repository name in the format 'owner/repo'.
        action (str): Action performed, either 'add' or 'remove'.
        categories_file (str): Path to the categories.json file.

    Returns:
    -------
        int: 0 if the check passes, 1 if it fails.

    """
    categorized_repos = load_categories_repositories(categories_file)
    if categorized_repos is None:
        return 1

    repo_count = int(repo in categorized_repos)

    if action == "add":
        if repo_count != 1:
            LOGGER.error(
                f"Repository '{repo}' must appear in exactly one category (found: {repo_count})"  # noqa: E501
            )
            return 1
        LOGGER.info(f"✅ '{repo}' is in exactly one category in categories.json")
    elif action == "remove":
        if repo_count != 0:
            LOGGER.error(
                f"Repository '{repo}' must NOT appear in any category (found: {repo_count})"  # noqa: E501
            )
            return 1
        LOGGER.info(f"✅ '{repo}' is not in any category in categories.json")
    else:
        LOGGER.error(f"Unknown action: '{action}' (should be 'add' or 'remove')")
        return 1
    return 0


def check_categories_plugins_sync(categories_file: str, plugins_file: str) -> int:
    """Check if all repositories in categories.json exist in plugins.json.

    Args:
    ----
        categories_file (str): Path to the categories.json file.
        plugins_file (str): Path to the plugins.json file.

    Returns:
    -------
        int: 0 if all checks pass, 1 if there are errors.

    """
    plugins_list = load_plugins_repositories(plugins_file)
    if plugins_list is None:
        return 1

    categorized_repos = load_categories_repositories(categories_file)
    if categorized_repos is None:
        return 1

    uncategorized = sorted(
        [repo for repo in plugins_list if repo not in categorized_repos]
    )
    for repo in uncategorized:
        LOGGER.error(
            f"Repository '{repo}' exists in plugins.json but is NOT assigned to any category!"  # noqa: E501
        )

    orphaned_categories = sorted(
        [repo for repo in categorized_repos if repo not in plugins_list]
    )
    for repo in orphaned_categories:
        LOGGER.error(
            f"Repository '{repo}' in categories.json does not exist in plugins.json!"
        )

    errors = len(uncategorized) + len(orphaned_categories)
    if errors == 0:
        LOGGER.info(
            "✅ All plugins are categorized, and all categories.json entries exist in plugins.json."  # noqa: E501
        )
    else:
        LOGGER.error(
            f"❌ {errors} error(s): {len(uncategorized)} plugin(s) not categorized, {len(orphaned_categories)} orphaned category entry(ies)."  # noqa: E501
        )
    return errors


async def check_canonical_repository_names(
    categories_file: str, plugins_file: str
) -> int:
    """Validate repo names against GitHub's canonical repository names."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        LOGGER.warning("⚠️ GITHUB_TOKEN not set, skipping canonical name validation")
        return 0

    plugins_list = load_plugins_repositories(plugins_file)
    if plugins_list is None:
        return 1

    categorized_repos = load_categories_repositories(categories_file)
    if categorized_repos is None:
        return 1

    errors = 0
    all_repositories = sorted(plugins_list | categorized_repos)

    async with GitHubAPI(token) as github:
        for repo in all_repositories:
            try:
                response = await github.repos.get(repo)
            except GitHubException:
                LOGGER.exception(f"Failed to fetch repository info for '{repo}'.")
                errors += 1
                continue

            canonical_repo = response.data.full_name
            if canonical_repo != repo:
                locations = []
                if repo in plugins_list:
                    locations.append("plugins.json")
                if repo in categorized_repos:
                    locations.append("categories.json")
                joined_locations = " and ".join(locations)
                LOGGER.error(
                    f"❌ Repository name mismatch detected!\n"
                    f"   In {joined_locations}: '{repo}'\n"
                    f"   Canonical name:      '{canonical_repo}'\n"
                    "   This usually means the repository was renamed or recased "
                    "on GitHub.\n"
                    f"   Please update plugins.json and categories.json to use '{canonical_repo}'"  # noqa: E501
                )
                errors += 1

    if errors == 0:
        LOGGER.info("✅ All repository names match GitHub canonical names.")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate repository category assignment in categories.json."
    )
    parser.add_argument(
        "--categories-file",
        default="categories.json",
        help="Path to categories.json file (default: categories.json)",
    )
    parser.add_argument(
        "--plugins-file",
        default="plugins.json",
        help="Path to plugins.json file (default: plugins.json)",
    )
    parser.add_argument(
        "--action",
        choices=["add", "remove"],
        help="Action performed: add or remove (optional)",
    )

    args = parser.parse_args()
    error_count = 0

    if args.action:
        repo = os.environ.get("REPOSITORY")
        if not repo:
            LOGGER.error("'REPOSITORY' environment variable is not set.")
            sys.exit(1)
        repo = repo.strip()
        error_count += check_repository_in_categories(
            repo, args.action, args.categories_file
        )

    error_count += check_categories_plugins_sync(
        args.categories_file, args.plugins_file
    )
    error_count += asyncio.run(
        check_canonical_repository_names(args.categories_file, args.plugins_file)
    )
    sys.exit(1 if error_count else 0)
