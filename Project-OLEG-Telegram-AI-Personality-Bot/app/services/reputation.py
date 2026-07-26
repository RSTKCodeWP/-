"""Reputation Service - Social Credit System.

This module provides the Reputation system for tracking user behavior
and applying consequences based on reputation score.

**Feature: fortress-update**
**Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8**
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import UserReputation, ReputationHistory, User
from app.database.session import get_session
from app.utils import utc_now

logger = logging.getLogger(__name__)


# ============================================================================
# Reputation Change Definitions
# ============================================================================

class ReputationChange(IntEnum):
    """
    Reputation change deltas for various events.
    
    Negative values decrease reputation, positive values increase it.
    
    **Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6**
    """
    WARNING = -50           # User receives a warning (Requirement 4.2)
    MUTE = -100             # User is muted (Requirement 4.3)
    MESSAGE_DELETED = -10   # User's message is deleted by moderation (Requirement 4.4)
    THANK_YOU = 5           # User receives a "thank you" reaction (Requirement 4.5)
    TOURNAMENT_WIN = 20     # User wins a tournament (Requirement 4.6)


# ============================================================================
# Reputation Thresholds
# ============================================================================

# Initial reputation score for new users (Requirement 4.1)
INITIAL_REPUTATION = 1000

# Threshold below which user becomes read-only (Requirement 4.7)
READ_ONLY_THRESHOLD = 200

# Threshold above which user exits read-only mode (Requirement 4.7)
READ_ONLY_RECOVERY_THRESHOLD = 300


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ReputationStatus:
    """
    Current reputation status for a user.
    
    Attributes:
        user_id: Telegram user ID
        chat_id: Telegram chat ID
        score: Current reputation score
        is_read_only: Whether user is in read-only mode
        recent_changes: List of recent reputation changes (datetime, delta, reason)
    """
    user_id: int
    chat_id: int
    score: int = INITIAL_REPUTATION
    is_read_only: bool = False
    recent_changes: List[Tuple[datetime, int, str]] = field(default_factory=list)


# ============================================================================
# Reputation Service
# ============================================================================

class ReputationService:
    """
    Service for managing user reputation scores.
    
    Provides methods for:
    - Getting and modifying reputation scores
    - Initializing new users with default reputation
    - Checking and updating read-only status
    - Tracking reputation history
    
    **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8**
    """
    
    def __init__(self):
        """Initialize ReputationService with in-memory cache."""
        # In-memory cache for reputation scores (reduces DB queries)
        self._cache: Dict[Tuple[int, int], ReputationStatus] = {}
        self._cache_ttl: Dict[Tuple[int, int], datetime] = {}
        self._cache_duration = timedelta(minutes=5)
    
    # =========================================================================
    # Core Reputation Methods
    # =========================================================================
    
    async def get_reputation(
        self,
        user_id: int,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> ReputationStatus:
        """
        Get reputation status for a user in a chat.
        
        If no reputation record exists, returns default status (score=1000).
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            session: Optional database session
            
        Returns:
            ReputationStatus with current score and status
        """
        cache_key = (user_id, chat_id)
        
        # Check cache first
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        # Load from database
        status = await self._load_from_db(user_id, chat_id, session)
        
        # Cache the result
        self._cache[cache_key] = status
        self._cache_ttl[cache_key] = utc_now()
        
        return status
    
    async def modify_reputation(
        self,
        user_id: int,
        chat_id: int,
        change: int,
        reason: str,
        session: Optional[AsyncSession] = None
    ) -> ReputationStatus:
        """
        Modify a user's reputation score.
        
        Updates the score, checks read-only thresholds, and logs the change.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            change: Amount to change (positive or negative)
            reason: Reason for the change
            session: Optional database session
            
        Returns:
            Updated ReputationStatus
        """
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            # Get or create reputation record
            result = await session.execute(
                select(UserReputation).filter_by(user_id=user_id, chat_id=chat_id)
            )
            db_record = result.scalar_one_or_none()
            
            if db_record is None:
                # Initialize new user
                db_record = UserReputation(
                    user_id=user_id,
                    chat_id=chat_id,
                    score=INITIAL_REPUTATION,
                    is_read_only=False
                )
                session.add(db_record)
            
            # Calculate new score
            old_score = db_record.score
            new_score = old_score + change
            
            # Ensure score doesn't go below 0
            new_score = max(0, new_score)
            
            # Update score
            db_record.score = new_score
            db_record.last_change_at = utc_now()
            
            # Check and update read-only status
            db_record.is_read_only = self._calculate_read_only_status(
                new_score, db_record.is_read_only
            )
            
            # Log the change in history
            history_entry = ReputationHistory(
                user_id=user_id,
                chat_id=chat_id,
                change_amount=change,
                reason=reason
            )
            session.add(history_entry)
            
            # Sync global User.reputation_score (average across all chats)
            await self._sync_global_reputation(user_id, session)
            
            await session.commit()
            
            # Update cache
            status = ReputationStatus(
                user_id=user_id,
                chat_id=chat_id,
                score=new_score,
                is_read_only=db_record.is_read_only,
                recent_changes=[(utc_now(), change, reason)]
            )
            
            cache_key = (user_id, chat_id)
            self._cache[cache_key] = status
            self._cache_ttl[cache_key] = utc_now()
            
            logger.info(
                f"Reputation changed for user {user_id} in chat {chat_id}: "
                f"{old_score} -> {new_score} ({change:+d}) - {reason}"
            )
            
            return status
            
        finally:
            if close_session:
                await session.close()
    
    async def initialize_user(
        self,
        user_id: int,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> ReputationStatus:
        """
        Initialize a new user with default reputation score.
        
        Creates a new reputation record with score=1000 if one doesn't exist.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            session: Optional database session
            
        Returns:
            ReputationStatus with initial score (1000)
            
        **Validates: Requirements 4.1**
        """
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            # Check if record already exists
            result = await session.execute(
                select(UserReputation).filter_by(user_id=user_id, chat_id=chat_id)
            )
            db_record = result.scalar_one_or_none()
            
            if db_record is not None:
                # User already initialized, return current status
                return ReputationStatus(
                    user_id=user_id,
                    chat_id=chat_id,
                    score=db_record.score,
                    is_read_only=db_record.is_read_only
                )
            
            # Create new record with initial score
            db_record = UserReputation(
                user_id=user_id,
                chat_id=chat_id,
                score=INITIAL_REPUTATION,
                is_read_only=False
            )
            session.add(db_record)
            await session.commit()
            
            # Create status
            status = ReputationStatus(
                user_id=user_id,
                chat_id=chat_id,
                score=INITIAL_REPUTATION,
                is_read_only=False
            )
            
            # Update cache
            cache_key = (user_id, chat_id)
            self._cache[cache_key] = status
            self._cache_ttl[cache_key] = utc_now()
            
            logger.info(f"Initialized reputation for user {user_id} in chat {chat_id}")
            
            return status
            
        finally:
            if close_session:
                await session.close()
    
    # =========================================================================
    # Read-Only Status Methods
    # =========================================================================
    # Global Reputation Sync
    # =========================================================================
    
    async def _sync_global_reputation(
        self,
        user_id: int,
        session: AsyncSession
    ) -> None:
        """
        Sync User.reputation_score with average from UserReputation.
        
        This keeps the global reputation_score in User model updated
        based on the average reputation across all chats.
        """
        try:
            # Calculate average reputation across all chats
            result = await session.execute(
                select(func.avg(UserReputation.score))
                .where(UserReputation.user_id == user_id)
            )
            avg_score = result.scalar()
            
            if avg_score is not None:
                # Update User.reputation_score
                user = await session.scalar(
                    select(User).where(User.tg_user_id == user_id)
                )
                if user:
                    user.reputation_score = int(avg_score)
                    logger.debug(f"Synced global reputation for user {user_id}: {int(avg_score)}")
        except Exception as e:
            logger.warning(f"Failed to sync global reputation for user {user_id}: {e}")
    
    # =========================================================================
    # Read-Only Status Methods
    # =========================================================================
    
    async def check_read_only_status(
        self,
        user_id: int,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> bool:
        """
        Check if a user is in read-only mode.
        
        A user is read-only if their reputation is below 200.
        They exit read-only mode when reputation recovers above 300.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            session: Optional database session
            
        Returns:
            True if user is in read-only mode
            
        **Validates: Requirements 4.7**
        """
        status = await self.get_reputation(user_id, chat_id, session)
        return status.is_read_only
    
    def _calculate_read_only_status(
        self,
        score: int,
        current_is_read_only: bool
    ) -> bool:
        """
        Calculate read-only status based on score and current status.
        
        Uses hysteresis to prevent rapid toggling:
        - Becomes read-only when score drops below 200
        - Exits read-only when score rises above 300
        
        Args:
            score: Current reputation score
            current_is_read_only: Current read-only status
            
        Returns:
            New read-only status
        """
        if current_is_read_only:
            # Currently read-only: exit only if score > 300
            return score <= READ_ONLY_RECOVERY_THRESHOLD
        else:
            # Currently not read-only: become read-only if score < 200
            return score < READ_ONLY_THRESHOLD
    
    # =========================================================================
    # Convenience Methods for Common Actions
    # =========================================================================
    
    async def apply_warning(
        self,
        user_id: int,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> ReputationStatus:
        """
        Apply reputation penalty for a warning.
        
        **Validates: Requirements 4.2**
        """
        return await self.modify_reputation(
            user_id, chat_id,
            change=ReputationChange.WARNING,
            reason="warning",
            session=session
        )
    
    async def apply_mute(
        self,
        user_id: int,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> ReputationStatus:
        """
        Apply reputation penalty for a mute.
        
        **Validates: Requirements 4.3**
        """
        return await self.modify_reputation(
            user_id, chat_id,
            change=ReputationChange.MUTE,
            reason="mute",
            session=session
        )
    
    async def apply_message_deleted(
        self,
        user_id: int,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> ReputationStatus:
        """
        Apply reputation penalty for message deletion.
        
        **Validates: Requirements 4.4**
        """
        return await self.modify_reputation(
            user_id, chat_id,
            change=ReputationChange.MESSAGE_DELETED,
            reason="message_deleted",
            session=session
        )
    
    async def apply_thank_you(
        self,
        user_id: int,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> ReputationStatus:
        """
        Apply reputation bonus for receiving a thank you reaction.
        
        **Validates: Requirements 4.5**
        """
        return await self.modify_reputation(
            user_id, chat_id,
            change=ReputationChange.THANK_YOU,
            reason="thank_you_reaction",
            session=session
        )
    
    async def apply_tournament_win(
        self,
        user_id: int,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> ReputationStatus:
        """
        Apply reputation bonus for winning a tournament.
        
        **Validates: Requirements 4.6**
        """
        return await self.modify_reputation(
            user_id, chat_id,
            change=ReputationChange.TOURNAMENT_WIN,
            reason="tournament_win",
            session=session
        )
    
    # =========================================================================
    # History Methods
    # =========================================================================
    
    async def get_recent_changes(
        self,
        user_id: int,
        chat_id: int,
        limit: int = 10,
        session: Optional[AsyncSession] = None
    ) -> List[Tuple[datetime, int, str]]:
        """
        Get recent reputation changes for a user.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            limit: Maximum number of changes to return
            session: Optional database session
            
        Returns:
            List of (datetime, change_amount, reason) tuples
            
        **Validates: Requirements 4.8**
        """
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            result = await session.execute(
                select(ReputationHistory)
                .filter_by(user_id=user_id, chat_id=chat_id)
                .order_by(ReputationHistory.created_at.desc())
                .limit(limit)
            )
            history = result.scalars().all()
            
            return [
                (entry.created_at, entry.change_amount, entry.reason)
                for entry in history
            ]
            
        finally:
            if close_session:
                await session.close()
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _is_cache_valid(self, cache_key: Tuple[int, int]) -> bool:
        """Check if cached status is still valid."""
        if cache_key not in self._cache:
            return False
        
        cache_time = self._cache_ttl.get(cache_key)
        if cache_time is None:
            return False
        
        return (utc_now() - cache_time) < self._cache_duration
    
    async def _load_from_db(
        self,
        user_id: int,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> ReputationStatus:
        """Load reputation status from database."""
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            result = await session.execute(
                select(UserReputation).filter_by(user_id=user_id, chat_id=chat_id)
            )
            db_record = result.scalar_one_or_none()
            
            if db_record is None:
                # Return default status (not yet initialized)
                return ReputationStatus(
                    user_id=user_id,
                    chat_id=chat_id,
                    score=INITIAL_REPUTATION,
                    is_read_only=False
                )
            
            # Load recent changes
            history_result = await session.execute(
                select(ReputationHistory)
                .filter_by(user_id=user_id, chat_id=chat_id)
                .order_by(ReputationHistory.created_at.desc())
                .limit(5)
            )
            history = history_result.scalars().all()
            
            recent_changes = [
                (entry.created_at, entry.change_amount, entry.reason)
                for entry in history
            ]
            
            return ReputationStatus(
                user_id=user_id,
                chat_id=chat_id,
                score=db_record.score,
                is_read_only=db_record.is_read_only,
                recent_changes=recent_changes
            )
            
        finally:
            if close_session:
                await session.close()
    
    def invalidate_cache(self, user_id: int, chat_id: int) -> None:
        """Invalidate cached status for a user."""
        cache_key = (user_id, chat_id)
        self._cache.pop(cache_key, None)
        self._cache_ttl.pop(cache_key, None)


# Global service instance
reputation_service = ReputationService()
