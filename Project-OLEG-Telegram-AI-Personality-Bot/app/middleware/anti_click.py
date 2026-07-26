"""Anti-Click middleware for protecting game buttons from unauthorized users.

Verifies that callback.from_user.id matches the game owner's ID.
Requirements: 3.1, 3.2, 3.3, 3.4
"""

import logging
from typing import Callable, Awaitable, Dict, Any, Optional

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery

logger = logging.getLogger(__name__)


class AntiClickMiddleware(BaseMiddleware):
    """Middleware to protect game buttons from non-owner clicks.
    
    Checks if the user clicking a game button is the owner of that game session.
    If not, shows an alert and blocks the action.
    """
    
    # Callback data prefixes that should be protected
    GAME_PREFIXES = ["game:", "bj:", "duel:", "roulette:", "coinflip:", "grow:"]
    
    # Alert message for non-owners
    ALERT_MESSAGE = "⚠️ Это не твоя кнопка, сталкер! Иди создай свою игру."
    
    def __init__(self, state_manager=None):
        """Initialize AntiClickMiddleware.
        
        Args:
            state_manager: StateManager instance for session lookups.
                          If None, will try to import global instance.
        """
        self._state_manager = state_manager
        super().__init__()
    
    def _get_state_manager(self):
        """Get state manager instance (lazy loading)."""
        if self._state_manager is None:
            try:
                from app.services.state_manager import state_manager
                self._state_manager = state_manager
            except ImportError:
                logger.warning("Could not import state_manager")
        return self._state_manager
    
    def _is_game_callback(self, callback_data: Optional[str]) -> bool:
        """Check if callback data is for a game action.
        
        Args:
            callback_data: The callback_data string from the button
            
        Returns:
            True if this is a game-related callback
        """
        if not callback_data:
            return False
        return any(callback_data.startswith(prefix) for prefix in self.GAME_PREFIXES)
    
    def _extract_owner_id(self, callback_data: str) -> Optional[int]:
        """Extract owner ID from callback data if present.
        
        Callback format: prefix:owner_id:action or prefix:owner_id:action:data
        Example: bj:123456789:hit
        
        Args:
            callback_data: The callback_data string
            
        Returns:
            Owner ID if found, None otherwise
        """
        try:
            parts = callback_data.split(":")
            if len(parts) >= 2:
                # Second part should be owner_id
                return int(parts[1])
        except (ValueError, IndexError):
            pass
        return None
    
    async def __call__(
        self,
        handler: Callable[[CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        """Process callback with anti-click protection.
        
        Args:
            handler: Next handler in chain
            event: Incoming callback query
            data: Handler data
            
        Returns:
            Handler result or None if blocked
        """
        callback_data = event.data
        
        # Only check game-related callbacks
        if not self._is_game_callback(callback_data):
            return await handler(event, data)
        
        # Get the user who clicked
        clicker_id = event.from_user.id
        
        # Try to extract owner ID from callback data
        owner_id = self._extract_owner_id(callback_data)
        
        if owner_id is not None:
            # Owner ID is in callback data - direct comparison
            if clicker_id != owner_id:
                logger.warning(
                    f"Anti-click blocked: user {clicker_id} tried to click "
                    f"button owned by {owner_id}"
                )
                await event.answer(self.ALERT_MESSAGE, show_alert=True)
                return None
        else:
            # Fallback: check state manager for session ownership
            state_manager = self._get_state_manager()
            if state_manager:
                chat_id = event.message.chat.id if event.message else None
                message_id = event.message.message_id if event.message else None
                
                if chat_id and message_id:
                    session = await state_manager.get_session_by_message(
                        chat_id, message_id
                    )
                    if session and session.user_id != clicker_id:
                        logger.warning(
                            f"Anti-click blocked: user {clicker_id} tried to click "
                            f"button owned by {session.user_id}"
                        )
                        await event.answer(self.ALERT_MESSAGE, show_alert=True)
                        return None
        
        # Owner verified or no owner info - proceed
        return await handler(event, data)


def verify_owner(callback: CallbackQuery, owner_id: int) -> bool:
    """Utility function to verify callback owner.
    
    Can be used directly in handlers for additional verification.
    
    Args:
        callback: The callback query
        owner_id: Expected owner ID
        
    Returns:
        True if callback sender matches owner
    """
    return callback.from_user.id == owner_id


async def reject_non_owner(callback: CallbackQuery) -> None:
    """Send rejection alert to non-owner.
    
    Args:
        callback: The callback query to respond to
    """
    await callback.answer(
        AntiClickMiddleware.ALERT_MESSAGE,
        show_alert=True
    )
