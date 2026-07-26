"""Shop Handler - Central shop for buying items with inline buttons.

Version 7.5
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select

from app.database.session import get_session
from app.database.models import UserInventory
from app.services.economy import economy_service, SHOP_ITEMS, ItemType, Rarity
from app.services import wallet_service

logger = logging.getLogger(__name__)
router = Router()

SHOP_PREFIX = "shop:"

# Shop categories
CATEGORIES = {
    "lootboxes": ("📦 Лутбоксы", [
        ItemType.LOOTBOX_COMMON, 
        ItemType.LOOTBOX_RARE, 
        ItemType.LOOTBOX_EPIC, 
        ItemType.LOOTBOX_LEGENDARY,
        "lootbox_mega",
        "lootbox_mystery"
    ]),
    "fishing": ("🎣 Рыбалка", [
        ItemType.FISHING_ROD_BASIC, 
        ItemType.FISHING_ROD_PRO, 
        ItemType.FISHING_ROD_GOLDEN,
        "diamond_rod",
        "cosmic_rod"
    ]),
    "boosters": ("⚡ Бустеры", [
        ItemType.LUCKY_CHARM, 
        ItemType.DOUBLE_XP, 
        ItemType.SHIELD, 
        ItemType.ENERGY_DRINK, 
        ItemType.VIP_STATUS,
        ItemType.DAMAGE_BOOST,
        ItemType.HEAL_POTION,
        ItemType.CRITICAL_BOOST,
        ItemType.COIN_MAGNET,
        ItemType.FISHING_BAIT,
        ItemType.GROW_ACCELERATOR
    ]),
    "roosters": ("🐔 Петухи", [
        ItemType.ROOSTER_COMMON, 
        ItemType.ROOSTER_RARE, 
        ItemType.ROOSTER_EPIC
    ]),
    "pp_creams": ("🍆 Мази для роста", [
        ItemType.PP_CREAM_SMALL, 
        ItemType.PP_CREAM_MEDIUM, 
        ItemType.PP_CREAM_LARGE, 
        ItemType.PP_CREAM_TITAN
    ]),
    "pp_protection": ("🔒 Защита PP", [ItemType.PP_CAGE]),
}


async def get_user_balance(user_id: int, chat_id: int) -> int:
    """Get user balance from unified Wallet."""
    return await wallet_service.get_balance(user_id)


async def update_user_balance(user_id: int, chat_id: int, change: int) -> int:
    """Update user balance using unified Wallet."""
    if change > 0:
        result = await wallet_service.add_balance(user_id, change, "shop")
    elif change < 0:
        result = await wallet_service.deduct_balance(user_id, abs(change), "shop purchase")
    else:
        return await wallet_service.get_balance(user_id)
    return result.balance


def get_main_shop_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Create main shop keyboard with categories."""
    buttons = []
    for cat_id, (cat_name, _) in CATEGORIES.items():
        buttons.append([InlineKeyboardButton(text=cat_name, callback_data=f"{SHOP_PREFIX}{user_id}:cat:{cat_id}")])
    
    buttons.append([InlineKeyboardButton(text="💰 Мой баланс", callback_data=f"{SHOP_PREFIX}{user_id}:balance")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_category_keyboard(user_id: int, category: str) -> InlineKeyboardMarkup:
    """Create category items keyboard."""
    from app.services.inventory import ITEM_CATALOG
    
    _, items = CATEGORIES.get(category, ("", []))
    buttons = []
    
    for item_type in items:
        # Check for enum FIRST (before str check) because ItemType inherits from str
        if isinstance(item_type, ItemType):
            # It's an enum - extract the value
            item_type_str = item_type.value
            item = SHOP_ITEMS.get(item_type)
            if not item:
                item = ITEM_CATALOG.get(item_type_str)
        elif isinstance(item_type, str):
            # It's a plain string (like "diamond_rod")
            item_type_str = item_type
            item = ITEM_CATALOG.get(item_type_str)
        else:
            continue
        
        if item:
            rarity_emoji = {"common": "", "uncommon": "⭐", "rare": "⭐⭐", "epic": "💜", "legendary": "🌟"}.get(getattr(item, 'rarity', Rarity.COMMON).value if hasattr(item, 'rarity') else 'common', "")
            price = item.price if hasattr(item, 'price') else 0
            text = f"{item.emoji} {item.name} — {price}💰 {rarity_emoji}"
            callback_data = f"{SHOP_PREFIX}{user_id}:buy:{item_type_str}"
            buttons.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{SHOP_PREFIX}{user_id}:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_item_keyboard(user_id: int, item_type: str) -> InlineKeyboardMarkup:
    """Create item purchase confirmation keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Купить", callback_data=f"{SHOP_PREFIX}{user_id}:confirm:{item_type}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"{SHOP_PREFIX}{user_id}:main"),
        ],
    ])


@router.message(Command("shop"))
async def cmd_shop(message: Message):
    """Open the shop."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    balance = await get_user_balance(user_id, chat_id)
    
    text = (
        "🏪 <b>МАГАЗИН ОЛЕГА</b>\n\n"
        "Добро пожаловать в магазин!\n"
        "Здесь ты можешь купить полезные предметы за монеты.\n\n"
        f"💰 Твой баланс: <b>{balance}</b> монет\n\n"
        "Выбери категорию:"
    )
    
    await message.reply(text, reply_markup=get_main_shop_keyboard(user_id), parse_mode="HTML")


@router.callback_query(F.data.startswith(SHOP_PREFIX))
async def callback_shop(callback: CallbackQuery):
    """Handle shop callbacks."""
    parts = callback.data.split(":")
    if len(parts) < 3:
        return await callback.answer("Ошибка")
    
    _, owner_id, action = parts[:3]
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if int(owner_id) != user_id:
        return await callback.answer("Это не твой магазин!", show_alert=True)
    
    if action == "main":
        balance = await get_user_balance(user_id, chat_id)
        text = (
            "🏪 <b>МАГАЗИН ОЛЕГА</b>\n\n"
            f"💰 Твой баланс: <b>{balance}</b> монет\n\n"
            "Выбери категорию:"
        )
        await callback.message.edit_text(text, reply_markup=get_main_shop_keyboard(user_id), parse_mode="HTML")
        await callback.answer()
    
    elif action == "cat":
        category = parts[3] if len(parts) > 3 else "lootboxes"
        cat_name, _ = CATEGORIES.get(category, ("Категория", []))
        balance = await get_user_balance(user_id, chat_id)
        
        text = (
            f"🏪 <b>{cat_name}</b>\n\n"
            f"💰 Баланс: <b>{balance}</b> монет\n\n"
            "Выбери товар:"
        )
        await callback.message.edit_text(text, reply_markup=get_category_keyboard(user_id, category), parse_mode="HTML")
        await callback.answer()
    
    elif action == "buy":
        from app.services.inventory import ITEM_CATALOG
        
        item_type_str = parts[3] if len(parts) > 3 else ""
        
        logger.info(f"Shop buy: user={user_id}, item_type_str='{item_type_str}'")
        
        # Try multiple lookup strategies
        item = None
        
        # 1. Try as ItemType enum in SHOP_ITEMS
        try:
            item_type_enum = ItemType(item_type_str)
            item = SHOP_ITEMS.get(item_type_enum)
            logger.info(f"Shop buy: enum lookup result: {item is not None}")
        except (ValueError, KeyError) as e:
            logger.info(f"Shop buy: enum lookup failed: {e}")
        
        # 2. Try as string key in SHOP_ITEMS (for diamond_rod, cosmic_rod, etc)
        if not item:
            item = SHOP_ITEMS.get(item_type_str)
            logger.info(f"Shop buy: string lookup in SHOP_ITEMS result: {item is not None}")
        
        # 3. Fallback to ITEM_CATALOG
        if not item:
            item = ITEM_CATALOG.get(item_type_str)
            logger.info(f"Shop buy: ITEM_CATALOG lookup result: {item is not None}")
        
        if not item:
            logger.error(f"Shop buy: item not found for '{item_type_str}'")
            logger.error(f"Available SHOP_ITEMS keys: {list(SHOP_ITEMS.keys())[:10]}")
            return await callback.answer("Товар не найден", show_alert=True)
        
        balance = await get_user_balance(user_id, chat_id)
        
        rarity_names = {
            Rarity.COMMON: "Обычный",
            Rarity.UNCOMMON: "Необычный",
            Rarity.RARE: "Редкий",
            Rarity.EPIC: "Эпический",
            Rarity.LEGENDARY: "Легендарный",
        }
        
        rarity = getattr(item, 'rarity', Rarity.COMMON) if hasattr(item, 'rarity') else Rarity.COMMON
        
        text = (
            f"🏪 <b>ПОКУПКА</b>\n\n"
            f"{item.emoji} <b>{item.name}</b>\n"
            f"📝 {item.description}\n"
            f"⭐ Редкость: {rarity_names.get(rarity, 'Обычный')}\n"
            f"💰 Цена: <b>{item.price}</b> монет\n\n"
            f"💰 Твой баланс: {balance} монет\n\n"
        )
        
        if balance < item.price:
            text += "❌ <i>Недостаточно монет!</i>"
        else:
            text += "Подтвердить покупку?"
        
        await callback.message.edit_text(text, reply_markup=get_item_keyboard(user_id, item_type_str), parse_mode="HTML")
        await callback.answer()
    
    elif action == "confirm":
        from app.services.inventory import ITEM_CATALOG
        
        item_type_str = parts[3] if len(parts) > 3 else ""
        
        # Try multiple lookup strategies
        item = None
        
        # 1. Try as ItemType enum in SHOP_ITEMS
        try:
            item_type_enum = ItemType(item_type_str)
            item = SHOP_ITEMS.get(item_type_enum)
        except (ValueError, KeyError):
            pass
        
        # 2. Try as string key in SHOP_ITEMS (for diamond_rod, cosmic_rod, etc)
        if not item:
            item = SHOP_ITEMS.get(item_type_str)
        
        # 3. Fallback to ITEM_CATALOG
        if not item:
            item = ITEM_CATALOG.get(item_type_str)
        
        if not item:
            return await callback.answer("Товар не найден", show_alert=True)
        
        balance = await get_user_balance(user_id, chat_id)
        
        if balance < item.price:
            return await callback.answer(f"Недостаточно монет! У тебя {balance}, нужно {item.price}", show_alert=True)
        
        # Deduct balance
        new_balance = await update_user_balance(user_id, chat_id, -item.price)
        
        # Add item to inventory
        async_session = get_session()
        async with async_session() as session:
            # Check if item already exists in inventory
            res = await session.execute(
                select(UserInventory).where(
                    UserInventory.user_id == user_id,
                    UserInventory.chat_id == chat_id,
                    UserInventory.item_type == item_type_str
                )
            )
            existing = res.scalars().first()
            
            if existing:
                existing.quantity += 1
            else:
                new_item = UserInventory(
                    user_id=user_id,
                    chat_id=chat_id,
                    item_type=item_type_str,
                    item_name=item.name,
                    quantity=1,
                    equipped=False
                )
                session.add(new_item)
            
            await session.commit()
        
        text = (
            f"🏪 <b>ПОКУПКА УСПЕШНА!</b>\n\n"
            f"✅ Куплено: {item.emoji} {item.name}\n"
            f"💰 Потрачено: {item.price} монет\n\n"
            f"💰 Остаток: {new_balance} монет"
        )
        
        await callback.message.edit_text(text, reply_markup=get_main_shop_keyboard(user_id), parse_mode="HTML")
        await callback.answer(f"✅ Куплено: {item.name}!")
        
        logger.info(f"User {user_id} purchased {item.name} for {item.price}")
    
    elif action == "balance":
        balance = await get_user_balance(user_id, chat_id)
        await callback.answer(f"💰 Твой баланс: {balance} монет", show_alert=True)
