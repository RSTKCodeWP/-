import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select, and_, delete
from sqlalchemy.orm import joinedload
from datetime import datetime

from app.database.session import get_session
from app.database.models import User, Guild, GuildMember
from app.handlers.games import ensure_user # Reusing ensure_user from games handler
from app.utils import utc_now

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("create_guild"))
async def cmd_create_guild(msg: Message):
    """
    Handles the /create_guild command to create a new guild.
    Usage: /create_guild <guild_name>
    """
    async_session = get_session()
    user = await ensure_user(msg.from_user)

    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) != 2:
        return await msg.reply("Использование: /create_guild <название_гильдии>")
    
    guild_name = parts[1].strip()
    if not guild_name:
        return await msg.reply("Название гильдии не может быть пустым.")

    async with async_session() as session:
        # Check if user is already in a guild
        member_res = await session.execute(select(GuildMember).filter_by(user_id=user.id))
        if member_res.scalars().first():
            return await msg.reply("Вы уже состоите в гильдии.")
        
        # Check if guild name already exists
        guild_res = await session.execute(select(Guild).filter_by(name=guild_name))
        if guild_res.scalars().first():
            return await msg.reply("Гильдия с таким названием уже существует.")
        
        new_guild = Guild(
            name=guild_name,
            owner_user_id=user.id,
            created_at=utc_now()
        )
        session.add(new_guild)
        await session.flush() # To get guild_id

        new_guild_member = GuildMember(
            guild_id=new_guild.id,
            user_id=user.id,
            joined_at=utc_now(),
            role="leader"
        )
        session.add(new_guild_member)
        await session.commit()
        await msg.reply(f"Гильдия '{guild_name}' успешно создана! Вы ее лидер.")


@router.message(Command("join_guild"))
async def cmd_join_guild(msg: Message):
    """
    Handles the /join_guild command to join an existing guild.
    Usage: /join_guild <guild_name>
    """
    async_session = get_session()
    user = await ensure_user(msg.from_user)

    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) != 2:
        return await msg.reply("Использование: /join_guild <название_гильдии>")
    
    guild_name = parts[1].strip()
    if not guild_name:
        return await msg.reply("Название гильдии не может быть пустым.")

    async with async_session() as session:
        # Check if user is already in a guild
        member_res = await session.execute(select(GuildMember).filter_by(user_id=user.id))
        if member_res.scalars().first():
            return await msg.reply("Вы уже состоите в гильдии.")
        
        # Find the guild
        guild_res = await session.execute(select(Guild).filter_by(name=guild_name))
        guild = guild_res.scalars().first()
        if not guild:
            return await msg.reply("Гильдия с таким названием не найдена.")
        
        # Add user to guild
        new_guild_member = GuildMember(
            guild_id=guild.id,
            user_id=user.id,
            joined_at=utc_now(),
            role="member"
        )
        session.add(new_guild_member)
        await session.commit()
        await msg.reply(f"Вы успешно присоединились к гильдии '{guild_name}'.")


@router.message(Command("leave_guild"))
async def cmd_leave_guild(msg: Message):
    """
    Handles the /leave_guild command for a user to leave their current guild.
    """
    async_session = get_session()
    user = await ensure_user(msg.from_user)

    async with async_session() as session:
        member_res = await session.execute(
            select(GuildMember)
            .filter_by(user_id=user.id)
            .options(joinedload(GuildMember.guild))
        )
        guild_member = member_res.scalars().first()

        if not guild_member:
            return await msg.reply("Вы не состоите ни в какой гильдии.")
        
        guild = guild_member.guild
        if guild.owner_user_id == user.id:
            # If owner leaves, delete guild and all members
            await session.delete(guild_member)
            await session.execute(delete(GuildMember).filter_by(guild_id=guild.id))
            await session.delete(guild)
            await session.commit()
            return await msg.reply(f"Вы покинули гильдию '{guild.name}'. Так как вы были лидером, гильдия расформирована.")
        else:
            await session.delete(guild_member)
            await session.commit()
            return await msg.reply(f"Вы покинули гильдию '{guild.name}'.")


@router.message(Command("guild_info"))
async def cmd_guild_info(msg: Message):
    """
    Handles the /guild_info command to display information about the user's guild.
    """
    async_session = get_session()
    user = await ensure_user(msg.from_user)

    async with async_session() as session:
        guild_member_res = await session.execute(
            select(GuildMember)
            .filter_by(user_id=user.id)
            .options(
                joinedload(GuildMember.guild).joinedload(Guild.owner),
                joinedload(GuildMember.guild).joinedload(Guild.members).joinedload(GuildMember.user)
            )
        )
        guild_member = guild_member_res.scalars().first()

        if not guild_member:
            return await msg.reply("Вы не состоите ни в какой гильдии.")
        
        guild = guild_member.guild
        owner_name = guild.owner.username or guild.owner.first_name or str(guild.owner.tg_user_id)
        
        members_list = []
        for member in guild.members:
            member_name = member.user.username or member.user.first_name or str(member.user.tg_user_id)
            members_list.append(f"- {member_name} ({member.role})")
        
        guild_info_text = (
            f"🛡️ Гильдия: {guild.name}\n"
            f"👑 Лидер: {owner_name}\n"
            f"👥 Участники ({len(guild.members)}):\n" + "\n".join(members_list)
        )
        await msg.reply(guild_info_text)


@router.message(Command("guild_war"))
async def cmd_guild_war(msg: Message):
    """
    Handles the /guild_war command to declare war on another guild.
    Usage: /guild_war <guild_name> [hours]
    """
    import random
    async_session = get_session()
    user = await ensure_user(msg.from_user)

    parts = (msg.text or "").split()
    if len(parts) < 2:
        return await msg.reply("Использование: /guild_war <название_гильдии> [часы]")
    
    target_guild_name = parts[1].strip()
    war_hours = 24  # Default war duration
    if len(parts) >= 3:
        try:
            war_hours = int(parts[2])
            war_hours = max(1, min(72, war_hours))  # Limit 1-72 hours
        except ValueError:
            pass

    async with async_session() as session:
        # Check if user is in a guild and is leader
        member_res = await session.execute(
            select(GuildMember)
            .filter_by(user_id=user.id)
            .options(joinedload(GuildMember.guild).joinedload(Guild.members))
        )
        guild_member = member_res.scalars().first()

        if not guild_member:
            return await msg.reply("Вы не состоите ни в какой гильдии.")
        
        if guild_member.role != "leader":
            return await msg.reply("Только лидер гильдии может объявлять войну.")
        
        attacker_guild = guild_member.guild
        
        # Find target guild
        target_res = await session.execute(
            select(Guild)
            .filter_by(name=target_guild_name)
            .options(joinedload(Guild.members))
        )
        target_guild = target_res.scalars().first()
        
        if not target_guild:
            return await msg.reply(f"Гильдия '{target_guild_name}' не найдена.")
        
        if target_guild.id == attacker_guild.id:
            return await msg.reply("Нельзя объявить войну своей гильдии.")
        
        # Calculate guild power (sum of member count + random factor)
        attacker_power = len(attacker_guild.members) * 10 + random.randint(1, 50)
        defender_power = len(target_guild.members) * 10 + random.randint(1, 50)
        
        # Determine winner
        if attacker_power > defender_power:
            winner = attacker_guild.name
            loser = target_guild.name
            result_text = f"🏆 Гильдия '{winner}' победила в войне против '{loser}'!"
        elif defender_power > attacker_power:
            winner = target_guild.name
            loser = attacker_guild.name
            result_text = f"🏆 Гильдия '{winner}' отразила атаку '{loser}'!"
        else:
            result_text = f"⚔️ Война между '{attacker_guild.name}' и '{target_guild.name}' закончилась ничьей!"
        
        await msg.reply(
            f"⚔️ <b>Война гильдий!</b>\n\n"
            f"🛡️ {attacker_guild.name} (сила: {attacker_power})\n"
            f"⚔️ vs\n"
            f"🛡️ {target_guild.name} (сила: {defender_power})\n\n"
            f"{result_text}",
            parse_mode="HTML"
        )
        logger.info(f"Guild war: {attacker_guild.name} vs {target_guild.name}")
