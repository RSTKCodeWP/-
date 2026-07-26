"""Command scope manager for registering different commands in group and private chats."""

import logging
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats

logger = logging.getLogger(__name__)


# Commands visible in group chats - games, moderation, group features
# Telegram limit: 100 commands max
GROUP_COMMANDS = [
    # === Основное ===
    BotCommand(command="help", description="📚 Справка по командам"),
    BotCommand(command="profile", description="👤 Твой профиль со статистикой"),
    BotCommand(command="balance", description="💰 Твой баланс монет"),
    BotCommand(command="daily", description="🎁 Ежедневный бонус"),
    
    # === Игры ===
    BotCommand(command="games", description="🎮 Игровой хаб с кнопками"),
    BotCommand(command="grow", description="🌱 Увеличить размер"),
    BotCommand(command="top", description="🏆 Топ-10 с графиками роста"),
    BotCommand(command="top_grow", description="🌱 Топ-10 по количеству ростов"),
    BotCommand(command="challenge", description="⚔️ PvP дуэль"),
    BotCommand(command="casino", description="🎰 Слоты"),
    BotCommand(command="roulette", description="🔫 Русская рулетка"),
    BotCommand(command="coinflip", description="🪙 Монетка"),
    BotCommand(command="bj", description="🃏 Блэкджек"),
    
    # === Мини-игры ===
    BotCommand(command="fish", description="🎣 Рыбалка"),
    BotCommand(command="crash", description="🚀 Краш"),
    BotCommand(command="dice", description="🎲 Кости"),
    BotCommand(command="guess", description="🔮 Угадай число"),
    BotCommand(command="wheel", description="🎡 Колесо фортуны"),
    BotCommand(command="loot", description="📦 Открыть лутбокс"),
    BotCommand(command="cockfight", description="🐔 Петушиные бои"),
    
    # === Магазин ===
    BotCommand(command="shop", description="🏪 Магазин"),
    BotCommand(command="inventory", description="🎒 Инвентарь"),
    BotCommand(command="transfer", description="💸 Перевести монеты"),
    
    # === Трейдинг v9.5 ===
    BotCommand(command="trade", description="🔄 Обмен с игроком (реплай)"),
    BotCommand(command="trades", description="📋 Активные обмены"),
    BotCommand(command="sell", description="🏪 Выставить на продажу"),
    BotCommand(command="market", description="🛒 Маркетплейс"),
    BotCommand(command="mylistings", description="📦 Мои объявления"),
    BotCommand(command="auction", description="🎯 Создать аукцион"),
    BotCommand(command="auctions", description="⚖️ Активные аукционы"),
    BotCommand(command="myauctions", description="🔨 Мои аукционы"),
    
    # === Социальное ===
    BotCommand(command="quests", description="📜 Ежедневные квесты"),
    BotCommand(command="achievements", description="🏆 Все достижения"),
    BotCommand(command="myach", description="🎖 Мои достижения"),
    BotCommand(command="marry", description="💍 Предложить брак"),
    BotCommand(command="divorce", description="💔 Развестись"),
    
    # === Гильдии ===
    BotCommand(command="create_guild", description="🏰 Создать гильдию"),
    BotCommand(command="join_guild", description="🚪 Вступить в гильдию"),
    BotCommand(command="guild_info", description="📋 Инфо о гильдии"),
    
    # === Дуэты ===
    BotCommand(command="create_duo", description="👥 Создать дуэт"),
    BotCommand(command="duo_stats", description="📊 Статистика дуэта"),
    BotCommand(command="top_duos", description="🏅 Топ дуэтов"),
    
    # === Цитаты ===
    BotCommand(command="q", description="💬 Сохранить цитату (реплай)"),
    
    # === Утилиты ===
    BotCommand(command="say", description="🔊 Озвучить текст"),
    BotCommand(command="tldr", description="📝 Пересказ контента"),
    BotCommand(command="whois", description="🔍 Инфо о пользователе"),
    BotCommand(command="birthday", description="🎂 Установить день рождения"),
    BotCommand(command="stats", description="📈 Статистика чата"),
    BotCommand(command="cancel", description="❌ Отменить текущую игру"),
    
    # === Модерация (для админов) ===
    BotCommand(command="warn", description="⚠️ Предупреждение (реплай)"),
    BotCommand(command="mute", description="🔇 Замутить (реплай)"),
    BotCommand(command="ban", description="🚫 Забанить (реплай)"),
    BotCommand(command="tips", description="💡 Советы для админов"),
]


# Commands visible in private chats - admin panel, personal commands
# Note: /owner is intentionally hidden (anonymous command for bot owner only)
PRIVATE_COMMANDS = [
    BotCommand(command="help", description="📚 Справка по командам"),
    BotCommand(command="start", description="👋 Начать общение"),
    BotCommand(command="admin", description="⚙️ Админ-панель для чатов"),
    BotCommand(command="reset", description="🔄 Сбросить контекст диалога"),
    BotCommand(command="myhistory", description="📜 История вопросов"),
    BotCommand(command="say", description="🔊 Озвучить текст"),
    BotCommand(command="tldr", description="📝 Пересказ по ссылке"),
]


async def setup_commands(bot: Bot) -> bool:
    """
    Register command scopes for different chat types.
    
    Sets up separate command menus for:
    - Private chats: admin, reset, help, say, start
    - Group chats: games, moderation, quotes, etc.
    
    Args:
        bot: The Bot instance to register commands for
        
    Returns:
        True if registration was successful, False otherwise
    """
    try:
        # Register commands for private chats
        await bot.set_my_commands(
            commands=PRIVATE_COMMANDS,
            scope=BotCommandScopeAllPrivateChats()
        )
        logger.info(f"Registered {len(PRIVATE_COMMANDS)} commands for private chats")
        
        # Register commands for group chats
        await bot.set_my_commands(
            commands=GROUP_COMMANDS,
            scope=BotCommandScopeAllGroupChats()
        )
        logger.info(f"Registered {len(GROUP_COMMANDS)} commands for group chats")
        
        return True
        
    except Exception as e:
        logger.warning(f"Failed to register command scopes: {e}")
        return False
