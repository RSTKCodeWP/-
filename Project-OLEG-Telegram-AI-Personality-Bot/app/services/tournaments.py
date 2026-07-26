"""
Tournament System - еженедельные турниры с призами.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import select, desc
from aiogram import Bot

from app.database.models import User, GameStat, UserBalance
from app.database.session import get_session
from app.utils import utc_now

logger = logging.getLogger(__name__)

# ID канала для объявлений (Steam Deck OC - Игры)
TOURNAMENT_CHANNEL_ID = -1002739723  # https://t.me/steamdeckoverclock/739723


class TournamentType(str, Enum):
    """Типы турниров."""
    PP_SIZE = "pp_size"  # Самый большой размер
    PP_GROWTH = "pp_growth"  # Наибольший рост за неделю
    PVP_WINS = "pvp_wins"  # Больше всего побед в PvP
    FISHING = "fishing"  # Больше всего рыбы поймано
    CASINO = "casino"  # Больше всего выигрышей в казино
    COINS_EARNED = "coins_earned"  # Больше всего монет заработано
    GAMES_PLAYED = "games_played"  # Больше всего игр сыграно


class TournamentDiscipline(str, Enum):
    """Дисциплины турниров для обновления очков."""
    GROW = "grow"
    PVP = "pvp"
    ROULETTE = "roulette"
    CASINO = "casino"
    FISHING = "fishing"


@dataclass
class TournamentConfig:
    """Конфигурация турнира."""
    type: TournamentType
    name: str
    description: str
    emoji: str
    prizes: List[int]  # Призы для топ-3
    duration_days: int = 7


# Конфигурации турниров
TOURNAMENT_CONFIGS = {
    TournamentType.PP_SIZE: TournamentConfig(
        type=TournamentType.PP_SIZE,
        name="Битва Титанов",
        description="Самый большой размер члена к концу недели",
        emoji="🍆",
        prizes=[5000, 3000, 1500]
    ),
    TournamentType.PP_GROWTH: TournamentConfig(
        type=TournamentType.PP_GROWTH,
        name="Гонка Роста",
        description="Наибольший прирост члена за неделю",
        emoji="📈",
        prizes=[4000, 2500, 1200]
    ),
    TournamentType.PVP_WINS: TournamentConfig(
        type=TournamentType.PVP_WINS,
        name="Арена Чемпионов",
        description="Больше всего побед в PvP за неделю",
        emoji="⚔️",
        prizes=[6000, 3500, 1800]
    ),
    TournamentType.FISHING: TournamentConfig(
        type=TournamentType.FISHING,
        name="Рыбацкий Турнир",
        description="Больше всего рыбы поймано за неделю",
        emoji="🎣",
        prizes=[3500, 2000, 1000]
    ),
    TournamentType.CASINO: TournamentConfig(
        type=TournamentType.CASINO,
        name="Казино Королей",
        description="Больше всего джекпотов за неделю",
        emoji="🎰",
        prizes=[7000, 4000, 2000]
    ),
}


@dataclass
class TournamentResult:
    """Результат турнира."""
    user_id: int
    username: str
    score: int
    rank: int
    prize: int


class TournamentService:
    """Сервис управления турнирами."""
    
    def __init__(self):
        self.current_tournament: Optional[TournamentType] = None
        self.tournament_start: Optional[datetime] = None
        self.tournament_end: Optional[datetime] = None
    
    async def start_weekly_tournament(self, bot: Bot) -> None:
        """Запустить еженедельный турнир."""
        # Выбираем случайный тип турнира
        import random
        tournament_type = random.choice(list(TOURNAMENT_CONFIGS.keys()))
        config = TOURNAMENT_CONFIGS[tournament_type]
        
        self.current_tournament = tournament_type
        self.tournament_start = utc_now()
        self.tournament_end = self.tournament_start + timedelta(days=config.duration_days)
        
        # Отправляем объявление в канал
        await self._announce_tournament_start(bot, config)
        
        logger.info(f"Started tournament: {config.name} ({tournament_type})")
    
    async def _announce_tournament_start(self, bot: Bot, config: TournamentConfig) -> None:
        """Объявить начало турнира в канале."""
        text = (
            f"{config.emoji} <b>ТУРНИР: {config.name}</b> {config.emoji}\n\n"
            f"📋 <b>Задание:</b> {config.description}\n\n"
            f"⏰ <b>Длительность:</b> {config.duration_days} дней\n\n"
            f"🏆 <b>Призы:</b>\n"
            f"  🥇 1 место: {config.prizes[0]:,} монет\n"
            f"  🥈 2 место: {config.prizes[1]:,} монет\n"
            f"  🥉 3 место: {config.prizes[2]:,} монет\n\n"
            f"💪 Участвуйте и побеждайте!\n"
            f"Проверить таблицу лидеров: /tournament"
        )
        
        try:
            await bot.send_message(
                chat_id=TOURNAMENT_CHANNEL_ID,
                text=text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to announce tournament: {e}")
    
    async def end_tournament(self, bot: Bot) -> List[TournamentResult]:
        """Завершить турнир и выдать призы."""
        if not self.current_tournament:
            return []
        
        config = TOURNAMENT_CONFIGS[self.current_tournament]
        
        # Получаем топ-3
        results = await self._get_tournament_results(self.current_tournament, limit=3)
        
        # Выдаём призы
        async_session = get_session()
        async with async_session() as session:
            for i, result in enumerate(results):
                if i < len(config.prizes):
                    prize = config.prizes[i]
                    result.prize = prize
                    
                    # Начисляем монеты
                    balance = await session.scalar(
                        select(UserBalance)
                        .where(
                            UserBalance.user_id == result.user_id,
                            UserBalance.chat_id == 0
                        )
                    )
                    if balance:
                        balance.balance += prize
                    else:
                        balance = UserBalance(user_id=result.user_id, chat_id=0, balance=prize)
                        session.add(balance)
            
            await session.commit()
        
        # Объявляем результаты
        await self._announce_tournament_end(bot, config, results)
        
        # Сбрасываем турнир
        self.current_tournament = None
        self.tournament_start = None
        self.tournament_end = None
        
        logger.info(f"Ended tournament: {config.name}")
        return results
    
    async def _announce_tournament_end(self, bot: Bot, config: TournamentConfig, 
                                       results: List[TournamentResult]) -> None:
        """Объявить результаты турнира в канале."""
        text = (
            f"{config.emoji} <b>ТУРНИР ЗАВЕРШЁН: {config.name}</b> {config.emoji}\n\n"
            f"🏆 <b>Победители:</b>\n\n"
        )
        
        medals = ["🥇", "🥈", "🥉"]
        for i, result in enumerate(results):
            if i < 3:
                text += (
                    f"{medals[i]} <b>{result.username}</b>\n"
                    f"   Результат: {result.score:,}\n"
                    f"   Приз: {result.prize:,} монет\n\n"
                )
        
        text += f"🎉 Поздравляем победителей!\n"
        text += f"Следующий турнир скоро..."
        
        try:
            await bot.send_message(
                chat_id=TOURNAMENT_CHANNEL_ID,
                text=text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to announce tournament results: {e}")
    
    async def _get_tournament_results(self, tournament_type: TournamentType, 
                                      limit: int = 10) -> List[TournamentResult]:
        """Получить результаты турнира."""
        async_session = get_session()
        async with async_session() as session:
            if tournament_type == TournamentType.PP_SIZE:
                # Топ по размеру PP
                result = await session.execute(
                    select(User, GameStat)
                    .join(GameStat, User.id == GameStat.user_id)
                    .order_by(desc(GameStat.size_cm))
                    .limit(limit)
                )
                rows = result.fetchall()
                return [
                    TournamentResult(
                        user_id=user.tg_user_id,
                        username=user.username or user.first_name or f"User{user.tg_user_id}",
                        score=game_stat.size_cm,
                        rank=i+1,
                        prize=0
                    )
                    for i, (user, game_stat) in enumerate(rows)
                ]
            
            elif tournament_type == TournamentType.PVP_WINS:
                # Топ по победам в PvP
                result = await session.execute(
                    select(User, GameStat)
                    .join(GameStat, User.id == GameStat.user_id)
                    .order_by(desc(GameStat.pvp_wins))
                    .limit(limit)
                )
                rows = result.fetchall()
                return [
                    TournamentResult(
                        user_id=user.tg_user_id,
                        username=user.username or user.first_name or f"User{user.tg_user_id}",
                        score=game_stat.pvp_wins,
                        rank=i+1,
                        prize=0
                    )
                    for i, (user, game_stat) in enumerate(rows)
                ]
            
            elif tournament_type == TournamentType.CASINO:
                # Топ по джекпотам
                result = await session.execute(
                    select(User, GameStat)
                    .join(GameStat, User.id == GameStat.user_id)
                    .order_by(desc(GameStat.casino_jackpots))
                    .limit(limit)
                )
                rows = result.fetchall()
                return [
                    TournamentResult(
                        user_id=user.tg_user_id,
                        username=user.username or user.first_name or f"User{user.tg_user_id}",
                        score=game_stat.casino_jackpots,
                        rank=i+1,
                        prize=0
                    )
                    for i, (user, game_stat) in enumerate(rows)
                ]
            
            # Для других типов турниров нужна дополнительная логика
            return []
    
    async def get_leaderboard(self, limit: int = 10) -> List[TournamentResult]:
        """Получить текущую таблицу лидеров."""
        if not self.current_tournament:
            return []
        
        return await self._get_tournament_results(self.current_tournament, limit)
    
    def is_active(self) -> bool:
        """Проверить, активен ли турнир."""
        if not self.current_tournament or not self.tournament_end:
            return False
        return utc_now() < self.tournament_end
    
    def get_time_remaining(self) -> Optional[timedelta]:
        """Получить оставшееся время турнира."""
        if not self.tournament_end:
            return None
        remaining = self.tournament_end - utc_now()
        return remaining if remaining.total_seconds() > 0 else timedelta(0)


# Singleton
tournament_service = TournamentService()
