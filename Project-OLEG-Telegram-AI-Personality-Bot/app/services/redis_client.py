"""Redis client for caching and rate limiting."""

import logging
from typing import Optional, Any
from datetime import timedelta

# Prefer orjson for faster JSON serialization
try:
    import orjson
    def _json_dumps(data: Any) -> str:
        return orjson.dumps(data).decode("utf-8")
    def _json_loads(data: str) -> Any:
        return orjson.loads(data)
except ImportError:
    import json
    _json_dumps = json.dumps
    _json_loads = json.loads

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from app.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client wrapper with fallback to in-memory."""
    
    def __init__(self):
        self._client: Optional[Any] = None
        self._available = False
        
    async def connect(self):
        """Connect to Redis server."""
        if not REDIS_AVAILABLE:
            logger.warning("redis package not installed, using in-memory fallback")
            return
            
        if not settings.redis_enabled:
            logger.info("Redis disabled in config, using in-memory fallback")
            return
            
        try:
            self._client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password if settings.redis_password else None,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test connection
            await self._client.ping()
            self._available = True
            logger.info(f"Connected to Redis at {settings.redis_host}:{settings.redis_port}")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Using in-memory fallback")
            self._client = None
            self._available = False
    
    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            logger.info("Redis connection closed")
    
    @property
    def is_available(self) -> bool:
        """Check if Redis is available."""
        return self._available
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        if not self._available:
            return None
        try:
            return await self._client.get(key)
        except Exception as e:
            logger.error(f"Redis GET error: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: str,
        ex: Optional[int] = None,
        px: Optional[int] = None,
    ) -> bool:
        """
        Set key-value pair.
        
        Args:
            key: Key name
            value: Value to store
            ex: Expiration time in seconds
            px: Expiration time in milliseconds
            
        Returns:
            True if successful
        """
        if not self._available:
            return False
        try:
            await self._client.set(key, value, ex=ex, px=px)
            return True
        except Exception as e:
            logger.error(f"Redis SET error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key."""
        if not self._available:
            return False
        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")
            return False
    
    async def incr(self, key: str) -> Optional[int]:
        """Increment counter."""
        if not self._available:
            return None
        try:
            return await self._client.incr(key)
        except Exception as e:
            logger.error(f"Redis INCR error: {e}")
            return None
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set key expiration."""
        if not self._available:
            return False
        try:
            await self._client.expire(key, seconds)
            return True
        except Exception as e:
            logger.error(f"Redis EXPIRE error: {e}")
            return False
    
    async def ttl(self, key: str) -> Optional[int]:
        """Get time to live for key."""
        if not self._available:
            return None
        try:
            return await self._client.ttl(key)
        except Exception as e:
            logger.error(f"Redis TTL error: {e}")
            return None
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self._available:
            return False
        try:
            return await self._client.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis EXISTS error: {e}")
            return False
    
    async def get_json(self, key: str) -> Optional[Any]:
        """Get JSON value by key."""
        value = await self.get(key)
        if value:
            try:
                return _json_loads(value)
            except (ValueError, TypeError):
                logger.error(f"Failed to decode JSON for key {key}")
        return None
    
    async def set_json(
        self,
        key: str,
        value: Any,
        ex: Optional[int] = None,
    ) -> bool:
        """Set JSON value."""
        try:
            json_str = _json_dumps(value)
            return await self.set(key, json_str, ex=ex)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to encode JSON: {e}")
            return False


# Global Redis client instance
redis_client = RedisClient()
