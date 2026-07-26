"""Loyalty build handlers for the EFT Helper bot."""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import Database
from database.models import WeaponCategory
from localization import get_text
from keyboards import get_builds_list_keyboard
from utils.constants import TRADER_EMOJIS

logger = logging.getLogger(__name__)


class LoyaltyBuildStates(StatesGroup):
    """States for loyalty build filtering."""
    waiting_for_budget = State()
    waiting_for_flea_choice = State()


router = Router()


@router.message(F.text.in_([get_text("loyalty_build_menu", "ru"), get_text("loyalty_build_menu", "en")]))
async def start_loyalty_build_from_menu(message: Message, user_service):
    """Start loyalty build from main menu - ask for weapon or any."""
    user = await user_service.get_or_create_user(message.from_user.id)
    
    text = "🤝 " + (
        "Выберите тип оружия или пропустите:"
        if user.language == "ru" else
        "Select weapon type or skip:"
    )
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    buttons = [
        [InlineKeyboardButton(
            text="🔫 " + ("Штурмовые винтовки" if user.language == "ru" else "Assault Rifles"),
            callback_data="loyalty_menu_weapon:assault_rifles"
        )],
        [InlineKeyboardButton(
            text="🎯 " + ("Марксманские винтовки" if user.language == "ru" else "DMR"),
            callback_data="loyalty_menu_weapon:dmr"
        )],
        [InlineKeyboardButton(
            text="🔫 " + ("Пистолеты-пулемёты" if user.language == "ru" else "SMG"),
            callback_data="loyalty_menu_weapon:smg"
        )],
        [InlineKeyboardButton(
            text="🔫 " + ("Снайперские винтовки" if user.language == "ru" else "Sniper Rifles"),
            callback_data="loyalty_menu_weapon:sniper_rifles"
        )],
        [InlineKeyboardButton(
            text="🔫 " + ("Пистолеты" if user.language == "ru" else "Pistols"),
            callback_data="loyalty_menu_weapon:pistols"
        )],
        [InlineKeyboardButton(
            text="🔫 " + ("Дробовики" if user.language == "ru" else "Shotguns"),
            callback_data="loyalty_menu_weapon:shotguns"
        )],
        [InlineKeyboardButton(
            text="🔫 " + ("Пулемёты" if user.language == "ru" else "LMG"),
            callback_data="loyalty_menu_weapon:lmg"
        )],
        [InlineKeyboardButton(
            text="⏭️ " + ("Любое оружие" if user.language == "ru" else "Any Weapon"),
            callback_data="loyalty_menu_weapon:any"
        )]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("loyalty_menu_weapon:"))
async def loyalty_weapon_selected_start_traders(callback: CallbackQuery, user_service):
    """Weapon type selected, start trader loyalty selection."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    
    user = await user_service.get_or_create_user(callback.from_user.id)
    weapon_category = callback.data.split(":")[1]
    
    trader_name = "Прапор" if user.language == "ru" else "Prapor"
    text = "🤝 " + (
        f"Выберите уровень лояльности для {trader_name}:"
        if user.language == "ru" else
        f"Select loyalty level for {trader_name}:"
    )
    
    buttons = []
    for level in [1, 2, 3, 4]:
        buttons.append([
            InlineKeyboardButton(
                text=f"LL{level}",
                callback_data=f"loyalty_menu:prapor:{weapon_category}:{level}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# Continue with other traders similar to search.py but with weapon_category in callback data
@router.callback_query(F.data.startswith("loyalty_menu:prapor:"))
async def loyalty_menu_select_therapist(callback: CallbackQuery, user_service):
    """Select Therapist loyalty level."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_category = parts[2]
    prapor_ll = int(parts[3])
    
    trader_name = "Терапевт" if user.language == "ru" else "Therapist"
    text = "🤝 " + (
        f"Выберите уровень лояльности для {trader_name}:"
        if user.language == "ru" else
        f"Select loyalty level for {trader_name}:"
    )
    
    buttons = []
    for level in [1, 2, 3, 4]:
        buttons.append([
            InlineKeyboardButton(
                text=f"LL{level}",
                callback_data=f"loyalty_menu:therapist:{weapon_category}:{prapor_ll}:{level}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# Similar handlers for remaining traders with weapon_category in callback data
@router.callback_query(F.data.startswith("loyalty_menu:therapist:"))
async def loyalty_menu_select_fence(callback: CallbackQuery, user_service):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_category, prapor_ll, therapist_ll = parts[2], int(parts[3]), int(parts[4])
    
    trader_name = "Скупщик" if user.language == "ru" else "Fence"
    text = "🤝 " + (f"Выберите уровень лояльности для {trader_name}:\n(Доступно только LL1 или LL4)" if user.language == "ru" else f"Select loyalty level for {trader_name}:\n(Only LL1 or LL4 available)")
    
    buttons = [
        [InlineKeyboardButton(text="LL1", callback_data=f"loyalty_menu:fence:{weapon_category}:{prapor_ll}:{therapist_ll}:1")],
        [InlineKeyboardButton(text="LL4", callback_data=f"loyalty_menu:fence:{weapon_category}:{prapor_ll}:{therapist_ll}:4")]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("loyalty_menu:fence:"))
async def loyalty_menu_select_skier(callback: CallbackQuery, user_service):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_category, prapor_ll, therapist_ll, fence_ll = parts[2], int(parts[3]), int(parts[4]), int(parts[5])
    
    trader_name = "Лыжник" if user.language == "ru" else "Skier"
    text = "🤝 " + (f"Выберите уровень лояльности для {trader_name}:" if user.language == "ru" else f"Select loyalty level for {trader_name}:")
    
    buttons = [[InlineKeyboardButton(text=f"LL{level}", callback_data=f"loyalty_menu:skier:{weapon_category}:{prapor_ll}:{therapist_ll}:{fence_ll}:{level}")] for level in [1,2,3,4]]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("loyalty_menu:skier:"))
async def loyalty_menu_select_mechanic(callback: CallbackQuery, user_service):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_category, prapor_ll, therapist_ll, fence_ll, skier_ll = parts[2], int(parts[3]), int(parts[4]), int(parts[5]), int(parts[6])
    
    trader_name = "Механик" if user.language == "ru" else "Mechanic"
    text = "🤝 " + (f"Выберите уровень лояльности для {trader_name}:" if user.language == "ru" else f"Select loyalty level for {trader_name}:")
    
    buttons = [[InlineKeyboardButton(text=f"LL{level}", callback_data=f"loyalty_menu:mechanic:{weapon_category}:{prapor_ll}:{therapist_ll}:{fence_ll}:{skier_ll}:{level}")] for level in [1,2,3,4]]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("loyalty_menu:mechanic:"))
async def loyalty_menu_select_ragman(callback: CallbackQuery, user_service):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_category, prapor_ll, therapist_ll, fence_ll, skier_ll, mechanic_ll = parts[2], int(parts[3]), int(parts[4]), int(parts[5]), int(parts[6]), int(parts[7])
    
    trader_name = "Барахольщик" if user.language == "ru" else "Ragman"
    text = "🤝 " + (f"Выберите уровень лояльности для {trader_name}:" if user.language == "ru" else f"Select loyalty level for {trader_name}:")
    
    buttons = [[InlineKeyboardButton(text=f"LL{level}", callback_data=f"loyalty_menu:ragman:{weapon_category}:{prapor_ll}:{therapist_ll}:{fence_ll}:{skier_ll}:{mechanic_ll}:{level}")] for level in [1,2,3,4]]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("loyalty_menu:ragman:"))
async def loyalty_menu_select_jaeger(callback: CallbackQuery, user_service):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_category, prapor_ll, therapist_ll, fence_ll, skier_ll, mechanic_ll, ragman_ll = parts[2], int(parts[3]), int(parts[4]), int(parts[5]), int(parts[6]), int(parts[7]), int(parts[8])
    
    trader_name = "Егерь" if user.language == "ru" else "Jaeger"
    text = "🤝 " + (f"Выберите уровень лояльности для {trader_name}:\n(LL0 = нет доступа)" if user.language == "ru" else f"Select loyalty level for {trader_name}:\n(LL0 = not available)")
    
    buttons = [[InlineKeyboardButton(text=("Нет доступа" if user.language == "ru" else "Not available") if level == 0 else f"LL{level}", callback_data=f"loyalty_menu:jaeger:{weapon_category}:{prapor_ll}:{therapist_ll}:{fence_ll}:{skier_ll}:{mechanic_ll}:{ragman_ll}:{level}")] for level in [0,1,2,3,4]]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("loyalty_menu:jaeger:"))
async def loyalty_menu_select_ref(callback: CallbackQuery, user_service):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_category, prapor_ll, therapist_ll, fence_ll, skier_ll, mechanic_ll, ragman_ll, jaeger_ll = parts[2], int(parts[3]), int(parts[4]), int(parts[5]), int(parts[6]), int(parts[7]), int(parts[8]), int(parts[9])
    
    trader_name = "Реф" if user.language == "ru" else "Ref"
    text = "🤝 " + (f"Выберите уровень лояльности для {trader_name}:\n(LL0 = нет доступа)" if user.language == "ru" else f"Select loyalty level for {trader_name}:\n(LL0 = not available)")
    
    buttons = [[InlineKeyboardButton(text=("Нет доступа" if user.language == "ru" else "Not available") if level == 0 else f"LL{level}", callback_data=f"loyalty_menu:ref:{weapon_category}:{prapor_ll}:{therapist_ll}:{fence_ll}:{skier_ll}:{mechanic_ll}:{ragman_ll}:{jaeger_ll}:{level}")] for level in [0,1,2,3,4]]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("loyalty_menu:ref:"))
async def loyalty_menu_select_budget(callback: CallbackQuery, user_service):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_category, prapor_ll, therapist_ll, fence_ll, skier_ll, mechanic_ll, ragman_ll, jaeger_ll, ref_ll = parts[2], int(parts[3]), int(parts[4]), int(parts[5]), int(parts[6]), int(parts[7]), int(parts[8]), int(parts[9]), int(parts[10])
    
    text = "💰 " + ("Выберите бюджет для сборки:" if user.language == "ru" else "Select budget for build:")
    
    budgets = [(50000, "50K"), (100000, "100K"), (200000, "200K"), (500000, "500K"), (1000000, "1M")]
    buttons = [[InlineKeyboardButton(text=label, callback_data=f"loyalty_menu_budget:{weapon_category}:{prapor_ll}:{therapist_ll}:{fence_ll}:{skier_ll}:{mechanic_ll}:{ragman_ll}:{jaeger_ll}:{ref_ll}:{budget_value}")] for budget_value, label in budgets]
    buttons.append([InlineKeyboardButton(text="⏭️ " + ("Пропустить" if user.language == "ru" else "Skip"), callback_data=f"loyalty_menu_budget:{weapon_category}:{prapor_ll}:{therapist_ll}:{fence_ll}:{skier_ll}:{mechanic_ll}:{ragman_ll}:{jaeger_ll}:{ref_ll}:0")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("loyalty_menu_budget:"))
async def loyalty_menu_select_flea(callback: CallbackQuery, user_service):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_category, prapor_ll, therapist_ll, fence_ll, skier_ll, mechanic_ll, ragman_ll, jaeger_ll, ref_ll, budget = parts[1], int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5]), int(parts[6]), int(parts[7]), int(parts[8]), int(parts[9]), int(parts[10])
    
    text = "🏪 " + ("Использовать Барахолку?" if user.language == "ru" else "Use Flea Market?")
    
    buttons = [
        [InlineKeyboardButton(text="✅ " + ("Да" if user.language == "ru" else "Yes"), callback_data=f"gen_loyalty_menu_final:{weapon_category}:{prapor_ll}:{therapist_ll}:{fence_ll}:{skier_ll}:{mechanic_ll}:{ragman_ll}:{jaeger_ll}:{ref_ll}:{budget}:1")],
        [InlineKeyboardButton(text="❌ " + ("Нет" if user.language == "ru" else "No"), callback_data=f"gen_loyalty_menu_final:{weapon_category}:{prapor_ll}:{therapist_ll}:{fence_ll}:{skier_ll}:{mechanic_ll}:{ragman_ll}:{jaeger_ll}:{ref_ll}:{budget}:0")]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("gen_loyalty_menu_final:"))
async def generate_loyalty_build_from_menu(callback: CallbackQuery, user_service, weapon_service, ai_gen_service=None):
    """Generate loyalty build from main menu with weapon category selection."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_category, prapor_ll, therapist_ll, fence_ll, skier_ll, mechanic_ll, ragman_ll, jaeger_ll, ref_ll, budget, use_flea = parts[1], int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5]), int(parts[6]), int(parts[7]), int(parts[8]), int(parts[9]), int(parts[10]), bool(int(parts[11]))
    
    if not ai_gen_service:
        await callback.answer(get_text("ai_not_available", user.language), show_alert=True)
        return
    
    # Select random weapon if any, else use category
    if weapon_category == "any":
        weapons = await weapon_service.get_all_weapons()
        import random
        weapon = random.choice(weapons) if weapons else None
    else:
        weapons = await weapon_service.get_weapons_by_category(weapon_category)
        import random
        weapon = random.choice(weapons) if weapons else None
    
    if not weapon:
        await callback.message.edit_text("❌ Оружие не найдено" if user.language == "ru" else "❌ Weapon not found")
        await callback.answer()
        return
    
    weapon_name = weapon.name_ru if user.language == "ru" else weapon.name_en
    
    trader_levels = {"prapor": prapor_ll, "therapist": therapist_ll, "fence": fence_ll, "skier": skier_ll, "mechanic": mechanic_ll, "ragman": ragman_ll, "jaeger": jaeger_ll, "ref": ref_ll}
    budget_text = f"{budget:,}₽" if budget > 0 else ("без лимита" if user.language == "ru" else "unlimited")
    flea_text = "с барахолкой" if use_flea else "без барахолки" if user.language == "ru" else "with flea" if use_flea else "no flea"
    
    loading_text = "⚙️ " + (f"Генерирую сборку для {weapon_name} ({flea_text}, бюджет: {budget_text})..." if user.language == "ru" else f"Generating build for {weapon_name} ({flea_text}, budget: {budget_text})...")
    await callback.message.edit_text(loading_text)
    
    try:
        context = {"weapon_id": weapon.tarkov_id, "weapon_name": weapon_name, "trader_levels": trader_levels, "budget": budget if budget > 0 else None, "use_flea_market": use_flea, "target_tier": "B"}
        
        build_data = await ai_gen_service.generate_build_with_ai(intent="custom_request", context=context, user_id=user.id, language=user.language)
        
        if not build_data or not build_data.get("text"):
            await callback.message.edit_text("❌ Не удалось сгенерировать сборку" if user.language == "ru" else "❌ Failed to generate build")
            await callback.answer()
            return
        
        from utils.formatters import format_ai_build_with_tier
        tier = build_data.get("tier", "B")
        formatted_build = format_ai_build_with_tier(build_data["text"], tier, user.language)
        
        await callback.message.edit_text(formatted_build, parse_mode="Markdown")
        await callback.answer()
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating loyalty build from menu: {e}", exc_info=True)
        await callback.message.edit_text(get_text("ai_error", user.language))
        await callback.answer()


def get_loyalty_setup_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    """Get keyboard for loyalty level setup."""
    traders = [
        "prapor", "therapist", "fence", "skier",
        "peacekeeper", "mechanic", "ragman", "jaeger", "ref"
    ]
    
    buttons = []
    for trader_key in traders:
        emoji = TRADER_EMOJIS.get(trader_key, "💼")
        trader_name = get_text(trader_key, language=language)
        buttons.append([InlineKeyboardButton(
            text=f"{emoji} {trader_name}",
            callback_data=f"set_loyalty:{trader_key}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text=get_text("select_weapon_category", language=language),
        callback_data="show_loyalty_builds"
    )])
    
    buttons.append([InlineKeyboardButton(
        text=get_text("reset_loyalty_levels", language=language),
        callback_data="reset_loyalty"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data.startswith("set_loyalty:"))
async def select_trader_level(callback: CallbackQuery, db: Database):
    """Handle trader selection for level setting."""
    user = await db.get_or_create_user(callback.from_user.id)
    trader = callback.data.split(":")[1]
    
    trader_name = get_text(trader, language=user.language)
    text = get_text("select_loyalty_level", language=user.language, trader=trader_name)
    
    # Fence (Скупщик) has only levels 1 and 4
    # Jaeger and Ref can have level 0 (not available)
    if trader == "fence":
        levels = [1, 4]
    elif trader in ["jaeger", "ref"]:
        levels = range(0, 5)
    else:
        levels = range(1, 5)
    
    buttons = []
    for level in levels:
        buttons.append([InlineKeyboardButton(
            text=get_text("loyalty_level", language=user.language, level=level),
            callback_data=f"update_loyalty:{trader}:{level}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text=get_text("back", language=user.language),
        callback_data="back_to_loyalty_setup"
    )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("update_loyalty:"))
async def update_trader_loyalty(callback: CallbackQuery, db: Database):
    """Update trader loyalty level."""
    user = await db.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    trader = parts[1]
    level = int(parts[2])
    
    # Update trader level
    user.trader_levels[trader] = level
    await db.update_trader_levels(callback.from_user.id, user.trader_levels)
    
    trader_name = get_text(trader, language=user.language)
    await callback.answer(
        get_text("trader_level_set", language=user.language, trader=trader_name, level=level),
        show_alert=True
    )
    
    # Return to loyalty setup
    text = get_text("setup_loyalty_levels", language=user.language) + "\n\n"
    text += get_text("current_loyalty_levels", language=user.language) + "\n"
    
    for t, l in user.trader_levels.items():
        t_name = get_text(t, language=user.language)
        text += f"  • {t_name}: {l}\n"
    
    keyboard = get_loyalty_setup_keyboard(user.language)
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data == "show_loyalty_builds")
async def start_loyalty_filters(callback: CallbackQuery, db: Database):
    """Start loyalty build filtering - select category."""
    user = await db.get_or_create_user(callback.from_user.id)
    
    text = get_text("select_weapon_category", language=user.language)
    
    # Create category selection keyboard
    categories = [
        ("any", get_text("any_category", user.language)),
        (WeaponCategory.ASSAULT_RIFLE.value, get_text("category_assault_rifles", user.language)),
        (WeaponCategory.SMG.value, get_text("category_smg", user.language)),
        (WeaponCategory.DMR.value, get_text("category_dmr", user.language)),
        (WeaponCategory.SNIPER.value, get_text("category_sniper_rifles", user.language)),
        (WeaponCategory.SHOTGUN.value, get_text("category_shotguns", user.language)),
        (WeaponCategory.PISTOL.value, get_text("category_pistols", user.language)),
        (WeaponCategory.LMG.value, get_text("category_lmg", user.language)),
    ]
    
    buttons = []
    for cat_value, cat_name in categories:
        buttons.append([InlineKeyboardButton(
            text=cat_name,
            callback_data=f"loyalty_category:{cat_value}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text=get_text("back", user.language),
        callback_data="back_to_loyalty_setup"
    )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "reset_loyalty")
async def reset_loyalty_levels(callback: CallbackQuery, db: Database):
    """Reset all trader loyalty levels to 1."""
    user = await db.get_or_create_user(callback.from_user.id)
    
    default_levels = {trader: 1 for trader in user.trader_levels.keys()}
    await db.update_trader_levels(callback.from_user.id, default_levels)
    
    await callback.answer(get_text("loyalty_levels_saved", language=user.language), show_alert=True)
    
    # Refresh display
    user = await db.get_user(callback.from_user.id)
    text = get_text("setup_loyalty_levels", language=user.language) + "\n\n"
    text += get_text("current_loyalty_levels", language=user.language) + "\n"
    
    for trader, level in user.trader_levels.items():
        trader_name = get_text(trader, language=user.language)
        text += f"  • {trader_name}: {level}\n"
    
    keyboard = get_loyalty_setup_keyboard(user.language)
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("loyalty_category:"))
async def select_category_for_loyalty(callback: CallbackQuery, db: Database, state: FSMContext):
    """Handle category selection and ask for budget."""
    user = await db.get_or_create_user(callback.from_user.id)
    category = callback.data.split(":")[1]
    
    # Store category in state
    await state.update_data(loyalty_category=category)
    
    # Ask for budget
    text = get_text("enter_max_budget", language=user.language)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=get_text("skip_budget", user.language),
                callback_data="loyalty_skip_budget"
            )],
            [InlineKeyboardButton(
                text=get_text("back", user.language),
                callback_data="back_to_loyalty_setup"
            )]
        ]
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(LoyaltyBuildStates.waiting_for_budget)
    await callback.answer()


@router.message(LoyaltyBuildStates.waiting_for_budget)
async def process_budget_input(message: Message, db: Database, state: FSMContext):
    """Process budget input."""
    user = await db.get_or_create_user(message.from_user.id)
    
    budget = None
    if message.text and message.text.strip().isdigit():
        budget = int(message.text.strip())
        await message.answer(get_text("budget_set_to", language=user.language, budget=f"{budget:,}"))
    else:
        await message.answer(get_text("invalid_budget_format", language=user.language))
        return
    
    # Store budget and ask for flea market choice
    await state.update_data(loyalty_budget=budget)
    
    text = get_text("select_flea_market", language=user.language)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=get_text("traders_only", user.language),
                callback_data="loyalty_flea:no"
            )],
            [InlineKeyboardButton(
                text=get_text("with_flea_market", user.language),
                callback_data="loyalty_flea:yes"
            )],
            [InlineKeyboardButton(
                text=get_text("back", user.language),
                callback_data="back_to_loyalty_setup"
            )]
        ]
    )
    
    await message.answer(text, reply_markup=keyboard)
    await state.set_state(LoyaltyBuildStates.waiting_for_flea_choice)


@router.callback_query(F.data == "loyalty_skip_budget", LoyaltyBuildStates.waiting_for_budget)
async def skip_budget_input(callback: CallbackQuery, db: Database, state: FSMContext):
    """Skip budget filter."""
    user = await db.get_or_create_user(callback.from_user.id)
    
    await callback.answer(get_text("no_budget_limit", language=user.language))
    
    # Store unlimited budget and ask for flea market choice
    await state.update_data(loyalty_budget=None)
    
    text = get_text("select_flea_market", language=user.language)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=get_text("traders_only", user.language),
                callback_data="loyalty_flea:no"
            )],
            [InlineKeyboardButton(
                text=get_text("with_flea_market", user.language),
                callback_data="loyalty_flea:yes"
            )],
            [InlineKeyboardButton(
                text=get_text("back", user.language),
                callback_data="back_to_loyalty_setup"
            )]
        ]
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(LoyaltyBuildStates.waiting_for_flea_choice)


@router.callback_query(F.data.startswith("loyalty_flea:"), LoyaltyBuildStates.waiting_for_flea_choice)
async def process_flea_choice(callback: CallbackQuery, db: Database, state: FSMContext):
    """Process flea market choice and generate build."""
    user = await db.get_or_create_user(callback.from_user.id)
    
    # Parse flea choice
    use_flea = callback.data.split(":")[1] == "yes"
    
    # Get stored data
    data = await state.get_data()
    category = data.get("loyalty_category", "any")
    budget = data.get("loyalty_budget")
    
    # Clear state
    await state.clear()
    
    # Delete old message and generate build
    await callback.message.delete()
    await show_filtered_loyalty_builds(callback.message, db, user, category, budget, use_flea)
    await callback.answer()


async def show_filtered_loyalty_builds(message, db: Database, user, category: str, max_budget: int = None, use_flea: bool = False):
    """Generate build via API with loyalty, category, and budget constraints."""
    from api_clients import TarkovAPIClient
    from services import BuildGenerator, BuildGeneratorConfig, CompatibilityChecker, TierEvaluator
    
    logger.info(f"Generating loyalty build: category={category}, budget={max_budget}")
    logger.info(f"User trader levels: {user.trader_levels}")
    
    # Show loading message
    loading_msg = await message.answer(get_text("generating_build", user.language))
    
    # Initialize services
    api_client = TarkovAPIClient()
    compatibility = CompatibilityChecker(api_client)
    tier_eval = TierEvaluator()
    generator = BuildGenerator(api_client, compatibility, tier_eval)
    
    # Map category to weapon type string for API
    # Use Russian names if user language is Russian, English otherwise
    weapon_type = None
    if category != "any":
        if user.language == "ru":
            category_map = {
                "assault_rifle": "Штурмовая винтовка",
                "smg": "Пистолет-пулемет",
                "dmr": "Марксманская винтовка",
                "sniper": "Снайперская винтовка",
                "shotgun": "Дробовик",
                "pistol": "Пистолет",
                "lmg": "Пулемет"
            }
        else:
            category_map = {
                "assault_rifle": "Assault rifle",
                "smg": "Submachine gun",
                "dmr": "Marksman rifle",
                "sniper": "Sniper rifle",
                "shotgun": "Shotgun",
                "pistol": "Pistol",
                "lmg": "Machine gun"
            }
        weapon_type = category_map.get(category)
    
    # Create configuration
    config = BuildGeneratorConfig(
        budget=max_budget,
        trader_levels=user.trader_levels,
        use_flea_only=use_flea,
        weapon_type=weapon_type,
        prioritize_ergonomics=False,
        prioritize_recoil=True
    )
    
    # Generate build
    try:
        build = await generator.generate_random_build(config, language=user.language)
        
        if not build:
            await loading_msg.edit_text(get_text("no_builds_found", user.language))
            return
        
        # Format and display build
        from handlers.dynamic_builds import format_generated_build
        text = await format_generated_build(build, max_budget, user.language, tier_eval)
        
        # Action buttons
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_text("regenerate", user.language),
                        callback_data=f"loyalty_regenerate:{category}:{max_budget}:{use_flea}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=get_text("back", user.language),
                        callback_data="back_to_loyalty_setup"
                    )
                ]
            ]
        )
        
        await loading_msg.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        logger.info(f"Successfully generated loyalty build")
        
    except Exception as e:
        logger.error(f"Error generating loyalty build: {e}")
        await loading_msg.edit_text(get_text("error", user.language))


@router.callback_query(F.data.startswith("loyalty_regenerate:"))
async def regenerate_loyalty_build(callback: CallbackQuery, db: Database):
    """Regenerate build with same parameters."""
    user = await db.get_or_create_user(callback.from_user.id)
    
    # Parse parameters from callback data
    parts = callback.data.split(":")
    category = parts[1]
    budget = int(parts[2]) if parts[2] != "None" else None
    use_flea = parts[3] == "True" if len(parts) > 3 else False
    
    # Delete old message and generate new build
    await callback.message.delete()
    await show_filtered_loyalty_builds(callback.message, db, user, category, budget, use_flea)
    await callback.answer()


@router.callback_query(F.data == "back_to_loyalty_setup")
async def back_to_loyalty_setup(callback: CallbackQuery, db: Database, state: FSMContext):
    """Go back to loyalty setup screen."""
    # Clear any active state
    await state.clear()
    
    user = await db.get_or_create_user(callback.from_user.id)
    
    text = get_text("setup_loyalty_levels", language=user.language) + "\n\n"
    text += get_text("current_loyalty_levels", language=user.language) + "\n"
    
    for trader, level in user.trader_levels.items():
        trader_name = get_text(trader, language=user.language)
        text += f"  • {trader_name}: {level}\n"
    
    keyboard = get_loyalty_setup_keyboard(user.language)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()
