"""Search handlers for the EFT Helper bot."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import Database, BuildCategory, WeaponCategory
from localization import get_text
from keyboards import (
    get_weapon_selection_keyboard,
    get_build_type_keyboard
)


router = Router()


class SearchStates(StatesGroup):
    """States for weapon search."""
    waiting_for_weapon_name = State()


def get_category_selection_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    """Get weapon category selection keyboard."""
    categories = [
        ("category_pistols", WeaponCategory.PISTOL),
        ("category_smg", WeaponCategory.SMG),
        ("category_assault_rifles", WeaponCategory.ASSAULT_RIFLE),
        ("category_dmr", WeaponCategory.DMR),
        ("category_sniper_rifles", WeaponCategory.SNIPER),
        ("category_shotguns", WeaponCategory.SHOTGUN),
        ("category_lmg", WeaponCategory.LMG)
    ]
    
    buttons = []
    for text_key, category in categories:
        buttons.append([InlineKeyboardButton(
            text=get_text(text_key, language=language),
            callback_data=f"category:{category.value}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text=get_text("search_by_name", language=language),
        callback_data="search_by_name"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(F.text.in_([get_text("search_weapon", "ru"), get_text("search_weapon", "en")]))
async def start_search(message: Message, state: FSMContext, user_service):
    """Start weapon search - show category selection."""
    user = await user_service.get_or_create_user(message.from_user.id)
    
    text = get_text("select_category", language=user.language)
    keyboard = get_category_selection_keyboard(user.language)
    
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("category:"))
async def show_category_weapons(callback: CallbackQuery, user_service, weapon_service):
    """Show weapons in selected category."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    category = callback.data.split(":")[1]
    
    # Get all weapons from service in this category
    from database import WeaponCategory
    category_enum = WeaponCategory(category)
    category_weapons = await weapon_service.get_weapons_by_category(category_enum)
    
    if not category_weapons:
        await callback.message.edit_text(get_text("no_weapons_found", language=user.language))
        await callback.answer()
        return
    
    text = get_text("select_weapon", language=user.language)
    keyboard = get_weapon_selection_keyboard(category_weapons, user.language)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "search_by_name")
async def search_by_name_prompt(callback: CallbackQuery, state: FSMContext, user_service):
    """Prompt user to enter weapon name."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    
    await state.set_state(SearchStates.waiting_for_weapon_name)
    await callback.message.edit_text(get_text("enter_weapon_name", language=user.language))
    await callback.answer()


@router.message(SearchStates.waiting_for_weapon_name)
async def process_weapon_search(message: Message, state: FSMContext, user_service, weapon_service):
    """Process weapon search query - supports both Russian and English names."""
    user = await user_service.get_or_create_user(message.from_user.id)
    query = message.text.strip()
    
    # Search for weapons using service
    weapons = await weapon_service.search_weapons(query, user.language)
    
    if not weapons:
        await message.answer(get_text("weapon_not_found", user.language))
        return
    
    if len(weapons) == 1:
        # If only one weapon found, show build types directly
        weapon = weapons[0]
        weapon_name = weapon.name_ru if user.language == "ru" else weapon.name_en
        text = get_text("select_build_type", user.language, weapon=weapon_name)
        keyboard = get_build_type_keyboard(weapon.id, user.language)
        await message.answer(text, reply_markup=keyboard)
    else:
        # Show weapon selection
        text = get_text("select_weapon", user.language)
        keyboard = get_weapon_selection_keyboard(weapons, user.language)
        await message.answer(text, reply_markup=keyboard)
    
    await state.clear()


@router.callback_query(F.data.startswith("weapon:"))
async def select_weapon(callback: CallbackQuery, user_service, weapon_service):
    """Handle weapon selection."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    weapon_id = int(callback.data.split(":")[1])
    
    weapon = await weapon_service.get_weapon_by_id(weapon_id)
    if not weapon:
        await callback.answer(get_text("error", user.language))
        return
    
    weapon_name = weapon.name_ru if user.language == "ru" else weapon.name_en
    text = get_text("select_build_type", user.language, weapon=weapon_name)
    
    # Build keyboard with all build options
    buttons = []
    
    # AI meta-build generation (v5.3)
    buttons.append([
        InlineKeyboardButton(
            text=get_text("meta_build_button", user.language),
            callback_data=f"build:meta:{weapon.id}"
        )
    ])
    
    # Loyalty-based build (select loyalty levels + budget)
    buttons.append([
        InlineKeyboardButton(
            text="🤝 " + ("Сборка по лояльности" if user.language == "ru" else "Loyalty Build"),
            callback_data=f"build:loyalty:{weapon.id}"
        )
    ])
    
    # Random build for this weapon
    buttons.append([
        InlineKeyboardButton(
            text="🎲 " + ("Случайная сборка" if user.language == "ru" else "Random Build"),
            callback_data=f"build:random:{weapon.id}"
        )
    ])
    
    # Dynamic build (budget-based)
    buttons.append([
        InlineKeyboardButton(
            text="💰 " + ("Сборка по бюджету" if user.language == "ru" else "Budget Build"),
            callback_data=f"build:budget:{weapon.id}"
        )
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("build:meta:"))
async def generate_meta_build_ai(callback: CallbackQuery, user_service, weapon_service, ai_gen_service=None):
    """Generate AI meta build for weapon from search (v5.3)."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    weapon_id = int(callback.data.split(":")[2])
    
    if not ai_gen_service:
        await callback.answer(get_text("ai_not_available", user.language), show_alert=True)
        return
    
    # Get weapon info
    weapon = await weapon_service.get_weapon_by_id(weapon_id)
    if not weapon:
        await callback.answer(get_text("error", user.language))
        return
    
    weapon_name = weapon.name_ru if user.language == "ru" else weapon.name_en
    
    # Show loading message
    loading_text = get_text("generating_meta_build", user.language)
    await callback.message.edit_text(loading_text)
    
    try:
        # Generate meta build using AI
        context = {
            "weapon_id": weapon.tarkov_id,
            "weapon_name": weapon_name,
            "target_tier": "A",  # Meta builds should be A or S tier
        }
        
        build_data = await ai_gen_service.generate_build_with_ai(
            intent="meta_build",
            context=context,
            user_id=user.id,
            language=user.language
        )
        
        if not build_data or not build_data.get("text"):
            error_text = "❌ Не удалось сгенерировать мета-сборку" if user.language == "ru" else "❌ Failed to generate meta build"
            await callback.message.edit_text(error_text)
            await callback.answer()
            return
        
        # Format build with tier display
        from utils.formatters import format_ai_build_with_tier
        tier = build_data.get("tier", "A")
        formatted_build = format_ai_build_with_tier(build_data["text"], tier, user.language)
        
        # Send build result
        await callback.message.edit_text(formatted_build, parse_mode="Markdown")
        await callback.answer()
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating meta build: {e}", exc_info=True)
        error_text = get_text("ai_error", user.language)
        await callback.message.edit_text(error_text)
        await callback.answer()


@router.callback_query(F.data.startswith("build:random:"))
async def generate_random_build_for_weapon(callback: CallbackQuery, user_service, weapon_service, ai_gen_service=None):
    """Generate random AI build for selected weapon."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    weapon_id = int(callback.data.split(":")[2])
    
    if not ai_gen_service:
        await callback.answer(get_text("ai_not_available", user.language), show_alert=True)
        return
    
    weapon = await weapon_service.get_weapon_by_id(weapon_id)
    if not weapon:
        await callback.answer(get_text("error", user.language))
        return
    
    weapon_name = weapon.name_ru if user.language == "ru" else weapon.name_en
    
    # Select random tier
    selected_tier = ai_gen_service._select_random_tier()
    loading_text = get_text("random_build_with_tier", user.language, tier=selected_tier)
    await callback.message.edit_text(loading_text)
    
    try:
        context = {
            "weapon_id": weapon.tarkov_id,
            "weapon_name": weapon_name,
            "target_tier": selected_tier,
        }
        
        build_data = await ai_gen_service.generate_build_with_ai(
            intent="random_build",
            context=context,
            user_id=user.id,
            language=user.language
        )
        
        if not build_data or not build_data.get("text"):
            error_text = "❌ Не удалось сгенерировать сборку" if user.language == "ru" else "❌ Failed to generate build"
            await callback.message.edit_text(error_text)
            await callback.answer()
            return
        
        from utils.formatters import format_ai_build_with_tier
        tier = build_data.get("tier", selected_tier)
        formatted_build = format_ai_build_with_tier(build_data["text"], tier, user.language)
        
        await callback.message.edit_text(formatted_build, parse_mode="Markdown")
        await callback.answer()
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating random build: {e}", exc_info=True)
        error_text = get_text("ai_error", user.language)
        await callback.message.edit_text(error_text)
        await callback.answer()


@router.callback_query(F.data.startswith("build:loyalty:"))
async def start_loyalty_build_prapor(callback: CallbackQuery, user_service):
    """Start loyalty build process - select Prapor level."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    weapon_id = int(callback.data.split(":")[2])
    
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
                callback_data=f"loyalty:prapor:{weapon_id}:{level}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("loyalty:prapor:"))
async def select_therapist_loyalty(callback: CallbackQuery, user_service):
    """Select Therapist loyalty level."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_id = int(parts[2])
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
                callback_data=f"loyalty:therapist:{weapon_id}:{prapor_ll}:{level}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("loyalty:therapist:"))
async def select_fence_loyalty(callback: CallbackQuery, user_service):
    """Select Fence loyalty level (only 1 or 4)."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_id = int(parts[2])
    prapor_ll = int(parts[3])
    therapist_ll = int(parts[4])
    
    trader_name = "Скупщик" if user.language == "ru" else "Fence"
    text = "🤝 " + (
        f"Выберите уровень лояльности для {trader_name}:\n(Доступно только LL1 или LL4)"
        if user.language == "ru" else
        f"Select loyalty level for {trader_name}:\n(Only LL1 or LL4 available)"
    )
    
    buttons = [
        [InlineKeyboardButton(
            text="LL1",
            callback_data=f"loyalty:fence:{weapon_id}:{prapor_ll}:{therapist_ll}:1"
        )],
        [InlineKeyboardButton(
            text="LL4",
            callback_data=f"loyalty:fence:{weapon_id}:{prapor_ll}:{therapist_ll}:4"
        )]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("loyalty:fence:"))
async def select_skier_loyalty(callback: CallbackQuery, user_service):
    """Select Skier loyalty level."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_id = int(parts[2])
    prapor_ll = int(parts[3])
    therapist_ll = int(parts[4])
    fence_ll = int(parts[5])
    
    trader_name = "Лыжник" if user.language == "ru" else "Skier"
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
                callback_data=f"loyalty:skier:{weapon_id}:{prapor_ll}:{therapist_ll}:{fence_ll}:{level}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("loyalty:skier:"))
async def select_mechanic_loyalty(callback: CallbackQuery, user_service):
    """Select Mechanic loyalty level."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_id = int(parts[2])
    prapor_ll = int(parts[3])
    therapist_ll = int(parts[4])
    fence_ll = int(parts[5])
    skier_ll = int(parts[6])
    
    trader_name = "Механик" if user.language == "ru" else "Mechanic"
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
                callback_data=f"loyalty:mechanic:{weapon_id}:{prapor_ll}:{therapist_ll}:{fence_ll}:{skier_ll}:{level}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("loyalty:mechanic:"))
async def select_ragman_loyalty(callback: CallbackQuery, user_service):
    """Select Ragman loyalty level."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_id = int(parts[2])
    prapor_ll = int(parts[3])
    therapist_ll = int(parts[4])
    fence_ll = int(parts[5])
    skier_ll = int(parts[6])
    mechanic_ll = int(parts[7])
    
    trader_name = "Барахольщик" if user.language == "ru" else "Ragman"
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
                callback_data=f"loyalty:ragman:{weapon_id}:{prapor_ll}:{therapist_ll}:{fence_ll}:{skier_ll}:{mechanic_ll}:{level}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("loyalty:ragman:"))
async def select_jaeger_loyalty(callback: CallbackQuery, user_service):
    """Select Jaeger loyalty level (can be 0 = not available)."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_id = int(parts[2])
    prapor_ll = int(parts[3])
    therapist_ll = int(parts[4])
    fence_ll = int(parts[5])
    skier_ll = int(parts[6])
    mechanic_ll = int(parts[7])
    ragman_ll = int(parts[8])
    
    trader_name = "Егерь" if user.language == "ru" else "Jaeger"
    text = "🤝 " + (
        f"Выберите уровень лояльности для {trader_name}:\n(LL0 = нет доступа)"
        if user.language == "ru" else
        f"Select loyalty level for {trader_name}:\n(LL0 = not available)"
    )
    
    buttons = []
    for level in [0, 1, 2, 3, 4]:
        label = ("Нет доступа" if user.language == "ru" else "Not available") if level == 0 else f"LL{level}"
        buttons.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"loyalty:jaeger:{weapon_id}:{prapor_ll}:{therapist_ll}:{fence_ll}:{skier_ll}:{mechanic_ll}:{ragman_ll}:{level}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("loyalty:jaeger:"))
async def select_ref_loyalty(callback: CallbackQuery, user_service):
    """Select Ref loyalty level (can be 0 = not available)."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_id = int(parts[2])
    prapor_ll = int(parts[3])
    therapist_ll = int(parts[4])
    fence_ll = int(parts[5])
    skier_ll = int(parts[6])
    mechanic_ll = int(parts[7])
    ragman_ll = int(parts[8])
    jaeger_ll = int(parts[9])
    
    trader_name = "Реф" if user.language == "ru" else "Ref"
    text = "🤝 " + (
        f"Выберите уровень лояльности для {trader_name}:\n(LL0 = нет доступа)"
        if user.language == "ru" else
        f"Select loyalty level for {trader_name}:\n(LL0 = not available)"
    )
    
    buttons = []
    for level in [0, 1, 2, 3, 4]:
        label = ("Нет доступа" if user.language == "ru" else "Not available") if level == 0 else f"LL{level}"
        buttons.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"loyalty:ref:{weapon_id}:{prapor_ll}:{therapist_ll}:{fence_ll}:{skier_ll}:{mechanic_ll}:{ragman_ll}:{jaeger_ll}:{level}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("loyalty:ref:"))
async def select_budget_for_loyalty_build(callback: CallbackQuery, user_service):
    """Ask for budget after all traders selected."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_id = int(parts[2])
    prapor_ll = int(parts[3])
    therapist_ll = int(parts[4])
    fence_ll = int(parts[5])
    skier_ll = int(parts[6])
    mechanic_ll = int(parts[7])
    ragman_ll = int(parts[8])
    jaeger_ll = int(parts[9])
    ref_ll = int(parts[10])
    
    text = "💰 " + (
        "Выберите бюджет для сборки:"
        if user.language == "ru" else
        "Select budget for build:"
    )
    
    budgets = [
        (50000, "50K"),
        (100000, "100K"),
        (200000, "200K"),
        (500000, "500K"),
        (1000000, "1M"),
        (0, "♾️ " + ("Без лимита" if user.language == "ru" else "Unlimited"))
    ]
    
    buttons = []
    for budget_value, label in budgets:
        buttons.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"loyalty_budget:{weapon_id}:{prapor_ll}:{therapist_ll}:{fence_ll}:{skier_ll}:{mechanic_ll}:{ragman_ll}:{jaeger_ll}:{ref_ll}:{budget_value}"
            )
        ])
    
    # Add skip button
    buttons.append([
        InlineKeyboardButton(
            text="⏭️ " + ("Пропустить" if user.language == "ru" else "Skip"),
            callback_data=f"loyalty_budget:{weapon_id}:{prapor_ll}:{therapist_ll}:{fence_ll}:{skier_ll}:{mechanic_ll}:{ragman_ll}:{jaeger_ll}:{ref_ll}:0"
        )
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("loyalty_budget:"))
async def select_flea_market_for_loyalty(callback: CallbackQuery, user_service):
    """Ask if user wants to use flea market."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_id = int(parts[1])
    prapor_ll = int(parts[2])
    therapist_ll = int(parts[3])
    fence_ll = int(parts[4])
    skier_ll = int(parts[5])
    mechanic_ll = int(parts[6])
    ragman_ll = int(parts[7])
    jaeger_ll = int(parts[8])
    ref_ll = int(parts[9])
    budget = int(parts[10])
    
    text = "🏪 " + (
        "Использовать Барахолку?"
        if user.language == "ru" else
        "Use Flea Market?"
    )
    
    buttons = [
        [InlineKeyboardButton(
            text="✅ " + ("Да" if user.language == "ru" else "Yes"),
            callback_data=f"gen_loyalty_final:{weapon_id}:{prapor_ll}:{therapist_ll}:{fence_ll}:{skier_ll}:{mechanic_ll}:{ragman_ll}:{jaeger_ll}:{ref_ll}:{budget}:1"
        )],
        [InlineKeyboardButton(
            text="❌ " + ("Нет" if user.language == "ru" else "No"),
            callback_data=f"gen_loyalty_final:{weapon_id}:{prapor_ll}:{therapist_ll}:{fence_ll}:{skier_ll}:{mechanic_ll}:{ragman_ll}:{jaeger_ll}:{ref_ll}:{budget}:0"
        )]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("gen_loyalty_final:"))
async def generate_loyalty_build_final(callback: CallbackQuery, user_service, weapon_service, ai_gen_service=None):
    """Generate build based on all selected trader loyalty levels, budget, and flea market."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_id = int(parts[1])
    prapor_ll = int(parts[2])
    therapist_ll = int(parts[3])
    fence_ll = int(parts[4])
    skier_ll = int(parts[5])
    mechanic_ll = int(parts[6])
    ragman_ll = int(parts[7])
    jaeger_ll = int(parts[8])
    ref_ll = int(parts[9])
    budget = int(parts[10])
    use_flea = bool(int(parts[11]))
    
    if not ai_gen_service:
        await callback.answer(get_text("ai_not_available", user.language), show_alert=True)
        return
    
    weapon = await weapon_service.get_weapon_by_id(weapon_id)
    if not weapon:
        await callback.answer(get_text("error", user.language))
        return
    
    weapon_name = weapon.name_ru if user.language == "ru" else weapon.name_en
    
    # Build trader levels summary
    trader_names_ru = {
        "prapor": "Прапор",
        "therapist": "Терапевт",
        "fence": "Скупщик",
        "skier": "Лыжник",
        "mechanic": "Механик",
        "ragman": "Барахольщик",
        "jaeger": "Егерь",
        "ref": "Реф"
    }
    
    trader_levels = {
        "prapor": prapor_ll,
        "therapist": therapist_ll,
        "fence": fence_ll,
        "skier": skier_ll,
        "mechanic": mechanic_ll,
        "ragman": ragman_ll,
        "jaeger": jaeger_ll,
        "ref": ref_ll
    }
    
    budget_text = f"{budget:,}₽" if budget > 0 else ("без лимита" if user.language == "ru" else "unlimited")
    flea_text = "с барахолкой" if use_flea else "без барахолки" if user.language == "ru" else "with flea" if use_flea else "no flea"
    
    loading_text = "⚙️ " + (
        f"Генерирую сборку ({flea_text}, бюджет: {budget_text})..."
        if user.language == "ru" else
        f"Generating build ({flea_text}, budget: {budget_text})..."
    )
    await callback.message.edit_text(loading_text)
    
    try:
        context = {
            "weapon_id": weapon.tarkov_id,
            "weapon_name": weapon_name,
            "trader_levels": trader_levels,
            "budget": budget if budget > 0 else None,
            "use_flea_market": use_flea,
            "target_tier": "B"  # Loyalty builds typically balanced
        }
        
        build_data = await ai_gen_service.generate_build_with_ai(
            intent="custom_request",
            context=context,
            user_id=user.id,
            language=user.language
        )
        
        if not build_data or not build_data.get("text"):
            error_text = "❌ Не удалось сгенерировать сборку" if user.language == "ru" else "❌ Failed to generate build"
            await callback.message.edit_text(error_text)
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
        logger.error(f"Error generating loyalty build: {e}", exc_info=True)
        error_text = get_text("ai_error", user.language)
        await callback.message.edit_text(error_text)
        await callback.answer()


@router.callback_query(F.data.startswith("build:budget:"))
async def select_budget_for_build(callback: CallbackQuery, user_service):
    """Show budget selection menu for dynamic build."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    weapon_id = int(callback.data.split(":")[2])
    
    text = "💰 " + ("Выберите бюджет для сборки:" if user.language == "ru" else "Select budget for build:")
    
    budgets = [
        (50000, "50,000₽ " + ("(Эконом)" if user.language == "ru" else "(Budget)")),
        (100000, "100,000₽ " + ("(Средний)" if user.language == "ru" else "(Medium)")),
        (200000, "200,000₽ " + ("(Хороший)" if user.language == "ru" else "(Good)")),
        (300000, "300,000₽ " + ("(Отличный)" if user.language == "ru" else "(Excellent)")),
        (500000, "500,000₽ " + ("(Премиум)" if user.language == "ru" else "(Premium)")),
        (1000000, "1,000,000₽ " + ("(Топ)" if user.language == "ru" else "(Top)"))
    ]
    
    buttons = []
    for budget_value, label in budgets:
        buttons.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"gen_budget:{weapon_id}:{budget_value}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("gen_budget:"))
async def generate_budget_build(callback: CallbackQuery, user_service, weapon_service, ai_gen_service=None):
    """Generate build based on budget."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_id = int(parts[1])
    budget = int(parts[2])
    
    if not ai_gen_service:
        await callback.answer(get_text("ai_not_available", user.language), show_alert=True)
        return
    
    weapon = await weapon_service.get_weapon_by_id(weapon_id)
    if not weapon:
        await callback.answer(get_text("error", user.language))
        return
    
    weapon_name = weapon.name_ru if user.language == "ru" else weapon.name_en
    
    loading_text = "⚙️ " + (f"Генерирую сборку (бюджет: {budget:,}₽)..." if user.language == "ru" 
                             else f"Generating build (budget: {budget:,}₽)...")
    await callback.message.edit_text(loading_text)
    
    try:
        # Determine tier based on budget
        if budget >= 500000:
            target_tier = "A"
        elif budget >= 200000:
            target_tier = "B"
        else:
            target_tier = "C"
        
        context = {
            "weapon_id": weapon.tarkov_id,
            "weapon_name": weapon_name,
            "budget": budget,
            "target_tier": target_tier
        }
        
        build_data = await ai_gen_service.generate_build_with_ai(
            intent="custom_request",
            context=context,
            user_id=user.id,
            language=user.language
        )
        
        if not build_data or not build_data.get("text"):
            error_text = "❌ Не удалось сгенерировать сборку" if user.language == "ru" else "❌ Failed to generate build"
            await callback.message.edit_text(error_text)
            await callback.answer()
            return
        
        from utils.formatters import format_ai_build_with_tier
        tier = build_data.get("tier", target_tier)
        formatted_build = format_ai_build_with_tier(build_data["text"], tier, user.language)
        
        await callback.message.edit_text(formatted_build, parse_mode="Markdown")
        await callback.answer()
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating budget build: {e}", exc_info=True)
        error_text = get_text("ai_error", user.language)
        await callback.message.edit_text(error_text)
        await callback.answer()


# Preset build handler removed - replaced with AI generation in v5.3
