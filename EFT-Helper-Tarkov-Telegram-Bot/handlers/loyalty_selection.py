"""Loyalty build selection handlers - multi-step trader loyalty selection."""
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from localization import get_text

logger = logging.getLogger(__name__)
router = Router()

# Trader flow order
TRADER_FLOW = [
    ("prapor", "💂 Прапор", "💂 Prapor"),
    ("therapist", "💊 Терапевт", "💊 Therapist"),
    ("fence", "🔒 Скупщик", "🔒 Fence"),
    ("skier", "⛷️ Лыжник", "⛷️ Skier"),
    ("peacekeeper", "🕊️ Миротворец", "🕊️ Peacekeeper"),
    ("mechanic", "🔧 Механик", "🔧 Mechanic"),
    ("ragman", "👔 Барахольщик", "👔 Ragman"),
    ("jaeger", "🏹 Егерь", "🏹 Jaeger"),
]


def get_trader_index(trader_name: str) -> int:
    """Get trader index in flow."""
    for i, (name, _, _) in enumerate(TRADER_FLOW):
        if name == trader_name:
            return i
    return -1


def get_next_trader(trader_name: str):
    """Get next trader in flow or None if finished."""
    idx = get_trader_index(trader_name)
    if idx >= 0 and idx < len(TRADER_FLOW) - 1:
        return TRADER_FLOW[idx + 1]
    return None


@router.callback_query(F.data.startswith("loy_sel:"))
async def select_trader_loyalty(callback: CallbackQuery, user_service):
    """Handle trader loyalty selection and move to next trader."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    
    # Parse: loy_sel:weapon_id:trader:level:existing_data
    parts = callback.data.split(":")
    weapon_id = int(parts[1])
    current_trader = parts[2]
    selected_level = int(parts[3])
    loyalty_data = parts[4] if len(parts) > 4 else ""
    
    # Add current selection to loyalty data
    # Format: trader1-level1_trader2-level2_...
    if loyalty_data:
        loyalty_data += f"_{current_trader}-{selected_level}"
    else:
        loyalty_data = f"{current_trader}-{selected_level}"
    
    # Get next trader
    next_trader = get_next_trader(current_trader)
    
    if next_trader:
        trader_key, trader_name_ru, trader_name_en = next_trader
        
        text = "🤝 " + ("Выбор уровней лояльности торговцев" if user.language == "ru" else "Select Trader Loyalty Levels")
        text += "\n\n" + (trader_name_ru if user.language == "ru" else trader_name_en) + " - "
        text += ("выберите уровень:" if user.language == "ru" else "select level:")
        
        # Special case for Fence - only LL1 or LL4
        if trader_key == "fence":
            buttons = [
                [InlineKeyboardButton(
                    text="0 (" + ("Нет" if user.language == "ru" else "None") + ")",
                    callback_data=f"loy_sel:{weapon_id}:{trader_key}:0:{loyalty_data}"
                )],
                [InlineKeyboardButton(
                    text="LL1",
                    callback_data=f"loy_sel:{weapon_id}:{trader_key}:1:{loyalty_data}"
                )],
                [InlineKeyboardButton(
                    text="LL4",
                    callback_data=f"loy_sel:{weapon_id}:{trader_key}:4:{loyalty_data}"
                )]
            ]
        else:
            buttons = []
            for level in [0, 1, 2, 3, 4]:
                label = f"LL{level}" if level > 0 else ("0 (Нет)" if user.language == "ru" else "0 (None)")
                buttons.append([
                    InlineKeyboardButton(
                        text=label,
                        callback_data=f"loy_sel:{weapon_id}:{trader_key}:{level}:{loyalty_data}"
                    )
                ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    else:
        # All traders selected - now ask for budget
        await ask_loyalty_budget(callback, user, weapon_id, loyalty_data)


async def ask_loyalty_budget(callback: CallbackQuery, user, weapon_id: int, loyalty_data: str):
    """Ask for optional budget after all traders selected."""
    text = "💰 " + ("Хотите указать бюджет?" if user.language == "ru" else "Do you want to specify a budget?")
    text += "\n\n" + ("Выберите бюджет или пропустите этот шаг." if user.language == "ru" else "Select a budget or skip this step.")
    
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
                callback_data=f"loy_budget:{weapon_id}:{loyalty_data}:{budget_value}"
            )
        ])
    
    # Add skip button
    buttons.append([
        InlineKeyboardButton(
            text="⏭️ " + ("Пропустить" if user.language == "ru" else "Skip"),
            callback_data=f"loy_budget:{weapon_id}:{loyalty_data}:skip"
        )
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("loy_budget:"))
async def select_loyalty_budget(callback: CallbackQuery, user_service):
    """Handle budget selection for loyalty build."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    
    # Parse: loy_budget:weapon_id:loyalty_data:budget
    parts = callback.data.split(":")
    weapon_id = int(parts[1])
    loyalty_data = parts[2]
    budget = parts[3]
    
    # Now ask about flea market
    await ask_flea_market(callback, user, weapon_id, loyalty_data, budget)


async def ask_flea_market(callback: CallbackQuery, user, weapon_id: int, loyalty_data: str, budget: str):
    """Ask if user wants to use flea market."""
    text = "🏪 " + ("Использовать барахолку?" if user.language == "ru" else "Use Flea Market?")
    text += "\n\n" + ("Разрешить покупку модулей на барахолке?" if user.language == "ru" 
                     else "Allow buying modules from the flea market?")
    
    buttons = [
        [InlineKeyboardButton(
            text="✅ " + ("Да" if user.language == "ru" else "Yes"),
            callback_data=f"gen_loyalty_full:{weapon_id}:{loyalty_data}:{budget}:yes"
        )],
        [InlineKeyboardButton(
            text="❌ " + ("Нет, только торговцы" if user.language == "ru" else "No, traders only"),
            callback_data=f"gen_loyalty_full:{weapon_id}:{loyalty_data}:{budget}:no"
        )]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("gen_loyalty_full:"))
async def generate_full_loyalty_build(callback: CallbackQuery, user_service, weapon_service, ai_gen_service=None):
    """Generate build with full loyalty configuration."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    
    # Parse: gen_loyalty_full:weapon_id:loyalty_data:budget:flea
    parts = callback.data.split(":")
    weapon_id = int(parts[1])
    loyalty_data = parts[2]
    budget = parts[3]
    use_flea = parts[4] == "yes"
    
    if not ai_gen_service:
        await callback.answer(get_text("ai_not_available", user.language), show_alert=True)
        return
    
    weapon = await weapon_service.get_weapon_by_id(weapon_id)
    if not weapon:
        await callback.answer(get_text("error", user.language))
        return
    
    weapon_name = weapon.name_ru if user.language == "ru" else weapon.name_en
    
    # Parse loyalty data: trader1-level1_trader2-level2
    trader_levels = {}
    for pair in loyalty_data.split("_"):
        if pair:
            trader, level = pair.split("-")
            trader_levels[trader] = int(level)
    
    # Format loading message
    budget_text = ""
    if budget != "skip":
        budget_value = int(budget) if budget != "0" else None
        if budget_value:
            budget_text = f", бюджет: {budget_value:,}₽" if user.language == "ru" else f", budget: {budget_value:,}₽"
        else:
            budget_text = ", " + ("без лимита" if user.language == "ru" else "unlimited")
    
    flea_text = (", с барахолкой" if use_flea else ", без барахолки") if user.language == "ru" else (", with flea" if use_flea else ", traders only")
    
    loading_text = "⚙️ " + (f"Генерирую сборку (лояльность торговцев{budget_text}{flea_text})..." if user.language == "ru" 
                             else f"Generating build (trader loyalty{budget_text}{flea_text})...")
    await callback.message.edit_text(loading_text)
    
    try:
        context = {
            "weapon_id": weapon.tarkov_id,
            "weapon_name": weapon_name,
            "trader_levels": trader_levels,
            "budget": int(budget) if budget not in ["skip", "0"] else None,
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
        logger.error(f"Error generating full loyalty build: {e}", exc_info=True)
        error_text = get_text("ai_error", user.language)
        await callback.message.edit_text(error_text)
        await callback.answer()
