"""
Сервис для получения настроек бота в чате.
"""

import logging
from typing import Optional
from sqlalchemy import select
from app.database.session import get_session

logger = logging.getLogger(__name__)

# Кэш конфигов (chat_id -> config dict)
_config_cache: dict[int, dict] = {}


async def get_bot_config(chat_id: int) -> dict:
    """
    Получить настройки бота для чата.
    
    Returns:
        dict с ключами: auto_reply_chance, quotes_enabled, voice_enabled, vision_enabled, games_enabled, pvp_accept_timeout
    """
    # Проверяем кэш
    if chat_id in _config_cache:
        return _config_cache[chat_id]
    
    # Дефолтные значения
    defaults = {
        "auto_reply_chance": 5,
        "quotes_enabled": True,
        "voice_enabled": True,
        "vision_enabled": True,
        "games_enabled": True,
        "pvp_accept_timeout": 120,  # 2 минуты
    }
    
    try:
        from app.database.models import BotConfig
        
        async with get_session()() as session:
            result = await session.execute(
                select(BotConfig).filter_by(chat_id=chat_id)
            )
            config = result.scalar_one_or_none()
            
            if config:
                result = {
                    "auto_reply_chance": config.auto_reply_chance,
                    "quotes_enabled": config.quotes_enabled,
                    "voice_enabled": config.voice_enabled,
                    "vision_enabled": config.vision_enabled,
                    "games_enabled": config.games_enabled,
                    "pvp_accept_timeout": getattr(config, 'pvp_accept_timeout', 120),
                }
                _config_cache[chat_id] = result
                return result
    except Exception as e:
        logger.warning(f"Failed to get bot config for chat {chat_id}: {e}")
    
    return defaults


def invalidate_cache(chat_id: int):
    """Сбросить кэш для чата."""
    _config_cache.pop(chat_id, None)


async def is_feature_enabled(chat_id: int, feature: str) -> bool:
    """
    Проверить включена ли функция.
    
    Args:
        chat_id: ID чата
        feature: quotes, voice, vision, games
    """
    config = await get_bot_config(chat_id)
    return config.get(f"{feature}_enabled", True)


async def get_pvp_accept_timeout(chat_id: int) -> int:
    """
    Получить время на принятие вызова в PvP/ПП (в секундах).
    
    Args:
        chat_id: ID чата
        
    Returns:
        Время в секундах (по умолчанию 120 = 2 минуты)
    """
    config = await get_bot_config(chat_id)
    return config.get("pvp_accept_timeout", 120)
