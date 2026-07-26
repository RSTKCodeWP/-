"""
Duel handlers with PvP and PvE modes.

Implements /challenge and /fight commands with RPG-style zone combat.
Requirements: 4.1, 4.2, 4.3, 4.4, 6.1, 6.2
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select

from app.database.session import get_session
from app.database.models import User, GameChallenge
from app.services.game_engine import game_engine, ChallengeStatus, GameType
from app.services.state_manager import state_manager
from app.services.duel_engine import DuelEngine, DuelState, DuelStatus, Zone, OLEG_USER_ID
from app.handlers.games import ensure_user
from app.services import wallet_service
from app.utils import utc_now

logger = logging.getLogger(__name__)

router = Router()

# Callback data prefixes
ACCEPT_PREFIX = "challenge_accept:"
DECLINE_PREFIX = "challenge_decline:"
DUEL_ATTACK_PREFIX = "duel:"  # duel:{owner_id}:attack:{zone}
DUEL_DEFEND_PREFIX = "duel:"  # duel:{owner_id}:defend:{zone}
PVP_MOVE_PREFIX = "pvp:"  # pvp:{duel_id}:{user_id}:attack:{zone} or pvp:{duel_id}:{user_id}:defend:{zone}

# Global duel engine instance
duel_engine = DuelEngine()

# In-memory storage for PvP duels (duel_id -> PvPDuelState)
pvp_duels: dict[str, dict] = {}

# Zone display names
ZONE_NAMES = {
    Zone.HEAD: "🎯 Голова",
    Zone.BODY: "💪 Тело",
    Zone.LEGS: "🦵 Ноги"
}

ZONE_EMOJI = {
    Zone.HEAD: "🎯",
    Zone.BODY: "💪",
    Zone.LEGS: "🦵"
}


async def ensure_user_balance(user_id: int, chat_id: int) -> int:
    """Ensure user has a balance record using unified wallet."""
    return await wallet_service.get_balance(user_id)


async def sync_balance_to_db(user_id: int, chat_id: int, new_balance: int, won: int = 0, lost: int = 0):
    """Sync balance changes to unified wallet."""
    current = await wallet_service.get_balance(user_id)
    diff = new_balance - current
    
    if diff > 0:
        await wallet_service.add_balance(user_id, diff, "duel win")
    elif diff < 0:
        await wallet_service.deduct_balance(user_id, abs(diff), "duel loss")


async def save_challenge_to_db(challenge):
    """Save challenge to database."""
    async_session = get_session()
    async with async_session() as session:
        db_challenge = GameChallenge(
            id=challenge.id,
            chat_id=challenge.chat_id,
            challenger_id=challenge.challenger_id,
            target_id=challenge.target_id,
            game_type=challenge.game_type,
            bet_amount=challenge.bet_amount,
            status=challenge.status,
            created_at=challenge.created_at,
            expires_at=challenge.expires_at
        )
        session.add(db_challenge)
        await session.commit()


async def update_challenge_status_in_db(challenge_id: str, status: str):
    """Update challenge status in database."""
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(GameChallenge).where(GameChallenge.id == challenge_id)
        )
        challenge = result.scalars().first()
        if challenge:
            challenge.status = status
            await session.commit()


def create_challenge_keyboard(challenge_id: str, thread_id: int = None) -> InlineKeyboardMarkup:
    """Create inline keyboard for challenge accept/decline.
    
    Args:
        challenge_id: Unique challenge identifier
        thread_id: Optional message_thread_id for topic routing
    """
    # Include thread_id in callback_data (0 means no thread)
    thread_suffix = f":{thread_id or 0}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="⚔️ Принять бой",
                callback_data=f"{ACCEPT_PREFIX}{challenge_id}{thread_suffix}"
            ),
            InlineKeyboardButton(
                text="🏃 Отклонить",
                callback_data=f"{DECLINE_PREFIX}{challenge_id}{thread_suffix}"
            )
        ]
    ])


def create_attack_keyboard(owner_id: int, thread_id: int = None) -> InlineKeyboardMarkup:
    """Create inline keyboard for attack zone selection.
    
    Requirements: 6.1 - Attack zones: [Голова] [Тело] [Ноги]
    
    Args:
        owner_id: User ID who owns this keyboard
        thread_id: Optional message_thread_id for topic routing
    """
    # Include thread_id in callback_data (0 means no thread)
    thread_suffix = f":{thread_id or 0}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🎯 Голова",
                callback_data=f"duel:{owner_id}:attack:head{thread_suffix}"
            ),
            InlineKeyboardButton(
                text="💪 Тело",
                callback_data=f"duel:{owner_id}:attack:body{thread_suffix}"
            ),
            InlineKeyboardButton(
                text="🦵 Ноги",
                callback_data=f"duel:{owner_id}:attack:legs{thread_suffix}"
            )
        ]
    ])


def create_defend_keyboard(owner_id: int, attack_zone: str, thread_id: int = None) -> InlineKeyboardMarkup:
    """Create inline keyboard for defense zone selection.
    
    Requirements: 6.1 - Defend zones: [Голова] [Тело] [Ноги]
    
    Args:
        owner_id: User ID who owns this keyboard
        attack_zone: The attack zone selected
        thread_id: Optional message_thread_id for topic routing
    """
    # Include thread_id in callback_data (0 means no thread)
    thread_suffix = f":{thread_id or 0}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🎯 Голова",
                callback_data=f"duel:{owner_id}:defend:{attack_zone}:head{thread_suffix}"
            ),
            InlineKeyboardButton(
                text="💪 Тело",
                callback_data=f"duel:{owner_id}:defend:{attack_zone}:body{thread_suffix}"
            ),
            InlineKeyboardButton(
                text="🦵 Ноги",
                callback_data=f"duel:{owner_id}:defend:{attack_zone}:legs{thread_suffix}"
            )
        ]
    ])


def create_pvp_move_keyboard(duel_id: str, user_id: int, phase: str, thread_id: int = None) -> InlineKeyboardMarkup:
    """Create keyboard for PvP move selection.
    
    Args:
        duel_id: Unique duel identifier
        user_id: Player making the move
        phase: 'attack' or 'defend'
        thread_id: Optional message_thread_id for topic routing
    """
    emoji = "⚔️" if phase == "attack" else "🛡️"
    # Include thread_id in callback_data (0 means no thread)
    thread_suffix = f":{thread_id or 0}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{emoji} 🎯 Голова",
                callback_data=f"pvp:{duel_id}:{user_id}:{phase}:head{thread_suffix}"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{emoji} 💪 Тело",
                callback_data=f"pvp:{duel_id}:{user_id}:{phase}:body{thread_suffix}"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{emoji} 🦵 Ноги",
                callback_data=f"pvp:{duel_id}:{user_id}:{phase}:legs{thread_suffix}"
            ),
        ]
    ])


def create_pvp_waiting_keyboard(duel_id: str) -> InlineKeyboardMarkup:
    """Create keyboard showing waiting status."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ Ожидание соперника...", callback_data=f"pvp:{duel_id}:wait")]
    ])


def render_duel_status(
    duel_state: DuelState,
    player1_name: str,
    player2_name: str,
    last_round_info: str = ""
) -> str:
    """Render duel status message with HP bars.
    
    Requirements: 6.2 - Show health bars in format: "Олег: [████░░░] 60%"
    """
    p1_hp_bar = duel_engine.render_hp_bar(duel_state.player1_hp)
    p2_hp_bar = duel_engine.render_hp_bar(duel_state.player2_hp)
    
    status_text = (
        f"⚔️ <b>Дуэль</b>\n\n"
        f"👤 {player1_name}: {p1_hp_bar}\n"
        f"👤 {player2_name}: {p2_hp_bar}\n"
    )
    
    if last_round_info:
        status_text += f"\n{last_round_info}\n"
    
    if duel_state.bet > 0:
        status_text += f"\n💰 Ставка: {duel_state.bet} очков"
    
    return status_text


def render_round_result(
    player_attack: Zone,
    player_defend: Zone,
    opp_attack: Zone,
    opp_defend: Zone,
    player_hit: bool,
    opp_hit: bool,
    player_name: str,
    opp_name: str
) -> str:
    """Render the result of a combat round."""
    lines = []
    
    if player_hit:
        lines.append(f"✅ {player_name} попал в {ZONE_NAMES[player_attack]}!")
    else:
        lines.append(f"❌ {player_name} промахнулся ({ZONE_NAMES[player_attack]} заблокирована)")
    
    if opp_hit:
        lines.append(f"✅ {opp_name} попал в {ZONE_NAMES[opp_attack]}!")
    else:
        lines.append(f"❌ {opp_name} промахнулся ({ZONE_NAMES[opp_attack]} заблокирована)")
    
    return "\n".join(lines)


def render_pvp_status(duel: dict) -> str:
    """Render PvP duel status with HP bars."""
    p1_bar = duel_engine.render_hp_bar(duel["player1_hp"])
    p2_bar = duel_engine.render_hp_bar(duel["player2_hp"])
    
    text = (
        f"⚔️ <b>PvP ДУЭЛЬ</b>\n\n"
        f"👤 {duel['player1_name']}: {p1_bar}\n"
        f"👤 {duel['player2_name']}: {p2_bar}"
    )
    
    if duel["bet"] > 0:
        text += f"\n\n💰 На кону: {duel['bet'] * 2} монет"
    
    return text


def get_pvp_move_status(duel: dict) -> str:
    """Get status of moves for current round."""
    p1_status = "✅" if duel["p1_phase"] == "done" else ("🛡️" if duel["p1_phase"] == "defend" else "⏳")
    p2_status = "✅" if duel["p2_phase"] == "done" else ("🛡️" if duel["p2_phase"] == "defend" else "⏳")
    
    return (
        f"👤 {duel['player1_name']}: {p1_status}\n"
        f"👤 {duel['player2_name']}: {p2_status}"
    )


@router.message(Command("challenge", "fight", "duel"))
async def cmd_challenge(msg: Message):
    """
    Command /challenge [@user] [bet] - Challenge to a duel.
    
    Requirements:
    - 4.1: PvP mode with @username argument (wait for confirmation)
    - 4.2: PvE mode without arguments (instant Oleg accept)
    - 4.4: Instant Oleg acceptance in PvE
    - 2.2, 2.3: Block if user already playing
    """
    if not msg.from_user:
        return
    
    challenger_id = msg.from_user.id
    chat_id = msg.chat.id
    challenger_name = msg.from_user.username or msg.from_user.first_name
    
    # Save challenger to DB for future PvP lookups
    await ensure_user(msg.from_user)
    
    # Check if user is already playing (Requirements 2.2, 2.3)
    if await state_manager.is_playing(challenger_id, chat_id):
        session = await state_manager.get_session(challenger_id, chat_id)
        game_name = session.game_type if session else "игру"
        return await msg.reply(
            f"⚠️ Ты уже играешь в {game_name}! Заверши текущую игру."
        )
    
    # Parse target user and bet amount
    target_id = None
    target_name = None
    bet_amount = 0
    
    # Check if replying to a message
    if msg.reply_to_message and msg.reply_to_message.from_user:
        reply_user = msg.reply_to_message.from_user
        # Skip if replying to bot or self
        if not reply_user.is_bot and reply_user.id != challenger_id:
            target_id = reply_user.id
            target_name = reply_user.username or reply_user.first_name
            # Save target user to DB for future PvP lookups
            await ensure_user(reply_user)
    
    # Parse command arguments
    parts = (msg.text or "").split()
    for part in parts[1:]:  # Skip command
        if part.startswith("@"):
            target_name = part[1:]  # Remove @
            target_id = None  # Will need to look up
        else:
            try:
                bet_amount = int(part)
            except ValueError:
                pass
    
    # If we have a username but no ID, try to find the user
    username_was_specified = False
    if target_name and not target_id:
        username_was_specified = True
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.username == target_name)
            )
            user = result.scalars().first()
            if user:
                target_id = user.tg_user_id
    
    # PvE mode: no target specified (Requirements 4.2, 4.4)
    if not target_id:
        # If username was specified but not found, show error instead of PvE
        if username_was_specified:
            await msg.reply(
                f"❌ Пользователь @{target_name} не найден.\n\n"
                "💡 <b>Совет:</b> Ответь на сообщение соперника командой /challenge\n"
                "Или просто /challenge для боя с Олегом.",
                parse_mode="HTML"
            )
            return
        await start_pve_duel(msg, challenger_id, chat_id, challenger_name, bet_amount)
        return
    
    # PvP mode: target specified (Requirement 4.1)
    await start_pvp_challenge(msg, challenger_id, target_id, target_name, chat_id, bet_amount)


async def start_pve_duel(
    msg: Message,
    challenger_id: int,
    chat_id: int,
    challenger_name: str,
    bet_amount: int
):
    """Start a PvE duel against Oleg.
    
    Requirements:
    - 4.2: PvE mode without arguments
    - 4.4: Instant Oleg acceptance
    - 4.3: Oleg makes moves using random selection
    - 5.1, 5.2, 5.3: Preserve message_thread_id for topic routing
    """
    # Capture thread_id for topic routing (Requirements 5.1, 5.2, 5.3)
    thread_id = getattr(msg, 'message_thread_id', None)
    
    # Ensure balance exists
    balance = await ensure_user_balance(challenger_id, chat_id)
    
    # Check if user has enough balance for bet
    if bet_amount > 0 and balance < bet_amount:
        await msg.reply(
            f"❌ Недостаточно очков! У тебя {balance}, нужно {bet_amount}."
        )
        return
    
    # Create duel state
    duel_state = duel_engine.create_duel(
        challenger_id=challenger_id,
        target_id=OLEG_USER_ID,  # Oleg's ID for PvE
        bet=bet_amount
    )
    
    # Send initial duel message
    status_text = render_duel_status(
        duel_state,
        challenger_name,
        "🤖 Олег"
    )
    status_text += "\n\n🎯 <b>Выбери зону атаки:</b>"
    
    sent_msg = await msg.reply(
        status_text,
        reply_markup=create_attack_keyboard(challenger_id, thread_id),
        parse_mode="HTML"
    )
    
    # Register game session with thread_id
    await state_manager.register_game(
        user_id=challenger_id,
        chat_id=chat_id,
        game_type="duel",
        message_id=sent_msg.message_id,
        initial_state={
            "duel_state": {
                "player1_id": duel_state.player1_id,
                "player2_id": duel_state.player2_id,
                "player1_hp": duel_state.player1_hp,
                "player2_hp": duel_state.player2_hp,
                "current_turn": duel_state.current_turn,
                "bet": duel_state.bet,
                "status": duel_state.status.value
            },
            "player1_name": challenger_name,
            "player2_name": "🤖 Олег",
            "phase": "attack",  # attack or defend
            "attack_zone": None,
            "thread_id": thread_id  # Store thread_id for topic routing
        }
    )
    
    logger.info(f"PvE duel started: {challenger_id} vs Oleg, bet={bet_amount}, thread_id={thread_id}")


async def start_pvp_challenge(
    msg: Message,
    challenger_id: int,
    target_id: int,
    target_name: str,
    chat_id: int,
    bet_amount: int
):
    """Start a PvP challenge (wait for opponent confirmation).
    
    Requirement 4.1: PvP mode with @username argument
    Requirements 5.1, 5.2, 5.3: Preserve message_thread_id for topic routing
    """
    # Capture thread_id for topic routing (Requirements 5.1, 5.2, 5.3)
    thread_id = getattr(msg, 'message_thread_id', None)
    
    # Ensure balances exist
    challenger_balance = await ensure_user_balance(challenger_id, chat_id)
    target_balance_val = await ensure_user_balance(target_id, chat_id)
    
    # Check balances for bet
    if bet_amount > 0:
        if challenger_balance < bet_amount:
            await msg.reply(f"❌ Недостаточно монет! У тебя {challenger_balance}, нужно {bet_amount}.")
            return
        if target_balance_val < bet_amount:
            await msg.reply(f"❌ У соперника недостаточно монет для ставки {bet_amount}.")
            return
    
    # Get timeout from chat settings
    from app.services.bot_config import get_pvp_accept_timeout
    timeout_seconds = await get_pvp_accept_timeout(chat_id)
    timeout_minutes = max(1, timeout_seconds // 60)  # Convert to minutes, minimum 1
    
    # Create challenge
    result = game_engine.create_challenge(
        chat_id=chat_id,
        challenger_id=challenger_id,
        target_id=target_id,
        game_type=GameType.PVP,
        bet_amount=bet_amount,
        timeout_minutes=timeout_minutes
    )
    
    if not result.success:
        await msg.reply(f"❌ {result.message}")
        return
    
    challenge = result.challenge
    
    # Save to database
    await save_challenge_to_db(challenge)
    
    # Build challenge message
    challenger_name = msg.from_user.username or msg.from_user.first_name
    bet_text = f" на <b>{bet_amount}</b> монет" if bet_amount > 0 else ""
    
    challenge_text = (
        f"⚔️ <b>ВЫЗОВ НА ДУЭЛЬ!</b>\n\n"
        f"👊 <b>@{challenger_name}</b> вызывает <b>@{target_name}</b>{bet_text}!\n\n"
        f"🎮 <i>Зонный бой: выбирай атаку и защиту одновременно с соперником!</i>\n\n"
        f"⏱ Время на ответ: {timeout_seconds} сек"
    )
    
    await msg.reply(
        challenge_text,
        reply_markup=create_challenge_keyboard(challenge.id, thread_id),
        parse_mode="HTML"
    )
    
    logger.info(f"PvP challenge created: {challenger_id} vs {target_id}, bet={bet_amount}, thread_id={thread_id}")


@router.callback_query(F.data.startswith(ACCEPT_PREFIX))
async def callback_accept_challenge(callback: CallbackQuery):
    """Handle Accept button click for PvP challenge."""
    if not callback.data or not callback.from_user:
        return
    
    # Parse callback data: challenge_accept:{challenge_id}:{thread_id}
    data_part = callback.data[len(ACCEPT_PREFIX):]
    parts = data_part.split(":")
    challenge_id = parts[0]
    thread_id = int(parts[1]) if len(parts) > 1 and parts[1] != "0" else None
    
    acceptor_id = callback.from_user.id
    acceptor_name = callback.from_user.username or callback.from_user.first_name
    chat_id = callback.message.chat.id if callback.message else 0
    
    # Accept challenge
    result = game_engine.accept_challenge(challenge_id, acceptor_id)
    
    if not result.success:
        await callback.answer(result.message, show_alert=True)
        return
    
    challenge = result.challenge
    
    # Update database
    await update_challenge_status_in_db(challenge_id, ChallengeStatus.ACCEPTED)
    
    # Deduct bets from both players using wallet_service
    if challenge.bet_amount > 0:
        await wallet_service.deduct_balance(
            challenge.challenger_id,
            challenge.bet_amount,
            "pvp challenge bet"
        )
        await wallet_service.deduct_balance(
            challenge.target_id,
            challenge.bet_amount,
            "pvp challenge bet"
        )
    
    # Get challenger name
    async_session = get_session()
    async with async_session() as session:
        result_db = await session.execute(
            select(User).where(User.tg_user_id == challenge.challenger_id)
        )
        challenger_user = result_db.scalars().first()
        challenger_name = challenger_user.username if challenger_user else "Игрок"
    
    # Create PvP duel state
    duel_id = challenge_id[:8]  # Short ID for callbacks
    pvp_duels[duel_id] = {
        "challenge_id": challenge_id,
        "chat_id": chat_id,
        "message_id": callback.message.message_id,
        "thread_id": thread_id,  # Store thread_id for topic routing
        "player1_id": challenge.challenger_id,
        "player2_id": challenge.target_id,
        "player1_name": challenger_name,
        "player2_name": acceptor_name,
        "player1_hp": 100,
        "player2_hp": 100,
        "bet": challenge.bet_amount,
        "round": 1,
        # Current round moves (reset each round)
        "p1_attack": None,
        "p1_defend": None,
        "p2_attack": None,
        "p2_defend": None,
        "p1_phase": "attack",  # attack -> defend -> done
        "p2_phase": "attack",
        # Message IDs for each player's buttons
        "p1_msg_id": None,
        "p2_msg_id": None,
    }
    
    # Build initial status message (без кнопок)
    duel_text = render_pvp_status(pvp_duels[duel_id])
    duel_text += (
        f"\n\n⚔️ <b>Раунд 1</b>\n"
        f"Оба игрока выбирают атаку..."
    )
    
    # Обновляем сообщение с вызовом — убираем кнопки принять/отклонить
    await callback.message.edit_text(duel_text, parse_mode="HTML")
    
    # Отправляем ОТДЕЛЬНЫЕ сообщения каждому игроку
    bot = callback.bot
    
    # Сообщение для challenger (игрок 1)
    try:
        p1_msg = await bot.send_message(
            chat_id=chat_id,
            text=f"🎯 <b>{challenger_name}</b>, выбери зону АТАКИ:",
            reply_markup=create_pvp_move_keyboard(duel_id, challenge.challenger_id, "attack", thread_id),
            message_thread_id=thread_id,
            parse_mode="HTML"
        )
        pvp_duels[duel_id]["p1_msg_id"] = p1_msg.message_id
    except Exception as e:
        logger.warning(f"Failed to send challenger message: {e}")
    
    # Сообщение для acceptor (игрок 2)
    try:
        p2_msg = await bot.send_message(
            chat_id=chat_id,
            text=f"🎯 <b>{acceptor_name}</b>, выбери зону АТАКИ:",
            reply_markup=create_pvp_move_keyboard(duel_id, acceptor_id, "attack", thread_id),
            message_thread_id=thread_id,
            parse_mode="HTML"
        )
        pvp_duels[duel_id]["p2_msg_id"] = p2_msg.message_id
    except Exception as e:
        logger.warning(f"Failed to send acceptor message: {e}")
    
    await callback.answer("⚔️ Бой начался!")
    logger.info(f"PvP duel started: {duel_id} - {challenger_name} vs {acceptor_name}, thread_id={thread_id}")


@router.callback_query(F.data.startswith(DECLINE_PREFIX))
async def callback_decline_challenge(callback: CallbackQuery):
    """Handle Decline button click."""
    if not callback.data or not callback.from_user:
        return
    
    # Parse callback data: challenge_decline:{challenge_id}:{thread_id}
    data_part = callback.data[len(DECLINE_PREFIX):]
    parts = data_part.split(":")
    challenge_id = parts[0]
    # thread_id not needed for decline, but parse for consistency
    
    decliner_id = callback.from_user.id
    
    result = game_engine.decline_challenge(challenge_id, decliner_id)
    
    if not result.success:
        await callback.answer(result.message, show_alert=True)
        return
    
    await update_challenge_status_in_db(challenge_id, ChallengeStatus.DECLINED)
    
    decliner_name = callback.from_user.username or callback.from_user.first_name
    
    await callback.message.edit_text(
        f"🏃 <b>Вызов отклонён</b>\n\n"
        f"@{decliner_name} струсил и убежал!",
        parse_mode="HTML"
    )
    
    await callback.answer("Вызов отклонён. Трус!")
    logger.info(f"Challenge declined: {challenge_id}")


@router.callback_query(F.data.startswith(PVP_MOVE_PREFIX))
async def callback_pvp_move(callback: CallbackQuery):
    """Handle PvP move selection (attack or defend)."""
    if not callback.data or not callback.from_user:
        return
    
    # Parse: pvp:{duel_id}:{user_id}:{phase}:{zone}:{thread_id} or pvp:{duel_id}:wait
    parts = callback.data.split(":")
    if len(parts) < 3:
        return
    
    duel_id = parts[1]
    
    # Handle wait button
    if parts[2] == "wait":
        await callback.answer("⏳ Ожидаем соперника...", show_alert=False)
        return
    
    if len(parts) < 5:
        return
    
    expected_user_id = int(parts[2])
    phase = parts[3]  # attack or defend
    zone = parts[4]   # head, body, legs or "pick"
    # Parse thread_id from callback data (last part)
    thread_id = int(parts[5]) if len(parts) > 5 and parts[5] != "0" else None
    
    # Handle "pick" - show zone selection
    if zone == "pick":
        user_id = callback.from_user.id
        if user_id != expected_user_id:
            await callback.answer("⚠️ Это не твоя кнопка!", show_alert=True)
            return
        
        if duel_id not in pvp_duels:
            await callback.answer("❌ Дуэль не найдена", show_alert=True)
            return
        
        duel = pvp_duels[duel_id]
        is_player1 = user_id == duel["player1_id"]
        player_prefix = "p1" if is_player1 else "p2"
        current_phase = duel[f"{player_prefix}_phase"]
        duel_thread_id = duel.get("thread_id")
        
        if current_phase == "done":
            await callback.answer("✅ Ты уже сделал ход!", show_alert=False)
            return
        
        await callback.message.edit_text(
            f"⚔️ <b>Раунд {duel['round']}</b>\n\n"
            f"🎯 Выбери зону {'АТАКИ' if current_phase == 'attack' else 'ЗАЩИТЫ'}:",
            reply_markup=create_pvp_move_keyboard(duel_id, user_id, current_phase, duel_thread_id),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    user_id = callback.from_user.id
    
    # Verify it's the right player
    if user_id != expected_user_id:
        await callback.answer("⚠️ Это не твоя кнопка!", show_alert=True)
        return
    
    # Get duel state
    if duel_id not in pvp_duels:
        await callback.answer("❌ Дуэль не найдена или завершена", show_alert=True)
        return
    
    duel = pvp_duels[duel_id]
    duel_thread_id = duel.get("thread_id")
    
    # Determine which player
    is_player1 = user_id == duel["player1_id"]
    player_prefix = "p1" if is_player1 else "p2"
    current_phase = duel[f"{player_prefix}_phase"]
    
    # Verify phase matches
    if current_phase != phase:
        if current_phase == "done":
            await callback.answer("✅ Ты уже сделал ход, ждём соперника", show_alert=False)
        else:
            await callback.answer(f"⚠️ Сейчас фаза: {current_phase}", show_alert=True)
        return
    
    # Record the move
    player_name = duel["player1_name"] if is_player1 else duel["player2_name"]
    
    if phase == "attack":
        duel[f"{player_prefix}_attack"] = zone
        duel[f"{player_prefix}_phase"] = "defend"
        
        # Update THIS player's message to show defend selection
        try:
            await callback.message.edit_text(
                f"⚔️ <b>{player_name}</b>\n"
                f"Атака: {ZONE_NAMES[Zone(zone)]}\n\n"
                f"🛡️ <b>Теперь выбери зону ЗАЩИТЫ:</b>",
                reply_markup=create_pvp_move_keyboard(duel_id, user_id, "defend", duel_thread_id),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Failed to edit attack message: {e}")
        await callback.answer(f"⚔️ Атака выбрана!")
        
    elif phase == "defend":
        duel[f"{player_prefix}_defend"] = zone
        duel[f"{player_prefix}_phase"] = "done"
        
        # Show waiting message for THIS player
        try:
            await callback.message.edit_text(
                f"✅ <b>{player_name} — ход сделан!</b>\n\n"
                f"⏳ Ожидаем соперника...",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Failed to edit defend message: {e}")
        await callback.answer("✅ Ход сделан!")
        
        # Check if both players are done
        if duel["p1_phase"] == "done" and duel["p2_phase"] == "done":
            await process_pvp_round(callback, duel_id)


async def process_pvp_round(callback: CallbackQuery, duel_id: str):
    """Process a completed PvP round."""
    if duel_id not in pvp_duels:
        return
    
    duel = pvp_duels[duel_id]
    
    # Get moves
    p1_attack = Zone(duel["p1_attack"])
    p1_defend = Zone(duel["p1_defend"])
    p2_attack = Zone(duel["p2_attack"])
    p2_defend = Zone(duel["p2_defend"])
    
    # Calculate hits
    p1_hits = p1_attack != p2_defend  # P1 hits P2
    p2_hits = p2_attack != p1_defend  # P2 hits P1
    
    # Apply damage
    damage = 25
    if p2_hits:
        duel["player1_hp"] = max(0, duel["player1_hp"] - damage)
    if p1_hits:
        duel["player2_hp"] = max(0, duel["player2_hp"] - damage)
    
    # Build round result (без спойлеров — только попал/промах)
    result_lines = []
    if p1_hits:
        result_lines.append(f"💥 {duel['player1_name']} попал!")
    else:
        result_lines.append(f"🛡️ {duel['player1_name']} промахнулся")
    
    if p2_hits:
        result_lines.append(f"💥 {duel['player2_name']} попал!")
    else:
        result_lines.append(f"🛡️ {duel['player2_name']} промахнулся")
    
    round_result = "\n".join(result_lines)
    
    # Check for game end
    game_over = duel["player1_hp"] <= 0 or duel["player2_hp"] <= 0
    
    if game_over:
        await finish_pvp_duel(callback, duel_id, round_result)
        return
    
    # Prepare next round
    duel["round"] += 1
    duel["p1_attack"] = None
    duel["p1_defend"] = None
    duel["p2_attack"] = None
    duel["p2_defend"] = None
    duel["p1_phase"] = "attack"
    duel["p2_phase"] = "attack"
    
    # Сохраняем message_id для обоих игроков
    duel["p1_msg_id"] = None
    duel["p2_msg_id"] = None
    
    # Get thread_id for topic routing
    thread_id = duel.get("thread_id")
    
    # Общее сообщение с результатом раунда (без кнопок)
    status_msg = (
        f"⚔️ <b>Раунд {duel['round']}</b>\n\n"
        f"{render_pvp_status(duel)}\n\n"
        f"📜 Раунд {duel['round'] - 1}: {round_result}\n\n"
        f"🎯 Игроки выбирают атаку..."
    )
    
    try:
        await callback.message.answer(status_msg, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Failed to send status message: {e}")
    
    # Отправляем ОТДЕЛЬНЫЕ сообщения каждому игроку с их кнопками
    bot = callback.bot
    chat_id = duel["chat_id"]
    
    # Сообщение для игрока 1
    try:
        p1_msg = await bot.send_message(
            chat_id=chat_id,
            text=f"🎯 <b>{duel['player1_name']}</b>, выбери зону АТАКИ:",
            reply_markup=create_pvp_move_keyboard(duel_id, duel["player1_id"], "attack", thread_id),
            message_thread_id=thread_id,
            parse_mode="HTML"
        )
        duel["p1_msg_id"] = p1_msg.message_id
    except Exception as e:
        logger.warning(f"Failed to send p1 message: {e}")
    
    # Сообщение для игрока 2
    try:
        p2_msg = await bot.send_message(
            chat_id=chat_id,
            text=f"🎯 <b>{duel['player2_name']}</b>, выбери зону АТАКИ:",
            reply_markup=create_pvp_move_keyboard(duel_id, duel["player2_id"], "attack", thread_id),
            message_thread_id=thread_id,
            parse_mode="HTML"
        )
        duel["p2_msg_id"] = p2_msg.message_id
    except Exception as e:
        logger.warning(f"Failed to send p2 message: {e}")


async def finish_pvp_duel(callback: CallbackQuery, duel_id: str, last_round: str):
    """Finish PvP duel and distribute rewards."""
    if duel_id not in pvp_duels:
        return
    
    duel = pvp_duels[duel_id]
    chat_id = duel["chat_id"]
    
    # Determine winner
    if duel["player1_hp"] <= 0 and duel["player2_hp"] <= 0:
        # Both dead - tie goes to player1 (challenger)
        winner_id = duel["player1_id"]
        winner_name = duel["player1_name"]
        loser_id = duel["player2_id"]
        loser_name = duel["player2_name"]
    elif duel["player1_hp"] <= 0:
        winner_id = duel["player2_id"]
        winner_name = duel["player2_name"]
        loser_id = duel["player1_id"]
        loser_name = duel["player1_name"]
    else:
        winner_id = duel["player1_id"]
        winner_name = duel["player1_name"]
        loser_id = duel["player2_id"]
        loser_name = duel["player2_name"]
    
    # Build final message (без спойлеров зон)
    final_text = render_pvp_status(duel)
    final_text += f"\n\n📜 <b>Финальный раунд:</b>\n{last_round}"
    final_text += f"\n\n🏆 <b>{winner_name} ПОБЕДИЛ!</b>"
    
    # Handle bet payouts using wallet_service
    if duel["bet"] > 0:
        winnings = duel["bet"] * 2
        await wallet_service.add_balance(winner_id, winnings, "pvp duel win")
        final_text += f"\n💰 Выигрыш: {winnings} монет!"
    
    # Update ELO
    try:
        from app.services.leagues import league_service
        from app.database.models import GameStat
        
        async_session = get_session()
        async with async_session() as db_session:
            winner_status, loser_status = await league_service.update_elo(
                winner_id=winner_id,
                loser_id=loser_id,
                session=db_session
            )
            await db_session.commit()
            
            final_text += (
                f"\n\n📊 <b>ELO:</b>\n"
                f"  {winner_name}: {winner_status.elo} (+16)\n"
                f"  {loser_name}: {loser_status.elo} (-16)"
            )
    except Exception as e:
        logger.warning(f"Failed to update ELO: {e}")
    
    # Send final message
    try:
        await callback.message.edit_text(final_text, parse_mode="HTML")
    except Exception:
        pass
    
    try:
        await callback.message.answer(
            f"🏆 <b>ДУЭЛЬ ЗАВЕРШЕНА!</b>\n\n"
            f"{final_text}",
            parse_mode="HTML"
        )
    except Exception:
        pass
    
    # Cleanup
    del pvp_duels[duel_id]
    logger.info(f"PvP duel finished: {duel_id}, winner={winner_name}")


@router.callback_query(F.data.regexp(r"^duel:\d+:attack:(head|body|legs)(:\d+)?$"))
async def callback_duel_attack(callback: CallbackQuery):
    """Handle attack zone selection.
    
    Requirements: 6.1 - Attack zones selection
    Requirements: 5.1, 5.2, 5.3 - Preserve message_thread_id for topic routing
    """
    if not callback.data or not callback.from_user:
        return
    
    # Parse callback data: duel:{owner_id}:attack:{zone}:{thread_id}
    parts = callback.data.split(":")
    owner_id = int(parts[1])
    zone_str = parts[3]
    thread_id = int(parts[4]) if len(parts) > 4 and parts[4] != "0" else None
    
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id if callback.message else 0
    
    # Verify owner (anti-click protection is also in middleware)
    if user_id != owner_id:
        await callback.answer("⚠️ Это не твоя кнопка, сталкер!", show_alert=True)
        return
    
    # Get session
    session = await state_manager.get_session(user_id, chat_id)
    if not session or session.game_type != "duel":
        await callback.answer("❌ Игра не найдена", show_alert=True)
        return
    
    # Store attack zone and show defend selection
    attack_zone = zone_str
    session.state["attack_zone"] = attack_zone
    session.state["phase"] = "defend"
    await state_manager.update_state(user_id, chat_id, session.state)
    
    # Get thread_id from session state if not in callback
    if thread_id is None:
        thread_id = session.state.get("thread_id")
    
    # Get duel state for display
    duel_data = session.state["duel_state"]
    duel_state = DuelState(
        player1_id=duel_data["player1_id"],
        player2_id=duel_data["player2_id"],
        player1_hp=duel_data["player1_hp"],
        player2_hp=duel_data["player2_hp"],
        current_turn=duel_data["current_turn"],
        bet=duel_data["bet"],
        status=DuelStatus(duel_data["status"])
    )
    
    player1_name = session.state["player1_name"]
    player2_name = session.state["player2_name"]
    
    zone_display = ZONE_NAMES[Zone(attack_zone)]
    status_text = render_duel_status(duel_state, player1_name, player2_name)
    status_text += f"\n\n⚔️ Атакуешь: {zone_display}\n🛡️ <b>Выбери зону защиты:</b>"
    
    await callback.message.edit_text(
        status_text,
        reply_markup=create_defend_keyboard(owner_id, attack_zone, thread_id),
        parse_mode="HTML"
    )
    
    await callback.answer(f"Атака: {zone_display}")


@router.callback_query(F.data.regexp(r"^duel:\d+:defend:(head|body|legs):(head|body|legs)(:\d+)?$"))
async def callback_duel_defend(callback: CallbackQuery):
    """Handle defense zone selection and execute combat round.
    
    Requirements: 6.1 - Defense zones and RPS mechanics
    Requirements: 5.1, 5.2, 5.3 - Preserve message_thread_id for topic routing
    """
    if not callback.data or not callback.from_user:
        return
    
    # Parse callback data: duel:{owner_id}:defend:{attack_zone}:{defend_zone}:{thread_id}
    parts = callback.data.split(":")
    owner_id = int(parts[1])
    attack_zone_str = parts[3]
    defend_zone_str = parts[4]
    thread_id = int(parts[5]) if len(parts) > 5 and parts[5] != "0" else None
    
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id if callback.message else 0
    
    # Verify owner
    if user_id != owner_id:
        await callback.answer("⚠️ Это не твоя кнопка, сталкер!", show_alert=True)
        return
    
    # Get session
    session = await state_manager.get_session(user_id, chat_id)
    if not session or session.game_type != "duel":
        await callback.answer("❌ Игра не найдена", show_alert=True)
        return
    
    # Get thread_id from session state if not in callback
    if thread_id is None:
        thread_id = session.state.get("thread_id")
    
    # Get duel state
    duel_data = session.state["duel_state"]
    duel_state = DuelState(
        player1_id=duel_data["player1_id"],
        player2_id=duel_data["player2_id"],
        player1_hp=duel_data["player1_hp"],
        player2_hp=duel_data["player2_hp"],
        current_turn=duel_data["current_turn"],
        bet=duel_data["bet"],
        status=DuelStatus(duel_data["status"])
    )
    
    player1_name = session.state["player1_name"]
    player2_name = session.state["player2_name"]
    
    # Convert zones
    player_attack = Zone(attack_zone_str)
    player_defend = Zone(defend_zone_str)
    
    # Get opponent's move (Oleg for PvE, or stored for PvP)
    if duel_state.is_pve:
        # PvE: Oleg makes random move (Requirement 4.3)
        opp_attack, opp_defend = duel_engine.oleg_move()
    else:
        # PvP: For now, simplified - opponent also makes random move
        # Full PvP would need turn-based system
        opp_attack, opp_defend = duel_engine.oleg_move()
    
    # Execute combat round
    new_duel_state = duel_engine.make_move(
        state=duel_state,
        player_id=user_id,
        attack=player_attack,
        defend=player_defend,
        opponent_attack=opp_attack,
        opponent_defend=opp_defend
    )
    
    # Calculate what happened
    player_hit = player_attack != opp_defend
    opp_hit = opp_attack != player_defend
    
    round_result = render_round_result(
        player_attack, player_defend,
        opp_attack, opp_defend,
        player_hit, opp_hit,
        player1_name, player2_name
    )
    
    # Check if game ended
    if new_duel_state.is_finished:
        await handle_duel_end(callback, new_duel_state, session, round_result)
        return
    
    # Update session state
    session.state["duel_state"] = {
        "player1_id": new_duel_state.player1_id,
        "player2_id": new_duel_state.player2_id,
        "player1_hp": new_duel_state.player1_hp,
        "player2_hp": new_duel_state.player2_hp,
        "current_turn": new_duel_state.current_turn,
        "bet": new_duel_state.bet,
        "status": new_duel_state.status.value
    }
    session.state["phase"] = "attack"
    session.state["attack_zone"] = None
    await state_manager.update_state(user_id, chat_id, session.state)
    
    # Show next round
    status_text = render_duel_status(new_duel_state, player1_name, player2_name, round_result)
    status_text += "\n\n🎯 <b>Выбери зону атаки:</b>"
    
    await callback.message.edit_text(
        status_text,
        reply_markup=create_attack_keyboard(owner_id, thread_id),
        parse_mode="HTML"
    )
    
    await callback.answer("Раунд завершён!")


async def handle_duel_end(
    callback: CallbackQuery,
    duel_state: DuelState,
    session,
    round_result: str
):
    """Handle duel end - determine winner, update balances and ELO.
    
    Requirements: 10.1 - Update ELO after PvP games
    """
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id if callback.message else 0
    
    player1_name = session.state["player1_name"]
    player2_name = session.state["player2_name"]
    
    # Determine winner and loser
    winner_id = duel_state.winner_id
    loser_id = duel_state.player2_id if winner_id == duel_state.player1_id else duel_state.player1_id
    winner_name = player1_name if winner_id == duel_state.player1_id else player2_name
    loser_name = player2_name if winner_id == duel_state.player1_id else player1_name
    
    # Build final message
    final_text = render_duel_status(duel_state, player1_name, player2_name, round_result)
    
    if winner_id == duel_state.player1_id:
        final_text += f"\n\n🏆 <b>{winner_name} победил!</b>"
        if duel_state.is_pve:
            final_text += "\n💪 Олег повержен!"
    else:
        final_text += f"\n\n🏆 <b>{winner_name} победил!</b>"
        if duel_state.is_pve:
            final_text += "\n😈 Олег торжествует!"
    
    # Handle bet payouts
    if duel_state.bet > 0:
        winnings = duel_state.bet * 2
        if winner_id == duel_state.player1_id:
            # Player won - add winnings using wallet_service
            await wallet_service.add_balance(duel_state.player1_id, winnings, "duel win")
            final_text += f"\n💰 Выигрыш: {winnings} очков!"
        else:
            # Player lost (to Oleg or opponent)
            if not duel_state.is_pve:
                # PvP: winner gets the pot
                await wallet_service.add_balance(winner_id, winnings, "duel win")
            final_text += f"\n💸 Проигрыш: {duel_state.bet} очков"
    
    # Update ELO ratings for PvP duels (Requirement 10.1)
    elo_info = ""
    if not duel_state.is_pve:
        try:
            from app.services.leagues import league_service
            from app.database.models import GameStat
            
            async_session = get_session()
            async with async_session() as db_session:
                # Update ELO ratings
                winner_status, loser_status = await league_service.update_elo(
                    winner_id=winner_id,
                    loser_id=loser_id,
                    session=db_session
                )
                
                # Also update GameStat ELO fields for consistency
                winner_stat_result = await db_session.execute(
                    select(GameStat).where(GameStat.tg_user_id == winner_id)
                )
                winner_stat = winner_stat_result.scalar_one_or_none()
                if winner_stat:
                    winner_stat.elo_rating = winner_status.elo
                    winner_stat.league = winner_status.league.code
                
                loser_stat_result = await db_session.execute(
                    select(GameStat).where(GameStat.tg_user_id == loser_id)
                )
                loser_stat = loser_stat_result.scalar_one_or_none()
                if loser_stat:
                    loser_stat.elo_rating = loser_status.elo
                    loser_stat.league = loser_status.league.code
                
                await db_session.commit()
                
                # Format ELO change info
                elo_info = (
                    f"\n\n📊 <b>ELO:</b>\n"
                    f"  {winner_name}: +{winner_status.elo - (winner_status.elo - 16)} → {winner_status.elo} ({winner_status.league.display_name})\n"
                    f"  {loser_name}: {loser_status.elo - (loser_status.elo + 16)} → {loser_status.elo} ({loser_status.league.display_name})"
                )
                
                logger.info(
                    f"ELO updated after duel: winner={winner_id} ({winner_status.elo}), "
                    f"loser={loser_id} ({loser_status.elo})"
                )
        except Exception as e:
            logger.warning(f"Failed to update ELO after duel: {e}")
    
    final_text += elo_info
    
    # End game session
    await state_manager.end_game(user_id, chat_id)
    
    await callback.message.edit_text(final_text, parse_mode="HTML")
    await callback.answer("Дуэль завершена!")
    
    logger.info(f"Duel ended: winner={winner_id}, bet={duel_state.bet}")


@router.message(Command("cancel_challenge"))
async def cmd_cancel_challenge(msg: Message):
    """Command /cancel_challenge - Cancel your pending challenge."""
    if not msg.from_user:
        return
    
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    
    # Find pending challenges
    pending = game_engine.get_user_pending_challenges(user_id, chat_id)
    
    if not pending:
        await msg.reply("У тебя нет активных вызовов.")
        return
    
    # Cancel the first pending challenge where user is challenger
    for challenge in pending:
        if challenge.challenger_id == user_id:
            result = game_engine.cancel_challenge(challenge.id, user_id)
            if result.success:
                await update_challenge_status_in_db(challenge.id, ChallengeStatus.CANCELLED)
                await msg.reply("✅ Вызов отменён.")
                return
    
    await msg.reply("У тебя нет вызовов, которые можно отменить.")


@router.message(Command("surrender", "ff"))
async def cmd_surrender(msg: Message):
    """Command /surrender - Surrender current duel."""
    if not msg.from_user:
        return
    
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    
    session = await state_manager.get_session(user_id, chat_id)
    if not session or session.game_type != "duel":
        await msg.reply("❌ Ты не в дуэли.")
        return
    
    # End the game
    await state_manager.end_game(user_id, chat_id)
    
    await msg.reply("🏳️ Ты сдался! Позор на твою голову, сталкер.")
    logger.info(f"User {user_id} surrendered duel")
