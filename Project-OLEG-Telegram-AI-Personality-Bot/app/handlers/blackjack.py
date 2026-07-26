"""Blackjack game handler with inline keyboard controls.

Provides /bj command and callback handlers for Hit, Stand, Double actions.
Integrates with State Manager and Anti-Click protection.
Requirements: 9.1, 9.2
"""

import logging
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select

from app.database.session import get_session
from app.database.models import User, GameStat
from app.services.blackjack import BlackjackEngine, BlackjackGame, GameStatus, Hand, Card
from app.services.state_manager import state_manager
from app.services import wallet_service

logger = logging.getLogger(__name__)

router = Router()

# Callback data format: bj:{owner_id}:{action}
# Actions: hit, stand, double
BJ_PREFIX = "bj:"

# Default bet amount
DEFAULT_BET = 10
MIN_BET = 1
MAX_BET = 10000

# Blackjack engine instance
blackjack_engine = BlackjackEngine()


def render_hand(hand: Hand, hide_second: bool = False) -> str:
    """Render a hand as a string with card emojis.
    
    Args:
        hand: The hand to render
        hide_second: If True, hide the second card (for dealer's initial hand)
        
    Returns:
        String representation of the hand
    """
    if not hand.cards:
        return "Пусто"
    
    cards_str = []
    for i, card in enumerate(hand.cards):
        if hide_second and i == 1:
            cards_str.append("🂠")  # Hidden card
        else:
            cards_str.append(str(card))
    
    if hide_second:
        # Only show first card's value
        return " ".join(cards_str) + f" ({hand.cards[0].value}+?)"
    else:
        return " ".join(cards_str) + f" ({hand.value})"


def render_game_message(game: BlackjackGame, user_name: str, hide_dealer: bool = True) -> str:
    """Render the full game state as a message.
    
    Args:
        game: The blackjack game state
        user_name: Player's display name
        hide_dealer: Whether to hide dealer's second card
        
    Returns:
        Formatted game message
    """
    # Determine if we should hide dealer's card
    should_hide = hide_dealer and game.status == GameStatus.PLAYING
    
    dealer_hand_str = render_hand(game.dealer_hand, hide_second=should_hide)
    player_hand_str = render_hand(game.player_hand)
    
    lines = [
        "🃏 <b>Blackjack</b>",
        "",
        f"🎰 Дилер: {dealer_hand_str}",
        f"👤 {user_name}: {player_hand_str}",
        "",
        f"💰 Ставка: {game.bet} монет",
    ]
    
    # Add status message
    if game.status == GameStatus.PLAYING:
        lines.append("")
        lines.append("Твой ход! Выбери действие:")
    elif game.status == GameStatus.PLAYER_BUSTED:
        lines.append("")
        lines.append("💥 <b>Перебор!</b> Ты проиграл.")
    elif game.status == GameStatus.DEALER_BUSTED:
        lines.append("")
        lines.append("🎉 <b>Дилер перебрал!</b> Ты выиграл!")
    elif game.status == GameStatus.PLAYER_WIN:
        lines.append("")
        lines.append("🎉 <b>Победа!</b> Твоя рука ближе к 21.")
    elif game.status == GameStatus.DEALER_WIN:
        lines.append("")
        lines.append("😢 <b>Проигрыш.</b> Рука дилера ближе к 21.")
    elif game.status == GameStatus.PUSH:
        lines.append("")
        lines.append("🤝 <b>Ничья!</b> Ставка возвращена.")
    elif game.status == GameStatus.PLAYER_BLACKJACK:
        lines.append("")
        lines.append("🎰 <b>BLACKJACK!</b> Выплата 1.5x!")
    
    return "\n".join(lines)


def get_game_keyboard(owner_id: int, game: BlackjackGame) -> InlineKeyboardMarkup:
    """Create inline keyboard for blackjack actions.
    
    Args:
        owner_id: The game owner's user ID (for anti-click protection)
        game: Current game state
        
    Returns:
        InlineKeyboardMarkup with action buttons
    """
    if game.status != GameStatus.PLAYING:
        # Game is over, no buttons needed
        return None
    
    buttons = [
        [
            InlineKeyboardButton(
                text="🎯 Hit",
                callback_data=f"{BJ_PREFIX}{owner_id}:hit"
            ),
            InlineKeyboardButton(
                text="✋ Stand",
                callback_data=f"{BJ_PREFIX}{owner_id}:stand"
            ),
            InlineKeyboardButton(
                text="💰 Double",
                callback_data=f"{BJ_PREFIX}{owner_id}:double"
            ),
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def ensure_user_and_balance(tg_user, chat_id: int) -> tuple:
    """Ensure user exists and has a balance record.
    
    Args:
        tg_user: Telegram user object
        chat_id: Chat ID for balance
        
    Returns:
        Tuple of (User, balance_amount)
    """
    # Ensure user exists
    user = await wallet_service.get_or_create_user(tg_user.id, tg_user.username)
    # Get balance from unified wallet
    balance = await wallet_service.get_balance(tg_user.id)
    return user, balance


async def update_balance(user_id: int, chat_id: int, change: int) -> int:
    """Update user's balance using unified wallet.
    
    Args:
        user_id: Telegram user ID
        chat_id: Chat ID (ignored, using global wallet)
        change: Amount to add (negative for deduction)
        
    Returns:
        New balance
    """
    if change > 0:
        result = await wallet_service.add_balance(user_id, change, "blackjack win")
    elif change < 0:
        result = await wallet_service.deduct_balance(user_id, abs(change), "blackjack loss")
    else:
        return await wallet_service.get_balance(user_id)
    return result.balance


def serialize_game(game: BlackjackGame) -> dict:
    """Serialize BlackjackGame to dict for state storage.
    
    Args:
        game: BlackjackGame instance
        
    Returns:
        Dictionary representation
    """
    return {
        "player_cards": [(c.suit, c.rank) for c in game.player_hand.cards],
        "dealer_cards": [(c.suit, c.rank) for c in game.dealer_hand.cards],
        "deck": [(c.suit, c.rank) for c in game.deck],
        "bet": game.bet,
        "status": game.status.value,
    }


def deserialize_game(data: dict) -> BlackjackGame:
    """Deserialize dict to BlackjackGame.
    
    Args:
        data: Dictionary from state storage
        
    Returns:
        BlackjackGame instance
    """
    player_hand = Hand([Card(suit, rank) for suit, rank in data["player_cards"]])
    dealer_hand = Hand([Card(suit, rank) for suit, rank in data["dealer_cards"]])
    deck = [Card(suit, rank) for suit, rank in data["deck"]]
    
    game = BlackjackGame(
        player_hand=player_hand,
        dealer_hand=dealer_hand,
        bet=data["bet"],
        status=GameStatus(data["status"]),
        deck=deck,
    )
    return game


@router.message(Command("bj"))
async def cmd_blackjack(message: Message):
    """Command /bj - Start a new Blackjack game.
    
    Usage: /bj [bet_amount]
    Example: /bj 50
    
    Requirements: 9.1
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_name = message.from_user.username or message.from_user.first_name or str(user_id)
    
    # Check if user is already playing (Requirements 2.2, 2.3)
    if await state_manager.is_playing(user_id, chat_id):
        session = await state_manager.get_session(user_id, chat_id)
        game_name = session.game_type if session else "игру"
        return await message.reply(
            f"⚠️ Ты уже играешь в {game_name}! Заверши текущую игру."
        )
    
    # Parse bet amount
    parts = message.text.split()
    bet = DEFAULT_BET
    if len(parts) >= 2:
        try:
            bet = int(parts[1])
        except ValueError:
            return await message.reply(
                "🃏 <b>Blackjack</b>\n\n"
                "Использование: <code>/bj [ставка]</code>\n"
                "Пример: <code>/bj 50</code>\n\n"
                f"Ставка по умолчанию: {DEFAULT_BET} монет",
                parse_mode="HTML"
            )
    
    # Validate bet
    bet = max(MIN_BET, min(MAX_BET, bet))
    
    # Ensure user exists and check balance
    user, balance = await ensure_user_and_balance(message.from_user, chat_id)
    
    if balance < bet:
        return await message.reply(
            f"🃏 <b>Blackjack</b>\n\n"
            f"💰 У тебя {balance} монет, а ставка {bet}.\n"
            f"Заработай больше в /pvp или /casino!",
            parse_mode="HTML"
        )
    
    # Deduct bet from balance
    await update_balance(user_id, chat_id, -bet)
    
    # Create new game
    game = blackjack_engine.create_game(user_id, bet)
    
    # Send game message
    game_msg = await message.reply(
        render_game_message(game, user_name),
        reply_markup=get_game_keyboard(user_id, game),
        parse_mode="HTML"
    )
    
    # Register game session if game is still playing
    if game.status == GameStatus.PLAYING:
        await state_manager.register_game(
            user_id=user_id,
            chat_id=chat_id,
            game_type="blackjack",
            message_id=game_msg.message_id,
            initial_state=serialize_game(game)
        )
        logger.info(f"Blackjack started: user={user_id}, bet={bet}")
    else:
        # Game ended immediately (blackjack or dealer blackjack)
        payout = blackjack_engine.calculate_payout(game)
        if payout != 0:
            # Return bet + payout (payout is relative to bet)
            await update_balance(user_id, chat_id, bet + payout)
        else:
            # Push - return bet
            await update_balance(user_id, chat_id, bet)
        logger.info(f"Blackjack instant result: user={user_id}, status={game.status.value}, payout={payout}")


@router.callback_query(F.data.startswith(BJ_PREFIX))
async def callback_blackjack_action(callback: CallbackQuery):
    """Handle Blackjack action button clicks.
    
    Callback format: bj:{owner_id}:{action}
    Actions: hit, stand, double
    
    Requirements: 9.2, 9.3, 9.4, 9.5
    """
    if not callback.data or not callback.message:
        return
    
    # Parse callback data
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    
    _, owner_id_str, action = parts
    
    try:
        owner_id = int(owner_id_str)
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    user_name = callback.from_user.username or callback.from_user.first_name or str(user_id)
    
    # Anti-click protection (Requirements 3.1, 3.3, 3.4)
    # Note: This is also handled by AntiClickMiddleware, but we double-check here
    if user_id != owner_id:
        await callback.answer(
            "⚠️ Это не твоя кнопка, сталкер! Иди создай свою игру.",
            show_alert=True
        )
        return
    
    # Get game session
    session = await state_manager.get_session(user_id, chat_id)
    if not session or session.game_type != "blackjack":
        await callback.answer("Игра не найдена или завершена", show_alert=True)
        return
    
    # Deserialize game state
    try:
        game = deserialize_game(session.state)
    except Exception as e:
        logger.error(f"Failed to deserialize game: {e}")
        await callback.answer("Ошибка загрузки игры", show_alert=True)
        return
    
    # Check if game is still playing
    if game.status != GameStatus.PLAYING:
        await callback.answer("Игра уже завершена", show_alert=True)
        return
    
    # Process action
    if action == "hit":
        # Hit - deal one card (Requirement 9.3)
        game = blackjack_engine.hit(game)
        await callback.answer("🎯 Hit!")
        
    elif action == "stand":
        # Stand - dealer plays (Requirement 9.4)
        game = blackjack_engine.stand(game)
        await callback.answer("✋ Stand!")
        
    elif action == "double":
        # Double - check if player can afford to double
        original_bet = game.bet
        
        # Check balance for doubling
        _, balance = await ensure_user_and_balance(callback.from_user, chat_id)
        if balance < original_bet:
            await callback.answer(
                f"💰 Недостаточно монет для удвоения! Нужно ещё {original_bet}.",
                show_alert=True
            )
            return
        
        # Deduct additional bet
        await update_balance(user_id, chat_id, -original_bet)
        
        # Double - double bet, one card, stand (Requirement 9.5)
        game = blackjack_engine.double(game)
        await callback.answer("💰 Double!")
        
    else:
        await callback.answer("Неизвестное действие", show_alert=True)
        return
    
    # Update game state or end game
    if game.status == GameStatus.PLAYING:
        # Game continues
        await state_manager.update_state(user_id, chat_id, serialize_game(game))
        
        # Update message
        await callback.message.edit_text(
            render_game_message(game, user_name),
            reply_markup=get_game_keyboard(user_id, game),
            parse_mode="HTML"
        )
    else:
        # Game ended
        payout = blackjack_engine.calculate_payout(game)
        
        # Calculate final balance change
        if payout > 0:
            # Won - return bet + winnings
            await update_balance(user_id, chat_id, game.bet + payout)
        elif payout == 0:
            # Push - return bet
            await update_balance(user_id, chat_id, game.bet)
        # Loss - bet already deducted
        
        # End game session
        await state_manager.end_game(user_id, chat_id)
        
        # Get final balance
        _, final_balance = await ensure_user_and_balance(callback.from_user, chat_id)
        
        # Update message with final state
        final_message = render_game_message(game, user_name, hide_dealer=False)
        
        # Add payout info
        if payout > 0:
            final_message += f"\n\n💵 Выигрыш: +{payout} монет"
        elif payout < 0:
            final_message += f"\n\n💸 Проигрыш: {payout} монет"
        else:
            final_message += "\n\n🔄 Ставка возвращена"
        
        final_message += f"\n💰 Баланс: {final_balance} монет"
        final_message += "\n📋 /games"
        
        await callback.message.edit_text(
            final_message,
            reply_markup=None,  # Remove buttons
            parse_mode="HTML"
        )
        
        logger.info(
            f"Blackjack ended: user={user_id}, status={game.status.value}, "
            f"payout={payout}, final_balance={final_balance}"
        )
