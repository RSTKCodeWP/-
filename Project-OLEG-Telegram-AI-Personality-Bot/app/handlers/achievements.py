import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from app.database.session import get_session
from app.database.models import User, UserAchievement, Achievement
from app.services.achievements import check_and_award_achievements

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("achievements"))
async def cmd_achievements(msg: Message):
    """Показать все доступные достижения."""
    async_session = get_session()
    async with async_session() as session:
        achievements_res = await session.execute(
            select(Achievement).order_by(Achievement.id)
        )
        achievements = achievements_res.scalars().all()

        if not achievements:
            return await msg.reply("🏆 Достижения пока не настроены.")

        text = "🏆 <b>Все достижения:</b>\n\n"
        for ach in achievements:
            text += f"{ach.name}\n<i>{ach.description}</i>\n\n"
        
        await msg.reply(text, parse_mode="HTML")


@router.message(Command("my_achievements", "myach"))
async def cmd_my_achievements(msg: Message):
    """Показать достижения пользователя."""
    user_id = msg.from_user.id
    
    # Сначала проверяем новые достижения
    new_achievements = await check_and_award_achievements(user_id)
    
    async_session = get_session()
    async with async_session() as session:
        user = await session.execute(
            select(User)
            .filter_by(tg_user_id=user_id)
            .options(joinedload(User.user_achievements).joinedload(UserAchievement.achievement))
        )
        user = user.scalars().first()

        if not user or not user.user_achievements:
            text = "🏆 У тебя пока нет достижений.\n\nИспользуй /achievements чтобы посмотреть все доступные."
            if new_achievements:
                text = f"🎉 <b>Новые достижения!</b>\n" + "\n".join(new_achievements) + "\n\n" + text
            return await msg.reply(text, parse_mode="HTML")

        # Считаем общее количество
        total = await session.scalar(select(func.count(Achievement.id)))
        unlocked = len(user.user_achievements)
        
        text = f"🏆 <b>Твои достижения ({unlocked}/{total}):</b>\n\n"
        
        if new_achievements:
            text = f"🎉 <b>Новые достижения!</b>\n" + "\n".join(new_achievements) + "\n\n" + text
        
        for ua in user.user_achievements:
            text += f"{ua.achievement.name}\n"
        
        await msg.reply(text, parse_mode="HTML")


@router.message(Command("achievements_leaderboard"))
async def cmd_achievements_leaderboard(msg: Message):
    """
    Displays a leaderboard of users with the most achievements.
    """
    async_session = get_session()
    async with async_session() as session:
        leaderboard_res = await session.execute(
            select(User, func.count(UserAchievement.user_id).label("achievement_count"))
            .join(UserAchievement)
            .group_by(User.id)
            .order_by(func.count(UserAchievement.user_id).desc())
            .limit(10)
        )
        leaderboard = leaderboard_res.all()

        if not leaderboard:
            return await msg.reply("Пока нет достижений для отображения в таблице лидеров.")

        leaderboard_list = ["Топ-10 по достижениям:"]
        for i, (user, count) in enumerate(leaderboard, start=1):
            name = user.username or user.first_name or str(user.tg_user_id)
            leaderboard_list.append(f"{i}. {name}: {count} достижений")
        
        await msg.reply("\n".join(leaderboard_list))