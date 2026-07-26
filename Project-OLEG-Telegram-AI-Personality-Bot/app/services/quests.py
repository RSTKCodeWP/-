"""
Quest Service - ежедневные квесты и турниры.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Quest, UserQuest, User, UserBalance
from app.database.session import get_session
from app.utils import utc_now

logger = logging.getLogger(__name__)

# Базовые квесты
BASE_QUESTS = [
    # Сообщения
    {"code": "send_messages_5", "name": "📝 Общительный", "description": "Написать 5 сообщений", 
     "reward_type": "coins", "reward_amount": 50, "event_type": "message", "target_value": 5},
    {"code": "send_messages_20", "name": "💬 Болтун дня", "description": "Написать 20 сообщений",
     "reward_type": "coins", "reward_amount": 150, "event_type": "message", "target_value": 20},
    {"code": "send_messages_50", "name": "🗣️ Спамер", "description": "Написать 50 сообщений",
     "reward_type": "coins", "reward_amount": 300, "event_type": "message", "target_value": 50},
    
    # Игры
    {"code": "play_games_3", "name": "🎮 Игрок", "description": "Сыграть 3 игры",
     "reward_type": "coins", "reward_amount": 100, "event_type": "game", "target_value": 3},
    {"code": "play_games_10", "name": "🕹️ Геймер", "description": "Сыграть 10 игр",
     "reward_type": "coins", "reward_amount": 250, "event_type": "game", "target_value": 10},
    {"code": "play_games_25", "name": "👾 Хардкорщик", "description": "Сыграть 25 игр",
     "reward_type": "coins", "reward_amount": 500, "event_type": "game", "target_value": 25},
    
    # PvP
    {"code": "win_pvp_1", "name": "⚔️ Победитель", "description": "Выиграть PvP",
     "reward_type": "coins", "reward_amount": 200, "event_type": "pvp_win", "target_value": 1},
    {"code": "win_pvp_3", "name": "🏆 Доминатор", "description": "Выиграть 3 PvP",
     "reward_type": "coins", "reward_amount": 500, "event_type": "pvp_win", "target_value": 3},
    {"code": "win_pvp_5", "name": "👑 Чемпион", "description": "Выиграть 5 PvP",
     "reward_type": "coins", "reward_amount": 800, "event_type": "pvp_win", "target_value": 5},
    {"code": "win_pvp_10", "name": "⚡ Легенда", "description": "Выиграть 10 PvP",
     "reward_type": "coins", "reward_amount": 1500, "event_type": "pvp_win", "target_value": 10},
    
    # Рыбалка
    {"code": "catch_fish_3", "name": "🎣 Рыбак дня", "description": "Поймать 3 рыбы",
     "reward_type": "coins", "reward_amount": 100, "event_type": "fish", "target_value": 3},
    {"code": "catch_fish_10", "name": "🐟 Мастер удочки", "description": "Поймать 10 рыб",
     "reward_type": "coins", "reward_amount": 300, "event_type": "fish", "target_value": 10},
    {"code": "catch_fish_25", "name": "🦈 Акула рыбалки", "description": "Поймать 25 рыб",
     "reward_type": "coins", "reward_amount": 600, "event_type": "fish", "target_value": 25},
    {"code": "catch_rare_fish", "name": "✨ Редкий улов", "description": "Поймать редкую рыбу",
     "reward_type": "coins", "reward_amount": 400, "event_type": "fish_rare", "target_value": 1},
    
    # Казино
    {"code": "casino_plays_5", "name": "🎰 Азартный", "description": "Сыграть 5 раз в казино",
     "reward_type": "coins", "reward_amount": 100, "event_type": "casino", "target_value": 5},
    {"code": "casino_plays_15", "name": "🎲 Игроман", "description": "Сыграть 15 раз в казино",
     "reward_type": "coins", "reward_amount": 300, "event_type": "casino", "target_value": 15},
    {"code": "casino_win_3", "name": "💰 Везунчик", "description": "Выиграть 3 раза в казино",
     "reward_type": "coins", "reward_amount": 250, "event_type": "casino_win", "target_value": 3},
    {"code": "casino_jackpot", "name": "🎰 Джекпот!", "description": "Сорвать джекпот",
     "reward_type": "coins", "reward_amount": 1000, "event_type": "jackpot", "target_value": 1},
    
    # Цитаты
    {"code": "create_quote", "name": "💬 Цитатник", "description": "Создать цитату",
     "reward_type": "coins", "reward_amount": 50, "event_type": "quote", "target_value": 1},
    {"code": "create_quote_5", "name": "📜 Философ", "description": "Создать 5 цитат",
     "reward_type": "coins", "reward_amount": 200, "event_type": "quote", "target_value": 5},
    
    # Grow
    {"code": "grow_3", "name": "🌱 Садовод", "description": "Использовать /grow 3 раза",
     "reward_type": "coins", "reward_amount": 75, "event_type": "grow", "target_value": 3},
    {"code": "grow_10", "name": "🌿 Фермер", "description": "Использовать /grow 10 раз",
     "reward_type": "coins", "reward_amount": 250, "event_type": "grow", "target_value": 10},
    {"code": "grow_size_100", "name": "📏 Метровый", "description": "Достичь 100 см",
     "reward_type": "coins", "reward_amount": 500, "event_type": "size_milestone", "target_value": 100},
    {"code": "grow_size_500", "name": "🚀 Гигант", "description": "Достичь 500 см",
     "reward_type": "coins", "reward_amount": 2000, "event_type": "size_milestone", "target_value": 500},
    
    # Покупки
    {"code": "shop_buy_3", "name": "🛒 Покупатель", "description": "Купить 3 предмета",
     "reward_type": "coins", "reward_amount": 150, "event_type": "shop_buy", "target_value": 3},
    {"code": "shop_buy_10", "name": "💳 Шопоголик", "description": "Купить 10 предметов",
     "reward_type": "coins", "reward_amount": 400, "event_type": "shop_buy", "target_value": 10},
    
    # Петушиные бои
    {"code": "cockfight_3", "name": "🐔 Птицевод", "description": "Провести 3 петушиных боя",
     "reward_type": "coins", "reward_amount": 150, "event_type": "cockfight", "target_value": 3},
    {"code": "cockfight_win_5", "name": "🐓 Чемпион арены", "description": "Выиграть 5 петушиных боёв",
     "reward_type": "coins", "reward_amount": 400, "event_type": "cockfight_win", "target_value": 5},
    
    # Краш
    {"code": "crash_survive_2x", "name": "🚀 Осторожный", "description": "Забрать на 2x в крэше",
     "reward_type": "coins", "reward_amount": 200, "event_type": "crash_2x", "target_value": 1},
    {"code": "crash_survive_5x", "name": "💎 Рисковый", "description": "Забрать на 5x в крэше",
     "reward_type": "coins", "reward_amount": 500, "event_type": "crash_5x", "target_value": 1},
]

# Генератор динамических квестов
DYNAMIC_QUEST_TEMPLATES = [
    # Заработать монеты
    {"name": "💰 Заработок дня", "description": "Заработать {amount} монет", 
     "event_type": "coins_earned", "reward_multiplier": 0.5, "amounts": [500, 1000, 2000, 5000]},
    
    # Потратить монеты
    {"name": "💸 Транжира", "description": "Потратить {amount} монет",
     "event_type": "coins_spent", "reward_multiplier": 0.3, "amounts": [1000, 2500, 5000]},
    
    # Выиграть подряд
    {"name": "🔥 Серия побед", "description": "Выиграть {count} игр подряд",
     "event_type": "win_streak", "reward_multiplier": 200, "counts": [3, 5, 7]},
    
    # Размер PP
    {"name": "📏 Рост дня", "description": "Вырастить PP на {amount} см за день",
     "event_type": "pp_growth_daily", "reward_multiplier": 2, "amounts": [50, 100, 200]},
]


def generate_dynamic_quest() -> dict:
    """Generate a random dynamic quest."""
    template = random.choice(DYNAMIC_QUEST_TEMPLATES)
    
    if "amounts" in template:
        amount = random.choice(template["amounts"])
        reward = int(amount * template["reward_multiplier"])
        return {
            "code": f"dynamic_{template['event_type']}_{amount}",
            "name": template["name"],
            "description": template["description"].format(amount=amount),
            "reward_type": "coins",
            "reward_amount": reward,
            "event_type": template["event_type"],
            "target_value": amount
        }
    elif "counts" in template:
        count = random.choice(template["counts"])
        reward = int(count * template["reward_multiplier"])
        return {
            "code": f"dynamic_{template['event_type']}_{count}",
            "name": template["name"],
            "description": template["description"].format(count=count),
            "reward_type": "coins",
            "reward_amount": reward,
            "event_type": template["event_type"],
            "target_value": count
        }
    
    return template


# Объединяем все квесты
QUESTS = BASE_QUESTS


async def init_quests():
    """Инициализировать квесты в БД при старте."""
    async_session = get_session()
    async with async_session() as session:
        for quest_data in QUESTS:
            existing = await session.scalar(
                select(Quest).where(Quest.code == quest_data["code"])
            )
            if not existing:
                quest = Quest(**quest_data)
                session.add(quest)
                logger.info(f"Added quest: {quest_data['code']}")
        await session.commit()


async def assign_daily_quests(user_id: int, count: int = 3) -> list[Quest]:
    """
    Назначить ежедневные квесты пользователю.
    Удаляет старые незавершённые квесты и назначает новые (включая динамические).
    """
    async_session = get_session()
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.tg_user_id == user_id)
        )
        if not user:
            return []
        
        # Удаляем старые незавершённые квесты (старше 24 часов)
        yesterday = utc_now() - timedelta(hours=24)
        await session.execute(
            delete(UserQuest)
            .where(
                UserQuest.user_id == user.id,
                UserQuest.completed_at.is_(None),
                UserQuest.assigned_at < yesterday
            )
        )
        
        # Проверяем текущие активные квесты
        active = await session.execute(
            select(UserQuest)
            .where(
                UserQuest.user_id == user.id,
                UserQuest.completed_at.is_(None)
            )
        )
        active_quest_ids = {uq.quest_id for uq in active.scalars()}
        
        # Если уже есть активные квесты, не назначаем новые
        if len(active_quest_ids) >= count:
            return []
        
        # Получаем все базовые квесты
        all_quests = await session.execute(select(Quest))
        available = [q for q in all_quests.scalars() if q.id not in active_quest_ids]
        
        # Добавляем 1-2 динамических квеста
        dynamic_count = random.randint(1, 2)
        for _ in range(dynamic_count):
            dynamic_quest_data = generate_dynamic_quest()
            # Проверяем, не существует ли уже такой квест
            existing = await session.scalar(
                select(Quest).where(Quest.code == dynamic_quest_data["code"])
            )
            if not existing:
                dynamic_quest = Quest(**dynamic_quest_data)
                session.add(dynamic_quest)
                await session.flush()
                available.append(dynamic_quest)
        
        # Выбираем случайные
        to_assign_count = min(count - len(active_quest_ids), len(available))
        to_assign = random.sample(available, to_assign_count)
        
        assigned = []
        for quest in to_assign:
            uq = UserQuest(
                user_id=user.id,
                quest_id=quest.id,
                assigned_at=utc_now(),
                progress=0
            )
            session.add(uq)
            assigned.append(quest)
        
        await session.commit()
        return assigned


async def update_quest_progress(
    user_id: int,
    event_type: str,
    amount: int = 1
) -> list[tuple[str, int]]:
    """
    Обновить прогресс квестов по событию.
    
    Returns:
        Список (название квеста, награда) для завершённых квестов
    """
    async_session = get_session()
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.tg_user_id == user_id)
        )
        if not user:
            return []
        
        # Получаем активные квесты с нужным event_type
        result = await session.execute(
            select(UserQuest, Quest)
            .join(Quest)
            .where(
                UserQuest.user_id == user.id,
                UserQuest.completed_at.is_(None),
                Quest.event_type == event_type
            )
        )
        
        completed = []
        for uq, quest in result.fetchall():
            uq.progress += amount
            
            if uq.progress >= quest.target_value:
                uq.completed_at = utc_now()
                
                # Выдаём награду
                if quest.reward_type == "coins":
                    balance = await session.scalar(
                        select(UserBalance)
                        .where(
                            UserBalance.user_id == user_id,
                            UserBalance.chat_id == 0
                        )
                    )
                    if not balance:
                        balance = UserBalance(user_id=user_id, chat_id=0, balance=0)
                        session.add(balance)
                    balance.balance += quest.reward_amount
                
                completed.append((quest.name, quest.reward_amount))
                logger.info(f"User {user_id} completed quest {quest.code}")
        
        await session.commit()
        return completed


async def get_user_quests(user_id: int) -> list[tuple[Quest, UserQuest]]:
    """Получить активные квесты пользователя."""
    async_session = get_session()
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.tg_user_id == user_id)
        )
        if not user:
            return []
        
        result = await session.execute(
            select(Quest, UserQuest)
            .join(UserQuest)
            .where(
                UserQuest.user_id == user.id,
                UserQuest.completed_at.is_(None)
            )
        )
        return [(q, uq) for q, uq in result.fetchall()]


# Алиас для совместимости со старым кодом
async def check_and_update_quests(session, user, event_type: str):
    """
    Алиас для update_quest_progress для совместимости.
    
    Returns:
        Список завершённых квестов как объекты с name и reward_amount
    """
    from dataclasses import dataclass
    
    @dataclass
    class QuestResult:
        name: str
        reward_amount: int
        reward_type: str = "coins"
    
    completed = await update_quest_progress(user.tg_user_id, event_type)
    return [QuestResult(name=name, reward_amount=amount) for name, amount in completed]
