"""Tests for asset handler functionality."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

from metadata.generator.asset_handler import get_release_asset_info
from metadata.generator.log_buffer import PluginLogBuffer

from .conftest import MockRelease, MockReleaseAsset


async def test_asset_not_found(mock_github: AsyncMock) -> None:
    """Test when asset is not found in release."""
    logger = PluginLogBuffer(Mock())
    release = MockRelease(
        tag_name="v1.0.0",
        prerelease=False,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
        assets=[
            MockReleaseAsset(
                name="other.zip",
                browser_download_url="https://example.com/other.zip",
                digest="sha256:abc123",
            )
        ],
    )

    result = await get_release_asset_info(mock_github, release, "plugin.zip", logger)
    assert result is None


async def test_asset_with_size_only(mock_github: AsyncMock) -> None:
    """Test asset with size but no download count."""
    logger = PluginLogBuffer(Mock())
    release = MockRelease(
        tag_name="v1.0.0",
        prerelease=False,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
        assets=[
            MockReleaseAsset(
                name="plugin.zip",
                browser_download_url="https://example.com/plugin.zip",
                digest="sha256:abc123",
                size=1024,
            )
        ],
    )

    result = await get_release_asset_info(mock_github, release, "plugin.zip", logger)
    assert result is not None
    assert result["size"] == 1024
    assert "download_count" not in result


async def test_asset_with_download_count_only(mock_github: AsyncMock) -> None:
    """Test asset with download count but no size."""
    logger = PluginLogBuffer(Mock())
    release = MockRelease(
        tag_name="v1.0.0",
        prerelease=False,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
        assets=[
            MockReleaseAsset(
                name="plugin.zip",
                browser_download_url="https://example.com/plugin.zip",
                digest="sha256:abc123",
                download_count=50,
            )
        ],
    )

    result = await get_release_asset_info(mock_github, release, "plugin.zip", logger)
    assert result is not None
    assert result["download_count"] == 50
    assert "size" not in result


async def test_asset_no_download_url(mock_github: AsyncMock) -> None:
    """Test asset without digest or download URL."""
    logger = PluginLogBuffer(Mock())
    asset = type(
        "Asset",
        (),
        {
            "name": "plugin.zip",
            "browser_download_url": None,
            "url": None,
            "digest": None,
            "size": 2048,
            "download_count": 10,
        },
    )
    release = MockRelease(
        tag_name="v1.0.0",
        prerelease=False,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
        assets=[asset],
    )

    result = await get_release_asset_info(mock_github, release, "plugin.zip", logger)
    assert result is not None
    assert "sha256" not in result
    assert result["size"] == 2048
    assert result["download_count"] == 10


async def test_asset_digest_from_data_payload(mock_github: AsyncMock) -> None:
    """Digest should be read from data payload when not exposed as attribute."""
    logger = PluginLogBuffer(Mock())

    class DataAsset:
        def __init__(self) -> None:
            self.name = "plugin.zip"
            self.browser_download_url = "https://example.com/plugin.zip"
            self.size = 111
            self.download_count = 22
            self.data = {"digest": "sha256:abc123"}

    release = MockRelease(
        tag_name="v1.0.0",
        prerelease=False,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
        assets=[DataAsset()],
    )

    result = await get_release_asset_info(mock_github, release, "plugin.zip", logger)
    assert result is not None
    assert result["sha256"] == "abc123"
    assert result["size"] == 111
    assert result["download_count"] == 22


async def test_asset_digest_from_raw_data_fields(mock_github: AsyncMock) -> None:
    """Digest should be found in raw_data fallback fields."""
    logger = PluginLogBuffer(Mock())

    class RawAsset:
        def __init__(self) -> None:
            self.name = "plugin.zip"
            self.browser_download_url = "https://example.com/plugin.zip"
            self.size = 333
            self.download_count = 44
            self._raw_data = {"digest": "sha256:def456"}

    release = MockRelease(
        tag_name="v1.0.0",
        prerelease=False,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
        assets=[RawAsset()],
    )

    result = await get_release_asset_info(mock_github, release, "plugin.zip", logger)
    assert result is not None
    assert result["sha256"] == "def456"
    assert result["size"] == 333
    assert result["download_count"] == 44


async def test_asset_data_without_digest(mock_github: AsyncMock) -> None:
    """When data payload has no digest, sha256 should be omitted."""
    logger = PluginLogBuffer(Mock())

    class DataAsset:
        def __init__(self) -> None:
            self.name = "plugin.zip"
            self.browser_download_url = "https://example.com/plugin.zip"
            self.size = 222
            self.download_count = 33
            self.data = {}

    release = MockRelease(
        tag_name="v1.0.0",
        prerelease=False,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
        assets=[DataAsset()],
    )

    result = await get_release_asset_info(mock_github, release, "plugin.zip", logger)
    assert result is not None
    assert result["name"] == "plugin.zip"
    assert result["size"] == 222
    assert result["download_count"] == 33
    assert "sha256" not in result
