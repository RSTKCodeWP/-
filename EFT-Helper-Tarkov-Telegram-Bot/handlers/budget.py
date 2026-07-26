"""Budget build handlers for the EFT Helper bot."""
import logging
import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from localization import get_text

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text.in_([get_text("budget_build_menu", "ru"), get_text("budget_build_menu", "en")]))
async def start_budget_build_from_menu(message: Message, user_service):
    """Start budget build from main menu - ask for weapon type or any."""
    user = await user_service.get_or_create_user(message.from_user.id)
    
    text = "💰 " + (
        "Выберите тип оружия или любое:"
        if user.language == "ru" else
        "Select weapon type or any:"
    )
    
    buttons = [
        [InlineKeyboardButton(
            text="🔫 " + ("Штурмовые винтовки" if user.language == "ru" else "Assault Rifles"),
            callback_data="budget_menu_weapon:assault_rifles"
        )],
        [InlineKeyboardButton(
            text="🎯 " + ("Марксманские винтовки" if user.language == "ru" else "DMR"),
            callback_data="budget_menu_weapon:dmr"
        )],
        [InlineKeyboardButton(
            text="🔫 " + ("Пистолеты-пулемёты" if user.language == "ru" else "SMG"),
            callback_data="budget_menu_weapon:smg"
        )],
        [InlineKeyboardButton(
            text="🔫 " + ("Снайперские винтовки" if user.language == "ru" else "Sniper Rifles"),
            callback_data="budget_menu_weapon:sniper_rifles"
        )],
        [InlineKeyboardButton(
            text="🔫 " + ("Дробовики" if user.language == "ru" else "Shotguns"),
            callback_data="budget_menu_weapon:shotguns"
        )],
        [InlineKeyboardButton(
            text="⏭️ " + ("Любое оружие" if user.language == "ru" else "Any Weapon"),
            callback_data="budget_menu_weapon:any"
        )]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("budget_menu_weapon:"))
async def budget_weapon_selected_choose_budget(callback: CallbackQuery, user_service):
    """Weapon type selected, ask for budget."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    weapon_category = callback.data.split(":")[1]
    
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
                callback_data=f"gen_budget_menu:{weapon_category}:{budget_value}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("gen_budget_menu:"))
async def generate_budget_build_from_menu(callback: CallbackQuery, user_service, weapon_service, ai_gen_service=None):
    """Generate budget build from main menu."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    weapon_category = parts[1]
    budget = int(parts[2])
    
    if not ai_gen_service:
        await callback.answer(get_text("ai_not_available", user.language), show_alert=True)
        return
    
    # Select random weapon from category or any
    if weapon_category == "any":
        weapons = await weapon_service.get_all_weapons()
        weapon = random.choice(weapons) if weapons else None
    else:
        weapons = await weapon_service.get_weapons_by_category(weapon_category)
        weapon = random.choice(weapons) if weapons else None
    
    if not weapon:
        await callback.message.edit_text("❌ Оружие не найдено" if user.language == "ru" else "❌ Weapon not found")
        await callback.answer()
        return
    
    weapon_name = weapon.name_ru if user.language == "ru" else weapon.name_en
    
    # Determine tier based on budget
    if budget >= 500000:
        target_tier = "A"
    elif budget >= 200000:
        target_tier = "B"
    else:
        target_tier = "C"
    
    loading_text = "⚙️ " + (
        f"Генерирую сборку для {weapon_name} (бюджет: {budget:,}₽)..."
        if user.language == "ru" else
        f"Generating build for {weapon_name} (budget: {budget:,}₽)..."
    )
    await callback.message.edit_text(loading_text)
    
    try:
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
        logger.error(f"Error generating budget build from menu: {e}", exc_info=True)
        error_text = get_text("ai_error", user.language)
        await callback.message.edit_text(error_text)
        await callback.answer()
