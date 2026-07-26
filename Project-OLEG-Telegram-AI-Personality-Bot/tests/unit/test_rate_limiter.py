"""Tests for rate limiter."""

import pytest
import asyncio
from app.middleware.rate_limit import RateLimiter


@pytest.fixture
def rate_limiter():
    """Create rate limiter instance."""
    return RateLimiter(max_requests=3, window_seconds=10)


@pytest.mark.asyncio
async def test_rate_limiter_allows_requests_within_limit(rate_limiter):
    """Test that requests within limit are allowed."""
    user_id = 12345
    
    # First 3 requests should be allowed
    assert await rate_limiter.is_allowed(user_id) is True
    assert await rate_limiter.is_allowed(user_id) is True
    assert await rate_limiter.is_allowed(user_id) is True


@pytest.mark.asyncio
async def test_rate_limiter_blocks_requests_over_limit(rate_limiter):
    """Test that requests over limit are blocked."""
    user_id = 12345
    
    # First 3 requests allowed
    for _ in range(3):
        await rate_limiter.is_allowed(user_id)
    
    # 4th request should be blocked
    assert await rate_limiter.is_allowed(user_id) is False


@pytest.mark.asyncio
async def test_rate_limiter_resets_after_window(rate_limiter):
    """Test that rate limiter resets after time window."""
    user_id = 12345
    
    # Use up all requests
    for _ in range(3):
        await rate_limiter.is_allowed(user_id)
    
    # Should be blocked
    assert await rate_limiter.is_allowed(user_id) is False
    
    # Wait for window to expire (add small buffer)
    await asyncio.sleep(11)
    
    # Should be allowed again
    assert await rate_limiter.is_allowed(user_id) is True


@pytest.mark.asyncio
async def test_rate_limiter_different_users(rate_limiter):
    """Test that different users have separate limits."""
    user1 = 12345
    user2 = 67890
    
    # User 1 uses all requests
    for _ in range(3):
        await rate_limiter.is_allowed(user1)
    
    # User 1 should be blocked
    assert await rate_limiter.is_allowed(user1) is False
    
    # User 2 should still be allowed
    assert await rate_limiter.is_allowed(user2) is True


@pytest.mark.asyncio
async def test_rate_limiter_remaining_time(rate_limiter):
    """Test remaining time calculation."""
    user_id = 12345
    
    # Use up all requests
    for _ in range(3):
        await rate_limiter.is_allowed(user_id)
    
    # Get remaining time
    remaining = await rate_limiter.get_remaining_time(user_id)
    
    # Should be close to window_seconds (10)
    assert 8 <= remaining <= 10
    
    # Wait a bit
    await asyncio.sleep(2)
    
    # Remaining time should decrease
    remaining_after = await rate_limiter.get_remaining_time(user_id)
    assert remaining_after < remaining
