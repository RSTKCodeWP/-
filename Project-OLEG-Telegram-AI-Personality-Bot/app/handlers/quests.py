import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.services.quests import get_user_quests, assign_daily_quests

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("quests", "квесты"))
async def cmd_quests(msg: Message):
    """Показать активные квесты пользователя."""
    user_id = msg.from_user.id
    
    # Получаем квесты
    quests = await get_user_quests(user_id)
    
    # Если нет квестов - назначаем новые
    if not quests:
        assigned = await assign_daily_quests(user_id, count=3)
        if assigned:
            quests = await get_user_quests(user_id)
    
    if not quests:
        return await msg.reply("📜 Квесты временно недоступны. Попробуй позже!")
    
    text = "📜 <b>Твои ежедневные квесты:</b>\n\n"
    
    for quest, user_quest in quests:
        progress_pct = min(100, int((user_quest.progress / quest.target_value) * 100))
        filled = progress_pct // 10
        bar = "█" * filled + "░" * (10 - filled)
        
        status = f"{user_quest.progress}/{quest.target_value}"
        reward = f"🎁 {quest.reward_amount} монет"
        
        text += f"<b>{quest.name}</b>\n"
        text += f"{quest.description}\n"
        text += f"[{bar}] {status}\n"
        text += f"{reward}\n\n"
    
    text += "<i>Квесты обновляются каждые 24 часа</i>"
    
    await msg.reply(text, parse_mode="HTML")


@router.message(Command("quest_progress"))
async def cmd_quest_progress(msg: Message):
    """Детальный прогресс по квестам (алиас для /quests)."""
    await cmd_quests(msg)