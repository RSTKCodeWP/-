"""Energy Limiter Service - Personal Cooldown System.

This module provides the Energy Limiter system for managing user request limits
to conserve LLM tokens through a personal cooldown mechanism.

**Feature: shield-economy-v65**
**Validates: Requirements 1.1, 1.2, 1.3, 1.4**
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import UserEnergy
from app.database.session import get_session
from app.services.redis_client import redis_client
from app.utils import utc_now

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Maximum energy a user can have
MAX_ENERGY = 3

# Time window for rapid requests (seconds)
RAPID_REQUEST_WINDOW = 10

# Cooldown duration when energy reaches 0 (seconds)
COOLDOWN_DURATION = 60

# Inactivity period after which energy resets (seconds)
INACTIVITY_RESET_PERIOD = 60

# Redis key prefix for energy data
REDIS_KEY_PREFIX = "energy:"

# Redis TTL for energy data (seconds) - longer than cooldown to persist state
REDIS_TTL = 300


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class EnergyStatus:
    """
    Current energy status for a user.
    
    Attributes:
        user_id: Telegram user ID
        chat_id: Telegram chat ID
        energy: Current energy level (0-3)
        last_request: Timestamp of last request
        cooldown_until: Timestamp when cooldown ends (if in cooldown)
        can_proceed: Whether the user can make a request
        cooldown_message: Message to show if in cooldown
    """
    user_id: int
    chat_id: int
    energy: int = MAX_ENERGY
    last_request: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    can_proceed: bool = True
    cooldown_message: Optional[str] = None


# ============================================================================
# Energy Limiter Service
# ============================================================================

class EnergyLimiterService:
    """
    Service for managing user energy and cooldowns.
    
    Provides methods for:
    - Checking if a user has energy to make a request
    - Consuming energy on rapid requests
    - Resetting energy after inactivity
    - Getting cooldown remaining time
    
    Uses Redis for fast access with database fallback.
    
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
    """
    
    def __init__(self):
        """Initialize EnergyLimiterService with in-memory fallback cache."""
        # In-memory fallback when Redis is unavailable
        self._memory_cache: Dict[Tuple[int, int], EnergyStatus] = {}
    
    # =========================================================================
    # Redis Key Helpers
    # =========================================================================
    
    def _get_redis_key(self, user_id: int, chat_id: int) -> str:
        """Generate Redis key for user energy data."""
        return f"{REDIS_KEY_PREFIX}{user_id}:{chat_id}"
    
    # =========================================================================
    # Core Energy Methods
    # =========================================================================
    
    async def check_energy(
        self,
        user_id: int,
        chat_id: int,
        user_mention: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a user has energy to make a request.
        
        This method:
        1. Loads current energy state
        2. Checks if user is in cooldown
        3. Checks if energy needs to be reset due to inactivity
        4. Returns whether the request can proceed
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            user_mention: User mention string for cooldown message
            
        Returns:
            Tuple of (can_proceed, cooldown_message)
            - can_proceed: True if user has energy
            - cooldown_message: Message to show if in cooldown, None otherwise
            
        **Validates: Requirements 1.2, 1.3, 1.4**
        """
        now = utc_now()
        status = await self._get_energy_status(user_id, chat_id)
        
        # Check if in cooldown
        if status.cooldown_until and status.cooldown_until > now:
            remaining = int((status.cooldown_until - now).total_seconds())
            message = self._format_cooldown_message(user_mention, remaining)
            return False, message
        
        # Check if energy should be reset due to inactivity (Requirement 1.3)
        if status.last_request:
            time_since_last = (now - status.last_request).total_seconds()
            if time_since_last >= INACTIVITY_RESET_PERIOD:
                # Reset energy after inactivity
                await self.reset_energy(user_id, chat_id)
                return True, None
        
        # Check if user has energy (Requirement 1.4)
        if status.energy > 0:
            return True, None
        
        # No energy and not in cooldown - this shouldn't happen normally
        # but handle it by putting user in cooldown
        await self._set_cooldown(user_id, chat_id, now)
        remaining = COOLDOWN_DURATION
        message = self._format_cooldown_message(user_mention, remaining)
        return False, message
    
    async def consume_energy(
        self,
        user_id: int,
        chat_id: int,
        user_mention: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Consume energy for a user request.
        
        This method should be called after check_energy() returns True.
        It decrements energy if the request is within the rapid request window.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            user_mention: User mention string for cooldown message
            
        Returns:
            Tuple of (success, cooldown_message)
            - success: True if energy was consumed successfully
            - cooldown_message: Message if user entered cooldown, None otherwise
            
        **Validates: Requirements 1.1, 1.2**
        """
        now = utc_now()
        status = await self._get_energy_status(user_id, chat_id)
        
        # Check if this is a rapid request (within 10 seconds of last request)
        is_rapid = False
        if status.last_request:
            time_since_last = (now - status.last_request).total_seconds()
            is_rapid = time_since_last < RAPID_REQUEST_WINDOW
        
        # Update last request time
        status.last_request = now
        
        if is_rapid and status.energy > 0:
            # Decrement energy on rapid request (Requirement 1.1)
            status.energy -= 1
            logger.debug(
                f"Energy decremented for user {user_id} in chat {chat_id}: "
                f"{status.energy + 1} -> {status.energy}"
            )
            
            if status.energy == 0:
                # Enter cooldown (Requirement 1.2)
                status.cooldown_until = now + timedelta(seconds=COOLDOWN_DURATION)
                await self._save_energy_status(status)
                message = self._format_cooldown_message(user_mention, COOLDOWN_DURATION)
                return True, message
        
        # Save updated status
        await self._save_energy_status(status)
        return True, None
    
    async def reset_energy(
        self,
        user_id: int,
        chat_id: int
    ) -> None:
        """
        Reset a user's energy to maximum.
        
        Called after inactivity period or manually by admin.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            
        **Validates: Requirements 1.3**
        """
        status = EnergyStatus(
            user_id=user_id,
            chat_id=chat_id,
            energy=MAX_ENERGY,
            last_request=None,
            cooldown_until=None,
            can_proceed=True
        )
        await self._save_energy_status(status)
        logger.debug(f"Energy reset for user {user_id} in chat {chat_id}")
    
    async def get_cooldown_remaining(
        self,
        user_id: int,
        chat_id: int
    ) -> int:
        """
        Get remaining cooldown time in seconds.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            
        Returns:
            Remaining cooldown time in seconds, 0 if not in cooldown
        """
        status = await self._get_energy_status(user_id, chat_id)
        
        if not status.cooldown_until:
            return 0
        
        now = utc_now()
        if status.cooldown_until <= now:
            return 0
        
        return int((status.cooldown_until - now).total_seconds())
    
    async def get_energy(
        self,
        user_id: int,
        chat_id: int
    ) -> int:
        """
        Get current energy level for a user.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            
        Returns:
            Current energy level (0-3)
        """
        status = await self._get_energy_status(user_id, chat_id)
        return status.energy

    
    # =========================================================================
    # Cooldown Message Formatting
    # =========================================================================
    
    def _format_cooldown_message(
        self,
        user_mention: str,
        remaining_seconds: int
    ) -> str:
        """
        Format the cooldown message for a user.
        
        The message contains the user's mention and wait instruction.
        
        Args:
            user_mention: User mention string (e.g., "@username" or "[Name](tg://user?id=123)")
            remaining_seconds: Remaining cooldown time in seconds
            
        Returns:
            Formatted cooldown message
            
        **Validates: Requirements 1.2**
        """
        if not user_mention:
            user_mention = "Пользователь"
        
        return (
            f"{user_mention}, подожди {remaining_seconds} секунд перед следующим запросом. "
            f"Энергия восстановится после паузы."
        )
    
    # =========================================================================
    # Private Helper Methods - Storage
    # =========================================================================
    
    async def _get_energy_status(
        self,
        user_id: int,
        chat_id: int
    ) -> EnergyStatus:
        """
        Get energy status from Redis or database.
        
        Priority: Redis -> Memory Cache -> Database -> Default
        """
        cache_key = (user_id, chat_id)
        
        # Try Redis first
        if redis_client.is_available:
            redis_key = self._get_redis_key(user_id, chat_id)
            data = await redis_client.get_json(redis_key)
            if data:
                return self._deserialize_status(user_id, chat_id, data)
        
        # Try memory cache
        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]
        
        # Load from database
        status = await self._load_from_db(user_id, chat_id)
        
        # Cache in memory
        self._memory_cache[cache_key] = status
        
        return status
    
    async def _save_energy_status(
        self,
        status: EnergyStatus
    ) -> None:
        """
        Save energy status to Redis and database.
        """
        cache_key = (status.user_id, status.chat_id)
        
        # Save to Redis
        if redis_client.is_available:
            redis_key = self._get_redis_key(status.user_id, status.chat_id)
            data = self._serialize_status(status)
            await redis_client.set_json(redis_key, data, ex=REDIS_TTL)
        
        # Update memory cache
        self._memory_cache[cache_key] = status
        
        # Save to database (async, for persistence)
        await self._save_to_db(status)
    
    def _serialize_status(self, status: EnergyStatus) -> dict:
        """Serialize EnergyStatus to dict for Redis storage."""
        return {
            "energy": status.energy,
            "last_request": status.last_request.isoformat() if status.last_request else None,
            "cooldown_until": status.cooldown_until.isoformat() if status.cooldown_until else None,
        }
    
    def _deserialize_status(
        self,
        user_id: int,
        chat_id: int,
        data: dict
    ) -> EnergyStatus:
        """Deserialize dict from Redis to EnergyStatus."""
        last_request = None
        if data.get("last_request"):
            last_request = datetime.fromisoformat(data["last_request"])
        
        cooldown_until = None
        if data.get("cooldown_until"):
            cooldown_until = datetime.fromisoformat(data["cooldown_until"])
        
        return EnergyStatus(
            user_id=user_id,
            chat_id=chat_id,
            energy=data.get("energy", MAX_ENERGY),
            last_request=last_request,
            cooldown_until=cooldown_until,
        )
    
    async def _load_from_db(
        self,
        user_id: int,
        chat_id: int
    ) -> EnergyStatus:
        """Load energy status from database."""
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(UserEnergy).filter_by(user_id=user_id, chat_id=chat_id)
            )
            db_record = result.scalar_one_or_none()
            
            if db_record is None:
                # Return default status
                return EnergyStatus(
                    user_id=user_id,
                    chat_id=chat_id,
                    energy=MAX_ENERGY,
                    last_request=None,
                    cooldown_until=None,
                )
            
            return EnergyStatus(
                user_id=user_id,
                chat_id=chat_id,
                energy=db_record.energy,
                last_request=db_record.last_request,
                cooldown_until=db_record.cooldown_until,
            )
    
    async def _save_to_db(
        self,
        status: EnergyStatus
    ) -> None:
        """Save energy status to database."""
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(UserEnergy).filter_by(
                    user_id=status.user_id,
                    chat_id=status.chat_id
                )
            )
            db_record = result.scalar_one_or_none()
            
            if db_record is None:
                # Create new record
                db_record = UserEnergy(
                    user_id=status.user_id,
                    chat_id=status.chat_id,
                    energy=status.energy,
                    last_request=status.last_request,
                    cooldown_until=status.cooldown_until,
                )
                session.add(db_record)
            else:
                # Update existing record
                db_record.energy = status.energy
                db_record.last_request = status.last_request
                db_record.cooldown_until = status.cooldown_until
            
            await session.commit()
    
    async def _set_cooldown(
        self,
        user_id: int,
        chat_id: int,
        now: datetime
    ) -> None:
        """Set cooldown for a user."""
        status = await self._get_energy_status(user_id, chat_id)
        status.energy = 0
        status.cooldown_until = now + timedelta(seconds=COOLDOWN_DURATION)
        await self._save_energy_status(status)
    
    def invalidate_cache(self, user_id: int, chat_id: int) -> None:
        """Invalidate cached status for a user."""
        cache_key = (user_id, chat_id)
        self._memory_cache.pop(cache_key, None)


# Global service instance
energy_limiter_service = EnergyLimiterService()
