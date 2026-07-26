"""Globale fixtures for the tests."""

import base64
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from . import load_fixture


@dataclass
class MockGitHubResponse:
    """Mock GitHub response."""

    data: Any
    etag: str = "mock_etag"


@dataclass
class MockRepo:
    """Mock GitHub repository."""

    full_name: str
    archived: bool = False
    default_branch: str = "main"
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    open_issues_count: int = 0
    stargazers_count: int = 10
    watchers_count: int = 10
    forks_count: int = 10
    topics: list[str] = field(default_factory=list)
    id: int = 123456


@dataclass
class MockRelease:
    """Mock GitHub release."""

    tag_name: str
    prerelease: bool
    created_at: datetime
    published_at: datetime
    assets: list[Any] = field(default_factory=list)


@dataclass
class MockReleaseAsset:
    """Mock GitHub release asset."""

    name: str
    browser_download_url: str
    digest: str | None = None
    size: int | None = None
    download_count: int | None = None


def create_mock_repos(
    mock_repos_releases: MagicMock,
    mock_repos_contents: MagicMock,
) -> MagicMock:
    """Create a mock GitHubAPI.repos object."""
    mock = MagicMock()
    # Simulate the GitHubAPI.repos.get method
    mock.get = AsyncMock()
    mock.get.return_value = MockGitHubResponse(
        data=MockRepo(
            full_name="owner/repo",
            archived=False,
            default_branch="main",
            updated_at=datetime.now(UTC).isoformat(),
            open_issues_count=5,
            stargazers_count=100,
            topics=["python", "plugin"],
            id=1,
        ),
        etag="mock_repo_etag",
    )
    mock.releases = MagicMock()
    mock.releases.list = mock_repos_releases
    mock.contents = MagicMock()
    mock.contents.get = mock_repos_contents
    return mock


@pytest.fixture
def mock_repos_releases() -> MagicMock:
    """Fixture to mock the GitHubAPI.repos.releases.list method."""

    async def list_releases(repo_name: str) -> MockGitHubResponse:
        """Return a list of releases."""
        release_data = load_fixture("releases_data.json")
        releases_list = []
        for item in release_data:
            created_at = datetime.strptime(
                item["created_at"], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=UTC)
            published_at = datetime.strptime(
                item["published_at"], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=UTC)
            assets = [
                MockReleaseAsset(
                    name=asset["name"],
                    browser_download_url=asset["browser_download_url"],
                    digest=asset.get("digest"),
                    size=asset.get("size"),
                    download_count=asset.get("download_count"),
                )
                for asset in item.get("assets", [])
            ]
            releases_list.append(
                MockRelease(
                    tag_name=item["tag_name"],
                    prerelease=item["prerelease"],
                    created_at=created_at,
                    published_at=published_at,
                    assets=assets,
                )
            )
        return MockGitHubResponse(data=releases_list, etag="mock_releases_etag")

    return AsyncMock(side_effect=list_releases)


@pytest.fixture
def mock_repos_contents() -> MagicMock:
    """Fixture to mock the GitHubAPI.repos.contents.get method."""

    async def get_contents(
        repo_name: str,
        path: str = "custom_plugins",
    ) -> MockGitHubResponse:
        base_path = path.split("?", 1)[0].strip()

        # Define a dataclass for the folder item
        @dataclass
        class FolderItem:
            name: str
            type: str

        if base_path == "" or base_path.startswith("?"):
            return MockGitHubResponse(data=[FolderItem("custom_plugins", "dir")])
        if base_path == "custom_plugins":
            return MockGitHubResponse(data=[FolderItem("testdomain", "dir")])
        if base_path == "custom_plugins/testdomain/manifest.json":
            content = base64.b64encode(
                json.dumps(load_fixture("manifest_data.json")).encode("utf-8")
            ).decode("utf-8")
            file_data = type("Data", (), {"content": content})
            return MockGitHubResponse(data=file_data, etag="mock_manifest_etag")
        file_data = type("Data", (), {"content": ""})
        return MockGitHubResponse(data=file_data, etag="mock_etag")

    return AsyncMock(side_effect=get_contents)


@pytest.fixture
def plugins_file(tmp_path: Path) -> Path:
    """Fixture to create a plugins.json file."""
    plugins = ["owner/repo", "owner/repo_archived"]
    file = tmp_path / "plugins.json"
    file.write_text(json.dumps(plugins))
    return file


@pytest.fixture
def mock_repos(
    mock_repos_releases: MagicMock,
    mock_repos_contents: MagicMock,
) -> MagicMock:
    """Fixture to mock the GitHubAPI.repos object."""
    return create_mock_repos(mock_repos_releases, mock_repos_contents)


@pytest.fixture
def mock_github(
    monkeypatch: pytest.MonkeyPatch,
    mock_repos_releases: MagicMock,
    mock_repos_contents: MagicMock,
) -> MagicMock:
    """Mock GitHubAPI for testing."""
    mock_repos_obj = create_mock_repos(mock_repos_releases, mock_repos_contents)

    class MockGitHubAPIForTest:
        def __init__(self, token: str | None = None) -> None:
            self.token = token
            self.repos = mock_repos_obj
            self._session = None  # Mock internal session (not used in tests)

        async def __aenter__(self) -> MagicMock:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            pass

    monkeypatch.setattr(
        "aiogithubapi.GitHubAPI", lambda token=None: MockGitHubAPIForTest(token)
    )
    return MockGitHubAPIForTest()
