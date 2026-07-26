"""Global Rate Limiter Service - Chat-level LLM Request Limiting.

This module provides the Global Rate Limiter system for managing chat-wide
LLM request limits to ensure cost-effectiveness and responsiveness.

**Feature: shield-economy-v65**
**Validates: Requirements 2.1, 2.2, 2.3, 2.4**
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ChatRateLimitConfig
from app.database.session import get_session
from app.services.redis_client import redis_client
from app.utils import utc_now

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Default LLM requests per minute limit
DEFAULT_LIMIT = 20

# Rate limit window in seconds (1 minute)
RATE_LIMIT_WINDOW = 60

# Redis key prefix for rate limit counters
REDIS_KEY_PREFIX = "rate_limit:"

# Cached "busy" response message
BUSY_RESPONSE = "Занят."


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ChatRateLimit:
    """
    Rate limit status for a chat.
    
    Attributes:
        chat_id: Telegram chat ID
        request_count: Current request count in window
        limit: Maximum requests per minute
        window_start: When the current window started
    """
    chat_id: int
    request_count: int = 0
    limit: int = DEFAULT_LIMIT
    window_start: Optional[datetime] = None


# ============================================================================
# Global Rate Limiter Service
# ============================================================================

class GlobalRateLimiterService:
    """
    Service for managing chat-wide LLM request rate limits.
    
    Provides methods for:
    - Checking if a chat has exceeded its rate limit
    - Incrementing the request counter
    - Configuring custom limits per chat
    - Getting current limit configuration
    
    Uses Redis for fast access with in-memory fallback.
    
    **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
    """
    
    def __init__(self):
        """Initialize GlobalRateLimiterService with in-memory fallback."""
        # In-memory fallback when Redis is unavailable
        self._memory_counters: Dict[int, Tuple[int, datetime]] = {}
        # Cache for limit configurations
        self._limit_cache: Dict[int, int] = {}

    
    # =========================================================================
    # Redis Key Helpers
    # =========================================================================
    
    def _get_redis_key(self, chat_id: int) -> str:
        """Generate Redis key for chat rate limit counter."""
        return f"{REDIS_KEY_PREFIX}{chat_id}"
    
    # =========================================================================
    # Core Rate Limiting Methods
    # =========================================================================
    
    async def check_chat_limit(
        self,
        chat_id: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a chat has exceeded its rate limit.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            Tuple of (can_proceed, busy_message)
            - can_proceed: True if chat is under limit
            - busy_message: "Занят." if limit exceeded, None otherwise
            
        **Validates: Requirements 2.1, 2.2**
        """
        limit = await self.get_chat_limit(chat_id)
        count = await self._get_current_count(chat_id)
        
        if count >= limit:
            logger.debug(f"Chat {chat_id} rate limit exceeded: {count}/{limit}")
            return False, BUSY_RESPONSE
        
        return True, None
    
    async def increment_chat_counter(
        self,
        chat_id: int
    ) -> int:
        """
        Increment the request counter for a chat.
        
        Should be called after a successful LLM request.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            New counter value
            
        **Validates: Requirements 2.1**
        """
        if redis_client.is_available:
            return await self._increment_redis(chat_id)
        else:
            return self._increment_memory(chat_id)
    
    async def set_chat_limit(
        self,
        chat_id: int,
        limit: int
    ) -> None:
        """
        Set custom rate limit for a chat.
        
        The new limit is applied within 5 seconds (immediately in practice).
        
        Args:
            chat_id: Telegram chat ID
            limit: New requests per minute limit
            
        **Validates: Requirements 2.3**
        """
        if limit < 1:
            raise ValueError("Limit must be at least 1")
        
        # Update database
        await self._save_limit_to_db(chat_id, limit)
        
        # Update cache immediately
        self._limit_cache[chat_id] = limit
        
        logger.info(f"Rate limit for chat {chat_id} set to {limit} req/min")
    
    async def get_chat_limit(
        self,
        chat_id: int
    ) -> int:
        """
        Get the rate limit for a chat.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            Requests per minute limit (default: 20)
        """
        # Check cache first
        if chat_id in self._limit_cache:
            return self._limit_cache[chat_id]
        
        # Load from database
        limit = await self._load_limit_from_db(chat_id)
        self._limit_cache[chat_id] = limit
        
        return limit
    
    async def get_current_count(
        self,
        chat_id: int
    ) -> int:
        """
        Get current request count for a chat.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            Current request count in the window
        """
        return await self._get_current_count(chat_id)
    
    async def reset_counter(
        self,
        chat_id: int
    ) -> None:
        """
        Reset the request counter for a chat.
        
        Args:
            chat_id: Telegram chat ID
            
        **Validates: Requirements 2.4**
        """
        if redis_client.is_available:
            redis_key = self._get_redis_key(chat_id)
            await redis_client.delete(redis_key)
        
        if chat_id in self._memory_counters:
            del self._memory_counters[chat_id]
        
        logger.debug(f"Rate limit counter reset for chat {chat_id}")
    
    # =========================================================================
    # Private Helper Methods - Redis
    # =========================================================================
    
    async def _get_current_count(
        self,
        chat_id: int
    ) -> int:
        """Get current request count from Redis or memory."""
        if redis_client.is_available:
            redis_key = self._get_redis_key(chat_id)
            value = await redis_client.get(redis_key)
            return int(value) if value else 0
        else:
            return self._get_memory_count(chat_id)
    
    async def _increment_redis(
        self,
        chat_id: int
    ) -> int:
        """Increment counter in Redis with TTL."""
        redis_key = self._get_redis_key(chat_id)
        
        # Check if key exists to determine if we need to set TTL
        exists = await redis_client.exists(redis_key)
        
        # Increment counter
        new_count = await redis_client.incr(redis_key)
        
        # Set TTL only on first increment (new window)
        if not exists and new_count is not None:
            await redis_client.expire(redis_key, RATE_LIMIT_WINDOW)
        
        return new_count or 0
    
    # =========================================================================
    # Private Helper Methods - Memory Fallback
    # =========================================================================
    
    def _get_memory_count(
        self,
        chat_id: int
    ) -> int:
        """Get current count from memory, handling window expiration."""
        if chat_id not in self._memory_counters:
            return 0
        
        count, window_start = self._memory_counters[chat_id]
        now = utc_now()
        
        # Check if window has expired
        elapsed = (now - window_start).total_seconds()
        if elapsed >= RATE_LIMIT_WINDOW:
            # Window expired, reset counter
            del self._memory_counters[chat_id]
            return 0
        
        return count
    
    def _increment_memory(
        self,
        chat_id: int
    ) -> int:
        """Increment counter in memory with window tracking."""
        now = utc_now()
        
        if chat_id in self._memory_counters:
            count, window_start = self._memory_counters[chat_id]
            elapsed = (now - window_start).total_seconds()
            
            if elapsed >= RATE_LIMIT_WINDOW:
                # Start new window
                self._memory_counters[chat_id] = (1, now)
                return 1
            else:
                # Increment in current window
                new_count = count + 1
                self._memory_counters[chat_id] = (new_count, window_start)
                return new_count
        else:
            # First request, start new window
            self._memory_counters[chat_id] = (1, now)
            return 1
    
    # =========================================================================
    # Private Helper Methods - Database
    # =========================================================================
    
    async def _load_limit_from_db(
        self,
        chat_id: int
    ) -> int:
        """Load rate limit configuration from database."""
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(ChatRateLimitConfig).filter_by(chat_id=chat_id)
            )
            config = result.scalar_one_or_none()
            
            if config is None:
                return DEFAULT_LIMIT
            
            return config.llm_requests_per_minute
    
    async def _save_limit_to_db(
        self,
        chat_id: int,
        limit: int
    ) -> None:
        """Save rate limit configuration to database."""
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(ChatRateLimitConfig).filter_by(chat_id=chat_id)
            )
            config = result.scalar_one_or_none()
            
            if config is None:
                config = ChatRateLimitConfig(
                    chat_id=chat_id,
                    llm_requests_per_minute=limit,
                )
                session.add(config)
            else:
                config.llm_requests_per_minute = limit
                config.updated_at = utc_now()
            
            await session.commit()
    
    def invalidate_cache(self, chat_id: int) -> None:
        """Invalidate cached limit for a chat."""
        self._limit_cache.pop(chat_id, None)


# Global service instance
global_rate_limiter_service = GlobalRateLimiterService()
