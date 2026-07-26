"""
Tournament Handlers - команды для турниров.
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from app.services.tournaments import tournament_service, TOURNAMENT_CONFIGS

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("tournament"))
async def cmd_tournament(message: Message):
    """Показать информацию о текущем турнире."""
    if not tournament_service.is_active():
        await message.reply(
            "🏆 <b>Турниры</b>\n\n"
            "Сейчас нет активных турниров.\n"
            "Следите за объявлениями в канале!",
            parse_mode="HTML"
        )
        return
    
    config = TOURNAMENT_CONFIGS[tournament_service.current_tournament]
    time_remaining = tournament_service.get_time_remaining()
    
    if time_remaining:
        days = time_remaining.days
        hours = time_remaining.seconds // 3600
        minutes = (time_remaining.seconds % 3600) // 60
        time_str = f"{days}д {hours}ч {minutes}м"
    else:
        time_str = "Завершается..."
    
    # Получаем таблицу лидеров
    leaderboard = await tournament_service.get_leaderboard(limit=10)
    
    text = (
        f"{config.emoji} <b>ТУРНИР: {config.name}</b> {config.emoji}\n\n"
        f"📋 <b>Задание:</b> {config.description}\n\n"
        f"⏰ <b>Осталось:</b> {time_str}\n\n"
        f"🏆 <b>Призы:</b>\n"
        f"  🥇 1 место: {config.prizes[0]:,} монет\n"
        f"  🥈 2 место: {config.prizes[1]:,} монет\n"
        f"  🥉 3 место: {config.prizes[2]:,} монет\n\n"
        f"📊 <b>Таблица лидеров:</b>\n\n"
    )
    
    medals = ["🥇", "🥈", "🥉"]
    for i, result in enumerate(leaderboard):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} {result.username}: {result.score:,}\n"
    
    if not leaderboard:
        text += "<i>Пока нет участников</i>\n"
    
    text += "\n💪 Участвуйте и побеждайте!"
    
    await message.reply(text, parse_mode="HTML")
