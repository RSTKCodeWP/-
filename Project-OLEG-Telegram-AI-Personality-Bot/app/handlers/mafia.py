"""
Mafia Game Handlers (v9.5.0)

Handles all mafia game commands and callbacks.
"""

import asyncio
import logging
from datetime import timedelta
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.database.models import MafiaGame
from app.services.mafia_game import MafiaGameService, LOBBY_TIMEOUT, NIGHT_TIMEOUT, DAY_DISCUSSION_TIMEOUT, DAY_VOTING_TIMEOUT
from app.services.economy import EconomyService
from app.utils import utc_now

logger = logging.getLogger(__name__)


router = Router()


# Role descriptions in Russian
ROLE_DESCRIPTIONS = {
    "citizen": "🧑‍🌾 Мирный житель — твоя задача вычислить мафию и проголосовать за её изгнание днём.",
    "mafia": "🔪 Мафия — каждую ночь выбирай жертву. Побеждаешь, когда мафии станет столько же или больше, чем мирных.",
    "doctor": "💉 Доктор — каждую ночь выбирай кого защитить. Если мафия нападёт на него, он выживет.",
    "detective": "🔍 Комиссар — каждую ночь проверяй одного игрока. Узнаешь, мафия он или нет.",
    "don": "👔 Дон мафии — главарь мафии. Видишь всю свою команду и координируешь убийства."
}


def get_lobby_keyboard(game_id: int) -> InlineKeyboardMarkup:
    """Keyboard for lobby."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎭 Войти в игру", callback_data=f"mafia_join:{game_id}")],
        [InlineKeyboardButton(text="❌ Выйти из лобби", callback_data=f"mafia_leave:{game_id}")],
        [InlineKeyboardButton(text="▶️ Начать игру", callback_data=f"mafia_start:{game_id}")]
    ])


def get_night_action_keyboard(game_id: int, players: list, action_type: str) -> InlineKeyboardMarkup:
    """Keyboard for night actions."""
    buttons = []
    for player in players:
        username = player.username or f"User {player.user_id}"
        buttons.append([InlineKeyboardButton(
            text=f"👤 {username}",
            callback_data=f"mafia_night:{game_id}:{action_type}:{player.user_id}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_voting_keyboard(game_id: int, players: list) -> InlineKeyboardMarkup:
    """Keyboard for day voting."""
    buttons = []
    for player in players:
        username = player.username or f"User {player.user_id}"
        buttons.append([InlineKeyboardButton(
            text=f"👤 {username}",
            callback_data=f"mafia_vote:{game_id}:{player.user_id}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("mafia"))
async def cmd_mafia_start(message: Message, bot: Bot):
    """Create mafia game lobby."""
    if message.chat.type == "private":
        await message.answer("❌ Мафия играется только в группах!")
        return
    
    async_session = get_session()
    async with async_session() as session:
        service = MafiaGameService(session)
        
        # Try to create lobby (will auto-cancel expired lobbies)
        game = await service.create_lobby(message.chat.id, message.from_user.id)
        if not game:
            await message.answer("❌ В этом чате уже идёт игра в мафию!")
            return
        
        # Auto-join creator
        await service.join_lobby(game.id, message.from_user.id, message.from_user.username)
        
        await message.answer(
            f"🎭 <b>МАФИЯ — Лобби #{game.id}</b>\n\n"
            f"Игра началась! Нажмите кнопку чтобы присоединиться.\n\n"
            f"👥 Игроки: 1/12\n"
            f"⏱ Лобби закроется через {LOBBY_TIMEOUT // 60} минут\n\n"
            f"<i>Минимум 4 игрока для старта</i>",
            reply_markup=get_lobby_keyboard(game.id),
            parse_mode="HTML"
        )
        
        # Schedule lobby timeout
        asyncio.create_task(schedule_lobby_timeout(bot, game.id, message.chat.id))


@router.callback_query(F.data.startswith("mafia_join:"))
async def callback_mafia_join(callback: CallbackQuery):
    """Join mafia game lobby."""
    game_id = int(callback.data.split(":")[1])
    
    async_session = get_session()
    async with async_session() as session:
        service = MafiaGameService(session)
        
        success = await service.join_lobby(
            game_id,
            callback.from_user.id,
            callback.from_user.username
        )
        
        if not success:
            await callback.answer("❌ Не удалось присоединиться (игра началась или вы уже в лобби)", show_alert=True)
            return
        
        # Get updated player count
        players = await service.get_game_players(game_id)
        
        await callback.message.edit_text(
            f"🎭 <b>МАФИЯ — Лобби #{game_id}</b>\n\n"
            f"Игра началась! Нажмите кнопку чтобы присоединиться.\n\n"
            f"👥 Игроки: {len(players)}/12\n"
            f"⏱ Лобби закроется через {LOBBY_TIMEOUT // 60} минут\n\n"
            f"<i>Минимум 4 игрока для старта</i>",
            reply_markup=get_lobby_keyboard(game_id),
            parse_mode="HTML"
        )
        
        await callback.answer(f"✅ Вы присоединились к игре!")


@router.callback_query(F.data.startswith("mafia_leave:"))
async def callback_mafia_leave(callback: CallbackQuery):
    """Leave mafia game lobby."""
    game_id = int(callback.data.split(":")[1])
    
    async_session = get_session()
    async with async_session() as session:
        service = MafiaGameService(session)
        
        success = await service.leave_lobby(game_id, callback.from_user.id)
        
        if not success:
            await callback.answer("❌ Не удалось выйти из лобби", show_alert=True)
            return
        
        # Get updated player count
        players = await service.get_game_players(game_id)
        
        if len(players) == 0:
            # Cancel game if no players left
            await service.cancel_game(game_id)
            await callback.message.edit_text("❌ Игра отменена — все игроки вышли из лобби.")
            return
        
        await callback.message.edit_text(
            f"🎭 <b>МАФИЯ — Лобби #{game_id}</b>\n\n"
            f"Игра началась! Нажмите кнопку чтобы присоединиться.\n\n"
            f"👥 Игроки: {len(players)}/12\n"
            f"⏱ Лобби закроется через {LOBBY_TIMEOUT // 60} минут\n\n"
            f"<i>Минимум 4 игрока для старта</i>",
            reply_markup=get_lobby_keyboard(game_id),
            parse_mode="HTML"
        )
        
        await callback.answer("✅ Вы вышли из лобби")


@router.callback_query(F.data.startswith("mafia_start:"))
async def callback_mafia_start_game(callback: CallbackQuery):
    """Start the mafia game."""
    game_id = int(callback.data.split(":")[1])
    
    async_session = get_session()
    async with async_session() as session:
        service = MafiaGameService(session)
        
        success, error = await service.start_game(game_id)
        
        if not success:
            await callback.answer(f"❌ {error}", show_alert=True)
            return
        
        # Get players
        players = await service.get_game_players(game_id)
        
        # Send roles to players via DM
        for player in players:
            role_desc = ROLE_DESCRIPTIONS.get(player.role, "Неизвестная роль")
            
            try:
                # Try to send DM
                role_msg = f"🎭 <b>Игра началась!</b>\n\n{role_desc}\n\n"
                
                if player.role in ["mafia", "don"]:
                    # Show mafia team
                    mafia_team = await service.get_mafia_team(game_id)
                    teammates = [p for p in mafia_team if p.user_id != player.user_id]
                    if teammates:
                        role_msg += "🤝 <b>Твоя команда:</b>\n"
                        for mate in teammates:
                            mate_name = mate.username or f"User {mate.user_id}"
                            role_msg += f"• @{mate_name}\n"
                
                await callback.bot.send_message(
                    player.user_id,
                    role_msg,
                    parse_mode="HTML"
                )
                
                # Send action keyboard for active roles
                if player.role in ["mafia", "doctor", "detective"]:
                    action_type = {"mafia": "kill", "doctor": "heal", "detective": "check"}[player.role]
                    action_text = {"kill": "убить", "heal": "защитить", "check": "проверить"}[action_type]
                    
                    # Get alive players except self
                    alive_players = [p for p in players if p.user_id != player.user_id and p.is_alive]
                    
                    await callback.bot.send_message(
                        player.user_id,
                        f"🌙 <b>Ночная фаза</b>\n\nВыбери кого {action_text}:",
                        reply_markup=get_night_action_keyboard(game_id, alive_players, action_type),
                        parse_mode="HTML"
                    )
            except Exception as e:
                logger.warning(f"Failed to send role to user {player.user_id}: {e}")
        
        # Announce game start in group
        player_list = "\n".join([f"• @{p.username or f'User {p.user_id}'}" for p in players])
        
        await callback.message.edit_text(
            f"🎭 <b>ИГРА НАЧАЛАСЬ!</b>\n\n"
            f"👥 Игроки ({len(players)}):\n{player_list}\n\n"
            f"🌙 Наступила ночь. Город засыпает...\n"
            f"Активные роли получили инструкции в ЛС.\n\n"
            f"⏱ Ночь продлится {NIGHT_TIMEOUT // 60} минут",
            parse_mode="HTML"
        )
        
        await callback.answer("✅ Игра началась!")
        
        # Schedule night phase processing
        asyncio.create_task(
            schedule_night_phase_end(callback.bot, game_id, callback.message.chat.id)
        )



@router.callback_query(F.data.startswith("mafia_night:"))
async def callback_mafia_night_action(callback: CallbackQuery):
    """Handle night action selection."""
    parts = callback.data.split(":")
    game_id = int(parts[1])
    action_type = parts[2]
    target_user_id = int(parts[3])
    
    async_session = get_session()
    async with async_session() as session:
        service = MafiaGameService(session)
        
        success = await service.submit_night_action(
            game_id,
            callback.from_user.id,
            action_type,
            target_user_id
        )
        
        if not success:
            await callback.answer("❌ Не удалось выполнить действие", show_alert=True)
            return
        
        action_names = {
            "kill": "убить",
            "heal": "защитить",
            "check": "проверить"
        }
        
        await callback.answer(f"✅ Вы выбрали цель для действия: {action_names.get(action_type, 'действие')}")
        await callback.message.edit_text(
            f"✅ Действие выбрано!\n\nОжидаем остальных игроков...",
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("mafia_vote:"))
async def callback_mafia_vote(callback: CallbackQuery):
    """Handle day voting."""
    parts = callback.data.split(":")
    game_id = int(parts[1])
    target_user_id = int(parts[2])
    
    async_session = get_session()
    async with async_session() as session:
        service = MafiaGameService(session)
        
        success = await service.submit_vote(
            game_id,
            callback.from_user.id,
            target_user_id
        )
        
        if not success:
            await callback.answer("❌ Не удалось проголосовать", show_alert=True)
            return
        
        await callback.answer("✅ Ваш голос учтён!")


@router.message(Command("mafia_cancel"))
async def cmd_mafia_cancel(message: Message):
    """Cancel active mafia game (admin only)."""
    if message.chat.type == "private":
        return
    
    # TODO: Add admin check
    
    async_session = get_session()
    async with async_session() as session:
        service = MafiaGameService(session)
        
        game = await service.get_active_game(message.chat.id)
        if not game:
            await message.answer("❌ В этом чате нет активной игры.")
            return
        
        await service.cancel_game(game.id)
        await message.answer("✅ Игра отменена администратором.")


@router.message(Command("mafia_debug"))
async def cmd_mafia_debug(message: Message):
    """Debug command to check game state."""
    if message.chat.type == "private":
        return
    
    from app.database.models import MafiaGame
    from sqlalchemy import select, desc
    
    async_session = get_session()
    async with async_session() as session:
        # Get last 3 games in this chat
        result = await session.execute(
            select(MafiaGame)
            .where(MafiaGame.chat_id == message.chat.id)
            .order_by(desc(MafiaGame.created_at))
            .limit(3)
        )
        games = list(result.scalars().all())
        
        if not games:
            await message.answer("🔍 В этом чате не было игр в мафию.")
            return
        
        text = "🔍 <b>Последние игры:</b>\n\n"
        for game in games:
            text += (
                f"ID: {game.id}\n"
                f"Статус: {game.status}\n"
                f"Создана: {game.created_at.strftime('%H:%M:%S')}\n"
            )
            if game.finished_at:
                text += f"Завершена: {game.finished_at.strftime('%H:%M:%S')}\n"
            text += "\n"
        
        await message.answer(text, parse_mode="HTML")


@router.message(Command("mafia_stats"))
async def cmd_mafia_stats(message: Message):
    """Show player's mafia statistics."""
    from app.database.models import MafiaStats
    from sqlalchemy import select, and_
    
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(MafiaStats).where(
                and_(
                    MafiaStats.user_id == message.from_user.id,
                    MafiaStats.chat_id == message.chat.id
                )
            )
        )
        stats = result.scalar_one_or_none()
        
        if not stats or stats.games_played == 0:
            await message.answer("📊 У вас пока нет статистики по игре в мафию.")
            return
        
        winrate = (stats.games_won / stats.games_played * 100) if stats.games_played > 0 else 0
        survival_rate = (stats.games_survived / stats.games_played * 100) if stats.games_played > 0 else 0
        vote_accuracy = (stats.correct_votes / stats.total_votes * 100) if stats.total_votes > 0 else 0
        
        mafia_winrate = (stats.mafia_wins / stats.mafia_games * 100) if stats.mafia_games > 0 else 0
        citizen_winrate = (stats.citizen_wins / stats.citizen_games * 100) if stats.citizen_games > 0 else 0
        
        text = (
            f"📊 <b>Статистика мафии</b>\n\n"
            f"🎮 Игр сыграно: {stats.games_played}\n"
            f"🏆 Побед: {stats.games_won} ({winrate:.1f}%)\n"
            f"💚 Выживаемость: {stats.games_survived} ({survival_rate:.1f}%)\n\n"
            f"<b>По ролям:</b>\n"
            f"🔪 Мафия: {stats.mafia_wins}/{stats.mafia_games} ({mafia_winrate:.1f}%)\n"
            f"🧑‍🌾 Мирные: {stats.citizen_wins}/{stats.citizen_games} ({citizen_winrate:.1f}%)\n"
        )
        
        if stats.detective_games > 0:
            text += f"🔍 Комиссар: {stats.detective_games} игр, {stats.detective_checks} мафий найдено\n"
        
        if stats.doctor_games > 0:
            text += f"💉 Доктор: {stats.doctor_games} игр, {stats.doctor_saves} спасений\n"
        
        text += f"\n🗳 Точность голосований: {stats.correct_votes}/{stats.total_votes} ({vote_accuracy:.1f}%)"
        
        await message.answer(text, parse_mode="HTML")


# Background task to process night phase
async def process_night_phase_task(bot, game_id: int, chat_id: int):
    """Process night phase after timeout."""
    async_session = get_session()
    async with async_session() as session:
        service = MafiaGameService(session)
        
        result = await service.process_night_phase(game_id)
        
        if not result:
            return
        
        killed_user_id = result.get("killed_user_id")
        detective_checks = result.get("detective_checks", {})
        
        # Announce results in group
        if killed_user_id:
            # Get victim info
            players = await service.get_game_players(game_id)
            victim = next((p for p in players if p.user_id == killed_user_id), None)
            victim_name = victim.username if victim and victim.username else f"User {killed_user_id}"
            
            await bot.send_message(
                chat_id,
                f"☀️ <b>Наступило утро...</b>\n\n"
                f"💀 Этой ночью был убит @{victim_name}\n\n"
                f"🗣 Начинается обсуждение. У вас {DAY_DISCUSSION_TIMEOUT // 60} минут.",
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                chat_id,
                f"☀️ <b>Наступило утро...</b>\n\n"
                f"✨ Этой ночью никто не пострадал!\n\n"
                f"🗣 Начинается обсуждение. У вас {DAY_DISCUSSION_TIMEOUT // 60} минут.",
                parse_mode="HTML"
            )
        
        # Send detective results via DM
        for detective_id, check_result in detective_checks.items():
            target_id = check_result["target_id"]
            is_mafia = check_result["is_mafia"]
            
            result_text = "мафия" if is_mafia else "не мафия"
            
            try:
                await bot.send_message(
                    detective_id,
                    f"🔍 <b>Результат проверки:</b>\n\n"
                    f"Игрок User {target_id}: <b>{result_text}</b>",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Failed to send detective result to {detective_id}: {e}")


# Background task to start voting
async def start_voting_task(bot, game_id: int, chat_id: int):
    """Start voting phase after discussion."""
    async_session = get_session()
    async with async_session() as session:
        service = MafiaGameService(session)
        
        await service.start_voting(game_id)
        
        # Get alive players
        players = await service.get_game_players(game_id, alive_only=True)
        
        await bot.send_message(
            chat_id,
            f"🗳 <b>Голосование началось!</b>\n\n"
            f"Выберите кого изгнать из города.\n"
            f"⏱ Время на голосование: {DAY_VOTING_TIMEOUT // 60} минут",
            reply_markup=get_voting_keyboard(game_id, players),
            parse_mode="HTML"
        )


# Background task to process voting
async def process_voting_task(bot, game_id: int, chat_id: int):
    """Process voting after timeout."""
    async_session = get_session()
    async with async_session() as session:
        service = MafiaGameService(session)
        
        result = await service.process_voting(game_id)
        
        if not result:
            return
        
        lynched_user_id = result.get("lynched_user_id")
        vote_counts = result.get("vote_counts", {})
        winner = result.get("winner")
        
        # Announce voting results
        if lynched_user_id:
            players = await service.get_game_players(game_id)
            victim = next((p for p in players if p.user_id == lynched_user_id), None)
            victim_name = victim.username if victim and victim.username else f"User {lynched_user_id}"
            victim_role = ROLE_DESCRIPTIONS.get(victim.role, "Неизвестная роль") if victim else ""
            
            text = (
                f"⚖️ <b>Результаты голосования:</b>\n\n"
                f"🪦 Город изгнал @{victim_name}\n"
                f"Роль: {victim_role}\n\n"
            )
        else:
            text = (
                f"⚖️ <b>Результаты голосования:</b>\n\n"
                f"🤷 Голоса разделились поровну. Никто не изгнан.\n\n"
            )
        
        # Check for winner
        if winner:
            winner_text = "🔪 <b>МАФИЯ ПОБЕДИЛА!</b>" if winner == "mafia" else "🧑‍🌾 <b>МИРНЫЕ ЖИТЕЛИ ПОБЕДИЛИ!</b>"
            text += f"\n{winner_text}\n\n"
            
            # Show all roles
            players = await service.get_game_players(game_id)
            text += "<b>Роли игроков:</b>\n"
            for player in players:
                role_emoji = {"citizen": "🧑‍🌾", "mafia": "🔪", "doctor": "💉", "detective": "🔍", "don": "👔"}.get(player.role, "❓")
                player_name = player.username or f"User {player.user_id}"
                text += f"{role_emoji} @{player_name} — {player.role}\n"
            
            # Award coins
            economy_service = EconomyService(session)
            for player in players:
                reward = 0
                if winner == "mafia" and player.role in ["mafia", "don"]:
                    reward = 300
                elif winner == "citizens" and player.role not in ["mafia", "don"]:
                    reward = 200
                else:
                    reward = 50  # Participation reward
                
                await economy_service.add_coins(player.user_id, reward, "mafia_game")
        else:
            text += f"🌙 Наступает ночь..."
        
        await bot.send_message(chat_id, text, parse_mode="HTML")



# Scheduling functions for phase transitions

async def schedule_lobby_timeout(bot: Bot, game_id: int, chat_id: int):
    """Cancel lobby if not started within timeout."""
    await asyncio.sleep(LOBBY_TIMEOUT)
    
    async_session = get_session()
    async with async_session() as session:
        service = MafiaGameService(session)
        
        # Check if game is still in lobby
        game = await session.get(MafiaGame, game_id)
        if not game:
            logger.warning(f"Lobby timeout: game {game_id} not found")
            return
        
        if game.status != "lobby":
            # Game already started or cancelled
            logger.info(f"Lobby timeout: game {game_id} already in status {game.status}")
            return
        
        logger.info(f"Lobby timeout: cancelling game {game_id} in chat {chat_id}")
        
        # Cancel the game
        success = await service.cancel_game(game_id)
        
        if not success:
            logger.error(f"Failed to cancel game {game_id}")
            return
        
        try:
            await bot.send_message(
                chat_id,
                f"⏱ <b>Лобби #{game_id} закрыто</b>\n\n"
                f"Время ожидания истекло. Игра отменена.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Failed to send lobby timeout message: {e}")


async def send_night_actions(bot: Bot, game_id: int):
    """Send night action keyboards to active roles."""
    async_session = get_session()
    async with async_session() as session:
        service = MafiaGameService(session)
        
        players = await service.get_game_players(game_id, alive_only=True)
        
        for player in players:
            if player.role in ["mafia", "doctor", "detective"]:
                action_type = {"mafia": "kill", "doctor": "heal", "detective": "check"}[player.role]
                action_text = {"kill": "убить", "heal": "защитить", "check": "проверить"}[action_type]
                
                # Get alive players except self
                alive_players = [p for p in players if p.user_id != player.user_id]
                
                try:
                    await bot.send_message(
                        player.user_id,
                        f"🌙 <b>Ночная фаза</b>\n\nВыбери кого {action_text}:",
                        reply_markup=get_night_action_keyboard(game_id, alive_players, action_type),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"Failed to send night action to user {player.user_id}: {e}")


async def schedule_night_phase_end(bot: Bot, game_id: int, chat_id: int):
    """Schedule night phase end after timeout."""
    # Send night actions first (only for subsequent nights, not first one)
    await send_night_actions(bot, game_id)
    
    await asyncio.sleep(NIGHT_TIMEOUT)
    await process_night_phase_task(bot, game_id, chat_id)
    
    # Schedule discussion end
    asyncio.create_task(schedule_discussion_end(bot, game_id, chat_id))


async def schedule_discussion_end(bot: Bot, game_id: int, chat_id: int):
    """Schedule discussion phase end after timeout."""
    await asyncio.sleep(DAY_DISCUSSION_TIMEOUT)
    await start_voting_task(bot, game_id, chat_id)
    
    # Schedule voting end
    asyncio.create_task(schedule_voting_end(bot, game_id, chat_id))


async def schedule_voting_end(bot: Bot, game_id: int, chat_id: int):
    """Schedule voting phase end after timeout."""
    await asyncio.sleep(DAY_VOTING_TIMEOUT)
    result = await process_voting_task(bot, game_id, chat_id)
    
    # If game continues, schedule next night
    if result and not result.get("winner"):
        # Announce night in group
        await bot.send_message(
            chat_id,
            f"🌙 <b>Наступила ночь...</b>\n\n"
            f"Город засыпает. Активные роли получили инструкции в ЛС.\n"
            f"⏱ Ночь продлится {NIGHT_TIMEOUT // 60} минут",
            parse_mode="HTML"
        )
        asyncio.create_task(schedule_night_phase_end(bot, game_id, chat_id))
