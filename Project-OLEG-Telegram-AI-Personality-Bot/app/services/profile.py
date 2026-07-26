from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import joinedload

from app.database.models import User, GameStat, Wallet, UserAchievement, Achievement, UserQuest, Quest, GuildMember, Guild, DuoTeam, DuoStat


async def get_full_user_profile(session: AsyncSession, user_id: int):
    """
    Fetches comprehensive profile data for a given user.
    """
    user_data = await session.execute(
        select(User)
        .filter_by(tg_user_id=user_id)
        .options(
            joinedload(User.game),
            joinedload(User.user_achievements).joinedload(UserAchievement.achievement),
            joinedload(User.user_quests).joinedload(UserQuest.quest),
            joinedload(User.guild_memberships).joinedload(GuildMember.guild),
        )
    )
    user = user_data.scalars().first()

    if not user:
        return None, None, None, [], [], None, None # user, game_stat, wallet, achievements, quests, guild, duo

    wallet_data = await session.execute(select(Wallet).filter_by(user_id=user.id))
    wallet = wallet_data.scalars().first()

    # Fetch duo information separately as it's a bit more complex (user can be user1 or user2)
    duo_team_data = await session.execute(
        select(DuoTeam)
        .filter(or_(DuoTeam.user1_id == user.id, DuoTeam.user2_id == user.id))
        .options(joinedload(DuoTeam.user1), joinedload(DuoTeam.user2), joinedload(DuoTeam.stats))
    )
    duo_team = duo_team_data.scalars().first()

    return user, user.game, wallet, user.user_achievements, user.user_quests, user.guild_memberships, duo_team