"""Rate limiting middleware to prevent spam and abuse."""

import logging
import re
import time
from typing import Callable, Awaitable, Dict, Any
from collections import defaultdict, deque
from aiogram import BaseMiddleware
from aiogram.types import Message

from app.config import settings

logger = logging.getLogger(__name__)


def is_direct_bot_request(event: Message) -> bool:
    """
    Проверяет, является ли сообщение прямым обращением к боту.
    
    Rate limit применяется только для прямых обращений:
    - Команды (начинаются с /)
    - Упоминание бота (@botname)
    - Упоминание "олег" в тексте
    - Реплай на сообщение бота
    - Личные сообщения
    
    Для рандомных ответов и ответов на вопросы (когда бот сам решает ответить)
    rate limit НЕ применяется.
    """
    # Личные сообщения — всегда прямое обращение
    if event.chat.type == "private":
        return True
    
    text = event.text or ""
    
    # Команды — прямое обращение
    if text.startswith('/'):
        return True
    
    # Реплай на сообщение бота — прямое обращение
    if event.reply_to_message:
        if (
            event.reply_to_message.from_user
            and event.reply_to_message.from_user.id == event.bot.id
        ):
            return True
    
    # Упоминание бота через @ — прямое обращение
    if event.entities and text and event.bot._me:
        bot_username = event.bot._me.username
        if bot_username and ("@" + bot_username) in text:
            return True
    
    # Упоминание "олег" в тексте — прямое обращение
    text_lower = text.lower()
    oleg_triggers = ["олег", "олега", "олегу", "олегом", "олеге", "oleg"]
    for trigger in oleg_triggers:
        if re.search(rf'\b{trigger}\b', text_lower):
            return True
    
    # Всё остальное (вопросы с ?, рандомные ответы) — НЕ прямое обращение
    # Бот сам решает отвечать, пользователь не спамит
    return False


class RateLimiter:
    """Rate limiter with Redis support and in-memory fallback."""
    
    def __init__(self, max_requests: int, window_seconds: int):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # In-memory fallback
        self.requests: Dict[int, deque] = defaultdict(deque)
        self._redis_client = None
    
    def set_redis_client(self, redis_client):
        """Set Redis client for distributed rate limiting."""
        self._redis_client = redis_client
        logger.info("Rate limiter configured to use Redis")
    
    async def is_allowed(self, user_id: int) -> bool:
        """
        Check if user is allowed to make a request.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if request is allowed, False otherwise
        """
        # Try Redis first
        if self._redis_client and self._redis_client.is_available:
            return await self._is_allowed_redis(user_id)
        
        # Fallback to in-memory
        return self._is_allowed_memory(user_id)
    
    async def _is_allowed_redis(self, user_id: int) -> bool:
        """Redis-based rate limiting."""
        key = f"rate_limit:{user_id}"
        
        try:
            # Get current count
            count = await self._redis_client.get(key)
            
            if count is None:
                # First request in window
                await self._redis_client.set(key, "1", ex=self.window_seconds)
                return True
            
            count = int(count)
            
            if count >= self.max_requests:
                return False
            
            # Increment counter
            await self._redis_client.incr(key)
            return True
            
        except Exception as e:
            logger.error(f"Redis rate limit error: {e}, falling back to memory")
            return self._is_allowed_memory(user_id)
    
    def _is_allowed_memory(self, user_id: int) -> bool:
        """In-memory rate limiting (fallback)."""
        now = time.time()
        user_requests = self.requests[user_id]
        
        # Remove old requests outside the window
        while user_requests and user_requests[0] < now - self.window_seconds:
            user_requests.popleft()
        
        # Check if user exceeded limit
        if len(user_requests) >= self.max_requests:
            return False
        
        # Add current request
        user_requests.append(now)
        return True
    
    async def get_remaining_time(self, user_id: int) -> int:
        """
        Get remaining time until user can make another request.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Seconds until next request is allowed
        """
        # Try Redis first
        if self._redis_client and self._redis_client.is_available:
            key = f"rate_limit:{user_id}"
            try:
                ttl = await self._redis_client.ttl(key)
                return max(0, ttl) if ttl and ttl > 0 else 0
            except Exception as e:
                logger.error(f"Redis TTL error: {e}")
        
        # Fallback to in-memory
        now = time.time()
        user_requests = self.requests[user_id]
        
        if not user_requests or len(user_requests) < self.max_requests:
            return 0
        
        oldest_request = user_requests[0]
        time_until_reset = int((oldest_request + self.window_seconds) - now)
        return max(0, time_until_reset)


# Global rate limiter instance
rate_limiter = RateLimiter(
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window
)


class RateLimitMiddleware(BaseMiddleware):
    """Middleware to enforce rate limiting on user requests."""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        """
        Process message with rate limiting.
        
        Args:
            handler: Next handler in chain
            event: Incoming message
            data: Handler data
            
        Returns:
            Handler result or None if rate limited
        """
        if not settings.rate_limit_enabled:
            return await handler(event, data)
        
        user_id = event.from_user.id
        
        # Skip rate limiting for bot owner
        if settings.owner_id and user_id == settings.owner_id:
            return await handler(event, data)
        
        # Skip rate limiting for non-direct requests (random responses, questions)
        # Rate limit only applies when user explicitly addresses the bot
        if not is_direct_bot_request(event):
            return await handler(event, data)
        
        # Check rate limit
        if not await rate_limiter.is_allowed(user_id):
            remaining_time = await rate_limiter.get_remaining_time(user_id)
            logger.warning(
                f"Rate limit exceeded for user {user_id} "
                f"(@{event.from_user.username}). "
                f"Retry in {remaining_time}s"
            )
            
            # Track rate limit hit
            try:
                from app.services.metrics import track_rate_limit_hit
                await track_rate_limit_hit(user_id)
            except Exception:
                pass  # Don't fail on metrics error
            
            try:
                await event.reply(
                    f"⏱ Слишком много запросов! "
                    f"Подожди {remaining_time} секунд, чемпион."
                )
            except Exception as e:
                logger.error(f"Failed to send rate limit message: {e}")
            
            return None
        
        return await handler(event, data)
