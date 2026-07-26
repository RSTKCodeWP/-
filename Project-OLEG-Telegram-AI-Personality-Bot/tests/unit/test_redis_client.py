"""Tests for Redis client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.redis_client import RedisClient


@pytest.fixture
def redis_client():
    """Create Redis client instance."""
    return RedisClient()


@pytest.mark.asyncio
async def test_redis_client_not_available_without_package(redis_client):
    """Test that client handles missing redis package."""
    with patch('app.services.redis_client.REDIS_AVAILABLE', False):
        await redis_client.connect()
        assert redis_client.is_available is False


@pytest.mark.asyncio
async def test_redis_client_get_returns_none_when_unavailable(redis_client):
    """Test that get returns None when Redis is unavailable."""
    redis_client._available = False
    result = await redis_client.get("test_key")
    assert result is None


@pytest.mark.asyncio
async def test_redis_client_set_returns_false_when_unavailable(redis_client):
    """Test that set returns False when Redis is unavailable."""
    redis_client._available = False
    result = await redis_client.set("test_key", "test_value")
    assert result is False


@pytest.mark.asyncio
async def test_redis_client_json_operations(redis_client):
    """Test JSON get/set operations."""
    redis_client._available = True
    redis_client._client = AsyncMock()
    
    # Mock get to return JSON string
    redis_client._client.get.return_value = '{"key": "value"}'
    
    result = await redis_client.get_json("test_key")
    assert result == {"key": "value"}
    
    # Test set_json
    redis_client._client.set = AsyncMock()
    await redis_client.set_json("test_key", {"key": "value"})
    redis_client._client.set.assert_called_once()


@pytest.mark.asyncio
async def test_redis_client_handles_connection_error(redis_client):
    """Test that client handles connection errors gracefully."""
    with patch('app.services.redis_client.REDIS_AVAILABLE', True):
        with patch('app.services.redis_client.redis.Redis') as mock_redis:
            mock_redis.return_value.ping = AsyncMock(side_effect=Exception("Connection failed"))
            
            await redis_client.connect()
            assert redis_client.is_available is False
