import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import joinedload

from app.database.session import get_session
from app.database.models import User, GameStat, DuoTeam, DuoStat
from app.handlers.games import ensure_user # Reusing ensure_user from games handler
from app.services.duos import update_duo_elo

logger = logging.getLogger(__name__)

# Default ELO rating for new duos
DEFAULT_RATING = 1000

router = Router()


@router.message(Command("duo_invite", "create_duo"))
async def cmd_duo_invite(msg: Message):
    """
    Invites another player to form a duo.
    Usage: /duo_invite <@username> or /create_duo <@username>
    """
    async_session = get_session()
    user = await ensure_user(msg.from_user)

    parts = (msg.text or "").split()
    if len(parts) != 2 or not parts[1].startswith("@"):
        return await msg.reply("Использование: /duo_invite <@ник_игрока>")
    
    invited_username = parts[1][1:]

    async with async_session() as session:
        # Check if inviting user is already in a duo
        existing_duo_res = await session.execute(
            select(DuoTeam)
            .filter(or_(DuoTeam.user1_id == user.id, DuoTeam.user2_id == user.id))
        )
        if existing_duo_res.scalars().first():
            return await msg.reply("Вы уже состоите в дуэте.")

        # Find the invited user
        invited_user_res = await session.execute(select(User).filter_by(username=invited_username))
        invited_user = invited_user_res.scalars().first()
        if not invited_user:
            return await msg.reply(f"Пользователь @{invited_username} не найден.")
        
        if invited_user.id == user.id:
            return await msg.reply("Вы не можете пригласить самого себя в дуэт.")

        # Check if invited user is already in a duo
        invited_duo_res = await session.execute(
            select(DuoTeam)
            .filter(or_(DuoTeam.user1_id == invited_user.id, DuoTeam.user2_id == invited_user.id))
        )
        if invited_duo_res.scalars().first():
            return await msg.reply(f"Пользователь @{invited_username} уже состоит в дуэте.")

        # Store the invitation (for simplicity, we'll use a temporary mechanism or directly create if accepted)
        # For a real system, you'd store pending invitations. For now, we'll just send a message.
        await msg.reply(f"Приглашение отправлено @{invited_username}. Он(а) может принять его командой: /duo_accept @{user.username or str(user.tg_user_id)}")
        
        # Notify invited user
        await msg.bot.send_message(
            chat_id=invited_user.tg_user_id,
            text=f"Вам пришло приглашение в дуэт от @{user.username or str(user.tg_user_id)}. "
                 f"Чтобы принять, используйте /duo_accept @{user.username or str(user.tg_user_id)}"
        )


@router.message(Command("duo_accept"))
async def cmd_duo_accept(msg: Message):
    """
    Accepts a duo invitation.
    Usage: /duo_accept <@inviting_username>
    """
    async_session = get_session()
    user = await ensure_user(msg.from_user)

    parts = (msg.text or "").split()
    if len(parts) != 2 or not parts[1].startswith("@"):
        return await msg.reply("Использование: /duo_accept <@ник_пригласившего_игрока>")
    
    inviting_username = parts[1][1:]

    async with async_session() as session:
        # Check if accepting user is already in a duo
        existing_duo_res = await session.execute(
            select(DuoTeam)
            .filter(or_(DuoTeam.user1_id == user.id, DuoTeam.user2_id == user.id))
        )
        if existing_duo_res.scalars().first():
            return await msg.reply("Вы уже состоите в дуэте.")

        # Find the inviting user
        inviting_user_res = await session.execute(select(User).filter_by(username=inviting_username))
        inviting_user = inviting_user_res.scalars().first()
        if not inviting_user:
            return await msg.reply(f"Пользователь @{inviting_username} не найден.")
        
        if inviting_user.id == user.id:
            return await msg.reply("Вы не можете принять приглашение от самого себя.")

        # Check if inviting user is still available
        inviting_duo_res = await session.execute(
            select(DuoTeam)
            .filter(or_(DuoTeam.user1_id == inviting_user.id, DuoTeam.user2_id == inviting_user.id))
        )
        if inviting_duo_res.scalars().first():
            return await msg.reply(f"Пользователь @{inviting_username} уже состоит в дуэте или его приглашение устарело.")

        # Create the duo
        user1_id = min(user.id, inviting_user.id)
        user2_id = max(user.id, inviting_user.id)
        
        new_duo_team = DuoTeam(user1_id=user1_id, user2_id=user2_id)
        session.add(new_duo_team)
        await session.flush() # To get duo_team_id
        
        # Create initial DuoStat
        new_duo_stat = DuoStat(duo_team_id=new_duo_team.id, rating=DEFAULT_RATING)
        session.add(new_duo_stat)

        await session.commit()
        await msg.reply(f"Вы успешно сформировали дуэт с @{inviting_username}!")
        await msg.bot.send_message(
            chat_id=inviting_user.tg_user_id,
            text=f"@{user.username or str(user.tg_user_id)} принял(а) ваше приглашение в дуэт!"
        )


@router.message(Command("duo_leave"))
async def cmd_duo_leave(msg: Message):
    """
    Leaves the current duo.
    """
    async_session = get_session()
    user = await ensure_user(msg.from_user)

    async with async_session() as session:
        duo_team_res = await session.execute(
            select(DuoTeam)
            .filter(or_(DuoTeam.user1_id == user.id, DuoTeam.user2_id == user.id))
            .options(joinedload(DuoTeam.stats))
        )
        duo_team = duo_team_res.scalars().first()

        if not duo_team:
            return await msg.reply("Вы не состоите ни в каком дуэте.")
        
        # Delete DuoStat first due to foreign key constraint
        if duo_team.stats:
            await session.delete(duo_team.stats)
        await session.delete(duo_team)
        await session.commit()
        await msg.reply("Вы покинули дуэт. Дуэт расформирован.")


@router.message(Command("pvp_duo", "duo_pvp"))
async def cmd_pvp_duo(msg: Message):
    """
    Initiates a 2v2 PvP duel.
    Usage: /pvp_duo <@opponent1> <@opponent2> or /duo_pvp (or reply to one opponent)
    """
    import random
    async_session = get_session()
    user = await ensure_user(msg.from_user)

    async with async_session() as session:
        # Determine user's duo
        user_duo_res = await session.execute(
            select(DuoTeam)
            .filter(or_(DuoTeam.user1_id == user.id, DuoTeam.user2_id == user.id))
            .options(joinedload(DuoTeam.stats))
        )
        user_duo = user_duo_res.scalars().first()
        if not user_duo:
            return await msg.reply("Для участия в дуэтных PvP вы должны состоять в дуэте.")
    
        user_duo_member_ids = {user_duo.user1_id, user_duo.user2_id}

        # Identify opponents (can be complex, for simplicity, expect two usernames)
        opponent_usernames = []
        if msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.username:
            opponent_usernames.append(msg.reply_to_message.from_user.username)
            # If reply, expect second opponent in message text
            parts = (msg.text or "").split()
            if len(parts) >= 2 and parts[1].startswith("@"):
                opponent_usernames.append(parts[1][1:])
        else:
            parts = (msg.text or "").split()
            if len(parts) >= 3 and parts[1].startswith("@") and parts[2].startswith("@"):
                opponent_usernames.append(parts[1][1:])
                opponent_usernames.append(parts[2][1:])
        
        if len(opponent_usernames) != 2:
            return await msg.reply("Использование: /duo_pvp <@оппонент1> <@оппонент2> (или ответьте на сообщение одного оппонента и укажите второго).")
        
        # Find opponent users
        opponent_users_res = await session.execute(
            select(User).filter(User.username.in_(opponent_usernames))
        )
        opponent_users = opponent_users_res.scalars().all()
        if len(opponent_users) != 2:
            return await msg.reply("Один или оба пользователя-оппонента не найдены.")
        
        opponent_user_ids = {u.id for u in opponent_users}

        # Find opponent duo
        opponent_duo_res = await session.execute(
            select(DuoTeam)
            .filter(and_(DuoTeam.user1_id.in_(opponent_user_ids), DuoTeam.user2_id.in_(opponent_user_ids)))
            .options(joinedload(DuoTeam.stats))
        )
        opponent_duo = opponent_duo_res.scalars().first()
        if not opponent_duo:
            return await msg.reply("Оппоненты не образуют действующий дуэт.")

        if user_duo.id == opponent_duo.id:
            return await msg.reply("Вы не можете сражаться со своим собственным дуэтом.")

        # Prevent fighting against own members of the duo
        if user_duo.user1_id in opponent_user_ids or user_duo.user2_id in opponent_user_ids:
            return await msg.reply("Вы не можете сражаться против членов своего дуэта.")

        # Calculate power for each duo
        # For simplicity, let's sum size_cm of duo members
        user_duo_member_stats_res = await session.execute(
            select(GameStat)
            .filter(GameStat.user_id.in_(user_duo_member_ids))
        )
        user_duo_member_stats = user_duo_member_stats_res.scalars().all()
        user_duo_power = sum(gs.size_cm for gs in user_duo_member_stats) + random.randint(-10, 10)

        opponent_duo_member_stats_res = await session.execute(
            select(GameStat)
            .filter(GameStat.user_id.in_(opponent_user_ids))
        )
        opponent_duo_member_stats = opponent_duo_member_stats_res.scalars().all()
        opponent_duo_power = sum(gs.size_cm for gs in opponent_duo_member_stats) + random.randint(-10, 10)

        # Determine winner
        winner_duo: DuoTeam | None = None
        loser_duo: DuoTeam | None = None
        if user_duo_power > opponent_duo_power:
            winner_duo = user_duo
            loser_duo = opponent_duo
            winning_names = f"@{user.username or str(user.tg_user_id)} и партнер"
            losing_names = f"@{opponent_users[0].username or str(opponent_users[0].tg_user_id)} и партнер"
        elif opponent_duo_power > user_duo_power:
            winner_duo = opponent_duo
            loser_duo = user_duo
            winning_names = f"@{opponent_users[0].username or str(opponent_users[0].tg_user_id)} и партнер"
            losing_names = f"@{user.username or str(user.tg_user_id)} и партнер"
        else:  # Draw
            await msg.reply("Дуэль дуэтов закончилась ничьей!")
            await update_duo_elo(session, user_duo.id, opponent_duo.id, draw=True)
            return

        # Update ELO ratings and stats
        await update_duo_elo(session, winner_duo.id, loser_duo.id)

        await msg.reply(f"Дуэль дуэтов: {winning_names} победили {losing_names}!")


@router.message(Command("top_duos"))
async def cmd_top_duos(msg: Message):
    """
    Displays a leaderboard of top duos by ELO rating.
    """
    async_session = get_session()
    async with async_session() as session:
        top_duos_res = await session.execute(
            select(DuoTeam)
            .join(DuoStat)
            .order_by(DuoStat.rating.desc())
            .options(joinedload(DuoTeam.user1), joinedload(DuoTeam.user2), joinedload(DuoTeam.stats))
            .limit(10)
        )
        top_duos = top_duos_res.scalars().all()

        if not top_duos:
            return await msg.reply("Пока нет сформированных дуэтов.")

        leaderboard_list = ["Топ-10 дуэтов по рейтингу:"]
        for i, duo_team in enumerate(top_duos, start=1):
            name1 = duo_team.user1.username or str(duo_team.user1.tg_user_id)
            name2 = duo_team.user2.username or str(duo_team.user2.tg_user_id)
            leaderboard_list.append(
                f"{i}. {name1} + {name2}: Рейтинг {duo_team.stats.rating} (W:{duo_team.stats.wins} L:{duo_team.stats.losses})"
            )
        await msg.reply("\n".join(leaderboard_list))


@router.message(Command("duo_profile", "duo_stats"))
async def cmd_duo_profile(msg: Message):
    """
    Displays the user's duo information and stats.
    Usage: /duo_profile or /duo_stats
    """
    async_session = get_session()
    user = await ensure_user(msg.from_user)

    async with async_session() as session:
        duo_team_res = await session.execute(
            select(DuoTeam)
            .filter(or_(DuoTeam.user1_id == user.id, DuoTeam.user2_id == user.id))
            .options(joinedload(DuoTeam.user1), joinedload(DuoTeam.user2), joinedload(DuoTeam.stats))
        )
        duo_team = duo_team_res.scalars().first()

        if not duo_team:
            return await msg.reply("Вы не состоите ни в каком дуэте.")
        
        partner_user = duo_team.user1 if duo_team.user2.id == user.id else duo_team.user2
        partner_name = partner_user.username or str(partner_user.tg_user_id)

        profile_text = (
            f"🤝 Ваш дуэт:\n"
            f"Партнер: @{partner_name}\n"
            f"Рейтинг: {duo_team.stats.rating}\n"
            f"Победы: {duo_team.stats.wins}\n"
            f"Поражения: {duo_team.stats.losses}\n"
        )
        await msg.reply(profile_text)
