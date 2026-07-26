"""
Alive UI Service - живые системные уведомления для OLEG v6.0.

Показывает развлекательные статусные сообщения во время
длительной обработки запросов.

**Feature: fortress-update**
**Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5, 12.6**
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class StatusCategory(Enum):
    """Категории статусных сообщений."""
    PHOTO = "photo"
    MODERATION = "moderation"
    THINKING = "thinking"
    SEARCH = "search"
    TTS = "tts"
    QUOTE = "quote"
    GIF = "gif"
    ERROR = "error"


# Пулы фраз для разных категорий
# **Property 31: Category-specific phrases**
ALIVE_PHRASES: Dict[str, List[str]] = {
    "photo": [
        "👀 Разглядываю твои пиксели...",
        "🔍 Анализирую картинку...",
        "🖼️ Смотрю что ты там прислал...",
        "📸 Изучаю фоточку...",
        "🎨 Оцениваю композицию...",
    ],
    "moderation": [
        "🔨 Достаю банхаммер...",
        "⚖️ Взвешиваю твои грехи...",
        "📋 Проверяю по базе...",
        "🚨 Сканирую на токсичность...",
        "👮 Включаю режим модератора...",
    ],
    "thinking": [
        "🧠 Прогреваю нейронку...",
        "💭 Думаю...",
        "🚬 Вышел покурить, ща отвечу...",
        "🤔 Соображаю...",
        "⚙️ Кручу шестерёнки...",
    ],
    "search": [
        "📂 Ищу компромат в базе...",
        "🔎 Копаюсь в архивах...",
        "📚 Листаю документацию...",
        "🗃️ Роюсь в файлах...",
        "🔍 Ищу ответ...",
    ],
    "tts": [
        "🎤 Прочищаю горло...",
        "🗣️ Готовлю голосовые связки...",
        "🎙️ Настраиваю микрофон...",
        "📢 Набираю воздуха...",
        "🔊 Генерирую звук...",
    ],
    "quote": [
        "🎨 Рисую цитату...",
        "✍️ Оформляю шедевр...",
        "🖌️ Добавляю градиенты...",
        "📝 Верстаю картинку...",
        "🎭 Создаю мем...",
    ],
    "gif": [
        "🎬 Разбираю гифку по кадрам...",
        "🎞️ Анализирую анимацию...",
        "📽️ Смотрю твой мультик...",
        "🔬 Исследую пиксели...",
        "👁️ Проверяю контент...",
    ],
    "error": [
        "❌ Что-то пошло не так...",
        "💥 Упс, ошибочка вышла...",
        "🔧 Сломалось что-то...",
        "⚠️ Произошла ошибка...",
        "🤷 Не получилось...",
    ],
}

# Timing configuration
# **Property 29: Status message timing** - 2 seconds threshold
STATUS_THRESHOLD_SECONDS = 2.0
# **Property 30: Status update interval** - 3 seconds
UPDATE_INTERVAL_SECONDS = 3.0


@dataclass
class StatusMessage:
    """Represents an active status message."""
    chat_id: int
    message_id: int
    category: str
    started_at: float
    last_updated_at: float
    update_count: int = 0
    is_finished: bool = False
    message_thread_id: Optional[int] = None


@dataclass
class StatusContext:
    """Context for tracking status during processing."""
    chat_id: int
    category: str
    started_at: float = field(default_factory=time.time)
    status_message: Optional[StatusMessage] = None
    _update_task: Optional[asyncio.Task] = None
    _bot: Any = None


class AliveUIService:
    """
    Сервис для отображения живых статусных сообщений.
    
    Показывает развлекательные фразы во время длительной обработки,
    обновляя их каждые 3 секунды.
    
    **Feature: fortress-update**
    **Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5, 12.6**
    """
    
    def __init__(self):
        """Initialize the Alive UI service."""
        self._active_statuses: Dict[str, StatusContext] = {}
        self._phrases = ALIVE_PHRASES.copy()
    
    def get_random_phrase(self, category: str) -> str:
        """
        Get a random phrase for the given category.
        
        **Property 31: Category-specific phrases**
        For any status message in category X, the phrase SHALL be 
        selected from the X-specific phrase pool.
        
        Args:
            category: The category of status message
            
        Returns:
            A random phrase from the category's pool
        """
        # Normalize category
        if isinstance(category, StatusCategory):
            category = category.value
        
        category = category.lower()
        
        # Get phrases for category, fallback to thinking
        phrases = self._phrases.get(category, self._phrases.get("thinking", ["Обрабатываю..."]))
        
        return random.choice(phrases)
    
    def get_phrases_for_category(self, category: str) -> List[str]:
        """
        Get all phrases for a category.
        
        Args:
            category: The category name
            
        Returns:
            List of phrases for the category
        """
        if isinstance(category, StatusCategory):
            category = category.value
        
        category = category.lower()
        return self._phrases.get(category, [])
    
    def add_phrase(self, category: str, phrase: str) -> None:
        """
        Add a phrase to a category.
        
        Args:
            category: The category name
            phrase: The phrase to add
        """
        if isinstance(category, StatusCategory):
            category = category.value
        
        category = category.lower()
        
        if category not in self._phrases:
            self._phrases[category] = []
        
        if phrase not in self._phrases[category]:
            self._phrases[category].append(phrase)
    
    async def start_status(
        self,
        chat_id: int,
        category: str,
        bot: Any = None,
        message_thread_id: Optional[int] = None
    ) -> Optional[StatusMessage]:
        """
        Start showing a status message.
        
        **Property 29: Status message timing**
        For any processing task exceeding 2 seconds, a status message 
        SHALL be sent.
        
        Note: This method sends the status immediately. The 2-second
        threshold should be checked by the caller or use start_status_delayed.
        
        Args:
            chat_id: The chat ID to send status to
            category: The category of status message
            bot: Telegram bot instance for sending messages
            message_thread_id: Optional thread/topic ID for forum chats
            
        Returns:
            StatusMessage if sent successfully, None otherwise
        """
        if isinstance(category, StatusCategory):
            category = category.value
        
        phrase = self.get_random_phrase(category)
        now = time.time()
        
        # Create status context
        context_key = f"{chat_id}_{now}"
        context = StatusContext(
            chat_id=chat_id,
            category=category,
            started_at=now,
            _bot=bot
        )
        
        try:
            if bot is not None:
                # Send the status message
                # Для форумов используем прямой API с reply_parameters (работает со старыми топиками)
                message_id = None
                if message_thread_id is not None:
                    import httpx
                    bot_token = bot.token
                    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    payload = {
                        "chat_id": chat_id,
                        "text": phrase,
                        "message_thread_id": message_thread_id
                    }
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(api_url, json=payload)
                        result = resp.json()
                        if result.get("ok"):
                            message_id = result["result"]["message_id"]
                        else:
                            logger.warning(f"Failed to send status to forum: {result.get('description')}")
                            return None
                else:
                    message = await bot.send_message(chat_id, phrase)
                    message_id = message.message_id
                
                status = StatusMessage(
                    chat_id=chat_id,
                    message_id=message_id,
                    category=category,
                    started_at=now,
                    last_updated_at=now,
                    update_count=0,
                    message_thread_id=message_thread_id
                )
                
                context.status_message = status
                self._active_statuses[context_key] = context
                
                logger.debug(f"Started status message in chat {chat_id} (thread {message_thread_id}): {phrase}")
                return status
            else:
                # No bot provided, just track timing
                logger.debug(f"Status tracking started for chat {chat_id} (no bot)")
                return None
                
        except Exception as e:
            logger.error(f"Failed to send status message: {e}")
            return None
    
    async def update_status(
        self,
        status: StatusMessage,
        category: Optional[str] = None,
        bot: Any = None
    ) -> bool:
        """
        Update an existing status message with a new phrase.
        
        **Property 30: Status update interval**
        For any ongoing processing with status message, updates SHALL 
        occur every 3 seconds.
        
        Args:
            status: The status message to update
            category: Optional new category (uses existing if not provided)
            bot: Telegram bot instance
            
        Returns:
            True if updated successfully, False otherwise
        """
        if status.is_finished:
            return False
        
        now = time.time()
        
        # Check if enough time has passed since last update
        time_since_update = now - status.last_updated_at
        if time_since_update < UPDATE_INTERVAL_SECONDS:
            return False
        
        # Use provided category or existing
        cat = category if category else status.category
        if isinstance(cat, StatusCategory):
            cat = cat.value
        
        phrase = self.get_random_phrase(cat)
        
        try:
            if bot is not None:
                await bot.edit_message_text(
                    chat_id=status.chat_id,
                    message_id=status.message_id,
                    text=phrase
                )
                
                status.last_updated_at = now
                status.update_count += 1
                status.category = cat
                
                logger.debug(f"Updated status message {status.message_id}: {phrase}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.warning(f"Failed to update status message: {e}")
            return False
    
    async def finish_status(
        self,
        status: StatusMessage,
        bot: Any = None,
        delete: bool = True
    ) -> bool:
        """
        Finish and clean up a status message.
        
        **Property 32: Status cleanup**
        For any completed processing, the status message SHALL be 
        deleted before sending the response.
        
        Args:
            status: The status message to finish
            bot: Telegram bot instance
            delete: Whether to delete the message (default True)
            
        Returns:
            True if cleaned up successfully, False otherwise
        """
        if status.is_finished:
            return True
        
        status.is_finished = True
        
        # Remove from active statuses
        keys_to_remove = [
            key for key, ctx in self._active_statuses.items()
            if ctx.status_message and ctx.status_message.message_id == status.message_id
        ]
        for key in keys_to_remove:
            ctx = self._active_statuses.pop(key, None)
            if ctx and ctx._update_task:
                ctx._update_task.cancel()
        
        if not delete:
            return True
        
        try:
            if bot is not None:
                await bot.delete_message(
                    chat_id=status.chat_id,
                    message_id=status.message_id
                )
                logger.debug(f"Deleted status message {status.message_id}")
                return True
            else:
                return True
                
        except Exception as e:
            logger.warning(f"Failed to delete status message: {e}")
            return False
    
    async def show_error(
        self,
        status: StatusMessage,
        error_message: str,
        bot: Any = None
    ) -> bool:
        """
        Update status message to show an error.
        
        **Validates: Requirements 12.6**
        WHEN an error occurs during processing THEN the Alive UI System 
        SHALL update the status message with an error phrase and explanation.
        
        Args:
            status: The status message to update
            error_message: The error explanation
            bot: Telegram bot instance
            
        Returns:
            True if updated successfully, False otherwise
        """
        if status.is_finished:
            return False
        
        error_phrase = self.get_random_phrase("error")
        full_message = f"{error_phrase}\n\n{error_message}"
        
        try:
            if bot is not None:
                await bot.edit_message_text(
                    chat_id=status.chat_id,
                    message_id=status.message_id,
                    text=full_message
                )
                
                status.is_finished = True
                logger.debug(f"Showed error on status message {status.message_id}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.warning(f"Failed to show error on status message: {e}")
            return False
    
    def should_show_status(self, elapsed_seconds: float) -> bool:
        """
        Check if status message should be shown based on elapsed time.
        
        **Property 29: Status message timing**
        For any processing task exceeding 2 seconds, a status message 
        SHALL be sent.
        
        Args:
            elapsed_seconds: Time elapsed since processing started
            
        Returns:
            True if status should be shown (elapsed > 2 seconds)
        """
        return elapsed_seconds > STATUS_THRESHOLD_SECONDS
    
    def should_update_status(self, last_update_seconds: float) -> bool:
        """
        Check if status message should be updated based on time since last update.
        
        **Property 30: Status update interval**
        For any ongoing processing with status message, updates SHALL 
        occur every 3 seconds.
        
        Args:
            last_update_seconds: Time since last update
            
        Returns:
            True if status should be updated (elapsed >= 3 seconds)
        """
        return last_update_seconds >= UPDATE_INTERVAL_SECONDS
    
    def get_category_for_task(self, task_type: str) -> str:
        """
        Get the appropriate category for a task type.
        
        Args:
            task_type: The type of task being performed
            
        Returns:
            The category string for status messages
        """
        task_mapping = {
            "photo_analysis": "photo",
            "image_analysis": "photo",
            "vision": "photo",
            "moderation": "moderation",
            "toxicity": "moderation",
            "ban": "moderation",
            "thinking": "thinking",
            "llm": "thinking",
            "chat": "thinking",
            "search": "search",
            "rag": "search",
            "database": "search",
            "tts": "tts",
            "voice": "tts",
            "speech": "tts",
            "quote": "quote",
            "sticker": "quote",
            "render": "quote",
            "gif": "gif",
            "animation": "gif",
        }
        
        task_lower = task_type.lower()
        
        # Check for exact match
        if task_lower in task_mapping:
            return task_mapping[task_lower]
        
        # Check for partial match
        for key, category in task_mapping.items():
            if key in task_lower:
                return category
        
        # Default to thinking
        return "thinking"


# Context manager for automatic status handling
class StatusContextManager:
    """
    Context manager for automatic status message handling.
    
    Usage:
        async with alive_ui.status_context(chat_id, "thinking", bot) as status:
            # Do long-running work
            result = await some_long_operation()
        # Status is automatically cleaned up
    """
    
    def __init__(
        self,
        service: AliveUIService,
        chat_id: int,
        category: str,
        bot: Any = None,
        delay_seconds: float = STATUS_THRESHOLD_SECONDS,
        message_thread_id: Optional[int] = None
    ):
        self.service = service
        self.chat_id = chat_id
        self.category = category
        self.bot = bot
        self.delay_seconds = delay_seconds
        self.message_thread_id = message_thread_id
        self.status: Optional[StatusMessage] = None
        self._start_time: float = 0
        self._update_task: Optional[asyncio.Task] = None
    
    async def __aenter__(self) -> Optional[StatusMessage]:
        self._start_time = time.time()
        
        # Start delayed status display
        self._update_task = asyncio.create_task(self._delayed_status_loop())
        
        return None  # Status will be created after delay
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Cancel update task
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        
        # Clean up status message
        if self.status:
            if exc_type is not None:
                # Show error if exception occurred
                error_msg = str(exc_val) if exc_val else "Unknown error"
                await self.service.show_error(self.status, error_msg, self.bot)
            else:
                # Delete status message on success
                await self.service.finish_status(self.status, self.bot)
        
        return False  # Don't suppress exceptions
    
    async def _delayed_status_loop(self):
        """Background task to show and update status after delay."""
        try:
            # Wait for threshold before showing status
            await asyncio.sleep(self.delay_seconds)
            
            # Show initial status (with thread_id for forum chats)
            self.status = await self.service.start_status(
                self.chat_id, 
                self.category, 
                self.bot,
                message_thread_id=self.message_thread_id
            )
            
            if not self.status:
                return
            
            # Update loop
            while True:
                await asyncio.sleep(UPDATE_INTERVAL_SECONDS)
                if self.status and not self.status.is_finished:
                    await self.service.update_status(self.status, bot=self.bot)
                else:
                    break
                    
        except asyncio.CancelledError:
            pass


# Global service instance
alive_ui_service = AliveUIService()


def status_context(
    chat_id: int,
    category: str,
    bot: Any = None,
    delay_seconds: float = STATUS_THRESHOLD_SECONDS,
    message_thread_id: Optional[int] = None
) -> StatusContextManager:
    """
    Create a status context manager for automatic status handling.
    
    Args:
        chat_id: The chat ID
        category: The status category
        bot: Telegram bot instance
        delay_seconds: Delay before showing status (default 2 seconds)
        message_thread_id: Optional thread/topic ID for forum chats
        
    Returns:
        StatusContextManager instance
    """
    return StatusContextManager(
        alive_ui_service,
        chat_id,
        category,
        bot,
        delay_seconds,
        message_thread_id
    )
