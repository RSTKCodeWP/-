"""User-related business logic."""
import logging
from typing import Optional
from database import Database, User

logger = logging.getLogger(__name__)


class UserService:
    """Service for user operations."""
    
    def __init__(self, db: Database):
        self.db = db
    
    async def get_or_create_user(self, user_id: int) -> User:
        """Get existing user or create a new one."""
        return await self.db.get_or_create_user(user_id)
    
    async def update_language(self, user_id: int, language: str) -> bool:
        """
        Update user's language preference.
        
        Args:
            user_id: Telegram user ID
            language: Language code ('ru' or 'en')
            
        Returns:
            True if successful
        """
        try:
            await self.db.update_user_language(user_id, language)
            logger.info(f"Updated language for user {user_id} to {language}")
            return True
        except Exception as e:
            logger.error(f"Failed to update language for user {user_id}: {e}")
            return False
    
    async def update_trader_levels(self, user_id: int, trader_levels: dict) -> bool:
        """
        Update user's trader loyalty levels.
        
        Args:
            user_id: Telegram user ID
            trader_levels: Dictionary with trader levels
            
        Returns:
            True if successful
        """
        try:
            await self.db.update_trader_levels(user_id, trader_levels)
            logger.info(f"Updated trader levels for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update trader levels for user {user_id}: {e}")
            return False
    
    async def get_trader_level(self, user_id: int, trader_name: str) -> int:
        """
        Get user's loyalty level for a specific trader.
        
        Args:
            user_id: Telegram user ID
            trader_name: Trader name (lowercase)
            
        Returns:
            Loyalty level (1-4)
        """
        user = await self.db.get_user(user_id)
        if not user or not user.trader_levels:
            return 1
        
        return user.trader_levels.get(trader_name.lower(), 1)
