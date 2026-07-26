"""Retry middleware for handling Telegram network errors."""

import asyncio
import logging
import random
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter, TelegramBadRequest

logger = logging.getLogger(__name__)

# Errors that should be silently ignored (not retried, not logged as errors)
SILENT_ERRORS = [
    "query is too old",
    "query id is invalid",
    "message is not modified",
    "message to edit not found",
    "message can't be edited",
]


class RetryMiddleware(BaseMiddleware):
    """
    Middleware that automatically retries failed requests due to network errors.
    
    Handles:
    - TelegramNetworkError (ServerDisconnectedError, timeouts, etc.)
    - TelegramRetryAfter (rate limiting)
    - TelegramBadRequest (silently ignores stale queries)
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
    ):
        """
        Initialize retry middleware.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay between retries (seconds)
            max_delay: Maximum delay between retries (seconds)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    def _is_silent_error(self, error_message: str) -> bool:
        """Check if error should be silently ignored."""
        error_lower = error_message.lower()
        return any(silent in error_lower for silent in SILENT_ERRORS)
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Process event with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await handler(event, data)
            
            except TelegramBadRequest as e:
                # Check if this is a "stale query" error - silently ignore
                if self._is_silent_error(str(e)):
                    logger.debug(f"[RETRY] Silently ignoring: {e}")
                    return None
                # Other bad requests should propagate
                raise
            
            except TelegramRetryAfter as e:
                # Telegram rate limiting - wait the specified time
                wait_time = e.retry_after
                logger.warning(
                    f"[RETRY] Rate limited, waiting {wait_time}s "
                    f"(attempt {attempt + 1}/{self.max_retries + 1})"
                )
                await asyncio.sleep(wait_time)
                last_exception = e
                
            except TelegramNetworkError as e:
                last_exception = e
                
                if attempt >= self.max_retries:
                    logger.error(
                        f"[RETRY] Max retries ({self.max_retries}) exceeded: {e}"
                    )
                    raise
                
                # Exponential backoff with jitter
                delay = min(
                    self.base_delay * (2 ** attempt),
                    self.max_delay
                )
                # Add small random jitter (0-20%)
                delay *= (1 + random.random() * 0.2)
                
                logger.warning(
                    f"[RETRY] Network error: {type(e).__name__}, "
                    f"retrying in {delay:.1f}s "
                    f"(attempt {attempt + 1}/{self.max_retries + 1})"
                )
                await asyncio.sleep(delay)
        
        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
