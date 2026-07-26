"""State Manager for tracking active game sessions.

Implements Redis-based session storage with in-memory fallback.
Requirements: 2.1, 2.2, 2.3, 2.4
"""

import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Session timeout in seconds (30 minutes)
SESSION_TIMEOUT = 1800

# Supported game types
GAME_TYPES = frozenset({
    "blackjack", "duel", "roulette", "coinflip", "grow",
    # v7.5 new games
    "fish", "crash", "dice", "guess", "war", "wheel", "loot", "cockfight"
})


@dataclass
class SerializableGameState:
    """Serializable game state for Redis storage.
    
    Supports all game types: blackjack, duel, roulette, coinflip, grow.
    Requirements: 16.1, 16.2, 16.3
    """
    game_type: str
    user_id: int
    chat_id: int
    message_id: int
    data: Dict[str, Any]
    created_at: str  # ISO format string
    
    def __post_init__(self):
        """Validate game_type after initialization."""
        if self.game_type not in GAME_TYPES:
            logger.warning(f"Unknown game type: {self.game_type}")
    
    def to_json(self) -> str:
        """Serialize game state to JSON string.
        
        Returns:
            JSON string representation of the game state.
        """
        return json.dumps(asdict(self), ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'SerializableGameState':
        """Deserialize game state from JSON string.
        
        Args:
            json_str: JSON string to deserialize.
            
        Returns:
            SerializableGameState instance.
            
        Raises:
            json.JSONDecodeError: If JSON is invalid.
            TypeError: If required fields are missing.
        """
        data = json.loads(json_str)
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.
        
        Returns:
            Dictionary representation of the game state.
        """
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SerializableGameState':
        """Create from dictionary.
        
        Args:
            data: Dictionary with game state fields.
            
        Returns:
            SerializableGameState instance.
        """
        return cls(**data)
    
    def __eq__(self, other: object) -> bool:
        """Check equality with another SerializableGameState."""
        if not isinstance(other, SerializableGameState):
            return NotImplemented
        return (
            self.game_type == other.game_type
            and self.user_id == other.user_id
            and self.chat_id == other.chat_id
            and self.message_id == other.message_id
            and self.data == other.data
            and self.created_at == other.created_at
        )


@dataclass
class GameSession:
    """Represents an active game session."""
    user_id: int
    chat_id: int
    game_type: str
    started_at: str  # ISO format string for JSON serialization
    message_id: int
    state: Dict[str, Any] = field(default_factory=dict)
    
    def to_json(self) -> str:
        """Serialize session to JSON."""
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, json_str: str) -> 'GameSession':
        """Deserialize session from JSON."""
        data = json.loads(json_str)
        return cls(**data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GameSession':
        """Create session from dictionary."""
        return cls(**data)


class StateManager:
    """Manages active game sessions with Redis storage and in-memory fallback.
    
    Key format: game_session:{user_id}:{chat_id}
    """
    
    KEY_PREFIX = "game_session"
    
    def __init__(self, redis_client=None):
        """Initialize StateManager.
        
        Args:
            redis_client: Optional RedisClient instance. If None, uses in-memory storage.
        """
        self._redis_client = redis_client
        self._memory_store: Dict[str, GameSession] = {}
    
    def _make_key(self, user_id: int, chat_id: int) -> str:
        """Generate Redis key for user/chat combination."""
        return f"{self.KEY_PREFIX}:{user_id}:{chat_id}"
    
    def set_redis_client(self, redis_client) -> None:
        """Set Redis client for distributed session storage."""
        self._redis_client = redis_client
        logger.info("StateManager configured to use Redis")

    async def register_game(
        self,
        user_id: int,
        chat_id: int,
        game_type: str,
        message_id: int,
        initial_state: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Register a new game session.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            game_type: Type of game (e.g., 'blackjack', 'duel', 'roulette')
            message_id: Message ID of the game UI
            initial_state: Optional initial game state
            
        Returns:
            True if registration successful, False if user already playing
        """
        # Check if user is already playing
        if await self.is_playing(user_id, chat_id):
            logger.warning(f"User {user_id} already playing in chat {chat_id}")
            return False
        
        session = GameSession(
            user_id=user_id,
            chat_id=chat_id,
            game_type=game_type,
            started_at=datetime.utcnow().isoformat(),
            message_id=message_id,
            state=initial_state or {}
        )
        
        key = self._make_key(user_id, chat_id)
        
        # Try Redis first
        if self._redis_client and self._redis_client.is_available:
            try:
                success = await self._redis_client.set(
                    key, session.to_json(), ex=SESSION_TIMEOUT
                )
                if success:
                    logger.info(f"Registered game {game_type} for user {user_id} in chat {chat_id}")
                    return True
            except Exception as e:
                logger.error(f"Redis error registering game: {e}")
        
        # Fallback to in-memory
        self._memory_store[key] = session
        logger.info(f"Registered game {game_type} for user {user_id} in chat {chat_id} (in-memory)")
        return True
    
    async def is_playing(self, user_id: int, chat_id: int) -> bool:
        """Check if user is currently in a game.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            
        Returns:
            True if user has an active game session (not expired)
        """
        session = await self.get_session(user_id, chat_id)
        if not session:
            return False
        
        # Check if session is expired (30 min timeout)
        try:
            created = datetime.fromisoformat(session.created_at)
            now = datetime.utcnow()
            if (now - created).total_seconds() > SESSION_TIMEOUT:
                # Session expired, clean it up
                await self.end_game(user_id, chat_id)
                logger.info(f"Auto-expired game session for user {user_id} in chat {chat_id}")
                return False
        except Exception as e:
            logger.warning(f"Error checking session timeout: {e}")
        
        return True
    
    async def get_session(self, user_id: int, chat_id: int) -> Optional[GameSession]:
        """Get current game session for user.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            
        Returns:
            GameSession if exists, None otherwise
        """
        key = self._make_key(user_id, chat_id)
        
        # Try Redis first
        if self._redis_client and self._redis_client.is_available:
            try:
                data = await self._redis_client.get(key)
                if data:
                    return GameSession.from_json(data)
            except Exception as e:
                logger.error(f"Redis error getting session: {e}")
        
        # Fallback to in-memory
        return self._memory_store.get(key)
    
    async def end_game(self, user_id: int, chat_id: int) -> bool:
        """End a game session and remove user from active players.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            
        Returns:
            True if session was ended, False if no session existed
        """
        key = self._make_key(user_id, chat_id)
        
        # Try Redis first
        if self._redis_client and self._redis_client.is_available:
            try:
                existed = await self._redis_client.exists(key)
                if existed:
                    await self._redis_client.delete(key)
                    logger.info(f"Ended game for user {user_id} in chat {chat_id}")
                    return True
                return False
            except Exception as e:
                logger.error(f"Redis error ending game: {e}")
        
        # Fallback to in-memory
        if key in self._memory_store:
            del self._memory_store[key]
            logger.info(f"Ended game for user {user_id} in chat {chat_id} (in-memory)")
            return True
        return False
    
    async def update_state(
        self,
        user_id: int,
        chat_id: int,
        state: Dict[str, Any]
    ) -> bool:
        """Update game state for an active session.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            state: New game state dictionary
            
        Returns:
            True if update successful, False if no session exists
        """
        session = await self.get_session(user_id, chat_id)
        if not session:
            logger.warning(f"No session found for user {user_id} in chat {chat_id}")
            return False
        
        session.state = state
        key = self._make_key(user_id, chat_id)
        
        # Try Redis first
        if self._redis_client and self._redis_client.is_available:
            try:
                # Get remaining TTL to preserve it
                ttl = await self._redis_client.ttl(key)
                if ttl and ttl > 0:
                    success = await self._redis_client.set(key, session.to_json(), ex=ttl)
                else:
                    success = await self._redis_client.set(key, session.to_json(), ex=SESSION_TIMEOUT)
                if success:
                    return True
            except Exception as e:
                logger.error(f"Redis error updating state: {e}")
        
        # Fallback to in-memory
        self._memory_store[key] = session
        return True
    
    async def get_session_by_message(
        self,
        chat_id: int,
        message_id: int
    ) -> Optional[GameSession]:
        """Find session by message ID (for callback handling).
        
        Args:
            chat_id: Telegram chat ID
            message_id: Message ID to search for
            
        Returns:
            GameSession if found, None otherwise
        """
        # This is less efficient but necessary for callback lookups
        # In production, consider maintaining a reverse index
        
        # Check in-memory store
        for key, session in self._memory_store.items():
            if session.chat_id == chat_id and session.message_id == message_id:
                return session
        
        # For Redis, we'd need to scan keys (not ideal for production)
        # This is a limitation of the current design
        return None


# Global state manager instance
state_manager = StateManager()
