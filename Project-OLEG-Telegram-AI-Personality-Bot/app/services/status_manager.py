"""Status Notification Manager - Anti-Flood Status Notifications.

This module provides the Status Manager for preventing status message spam
during high activity periods by using reactions instead of messages.

**Feature: shield-economy-v65**
**Validates: Requirements 3.1, 3.2, 3.3**
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set

from app.services.redis_client import redis_client
from app.utils import utc_now

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Redis key prefix for processing state
REDIS_KEY_PREFIX = "processing:"

# Redis TTL for processing state (seconds)
REDIS_TTL = 300

# Reaction emoji for pending messages
PENDING_REACTION = "⏳"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ProcessingStatus:
    """
    Processing status for a chat.
    
    Attributes:
        chat_id: Telegram chat ID
        is_processing: Whether the chat is currently processing a request
        pending_messages: List of message IDs with pending reactions
        started_at: When processing started
    """
    chat_id: int
    is_processing: bool = False
    pending_messages: List[int] = field(default_factory=list)
    started_at: Optional[datetime] = None


# ============================================================================
# Status Manager Service
# ============================================================================

class StatusManager:
    """
    Service for managing status notifications to prevent flood.
    
    Provides methods for:
    - Starting processing state for a chat
    - Adding pending reactions to messages
    - Finishing processing and cleaning up
    - Checking if a chat is currently processing
    
    Uses Redis for state tracking with in-memory fallback.
    
    **Validates: Requirements 3.1, 3.2, 3.3**
    """
    
    def __init__(self):
        """Initialize StatusManager with in-memory fallback."""
        # In-memory state when Redis is unavailable
        self._processing_state: Dict[int, ProcessingStatus] = {}
    
    # =========================================================================
    # Redis Key Helpers
    # =========================================================================
    
    def _get_redis_key(self, chat_id: int) -> str:
        """Generate Redis key for chat processing state."""
        return f"{REDIS_KEY_PREFIX}{chat_id}"
    
    # =========================================================================
    # Core Status Methods
    # =========================================================================
    
    async def start_processing(
        self,
        chat_id: int,
        message_id: int
    ) -> bool:
        """
        Start processing state for a chat.
        
        If the chat is not already processing, marks it as processing
        and returns True (indicating a status notification should be sent).
        
        If already processing, returns False (no notification needed).
        
        Args:
            chat_id: Telegram chat ID
            message_id: ID of the message being processed
            
        Returns:
            True if this is the first request (send notification),
            False if already processing (add reaction instead)
            
        **Validates: Requirements 3.1, 3.2**
        """
        is_first = not await self.is_processing(chat_id)
        
        if is_first:
            # First request - start processing state
            status = ProcessingStatus(
                chat_id=chat_id,
                is_processing=True,
                pending_messages=[message_id],
                started_at=utc_now(),
            )
            await self._save_status(status)
            logger.debug(f"Started processing for chat {chat_id}")
            return True
        else:
            # Already processing - add to pending
            await self.add_pending_reaction(chat_id, message_id)
            return False
    
    async def add_pending_reaction(
        self,
        chat_id: int,
        message_id: int
    ) -> None:
        """
        Add a message to the pending reactions list.
        
        This message should receive a ⏳ reaction instead of a status notification.
        
        Args:
            chat_id: Telegram chat ID
            message_id: ID of the message to add reaction to
            
        **Validates: Requirements 3.1**
        """
        status = await self._get_status(chat_id)
        
        if message_id not in status.pending_messages:
            status.pending_messages.append(message_id)
            await self._save_status(status)
            logger.debug(f"Added pending reaction for message {message_id} in chat {chat_id}")
    
    async def finish_processing(
        self,
        chat_id: int
    ) -> List[int]:
        """
        Finish processing state for a chat.
        
        Returns the list of message IDs that had pending reactions
        (so reactions can be removed).
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            List of message IDs with pending reactions to remove
            
        **Validates: Requirements 3.3**
        """
        status = await self._get_status(chat_id)
        pending = status.pending_messages.copy()
        
        # Clear processing state
        status.is_processing = False
        status.pending_messages = []
        status.started_at = None
        await self._save_status(status)
        
        logger.debug(f"Finished processing for chat {chat_id}, {len(pending)} pending reactions")
        return pending
    
    async def is_processing(
        self,
        chat_id: int
    ) -> bool:
        """
        Check if a chat is currently processing a request.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            True if chat is processing, False otherwise
        """
        status = await self._get_status(chat_id)
        return status.is_processing
    
    async def get_pending_messages(
        self,
        chat_id: int
    ) -> List[int]:
        """
        Get list of messages with pending reactions.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            List of message IDs with pending reactions
        """
        status = await self._get_status(chat_id)
        return status.pending_messages.copy()
    
    def get_pending_reaction_emoji(self) -> str:
        """
        Get the emoji used for pending reactions.
        
        Returns:
            The ⏳ emoji
        """
        return PENDING_REACTION
    
    # =========================================================================
    # Private Helper Methods - Storage
    # =========================================================================
    
    async def _get_status(
        self,
        chat_id: int
    ) -> ProcessingStatus:
        """Get processing status from Redis or memory."""
        # Try Redis first
        if redis_client.is_available:
            redis_key = self._get_redis_key(chat_id)
            data = await redis_client.get_json(redis_key)
            if data:
                return self._deserialize_status(chat_id, data)
        
        # Fall back to memory
        if chat_id in self._processing_state:
            return self._processing_state[chat_id]
        
        # Return default status
        return ProcessingStatus(chat_id=chat_id)
    
    async def _save_status(
        self,
        status: ProcessingStatus
    ) -> None:
        """Save processing status to Redis and memory."""
        # Save to Redis
        if redis_client.is_available:
            redis_key = self._get_redis_key(status.chat_id)
            data = self._serialize_status(status)
            await redis_client.set_json(redis_key, data, ex=REDIS_TTL)
        
        # Save to memory
        self._processing_state[status.chat_id] = status
    
    def _serialize_status(self, status: ProcessingStatus) -> dict:
        """Serialize ProcessingStatus to dict for Redis storage."""
        return {
            "is_processing": status.is_processing,
            "pending_messages": status.pending_messages,
            "started_at": status.started_at.isoformat() if status.started_at else None,
        }
    
    def _deserialize_status(
        self,
        chat_id: int,
        data: dict
    ) -> ProcessingStatus:
        """Deserialize dict from Redis to ProcessingStatus."""
        started_at = None
        if data.get("started_at"):
            started_at = datetime.fromisoformat(data["started_at"])
        
        return ProcessingStatus(
            chat_id=chat_id,
            is_processing=data.get("is_processing", False),
            pending_messages=data.get("pending_messages", []),
            started_at=started_at,
        )
    
    def invalidate_cache(self, chat_id: int) -> None:
        """Invalidate cached status for a chat."""
        self._processing_state.pop(chat_id, None)


# Global service instance
status_manager = StatusManager()
