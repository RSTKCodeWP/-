"""
Achievement Service - автоматическая выдача достижений.
"""

import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Achievement, UserAchievement, User, GameStat, MessageLog
from app.database.session import get_session
from app.utils import utc_now

logger = logging.getLogger(__name__)

# Определения достижений
ACHIEVEMENTS = [
    # Общение
    {"code": "first_message", "name": "🗣 Первое слово", "description": "Написать первое сообщение"},
    {"code": "chatterbox", "name": "💬 Болтун", "description": "Написать 100 сообщений"},
    {"code": "storyteller", "name": "📚 Рассказчик", "description": "Написать 1000 сообщений"},
    {"code": "legend", "name": "🏛 Легенда чата", "description": "Написать 10000 сообщений"},
    
    # Игры - размер
    {"code": "grower", "name": "🌱 Растущий", "description": "Достичь 10 см"},
    {"code": "average", "name": "📏 Средний", "description": "Достичь 15 см"},
    {"code": "big_boy", "name": "🍆 Большой парень", "description": "Достичь 25 см"},
    {"code": "monster", "name": "👹 Монстр", "description": "Достичь 50 см"},
    {"code": "titan", "name": "🗿 Титан", "description": "Достичь 100 см"},
    
    # PvP
    {"code": "first_blood", "name": "🩸 Первая кровь", "description": "Выиграть первый PvP"},
    {"code": "fighter", "name": "⚔️ Боец", "description": "Выиграть 10 PvP"},
    {"code": "warrior", "name": "🛡 Воин", "description": "Выиграть 50 PvP"},
    {"code": "champion", "name": "🏆 Чемпион", "description": "Выиграть 100 PvP"},
    
    # Казино
    {"code": "gambler", "name": "🎰 Игрок", "description": "Сыграть в казино 10 раз"},
    {"code": "high_roller", "name": "💎 Хайроллер", "description": "Выиграть 10000 монет за раз"},
    {"code": "jackpot", "name": "🎉 Джекпот!", "description": "Сорвать джекпот"},
    
    # Социальные
    {"code": "quoter", "name": "💬 Цитатник", "description": "Создать 10 цитат"},
    {"code": "popular", "name": "⭐ Популярный", "description": "Получить 50 реакций на цитаты"},
    {"code": "married", "name": "💍 В браке", "description": "Вступить в брак"},
    
    # Рыбалка
    {"code": "fisherman", "name": "🎣 Рыбак", "description": "Поймать 10 рыб"},
    {"code": "master_angler", "name": "🐟 Мастер рыбалки", "description": "Поймать 100 рыб"},
    {"code": "legendary_catch", "name": "🐋 Легендарный улов", "description": "Поймать легендарную рыбу"},
]


async def init_achievements():
    """Инициализировать достижения в БД при старте."""
    async_session = get_session()
    async with async_session() as session:
        for ach_data in ACHIEVEMENTS:
            existing = await session.scalar(
                select(Achievement).where(Achievement.code == ach_data["code"])
            )
            if not existing:
                ach = Achievement(**ach_data)
                session.add(ach)
                logger.info(f"Added achievement: {ach_data['code']}")
        await session.commit()


async def check_and_award_achievements(
    session_or_user_id,
    bot_or_session=None,
    user=None,
    game_stat=None,
    event_type: str = None
) -> list[str]:
    """
    Проверить и выдать достижения пользователю.
    
    Поддерживает два варианта вызова:
    1. check_and_award_achievements(user_id) - новый стиль
    2. check_and_award_achievements(session, bot, user, gs, event) - старый стиль
    
    Returns:
        Список названий новых достижений
    """
    # Определяем стиль вызова
    if isinstance(session_or_user_id, int):
        # Новый стиль: просто user_id
        user_id = session_or_user_id
        session = bot_or_session
    else:
        # Старый стиль: session, bot, user, gs, event
        if user is None:
            return []
        user_id = user.tg_user_id
        session = None  # Создадим новую
    
    close_session = False
    if session is None:
        async_session = get_session()
        session = async_session()
        close_session = True
    
    awarded = []
    
    try:
        # Получаем пользователя
        user = await session.scalar(
            select(User).where(User.tg_user_id == user_id)
        )
        if not user:
            return []
        
        # Получаем уже полученные достижения
        existing = await session.execute(
            select(UserAchievement.achievement_id)
            .where(UserAchievement.user_id == user.id)
        )
        existing_ids = {row[0] for row in existing.fetchall()}
        
        # Получаем все достижения
        all_achievements = await session.execute(select(Achievement))
        achievements_map = {a.code: a for a in all_achievements.scalars()}
        
        # Получаем статистику
        game_stat = await session.scalar(
            select(GameStat).where(GameStat.tg_user_id == user_id)
        )
        
        # Считаем сообщения
        from sqlalchemy import func
        msg_count = await session.scalar(
            select(func.count(MessageLog.id))
            .where(MessageLog.user_id == user_id)
        ) or 0
        
        # Проверяем достижения
        checks = [
            ("first_message", msg_count >= 1),
            ("chatterbox", msg_count >= 100),
            ("storyteller", msg_count >= 1000),
            ("legend", msg_count >= 10000),
        ]
        
        if game_stat:
            checks.extend([
                ("grower", game_stat.size_cm >= 10),
                ("average", game_stat.size_cm >= 15),
                ("big_boy", game_stat.size_cm >= 25),
                ("monster", game_stat.size_cm >= 50),
                ("titan", game_stat.size_cm >= 100),
                ("first_blood", game_stat.pvp_wins >= 1),
                ("fighter", game_stat.pvp_wins >= 10),
                ("warrior", game_stat.pvp_wins >= 50),
                ("champion", game_stat.pvp_wins >= 100),
                ("jackpot", game_stat.casino_jackpots >= 1),
            ])
        
        # Выдаём достижения
        for code, condition in checks:
            if code in achievements_map and condition:
                ach = achievements_map[code]
                if ach.id not in existing_ids:
                    ua = UserAchievement(
                        user_id=user.id,
                        achievement_id=ach.id,
                        unlocked_at=utc_now()
                    )
                    session.add(ua)
                    awarded.append(ach.name)
                    existing_ids.add(ach.id)
                    logger.info(f"Awarded achievement {code} to user {user_id}")
        
        if awarded:
            await session.commit()
        
        return awarded
        
    finally:
        if close_session:
            await session.close()


async def award_achievement(user_id: int, code: str) -> Optional[str]:
    """Выдать конкретное достижение пользователю."""
    async_session = get_session()
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.tg_user_id == user_id)
        )
        if not user:
            return None
        
        ach = await session.scalar(
            select(Achievement).where(Achievement.code == code)
        )
        if not ach:
            return None
        
        # Проверяем что ещё нет
        existing = await session.scalar(
            select(UserAchievement)
            .where(
                UserAchievement.user_id == user.id,
                UserAchievement.achievement_id == ach.id
            )
        )
        if existing:
            return None
        
        ua = UserAchievement(
            user_id=user.id,
            achievement_id=ach.id,
            unlocked_at=utc_now()
        )
        session.add(ua)
        await session.commit()
        
        logger.info(f"Awarded achievement {code} to user {user_id}")
        return ach.name
