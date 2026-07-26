"""
Обработчик реакций на сообщения Олега.

Олег реагирует на реакции пользователей к его сообщениям,
делая взаимодействие более живым.

**Features:**
- Расширенные категории реакций (позитивные, негативные, флирт, удивление, смех, грусть)
- Combo System - особые ответы при массовых одинаковых реакциях
- Rare Reactions - редкие забавные ответы (5% шанс)
- Easter Eggs - секретные комбинации реакций

**Validates: Requirements 8.1, 8.2, 8.3, 8.4**
"""

import logging
import random
import time
from typing import Dict, List, Tuple
from aiogram import Router, Bot
from aiogram.types import MessageReactionUpdated, ReactionTypeEmoji

logger = logging.getLogger(__name__)

router = Router()

# ============================================================================
# REACTION CATEGORIES
# ============================================================================

# Positive reactions that Oleg responds to positively
# **Validates: Requirements 8.2**
POSITIVE_REACTIONS = {"❤️", "👍", "🔥", "😍", "🎉", "💯", "⚡", "🥰", "😘", "🤩", "👏", "🙏", "✨", "💖", "🌟", "🎊"}

# Negative reactions that Oleg may respond to sarcastically
# **Validates: Requirements 8.3**
NEGATIVE_REACTIONS = {"👎", "💩", "🤮", "😡", "🤬", "😤", "👿", "🖕", "😠"}

# Flirty reactions - Oleg flirts back
FLIRTY_REACTIONS = {"😏", "😉", "💋", "💕", "💘", "😻", "🫦", "🔥"}

# Surprised reactions - Oleg acts surprised
SURPRISED_REACTIONS = {"😱", "🤯", "😲", "😳", "🫢", "😮", "🙀"}

# Funny reactions - Oleg is happy he made you laugh
FUNNY_REACTIONS = {"😂", "🤣", "😹", "💀", "☠️", "😆", "🤪"}

# Sad reactions - Oleg comforts or trolls
SAD_REACTIONS = {"😢", "😭", "😔", "😞", "🥺", "😿", "💔"}

# Thinking reactions - Oleg acknowledges deep thoughts
THINKING_REACTIONS = {"🤔", "🧐", "🤨", "👀", "🫡", "🗿"}

# ============================================================================
# EASTER EGGS - Special reaction combinations
# ============================================================================

EASTER_EGGS = {
    # Eggplant + water = classic meme
    frozenset({"🍆", "💦"}): ["Бондаж? 😏", "Классика жанра 💦", "Ммм, интересно 🤔"],
    # 420 blaze it
    frozenset({"🌿", "🔥"}): ["420 blaze it 🌿", "Легализуй это 😎", "Травка-муравка 🍃"],
    # Devil number
    frozenset({"😈", "🔥", "666"}): ["Hail Satan 😈", "Адский комбо 🔥", "666 - число зверя 👿"],
    # Love combo
    frozenset({"❤️", "🔥", "💯"}): ["Любовь горит! 🔥❤️", "100% страсти 💯", "Это любовь 😍"],
    # Thinking hard
    frozenset({"🤔", "🧠", "💭"}): ["Философствуем? 🧐", "Большие мысли 🧠", "Думай, думай... 🤔"],
    # Party time
    frozenset({"🎉", "🍾", "🎊"}): ["Вечеринка! 🎉", "Отмечаем? 🍾", "Праздник к нам приходит! 🎊"],
}

# ============================================================================
# COOLDOWN & COMBO TRACKING
# ============================================================================

# Cooldown mechanism to prevent spam
# Key: (chat_id, message_id), Value: timestamp of last reaction response
# **Validates: Requirements 8.4**
_reaction_cooldowns: Dict[Tuple[int, int], float] = {}
REACTION_COOLDOWN = 30.0  # 30 seconds cooldown per message

# Combo tracking - multiple users reacting with same emoji
# Key: message_id, Value: {emoji: [(user_id, timestamp)]}
_reaction_combos: Dict[int, Dict[str, List[Tuple[int, float]]]] = {}
COMBO_THRESHOLD = 5  # Number of users needed for combo
COMBO_WINDOW = 60.0  # Time window for combo (seconds)


def is_on_cooldown(chat_id: int, message_id: int) -> bool:
    """
    Check if a message is on cooldown for reaction responses.
    
    **Validates: Requirements 8.4**
    
    Args:
        chat_id: Chat ID
        message_id: Message ID
        
    Returns:
        True if on cooldown, False otherwise
    """
    key = (chat_id, message_id)
    last_response_time = _reaction_cooldowns.get(key, 0)
    return time.time() - last_response_time < REACTION_COOLDOWN


def set_cooldown(chat_id: int, message_id: int) -> None:
    """
    Set cooldown for a message after responding to a reaction.
    
    **Validates: Requirements 8.4**
    
    Args:
        chat_id: Chat ID
        message_id: Message ID
    """
    key = (chat_id, message_id)
    _reaction_cooldowns[key] = time.time()


def cleanup_old_cooldowns() -> None:
    """
    Remove expired cooldowns to prevent memory leaks.
    Called periodically during reaction processing.
    """
    current_time = time.time()
    expired_keys = [
        key for key, timestamp in _reaction_cooldowns.items()
        if current_time - timestamp > REACTION_COOLDOWN * 2
    ]
    for key in expired_keys:
        del _reaction_cooldowns[key]


def cleanup_old_combos() -> None:
    """
    Remove expired combo tracking data.
    Called periodically during reaction processing.
    """
    current_time = time.time()
    expired_messages = []
    
    for message_id, emoji_data in _reaction_combos.items():
        # Clean up old user reactions within each emoji
        for emoji in list(emoji_data.keys()):
            emoji_data[emoji] = [
                (user_id, ts) for user_id, ts in emoji_data[emoji]
                if current_time - ts < COMBO_WINDOW * 2
            ]
            # Remove emoji if no recent reactions
            if not emoji_data[emoji]:
                del emoji_data[emoji]
        
        # Mark message for removal if no emojis left
        if not emoji_data:
            expired_messages.append(message_id)
    
    for message_id in expired_messages:
        del _reaction_combos[message_id]


def check_combo(message_id: int, emoji: str, user_id: int) -> int:
    """
    Check if a combo is happening (multiple users reacting with same emoji).
    
    Args:
        message_id: Message ID
        emoji: Emoji being reacted with
        user_id: User who reacted
        
    Returns:
        Number of users in the combo (0 if no combo)
    """
    current_time = time.time()
    
    # Initialize tracking for this message if needed
    if message_id not in _reaction_combos:
        _reaction_combos[message_id] = {}
    
    # Initialize tracking for this emoji if needed
    if emoji not in _reaction_combos[message_id]:
        _reaction_combos[message_id][emoji] = []
    
    # Add this user's reaction
    _reaction_combos[message_id][emoji].append((user_id, current_time))
    
    # Count recent reactions (within combo window)
    recent_reactions = [
        (uid, ts) for uid, ts in _reaction_combos[message_id][emoji]
        if current_time - ts < COMBO_WINDOW
    ]
    
    # Update with only recent reactions
    _reaction_combos[message_id][emoji] = recent_reactions
    
    # Get unique users
    unique_users = len(set(uid for uid, _ in recent_reactions))
    
    return unique_users if unique_users >= COMBO_THRESHOLD else 0


def check_easter_egg(new_emojis: set) -> str | None:
    """
    Check if the reaction combination triggers an easter egg.
    
    Args:
        new_emojis: Set of emojis in the reaction
        
    Returns:
        Easter egg message or None
    """
    for egg_combo, messages in EASTER_EGGS.items():
        if egg_combo.issubset(new_emojis):
            return random.choice(messages)
    return None


@router.message_reaction()
async def on_reaction(event: MessageReactionUpdated):
    """
    Handle reactions to Oleg's messages.
    
    **Features:**
    - Multiple reaction categories with unique responses
    - Combo system for mass reactions
    - Rare reactions (5% chance)
    - Easter eggs for special combinations
    - Per-chat enable/disable via admin panel
    
    **Validates: Requirements 8.1, 8.2, 8.3, 8.4**
    
    Args:
        event: MessageReactionUpdated event from Telegram
    """
    # Cleanup old data periodically
    if random.random() < 0.1:  # 10% chance to cleanup
        cleanup_old_cooldowns()
        cleanup_old_combos()
    
    # Check if we have new reactions
    if not event.new_reaction:
        return
    
    chat_id = event.chat.id
    message_id = event.message_id
    user_id = event.user.id if event.user else 0
    
    # Check if reactions are enabled for this chat
    from app.database.session import get_session
    from app.database.models import Chat
    
    async with get_session()() as session:
        chat = await session.get(Chat, chat_id)
        if chat and not chat.reactions_enabled:
            logger.debug(f"Reactions disabled for chat {chat_id}")
            return
    
    # Check cooldown - prevent spam responses
    # **Validates: Requirements 8.4**
    if is_on_cooldown(chat_id, message_id):
        logger.debug(f"Reaction on cooldown for message {message_id} in chat {chat_id}")
        return
    
    # Get the bot instance
    bot: Bot = event.bot
    
    # Extract emoji from reactions
    new_emojis = set()
    for reaction in event.new_reaction:
        if isinstance(reaction, ReactionTypeEmoji):
            new_emojis.add(reaction.emoji)
        elif hasattr(reaction, 'emoji'):
            new_emojis.add(reaction.emoji)
    
    if not new_emojis:
        return
    
    # Get thread_id for forum support
    thread_id = getattr(event, 'message_thread_id', None)
    
    # ========================================================================
    # EASTER EGGS - Check first for special combinations
    # ========================================================================
    easter_egg_msg = check_easter_egg(new_emojis)
    if easter_egg_msg:
        set_cooldown(chat_id, message_id)
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"🥚 {easter_egg_msg}",
                message_thread_id=thread_id
            )
            logger.info(f"Easter egg triggered in chat {chat_id}, message {message_id}")
            return
        except Exception as e:
            logger.warning(f"Failed to send easter egg: {e}")
    
    # ========================================================================
    # COMBO SYSTEM - Check for mass reactions
    # ========================================================================
    for emoji in new_emojis:
        combo_count = check_combo(message_id, emoji, user_id)
        if combo_count >= COMBO_THRESHOLD:
            set_cooldown(chat_id, message_id)
            combo_messages = [
                f"КОМБО x{combo_count}! {emoji * 3}",
                f"Вау, {combo_count} человек! {emoji}",
                f"Массовая реакция detected! {emoji} x{combo_count}",
                f"{emoji} ЦЕПОЧКА! {combo_count} в ряд!",
            ]
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=random.choice(combo_messages),
                    message_thread_id=thread_id
                )
                logger.info(f"Combo x{combo_count} triggered for {emoji} in chat {chat_id}")
                return
            except Exception as e:
                logger.warning(f"Failed to send combo message: {e}")
    
    # ========================================================================
    # RARE REACTIONS - DISABLED (was spamming chats)
    # ========================================================================
    # Rare reactions disabled to prevent spam in general chat
    # if random.random() < 0.001:  # Reduced from 5% to 0.1% if re-enabled
    #     set_cooldown(chat_id, message_id)
    #     rare_messages = [
    #         "Редкая реакция разблокирована! ✨",
    #         "Ого, это было неожиданно 🎲",
    #         "Критический хит реакцией! 💥",
    #         "Легендарный ответ активирован 🌟",
    #         "RNG благосклонен к тебе 🎰",
    #     ]
    #     try:
    #         await bot.send_message(
    #             chat_id=chat_id,
    #             text=random.choice(rare_messages),
    #             message_thread_id=thread_id
    #         )
    #         logger.info(f"Rare reaction triggered in chat {chat_id}, message {message_id}")
    #         return
    #     except Exception as e:
    #         logger.warning(f"Failed to send rare reaction: {e}")
    
    # ========================================================================
    # CATEGORY-BASED RESPONSES
    # ========================================================================
    
    # Flirty reactions
    flirty_match = new_emojis & FLIRTY_REACTIONS
    if flirty_match:
        set_cooldown(chat_id, message_id)
        # Always react back with emoji, no text spam
        response_emoji = random.choice(["😏", "😉", "💋", "🔥", "😘"])
        try:
            await bot.set_message_reaction(
                chat_id=chat_id,
                message_id=message_id,
                reaction=[ReactionTypeEmoji(emoji=response_emoji)]
            )
            logger.info(f"Oleg flirted back with {response_emoji}")
        except Exception as e:
            logger.warning(f"Failed to set flirty reaction: {e}")
        return
    
    # Surprised reactions
    surprised_match = new_emojis & SURPRISED_REACTIONS
    if surprised_match:
        set_cooldown(chat_id, message_id)
        response_emoji = random.choice(["😱", "🤯", "😲", "🫢"])
        try:
            await bot.set_message_reaction(
                chat_id=chat_id,
                message_id=message_id,
                reaction=[ReactionTypeEmoji(emoji=response_emoji)]
            )
            logger.info(f"Oleg acted surprised with {response_emoji}")
        except Exception as e:
            logger.warning(f"Failed to set surprised reaction: {e}")
        return
    
    # Funny reactions
    funny_match = new_emojis & FUNNY_REACTIONS
    if funny_match:
        set_cooldown(chat_id, message_id)
        # Always react back with emoji
        response_emoji = random.choice(["😂", "🤣", "😎", "💯", "🔥"])
        try:
            await bot.set_message_reaction(
                chat_id=chat_id,
                message_id=message_id,
                reaction=[ReactionTypeEmoji(emoji=response_emoji)]
            )
            logger.info(f"Oleg laughed back with {response_emoji}")
        except Exception as e:
            logger.warning(f"Failed to set funny reaction: {e}")
        return
    
    # Sad reactions - DISABLED
    # sad_match = new_emojis & SAD_REACTIONS
    # if sad_match:
    #     set_cooldown(chat_id, message_id)
    #     if random.random() < 0.5:  # 50% comfort
    #         comfort_messages = [
    #             "Не грусти 🥺",
    #             "Всё будет хорошо 💙",
    #             "Держись там 💪",
    #             "Обнял 🤗",
    #         ]
    #         try:
    #             await bot.send_message(
    #                 chat_id=chat_id,
    #                 text=random.choice(comfort_messages),
    #                 message_thread_id=thread_id
    #             )
    #         except Exception as e:
    #             logger.warning(f"Failed to send comfort message: {e}")
    #     else:  # 50% troll
    #         troll_messages = [
    #             "Ну не реви 😏",
    #             "Слёзы не помогут 🙄",
    #             "Драма-квин 💅",
    #             "Ой, всё 😤",
    #         ]
    #         try:
    #             await bot.send_message(
    #                 chat_id=chat_id,
    #                 text=random.choice(troll_messages),
    #                 message_thread_id=thread_id
    #             )
    #         except Exception as e:
    #             logger.warning(f"Failed to send troll message: {e}")
    #     return
    
    # Thinking reactions
    thinking_match = new_emojis & THINKING_REACTIONS
    if thinking_match:
        set_cooldown(chat_id, message_id)
        response_emoji = random.choice(["🤔", "🧐", "💭", "🗿"])
        try:
            await bot.set_message_reaction(
                chat_id=chat_id,
                message_id=message_id,
                reaction=[ReactionTypeEmoji(emoji=response_emoji)]
            )
            logger.info(f"Oleg acknowledged thinking with {response_emoji}")
        except Exception as e:
            logger.warning(f"Failed to set thinking reaction: {e}")
        return
    
    # ========================================================================
    # ORIGINAL CATEGORIES (fallback)
    # ========================================================================
    
    # Check for positive reactions
    # **Validates: Requirements 8.2**
    positive_match = new_emojis & POSITIVE_REACTIONS
    if positive_match:
        set_cooldown(chat_id, message_id)
        response_emoji = random.choice(["❤️", "🔥", "😊", "👍", "🤗", "✨"])
        try:
            await bot.set_message_reaction(
                chat_id=chat_id,
                message_id=message_id,
                reaction=[ReactionTypeEmoji(emoji=response_emoji)]
            )
            logger.info(
                f"Oleg responded with {response_emoji} to positive reaction "
                f"in chat {chat_id}, message {message_id}"
            )
        except Exception as e:
            logger.warning(f"Failed to set reaction response: {e}")
        return
    
    # Check for negative reactions
    # **Validates: Requirements 8.3**
    negative_match = new_emojis & NEGATIVE_REACTIONS
    if negative_match:
        set_cooldown(chat_id, message_id)
        
        # 30% chance to respond sarcastically with a message
        if random.random() < 0.3:
            sarcastic_responses = [
                "Ну и ладно 😤",
                "Сам такой 🙄",
                "Обидно, да? 😏",
                "Критика принята, но проигнорирована 😎",
                "Ой, всё 💅",
                "Хейтеры gonna hate 🤷",
                "Твоё мнение очень важно для меня 🥱",
            ]
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=random.choice(sarcastic_responses),
                    message_thread_id=thread_id
                )
                logger.info(
                    f"Oleg responded sarcastically to negative reaction "
                    f"in chat {chat_id}, message {message_id}"
                )
            except Exception as e:
                logger.warning(f"Failed to send sarcastic response: {e}")
        else:
            # Just react back with something neutral
            try:
                await bot.set_message_reaction(
                    chat_id=chat_id,
                    message_id=message_id,
                    reaction=[ReactionTypeEmoji(emoji="🤷")]
                )
                logger.info(
                    f"Oleg responded with 🤷 to negative reaction "
                    f"in chat {chat_id}, message {message_id}"
                )
            except Exception as e:
                logger.warning(f"Failed to set neutral reaction: {e}")
