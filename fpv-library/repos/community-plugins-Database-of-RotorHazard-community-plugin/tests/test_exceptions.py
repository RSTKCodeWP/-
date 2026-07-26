"""Test exceptions in the generate_metadata script."""

import base64
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from aiogithubapi import (
    GitHubException,
    GitHubNotFoundException,
    GitHubRatelimitException,
)
from metadata import PluginMetadataGenerator, validate_manifest_domain

from . import load_fixture
from .conftest import MockGitHubResponse, MockRepo


async def test_fetch_repository_info_not_found(
    mock_github: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test repository not found exception in the PluginMetadataGenerator class."""

    async def get_raise(repo_name: str) -> None:
        raise GitHubNotFoundException("Repository not found")

    monkeypatch.setattr(mock_github.repos, "get", get_raise)
    plugin = PluginMetadataGenerator("owner/nonexistent")
    result = await plugin.fetch_repository_info(mock_github)
    assert result is False


async def test_fetch_repository_info_rate_limit(
    mock_github: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test rate limit exception in the PluginMetadataGenerator class."""

    async def get_rate_limit(repo_name: str) -> None:
        raise GitHubRatelimitException("Rate limit exceeded")

    monkeypatch.setattr(mock_github.repos, "get", get_rate_limit)
    plugin = PluginMetadataGenerator("owner/repo")
    result = await plugin.fetch_repository_info(mock_github)
    assert result is False


async def test_fetch_manifest_file_json_decode_error(
    mock_github: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the PluginMetadataGenerator class with a JSON decode error."""

    async def get_bad_manifest(
        repo_name: str,
        path: str,
        etag: str | None = None,
    ) -> MockGitHubResponse:
        content = base64.b64encode(b"not a json").decode("utf-8")
        file_data = type("Data", (), {"content": content})
        return MockGitHubResponse(data=file_data, etag="mock_manifest_etag")

    monkeypatch.setattr(mock_github.repos.contents, "get", get_bad_manifest)
    plugin = PluginMetadataGenerator("owner/repo")
    plugin.repo_metadata = MockRepo(
        full_name="owner/repo",
        default_branch="main",
        updated_at=datetime(2025, 3, 9, tzinfo=UTC).isoformat(),
    )
    result = await plugin.fetch_manifest_file(mock_github)
    assert result is False


async def test_fetch_manifest_file_not_found(
    mock_github: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the PluginMetadataGenerator class with a missing manifest file."""

    async def get_raise(
        repo_name: str,
        path: str,
        etag: str | None = None,
    ) -> None:
        raise GitHubNotFoundException("Manifest file not found")

    monkeypatch.setattr(mock_github.repos.contents, "get", get_raise)
    plugin = PluginMetadataGenerator("owner/repo")
    plugin.repo_metadata = MockRepo(
        full_name="owner/repo",
        default_branch="main",
        updated_at=datetime(2025, 3, 9, tzinfo=UTC).isoformat(),
    )
    result = await plugin.fetch_manifest_file(mock_github)
    assert result is False


async def test_validate_manifest_domain_exception(
    mock_github: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test on a manifest with an invalid domain set as the plugin domain."""
    original_get = mock_github.repos.contents.get

    async def get_manifest(
        repo_name: str,
        path: str = "",
    ) -> MockGitHubResponse:
        if not path:
            path = "custom_plugins"
        base_path = path.split("?", 1)[0]
        if base_path == "custom_plugins/testdomain/manifest.json":
            content = base64.b64encode(
                json.dumps(load_fixture("wrong_domain_manifest.json")).encode("utf-8")
            ).decode("utf-8")
            file_data = type("Data", (), {"content": content})
            return MockGitHubResponse(data=file_data, etag="mock_manifest_etag")
        return await original_get(repo_name, path)

    monkeypatch.setattr(mock_github.repos.contents, "get", get_manifest)

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


async def test_validate_plugin_repository_missing_custom_plugins(
    mock_github: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test validation when custom_plugins folder is missing."""
    original_get = mock_github.repos.contents.get

    async def get_no_custom_plugins(
        repo_name: str,
        path: str = "",
    ) -> MockGitHubResponse:
        # Return empty list of folders (no custom_plugins) when fetching root
        if "?ref=" in path and "custom_plugins" not in path:
            # Root directory with no custom_plugins folder
            other_folder = type("Folder", (), {"name": "other", "type": "dir"})
            return MockGitHubResponse(data=[other_folder], etag="mock_etag")
        return await original_get(repo_name, path)

    monkeypatch.setattr(mock_github.repos.contents, "get", get_no_custom_plugins)

    plugin = PluginMetadataGenerator("owner/repo")
    await plugin.fetch_repository_info(mock_github)
    await plugin.fetch_github_releases(mock_github)
    result = await plugin.validate_plugin_repository(mock_github)
    assert result is False


async def test_validate_plugin_repository_multiple_domains(
    mock_github: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test validation when custom_plugins has multiple domain folders."""
    original_get = mock_github.repos.contents.get

    async def get_multiple_domains(
        repo_name: str,
        path: str = "",
    ) -> MockGitHubResponse:
        if "custom_plugins" in path and "ref=" in path and "manifest" not in path:
            # Return multiple domain folders
            folder1 = type("Folder", (), {"name": "domain1", "type": "dir"})
            folder2 = type("Folder", (), {"name": "domain2", "type": "dir"})
            return MockGitHubResponse(data=[folder1, folder2], etag="mock_etag")
        return await original_get(repo_name, path)

    monkeypatch.setattr(mock_github.repos.contents, "get", get_multiple_domains)

    plugin = PluginMetadataGenerator("owner/repo")
    await plugin.fetch_repository_info(mock_github)
    await plugin.fetch_github_releases(mock_github)
    result = await plugin.validate_plugin_repository(mock_github)
    assert result is False


async def test_validate_plugin_repository_github_exception(
    mock_github: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test validation when GitHub API raises an exception."""

    async def get_raise(
        repo_name: str,
        path: str = "",
    ) -> None:
        raise GitHubException("API error")

    monkeypatch.setattr(mock_github.repos.contents, "get", get_raise)

    plugin = PluginMetadataGenerator("owner/repo")
    await plugin.fetch_repository_info(mock_github)
    await plugin.fetch_github_releases(mock_github)
    result = await plugin.validate_plugin_repository(mock_github)
    assert result is False


async def test_fetch_github_releases_no_releases(
    mock_github: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test when repository has no releases."""

    async def list_no_releases(repo_name: str) -> MockGitHubResponse:
        return MockGitHubResponse(data=[], etag="mock_etag")

    monkeypatch.setattr(
        mock_github.repos.releases,
        "list",
        AsyncMock(side_effect=list_no_releases),
    )

    plugin = PluginMetadataGenerator("owner/repo")
    await plugin.fetch_repository_info(mock_github)
    result = await plugin.fetch_github_releases(mock_github)
    assert result is False


async def test_fetch_github_releases_exception(
    mock_github: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test when fetching releases raises an exception."""

    async def list_raise(repo_name: str) -> None:
        raise GitHubException("Error fetching releases")

    monkeypatch.setattr(
        mock_github.repos.releases,
        "list",
        AsyncMock(side_effect=list_raise),
    )

    plugin = PluginMetadataGenerator("owner/repo")
    await plugin.fetch_repository_info(mock_github)
    result = await plugin.fetch_github_releases(mock_github)
    assert result is False
