"""Budget build and constructor handlers for specific weapons."""
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from database import Database
from localization import get_text
from handlers.dynamic_builds import DynamicBuildStates, temp_build_data, format_generated_build
from services import BuildGenerator, BuildGeneratorConfig, CompatibilityChecker, TierEvaluator

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data.startswith("build:budget:"))
async def start_budget_build_for_weapon(callback: CallbackQuery, db: Database, user_service, state: FSMContext):
    """Start budget build generation for specific weapon."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    weapon_id = int(callback.data.split(":")[2])
    
    # Get weapon from database
    weapon = await db.get_weapon_by_id(weapon_id)
    if not weapon:
        await callback.answer(get_text("weapon_not_found", user.language))
        return
    
    # Store weapon info in state
    await state.update_data(budget_weapon_id=weapon_id)
    
    weapon_name = weapon.name_ru if user.language == "ru" else weapon.name_en
    message_text = (
        f"💰 **Сборка по бюджету**\n\n"
        f"🔫 Оружие: **{weapon_name}**\n\n"
        f"Введите ваш бюджет в рублях (например: 150000):"
        if user.language == "ru"
        else f"💰 **Budget Build**\n\n"
        f"🔫 Weapon: **{weapon_name}**\n\n"
        f"Enter your budget in rubles (e.g., 150000):"
    )
    
    await callback.message.edit_text(message_text, parse_mode="Markdown")
    await state.set_state(DynamicBuildStates.waiting_for_weapon_budget)
    await callback.answer()


@router.message(DynamicBuildStates.waiting_for_weapon_budget)
async def process_weapon_budget(message: Message, db: Database, user_service, state: FSMContext, api_client):
    """Process budget input and generate build for specific weapon."""
    user = await user_service.get_or_create_user(message.from_user.id)
    
    # Validate budget
    try:
        budget = int(message.text.strip().replace(",", "").replace(" ", ""))
        if budget <= 0:
            raise ValueError()
    except ValueError:
        await message.answer(get_text("invalid_budget", user.language))
        return
    
    # Get weapon_id from state
    data = await state.get_data()
    weapon_id = data.get("budget_weapon_id")
    
    if not weapon_id:
        await message.answer(get_text("error", user.language))
        await state.clear()
        return
    
    # Get weapon from database
    weapon = await db.get_weapon_by_id(weapon_id)
    if not weapon:
        await message.answer(get_text("weapon_not_found", user.language))
        await state.clear()
        return
    
    # Show loading message
    weapon_name = weapon.name_ru if user.language == "ru" else weapon.name_en
    loading_msg = await message.answer(
        f"⚙️ Генерирую сборку для {weapon_name}..." 
        if user.language == "ru" 
        else f"⚙️ Generating build for {weapon_name}..."
    )
    
    # Search for weapon in API by name
    try:
        weapons = await api_client.get_all_weapons(lang=user.language)
        weapon_name_search = weapon.name_en.lower()
        
        api_weapon = None
        for w in weapons:
            if weapon_name_search in w.get("name", "").lower() or weapon_name_search in w.get("shortName", "").lower():
                api_weapon = w
                break
        
        if not api_weapon:
            error_text = (
                f"❌ Не удалось найти {weapon_name} в API для генерации сборки."
                if user.language == "ru"
                else f"❌ Could not find {weapon_name} in API for build generation."
            )
            await loading_msg.edit_text(error_text)
            await state.clear()
            return
        
        weapon_api_id = api_weapon.get("id")
        
        # Initialize services
        compatibility = CompatibilityChecker(api_client)
        tier_eval = TierEvaluator()
        generator = BuildGenerator(api_client, compatibility, tier_eval)
        
        # Get user's trader levels
        trader_levels = user.trader_levels or {
            "prapor": 1, "therapist": 1, "fence": 1, "skier": 1,
            "peacekeeper": 1, "mechanic": 1, "ragman": 1, "jaeger": 1
        }
        
        # Create configuration for specific weapon
        config = BuildGeneratorConfig(
            budget=budget,
            trader_levels=trader_levels,
            use_flea_only=False,
            weapon_type=None,
            prioritize_ergonomics=False,
            prioritize_recoil=True
        )
        
        # Generate build for specific weapon
        build = await generator.generate_build_for_weapon(weapon_api_id, config, language=user.language)
        
        if not build:
            error_text = (
                "❌ Не удалось сгенерировать сборку. Попробуйте увеличить бюджет."
                if user.language == "ru"
                else "❌ Failed to generate build. Try increasing the budget."
            )
            await loading_msg.edit_text(error_text)
            await state.clear()
            return
        
        # Store build data temporarily
        temp_build_data[user.user_id] = {
            "build": build,
            "budget": budget
        }
        
        # Format build display
        text = await format_generated_build(build, budget, user.language, tier_eval)
        
        # Action buttons
        buttons = [
            [
                InlineKeyboardButton(
                    text=get_text("save_build", user.language),
                    callback_data="save_dynamic_build"
                ),
                InlineKeyboardButton(
                    text=get_text("regenerate_build", user.language),
                    callback_data=f"regenerate_weapon_build:{weapon_id}:{budget}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("back", user.language),
                    callback_data="cancel_build"
                )
            ]
        ]
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await loading_msg.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error generating weapon budget build: {e}", exc_info=True)
        await loading_msg.edit_text(get_text("error", user.language))
        await state.clear()


@router.callback_query(F.data.startswith("regenerate_weapon_build:"))
async def regenerate_weapon_build(callback: CallbackQuery, db: Database, user_service, api_client):
    """Regenerate a build for specific weapon with same budget."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_id = int(parts[1])
    budget = int(parts[2])
    
    # Get weapon from database
    weapon = await db.get_weapon_by_id(weapon_id)
    if not weapon:
        await callback.answer(get_text("weapon_not_found", user.language))
        return
    
    weapon_name = weapon.name_ru if user.language == "ru" else weapon.name_en
    
    # Show loading message
    await callback.message.edit_text(
        f"⚙️ Генерирую новую сборку для {weapon_name}..." 
        if user.language == "ru" 
        else f"⚙️ Generating new build for {weapon_name}..."
    )
    
    # Search for weapon in API
    try:
        weapons = await api_client.get_all_weapons(lang=user.language)
        weapon_name_search = weapon.name_en.lower()
        
        api_weapon = None
        for w in weapons:
            if weapon_name_search in w.get("name", "").lower() or weapon_name_search in w.get("shortName", "").lower():
                api_weapon = w
                break
        
        if not api_weapon:
            await callback.message.edit_text(get_text("error", user.language))
            await callback.answer()
            return
        
        weapon_api_id = api_weapon.get("id")
        
        # Initialize services
        compatibility = CompatibilityChecker(api_client)
        tier_eval = TierEvaluator()
        generator = BuildGenerator(api_client, compatibility, tier_eval)
        
        # Get user's trader levels
        trader_levels = user.trader_levels or {
            "prapor": 1, "therapist": 1, "fence": 1, "skier": 1,
            "peacekeeper": 1, "mechanic": 1, "ragman": 1, "jaeger": 1
        }
        
        # Create configuration
        config = BuildGeneratorConfig(
            budget=budget,
            trader_levels=trader_levels,
            use_flea_only=False,
            weapon_type=None,
            prioritize_ergonomics=False,
            prioritize_recoil=True
        )
        
        # Generate build
        build = await generator.generate_build_for_weapon(weapon_api_id, config, language=user.language)
        
        if not build:
            await callback.message.edit_text(get_text("error", user.language))
            await callback.answer()
            return
        
        # Store build data temporarily
        temp_build_data[user.user_id] = {
            "build": build,
            "budget": budget
        }
        
        # Format build display
        text = await format_generated_build(build, budget, user.language, tier_eval)
        
        # Action buttons
        buttons = [
            [
                InlineKeyboardButton(
                    text=get_text("save_build", user.language),
                    callback_data="save_dynamic_build"
                ),
                InlineKeyboardButton(
                    text=get_text("regenerate_build", user.language),
                    callback_data=f"regenerate_weapon_build:{weapon_id}:{budget}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("back", user.language),
                    callback_data="cancel_build"
                )
            ]
        ]
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer(get_text("build_generated", user.language))
        
    except Exception as e:
        logger.error(f"Error regenerating weapon build: {e}", exc_info=True)
        await callback.message.edit_text(get_text("error", user.language))
        await callback.answer()


@router.callback_query(F.data.startswith("build:constructor:"))
async def start_constructor(callback: CallbackQuery, db: Database, user_service, state: FSMContext, api_client):
    """Start build constructor for specific weapon."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    weapon_id = int(callback.data.split(":")[2])
    
    # Get weapon from database
    weapon = await db.get_weapon_by_id(weapon_id)
    if not weapon:
        await callback.answer(get_text("weapon_not_found", user.language))
        return
    
    weapon_name = weapon.name_ru if user.language == "ru" else weapon.name_en
    
    # Show loading message
    await callback.message.edit_text(
        f"⚙️ Загружаю данные для {weapon_name}..." 
        if user.language == "ru" 
        else f"⚙️ Loading data for {weapon_name}..."
    )
    
    # Use tarkov_id from database if available
    try:
        if not weapon.tarkov_id:
            error_text = (
                f"❌ {weapon_name} не поддерживается конструктором. Попробуйте другое оружие."
                if user.language == "ru"
                else f"❌ {weapon_name} is not supported by constructor. Try another weapon."
            )
            await callback.message.edit_text(error_text)
            await callback.answer()
            return
        
        # Get weapon details with slots using tarkov_id
        weapon_details = await api_client.get_weapon_details(weapon.tarkov_id)
        
        if not weapon_details or "properties" not in weapon_details:
            await callback.message.edit_text(get_text("error", user.language))
            await callback.answer()
            return
        
        slots = weapon_details.get("properties", {}).get("slots", [])
        
        if not slots:
            error_text = (
                f"❌ {weapon_name} не имеет модифицируемых слотов."
                if user.language == "ru"
                else f"❌ {weapon_name} has no modifiable slots."
            )
            await callback.message.edit_text(error_text)
            await callback.answer()
            return
        
        # Store constructor data in state
        await state.update_data(
            constructor_weapon_id=weapon_id,
            constructor_weapon_api_id=api_weapon.get("id"),
            constructor_weapon_name=weapon_name,
            constructor_slots=slots,
            constructor_current_slot=0,
            constructor_selected_modules={}
        )
        
        # Show first slot selection
        await show_slot_selection(callback.message, state, user.language, api_client)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error starting constructor: {e}", exc_info=True)
        await callback.message.edit_text(get_text("error", user.language))
        await callback.answer()


async def show_slot_selection(message, state: FSMContext, language: str, api_client):
    """Show module selection for current slot."""
    data = await state.get_data()
    slots = data.get("constructor_slots", [])
    current_slot_idx = data.get("constructor_current_slot", 0)
    weapon_name = data.get("constructor_weapon_name", "")
    selected_modules = data.get("constructor_selected_modules", {})
    
    if current_slot_idx >= len(slots):
        # All slots filled, show final build
        await show_final_constructor_build(message, state, language)
        return
    
    current_slot = slots[current_slot_idx]
    slot_name = current_slot.get("name", f"Slot {current_slot_idx + 1}")
    allowed_items = current_slot.get("filters", {}).get("allowedItems", [])
    
    if not allowed_items:
        # Skip this slot, no compatible items
        await state.update_data(constructor_current_slot=current_slot_idx + 1)
        await show_slot_selection(message, state, language, api_client)
        return
    
    # Limit to first 10 items for display
    display_items = allowed_items[:10]
    
    text = (
        f"🛠️ **Конфигуратор сборки**\n\n"
        f"🔫 {weapon_name}\n"
        f"📍 Слот: **{slot_name}**\n\n"
        f"Выберите модуль ({current_slot_idx + 1}/{len(slots)}):"
        if language == "ru"
        else f"🛠️ **Build Constructor**\n\n"
        f"🔫 {weapon_name}\n"
        f"📍 Slot: **{slot_name}**\n\n"
        f"Select module ({current_slot_idx + 1}/{len(slots)}):"
    )
    
    # Create buttons for each module
    buttons = []
    for item in display_items:
        item_name = item.get("name", item.get("shortName", "Unknown"))
        price = item.get("avg24hPrice", 0)
        button_text = f"{item_name} ({price:,}₽)" if price else item_name
        
        buttons.append([
            InlineKeyboardButton(
                text=button_text[:60],  # Limit length
                callback_data=f"constructor_select:{current_slot_idx}:{item.get('id')}"
            )
        ])
    
    # Add skip button
    buttons.append([
        InlineKeyboardButton(
            text="⏭️ Пропустить" if language == "ru" else "⏭️ Skip",
            callback_data=f"constructor_skip:{current_slot_idx}"
        )
    ])
    
    # Add cancel button
    buttons.append([
        InlineKeyboardButton(
            text="❌ Отмена" if language == "ru" else "❌ Cancel",
            callback_data="cancel_build"
        )
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")


@router.callback_query(F.data.startswith("constructor_select:"))
async def constructor_select_module(callback: CallbackQuery, state: FSMContext, api_client, user_service):
    """Handle module selection in constructor."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    slot_idx = int(parts[1])
    module_id = parts[2]
    
    # Store selected module
    data = await state.get_data()
    selected_modules = data.get("constructor_selected_modules", {})
    selected_modules[str(slot_idx)] = module_id
    
    # Move to next slot
    await state.update_data(
        constructor_selected_modules=selected_modules,
        constructor_current_slot=slot_idx + 1
    )
    
    await show_slot_selection(callback.message, state, user.language, api_client)
    await callback.answer()


@router.callback_query(F.data.startswith("constructor_skip:"))
async def constructor_skip_slot(callback: CallbackQuery, state: FSMContext, api_client, user_service):
    """Skip current slot in constructor."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    slot_idx = int(callback.data.split(":")[1])
    
    # Move to next slot without selecting module
    await state.update_data(constructor_current_slot=slot_idx + 1)
    
    await show_slot_selection(callback.message, state, user.language, api_client)
    await callback.answer()


async def show_final_constructor_build(message, state: FSMContext, language: str):
    """Show final constructed build."""
    data = await state.get_data()
    weapon_name = data.get("constructor_weapon_name", "")
    selected_modules = data.get("constructor_selected_modules", {})
    
    if not selected_modules:
        text = (
            "❌ Вы не выбрали ни одного модуля."
            if language == "ru"
            else "❌ You didn't select any modules."
        )
        await message.edit_text(text)
        await state.clear()
        return
    
    text = (
        f"✅ **Сборка завершена!**\n\n"
        f"🔫 {weapon_name}\n"
        f"🔧 Выбрано модулей: {len(selected_modules)}\n\n"
        f"💾 Функция сохранения в разработке."
        if language == "ru"
        else f"✅ **Build completed!**\n\n"
        f"🔫 {weapon_name}\n"
        f"🔧 Selected modules: {len(selected_modules)}\n\n"
        f"💾 Save function under development."
    )
    
    await message.edit_text(text, parse_mode="Markdown")
    await state.clear()
