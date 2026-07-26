"""
Property-based tests for Vision Module image filtering.

Tests correctness properties defined in the design document for
disabling automatic image responses.

**Feature: oleg-behavior-improvements**
**Validates: Requirements 1.1, 1.2, 1.3, 1.4**
"""

import re
from unittest.mock import MagicMock
from hypothesis import given, strategies as st, settings, assume
import pytest


# Define the filtering logic locally to avoid importing app dependencies
# This mirrors the implementation in app/handlers/vision.py

OLEG_TRIGGERS = ["олег", "олега", "олегу", "олегом", "олеге", "oleg"]


def _contains_bot_mention(text: str, bot) -> bool:
    """
    Проверяет, содержит ли текст упоминание бота.
    
    Args:
        text: Текст для проверки (caption или message text)
        bot: Объект бота для получения username
        
    Returns:
        True если текст содержит упоминание бота
    """
    if not text:
        return False
    
    text_lower = text.lower()
    
    # Проверяем @username бота
    if bot and bot._me and bot._me.username:
        bot_username = bot._me.username.lower()
        if f"@{bot_username}" in text_lower:
            return True
    
    # Проверяем слово "олег" и его формы как отдельное слово
    for trigger in OLEG_TRIGGERS:
        if re.search(rf'\b{trigger}\b', text_lower):
            return True
    
    return False


async def should_process_image(msg) -> bool:
    """
    Проверяет, нужно ли обрабатывать изображение.
    
    Бот обрабатывает изображение только если:
    - В caption есть упоминание бота (@username или "олег")
    - Это ответ на сообщение бота
    
    Args:
        msg: Сообщение с изображением
        
    Returns:
        True если нужно обработать изображение
        
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
    """
    # Проверяем caption на упоминание бота
    caption = msg.caption or ""
    if _contains_bot_mention(caption, msg.bot):
        return True
    
    # Проверяем, является ли это ответом на сообщение бота
    if msg.reply_to_message and msg.reply_to_message.from_user:
        if msg.reply_to_message.from_user.id == msg.bot.id:
            return True
    
    return False


def create_mock_message(
    caption: str = None,
    is_reply_to_bot: bool = False,
    bot_username: str = "oleg_bot",
    bot_id: int = 12345
) -> MagicMock:
    """
    Creates a mock Message object for testing.
    
    Args:
        caption: Caption text for the image
        is_reply_to_bot: Whether this is a reply to bot's message
        bot_username: Bot's username
        bot_id: Bot's user ID
    
    Returns:
        Mock Message object
    """
    msg = MagicMock()
    msg.caption = caption
    msg.message_id = 1
    
    # Mock bot object
    msg.bot = MagicMock()
    msg.bot.id = bot_id
    msg.bot._me = MagicMock()
    msg.bot._me.username = bot_username
    
    # Mock reply_to_message
    if is_reply_to_bot:
        msg.reply_to_message = MagicMock()
        msg.reply_to_message.from_user = MagicMock()
        msg.reply_to_message.from_user.id = bot_id
    else:
        msg.reply_to_message = None
    
    return msg


class TestContainsBotMention:
    """
    Tests for the _contains_bot_mention helper function.
    """
    
    @settings(max_examples=100)
    @given(st.text(min_size=0, max_size=200))
    def test_no_mention_returns_false(self, text: str):
        """
        For any text without bot mention, _contains_bot_mention returns False.
        """
        # Exclude texts that contain any trigger
        for trigger in OLEG_TRIGGERS:
            assume(trigger not in text.lower())
        assume("@oleg_bot" not in text.lower())
        
        bot = MagicMock()
        bot._me = MagicMock()
        bot._me.username = "oleg_bot"
        
        result = _contains_bot_mention(text, bot)
        assert result is False
    
    @settings(max_examples=100)
    @given(
        st.text(min_size=0, max_size=100),
        st.sampled_from(OLEG_TRIGGERS)
    )
    def test_oleg_trigger_detected(self, prefix: str, trigger: str):
        """
        For any text containing an Oleg trigger word, _contains_bot_mention returns True.
        """
        # Ensure prefix doesn't accidentally contain triggers
        for t in OLEG_TRIGGERS:
            assume(t not in prefix.lower())
        
        text = f"{prefix} {trigger} "
        
        bot = MagicMock()
        bot._me = MagicMock()
        bot._me.username = "oleg_bot"
        
        result = _contains_bot_mention(text, bot)
        assert result is True, f"Should detect trigger '{trigger}' in text '{text}'"
    
    @settings(max_examples=100)
    @given(st.text(min_size=0, max_size=100))
    def test_at_mention_detected(self, prefix: str):
        """
        For any text containing @botname, _contains_bot_mention returns True.
        """
        text = f"{prefix} @oleg_bot что это?"
        
        bot = MagicMock()
        bot._me = MagicMock()
        bot._me.username = "oleg_bot"
        
        result = _contains_bot_mention(text, bot)
        assert result is True


class TestImageFilteringWithoutMention:
    """
    **Feature: oleg-behavior-improvements, Property 1: Image filtering without explicit mention**
    **Validates: Requirements 1.1, 1.4**
    
    *For any* image message without bot mention in caption and not a reply to bot,
    the Vision_Module should skip processing and return immediately without calling LLM.
    """
    
    @settings(max_examples=100)
    @given(st.text(min_size=0, max_size=200))
    @pytest.mark.asyncio
    async def test_no_mention_no_reply_skips_processing(self, caption: str):
        """
        Property 1: Image filtering without explicit mention
        
        For any image message without bot mention in caption and not a reply to bot,
        should_process_image returns False.
        """
        # Exclude captions that contain any trigger
        for trigger in OLEG_TRIGGERS:
            assume(trigger not in caption.lower())
        assume("@oleg_bot" not in caption.lower())
        
        msg = create_mock_message(
            caption=caption,
            is_reply_to_bot=False
        )
        
        result = await should_process_image(msg)
        assert result is False, \
            f"Should skip processing for caption '{caption}' without mention"
    
    @settings(max_examples=100)
    @given(st.none() | st.just(""))
    @pytest.mark.asyncio
    async def test_empty_caption_no_reply_skips_processing(self, caption):
        """
        Property 1 extended: Empty or None caption without reply skips processing.
        """
        msg = create_mock_message(
            caption=caption,
            is_reply_to_bot=False
        )
        
        result = await should_process_image(msg)
        assert result is False, "Should skip processing for empty caption without reply"


class TestImageProcessingWithMention:
    """
    **Feature: oleg-behavior-improvements, Property 2: Image processing with explicit mention**
    **Validates: Requirements 1.2, 1.3**
    
    *For any* image message with bot mention ("олег", "@botname") in caption 
    OR as reply to bot message, the Vision_Module should process the image.
    """
    
    @settings(max_examples=100)
    @given(
        st.text(min_size=0, max_size=100),
        st.sampled_from(OLEG_TRIGGERS)
    )
    @pytest.mark.asyncio
    async def test_oleg_mention_triggers_processing(self, prefix: str, trigger: str):
        """
        Property 2a: Image with "олег" mention in caption triggers processing.
        
        **Validates: Requirements 1.2**
        """
        # Ensure prefix doesn't accidentally contain triggers
        for t in OLEG_TRIGGERS:
            assume(t not in prefix.lower())
        
        caption = f"{prefix} {trigger} что это за картинка?"
        
        msg = create_mock_message(
            caption=caption,
            is_reply_to_bot=False
        )
        
        result = await should_process_image(msg)
        assert result is True, \
            f"Should process image with trigger '{trigger}' in caption"
    
    @settings(max_examples=100)
    @given(st.text(min_size=0, max_size=100))
    @pytest.mark.asyncio
    async def test_at_mention_triggers_processing(self, prefix: str):
        """
        Property 2b: Image with @botname mention in caption triggers processing.
        
        **Validates: Requirements 1.2**
        """
        caption = f"{prefix} @oleg_bot посмотри на это"
        
        msg = create_mock_message(
            caption=caption,
            is_reply_to_bot=False
        )
        
        result = await should_process_image(msg)
        assert result is True, "Should process image with @mention in caption"
    
    @settings(max_examples=100)
    @given(st.text(min_size=0, max_size=200))
    @pytest.mark.asyncio
    async def test_reply_to_bot_triggers_processing(self, caption: str):
        """
        Property 2c: Image as reply to bot message triggers processing.
        
        **Validates: Requirements 1.3**
        """
        # Caption can be anything, even without mention
        msg = create_mock_message(
            caption=caption,
            is_reply_to_bot=True
        )
        
        result = await should_process_image(msg)
        assert result is True, \
            f"Should process image when replying to bot, regardless of caption '{caption}'"
    
    @settings(max_examples=50)
    @given(st.none() | st.just(""))
    @pytest.mark.asyncio
    async def test_reply_to_bot_empty_caption_triggers_processing(self, caption):
        """
        Property 2d: Reply to bot with empty caption still triggers processing.
        
        **Validates: Requirements 1.3**
        """
        msg = create_mock_message(
            caption=caption,
            is_reply_to_bot=True
        )
        
        result = await should_process_image(msg)
        assert result is True, "Should process image reply to bot even with empty caption"
