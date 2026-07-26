"""Tests for the Generate Metadata script."""

import asyncio
import base64
import json
import runpy
import sys
import types
from datetime import UTC, datetime
from pathlib import Path
from typing import Self
from unittest.mock import AsyncMock

import pytest
from aiogithubapi import GitHubException, GitHubNotFoundException
from metadata import (
    PluginMetadataGenerator,
    validate_manifest_domain,
    validate_manifest_version,
)
from metadata.summary_generator import SummaryGenerator
from syrupy.assertion import SnapshotAssertion

from tests.conftest import MockRelease, MockReleaseAsset

from . import load_fixture
from .conftest import MockGitHubResponse, MockRepo

TEST_GITHUB_TOKEN = "token-123"  # noqa: S105


@pytest.mark.freeze_time("2025-03-09 15:00:00+01:00")
async def test_rotorhazard_plugin_success(
    mock_github: AsyncMock, snapshot: SnapshotAssertion
) -> None:
    """Test the PluginMetadataGenerator class with a successful repository."""
    plugin = PluginMetadataGenerator("owner/repo")
    metadata = await plugin.fetch_metadata(mock_github)

    # Check if the metadata is not empty
    assert metadata is not None
    repo_id, data = next(iter(metadata.items()))

    assert "manifest" in data
    assert repo_id == 1
    assert data["manifest"]["name"] == "Test Plugin"
    assert data["manifest"]["domain"] == "testdomain"

    snapshot.assert_match(data)


async def test_rotor_hazard_plugin_archived(
    mock_github: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the PluginMetadataGenerator class with an archived repository."""

    # Patch the GitHubAPI class to return the mock_github instance
    async def archived_get(repo_name: str) -> MockGitHubResponse:
        repo = MockRepo(
            full_name=repo_name,
            archived=True,
            updated_at=datetime.now(UTC).isoformat(),
            open_issues_count=5,
            stargazers_count=100,
            topics=["python", "plugin"],
            id=1,
        )
        return MockGitHubResponse(data=repo, etag="mock_repo_etag")

    monkeypatch.setattr(mock_github.repos, "get", archived_get)
    plugin = PluginMetadataGenerator("owner/repo_archived")
    metadata = await plugin.fetch_metadata(mock_github)
    assert metadata is not None
    repo_name, data = next(iter(metadata.items()))

    # Expect the plugin to be archived
    assert repo_name == "owner/repo_archived"
    assert data.get("archived") is True


async def test_manifest_domain_mismatch(
    mock_github: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test the PluginMetadataGenerator class with a mismatched manifest domain."""
    original_get = mock_github.repos.contents.get

    async def wrong_manifest_get(
        repo_name: str,
        path: str = "custom_plugins",
    ) -> MockGitHubResponse:
        if not path:
            path = "custom_plugins"
        if path.split("?", 1)[0] == "custom_plugins/testdomain/manifest.json":
            content = base64.b64encode(
                json.dumps(load_fixture("wrong_domain_manifest.json")).encode("utf-8")
            ).decode("utf-8")
            file_data = type("Data", (), {"content": content})
            return MockGitHubResponse(data=file_data, etag="mock_manifest_etag")
        return await original_get(repo_name, path)

    monkeypatch.setattr(mock_github.repos.contents, "get", wrong_manifest_get)
    plugin = PluginMetadataGenerator("owner/repo")
    await plugin.fetch_repository_info(mock_github)
    await plugin.fetch_github_releases(mock_github)
    await plugin.validate_plugin_repository(mock_github)
    manifest_fetched = await plugin.fetch_manifest_file(mock_github)
    assert manifest_fetched is True
    valid_domain = validate_manifest_domain(
        plugin.domain, plugin.manifest_data, plugin.logger
    )
    assert valid_domain is False
    monkeypatch.setattr(mock_github.repos.contents, "get", original_get)


async def test_manifest_version_mismatch(
    mock_github: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the PluginMetadataGenerator class with a mismatched manifest version."""
    original_get = mock_github.repos.contents.get

    async def wrong_version_get(
        repo_name: str,
        path: str = "custom_plugins",
    ) -> MockGitHubResponse:
        if not path:
            path = "custom_plugins"
        if path.split("?", 1)[0] == "custom_plugins/testdomain/manifest.json":
            content = base64.b64encode(
                json.dumps(load_fixture("wrong_version_manifest.json")).encode("utf-8")
            ).decode("utf-8")
            file_data = type("Data", (), {"content": content})
            return MockGitHubResponse(data=file_data, etag="mock_manifest_etag")
        return await original_get(repo_name, path)

    monkeypatch.setattr(mock_github.repos.contents, "get", wrong_version_get)
    plugin = PluginMetadataGenerator("owner/repo")
    await plugin.fetch_repository_info(mock_github)
    await plugin.fetch_github_releases(mock_github)
    await plugin.validate_plugin_repository(mock_github)
    await plugin.fetch_manifest_file(mock_github)
    valid_version = validate_manifest_version(
        plugin.manifest_data, plugin.used_ref, plugin.logger
    )
    assert valid_version is False
    monkeypatch.setattr(mock_github.repos.contents, "get", original_get)


async def test_metadata_generator(
    tmp_path: Path,
    plugins_file: Path,
    mock_github: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the MetadataGenerator class."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    # Create a diff directory to store the diff files
    (output_dir / "diff").mkdir(parents=True, exist_ok=True)

    # Patch the GitHubAPI class to return the mock_github instance
    monkeypatch.setattr("aiogithubapi.GitHubAPI", AsyncMock(return_value=mock_github))
    fake_perf_calls = iter([100.0, 101.23])
    monkeypatch.setattr(
        "metadata.summary_generator.perf_counter", lambda: next(fake_perf_calls)
    )
    summary = SummaryGenerator(str(plugins_file), str(output_dir))
    await summary.generate("test_token")

    # Check if the output files are created
    data_file = output_dir / "data.json"
    repos_file = output_dir / "repositories.json"
    summary_file = output_dir / "summary.json"
    assert data_file.exists()
    assert repos_file.exists()
    assert summary_file.exists()

    data = json.loads(data_file.read_text())
    repos = json.loads(repos_file.read_text())
    summary = json.loads(summary_file.read_text())

    assert isinstance(data, dict)
    assert isinstance(repos, list)
    assert "total_plugins" in summary

    assert summary.get("execution_time_seconds") == round(1.23, 2)
    snapshot.assert_match(summary)


async def test_asset_info_with_size_and_download_count(
    mock_github: AsyncMock,
) -> None:
    """Test that asset info includes size and download_count."""
    plugin = PluginMetadataGenerator("owner/repo")
    metadata = await plugin.fetch_metadata(mock_github)

    assert metadata is not None
    _repo_id, data = next(iter(metadata.items()))

    # Check the first release has asset info
    first_release = data["releases"][0]
    assert "assets" in first_release
    assets = first_release["assets"]
    assert len(assets) == 2
    asset = assets[0]

    # Verify all expected fields are present
    assert "name" in asset
    assert "sha256" in asset
    assert "size" in asset
    assert "download_count" in asset

    # Verify the values match our test data
    assert asset["name"] == "plugin.zip"
    assert asset["size"] == 12345
    assert asset["download_count"] == 42
    # Verify additional assets are preserved
    second_asset = assets[1]
    assert second_asset["name"] == "plugin-debug.zip"
    assert second_asset["size"] == 15000


async def test_digest_prefix_stripping(
    mock_github: AsyncMock,
) -> None:
    """Test that the 'sha256:' prefix is stripped from digest field."""
    plugin = PluginMetadataGenerator("owner/repo")
    metadata = await plugin.fetch_metadata(mock_github)

    assert metadata is not None
    _repo_id, data = next(iter(metadata.items()))

    # Check the first release asset
    first_release = data["releases"][0]
    assets = first_release["assets"]

    # The digest should not have the 'sha256:' prefix
    for asset in assets:
        assert "sha256" in asset
        sha256_hash = asset["sha256"]
        assert not sha256_hash.startswith("sha256:")
        # Verify it's a valid hex string (64 chars for SHA256)
        assert len(sha256_hash) == 64
        assert all(c in "0123456789abcdef" for c in sha256_hash)


async def test_asset_without_digest_fallback(
    mock_github: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test fallback behavior when digest is not available (older releases)."""

    async def list_releases_without_digest(repo_name: str) -> MockGitHubResponse:
        """Return releases without digest field."""
        release = MockRelease(
            tag_name="v0.9.0",
            prerelease=False,
            created_at=datetime(2013, 1, 1, tzinfo=UTC),
            published_at=datetime(2013, 1, 1, tzinfo=UTC),
            assets=[
                MockReleaseAsset(
                    name="plugin.zip",
                    browser_download_url="https://example.com/old/plugin.zip",
                    digest=None,  # No digest available
                    size=10000,
                    download_count=100,
                )
            ],
        )
        return MockGitHubResponse(data=[release], etag="mock_etag")

    monkeypatch.setattr(
        mock_github.repos.releases,
        "list",
        AsyncMock(side_effect=list_releases_without_digest),
    )

    plugin = PluginMetadataGenerator("owner/repo")
    await plugin.fetch_repository_info(mock_github)
    await plugin.fetch_github_releases(mock_github)

    # The asset should still have size and download_count
    # but might not have sha256 (depends on whether fallback download succeeds)
    first_release = plugin.releases[0]
    assert first_release.tag_name == "v0.9.0"
    assert len(first_release.assets) == 1
    asset = first_release.assets[0]
    assert asset.digest is None
    assert asset.size == 10000
    assert asset.download_count == 100


async def test_renamed_repository(
    mock_github: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test handling of renamed repositories."""
    _original_get = mock_github.repos.get

    async def renamed_get(repo_name: str) -> MockGitHubResponse:
        # Return a different full_name to simulate rename
        repo = MockRepo(
            full_name="owner/new_repo_name",  # Different from original
            archived=False,
            updated_at=datetime.now(UTC).isoformat(),
            open_issues_count=5,
            stargazers_count=100,
            topics=["python", "plugin"],
            id=1,
        )
        return MockGitHubResponse(data=repo, etag="mock_repo_etag")

    monkeypatch.setattr(mock_github.repos, "get", renamed_get)

    plugin = PluginMetadataGenerator("owner/old_repo_name")
    await plugin.fetch_repository_info(mock_github)

    # Verify the repo name was updated
    assert plugin.original_repo == "owner/old_repo_name"
    assert plugin.repo != plugin.original_repo
    assert plugin.repo == "owner/new_repo_name"


async def test_summary_generator_missing_plugin_file(
    tmp_path: Path,
    mock_github: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test SummaryGenerator when plugin list file doesn't exist."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "diff").mkdir(parents=True, exist_ok=True)

    # Use a non-existent plugin file
    non_existent_file = tmp_path / "non_existent.json"

    monkeypatch.setattr("aiogithubapi.GitHubAPI", AsyncMock(return_value=mock_github))
    fake_perf_calls = iter([100.0, 100.5])
    monkeypatch.setattr(
        "metadata.summary_generator.perf_counter", lambda: next(fake_perf_calls)
    )

    summary = SummaryGenerator(str(non_existent_file), str(output_dir))
    await summary.generate("test_token")

    # Should still generate files with empty data
    data_file = output_dir / "data.json"
    assert data_file.exists()
    data = json.loads(data_file.read_text())
    assert isinstance(data, dict)
    assert len(data) == 0  # Empty since no plugins were loaded


async def test_fetch_github_releases_no_releases(
    mock_github: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Return False when no releases are found."""
    monkeypatch.setattr(
        mock_github.repos.releases,
        "list",
        AsyncMock(return_value=MockGitHubResponse(data=[], etag=None)),
    )
    plugin = PluginMetadataGenerator("owner/repo")
    result = await plugin.fetch_github_releases(mock_github)
    assert result is False


async def test_validate_plugin_repository_missing_custom_folder(
    mock_github: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing custom_plugins folder should return False."""
    plugin = PluginMetadataGenerator("owner/repo")
    await plugin.fetch_repository_info(mock_github)

    async def no_custom_folder(_repo: str, _path: str = "") -> MockGitHubResponse:
        return MockGitHubResponse(data=[])

    monkeypatch.setattr(mock_github.repos.contents, "get", no_custom_folder)
    result = await plugin.validate_plugin_repository(mock_github)
    assert result is False


async def test_validate_plugin_repository_not_found(
    mock_github: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GitHubNotFoundException should return False."""
    plugin = PluginMetadataGenerator("owner/repo")
    await plugin.fetch_repository_info(mock_github)

    async def raise_not_found(_repo: str, _path: str = "") -> MockGitHubResponse:
        raise GitHubNotFoundException

    monkeypatch.setattr(mock_github.repos.contents, "get", raise_not_found)
    result = await plugin.validate_plugin_repository(mock_github)
    assert result is False


async def test_fetch_metadata_with_renamed_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Renamed repository path should still build metadata."""
    plugin = PluginMetadataGenerator("owner/original")

    async def fake_fetch_repository_info(_github: AsyncMock) -> bool:
        plugin.repo_metadata = MockRepo(
            full_name="owner/renamed",
            archived=False,
            default_branch="main",
            updated_at=datetime.now(UTC).isoformat(),
            open_issues_count=1,
            stargazers_count=2,
            watchers_count=3,
            forks_count=4,
            topics=["x"],
            id=99,
        )
        plugin.repo = plugin.repo_metadata.full_name
        return True

    monkeypatch.setattr(plugin, "fetch_repository_info", fake_fetch_repository_info)
    monkeypatch.setattr(plugin, "fetch_github_releases", AsyncMock(return_value=True))
    monkeypatch.setattr(
        plugin, "validate_plugin_repository", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(plugin, "fetch_manifest_file", AsyncMock(return_value=True))
    monkeypatch.setattr(
        plugin,
        "_build_releases_metadata",
        AsyncMock(return_value=[]),
    )
    plugin.manifest_data = {"name": "X", "domain": "d", "version": "1.0.0"}
    monkeypatch.setattr(
        "metadata.plugin_metadata_generator.validate_manifest_domain",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        "metadata.plugin_metadata_generator.validate_manifest_version",
        lambda *_args, **_kwargs: True,
    )

    metadata = await plugin.fetch_metadata(AsyncMock())
    assert metadata is not None
    repo_id, data = next(iter(metadata.items()))
    assert repo_id == 99
    assert data["repository"] == "owner/renamed"
    assert data["manifest"]["name"] == "X"


async def test_summary_generator_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure summary counts renamed/archived/skipped/valid plugins."""
    plugin_file = tmp_path / "plugins.json"
    plugin_file.write_text(json.dumps(["skip", "archived", "ok"]))
    output_dir = tmp_path / "output"
    (output_dir / "diff").mkdir(parents=True, exist_ok=True)

    class FakeLogger:
        def flush(self) -> None:
            pass

    class FakeGenerator:
        def __init__(self, repo: str) -> None:
            self.original_repo = repo
            self.repo = repo
            self.logger = FakeLogger()

        async def fetch_metadata(self, _github: AsyncMock) -> dict | None:
            if self.original_repo == "skip":
                return None
            if self.original_repo == "archived":
                self.repo = "archived-renamed"
                return {1: {"archived": True}}
            self.repo = "ok-renamed"
            return {2: {"repository": "ok"}}

    class FakeGitHub:
        async def __aenter__(self) -> Self:
            return Self

        async def __aexit__(self, *_args: object) -> None:
            pass

    monkeypatch.setattr(
        "metadata.summary_generator.PluginMetadataGenerator", FakeGenerator
    )
    monkeypatch.setattr(
        "aiogithubapi.GitHubAPI",
        lambda *_args, **_kwargs: FakeGitHub(),
    )
    fake_perf = iter([0.0, 1.0])
    monkeypatch.setattr(
        "metadata.summary_generator.perf_counter", lambda: next(fake_perf)
    )

    summary = SummaryGenerator(str(plugin_file), str(output_dir))
    await summary.generate("token")

    summary_data = json.loads((output_dir / "summary.json").read_text())
    assert summary_data["total_plugins"] == 3
    assert summary_data["skipped_plugins"] == 1
    assert summary_data["archived_plugins"] == 1
    assert summary_data["valid_plugins"] == 1
    assert summary_data["renamed_plugins"] == 2


async def test_fetch_metadata_early_exit_on_releases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fetch_metadata returns None if releases cannot be fetched."""
    plugin = PluginMetadataGenerator("owner/repo")

    async def fake_fetch_repository_info(_github: AsyncMock) -> bool:
        plugin.repo_metadata = MockRepo(full_name="owner/repo")
        return True

    monkeypatch.setattr(plugin, "fetch_repository_info", fake_fetch_repository_info)
    monkeypatch.setattr(plugin, "fetch_github_releases", AsyncMock(return_value=False))

    result = await plugin.fetch_metadata(AsyncMock())
    assert result is None


async def test_fetch_metadata_early_exit_on_validate_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fetch_metadata returns None if repository validation fails."""
    plugin = PluginMetadataGenerator("owner/repo")

    async def fake_fetch_repository_info(_github: AsyncMock) -> bool:
        plugin.repo_metadata = MockRepo(full_name="owner/repo")
        return True

    monkeypatch.setattr(plugin, "fetch_repository_info", fake_fetch_repository_info)
    monkeypatch.setattr(plugin, "fetch_github_releases", AsyncMock(return_value=True))
    monkeypatch.setattr(
        plugin, "validate_plugin_repository", AsyncMock(return_value=False)
    )

    result = await plugin.fetch_metadata(AsyncMock())
    assert result is None


async def test_fetch_metadata_early_exit_on_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fetch_metadata returns None if manifest fetch fails."""
    plugin = PluginMetadataGenerator("owner/repo")

    async def fake_fetch_repository_info(_github: AsyncMock) -> bool:
        plugin.repo_metadata = MockRepo(full_name="owner/repo")
        return True

    monkeypatch.setattr(plugin, "fetch_repository_info", fake_fetch_repository_info)
    monkeypatch.setattr(plugin, "fetch_github_releases", AsyncMock(return_value=True))
    monkeypatch.setattr(
        plugin, "validate_plugin_repository", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(plugin, "fetch_manifest_file", AsyncMock(return_value=False))

    result = await plugin.fetch_metadata(AsyncMock())
    assert result is None


async def test_fetch_metadata_early_exit_on_domain_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fetch_metadata returns None if domain validation fails."""
    plugin = PluginMetadataGenerator("owner/repo")

    async def fake_fetch_repository_info(_github: AsyncMock) -> bool:
        plugin.repo_metadata = MockRepo(full_name="owner/repo")
        return True

    monkeypatch.setattr(plugin, "fetch_repository_info", fake_fetch_repository_info)
    monkeypatch.setattr(plugin, "fetch_github_releases", AsyncMock(return_value=True))
    monkeypatch.setattr(
        plugin, "validate_plugin_repository", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(plugin, "fetch_manifest_file", AsyncMock(return_value=True))
    monkeypatch.setattr(
        "metadata.plugin_metadata_generator.validate_manifest_domain",
        lambda *_args, **_kwargs: False,
    )

    result = await plugin.fetch_metadata(AsyncMock())
    assert result is None


async def test_fetch_metadata_early_exit_on_version_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fetch_metadata returns None if manifest version validation fails."""
    plugin = PluginMetadataGenerator("owner/repo")

    async def fake_fetch_repository_info(_github: AsyncMock) -> bool:
        plugin.repo_metadata = MockRepo(full_name="owner/repo")
        return True

    monkeypatch.setattr(plugin, "fetch_repository_info", fake_fetch_repository_info)
    monkeypatch.setattr(plugin, "fetch_github_releases", AsyncMock(return_value=True))
    monkeypatch.setattr(
        plugin, "validate_plugin_repository", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(plugin, "fetch_manifest_file", AsyncMock(return_value=True))
    monkeypatch.setattr(
        "metadata.plugin_metadata_generator.validate_manifest_domain",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        "metadata.plugin_metadata_generator.validate_manifest_version",
        lambda *_args, **_kwargs: False,
    )

    result = await plugin.fetch_metadata(AsyncMock())
    assert result is None


async def test_fetch_metadata_handles_github_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fetch_metadata returns None if a GitHubException occurs mid-generation."""
    plugin = PluginMetadataGenerator("owner/repo")

    async def fake_fetch_repository_info(_github: AsyncMock) -> bool:
        plugin.repo_metadata = MockRepo(full_name="owner/repo")
        plugin.repo = "owner/repo"
        return True

    monkeypatch.setattr(plugin, "fetch_repository_info", fake_fetch_repository_info)
    monkeypatch.setattr(plugin, "fetch_github_releases", AsyncMock(return_value=True))
    monkeypatch.setattr(
        plugin, "validate_plugin_repository", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(plugin, "fetch_manifest_file", AsyncMock(return_value=True))
    monkeypatch.setattr(
        "metadata.plugin_metadata_generator.validate_manifest_domain",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        "metadata.plugin_metadata_generator.validate_manifest_version",
        lambda *_args, **_kwargs: True,
    )
    plugin.manifest_data = {"name": "X", "domain": "d", "version": "1.0.0"}
    monkeypatch.setattr(
        plugin,
        "_build_releases_metadata",
        AsyncMock(side_effect=GitHubException()),
    )

    result = await plugin.fetch_metadata(AsyncMock())

    assert result is None


async def test_build_releases_metadata_ignores_unrelated_zip_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not warn when a release has zip assets but no zip_filename is set."""
    plugin = PluginMetadataGenerator("owner/repo")
    plugin.manifest_data = {"name": "X"}  # No zip_filename

    class Release:
        def __init__(self) -> None:
            self.tag_name = "v1"
            self.published_at = datetime.now(UTC)
            self.prerelease = False
            self.assets = [
                type(
                    "Asset", (), {"name": "plugin.zip", "size": 1, "download_count": 2}
                )()
            ]

    plugin.releases = [Release()]
    monkeypatch.setattr(
        "metadata.plugin_metadata_generator.get_release_asset_info",
        AsyncMock(return_value=None),
    )

    releases = await plugin._build_releases_metadata(AsyncMock())
    assert releases[0]["tag_name"] == "v1"
    assert not plugin.logger.buffer


async def test_missing_asset_warning_only_on_used_ref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Warn only for used_ref when zip_filename is set."""
    plugin = PluginMetadataGenerator("owner/repo")
    plugin.manifest_data = {"name": "X", "zip_filename": "bundle.zip"}

    class ReleaseWithAsset:
        def __init__(self) -> None:
            self.tag_name = "v2"
            self.published_at = datetime.now(UTC)
            self.prerelease = False
            self.assets = [type("Asset", (), {"name": "bundle.zip"})()]

    class ReleaseWithoutAsset:
        def __init__(self) -> None:
            self.tag_name = "v1"
            self.published_at = datetime.now(UTC)
            self.prerelease = False
            self.assets = [type("Asset", (), {"name": "other.zip"})()]

    plugin.releases = [ReleaseWithAsset(), ReleaseWithoutAsset()]

    monkeypatch.setattr(
        "metadata.plugin_metadata_generator.get_release_asset_info",
        AsyncMock(return_value={"name": "bundle.zip"}),
    )

    releases = await plugin._build_releases_metadata(AsyncMock())

    assert len(releases) == 2
    # No warnings because used_ref (v2) had the asset, v1 missing does not warn
    assert not plugin.logger.buffer


async def test_build_releases_metadata_skips_missing_and_duplicate_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unnamed and duplicate assets should be skipped before asset lookup."""
    plugin = PluginMetadataGenerator("owner/repo")
    plugin.manifest_data = {"name": "X"}

    class Release:
        def __init__(self) -> None:
            self.tag_name = "v1"
            self.published_at = datetime.now(UTC)
            self.prerelease = False
            self.assets = [
                type("Asset", (), {"name": None})(),
                type("Asset", (), {"name": "plugin.zip"})(),
                type("Asset", (), {"name": "plugin.zip"})(),
            ]

    asset_lookup = AsyncMock(return_value={"name": "plugin.zip"})
    plugin.releases = [Release()]
    monkeypatch.setattr(
        "metadata.plugin_metadata_generator.get_release_asset_info",
        asset_lookup,
    )

    releases = await plugin._build_releases_metadata(AsyncMock())

    assert releases == [
        {
            "tag_name": "v1",
            "published_at": plugin.releases[0].published_at,
            "prerelease": False,
            "assets": [{"name": "plugin.zip"}],
        }
    ]
    assert asset_lookup.await_count == 1


async def test_build_releases_metadata_warns_for_missing_manifest_zip_on_used_ref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Warn when manifest zip_filename is absent from the release for used_ref."""
    plugin = PluginMetadataGenerator("owner/repo")
    plugin.manifest_data = {"name": "X", "zip_filename": "bundle.zip"}

    class Release:
        def __init__(self) -> None:
            self.tag_name = "v1"
            self.published_at = datetime.now(UTC)
            self.prerelease = False
            self.assets = [type("Asset", (), {"name": "other.zip"})()]

    plugin.releases = [Release()]
    monkeypatch.setattr(
        "metadata.plugin_metadata_generator.get_release_asset_info",
        AsyncMock(return_value=None),
    )

    releases = await plugin._build_releases_metadata(AsyncMock())

    assert releases == [
        {
            "tag_name": "v1",
            "published_at": plugin.releases[0].published_at,
            "prerelease": False,
        }
    ]
    assert any(
        message == "Manifest `zip_filename` 'bundle.zip' was not found in release v1."
        for _level, message in plugin.logger.buffer
    )


def test_metadata_main_runs_summary_generator(monkeypatch: pytest.MonkeyPatch) -> None:
    """metadata/main.py should instantiate SummaryGenerator and run generate()."""
    calls: dict[str, object] = {}
    fake_output_dir = Path("/safe/test-output")
    fake_plugin_list_file = Path("/safe/test-plugins.json")

    class FakeSummaryGenerator:
        def __init__(self, plugin_file: str, output_dir: str) -> None:
            calls["plugin_file"] = plugin_file
            calls["output_dir"] = output_dir

        async def generate(self, token: str) -> str:
            calls["token"] = token
            return "generated"

    fake_const = types.SimpleNamespace(
        GITHUB_TOKEN=TEST_GITHUB_TOKEN,
        OUTPUT_DIR=str(fake_output_dir),
        PLUGIN_LIST_FILE=str(fake_plugin_list_file),
    )
    fake_summary_module = types.SimpleNamespace(SummaryGenerator=FakeSummaryGenerator)
    original_asyncio_run = asyncio.run

    def fake_run(awaitable: object) -> None:
        calls["awaitable"] = awaitable
        calls["result"] = original_asyncio_run(awaitable)

    monkeypatch.setitem(sys.modules, "const", fake_const)
    monkeypatch.setitem(sys.modules, "summary_generator", fake_summary_module)
    monkeypatch.setattr(asyncio, "run", fake_run)

    runpy.run_path(
        "/home/klaas/community-plugins/metadata/main.py",
        run_name="__main__",
    )

    assert calls["plugin_file"] == str(fake_plugin_list_file)
    assert calls["output_dir"] == str(fake_output_dir)
    assert calls["token"] == TEST_GITHUB_TOKEN
    assert calls["awaitable"] is not None
    assert calls["result"] == "generated"
