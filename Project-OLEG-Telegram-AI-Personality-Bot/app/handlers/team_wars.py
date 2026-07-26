import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select, and_, or_, or_
from sqlalchemy.orm import joinedload

from app.database.session import get_session
from app.database.models import User, Guild, GuildMember, TeamWar, TeamWarParticipant
from app.handlers.games import ensure_user # Reusing ensure_user from games handler
from app.utils import utc_now

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("war_declare"))
async def cmd_war_declare(msg: Message):
    """
    Handles the /war_declare command to declare war on another guild.
    Usage: /war_declare <defender_guild_name> <duration_hours>
    """
    async_session = get_session()
    declarer_user = await ensure_user(msg.from_user)

    parts = (msg.text or "").split(maxsplit=2)
    if len(parts) != 3:
        return await msg.reply("Использование: /war_declare <название_гильдии_защитника> <длительность_часы>")
    
    defender_guild_name = parts[1].strip()
    try:
        duration_hours = int(parts[2])
    except ValueError:
        return await msg.reply("Длительность войны должна быть числом в часах.")

    if duration_hours <= 0:
        return await msg.reply("Длительность войны должна быть положительным числом.")

    async with async_session() as session:
        # Check if declarer user is in a guild and is an owner
        declarer_member_res = await session.execute(
            select(GuildMember)
            .filter_by(user_id=declarer_user.id, role="leader")
            .options(joinedload(GuildMember.guild))
        )
        declarer_member = declarer_member_res.scalars().first()
        if not declarer_member:
            return await msg.reply("Вы должны быть лидером гильдии, чтобы объявлять войну.")
        
        declarer_guild = declarer_member.guild

        # Check if defender guild exists
        defender_guild_res = await session.execute(
            select(Guild).filter_by(name=defender_guild_name)
        )
        defender_guild = defender_guild_res.scalars().first()
        if not defender_guild:
            return await msg.reply(f"Гильдия '{defender_guild_name}' не найдена.")

        if declarer_guild.id == defender_guild.id:
            return await msg.reply("Вы не можете объявить войну своей собственной гильдии.")

        # Check for existing wars between these guilds
        existing_war_res = await session.execute(
            select(TeamWar).filter(
                and_(
                    TeamWar.status.in_(["declared", "active"]),
                    or_(
                        and_(TeamWar.declarer_guild_id == declarer_guild.id, TeamWar.defender_guild_id == defender_guild.id),
                        and_(TeamWar.declarer_guild_id == defender_guild.id, TeamWar.defender_guild_id == declarer_guild.id)
                    )
                )
            )
        )
        if existing_war_res.scalars().first():
            return await msg.reply("Между вашими гильдиями уже идет война или объявлена новая.")

        end_time = utc_now() + timedelta(hours=duration_hours)

        new_war = TeamWar(
            declarer_guild_id=declarer_guild.id,
            defender_guild_id=defender_guild.id,
            start_time=None, # Will be set upon acceptance
            end_time=end_time,
            status="declared"
        )
        session.add(new_war)
        await session.commit()
        await msg.reply(f"Ваша гильдия '{declarer_guild.name}' объявила войну гильдии '{defender_guild.name}'! "
                        f"Война продлится {duration_hours} часов после принятия.")
        # Notify defender guild leader
        defender_leader_res = await session.execute(
            select(User)
            .join(GuildMember)
            .filter(and_(GuildMember.guild_id == defender_guild.id, GuildMember.role == "leader"))
        )
        defender_leader = defender_leader_res.scalars().first()
        if defender_leader:
            await msg.bot.send_message(
                chat_id=defender_leader.tg_user_id,
                text=f"Гильдия '{declarer_guild.name}' объявила войну вашей гильдии! "
                     f"Используйте /war_accept {declarer_guild.name} для принятия или проигнорируйте."
            )


@router.message(Command("war_accept"))
async def cmd_war_accept(msg: Message):
    """
    Handles the /war_accept command to accept a war declaration.
    Usage: /war_accept <declarer_guild_name>
    """
    async_session = get_session()
    defender_user = await ensure_user(msg.from_user)

    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) != 2:
        return await msg.reply("Использование: /war_accept <название_гильдии_объявившей_войну>")
    
    declarer_guild_name = parts[1].strip()

    async with async_session() as session:
        # Check if defender user is in a guild and is an owner
        defender_member_res = await session.execute(
            select(GuildMember)
            .filter_by(user_id=defender_user.id, role="leader")
            .options(joinedload(GuildMember.guild))
        )
        defender_member = defender_member_res.scalars().first()
        if not defender_member:
            return await msg.reply("Вы должны быть лидером гильдии, чтобы принять войну.")
        
        defender_guild = defender_member.guild

        # Find declarer guild
        declarer_guild_res = await session.execute(
            select(Guild).filter_by(name=declarer_guild_name)
        )
        declarer_guild = declarer_guild_res.scalars().first()
        if not declarer_guild:
            return await msg.reply(f"Гильдия '{declarer_guild_name}' не найдена.")
        
        # Find the declared war
        war_res = await session.execute(
            select(TeamWar).filter(
                and_(
                    TeamWar.declarer_guild_id == declarer_guild.id,
                    TeamWar.defender_guild_id == defender_guild.id,
                    TeamWar.status == "declared"
                )
            )
        )
        war = war_res.scalars().first()

        if not war:
            return await msg.reply("Объявленная война от этой гильдии не найдена.")

        war.status = "active"
        war.start_time = utc_now()
        await session.commit()
        await msg.reply(f"Вы приняли войну от гильдии '{declarer_guild.name}'. Война началась!")
        # Notify declarer guild leader
        declarer_leader_res = await session.execute(
            select(User)
            .join(GuildMember)
            .filter(and_(GuildMember.guild_id == declarer_guild.id, GuildMember.role == "leader"))
        )
        declarer_leader = declarer_leader_res.scalars().first()
        if declarer_leader:
            await msg.bot.send_message(
                chat_id=declarer_leader.tg_user_id,
                text=f"Гильдия '{defender_guild.name}' приняла вашу войну! Война началась!"
            )


@router.message(Command("war_info"))
async def cmd_war_info(msg: Message):
    """
    Handles the /war_info command to display information about ongoing wars.
    """
    async_session = get_session()
    user = await ensure_user(msg.from_user)

    async with async_session() as session:
        # Check if user is in a guild
        member_res = await session.execute(
            select(GuildMember)
            .filter_by(user_id=user.id)
            .options(joinedload(GuildMember.guild))
        )
        guild_member = member_res.scalars().first()

        if not guild_member:
            return await msg.reply("Вы не состоите ни в какой гильдии, чтобы просматривать информацию о войнах.")
        
        user_guild = guild_member.guild

        # Find active or declared wars involving this guild
        wars_res = await session.execute(
            select(TeamWar)
            .filter(
                and_(
                    TeamWar.status.in_(["declared", "active"]),
                    or_(TeamWar.declarer_guild_id == user_guild.id, TeamWar.defender_guild_id == user_guild.id)
                )
            )
            .options(
                joinedload(TeamWar.declarer_guild),
                joinedload(TeamWar.defender_guild)
            )
        )
        wars = wars_res.scalars().all()

        if not wars:
            return await msg.reply("В данный момент нет активных или объявленных войн с участием вашей гильдии.")
        
        war_info_list = ["Информация о войнах:"]
        for war in wars:
            status = "Объявлена" if war.status == "declared" else "Активна"
            start_time = war.start_time.strftime('%Y-%m-%d %H:%M') if war.start_time else "Не началась"
            end_time = war.end_time.strftime('%Y-%m-%d %H:%M') if war.end_time else "Неизвестно"
            
            war_info_list.append(
                f"ID Войны: {war.id} | Статус: {status}\n"
                f"Объявитель: {war.declarer_guild.name} vs Защитник: {war.defender_guild.name}\n"
                f"Начало: {start_time} | Конец: {end_time}\n"
            )
        await msg.reply("\n".join(war_info_list))