"""Trading Handlers - P2P trades, marketplace, and auctions.

v9.5 - Complete trading system implementation.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.services.trade_service import trade_service
from app.services.market_service import market_service
from app.services.auction_service import auction_service
from app.services.inventory import inventory_service, ITEM_CATALOG
from app.services import wallet_service

logger = logging.getLogger(__name__)

router = Router()


# ============================================================================
# FSM States
# ============================================================================


class TradeStates(StatesGroup):
    """States for trade creation."""
    selecting_offer_items = State()
    entering_offer_coins = State()
    selecting_request_items = State()
    entering_request_coins = State()
    confirming = State()


class MarketStates(StatesGroup):
    """States for market listing creation."""
    selecting_item = State()
    entering_price = State()


class AuctionStates(StatesGroup):
    """States for auction creation."""
    selecting_item = State()
    entering_start_price = State()
    entering_duration = State()


# ============================================================================
# TRADES - P2P Exchange
# ============================================================================


@router.message(Command("trade"))
async def cmd_trade(message: Message, state: FSMContext):
    """Start P2P trade with another user."""
    if not message.reply_to_message:
        await message.answer("❌ Ответь на сообщение пользователя, с которым хочешь обменяться!")
        return
    
    target_user_id = message.reply_to_message.from_user.id
    if target_user_id == message.from_user.id:
        await message.answer("❌ Нельзя обмениваться с самим собой!")
        return
    
    # Get user's inventory
    inventory = await inventory_service.get_inventory(message.from_user.id, message.chat.id)
    if not inventory:
        await message.answer("❌ У тебя нет предметов для обмена!")
        return
    
    # Store trade context
    await state.update_data(
        target_user_id=target_user_id,
        target_username=message.reply_to_message.from_user.username or message.reply_to_message.from_user.first_name,
        offer_items=[],
        offer_coins=0,
        request_items=[],
        request_coins=0
    )
    
    # Show inventory selection
    keyboard = []
    for item in inventory[:10]:  # Show first 10 items
        item_info = ITEM_CATALOG.get(item.item_type)
        if item_info:
            keyboard.append([InlineKeyboardButton(
                text=f"{item_info.emoji} {item_info.name} x{item.quantity}",
                callback_data=f"trade_offer_item:{item.item_type}"
            )])
    
    keyboard.append([InlineKeyboardButton(text="💰 Предложить монеты", callback_data="trade_offer_coins")])
    keyboard.append([InlineKeyboardButton(text="➡️ Далее (запросить предметы)", callback_data="trade_next_request")])
    
    await message.answer(
        f"🔄 Обмен с @{message.reply_to_message.from_user.username or 'пользователем'}\n\n"
        "Выбери предметы, которые хочешь предложить:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await state.set_state(TradeStates.selecting_offer_items)


@router.callback_query(F.data.startswith("trade_offer_item:"))
async def trade_offer_item_callback(callback: CallbackQuery, state: FSMContext):
    """Add item to trade offer."""
    item_type = callback.data.split(":")[1]
    data = await state.get_data()
    
    offer_items = data.get("offer_items", [])
    offer_items.append({"item_type": item_type, "quantity": 1})
    await state.update_data(offer_items=offer_items)
    
    item_info = ITEM_CATALOG[item_type]
    await callback.answer(f"✅ Добавлено: {item_info.emoji} {item_info.name}")


@router.callback_query(F.data == "trade_offer_coins")
async def trade_offer_coins_callback(callback: CallbackQuery, state: FSMContext):
    """Prompt for coin amount."""
    await callback.message.answer("💰 Сколько монет хочешь предложить? (введи число)")
    await state.set_state(TradeStates.entering_offer_coins)
    await callback.answer()


@router.message(TradeStates.entering_offer_coins)
async def trade_enter_offer_coins(message: Message, state: FSMContext):
    """Enter offered coin amount."""
    try:
        amount = int(message.text)
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0!")
            return
        
        balance = await wallet_service.get_balance(message.from_user.id)
        if amount > balance:
            await message.answer(f"❌ У тебя недостаточно монет! (есть {balance})")
            return
        
        await state.update_data(offer_coins=amount)
        await message.answer(f"✅ Предложено: {amount} 🪙")
        await state.set_state(TradeStates.selecting_offer_items)
    except ValueError:
        await message.answer("❌ Введи корректное число!")


@router.callback_query(F.data == "trade_next_request")
async def trade_next_request_callback(callback: CallbackQuery, state: FSMContext):
    """Move to requesting items."""
    await callback.message.answer(
        "📥 Теперь укажи, что хочешь получить взамен:\n\n"
        "Введи тип предмета и количество через пробел, например:\n"
        "`fishing_rod_golden 1`\n\n"
        "Или введи `/coins <сумма>` для запроса монет\n"
        "Или `/done` для завершения",
        parse_mode="Markdown"
    )
    await state.set_state(TradeStates.selecting_request_items)
    await callback.answer()


@router.message(TradeStates.selecting_request_items, Command("coins"))
async def trade_request_coins(message: Message, state: FSMContext):
    """Request coins in trade."""
    try:
        amount = int(message.text.split()[1])
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0!")
            return
        
        await state.update_data(request_coins=amount)
        await message.answer(f"✅ Запрошено: {amount} 🪙")
    except (IndexError, ValueError):
        await message.answer("❌ Используй: /coins <сумма>")


@router.message(TradeStates.selecting_request_items, Command("done"))
async def trade_done(message: Message, state: FSMContext):
    """Finalize and send trade offer."""
    data = await state.get_data()
    
    offer_items = data.get("offer_items", [])
    offer_coins = data.get("offer_coins", 0)
    request_items = data.get("request_items", [])
    request_coins = data.get("request_coins", 0)
    target_user_id = data["target_user_id"]
    
    # Create trade
    result = await trade_service.create_trade(
        from_user_id=message.from_user.id,
        to_user_id=target_user_id,
        chat_id=message.chat.id,
        offer_items=offer_items,
        offer_coins=offer_coins,
        request_items=request_items,
        request_coins=request_coins
    )
    
    if result.success:
        # Notify target user
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"trade_accept:{result.trade_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"trade_reject:{result.trade_id}")
            ]
        ])
        
        await message.answer(
            f"🔄 Предложение обмена отправлено @{data['target_username']}!\n"
            f"ID обмена: #{result.trade_id}",
            reply_markup=keyboard
        )
    else:
        await message.answer(result.message)
    
    await state.clear()


@router.callback_query(F.data.startswith("trade_accept:"))
async def trade_accept_callback(callback: CallbackQuery):
    """Accept trade offer."""
    trade_id = int(callback.data.split(":")[1])
    result = await trade_service.accept_trade(trade_id, callback.from_user.id)
    await callback.message.edit_text(result.message)
    await callback.answer()


@router.callback_query(F.data.startswith("trade_reject:"))
async def trade_reject_callback(callback: CallbackQuery):
    """Reject trade offer."""
    trade_id = int(callback.data.split(":")[1])
    result = await trade_service.reject_trade(trade_id, callback.from_user.id)
    await callback.message.edit_text(result.message)
    await callback.answer()


@router.message(Command("trades"))
async def cmd_trades(message: Message):
    """List pending trades."""
    trades = await trade_service.get_pending_trades(message.from_user.id, message.chat.id)
    
    if not trades:
        await message.answer("📭 У тебя нет активных обменов")
        return
    
    text = "🔄 Твои активные обмены:\n\n"
    for trade in trades:
        offer_items = json.loads(trade.offer_items) if trade.offer_items else []
        request_items = json.loads(trade.request_items) if trade.request_items else []
        
        text += f"#{trade.id} "
        if trade.from_user_id == message.from_user.id:
            text += "(ты предлагаешь)\n"
        else:
            text += "(тебе предлагают)\n"
        
        text += f"Предложение: "
        if offer_items:
            text += ", ".join([f"{ITEM_CATALOG[i['item_type']].emoji} x{i['quantity']}" for i in offer_items])
        if trade.offer_coins > 0:
            text += f" + {trade.offer_coins} 🪙"
        text += "\n"
        
        text += f"Запрос: "
        if request_items:
            text += ", ".join([f"{ITEM_CATALOG[i['item_type']].emoji} x{i['quantity']}" for i in request_items])
        if trade.request_coins > 0:
            text += f" + {trade.request_coins} 🪙"
        text += "\n\n"
    
    await message.answer(text)


# ============================================================================
# MARKET - Direct Sales
# ============================================================================


@router.message(Command("sell"))
async def cmd_sell(message: Message, state: FSMContext):
    """List item for sale on marketplace."""
    inventory = await inventory_service.get_inventory(message.from_user.id, message.chat.id)
    if not inventory:
        await message.answer("❌ У тебя нет предметов для продажи!")
        return
    
    keyboard = []
    for item in inventory[:15]:
        item_info = ITEM_CATALOG.get(item.item_type)
        if item_info:
            keyboard.append([InlineKeyboardButton(
                text=f"{item_info.emoji} {item_info.name} x{item.quantity}",
                callback_data=f"sell_item:{item.item_type}"
            )])
    
    await message.answer(
        "🏪 Выбери предмет для продажи:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await state.set_state(MarketStates.selecting_item)


@router.callback_query(F.data.startswith("sell_item:"), MarketStates.selecting_item)
async def sell_item_callback(callback: CallbackQuery, state: FSMContext):
    """Select item to sell."""
    item_type = callback.data.split(":")[1]
    await state.update_data(item_type=item_type, quantity=1)
    
    item_info = ITEM_CATALOG[item_type]
    await callback.message.answer(
        f"💰 Установи цену для {item_info.emoji} {item_info.name}:\n"
        "(введи число)"
    )
    await state.set_state(MarketStates.entering_price)
    await callback.answer()


@router.message(MarketStates.entering_price)
async def sell_enter_price(message: Message, state: FSMContext):
    """Enter sale price."""
    try:
        price = int(message.text)
        if price <= 0:
            await message.answer("❌ Цена должна быть больше 0!")
            return
        
        data = await state.get_data()
        result = await market_service.create_listing(
            seller_user_id=message.from_user.id,
            chat_id=message.chat.id,
            item_type=data["item_type"],
            quantity=data["quantity"],
            price=price
        )
        
        await message.answer(result.message)
        await state.clear()
    except ValueError:
        await message.answer("❌ Введи корректное число!")


@router.message(Command("market"))
async def cmd_market(message: Message):
    """Show marketplace listings."""
    listings = await market_service.get_active_listings(message.chat.id, limit=10)
    
    if not listings:
        await message.answer("🏪 Маркет пуст. Используй /sell чтобы выставить предмет!")
        return
    
    text = "🏪 Маркет:\n\n"
    keyboard = []
    
    for listing in listings:
        item_data = json.loads(listing.item_data)
        item_info = ITEM_CATALOG[item_data["item_type"]]
        
        text += f"#{listing.id} {item_info.emoji} {item_info.name} x{item_data['quantity']} — {listing.price} 🪙\n"
        keyboard.append([InlineKeyboardButton(
            text=f"Купить #{listing.id}",
            callback_data=f"buy:{listing.id}"
        )])
    
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))


@router.callback_query(F.data.startswith("buy:"))
async def buy_callback(callback: CallbackQuery):
    """Purchase marketplace listing."""
    listing_id = int(callback.data.split(":")[1])
    result = await market_service.buy_listing(listing_id, callback.from_user.id)
    await callback.answer(result.message, show_alert=True)
    
    if result.success:
        await callback.message.edit_text(callback.message.text + f"\n\n✅ Продано!")


@router.message(Command("mylistings"))
async def cmd_mylistings(message: Message):
    """Show user's active listings."""
    listings = await market_service.get_user_listings(message.from_user.id, message.chat.id)
    
    if not listings:
        await message.answer("📭 У тебя нет активных объявлений")
        return
    
    text = "🏪 Твои объявления:\n\n"
    keyboard = []
    
    for listing in listings:
        item_data = json.loads(listing.item_data)
        item_info = ITEM_CATALOG[item_data["item_type"]]
        
        text += f"#{listing.id} {item_info.emoji} {item_info.name} x{item_data['quantity']} — {listing.price} 🪙\n"
        keyboard.append([InlineKeyboardButton(
            text=f"Отменить #{listing.id}",
            callback_data=f"cancel_listing:{listing.id}"
        )])
    
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))


@router.callback_query(F.data.startswith("cancel_listing:"))
async def cancel_listing_callback(callback: CallbackQuery):
    """Cancel marketplace listing."""
    listing_id = int(callback.data.split(":")[1])
    result = await market_service.cancel_listing(listing_id, callback.from_user.id)
    await callback.answer(result.message, show_alert=True)
    
    if result.success:
        await callback.message.edit_text(callback.message.text + f"\n\n🚫 Отменено!")


# ============================================================================
# AUCTIONS - Bidding System
# ============================================================================


@router.message(Command("auction"))
async def cmd_auction(message: Message, state: FSMContext):
    """Create auction."""
    inventory = await inventory_service.get_inventory(message.from_user.id, message.chat.id)
    if not inventory:
        await message.answer("❌ У тебя нет предметов для аукциона!")
        return
    
    keyboard = []
    for item in inventory[:15]:
        item_info = ITEM_CATALOG.get(item.item_type)
        if item_info:
            keyboard.append([InlineKeyboardButton(
                text=f"{item_info.emoji} {item_info.name} x{item.quantity}",
                callback_data=f"auction_item:{item.item_type}"
            )])
    
    await message.answer(
        "🎯 Выбери предмет для аукциона:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await state.set_state(AuctionStates.selecting_item)


@router.callback_query(F.data.startswith("auction_item:"), AuctionStates.selecting_item)
async def auction_item_callback(callback: CallbackQuery, state: FSMContext):
    """Select item for auction."""
    item_type = callback.data.split(":")[1]
    await state.update_data(item_type=item_type, quantity=1)
    
    item_info = ITEM_CATALOG[item_type]
    await callback.message.answer(
        f"💰 Установи стартовую цену для {item_info.emoji} {item_info.name}:\n"
        "(введи число)"
    )
    await state.set_state(AuctionStates.entering_start_price)
    await callback.answer()


@router.message(AuctionStates.entering_start_price)
async def auction_enter_start_price(message: Message, state: FSMContext):
    """Enter auction start price."""
    try:
        start_price = int(message.text)
        if start_price <= 0:
            await message.answer("❌ Цена должна быть больше 0!")
            return
        
        await state.update_data(start_price=start_price)
        await message.answer("⏱ Длительность аукциона в часах (1-72):")
        await state.set_state(AuctionStates.entering_duration)
    except ValueError:
        await message.answer("❌ Введи корректное число!")


@router.message(AuctionStates.entering_duration)
async def auction_enter_duration(message: Message, state: FSMContext):
    """Enter auction duration."""
    try:
        duration = int(message.text)
        if duration < 1 or duration > 72:
            await message.answer("❌ Длительность должна быть от 1 до 72 часов!")
            return
        
        data = await state.get_data()
        result = await auction_service.create_auction(
            seller_user_id=message.from_user.id,
            chat_id=message.chat.id,
            item_type=data["item_type"],
            quantity=data["quantity"],
            start_price=data["start_price"],
            duration_hours=duration
        )
        
        await message.answer(result.message)
        await state.clear()
    except ValueError:
        await message.answer("❌ Введи корректное число!")


@router.message(Command("auctions"))
async def cmd_auctions(message: Message):
    """Show active auctions."""
    auctions = await auction_service.get_active_auctions(message.chat.id, limit=10)
    
    if not auctions:
        await message.answer("🎯 Нет активных аукционов. Используй /auction чтобы создать!")
        return
    
    text = "🎯 Активные аукционы:\n\n"
    keyboard = []
    
    for auction in auctions:
        item_data = json.loads(auction.item_data)
        item_info = ITEM_CATALOG[item_data["item_type"]]
        
        time_left = auction.ends_at - datetime.now(auction.ends_at.tzinfo)
        hours_left = int(time_left.total_seconds() // 3600)
        
        text += f"#{auction.id} {item_info.emoji} {item_info.name} x{item_data['quantity']}\n"
        text += f"Текущая ставка: {auction.current_price} 🪙\n"
        text += f"Осталось: {hours_left}ч\n\n"
        
        keyboard.append([InlineKeyboardButton(
            text=f"Ставка на #{auction.id}",
            callback_data=f"bid_prompt:{auction.id}"
        )])
    
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))


@router.callback_query(F.data.startswith("bid_prompt:"))
async def bid_prompt_callback(callback: CallbackQuery, state: FSMContext):
    """Prompt for bid amount."""
    auction_id = int(callback.data.split(":")[1])
    await state.update_data(auction_id=auction_id)
    await callback.message.answer("💰 Введи сумму ставки:")
    await callback.answer()


@router.message(F.text.isdigit())
async def bid_enter_amount(message: Message, state: FSMContext):
    """Enter bid amount (catches numeric input when auction_id is set)."""
    data = await state.get_data()
    auction_id = data.get("auction_id")
    
    if not auction_id:
        return  # Not in bidding flow
    
    try:
        amount = int(message.text)
        result = await auction_service.place_bid(auction_id, message.from_user.id, amount)
        await message.answer(result.message)
        await state.clear()
    except ValueError:
        await message.answer("❌ Введи корректное число!")


@router.message(Command("myauctions"))
async def cmd_myauctions(message: Message):
    """Show user's active auctions."""
    auctions = await auction_service.get_user_auctions(message.from_user.id, message.chat.id)
    
    if not auctions:
        await message.answer("📭 У тебя нет активных аукционов")
        return
    
    text = "🎯 Твои аукционы:\n\n"
    keyboard = []
    
    for auction in auctions:
        item_data = json.loads(auction.item_data)
        item_info = ITEM_CATALOG[item_data["item_type"]]
        
        time_left = auction.ends_at - datetime.now(auction.ends_at.tzinfo)
        hours_left = int(time_left.total_seconds() // 3600)
        
        text += f"#{auction.id} {item_info.emoji} {item_info.name} x{item_data['quantity']}\n"
        text += f"Текущая ставка: {auction.current_price} 🪙\n"
        text += f"Осталось: {hours_left}ч\n\n"
        
        # Can only cancel if no bids
        bids = await auction_service.get_auction_bids(auction.id)
        if not bids:
            keyboard.append([InlineKeyboardButton(
                text=f"Отменить #{auction.id}",
                callback_data=f"cancel_auction:{auction.id}"
            )])
    
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None)


@router.callback_query(F.data.startswith("cancel_auction:"))
async def cancel_auction_callback(callback: CallbackQuery):
    """Cancel auction."""
    auction_id = int(callback.data.split(":")[1])
    result = await auction_service.cancel_auction(auction_id, callback.from_user.id)
    await callback.answer(result.message, show_alert=True)
    
    if result.success:
        await callback.message.edit_text(callback.message.text + f"\n\n🚫 Отменено!")
