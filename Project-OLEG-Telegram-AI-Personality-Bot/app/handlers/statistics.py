import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from datetime import datetime, timedelta

from app.database.session import get_session
from app.database.models import GlobalStats
from app.utils import utc_now

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("stats"))
async def cmd_stats(msg: Message):
    """
    Displays overall daily statistics.
    """
    async_session = get_session()
    async with async_session() as session:
        today = utc_now().date()
        yesterday = today - timedelta(days=1)

        today_stats_res = await session.execute(
            select(GlobalStats)
            .filter(GlobalStats.date == today, GlobalStats.period_type == "daily")
        )
        today_stats = today_stats_res.scalars().first()

        if not today_stats:
            return await msg.reply("Статистика за сегодня пока не доступна.")
        
        # Optionally, fetch yesterday's stats to show deltas clearly if not already embedded
        yesterday_stats_res = await session.execute(
            select(GlobalStats)
            .filter(GlobalStats.date == yesterday, GlobalStats.period_type == "daily")
        )
        yesterday_stats = yesterday_stats_res.scalars().first()


        stats_text = (
            f"📊 Ежедневная статистика за {today.strftime('%Y-%m-%d')}:\n\n"
            f"Победы в PvP:\n"
            f"  Всего: {today_stats.total_pvp_wins}\n"
            f"  За день: {today_stats.pvp_wins_delta}\n\n"
            f"Выращивания:\n"
            f"  Всего: {today_stats.total_grow_count}\n"
            f"  За день: {today_stats.grow_count_delta}\n\n"
            f"Джекпоты казино:\n"
            f"  Всего: {today_stats.total_casino_jackpots}\n"
            f"  За день: {today_stats.casino_jackpots_delta}\n\n"
            f"Репутация:\n"
            f"  Всего: {today_stats.total_reputation}\n"
            f"  За день: {today_stats.reputation_delta}\n"
        )
        await msg.reply(stats_text)