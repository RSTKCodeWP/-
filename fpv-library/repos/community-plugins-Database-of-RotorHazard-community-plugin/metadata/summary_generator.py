"""Generates a summary of the plugin metadata."""

import asyncio
import json
from pathlib import Path
from time import perf_counter

from aiogithubapi import GitHubAPI
from const import LOGGER
from plugin_metadata_generator import PluginMetadataGenerator

COMPARE_IGNORE = ["last_fetched", "etag_release", "etag_repository"]


class SummaryData:
    """Summary data for metadata generation."""

    def __init__(
        self, total: int, valid: int, archived: int, renamed: int, skipped: int
    ) -> None:
        """Initialize the summary data."""
        self.total = total
        self.valid = valid
        self.archived = archived
        self.renamed = renamed
        self.skipped = skipped


class SummaryGenerator:
    """Handles generating and saving metadata for all repositories."""

    def __init__(self, plugin_file: str, output_dir: str) -> None:
        """Initialize the metadata generator."""
        self.plugin_file = Path(plugin_file)
        self.output_dir = output_dir
        self.repos_list = self.load_repos()

    def load_repos(self) -> list[str]:
        """Load repository list from the plugin file.

        Returns
        -------
            list[str]: List of repositories.

        """
        if self.plugin_file.exists():
            with Path.open(self.plugin_file, encoding="utf-8") as f:
                return json.load(f)
        else:
            LOGGER.warning("Plugin list file not found. Using an empty list.")
            return []

    def save_filtered_json(self, filepath: str, data: dict) -> None:
        """Save data to a JSON file with filtered keys.

        Args:
        ----
            filepath: Path to the output JSON file.
            data: Data to be saved.

        """
        filtered_data = {
            key: {k: v for k, v in value.items() if k not in COMPARE_IGNORE}
            for key, value in data.items()
        }
        with Path.open(filepath, "w", encoding="utf-8") as f:
            json.dump(filtered_data, f, indent=2)

    def save_json(self, filepath: str, data: dict) -> None:
        """Save data to a JSON file.

        Args:
        ----
            filepath: Path to the output JSON file.
            data: Data to be saved.

        """
        with Path.open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    async def summarize_results(
        self,
        summary_data: SummaryData,
        start_time: float,
    ) -> None:
        """Summarize the generation results.

        Args:
        ----
            total: Total number of repositories.
            summary_data: An instance of SummaryData containing summary data.
            start_time: Time when the generation started.

        """
        end_time = perf_counter()
        elapsed_time = end_time - start_time
        summary = {
            "total_plugins": summary_data.total,
            "valid_plugins": summary_data.valid,
            "archived_plugins": summary_data.archived,
            "renamed_plugins": summary_data.renamed,
            "skipped_plugins": summary_data.skipped,
            "execution_time_seconds": round(elapsed_time, 2),
        }
        summary_path = f"{self.output_dir}/summary.json"
        self.save_json(summary_path, summary)

    async def generate(self, github_token: str) -> None:
        """Generate metadata for all repositories."""
        plugin_data: dict[str, dict] = {}
        valid_repositories: list[str] = []
        skipped_plugins = 0
        archived_plugins = 0
        renamed_plugins = 0

        start_time = perf_counter()

        async with GitHubAPI(token=github_token) as github:
            generators = [PluginMetadataGenerator(repo) for repo in self.repos_list]
            tasks = [g.fetch_metadata(github) for g in generators]
            results = await asyncio.gather(*tasks)

            for generator, result in zip(generators, results, strict=False):
                # Flush plugin logs (grouped)
                generator.logger.flush()

                # Check if the repository has been renamed
                # This works even if the plugin is skipped
                if generator.repo != generator.original_repo:
                    renamed_plugins += 1

                if not result:
                    skipped_plugins += 1
                    continue

                repo_id, metadata = next(iter(result.items()))
                if metadata.get("archived"):
                    archived_plugins += 1
                    continue

                plugin_data[repo_id] = metadata
                valid_repositories.append(metadata.get("repository"))

        # Save generated metadata to local JSON files
        self.save_filtered_json(f"{self.output_dir}/diff/after.json", plugin_data)
        self.save_json(f"{self.output_dir}/data.json", plugin_data)
        self.save_json(f"{self.output_dir}/repositories.json", valid_repositories)

        # Generate and save summary data
        summary_data = SummaryData(
            total=len(self.repos_list),
            valid=len(valid_repositories),
            archived=archived_plugins,
            renamed=renamed_plugins,
            skipped=skipped_plugins,
        )
        await self.summarize_results(summary_data, start_time)
