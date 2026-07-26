"""Mini Games Handlers - All new games for v7.5 with inline buttons.

Includes: Fishing, Crash, Dice, Guess, War, Wheel, Lootbox, Cockfight.
Updated in v7.5.1 with full inventory, fishing shop, and statistics.
"""

import logging
import asyncio
import random
import uuid
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select

from app.database.session import get_session
from app.database.models import User, GameStat
from app.utils import utc_now
from app.services.mini_games import (
    fishing_game, crash_engine, dice_game, guess_engine,
    war_game, wheel_game, lootbox_engine, cockfight_game,
    RoosterTier, FishRarity
)
from app.services.state_manager import state_manager
from app.services.economy import economy_service
from app.services.inventory import inventory_service, ITEM_CATALOG, ItemType
from app.services.fishing_stats import fishing_stats_service
from app.services import wallet_service

logger = logging.getLogger(__name__)
router = Router()

# Callback prefixes
FISH_PREFIX = "fish:"
CRASH_PREFIX = "crash:"
DICE_PREFIX = "dice:"
GUESS_PREFIX = "guess:"
WAR_PREFIX = "war:"
WHEEL_PREFIX = "wheel:"
LOOT_PREFIX = "loot:"
COCK_PREFIX = "cock:"


async def get_user_balance(user_id: int, chat_id: int) -> int:
    """Get user balance from unified Wallet."""
    return await wallet_service.get_balance(user_id)


async def update_user_balance(user_id: int, chat_id: int, change: int, apply_coin_magnet: bool = True) -> int:
    """Update user balance and return new value.
    
    Args:
        user_id: User ID
        chat_id: Chat ID
        change: Amount to change (positive for add, negative for deduct)
        apply_coin_magnet: Whether to apply coin magnet bonus (default True)
    """
    # Apply coin magnet bonus if enabled and change is positive
    if apply_coin_magnet and change > 0:
        from app.handlers.inventory import get_booster_effect
        coin_magnet_data = await get_booster_effect(user_id, chat_id, "coin_magnet")
        if coin_magnet_data:
            coin_bonus = coin_magnet_data.get("coin_bonus", 0.25)
            bonus_amount = int(change * coin_bonus)
            change += bonus_amount
    
    if change > 0:
        result = await wallet_service.add_balance(user_id, change, "mini_game win")
    elif change < 0:
        result = await wallet_service.deduct_balance(user_id, abs(change), "mini_game loss")
    else:
        return await wallet_service.get_balance(user_id)
    
    return result.balance


# ============================================================================
# FISHING GAME
# ============================================================================

def get_fishing_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Create fishing game keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎣 Забросить", callback_data=f"{FISH_PREFIX}{user_id}:cast"),
            InlineKeyboardButton(text="📊 Статистика", callback_data=f"{FISH_PREFIX}{user_id}:stats"),
        ],
        [
            InlineKeyboardButton(text="🏪 Магазин удочек", callback_data=f"{FISH_PREFIX}{user_id}:shop"),
            InlineKeyboardButton(text="🎒 Инвентарь", callback_data=f"{FISH_PREFIX}{user_id}:inventory"),
        ]
    ])


def get_rod_shop_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Create fishing rod shop keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥈 Серебряная (500)", callback_data=f"{FISH_PREFIX}{user_id}:buy:silver_rod")],
        [InlineKeyboardButton(text="🥇 Золотая (2000)", callback_data=f"{FISH_PREFIX}{user_id}:buy:golden_rod")],
        [InlineKeyboardButton(text="👑 Легендарная (10000)", callback_data=f"{FISH_PREFIX}{user_id}:buy:legendary_rod")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{FISH_PREFIX}{user_id}:back")],
    ])


def get_inventory_keyboard(user_id: int, items: list) -> InlineKeyboardMarkup:
    """Create inventory keyboard with equip buttons for rods."""
    buttons = []
    
    rod_types = [ItemType.SILVER_ROD, ItemType.GOLDEN_ROD, ItemType.LEGENDARY_ROD]
    for item in items:
        if item.item_type in [r.value for r in rod_types]:
            equipped = "✅ " if item.equipped else ""
            item_info = ITEM_CATALOG.get(item.item_type)
            if item_info:
                buttons.append([
                    InlineKeyboardButton(
                        text=f"{equipped}{item_info.emoji} {item_info.name}",
                        callback_data=f"{FISH_PREFIX}{user_id}:equip:{item.item_type}"
                    )
                ])
    
    # Show consumables count
    consumable_types = [ItemType.LUCKY_CHARM, ItemType.ENERGY_DRINK, ItemType.SHIELD]
    consumable_row = []
    for item in items:
        if item.item_type in [c.value for c in consumable_types]:
            item_info = ITEM_CATALOG.get(item.item_type)
            if item_info:
                consumable_row.append(f"{item_info.emoji}x{item.quantity}")
    
    if consumable_row:
        buttons.append([InlineKeyboardButton(text=" | ".join(consumable_row), callback_data=f"{FISH_PREFIX}{user_id}:noop")])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{FISH_PREFIX}{user_id}:back")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("fish"))
async def cmd_fish(message: Message):
    """Start fishing game."""
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        balance = await get_user_balance(user_id, chat_id)
        
        # Get equipped rod with fallback to basic rod
        try:
            equipped_rod = await inventory_service.get_equipped_rod(user_id, chat_id)
        except Exception as rod_error:
            logger.warning(f"Failed to get equipped rod for user {user_id}: {rod_error}")
            # Fallback to basic rod from catalog
            equipped_rod = ITEM_CATALOG.get(ItemType.BASIC_ROD)
            if not equipped_rod:
                # Ultimate fallback - create minimal rod info
                from app.services.inventory import ItemInfo
                equipped_rod = ItemInfo(
                    item_type="basic_rod",
                    name="Базовая удочка",
                    emoji="🎣",
                    description="Простая удочка для начинающих",
                    price=0,
                    effect={"rod_bonus": 0.0}
                )
        
        rod_bonus = int(equipped_rod.effect.get("rod_bonus", 0) * 100)
        
        text = (
            "🎣 <b>РЫБАЛКА</b>\n\n"
            "Лови рыбу и продавай за монеты!\n"
            f"🎣 Удочка: {equipped_rod.emoji} {equipped_rod.name}\n"
            f"📈 Бонус: +{rod_bonus}% к редким рыбам\n\n"
            f"💰 Баланс: {balance} монет\n\n"
            "Нажми «Забросить» чтобы начать!"
        )
        
        await message.reply(text, reply_markup=get_fishing_keyboard(user_id), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Fishing error for user {message.from_user.id}: {e}")
        await message.reply("🎣 Упс, удочка сломалась. Попробуй позже!")


@router.callback_query(F.data.startswith(FISH_PREFIX))
async def callback_fishing(callback: CallbackQuery):
    """Handle fishing callbacks."""
    parts = callback.data.split(":")
    if len(parts) < 3:
        return await callback.answer("Ошибка")
    
    _, owner_id, action = parts[:3]
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if int(owner_id) != user_id:
        return await callback.answer("Это не твоя удочка!", show_alert=True)
    
    if action == "noop":
        return await callback.answer()
    
    if action == "cast":
        try:
            # Get equipped rod bonus with fallback
            try:
                equipped_rod = await inventory_service.get_equipped_rod(user_id, chat_id)
                rod_bonus = equipped_rod.effect.get("rod_bonus", 0.0)
            except Exception as rod_error:
                logger.warning(f"Failed to get equipped rod for user {user_id}: {rod_error}")
                rod_bonus = 0.0
            
            # Check for fishing bait booster
            from app.handlers.inventory import get_booster_effect, consume_booster_effect
            fishing_bait_data = await get_booster_effect(user_id, chat_id, "fishing_bait")
            fishing_bonus = 0.0
            if fishing_bait_data:
                fishing_bonus = fishing_bait_data.get("fishing_bonus", 0.3)
                # Decrement uses
                uses = fishing_bait_data.get("uses", 5)
                if uses > 1:
                    fishing_bait_data["uses"] = uses - 1
                    from app.handlers.inventory import _set_booster_effect
                    await _set_booster_effect(user_id, chat_id, "fishing_bait", fishing_bait_data)
                else:
                    # Last use - consume it
                    await consume_booster_effect(user_id, chat_id, "fishing_bait")
            
            result = fishing_game.cast(user_id, rod_bonus, fishing_bonus)
            
            if not result.success:
                return await callback.answer(result.message, show_alert=True)
            
            # Record catch in stats
            if result.fish:
                try:
                    await fishing_stats_service.record_catch(
                        user_id, chat_id, 
                        result.fish.rarity.value, 
                        result.fish.name,
                        result.coins_earned
                    )
                except Exception as stats_error:
                    logger.warning(f"Failed to record fishing stats for user {user_id}: {stats_error}")
            
            # Add coins
            if result.coins_earned > 0:
                new_balance = await update_user_balance(user_id, chat_id, result.coins_earned)
            else:
                new_balance = await get_user_balance(user_id, chat_id)
            
            text = f"{result.message}\n\n💰 Баланс: {new_balance} монет"
            await callback.message.edit_text(text, reply_markup=get_fishing_keyboard(user_id), parse_mode="HTML")
            await callback.answer()
        except Exception as e:
            logger.error(f"Fishing cast error for user {user_id}: {e}")
            try:
                await callback.answer("🎣 Упс, удочка сломалась. Попробуй позже!", show_alert=True)
            except Exception:
                pass  # Ignore if callback is too old
    
    elif action == "stats":
        stats = await fishing_stats_service.get_stats(user_id, chat_id)
        balance = await get_user_balance(user_id, chat_id)
        
        stats_text = fishing_stats_service.format_stats(stats)
        stats_text += f"\n\n💰 Баланс: {balance} монет"
        
        await callback.message.edit_text(
            stats_text, 
            reply_markup=get_fishing_keyboard(user_id), 
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif action == "shop":
        balance = await get_user_balance(user_id, chat_id)
        
        text = (
            "🏪 <b>МАГАЗИН УДОЧЕК</b>\n\n"
            "🥈 <b>Серебряная</b> — 500 монет\n"
            "   +10% к редким рыбам\n\n"
            "🥇 <b>Золотая</b> — 2000 монет\n"
            "   +25% к редким рыбам\n\n"
            "👑 <b>Легендарная</b> — 10000 монет\n"
            "   +50% к редким рыбам!\n\n"
            f"💰 Твой баланс: {balance} монет"
        )
        
        await callback.message.edit_text(
            text, 
            reply_markup=get_rod_shop_keyboard(user_id), 
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif action == "buy":
        item_type = parts[3] if len(parts) > 3 else None
        if not item_type or item_type not in ITEM_CATALOG:
            return await callback.answer("Неизвестный предмет", show_alert=True)
        
        item_info = ITEM_CATALOG[item_type]
        balance = await get_user_balance(user_id, chat_id)
        
        if balance < item_info.price:
            return await callback.answer(
                f"Недостаточно монет! Нужно {item_info.price}, у тебя {balance}", 
                show_alert=True
            )
        
        # Check if already owned
        if await inventory_service.has_item(user_id, chat_id, item_type):
            return await callback.answer(
                f"У тебя уже есть {item_info.emoji} {item_info.name}!", 
                show_alert=True
            )
        
        # Deduct money and add item
        await update_user_balance(user_id, chat_id, -item_info.price)
        result = await inventory_service.add_item(user_id, chat_id, item_type)
        
        # Auto-equip if it's a rod
        if item_type.endswith("_rod"):
            await inventory_service.equip_item(user_id, chat_id, item_type)
            await fishing_stats_service.update_equipped_rod(user_id, chat_id, item_type)
        
        new_balance = await get_user_balance(user_id, chat_id)
        
        await callback.message.edit_text(
            f"✅ Куплено {item_info.emoji} {item_info.name}!\n\n"
            f"💰 Баланс: {new_balance} монет\n\n"
            f"<i>Удочка автоматически экипирована.</i>",
            reply_markup=get_fishing_keyboard(user_id),
            parse_mode="HTML"
        )
        await callback.answer(f"🎉 {item_info.name} куплена!")
    
    elif action == "inventory":
        items = await inventory_service.get_inventory(user_id, chat_id)
        balance = await get_user_balance(user_id, chat_id)
        
        if not items:
            text = (
                "🎒 <b>ИНВЕНТАРЬ</b>\n\n"
                "Пусто! Покупай предметы в магазине.\n\n"
                f"💰 Баланс: {balance} монет"
            )
        else:
            text = "🎒 <b>ИНВЕНТАРЬ</b>\n\n"
            
            # Group items
            rods = []
            consumables = []
            for item in items:
                item_info = ITEM_CATALOG.get(item.item_type)
                if item_info:
                    if item.item_type.endswith("_rod"):
                        equipped = " ✅" if item.equipped else ""
                        rods.append(f"{item_info.emoji} {item_info.name}{equipped}")
                    else:
                        consumables.append(f"{item_info.emoji} {item_info.name} x{item.quantity}")
            
            if rods:
                text += "<b>Удочки:</b>\n" + "\n".join(f"  {r}" for r in rods) + "\n\n"
            if consumables:
                text += "<b>Расходники:</b>\n" + "\n".join(f"  {c}" for c in consumables) + "\n\n"
            
            text += f"💰 Баланс: {balance} монет"
        
        await callback.message.edit_text(
            text, 
            reply_markup=get_inventory_keyboard(user_id, items), 
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif action == "equip":
        item_type = parts[3] if len(parts) > 3 else None
        if not item_type:
            return await callback.answer("Ошибка", show_alert=True)
        
        result = await inventory_service.equip_item(user_id, chat_id, item_type)
        
        if result.success:
            await fishing_stats_service.update_equipped_rod(user_id, chat_id, item_type)
            await callback.answer(f"✅ {result.message}")
            
            # Refresh inventory view
            items = await inventory_service.get_inventory(user_id, chat_id)
            balance = await get_user_balance(user_id, chat_id)
            
            text = "🎒 <b>ИНВЕНТАРЬ</b>\n\n"
            rods = []
            for item in items:
                item_info = ITEM_CATALOG.get(item.item_type)
                if item_info and item.item_type.endswith("_rod"):
                    equipped = " ✅" if item.equipped else ""
                    rods.append(f"{item_info.emoji} {item_info.name}{equipped}")
            
            if rods:
                text += "<b>Удочки:</b>\n" + "\n".join(f"  {r}" for r in rods) + "\n\n"
            text += f"💰 Баланс: {balance} монет"
            
            await callback.message.edit_text(
                text, 
                reply_markup=get_inventory_keyboard(user_id, items), 
                parse_mode="HTML"
            )
        else:
            await callback.answer(result.message, show_alert=True)
    
    elif action == "back":
        balance = await get_user_balance(user_id, chat_id)
        equipped_rod = await inventory_service.get_equipped_rod(user_id, chat_id)
        
        text = (
            "🎣 <b>РЫБАЛКА</b>\n\n"
            "Лови рыбу и продавай за монеты!\n"
            f"🎣 Удочка: {equipped_rod.emoji} {equipped_rod.name}\n"
            f"📈 Бонус: +{int(equipped_rod.effect.get('rod_bonus', 0) * 100)}% к редким\n\n"
            f"💰 Баланс: {balance} монет\n\n"
            "Нажми «Забросить» чтобы начать!"
        )
        
        await callback.message.edit_text(text, reply_markup=get_fishing_keyboard(user_id), parse_mode="HTML")
        await callback.answer()


# ============================================================================
# CRASH GAME
# ============================================================================

def get_crash_keyboard(user_id: int, playing: bool = False) -> InlineKeyboardMarkup:
    """Create crash game keyboard."""
    if playing:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 ЗАБРАТЬ", callback_data=f"{CRASH_PREFIX}{user_id}:cashout")],
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 10", callback_data=f"{CRASH_PREFIX}{user_id}:start:10"),
                InlineKeyboardButton(text="🚀 50", callback_data=f"{CRASH_PREFIX}{user_id}:start:50"),
                InlineKeyboardButton(text="🚀 100", callback_data=f"{CRASH_PREFIX}{user_id}:start:100"),
            ],
            [
                InlineKeyboardButton(text="🚀 250", callback_data=f"{CRASH_PREFIX}{user_id}:start:250"),
                InlineKeyboardButton(text="🚀 500", callback_data=f"{CRASH_PREFIX}{user_id}:start:500"),
            ],
        ])


@router.message(Command("crash"))
async def cmd_crash(message: Message):
    """Start crash game."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    balance = await get_user_balance(user_id, chat_id)
    
    text = (
        "🚀 <b>CRASH</b>\n\n"
        "Множитель растёт — успей забрать до краша!\n"
        "Чем дольше ждёшь — тем больше выигрыш, но рискуешь всё потерять.\n\n"
        f"💰 Баланс: {balance} монет\n\n"
        "Выбери ставку:"
    )
    
    await message.reply(text, reply_markup=get_crash_keyboard(user_id), parse_mode="HTML")


@router.callback_query(F.data.startswith(CRASH_PREFIX))
async def callback_crash(callback: CallbackQuery):
    """Handle crash game callbacks."""
    parts = callback.data.split(":")
    if len(parts) < 3:
        return await callback.answer("Ошибка")
    
    _, owner_id, action = parts[:3]
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if int(owner_id) != user_id:
        return await callback.answer("Это не твоя игра!", show_alert=True)
    
    if action == "start":
        bet = int(parts[3]) if len(parts) > 3 else 10
        balance = await get_user_balance(user_id, chat_id)
        
        if balance < bet:
            return await callback.answer(f"Недостаточно монет! У тебя {balance}", show_alert=True)
        
        # Check if already playing
        if await state_manager.is_playing(user_id, chat_id):
            return await callback.answer("У тебя уже есть активная игра!", show_alert=True)
        
        # Deduct bet
        await update_user_balance(user_id, chat_id, -bet)
        
        # Start game
        result = crash_engine.start_game(user_id, bet)
        if not result.success:
            await update_user_balance(user_id, chat_id, bet)  # Refund
            return await callback.answer(result.message, show_alert=True)
        
        # Register session
        await state_manager.register_game(user_id, chat_id, "crash", callback.message.message_id, {"bet": bet})
        
        # Start multiplier animation
        await callback.message.edit_text(
            f"🚀 <b>CRASH</b>\n\n"
            f"Ставка: {bet} монет\n"
            f"Множитель: x{result.multiplier}\n\n"
            f"Жми ЗАБРАТЬ пока не поздно!",
            reply_markup=get_crash_keyboard(user_id, playing=True),
            parse_mode="HTML"
        )
        
        # Auto-tick the game
        asyncio.create_task(crash_auto_tick(callback.message, user_id, chat_id, bet))
        await callback.answer("🚀 Поехали!")
    
    elif action == "cashout":
        result = crash_engine.cash_out(user_id)
        if not result.success:
            return await callback.answer(result.message, show_alert=True)
        
        # Add winnings
        game = crash_engine.get_game(user_id)
        if game:
            total = game.bet + result.winnings
            new_balance = await update_user_balance(user_id, chat_id, total)
            crash_engine.end_game(user_id)
            await state_manager.end_game(user_id, chat_id)
            
            await callback.message.edit_text(
                f"🚀 <b>CRASH</b>\n\n"
                f"💰 Забрал на x{result.multiplier}!\n"
                f"Выигрыш: +{result.winnings} монет\n\n"
                f"💰 Баланс: {new_balance} монет",
                reply_markup=get_crash_keyboard(user_id, playing=False),
                parse_mode="HTML"
            )
        await callback.answer(f"💰 +{result.winnings} монет!")


async def crash_auto_tick(message: Message, user_id: int, chat_id: int, bet: int):
    """Auto-tick crash game."""
    while True:
        await asyncio.sleep(0.8)
        
        game = crash_engine.get_game(user_id)
        if not game or game.status != "playing":
            break
        
        result = crash_engine.tick(user_id)
        
        if result.crashed:
            crash_engine.end_game(user_id)
            await state_manager.end_game(user_id, chat_id)
            balance = await get_user_balance(user_id, chat_id)
            
            try:
                await message.edit_text(
                    f"🚀 <b>CRASH</b>\n\n"
                    f"💥 КРАШ на x{result.multiplier}!\n"
                    f"Потерял: -{bet} монет\n\n"
                    f"💰 Баланс: {balance} монет",
                    reply_markup=get_crash_keyboard(user_id, playing=False),
                    parse_mode="HTML"
                )
            except:
                pass
            break
        
        try:
            await message.edit_text(
                f"🚀 <b>CRASH</b>\n\n"
                f"Ставка: {bet} монет\n"
                f"Множитель: x{result.multiplier}\n"
                f"Потенциальный выигрыш: {int(bet * result.multiplier)} монет\n\n"
                f"Жми ЗАБРАТЬ пока не поздно!",
                reply_markup=get_crash_keyboard(user_id, playing=True),
                parse_mode="HTML"
            )
        except:
            pass


# ============================================================================
# DICE GAME
# ============================================================================

def get_dice_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Create dice game keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎲 10", callback_data=f"{DICE_PREFIX}{user_id}:10"),
            InlineKeyboardButton(text="🎲 25", callback_data=f"{DICE_PREFIX}{user_id}:25"),
            InlineKeyboardButton(text="🎲 50", callback_data=f"{DICE_PREFIX}{user_id}:50"),
        ],
        [
            InlineKeyboardButton(text="🎲 100", callback_data=f"{DICE_PREFIX}{user_id}:100"),
            InlineKeyboardButton(text="🎲 250", callback_data=f"{DICE_PREFIX}{user_id}:250"),
        ],
    ])


@router.message(Command("dice"))
async def cmd_dice(message: Message):
    """Start dice game."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    balance = await get_user_balance(user_id, chat_id)
    
    text = (
        "🎲 <b>КОСТИ</b>\n\n"
        "Бросаешь 2 кубика против бота.\n"
        "У кого сумма больше — тот победил!\n\n"
        f"💰 Баланс: {balance} монет\n\n"
        "Выбери ставку:"
    )
    
    await message.reply(text, reply_markup=get_dice_keyboard(user_id), parse_mode="HTML")


@router.callback_query(F.data.startswith(DICE_PREFIX))
async def callback_dice(callback: CallbackQuery):
    """Handle dice game callbacks."""
    parts = callback.data.split(":")
    if len(parts) != 3:
        return await callback.answer("Ошибка")
    
    _, owner_id, bet_str = parts
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if int(owner_id) != user_id:
        return await callback.answer("Это не твои кости!", show_alert=True)
    
    bet = int(bet_str)
    balance = await get_user_balance(user_id, chat_id)
    
    if balance < bet:
        return await callback.answer(f"Недостаточно монет! У тебя {balance}", show_alert=True)
    
    # Check for luck bonus
    from app.handlers.inventory import consume_booster_effect
    luck_bonus = await consume_booster_effect(user_id, chat_id, "luck_bonus") or 0.0
    
    # Deduct bet first
    await update_user_balance(user_id, chat_id, -bet)
    
    # Play game
    result = dice_game.play_vs_bot(user_id, bet)
    
    # Apply luck bonus to close games (within 2 points)
    if luck_bonus > 0 and abs(result.player_roll - result.opponent_roll) <= 2:
        if result.player_roll >= result.opponent_roll - 1:
            # Luck tips the scale!
            result.won = True
            result.winnings = bet * 2
            result.message += f"\n\n🍀 Удача на твоей стороне! (+{int(luck_bonus * 100)}%)"
    
    # Add winnings (includes bet back if won/draw)
    new_balance = await update_user_balance(user_id, chat_id, result.winnings)
    
    text = f"🎲 <b>КОСТИ</b>\n\n{result.message}\n\n💰 Баланс: {new_balance} монет"
    await callback.message.edit_text(text, reply_markup=get_dice_keyboard(user_id), parse_mode="HTML")
    await callback.answer()


# ============================================================================
# GUESS NUMBER GAME
# ============================================================================

def get_guess_keyboard(user_id: int, game_active: bool = False, min_val: int = 1, max_val: int = 100) -> InlineKeyboardMarkup:
    """Create guess game keyboard."""
    if not game_active:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔮 10 монет", callback_data=f"{GUESS_PREFIX}{user_id}:start:10"),
                InlineKeyboardButton(text="🔮 50 монет", callback_data=f"{GUESS_PREFIX}{user_id}:start:50"),
            ],
            [
                InlineKeyboardButton(text="🔮 100 монет", callback_data=f"{GUESS_PREFIX}{user_id}:start:100"),
            ],
        ])
    else:
        # Generate number buttons based on current range
        buttons = []
        step = max(1, (max_val - min_val) // 5)
        row = []
        for i, num in enumerate(range(min_val, max_val + 1, step)):
            if num <= max_val:
                row.append(InlineKeyboardButton(text=str(num), callback_data=f"{GUESS_PREFIX}{user_id}:guess:{num}"))
                if len(row) == 3:
                    buttons.append(row)
                    row = []
        if row:
            buttons.append(row)
        
        buttons.append([InlineKeyboardButton(text="❌ Сдаться", callback_data=f"{GUESS_PREFIX}{user_id}:giveup")])
        return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("guess"))
async def cmd_guess(message: Message):
    """Start guess number game."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    balance = await get_user_balance(user_id, chat_id)
    
    # Check for active game
    game = guess_engine.get_game(user_id)
    if game and game.status.value == "playing":
        text = (
            f"🔮 <b>УГАДАЙ ЧИСЛО</b>\n\n"
            f"Число от {game.min_val} до {game.max_val}\n"
            f"Попыток осталось: {game.max_attempts - game.attempts}\n\n"
            f"Выбери число:"
        )
        await message.reply(text, reply_markup=get_guess_keyboard(user_id, True, game.min_val, game.max_val), parse_mode="HTML")
        return
    
    text = (
        "🔮 <b>УГАДАЙ ЧИСЛО</b>\n\n"
        "Загадываю число от 1 до 100.\n"
        "У тебя 7 попыток угадать!\n"
        "Чем меньше попыток — тем больше награда.\n\n"
        f"💰 Баланс: {balance} монет\n\n"
        "Выбери ставку:"
    )
    
    await message.reply(text, reply_markup=get_guess_keyboard(user_id), parse_mode="HTML")


@router.callback_query(F.data.startswith(GUESS_PREFIX))
async def callback_guess(callback: CallbackQuery):
    """Handle guess game callbacks."""
    parts = callback.data.split(":")
    if len(parts) < 3:
        return await callback.answer("Ошибка")
    
    _, owner_id, action = parts[:3]
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if int(owner_id) != user_id:
        return await callback.answer("Это не твоя игра!", show_alert=True)
    
    if action == "start":
        bet = int(parts[3]) if len(parts) > 3 else 10
        balance = await get_user_balance(user_id, chat_id)
        
        if balance < bet:
            return await callback.answer(f"Недостаточно монет! У тебя {balance}", show_alert=True)
        
        # Deduct bet
        await update_user_balance(user_id, chat_id, -bet)
        
        # Start game
        result = guess_engine.start_game(user_id, bet)
        game = guess_engine.get_game(user_id)
        
        text = f"🔮 <b>УГАДАЙ ЧИСЛО</b>\n\n{result.message}\n\nВыбери число:"
        await callback.message.edit_text(
            text, 
            reply_markup=get_guess_keyboard(user_id, True, game.min_val, game.max_val),
            parse_mode="HTML"
        )
        await callback.answer("Игра началась!")
    
    elif action == "guess":
        number = int(parts[3]) if len(parts) > 3 else 50
        result = guess_engine.guess(user_id, number)
        game = guess_engine.get_game(user_id)
        
        if result.correct or result.attempts_left == 0:
            # Game over
            if result.winnings > 0:
                new_balance = await update_user_balance(user_id, chat_id, result.winnings + game.bet)
            else:
                new_balance = await get_user_balance(user_id, chat_id)
            
            guess_engine.end_game(user_id)
            text = f"🔮 <b>УГАДАЙ ЧИСЛО</b>\n\n{result.message}\n\n💰 Баланс: {new_balance} монет"
            await callback.message.edit_text(text, reply_markup=get_guess_keyboard(user_id), parse_mode="HTML")
        else:
            text = (
                f"🔮 <b>УГАДАЙ ЧИСЛО</b>\n\n"
                f"{result.hint}\n"
                f"Попыток осталось: {result.attempts_left}\n\n"
                f"Выбери число:"
            )
            await callback.message.edit_text(
                text,
                reply_markup=get_guess_keyboard(user_id, True, game.min_val, game.max_val),
                parse_mode="HTML"
            )
        await callback.answer()
    
    elif action == "giveup":
        game = guess_engine.get_game(user_id)
        if game:
            guess_engine.end_game(user_id)
            balance = await get_user_balance(user_id, chat_id)
            text = f"🔮 <b>УГАДАЙ ЧИСЛО</b>\n\n😢 Сдался! Число было {game.target}.\n-{game.bet} монет\n\n💰 Баланс: {balance} монет"
            await callback.message.edit_text(text, reply_markup=get_guess_keyboard(user_id), parse_mode="HTML")
        await callback.answer("Сдался!")


# ============================================================================
# WAR CARD GAME
# ============================================================================

def get_war_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Create war game keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🃏 10", callback_data=f"{WAR_PREFIX}{user_id}:10"),
            InlineKeyboardButton(text="🃏 25", callback_data=f"{WAR_PREFIX}{user_id}:25"),
            InlineKeyboardButton(text="🃏 50", callback_data=f"{WAR_PREFIX}{user_id}:50"),
        ],
        [
            InlineKeyboardButton(text="🃏 100", callback_data=f"{WAR_PREFIX}{user_id}:100"),
            InlineKeyboardButton(text="🃏 250", callback_data=f"{WAR_PREFIX}{user_id}:250"),
        ],
    ])


@router.message(Command("war"))
async def cmd_war(message: Message):
    """Start war card game."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    balance = await get_user_balance(user_id, chat_id)
    
    text = (
        "🃏 <b>ВОЙНА</b>\n\n"
        "Простая карточная игра!\n"
        "Ты и бот тянете по карте — у кого старше, тот победил.\n\n"
        f"💰 Баланс: {balance} монет\n\n"
        "Выбери ставку:"
    )
    
    await message.reply(text, reply_markup=get_war_keyboard(user_id), parse_mode="HTML")


@router.callback_query(F.data.startswith(WAR_PREFIX))
async def callback_war(callback: CallbackQuery):
    """Handle war game callbacks."""
    parts = callback.data.split(":")
    if len(parts) != 3:
        return await callback.answer("Ошибка")
    
    _, owner_id, bet_str = parts
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if int(owner_id) != user_id:
        return await callback.answer("Это не твои карты!", show_alert=True)
    
    bet = int(bet_str)
    balance = await get_user_balance(user_id, chat_id)
    
    if balance < bet:
        return await callback.answer(f"Недостаточно монет! У тебя {balance}", show_alert=True)
    
    # Check for luck bonus
    from app.handlers.inventory import consume_booster_effect
    luck_bonus = await consume_booster_effect(user_id, chat_id, "luck_bonus") or 0.0
    
    # Deduct bet first
    await update_user_balance(user_id, chat_id, -bet)
    
    # Play game
    result = war_game.play(user_id, bet)
    
    # Apply luck bonus to ties - player wins on tie with luck
    if luck_bonus > 0 and result.is_war:
        result.won = True
        result.winnings = bet * 2
        result.message += f"\n\n🍀 Удача решила исход! Ты побеждаешь!"
    
    # Add winnings (includes bet back if won/draw)
    new_balance = await update_user_balance(user_id, chat_id, result.winnings)
    
    text = f"🃏 <b>ВОЙНА</b>\n\n{result.message}\n\n💰 Баланс: {new_balance} монет"
    await callback.message.edit_text(text, reply_markup=get_war_keyboard(user_id), parse_mode="HTML")
    await callback.answer()


# ============================================================================
# WHEEL OF FORTUNE
# ============================================================================

def get_wheel_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Create wheel game keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎡 10", callback_data=f"{WHEEL_PREFIX}{user_id}:10"),
            InlineKeyboardButton(text="🎡 25", callback_data=f"{WHEEL_PREFIX}{user_id}:25"),
            InlineKeyboardButton(text="🎡 50", callback_data=f"{WHEEL_PREFIX}{user_id}:50"),
        ],
        [
            InlineKeyboardButton(text="🎡 100", callback_data=f"{WHEEL_PREFIX}{user_id}:100"),
            InlineKeyboardButton(text="🎡 250", callback_data=f"{WHEEL_PREFIX}{user_id}:250"),
        ],
    ])


@router.message(Command("wheel"))
async def cmd_wheel(message: Message):
    """Start wheel of fortune game."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    balance = await get_user_balance(user_id, chat_id)
    
    text = (
        "🎡 <b>КОЛЕСО ФОРТУНЫ</b>\n\n"
        "Крути колесо и испытай удачу!\n\n"
        "💀 Банкрот — потеря всего\n"
        "😢 x0.5 — минус половина\n"
        "🔄 x1 — возврат ставки\n"
        "💰 x1.5-x3 — выигрыш\n"
        "🌟 x5 — большой выигрыш\n"
        "👑 x10 — ДЖЕКПОТ!\n\n"
        f"💰 Баланс: {balance} монет\n\n"
        "Выбери ставку:"
    )
    
    await message.reply(text, reply_markup=get_wheel_keyboard(user_id), parse_mode="HTML")


@router.callback_query(F.data.startswith(WHEEL_PREFIX))
async def callback_wheel(callback: CallbackQuery):
    """Handle wheel game callbacks."""
    parts = callback.data.split(":")
    if len(parts) != 3:
        return await callback.answer("Ошибка")
    
    _, owner_id, bet_str = parts
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if int(owner_id) != user_id:
        return await callback.answer("Это не твоё колесо!", show_alert=True)
    
    bet = int(bet_str)
    balance = await get_user_balance(user_id, chat_id)
    
    if balance < bet:
        return await callback.answer(f"Недостаточно монет! У тебя {balance}", show_alert=True)
    
    # Check for luck bonus
    from app.handlers.inventory import consume_booster_effect
    luck_bonus = await consume_booster_effect(user_id, chat_id, "luck_bonus") or 0.0
    
    # Deduct bet first
    await update_user_balance(user_id, chat_id, -bet)
    
    # Play game
    result = wheel_game.spin(user_id, bet)
    
    # Apply luck bonus - increase winnings by luck_bonus %
    if luck_bonus > 0 and result.winnings > bet:
        bonus_amount = int((result.winnings - bet) * luck_bonus)
        result.winnings += bonus_amount
        result.message += f"\n\n🍀 Бонус удачи: +{bonus_amount} монет!"
    
    # Add winnings (includes bet back based on multiplier)
    new_balance = await update_user_balance(user_id, chat_id, result.winnings)
    
    text = f"{result.message}\n\n💰 Баланс: {new_balance} монет"
    await callback.message.edit_text(text, reply_markup=get_wheel_keyboard(user_id), parse_mode="HTML")
    await callback.answer()


# ============================================================================
# LOOTBOX SYSTEM
# ============================================================================

def get_lootbox_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Create lootbox keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📦 Обычный (50)", callback_data=f"{LOOT_PREFIX}{user_id}:common"),
            InlineKeyboardButton(text="📦 Редкий (150)", callback_data=f"{LOOT_PREFIX}{user_id}:rare"),
        ],
        [
            InlineKeyboardButton(text="📦 Эпик (400)", callback_data=f"{LOOT_PREFIX}{user_id}:epic"),
            InlineKeyboardButton(text="📦 Легенда (1000)", callback_data=f"{LOOT_PREFIX}{user_id}:legendary"),
        ],
        [
            InlineKeyboardButton(text="🎁 Мега (2500)", callback_data=f"{LOOT_PREFIX}{user_id}:mega"),
            InlineKeyboardButton(text="🔮 Мистика (500)", callback_data=f"{LOOT_PREFIX}{user_id}:mystery"),
        ],
    ])


LOOTBOX_PRICES = {
    "common": 50,
    "rare": 150,
    "epic": 400,
    "legendary": 1000,
    "mega": 2500,
    "mystery": 500,
}


@router.message(Command("loot"))
async def cmd_loot(message: Message):
    """Open lootbox menu."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    balance = await get_user_balance(user_id, chat_id)
    
    text = (
        "📦 <b>ЛУТБОКСЫ</b>\n\n"
        "Открывай коробки и получай награды!\n\n"
        "📦 <b>Обычный</b> (50) — базовые награды\n"
        "📦 <b>Редкий</b> (150) — лучше шансы\n"
        "📦 <b>Эпический</b> (400) — гарантированный эпик+\n"
        "📦 <b>Легендарный</b> (1000) — шанс на легендарку!\n"
        "🎁 <b>Мега</b> (2500) — гарантированная легенда!\n"
        "🔮 <b>Мистический</b> (500) — всё или ничего!\n\n"
        f"💰 Баланс: {balance} монет\n\n"
        "Выбери лутбокс:"
    )
    
    await message.reply(text, reply_markup=get_lootbox_keyboard(user_id), parse_mode="HTML")


@router.callback_query(F.data.startswith(LOOT_PREFIX))
async def callback_lootbox(callback: CallbackQuery):
    """Handle lootbox callbacks."""
    parts = callback.data.split(":")
    if len(parts) != 3:
        return await callback.answer("Ошибка")
    
    _, owner_id, loot_type = parts
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if int(owner_id) != user_id:
        return await callback.answer("Это не твой лутбокс!", show_alert=True)
    
    price = LOOTBOX_PRICES.get(loot_type, 50)
    balance = await get_user_balance(user_id, chat_id)
    
    if balance < price:
        return await callback.answer(f"Недостаточно монет! У тебя {balance}, нужно {price}", show_alert=True)
    
    # Deduct price
    await update_user_balance(user_id, chat_id, -price)
    
    # Open lootbox
    result = lootbox_engine.open(loot_type)
    
    # Add coins from lootbox
    if result.total_coins > 0:
        await update_user_balance(user_id, chat_id, result.total_coins)
    
    # Add items to inventory
    items_added = []
    for item_type in result.items:
        if item_type:
            add_result = await inventory_service.add_item(user_id, chat_id, item_type)
            if add_result.success and add_result.item:
                items_added.append(f"{add_result.item.emoji} {add_result.item.name}")
    
    new_balance = await get_user_balance(user_id, chat_id)
    
    text = f"{result.message}"
    if items_added:
        text += f"\n\n🎁 Добавлено в инвентарь:\n" + "\n".join(f"  {i}" for i in items_added)
    text += f"\n\n💰 Баланс: {new_balance} монет"
    
    await callback.message.edit_text(text, reply_markup=get_lootbox_keyboard(user_id), parse_mode="HTML")
    await callback.answer("📦 Открыто!")


# ============================================================================
# COCKFIGHT GAME
# ============================================================================

async def get_cockfight_keyboard(user_id: int, chat_id: int) -> InlineKeyboardMarkup:
    """Create cockfight keyboard with only owned roosters."""
    from app.services.inventory import inventory_service, ItemType
    
    buttons = []
    
    # Check ownership for each rooster tier
    if await inventory_service.has_item(user_id, chat_id, ItemType.ROOSTER_COMMON):
        buttons.append([InlineKeyboardButton(text="🐔 Обычный петух", callback_data=f"{COCK_PREFIX}{user_id}:select:common")])
    
    if await inventory_service.has_item(user_id, chat_id, ItemType.ROOSTER_RARE):
        buttons.append([InlineKeyboardButton(text="🐓 Редкий петух", callback_data=f"{COCK_PREFIX}{user_id}:select:rare")])
    
    if await inventory_service.has_item(user_id, chat_id, ItemType.ROOSTER_EPIC):
        buttons.append([InlineKeyboardButton(text="🦃 Эпический петух", callback_data=f"{COCK_PREFIX}{user_id}:select:epic")])
    
    # If no roosters owned, show shop link
    if not buttons:
        buttons.append([InlineKeyboardButton(text="🛒 Купить петуха", callback_data=f"shop:{user_id}:cat:roosters")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cockfight_bet_keyboard(user_id: int, tier: str) -> InlineKeyboardMarkup:
    """Create cockfight bet keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 50", callback_data=f"{COCK_PREFIX}{user_id}:fight:{tier}:50"),
            InlineKeyboardButton(text="💰 100", callback_data=f"{COCK_PREFIX}{user_id}:fight:{tier}:100"),
            InlineKeyboardButton(text="💰 200", callback_data=f"{COCK_PREFIX}{user_id}:fight:{tier}:200"),
        ],
        [
            InlineKeyboardButton(text="💰 500", callback_data=f"{COCK_PREFIX}{user_id}:fight:{tier}:500"),
            InlineKeyboardButton(text="💰 1000", callback_data=f"{COCK_PREFIX}{user_id}:fight:{tier}:1000"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{COCK_PREFIX}{user_id}:back")],
    ])


@router.message(Command("cockfight"))
async def cmd_cockfight(message: Message):
    """Start cockfight game."""
    from datetime import datetime, timezone, timedelta
    from app.database.models import GameStat
    from app.database.session import get_session
    from sqlalchemy import select
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Check cooldown (60 seconds)
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(GameStat).where(GameStat.tg_user_id == user_id)
        )
        game_stat = result.scalars().first()
        
        if game_stat and game_stat.last_cockfight:
            now = datetime.now(timezone.utc)
            if game_stat.last_cockfight.tzinfo is None:
                last_fight = game_stat.last_cockfight.replace(tzinfo=timezone.utc)
            else:
                last_fight = game_stat.last_cockfight
            
            cooldown_seconds = 300  # 5 minutes
            elapsed = (now - last_fight).total_seconds()
            
            if elapsed < cooldown_seconds:
                remaining = int(cooldown_seconds - elapsed)
                await message.reply(
                    f"⏳ Петухи отдыхают! Подожди {remaining} сек.",
                    parse_mode="HTML"
                )
                return
    
    balance = await get_user_balance(user_id, chat_id)
    
    text = (
        "🐔 <b>ПЕТУШИНЫЕ БОИ</b> 🐔\n\n"
        "Выбери своего бойца и сделай ставку!\n\n"
        "🐔 <b>Обычный</b> — базовая сила, x1.2 выигрыш\n"
        "🐓 <b>Редкий</b> — сильнее, x1.4 выигрыш\n"
        "🦃 <b>Эпический</b> — элита, x1.7 выигрыш\n\n"
        "⚠️ Стоимость боя: ставка + 10% на корм\n"
        "⏱️ Кулдаун: 5 минут\n\n"
        f"💰 Баланс: {balance} монет\n\n"
        "Выбери петуха:"
    )
    
    keyboard = await get_cockfight_keyboard(user_id, chat_id)
    await message.reply(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith(COCK_PREFIX))
async def callback_cockfight(callback: CallbackQuery):
    """Handle cockfight callbacks."""
    parts = callback.data.split(":")
    if len(parts) < 3:
        return await callback.answer("Ошибка")
    
    _, owner_id, action = parts[:3]
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if int(owner_id) != user_id:
        return await callback.answer("Это не твой петух!", show_alert=True)
    
    if action == "select":
        tier = parts[3] if len(parts) > 3 else "common"
        tier_names = {"common": "Обычный 🐔", "rare": "Редкий 🐓", "epic": "Эпический 🦃"}
        
        text = (
            f"🐔 <b>ПЕТУШИНЫЕ БОИ</b>\n\n"
            f"Выбран: {tier_names.get(tier, tier)}\n\n"
            f"Выбери ставку:"
        )
        await callback.message.edit_text(text, reply_markup=get_cockfight_bet_keyboard(user_id, tier), parse_mode="HTML")
        await callback.answer()
    
    elif action == "fight":
        from datetime import datetime, timezone
        from app.database.models import GameStat
        from app.database.session import get_session
        from sqlalchemy import select
        from app.services.inventory import inventory_service, ItemType
        from app.handlers.inventory import consume_booster_effect
        
        tier = parts[3] if len(parts) > 3 else "common"
        bet = int(parts[4]) if len(parts) > 4 else 25
        
        # Check for luck bonus
        luck_bonus = await consume_booster_effect(user_id, chat_id, "luck_bonus") or 0.0
        
        # Verify rooster ownership before fight
        tier_to_item = {
            "common": ItemType.ROOSTER_COMMON,
            "rare": ItemType.ROOSTER_RARE,
            "epic": ItemType.ROOSTER_EPIC
        }
        required_item = tier_to_item.get(tier, ItemType.ROOSTER_COMMON)
        
        if not await inventory_service.has_item(user_id, chat_id, required_item):
            return await callback.answer("❌ У тебя нет этого петуха! Купи в /shop", show_alert=True)
        
        # Check rooster HP
        from app.services.rooster_hp import can_fight, damage_rooster, FIGHT_HP_LOSS_MIN, FIGHT_HP_LOSS_MAX
        import random
        
        can_fight_result, reason = await can_fight(user_id, chat_id, required_item)
        if not can_fight_result:
            return await callback.answer(reason, show_alert=True)
        
        # Calculate entry fee (10% of bet for rooster food)
        entry_fee = max(5, int(bet * 0.1))
        total_cost = bet + entry_fee
        
        balance = await get_user_balance(user_id, chat_id)
        if balance < total_cost:
            return await callback.answer(f"Недостаточно монет! Нужно {total_cost} (ставка {bet} + корм {entry_fee})", show_alert=True)
        
        # Update cooldown
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(GameStat).where(GameStat.tg_user_id == user_id)
            )
            game_stat = result.scalars().first()
            
            if game_stat:
                game_stat.last_cockfight = datetime.now(timezone.utc)
                await session.commit()
        
        # Deduct bet + entry fee
        await update_user_balance(user_id, chat_id, -total_cost)
        
        # Map tier string to enum
        tier_map = {"common": RoosterTier.COMMON, "rare": RoosterTier.RARE, "epic": RoosterTier.EPIC}
        rooster_tier = tier_map.get(tier, RoosterTier.COMMON)
        
        # Check for boosters
        from app.handlers.inventory import consume_booster_effect, get_booster_effect
        damage_bonus = 0.0
        crit_bonus = 0.0
        
        # Check damage boost (steroids)
        damage_boost_data = await get_booster_effect(user_id, chat_id, "damage_boost")
        if damage_boost_data:
            damage_bonus = damage_boost_data.get("damage_bonus", 0.2)
        
        # Check critical boost (adrenaline) - one-time use
        crit_boost_data = await consume_booster_effect(user_id, chat_id, "critical_boost")
        if crit_boost_data:
            crit_bonus = crit_boost_data.get("crit_chance", 0.15)
        
        # Play game with all bonuses
        result = cockfight_game.fight(user_id, bet, rooster_tier, luck_bonus, damage_bonus, crit_bonus)
        
        # Apply HP damage to rooster after fight
        hp_loss = random.randint(FIGHT_HP_LOSS_MIN, FIGHT_HP_LOSS_MAX)
        new_hp, max_hp = await damage_rooster(user_id, chat_id, required_item, hp_loss)
        
        # Update balance with result (winnings already include bet back if won)
        if result.won:
            # Won: add winnings (which is bet * multiplier)
            new_balance = await update_user_balance(user_id, chat_id, result.winnings + bet)
        elif result.winnings == 0:
            # Draw: refund bet
            new_balance = await update_user_balance(user_id, chat_id, bet)
        else:
            # Lost: bet already deducted
            new_balance = await get_user_balance(user_id, chat_id)
        
        text = f"{result.message}\n\n💰 Баланс: {new_balance} монет\n❤️ HP петуха: {new_hp}/{max_hp} (-{hp_loss})"
        keyboard = await get_cockfight_keyboard(user_id, chat_id)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
    
    elif action == "back":
        balance = await get_user_balance(user_id, chat_id)
        text = (
            "🐔 <b>ПЕТУШИНЫЕ БОИ</b> 🐔\n\n"
            "Выбери своего бойца и сделай ставку!\n\n"
            f"💰 Баланс: {balance} монет\n\n"
            "Выбери петуха:"
        )
        keyboard = await get_cockfight_keyboard(user_id, chat_id)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()


# ============================================================================
# BALANCE & DAILY BONUS
# ============================================================================

@router.message(Command("balance"))
async def cmd_balance(message: Message):
    """Show user balance."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    balance = await get_user_balance(user_id, chat_id)
    
    await message.reply(
        f"💰 <b>Твой баланс</b>\n\n"
        f"🪙 {balance} монет\n\n"
        f"<i>Зарабатывай в играх: /games</i>",
        parse_mode="HTML"
    )


@router.message(Command("daily"))
async def cmd_daily(message: Message):
    """Claim daily bonus."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # TODO: Add proper daily tracking with cooldown
    # For now, just give a small bonus (reduced from 100 to 50 for balance)
    bonus = 50
    new_balance = await update_user_balance(user_id, chat_id, bonus)
    
    await message.reply(
        f"🎁 <b>Ежедневный бонус!</b>\n\n"
        f"+{bonus} монет\n\n"
        f"💰 Баланс: {new_balance} монет\n\n"
        f"<i>Приходи завтра за новым бонусом!</i>",
        parse_mode="HTML"
    )
    
    logger.info(f"Daily bonus claimed by user {user_id}: +{bonus}")


@router.message(Command("transfer"))
async def cmd_transfer(message: Message):
    """Transfer coins to another user."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Parse command: /transfer @user amount
    parts = message.text.split()
    if len(parts) < 3:
        return await message.reply(
            "💸 <b>Перевод монет</b>\n\n"
            "Использование: /transfer @username сумма\n"
            "Пример: /transfer @friend 100",
            parse_mode="HTML"
        )
    
    # Get target user
    target_mention = parts[1]
    if not target_mention.startswith("@"):
        return await message.reply("❌ Укажи пользователя через @username")
    
    try:
        amount = int(parts[2])
    except ValueError:
        return await message.reply("❌ Укажи корректную сумму")
    
    if amount <= 0:
        return await message.reply("❌ Сумма должна быть положительной")
    
    balance = await get_user_balance(user_id, chat_id)
    if balance < amount:
        return await message.reply(f"❌ Недостаточно монет! У тебя {balance}")
    
    # For now, just show the intent (need target user ID for actual transfer)
    await message.reply(
        f"💸 Для перевода {amount} монет пользователю {target_mention}, "
        f"попроси его написать что-нибудь в чат, чтобы я мог его найти.",
        parse_mode="HTML"
    )


# ============================================================================
# INVENTORY COMMAND (moved to app/handlers/inventory.py)
# ============================================================================

# Old inventory handler removed - now handled by inventory.py with inline buttons


# ============================================================================
# USE CONSUMABLE ITEMS (DEPRECATED - redirects to /inventory)
# ============================================================================

@router.message(Command("use"))
async def cmd_use(message: Message):
    """Use a consumable item - redirects to unified inventory."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    parts = message.text.split(maxsplit=1)
    
    # If no item specified, redirect to inventory
    if len(parts) < 2:
        # Import inventory handler functions
        from app.handlers.inventory import build_inventory_text, build_inventory_keyboard
        
        text = await build_inventory_text(user_id, chat_id)
        keyboard = await build_inventory_keyboard(user_id, chat_id)
        
        await message.reply(
            "💡 <b>Совет:</b> Используй /inventory для управления предметами!\n\n" + text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return
    
    item_name = parts[1].lower().strip()
    
    # Map Russian names to item types
    item_map = {
        "энергетик": ItemType.ENERGY_DRINK,
        "energy": ItemType.ENERGY_DRINK,
        "талисман": ItemType.LUCKY_CHARM,
        "luck": ItemType.LUCKY_CHARM,
        "щит": ItemType.SHIELD,
        "shield": ItemType.SHIELD,
    }
    
    item_type = item_map.get(item_name)
    if not item_type:
        # Redirect to inventory for unknown items
        from app.handlers.inventory import build_inventory_text, build_inventory_keyboard
        
        text = await build_inventory_text(user_id, chat_id)
        keyboard = await build_inventory_keyboard(user_id, chat_id)
        
        await message.reply(
            "❌ Неизвестный предмет.\n\n"
            "💡 Используй /inventory для управления предметами!\n\n" + text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return
    
    # Use the unified inventory handler for boosters
    from app.handlers.inventory import apply_booster, build_inventory_text, build_inventory_keyboard
    
    result = await apply_booster(user_id, chat_id, item_type)
    
    if result.success:
        text = await build_inventory_text(user_id, chat_id)
        keyboard = await build_inventory_keyboard(user_id, chat_id)
        await message.reply(
            f"{result.message}\n\n{text}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await message.reply(result.message, parse_mode="HTML")
    
    logger.info(f"User {user_id} used /use command (redirected to inventory)")


# ============================================================================
# PP CAGE MANAGEMENT (DEPRECATED - redirects to /inventory)
# ============================================================================

@router.message(Command("cage"))
async def cmd_cage(message: Message):
    """
    Manage PP Cage - redirects to unified inventory.
    
    Usage:
      /cage - show inventory with cage controls
      /cage on - activate cage via inventory
      /cage off - deactivate cage via inventory
      
    Requirements: 10.5 (backward compatibility)
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    parts = message.text.split()
    action = parts[1].lower() if len(parts) > 1 else None
    
    # Import inventory handler functions
    from app.handlers.inventory import toggle_cage, build_inventory_text, build_inventory_keyboard
    
    if action == "on":
        # Activate cage via unified handler
        result = await toggle_cage(user_id, chat_id, activate=True)
        
        if result.success:
            text = await build_inventory_text(user_id, chat_id)
            keyboard = await build_inventory_keyboard(user_id, chat_id)
            await message.reply(
                f"{result.message}\n\n"
                f"💡 <b>Совет:</b> Используй /inventory для управления клеткой!\n\n{text}",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await message.reply(result.message, parse_mode="HTML")
    
    elif action == "off":
        # Deactivate cage via unified handler
        result = await toggle_cage(user_id, chat_id, activate=False)
        
        if result.success:
            text = await build_inventory_text(user_id, chat_id)
            keyboard = await build_inventory_keyboard(user_id, chat_id)
            await message.reply(
                f"{result.message}\n\n"
                f"💡 <b>Совет:</b> Используй /inventory для управления клеткой!\n\n{text}",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await message.reply(result.message, parse_mode="HTML")
    
    else:
        # Show inventory with cage controls
        text = await build_inventory_text(user_id, chat_id)
        keyboard = await build_inventory_keyboard(user_id, chat_id)
        
        # Check cage status for info message
        has_cage = await inventory_service.has_item(user_id, chat_id, ItemType.PP_CAGE)
        is_active = await inventory_service.has_active_item(user_id, chat_id, ItemType.PP_CAGE)
        
        status_text = ""
        if is_active:
            status_text = "🔒 <b>Клетка активна!</b>\n\n"
        elif has_cage:
            status_text = "🔓 <b>Клетка в инвентаре</b>\n\n"
        else:
            status_text = "❌ <b>Клетки нет</b> — купи в /shop\n\n"
        
        await message.reply(
            f"{status_text}"
            f"💡 <b>Совет:</b> Используй /inventory для управления клеткой!\n\n{text}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    logger.info(f"User {user_id} used /cage command (redirected to inventory)")


# ============================================================================
# PP BATTLE GAME (Битва пиписек) - использует GameStat.size_cm от /grow
# ============================================================================

PP_PREFIX = "pp:"

# Хранилище активных вызовов на битву {challenge_id: PPChallenge}
pp_challenges: dict[str, dict] = {}


def get_pp_size_emoji(size: int) -> str:
    """Get emoji representation of PP size."""
    if size <= 0:
        return "❓"
    elif size < 10:
        return "🤏"
    elif size < 30:
        return "👌"
    elif size < 50:
        return "👍"
    elif size < 100:
        return "💪"
    elif size < 200:
        return "🔥"
    elif size < 500:
        return "🚀"
    else:
        return "🏆"


def get_pp_bar(size: int, max_display: int = 30) -> str:
    """Generate visual PP bar."""
    # Масштабируем для отображения (каждые 10 см = 1 символ)
    display_size = min(size // 10, max_display)
    if display_size < 1:
        display_size = 1
    bar = "8" + "=" * display_size + "D"
    return bar


async def get_or_create_game_stat(tg_user_id: int, username: str = None) -> tuple[int, int, int]:
    """Get user's PP stats from GameStat. Returns (size_cm, pvp_wins, pvp_losses)."""
    async_session = get_session()
    async with async_session() as session:
        # Сначала проверяем/создаём User
        res = await session.execute(
            select(User).where(User.tg_user_id == tg_user_id)
        )
        user = res.scalars().first()
        if not user:
            user = User(tg_user_id=tg_user_id, username=username or "")
            session.add(user)
            await session.flush()
        
        # Теперь GameStat
        res = await session.execute(
            select(GameStat).where(GameStat.tg_user_id == tg_user_id)
        )
        gs = res.scalars().first()
        if not gs:
            gs = GameStat(user_id=user.id, tg_user_id=tg_user_id, username=username)
            session.add(gs)
            await session.commit()
        
        return gs.size_cm, gs.pvp_wins, getattr(gs, 'pvp_losses', 0)


async def apply_pp_change(user_id: int, chat_id: int, change: int) -> int:
    """
    Apply PP size change with PP_CAGE protection check.
    
    If change is negative and user has active PP_CAGE, the change is blocked.
    
    Args:
        user_id: Telegram user ID
        chat_id: Chat ID
        change: Amount to change (positive or negative)
        
    Returns:
        Actual change applied (0 if blocked by PP_CAGE)
        
    Requirements: 10.3
    """
    from app.services.inventory import inventory_service, ItemType as InvItemType
    
    if change < 0:
        # Check if PP_CAGE is active
        if await inventory_service.has_active_item(user_id, chat_id, InvItemType.PP_CAGE):
            return 0  # Protection activated, no change
    
    return change


async def update_pp_size(tg_user_id: int, change: int, chat_id: int = 0) -> int:
    """
    Update PP size (GameStat.size_cm) and return new value.
    
    If chat_id is provided and change is negative, checks for PP_CAGE protection.
    """
    # Apply PP_CAGE protection if chat_id is provided
    if chat_id and change < 0:
        actual_change = await apply_pp_change(tg_user_id, chat_id, change)
        if actual_change == 0:
            # PP_CAGE blocked the change, return current size
            async_session = get_session()
            async with async_session() as session:
                res = await session.execute(
                    select(GameStat).where(GameStat.tg_user_id == tg_user_id)
                )
                gs = res.scalars().first()
                return gs.size_cm if gs else 0
        change = actual_change
    
    async_session = get_session()
    async with async_session() as session:
        res = await session.execute(
            select(GameStat).where(GameStat.tg_user_id == tg_user_id)
        )
        gs = res.scalars().first()
        if gs:
            gs.size_cm = max(1, gs.size_cm + change)
            await session.commit()
            return gs.size_cm
        return 0


async def update_pp_stats(tg_user_id: int, won: bool) -> None:
    """Update PP battle stats in GameStat."""
    async_session = get_session()
    async with async_session() as session:
        res = await session.execute(
            select(GameStat).where(GameStat.tg_user_id == tg_user_id)
        )
        gs = res.scalars().first()
        if gs:
            if won:
                gs.pvp_wins += 1
            else:
                gs.pvp_losses += 1
            await session.commit()


def get_pp_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Create PP game keyboard (для callback-ов, если нужно)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏆 Топ", callback_data=f"{PP_PREFIX}{user_id}:top"),
        ]
    ])


def get_bet_keyboard(user_id: int, max_bet: int) -> InlineKeyboardMarkup:
    """Create bet selection keyboard."""
    # Предлагаем ставки: 10, 20, 50, 100, 200 см (но не больше чем есть)
    bets = [b for b in [10, 20, 50, 100, 200] if b <= max_bet]
    if not bets:
        # Если меньше 10 см — предлагаем всё что есть
        bets = [max_bet] if max_bet > 0 else [1]
    
    buttons = []
    row = []
    for bet in bets:
        row.append(InlineKeyboardButton(text=f"{bet} см", callback_data=f"{PP_PREFIX}{user_id}:bet:{bet}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data=f"{PP_PREFIX}{user_id}:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_challenge_keyboard(challenge_id: str, target_id: int) -> InlineKeyboardMarkup:
    """Create challenge accept/decline keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ Принять бой!", callback_data=f"{PP_PREFIX}accept:{challenge_id}"),
            InlineKeyboardButton(text="🏃 Сбежать", callback_data=f"{PP_PREFIX}decline:{challenge_id}"),
        ]
    ])


@router.message(Command("pp"))
async def cmd_pp(message: Message):
    """PP battle game - использует размер из /grow.
    
    Использование:
    - /pp — справка по командам
    - /pp @username [ставка] — вызвать конкретного человека
    - /pp [ставка] — открытый вызов со ставкой
    - Ответ на сообщение: /pp [ставка] — вызвать автора сообщения
    """
    user_id = message.from_user.id
    username = message.from_user.first_name or "Аноним"
    tg_username = message.from_user.username
    chat_id = message.chat.id
    
    # Парсим аргументы
    args = message.text.split()[1:] if message.text else []
    target_username = None
    target_id = 0  # 0 = открытый вызов
    bet = 20  # Дефолтная ставка
    
    # Если нет аргументов и нет reply — показываем справку
    if not args and not message.reply_to_message:
        size, wins, losses = await get_or_create_game_stat(user_id, tg_username)
        help_text = (
            "🍆 <b>PP БИТВЫ</b>\n\n"
            f"📏 Твой размер: <b>{size} см</b>\n"
            f"📊 Побед/Поражений: {wins}/{losses}\n\n"
            "<b>Команды:</b>\n"
            "• /pp @user [ставка] — вызвать игрока\n"
            "• /pp [ставка] — открытый вызов\n"
            "• /ppo — бой с Олегом (PvE)\n"
            "• /grow — вырастить пипиську\n"
            "• /ppstats — статистика\n"
            "• /pptop — топ игроков\n\n"
            "<i>Ответь на сообщение с /pp чтобы вызвать автора</i>"
        )
        await message.reply(help_text, parse_mode="HTML")
        return
    
    # Проверяем reply — вызов автора сообщения
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        if target_user.id == user_id:
            await message.reply("❌ Нельзя вызвать самого себя!")
            return
        if target_user.is_bot:
            await message.reply("❌ Нельзя вызвать бота! Используй /ppo для боя с Олегом")
            return
        target_username = target_user.username
        target_id = target_user.id
        # Ставка из аргументов
        if args and args[0].isdigit():
            bet = int(args[0])
    # Проверяем @username в аргументах
    elif args and args[0].startswith("@"):
        target_username = args[0][1:]  # Убираем @
        if len(args) > 1 and args[1].isdigit():
            bet = int(args[1])
        target_id = 0  # Будет определён при принятии по username
    # Проверяем числовую ставку
    elif args and args[0].isdigit():
        bet = int(args[0])
        target_id = 0  # Открытый вызов
    # Просто /pp — открытый вызов с дефолтной ставкой
    else:
        target_id = 0
    
    # Получаем размер игрока
    size, wins, losses = await get_or_create_game_stat(user_id, tg_username)
    
    if size == 0:
        text = (
            f"🍆 <b>Пиписька {username}</b>\n\n"
            f"❓ Размер: <b>неизвестен</b>\n\n"
            f"Сначала используй /grow чтобы вырастить пипиську!\n\n"
            f"<i>/pp — вызов на бой | /ppo — бой с Олегом</i>"
        )
        await message.reply(text)
        return
    
    # Ограничиваем ставку
    if bet < 1:
        bet = 1
    if bet > size:
        bet = min(bet, size)
    
    # Получаем таймаут из настроек чата
    from app.services.bot_config import get_pvp_accept_timeout
    timeout = await get_pvp_accept_timeout(chat_id)
    
    # Создаём вызов
    challenge_id = str(uuid.uuid4())[:8]
    pp_challenges[challenge_id] = {
        "challenger_id": user_id,
        "challenger_name": username,
        "challenger_size": size,
        "target_id": target_id,
        "target_username": target_username,
        "bet": bet,
        "chat_id": chat_id,
        "created_at": utc_now(),
        "timeout": timeout,
    }
    
    bar = get_pp_bar(size)
    
    if target_username:
        mention = f"@{target_username}"
        text = (
            f"⚔️ <b>ВЫЗОВ НА БИТВУ ПИПИСЕК!</b>\n\n"
            f"🍆 <b>{username}</b> вызывает {mention}!\n\n"
            f"{bar}\n"
            f"📏 Размер: <b>{size} см</b>\n"
            f"💰 Ставка: <b>{bet} см</b>\n"
            f"⏱ Время: <b>{timeout} сек</b>\n\n"
            f"<i>У соперника должно быть минимум {bet} см!</i>"
        )
    else:
        text = (
            f"⚔️ <b>ВЫЗОВ НА БИТВУ ПИПИСЕК!</b>\n\n"
            f"🍆 <b>{username}</b> бросает вызов!\n\n"
            f"{bar}\n"
            f"📏 Размер: <b>{size} см</b>\n"
            f"💰 Ставка: <b>{bet} см</b>\n"
            f"⏱ Время: <b>{timeout} сек</b>\n\n"
            f"<i>Кто осмелится принять бой?</i>"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Принять бой!", callback_data=f"{PP_PREFIX}fight:{challenge_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"{PP_PREFIX}{user_id}:cancel_challenge:{challenge_id}")]
    ])
    
    await message.reply(text, reply_markup=keyboard)


@router.message(Command("ppo"))
async def cmd_pp_oleg(message: Message):
    """Бой с Олегом (PvE) - отдельная команда."""
    user_id = message.from_user.id
    username = message.from_user.first_name or "Аноним"
    tg_username = message.from_user.username
    chat_id = message.chat.id
    
    size, _, _ = await get_or_create_game_stat(user_id, tg_username)
    
    if size < 1:
        await message.reply("❌ Сначала вырасти пипиську через /grow!")
        return
    
    # Проверяем активную клетку — защищает от потерь
    has_cage = await inventory_service.has_active_item(user_id, chat_id, ItemType.PP_CAGE)
    
    # Олег имеет случайный размер от 50% до 150% от игрока (минимум 5)
    oleg_size = random.randint(int(size * 0.5), int(size * 1.5))
    oleg_size = max(5, oleg_size)
    
    # Ставка = 10% от размера игрока (минимум 1)
    bet = max(1, size // 10)
    
    # Если есть клетка — ставка 0 (защита от потерь)
    if has_cage:
        bet = 0
    
    # Выполняем битву
    result_text = await execute_pp_battle(
        chat_id,
        user_id, username, size,
        0, "Олег 🤖", oleg_size,
        bet
    )
    
    # Добавляем инфо о клетке если активна
    if has_cage:
        result_text += "\n\n🔒 <i>Клетка защитила от потери размера!</i>"
    
    await message.reply(result_text, parse_mode="HTML")


@router.message(Command("ppstats"))
async def cmd_pp_stats(message: Message):
    """Показать статистику пиписьки."""
    user_id = message.from_user.id
    username = message.from_user.first_name or "Аноним"
    tg_username = message.from_user.username
    
    size, wins, losses = await get_or_create_game_stat(user_id, tg_username)
    
    if size == 0:
        text = (
            f"🍆 <b>Пиписька {username}</b>\n\n"
            f"❓ Размер: <b>неизвестен</b>\n\n"
            f"Сначала используй /grow чтобы вырастить пипиську!"
        )
        await message.reply(text)
        return
    
    emoji = get_pp_size_emoji(size)
    bar = get_pp_bar(size)
    
    total_battles = wins + losses
    winrate = (wins / total_battles * 100) if total_battles > 0 else 0
    
    text = (
        f"🍆 <b>Пиписька {username}</b>\n\n"
        f"{bar}\n\n"
        f"📏 Размер: <b>{size} см</b> {emoji}\n"
        f"⚔️ PvP: {wins}W / {losses}L ({winrate:.0f}%)\n\n"
        f"<i>/pp — вызов | /ppo — бой с Олегом</i>"
    )
    
    await message.reply(text)


async def execute_pp_battle(
    chat_id: int,
    challenger_id: int, challenger_name: str, challenger_size: int,
    target_id: int, target_name: str, target_size: int,
    bet: int
) -> str:
    """Execute PP battle and return result text."""
    # Определяем победителя (увеличен рандом до ±40% + шанс крита)
    challenger_variance = random.randint(-challenger_size * 2 // 5, challenger_size * 2 // 5)
    target_variance = random.randint(-target_size * 2 // 5, target_size * 2 // 5)
    
    # 15% шанс критического удара (x1.5 к силе)
    challenger_crit = random.random() < 0.15
    target_crit = random.random() < 0.15
    
    challenger_power = challenger_size + challenger_variance
    target_power = target_size + target_variance
    
    if challenger_crit:
        challenger_power = int(challenger_power * 1.5)
    if target_crit:
        target_power = int(target_power * 1.5)
    
    crit_text = ""
    if challenger_crit or target_crit:
        crit_names = []
        if challenger_crit:
            crit_names.append(challenger_name)
        if target_crit:
            crit_names.append(target_name)
        crit_text = f"\n💥 <b>КРИТИЧЕСКИЙ УДАР!</b> ({', '.join(crit_names)})"
    
    if challenger_power > target_power:
        winner_id, winner_name = challenger_id, challenger_name
        loser_id, loser_name = target_id, target_name
        winner_power, loser_power = challenger_power, target_power
    elif target_power > challenger_power:
        winner_id, winner_name = target_id, target_name
        loser_id, loser_name = challenger_id, challenger_name
        winner_power, loser_power = target_power, challenger_power
    else:
        # Ничья — никто не теряет
        return (
            f"⚔️ <b>БИТВА ПИПИСЕК!</b>\n\n"
            f"🍆 {challenger_name}: {challenger_size} см (сила: {challenger_power})\n"
            f"🍆 {target_name}: {target_size} см (сила: {target_power}){crit_text}\n\n"
            f"🤝 <b>НИЧЬЯ!</b>\n"
            f"Пиписьки оказались равны по силе!\n"
            f"Ставка {bet} см возвращена обоим."
        )
    
    # Check if loser has active cage and handle HP system
    cage_protected = False
    cage_broken = False
    reduced_bet = bet
    
    if loser_id > 0:
        from app.services.inventory import inventory_service, ItemType
        has_cage = await inventory_service.has_active_item(loser_id, chat_id, ItemType.PP_CAGE)
        
        if has_cage:
            # Get cage item and check HP
            cage_item = await inventory_service.get_item(loser_id, chat_id, ItemType.PP_CAGE)
            if cage_item and cage_item.item_data:
                import json
                try:
                    cage_data = json.loads(cage_item.item_data)
                    cage_hp = cage_data.get("cage_hp", 5)
                    
                    if cage_hp > 1:
                        # Cage takes damage but survives
                        cage_data["cage_hp"] = cage_hp - 1
                        cage_item.item_data = json.dumps(cage_data)
                        
                        from app.database.session import get_session
                        async_session = get_session()
                        async with async_session() as session:
                            await session.merge(cage_item)
                            await session.commit()
                        
                        cage_protected = True
                        reduced_bet = bet // 2  # Winner gets only 50% when cage protects
                    else:
                        # Cage breaks (HP = 1 -> 0)
                        cage_broken = True
                        await inventory_service.remove_item(loser_id, chat_id, ItemType.PP_CAGE, 1)
                except (json.JSONDecodeError, ValueError):
                    pass
    
    # Обновляем статистику (только для реальных игроков, не для Олега id=0)
    if winner_id > 0:
        await update_pp_stats(winner_id, won=True)
        await update_pp_size(winner_id, reduced_bet, chat_id)
        winner_new_size, _, _ = await get_or_create_game_stat(winner_id)
    else:
        winner_new_size = target_size + reduced_bet  # Олег "выиграл"
    
    if loser_id > 0:
        await update_pp_stats(loser_id, won=False)
        
        if cage_protected:
            # Cage protected - no size loss for loser
            loser_new_size, _, _ = await get_or_create_game_stat(loser_id)
            cage_hp_remaining = 0
            cage_item = await inventory_service.get_item(loser_id, chat_id, ItemType.PP_CAGE)
            if cage_item and cage_item.item_data:
                try:
                    cage_data = json.loads(cage_item.item_data)
                    cage_hp_remaining = cage_data.get("cage_hp", 0)
                except:
                    pass
            
            return (
                f"⚔️ <b>БИТВА ПИПИСЕК!</b>\n\n"
                f"🍆 {challenger_name}: {challenger_size} см (сила: {challenger_power})\n"
                f"🍆 {target_name}: {target_size} см (сила: {target_power}){crit_text}\n\n"
                f"🏆 <b>ПОБЕДИТЕЛЬ: {winner_name}!</b>\n\n"
                f"💪 {winner_name}: +{reduced_bet} см → <b>{winner_new_size} см</b>\n"
                f"🔒 {loser_name}: Клетка защитила! Размер: <b>{loser_new_size} см</b>\n"
                f"⚠️ Прочность клетки: {cage_hp_remaining} HP"
            )
        elif cage_broken:
            # Cage broke - full damage
            await update_pp_size(loser_id, -bet, chat_id)
            loser_new_size, _, _ = await get_or_create_game_stat(loser_id)
            return (
                f"⚔️ <b>БИТВА ПИПИСЕК!</b>\n\n"
                f"🍆 {challenger_name}: {challenger_size} см (сила: {challenger_power})\n"
                f"🍆 {target_name}: {target_size} см (сила: {target_power}){crit_text}\n\n"
                f"🏆 <b>ПОБЕДИТЕЛЬ: {winner_name}!</b>\n\n"
                f"💪 {winner_name}: +{bet} см → <b>{winner_new_size} см</b>\n"
                f"💀 {loser_name}: -{bet} см → <b>{loser_new_size} см</b>\n"
                f"💔 <b>КЛЕТКА СЛОМАЛАСЬ!</b>"
            )
        else:
            # No cage - normal damage
            await update_pp_size(loser_id, -bet, chat_id)
            loser_new_size, _, _ = await get_or_create_game_stat(loser_id)
    else:
        loser_new_size = target_size - bet  # Олег "проиграл"
    
    return (
        f"⚔️ <b>БИТВА ПИПИСЕК!</b>\n\n"
        f"🍆 {challenger_name}: {challenger_size} см (сила: {challenger_power})\n"
        f"🍆 {target_name}: {target_size} см (сила: {target_power}){crit_text}\n\n"
        f"🏆 <b>ПОБЕДИТЕЛЬ: {winner_name}!</b>\n\n"
        f"💪 {winner_name}: +{bet} см → <b>{winner_new_size} см</b>\n"
        f"💀 {loser_name}: -{bet} см → <b>{loser_new_size} см</b>"
    )


@router.callback_query(F.data.startswith(PP_PREFIX))
async def pp_callback(callback: CallbackQuery):
    """Handle PP game callbacks."""
    data = callback.data[len(PP_PREFIX):]
    parts = data.split(":")
    
    if len(parts) < 1:
        return await callback.answer("❌ Ошибка")
    
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    username = callback.from_user.first_name or "Аноним"
    
    # Обработка принятия вызова (fight: или accept:)
    if parts[0] in ("accept", "fight") and len(parts) >= 2:
        challenge_id = parts[1]
        challenge = pp_challenges.get(challenge_id)
        
        if not challenge:
            return await callback.answer("❌ Вызов истёк или не найден", show_alert=True)
        
        # Нельзя принять свой вызов
        if user_id == challenge["challenger_id"]:
            return await callback.answer("❌ Нельзя принять свой же вызов!", show_alert=True)
        
        # Проверяем таймаут (2 минуты = 120 сек)
        timeout = challenge.get("timeout", 120)
        created_at = challenge.get("created_at")
        if created_at:
            elapsed = (utc_now() - created_at).total_seconds()
            if elapsed > timeout:
                del pp_challenges[challenge_id]
                return await callback.answer(f"❌ Время на принятие вызова истекло!", show_alert=True)
        
        # Проверяем target_id: 0 или None = открытый вызов (любой может принять)
        target_id = challenge.get("target_id", 0)
        target_username = challenge.get("target_username")
        
        # Если вызов по @username — проверяем username (case-insensitive) ПРИОРИТЕТНО
        if target_username:
            user_tg_username = callback.from_user.username or ""
            if not user_tg_username:
                return await callback.answer(f"❌ Этот вызов для @{target_username}! У тебя нет username.", show_alert=True)
            if user_tg_username.lower() != target_username.lower():
                return await callback.answer(f"❌ Этот вызов для @{target_username}!", show_alert=True)
        
        # Если вызов по user_id (через reply) — проверяем user_id
        elif target_id and target_id != 0 and user_id != target_id:
            # Вызов адресован конкретному человеку
            return await callback.answer("❌ Этот вызов не для тебя!", show_alert=True)
        
        # Проверяем что у цели хватает см для ставки
        target_size, _, _ = await get_or_create_game_stat(user_id)
        if target_size < challenge["bet"]:
            return await callback.answer(f"❌ У тебя только {target_size} см, а ставка {challenge['bet']} см!", show_alert=True)
        
        # Выполняем битву
        result_text = await execute_pp_battle(
            chat_id,
            challenge["challenger_id"], challenge["challenger_name"], challenge["challenger_size"],
            user_id, username, target_size,
            challenge["bet"]
        )
        
        del pp_challenges[challenge_id]
        await callback.message.edit_text(result_text)
        await callback.answer("⚔️ Битва завершена!")
        return
    
    elif parts[0] == "decline" and len(parts) >= 2:
        challenge_id = parts[1]
        challenge = pp_challenges.get(challenge_id)
        
        if not challenge:
            return await callback.answer("❌ Вызов уже истёк", show_alert=True)
        
        # Отклонить может только тот кому адресован вызов (или любой для открытого)
        target_id = challenge.get("target_id", 0)
        if target_id and target_id != 0 and user_id != target_id:
            return await callback.answer("❌ Этот вызов не для тебя!", show_alert=True)
        
        del pp_challenges[challenge_id]
        await callback.message.edit_text(
            f"🏃 <b>{username}</b> сбежал от битвы пиписек!\n\n"
            f"Видимо, не уверен в своих силах..."
        )
        await callback.answer("🏃 Ты сбежал!")
        return
    
    # Остальные действия требуют owner_id
    if len(parts) < 2:
        return await callback.answer("❌ Ошибка")
    
    try:
        owner_id = int(parts[0])
    except ValueError:
        return await callback.answer("❌ Ошибка")
    
    action = parts[1]
    
    # pve теперь через /ppo, но оставим для совместимости со старыми кнопками
    if action == "pve":
        # Бой с Олегом (PvE)
        if user_id != owner_id:
            return await callback.answer("❌ Это не твоя пиписька!", show_alert=True)
        
        size, _, _ = await get_or_create_game_stat(user_id)
        if size < 1:
            return await callback.answer("❌ Сначала вырасти пипиську через /grow!", show_alert=True)
        
        # Олег имеет случайный размер от 50% до 150% от игрока (минимум 5)
        oleg_size = random.randint(int(size * 0.5), int(size * 1.5))
        oleg_size = max(5, oleg_size)
        
        # Ставка = 10% от размера игрока (минимум 1)
        bet = max(1, size // 10)
        
        # Выполняем битву
        result_text = await execute_pp_battle(
            chat_id,
            user_id, username, size,
            0, "Олег 🤖", oleg_size,
            bet
        )
        
        await callback.message.edit_text(result_text, reply_markup=get_pp_keyboard(user_id))
        await callback.answer("⚔️ Битва с Олегом!")
    
    elif action == "bet" and len(parts) >= 3:
        # Выбрана ставка — создаём вызов
        if user_id != owner_id:
            return await callback.answer("❌ Это не твоя пиписька!", show_alert=True)
        
        try:
            bet = int(parts[2])
        except ValueError:
            return await callback.answer("❌ Неверная ставка")
        
        size, _, _ = await get_or_create_game_stat(user_id)
        if bet > size:
            return await callback.answer(f"❌ У тебя только {size} см!", show_alert=True)
        if bet < 1:
            return await callback.answer("❌ Минимальная ставка 1 см!", show_alert=True)
        
        # Получаем таймаут из настроек чата
        from app.services.bot_config import get_pvp_accept_timeout
        timeout = await get_pvp_accept_timeout(chat_id)
        
        # Создаём вызов
        challenge_id = str(uuid.uuid4())[:8]
        pp_challenges[challenge_id] = {
            "challenger_id": user_id,
            "challenger_name": username,
            "challenger_size": size,
            "target_id": None,  # Любой может принять
            "bet": bet,
            "chat_id": chat_id,
            "created_at": utc_now(),
            "timeout": timeout,
        }
        
        bar = get_pp_bar(size)
        text = (
            f"⚔️ <b>ВЫЗОВ НА БИТВУ ПИПИСЕК!</b>\n\n"
            f"🍆 <b>{username}</b> бросает вызов!\n\n"
            f"{bar}\n"
            f"📏 Размер: <b>{size} см</b>\n"
            f"💰 Ставка: <b>{bet} см</b>\n"
            f"⏱ Время на принятие: <b>{timeout} сек</b>\n\n"
            f"<i>Кто осмелится принять бой?</i>\n"
            f"<i>У соперника должно быть минимум {bet} см!</i>"
        )
        
        # Обновляем target_id на "любой" — первый кто нажмёт
        pp_challenges[challenge_id]["target_id"] = 0  # 0 = любой
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⚔️ Принять бой!", callback_data=f"{PP_PREFIX}fight:{challenge_id}"),
            ],
            [
                InlineKeyboardButton(text="❌ Отменить", callback_data=f"{PP_PREFIX}{user_id}:cancel_challenge:{challenge_id}"),
            ]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer(f"⚔️ Вызов создан! Ставка: {bet} см")
    
    elif action == "cancel_challenge" and len(parts) >= 3:
        # Отмена вызова создателем
        challenge_id = parts[2]
        challenge = pp_challenges.get(challenge_id)
        
        if not challenge:
            return await callback.answer("❌ Вызов уже истёк", show_alert=True)
        
        if user_id != challenge["challenger_id"]:
            return await callback.answer("❌ Только создатель может отменить!", show_alert=True)
        
        del pp_challenges[challenge_id]
        
        size, wins, losses = await get_or_create_game_stat(user_id)
        bar = get_pp_bar(size)
        emoji = get_pp_size_emoji(size)
        total_battles = wins + losses
        winrate = (wins / total_battles * 100) if total_battles > 0 else 0
        
        text = (
            f"🍆 <b>Пиписька {username}</b>\n\n"
            f"{bar}\n\n"
            f"📏 Размер: <b>{size} см</b> {emoji}\n"
            f"⚔️ Битвы: {wins}W / {losses}L ({winrate:.0f}%)\n\n"
            f"<i>Вызов отменён</i>"
        )
        
        await callback.message.edit_text(text, reply_markup=get_pp_keyboard(user_id))
        await callback.answer("❌ Вызов отменён")
    
    elif action == "cancel":
        # Отмена выбора ставки
        if user_id != owner_id:
            return await callback.answer("❌ Это не твоя пиписька!", show_alert=True)
        
        size, wins, losses = await get_or_create_game_stat(user_id)
        bar = get_pp_bar(size)
        emoji = get_pp_size_emoji(size)
        total_battles = wins + losses
        winrate = (wins / total_battles * 100) if total_battles > 0 else 0
        
        text = (
            f"🍆 <b>Пиписька {username}</b>\n\n"
            f"{bar}\n\n"
            f"📏 Размер: <b>{size} см</b> {emoji}\n"
            f"⚔️ Битвы: {wins}W / {losses}L ({winrate:.0f}%)\n\n"
            f"Выбери действие:"
        )
        
        await callback.message.edit_text(text, reply_markup=get_pp_keyboard(user_id))
        await callback.answer()
    
    elif action == "cream":
        if user_id != owner_id:
            return await callback.answer("❌ Это не твоя пиписька!", show_alert=True)
        
        # Проверяем наличие мазей (от лучшей к худшей)
        creams = [
            (ItemType.PP_CREAM_TITAN, "Эликсир 'Годзилла'", 10, 20),
            (ItemType.PP_CREAM_LARGE, "Гель 'Мегамен'", 5, 10),
            (ItemType.PP_CREAM_MEDIUM, "Крем 'Титан'", 2, 5),
            (ItemType.PP_CREAM_SMALL, "Мазь 'Подрастай'", 1, 3),
        ]
        
        used_cream = None
        for cream_type, cream_name, min_boost, max_boost in creams:
            if await inventory_service.has_item(user_id, chat_id, cream_type):
                await inventory_service.remove_item(user_id, chat_id, cream_type, 1)
                boost = random.randint(min_boost, max_boost)
                new_size = await update_pp_size(user_id, boost)
                used_cream = (cream_name, boost, new_size)
                break
        
        if used_cream:
            cream_name, boost, new_size = used_cream
            bar = get_pp_bar(new_size)
            emoji = get_pp_size_emoji(new_size)
            
            text = (
                f"🧴 <b>Использована {cream_name}!</b>\n\n"
                f"{bar}\n\n"
                f"📈 +{boost} см!\n"
                f"📏 Новый размер: <b>{new_size} см</b> {emoji}"
            )
            await callback.message.edit_text(text, reply_markup=get_pp_keyboard(user_id))
            await callback.answer(f"📈 +{boost} см!")
        else:
            await callback.answer("❌ У тебя нет мазей! Купи в /shop", show_alert=True)
    
    elif action == "top":
        # Топ пиписек (глобальный, т.к. GameStat не привязан к чату)
        async_session = get_session()
        async with async_session() as session:
            res = await session.execute(
                select(GameStat)
                .where(GameStat.size_cm > 0)
                .order_by(GameStat.size_cm.desc())
                .limit(10)
            )
            top_users = res.scalars().all()
        
        if not top_users:
            return await callback.answer("❌ Пока никто не измерял!", show_alert=True)
        
        lines = ["🏆 <b>ТОП ПИПИСЕК</b>\n"]
        medals = ["🥇", "🥈", "🥉"]
        
        for i, gs in enumerate(top_users):
            medal = medals[i] if i < 3 else f"{i+1}."
            emoji = get_pp_size_emoji(gs.size_cm)
            name = gs.username or f"id{gs.tg_user_id}"
            lines.append(f"{medal} @{name}: {gs.size_cm} см {emoji} (W:{gs.pvp_wins}/L:{gs.pvp_losses})")
        
        text = "\n".join(lines)
        await callback.message.edit_text(text, reply_markup=get_pp_keyboard(owner_id))
        await callback.answer()
