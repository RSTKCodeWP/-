from datetime import datetime, timedelta
import pytz
import random
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from aiogram import Bot
from sqlalchemy import select, and_, delete, or_, func
from sqlalchemy.orm import joinedload

from app.config import settings
from app.services.ollama_client import summarize_chat, generate_creative
from app.services.tournaments import tournament_service, TournamentType, TournamentDiscipline
from app.database.session import get_session
from app.database.models import User, Wallet, GameStat, Auction, AuctionBid, Quest, UserQuest, TeamWar, TeamWarParticipant, GlobalStats, GuildMember, Chat, PendingVerification, Tournament
from app.utils import utc_now

logger = logging.getLogger(__name__)

# Отключаем дублирующее логирование APScheduler
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("apscheduler.scheduler").setLevel(logging.WARNING)
logging.getLogger("apscheduler.executors").setLevel(logging.WARNING)
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)

_scheduler: AsyncIOScheduler | None = None


async def job_regenerate_rooster_hp(bot: Bot):
    """
    Regenerate HP for all roosters every hour.
    Roosters regenerate 5 HP per hour up to max HP.
    """
    from app.services.rooster_hp import HP_REGEN_PER_HOUR, MAX_HP
    from app.database.models import UserInventory
    import json
    
    async_session = get_session()
    async with async_session() as session:
        # Get all roosters
        result = await session.execute(
            select(UserInventory).where(
                UserInventory.item_type.in_(['rooster_common', 'rooster_rare', 'rooster_epic'])
            )
        )
        roosters = result.scalars().all()
        
        regenerated_count = 0
        for rooster in roosters:
            try:
                # Parse metadata
                metadata = {}
                if rooster.item_data:
                    try:
                        metadata = json.loads(rooster.item_data)
                    except json.JSONDecodeError:
                        continue
                
                current_hp = metadata.get("hp", MAX_HP)
                max_hp = metadata.get("max_hp", MAX_HP)
                
                # Regenerate if not at max
                if current_hp < max_hp:
                    new_hp = min(max_hp, current_hp + HP_REGEN_PER_HOUR)
                    metadata["hp"] = new_hp
                    metadata["last_regen"] = datetime.now(pytz.UTC).isoformat()
                    rooster.item_data = json.dumps(metadata)
                    regenerated_count += 1
                    
            except Exception as e:
                logger.error(f"Error regenerating HP for rooster {rooster.id}: {e}")
                continue
        
        if regenerated_count > 0:
            await session.commit()
            logger.info(f"Regenerated HP for {regenerated_count} roosters")


async def job_check_pending_verifications(bot: Bot):
    """
    Проверяет истекшие верификации и кикает пользователей, которые не нажали кнопку.
    Запускается каждую минуту.
    """
    async_session = get_session()
    now = utc_now()
    
    async with async_session() as session:
        # Находим все истекшие и необработанные верификации
        result = await session.execute(
            select(PendingVerification).filter(
                PendingVerification.expires_at <= now,
                PendingVerification.is_verified == False,
                PendingVerification.is_kicked == False
            )
        )
        expired_verifications = result.scalars().all()
        
        for verification in expired_verifications:
            try:
                # Проверяем, не стал ли пользователь админом
                try:
                    member = await bot.get_chat_member(verification.chat_id, verification.user_id)
                    if member.status in ['administrator', 'creator']:
                        # Админов не кикаем, просто отмечаем как верифицированных
                        verification.is_verified = True
                        logger.info(f"Пользователь {verification.user_id} — админ, пропускаем кик")
                        continue
                except Exception:
                    pass
                
                # Кикаем пользователя
                await bot.ban_chat_member(
                    chat_id=verification.chat_id,
                    user_id=verification.user_id,
                    until_date=now + timedelta(seconds=60)  # Бан на 60 сек = кик с возможностью вернуться
                )
                
                verification.is_kicked = True
                
                # Удаляем приветственное сообщение
                if verification.welcome_message_id:
                    try:
                        await bot.delete_message(verification.chat_id, verification.welcome_message_id)
                    except Exception:
                        pass
                
                # Отправляем уведомление
                try:
                    username = verification.username or str(verification.user_id)
                    await bot.send_message(
                        verification.chat_id,
                        f"👢 {username} был кикнут за неактивность (не подтвердил, что не бот)."
                    )
                except Exception:
                    pass
                
                logger.info(f"Кикнут пользователь {verification.user_id} из чата {verification.chat_id} (не прошел верификацию)")
                
            except Exception as e:
                logger.error(f"Ошибка при кике пользователя {verification.user_id}: {e}")
                # Отмечаем как обработанный чтобы не пытаться снова
                verification.is_kicked = True
        
        await session.commit()
        
        # Удаляем старые записи (старше 1 дня)
        old_date = now - timedelta(days=1)
        await session.execute(
            delete(PendingVerification).where(PendingVerification.created_at < old_date)
        )
        await session.commit()


async def job_daily_summary(bot: Bot):
    """
    Morning summary job (08:00). Summarizes yesterday.
    Sends to summary_topic_id if set, otherwise to main chat.
    """
    from app.services.dailies import dailies_service
    
    async_session = get_session()
    async with async_session() as session:
        try:
            result = await session.execute(select(Chat))
            chats = result.scalars().all()

            for chat in chats:
                try:
                    # Get summary for yesterday
                    messages = await dailies_service.get_morning_messages(
                        chat.id, session, for_today=False
                    )
                    
                    for msg in messages:
                        text = msg.get("text")
                        # In the morning we send to summary_topic_id if available
                        target_topic = chat.summary_topic_id
                        
                        await bot.send_message(
                            chat_id=chat.id,
                            message_thread_id=target_topic,
                            text=text,
                            parse_mode="HTML",
                            disable_web_page_preview=True
                        )
                        await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Failed morning summary for chat {chat.id}: {e}")
        except Exception as e:
            logger.error(f"Error in morning summary job: {e}")

async def job_creative(bot: Bot):
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(select(Chat))
        chats = result.scalars().all()

        for chat in chats:
            if chat.creative_topic_id:
                text = await generate_creative(chat.id)
                await bot.send_message(
                    chat_id=chat.id,
                    message_thread_id=chat.creative_topic_id,
                    text=text,
                    disable_web_page_preview=True
                )
                await asyncio.sleep(1)


async def job_expire_trades_and_auctions(bot: Bot):
    """
    Expire old trades and complete finished auctions (v9.5).
    Runs every minute.
    """
    from app.services.trade_service import trade_service
    from app.services.auction_service import auction_service
    
    try:
        # Expire old trades
        expired_count = await trade_service.expire_old_trades()
        if expired_count > 0:
            logger.info(f"Expired {expired_count} old trades")
        
        # Complete finished auctions
        completed_count = await auction_service.complete_expired_auctions()
        if completed_count > 0:
            logger.info(f"Completed {completed_count} expired auctions")
            
    except Exception as e:
        logger.error(f"Error in expire_trades_and_auctions job: {e}")


async def job_assign_daily_quests(bot: Bot):
    """
    Assigns a random set of daily quests to all active users.
    """
    async_session = get_session()
    async with async_session() as session:
        # Get all available quests
        all_quests_res = await session.execute(select(Quest))
        all_quests = all_quests_res.scalars().all()

        if not all_quests:
            logger.warning("No quests found in the database to assign.")
            return

        # Get all active users
        active_users_res = await session.execute(select(User))
        active_users = active_users_res.scalars().all()

        if not active_users:
            logger.info("No active users to assign quests to.")
            return

        for user in active_users:
            # Clear previous day's quests
            await session.execute(
                delete(UserQuest).where(
                    and_(UserQuest.user_id == user.id, UserQuest.completed_at == None) # Only delete uncompleted quests from previous days
                )
            )

            # Select a random subset of quests to assign (e.g., 3 quests)
            quests_to_assign = random.sample(all_quests, min(3, len(all_quests)))

            for quest in quests_to_assign:
                user_quest = UserQuest(
                    user_id=user.id,
                    quest_id=quest.id,
                    assigned_at=utc_now(),
                    progress=0,
                    completed_at=None
                )
                session.add(user_quest)
            await session.commit()
            logger.info(f"Assigned {len(quests_to_assign)} quests to user {user.tg_user_id}")


async def job_update_team_wars(bot: Bot):
    """
    Manages the lifecycle of team wars: starting, ending, and determining winners.
    """
    async_session = get_session()
    async with async_session() as session:
        # 1. Activate declared wars
        declared_wars_res = await session.execute(
            select(TeamWar)
            .filter(
                TeamWar.start_time == None, # Not yet started
                TeamWar.status == "declared",
                TeamWar.created_at <= utc_now() - timedelta(minutes=5) # Allow some time for acceptance
            )
            .options(joinedload(TeamWar.declarer_guild), joinedload(TeamWar.defender_guild))
        )
        declared_wars = declared_wars_res.scalars().all()

        for war in declared_wars:
            # Check if defender accepted (start_time is set)
            if war.start_time: # War was accepted by defender
                war.status = "active"
                await session.commit()
                # Notify declarer guild leader
                declarer_leader_res = await session.execute(
                    select(User)
                    .join(GuildMember)
                    .filter(and_(GuildMember.guild_id == war.declarer_guild.id, GuildMember.role == "leader"))
                )
                declarer_leader = declarer_leader_res.scalars().first()
                if declarer_leader:
                    await bot.send_message(
                        chat_id=declarer_leader.tg_user_id,
                        text=f"Война ID:{war.id} между '{war.declarer_guild.name}' и '{war.defender_guild.name}' началась!"
                    )
                # Notify defender guild leader
                defender_leader_res = await session.execute(
                    select(User)
                    .join(GuildMember)
                    .filter(and_(GuildMember.guild_id == war.defender_guild.id, GuildMember.role == "leader"))
                )
                defender_leader = defender_leader_res.scalars().first()
                if defender_leader:
                    await bot.send_message(
                        chat_id=defender_leader.tg_user_id,
                        text=f"Война ID:{war.id} между '{war.declarer_guild.name}' и '{war.defender_guild.name}' началась!"
                    )
            else: # Defender did not accept within the grace period, cancel the war
                war.status = "cancelled"
                await session.commit()
                # Notify declarer guild leader
                declarer_leader_res = await session.execute(
                    select(User)
                    .join(GuildMember)
                    .filter(and_(GuildMember.guild_id == war.declarer_guild.id, GuildMember.role == "leader"))
                )
                declarer_leader = declarer_leader_res.scalars().first()
                if declarer_leader:
                    await bot.send_message(
                        chat_id=declarer_leader.tg_user_id,
                        text=f"Война ID:{war.id} против '{war.defender_guild.name}' была отменена, так как не была принята вовремя."
                    )
        
        # 2. End active wars
        active_wars_res = await session.execute(
            select(TeamWar)
            .filter(
                TeamWar.end_time <= utc_now(),
                TeamWar.status == "active"
            )
            .options(joinedload(TeamWar.declarer_guild), joinedload(TeamWar.defender_guild))
        )
        active_wars = active_wars_res.scalars().all()

        for war in active_wars:
            # Determine winner based on participant scores (or other criteria)
            declarer_guild_score = await session.execute(
                select(func.sum(TeamWarParticipant.score))
                .filter(and_(TeamWarParticipant.team_war_id == war.id, TeamWarParticipant.guild_id == war.declarer_guild_id))
            )
            declarer_guild_score = declarer_guild_score.scalar_one_or_none() or 0

            defender_guild_score = await session.execute(
                select(func.sum(TeamWarParticipant.score))
                .filter(and_(TeamWarParticipant.team_war_id == war.id, TeamWarParticipant.guild_id == war.defender_guild_id))
            )
            defender_guild_score = defender_guild_score.scalar_one_or_none() or 0

            if declarer_guild_score > defender_guild_score:
                war.winner_guild_id = war.declarer_guild_id
                winner_message = f"Гильдия '{war.declarer_guild.name}' победила!"
            elif defender_guild_score > declarer_guild_score:
                war.winner_guild_id = war.defender_guild_id
                winner_message = f"Гильдия '{war.defender_guild.name}' победила!"
            else:
                war.winner_guild_id = None
                winner_message = "Война закончилась ничьей!"
            
            war.status = "finished"
            await session.commit()

            # Notify both guilds
            message_text = f"Война ID:{war.id} между '{war.declarer_guild.name}' ({declarer_guild_score}) и '{war.defender_guild.name}' ({defender_guild_score}) завершена. {winner_message}"
            await bot.send_message(
                chat_id=war.declarer_guild.owner.tg_user_id,
                text=message_text
            )
            await bot.send_message(
                chat_id=war.defender_guild.owner.tg_user_id,
                text=message_text
            )


async def job_aggregate_daily_stats(bot: Bot):
    """
    Aggregates daily statistics from GameStat into GlobalStats.
    """
    async_session = get_session()
    async with async_session() as session:
        today = utc_now().date()
        yesterday = today - timedelta(days=1)

        # Get total stats from GameStat for today
        current_game_stats_res = await session.execute(
            select(
                func.sum(GameStat.pvp_wins).label("total_pvp_wins"),
                func.sum(GameStat.grow_count).label("total_grow_count"),
                func.sum(GameStat.casino_jackpots).label("total_casino_jackpots"),
                func.sum(GameStat.reputation).label("total_reputation")
            )
        )
        current_stats = current_game_stats_res.one()

        # Get yesterday's global stats
        yesterday_global_stats_res = await session.execute(
            select(GlobalStats)
            .filter(GlobalStats.date == yesterday, GlobalStats.period_type == "daily")
        )
        yesterday_global_stats = yesterday_global_stats_res.scalars().first()

        # Calculate deltas
        pvp_wins_delta = current_stats.total_pvp_wins - (yesterday_global_stats.total_pvp_wins if yesterday_global_stats else 0)
        grow_count_delta = current_stats.total_grow_count - (yesterday_global_stats.total_grow_count if yesterday_global_stats else 0)
        casino_jackpots_delta = current_stats.total_casino_jackpots - (yesterday_global_stats.total_casino_jackpots if yesterday_global_stats else 0)
        reputation_delta = current_stats.total_reputation - (yesterday_global_stats.total_reputation if yesterday_global_stats else 0)

        # Create new GlobalStats entry
        new_global_stats = GlobalStats(
            date=today,
            period_type="daily",
            total_pvp_wins=current_stats.total_pvp_wins,
            pvp_wins_delta=pvp_wins_delta,
            total_grow_count=current_stats.total_grow_count,
            grow_count_delta=grow_count_delta,
            total_casino_jackpots=current_stats.total_casino_jackpots,
            casino_jackpots_delta=casino_jackpots_delta,
            total_reputation=current_stats.total_reputation,
            reputation_delta=reputation_delta
        )
        session.add(new_global_stats)
        await session.commit()
        logger.info(f"Daily statistics aggregated for {today}")


async def job_sync_chat_members(bot: Bot):
    """
    Periodically checks chat members and updates their status in the database.
    """
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(select(Chat))
        chats = result.scalars().all()

        for chat in chats:
            active_users_res = await session.execute(
                select(User).filter(User.status == "active")
            )
            active_users = active_users_res.scalars().all()

            for user in active_users:
                try:
                    chat_member = await bot.get_chat_member(
                        chat_id=chat.id,
                        user_id=user.tg_user_id
                    )
                    if chat_member.status in ["left", "kicked"]:
                        user.status = "left"
                        logger.info(f"User {user.tg_user_id} has left the chat {chat.id}. Updating status.")
                except Exception:
                    user.status = "left" # User not found in chat
                    logger.info(f"User {user.tg_user_id} not found in chat {chat.id}. Updating status.")
                
                await asyncio.sleep(0.1) # Rate limit
            
            await session.commit()




async def job_start_daily_tournament(bot: Bot):
    """
    Start a new daily tournament at 00:00 UTC.
    
    Also ends the previous daily tournament and announces winners.
    
    **Validates: Requirements 10.1**
    """
    async_session = get_session()
    async with async_session() as session:
        try:
            # End any active daily tournaments first
            result = await session.execute(
                select(Tournament).filter(
                    Tournament.type == TournamentType.DAILY.value,
                    Tournament.status == 'active'
                )
            )
            active_tournaments = result.scalars().all()
            
            for tournament in active_tournaments:
                winners = await tournament_service.end_tournament(tournament.id, session)
                
                if winners:
                    # Announce winners (simplified - in production would send to chats)
                    logger.info(
                        f"Daily tournament {tournament.id} ended with "
                        f"{len(winners)} winners"
                    )
                    
                    # Log top winners per discipline
                    for discipline in TournamentDiscipline:
                        discipline_winners = [
                            w for w in winners 
                            if w.discipline == discipline and w.rank == 1
                        ]
                        for winner in discipline_winners:
                            logger.info(
                                f"Daily {discipline.value} champion: "
                                f"user {winner.user_id} with score {winner.score}"
                            )
            
            # Start new daily tournament
            new_tournament = await tournament_service.start_tournament(
                TournamentType.DAILY, session
            )
            logger.info(f"Started new daily tournament (ID: {new_tournament.id})")
            
        except Exception as e:
            logger.error(f"Error in daily tournament job: {e}")


async def job_start_weekly_tournament(bot: Bot):
    """
    Start a new weekly tournament on Monday 00:00 UTC.
    
    Also ends the previous weekly tournament and announces winners.
    
    **Validates: Requirements 10.2**
    """
    from app.services.tournaments import tournament_service
    
    async_session = get_session()
    async with async_session() as session:
        try:
            # End previous tournament if active
            if tournament_service.is_active():
                await tournament_service.end_tournament(bot)
                logger.info("Ended previous weekly tournament")
            
            # Start new tournament
            await tournament_service.start_weekly_tournament(bot)
            logger.info("Started new weekly tournament")
            
        except Exception as e:
            logger.error(f"Error in weekly tournament job: {e}")


async def job_start_monthly_tournament(bot: Bot):
    """
    Start a new Grand Cup (monthly) tournament on the 1st of each month.
    
    Also ends the previous monthly tournament and announces winners.
    
    **Validates: Requirements 10.3**
    """
    async_session = get_session()
    async with async_session() as session:
        try:
            # End any active monthly tournaments first
            result = await session.execute(
                select(Tournament).filter(
                    Tournament.type == TournamentType.GRAND_CUP.value,
                    Tournament.status == 'active'
                )
            )
            active_tournaments = result.scalars().all()
            
            for tournament in active_tournaments:
                winners = await tournament_service.end_tournament(tournament.id, session)
                
                if winners:
                    logger.info(
                        f"Grand Cup tournament {tournament.id} ended with "
                        f"{len(winners)} winners"
                    )
                    
                    for discipline in TournamentDiscipline:
                        discipline_winners = [
                            w for w in winners 
                            if w.discipline == discipline and w.rank == 1
                        ]
                        for winner in discipline_winners:
                            logger.info(
                                f"Grand Cup {discipline.value} champion: "
                                f"user {winner.user_id} with score {winner.score}"
                            )
            
            # Start new monthly tournament
            new_tournament = await tournament_service.start_tournament(
                TournamentType.GRAND_CUP, session
            )
            logger.info(f"Started new Grand Cup tournament (ID: {new_tournament.id})")
            
        except Exception as e:
            logger.error(f"Error in monthly tournament job: {e}")


# ============================================================================
# Fortress Update: Dailies System Jobs (Requirements 13.1, 13.2, 13.3)
# ============================================================================

async def job_dailies_evening_summary(bot: Bot):
    """
    Send evening summary (#dailysummary) to all chats at 20:00 Moscow time.
    
    Respects chat-specific settings and skips chats with no activity.
    
    **Validates: Requirements 13.1, 13.4, 13.5**
    """
    from app.services.dailies import dailies_service
    from aiogram.types import BufferedInputFile
    
    async_session = get_session()
    async with async_session() as session:
        try:
            # Get all chats
            result = await session.execute(select(Chat))
            chats = result.scalars().all()
            
            for chat in chats:
                try:
                    # Get summary messages (for_today=True for evening summary)
                    messages = await dailies_service.get_morning_messages(
                        chat.id, session, for_today=True
                    )
                    
                    target_topic = chat.summary_topic_id
                    
                    for msg in messages:
                        text = msg.get("text")
                        photo = msg.get("photo")
                        
                        if photo:
                            input_file = BufferedInputFile(photo, filename="summary.png")
                            await bot.send_photo(
                                chat_id=chat.id,
                                message_thread_id=target_topic,
                                photo=input_file,
                                caption=text,
                                parse_mode="HTML"
                            )
                        else:
                            await bot.send_message(
                                chat_id=chat.id,
                                message_thread_id=target_topic,
                                text=text,
                                parse_mode="HTML",
                                disable_web_page_preview=True
                            )
                        await asyncio.sleep(0.5)  # Rate limiting
                    
                    if messages:
                        logger.info(f"Sent evening summary to chat {chat.id}")
                    else:
                        logger.debug(f"Skipped evening summary for chat {chat.id} (no activity or disabled)")
                        
                except Exception as e:
                    logger.error(f"Failed to send evening summary to chat {chat.id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in evening summary job: {e}")


async def job_dailies_evening_quote_and_stats(bot: Bot):
    """
    Send evening quote (#dailyquote) and stats (#dailystats) to all chats at 21:00 Moscow time.
    
    Respects chat-specific settings.
    
    **Validates: Requirements 13.2, 13.3, 13.4**
    """
    from app.services.dailies import dailies_service
    from aiogram.types import BufferedInputFile
    
    async_session = get_session()
    async with async_session() as session:
        try:
            # Get all chats
            result = await session.execute(select(Chat))
            chats = result.scalars().all()
            
            for chat in chats:
                try:
                    # Get evening messages (respects settings)
                    messages = await dailies_service.get_evening_messages(
                        chat.id, session
                    )
                    
                    target_topic = chat.summary_topic_id
                    
                    for msg in messages:
                        text = msg.get("text")
                        photo = msg.get("photo")
                        
                        if photo:
                            input_file = BufferedInputFile(photo, filename="stats.png")
                            await bot.send_photo(
                                chat_id=chat.id,
                                message_thread_id=target_topic,
                                photo=input_file,
                                caption=text,
                                parse_mode="HTML"
                            )
                        else:
                            await bot.send_message(
                                chat_id=chat.id,
                                message_thread_id=target_topic,
                                text=text,
                                parse_mode="HTML",
                                disable_web_page_preview=True
                            )
                        await asyncio.sleep(0.5)  # Rate limiting
                    
                    if messages:
                        logger.info(f"Sent evening quote/stats to chat {chat.id}")
                    else:
                        logger.debug(f"Skipped evening messages for chat {chat.id} (disabled)")
                        
                except Exception as e:
                    logger.error(f"Failed to send evening messages to chat {chat.id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in evening quote/stats job: {e}")


async def job_sync_sdoc_admins(bot: Bot):
    """
    Синхронизация админов группы SDOC.
    Запускается каждые 6 часов.
    """
    try:
        from app.services.sdoc_service import sdoc_service
        
        if not settings.sdoc_chat_id:
            logger.debug("SDOC chat_id не указан, пропускаем синхронизацию админов")
            return
        
        count = await sdoc_service.sync_admins(bot, settings.sdoc_chat_id)
        logger.info(f"Синхронизировано {count} админов SDOC")
        
    except Exception as e:
        logger.error(f"Ошибка синхронизации админов SDOC: {e}")


async def job_birthday_greetings(bot: Bot):
    """
    Поздравляет пользователей с днём рождения.
    Запускается в 10:00 по Москве.
    """
    from app.services.user_memory import user_memory
    from app.services.ollama_client import generate_text_reply
    
    try:
        tz = pytz.timezone(settings.timezone)
        today = datetime.now(tz)
        today_str = today.strftime("%d.%m")
        
        birthdays = await user_memory.get_birthdays_today(today_str)
        
        if not birthdays:
            logger.debug("Сегодня нет именинников")
            return
        
        # Группируем по чатам для отправки
        sent_users = set()  # Чтобы не поздравлять дважды
        
        for bday in birthdays:
            user_id = bday.get('user_id')
            if not user_id or user_id in sent_users:
                continue
            
            username = bday.get('username')
            name = bday.get('name') or username or f"ID:{user_id}"
            chat_id = bday.get('birthday_chat_id') or bday.get('chat_id')
            
            if not chat_id:
                continue
            
            try:
                # Генерируем персональное поздравление через LLM
                prompt = f"Напиши короткое (2-3 предложения) поздравление с днём рождения для {name}. Будь в своём стиле — циничный, но добрый. Без эмодзи в начале."
                
                greeting = await generate_text_reply(
                    user_text=prompt,
                    username="system",
                    chat_context=None,
                    conversation_history=None
                )
                
                # Fallback если LLM недоступен
                if not greeting or len(greeting) < 10:
                    greeting = f"Ну чё, {name}, с днюхой тебя! Желаю чтобы код компилился с первого раза, а пинг был низким. 🎂"
                
                mention = f"@{username}" if username else name
                message = f"🎂 <b>С днём рождения, {mention}!</b>\n\n{greeting}"
                
                await bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode="HTML"
                )
                
                sent_users.add(user_id)
                logger.info(f"Поздравил {name} (user_id={user_id}) в чате {chat_id}")
                
                await asyncio.sleep(1)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Ошибка поздравления user_id={user_id}: {e}")
                continue
        
        logger.info(f"Поздравлено {len(sent_users)} именинников")
        
    except Exception as e:
        logger.error(f"Ошибка в job_birthday_greetings: {e}")


async def job_generate_daily_event(bot: Bot):
    """Generate a new daily dynamic event."""
    from app.services.event_service import event_service, EventType
    await event_service.generate_event(EventType.DAILY, bot)

async def job_generate_weekly_event(bot: Bot):
    """Generate a new weekly dynamic event."""
    from app.services.event_service import event_service, EventType
    await event_service.generate_event(EventType.WEEKLY, bot)

async def job_generate_system_auction(bot: Bot):
    """Generate a random system auction."""
    from app.services.auction_service import auction_service
    await auction_service.create_system_auction(bot)


async def setup_scheduler(bot: Bot):
    global _scheduler
    if _scheduler:
        return
        
    # Load active events on startup
    from app.services.event_service import event_service
    await event_service.load_active_events()
    
    tz = pytz.timezone(settings.timezone)
    _scheduler = AsyncIOScheduler(timezone=tz)
    _scheduler.add_job(job_daily_summary, CronTrigger(hour=8, minute=0), args=[bot], id="daily_summary")
    _scheduler.add_job(job_creative, CronTrigger(hour=20, minute=0), args=[bot], id="creative")
    _scheduler.add_job(job_assign_daily_quests, CronTrigger(hour=0, minute=0), args=[bot], id="assign_daily_quests")
    _scheduler.add_job(job_update_team_wars, CronTrigger(minute="*/1"), args=[bot], id="update_team_wars")
    _scheduler.add_job(job_aggregate_daily_stats, CronTrigger(hour=23, minute=59), args=[bot], id="aggregate_daily_stats")
    _scheduler.add_job(job_sync_chat_members, CronTrigger(hour=3, minute=0), args=[bot], id="sync_chat_members")
    # Welcome 2.0: проверка истекших верификаций каждую минуту
    _scheduler.add_job(job_check_pending_verifications, IntervalTrigger(minutes=1), args=[bot], id="check_pending_verifications")
    # Trading v9.5: expire trades and complete auctions every minute
    _scheduler.add_job(job_expire_trades_and_auctions, IntervalTrigger(minutes=1), args=[bot], id="expire_trades_and_auctions")
    
    # Dynamic Events
    _scheduler.add_job(job_generate_daily_event, CronTrigger(hour=9, minute=0), args=[bot], id="generate_daily_event")
    _scheduler.add_job(job_generate_weekly_event, CronTrigger(day_of_week='mon', hour=10, minute=0), args=[bot], id="generate_weekly_event")
    
    # System Auctions (Black Market) - Every 6 hours
    _scheduler.add_job(job_generate_system_auction, IntervalTrigger(hours=6), args=[bot], id="generate_system_auction")
    
    # Rooster HP regeneration: every hour
    _scheduler.add_job(
        job_regenerate_rooster_hp,
        IntervalTrigger(hours=1),
        args=[bot],
        id="regenerate_rooster_hp"
    )
    
    # SDOC: синхронизация админов группы каждые 6 часов
    if settings.sdoc_exclusive_mode and settings.sdoc_chat_id:
        _scheduler.add_job(
            job_sync_sdoc_admins,
            IntervalTrigger(hours=6),
            args=[bot],
            id="sync_sdoc_admins"
        )
    
    # Birthday greetings: поздравления с ДР в 10:00 по Москве
    _scheduler.add_job(
        job_birthday_greetings,
        CronTrigger(hour=10, minute=0, timezone='Europe/Moscow'),
        args=[bot],
        id="birthday_greetings"
    )
    
    # Fortress Update: Tournament scheduler jobs (Requirements 10.1, 10.2, 10.3)
    # Daily tournament: starts at 00:00 UTC every day
    _scheduler.add_job(
        job_start_daily_tournament, 
        CronTrigger(hour=0, minute=0, timezone='UTC'), 
        args=[bot], 
        id="start_daily_tournament"
    )
    # Weekly tournament: starts on Monday 00:00 UTC
    _scheduler.add_job(
        job_start_weekly_tournament, 
        CronTrigger(day_of_week='mon', hour=0, minute=0, timezone='UTC'), 
        args=[bot], 
        id="start_weekly_tournament"
    )
    # Monthly tournament (Grand Cup): starts on 1st of each month 00:00 UTC
    _scheduler.add_job(
        job_start_monthly_tournament, 
        CronTrigger(day=1, hour=0, minute=0, timezone='UTC'), 
        args=[bot], 
        id="start_monthly_tournament"
    )
    
    # Fortress Update: Dailies System jobs (Requirements 13.1, 13.2, 13.3)
    # Evening summary at 20:00 Moscow time (UTC+3)
    _scheduler.add_job(
        job_dailies_evening_summary,
        CronTrigger(hour=20, minute=0, timezone='Europe/Moscow'),
        args=[bot],
        id="dailies_evening_summary"
    )
    # Evening quote and stats at 21:00 Moscow time (UTC+3)
    _scheduler.add_job(
        job_dailies_evening_quote_and_stats,
        CronTrigger(hour=21, minute=0, timezone='Europe/Moscow'),
        args=[bot],
        id="dailies_evening_quote_stats"
    )
    
    _scheduler.start()
    logger.info("Планировщик запущен с tournament jobs, dailies jobs и job_check_pending_verifications")