"""Dynamic build generation handler for v3.0."""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import Database, UserBuild
from localization import get_text
from services import BuildGenerator, BuildGeneratorConfig, CompatibilityChecker, TierEvaluator

logger = logging.getLogger(__name__)

router = Router()


class DynamicBuildStates(StatesGroup):
    """States for dynamic build generation."""
    waiting_for_budget = State()
    waiting_for_build_name = State()
    # Budget build for specific weapon
    waiting_for_weapon_budget = State()
    # Constructor states
    selecting_modules = State()
    waiting_for_constructor_name = State()


# Store temporary build data
temp_build_data = {}


@router.message(F.text.in_([get_text("dynamic_random_build", "ru"), get_text("dynamic_random_build", "en")]))
async def start_dynamic_build(message: Message, user_service, state: FSMContext):
    """Start dynamic build generation process."""
    user = await user_service.get_or_create_user(message.from_user.id)
    
    text = f"**{get_text('dynamic_build_title', user.language)}**\n\n"
    text += get_text("dynamic_build_desc", user.language) + "\n\n"
    text += get_text("enter_budget", user.language)
    
    await state.set_state(DynamicBuildStates.waiting_for_budget)
    await message.answer(text, parse_mode="Markdown")


@router.message(DynamicBuildStates.waiting_for_budget)
async def process_budget(message: Message, user_service, state: FSMContext, api_client):
    """Process budget input and generate build."""
    user = await user_service.get_or_create_user(message.from_user.id)
    
    # Validate budget
    try:
        budget = int(message.text.strip().replace(",", "").replace(" ", ""))
        if budget <= 0:
            raise ValueError()
    except ValueError:
        await message.answer(get_text("invalid_budget", user.language))
        return
    
    # Show loading message
    loading_msg = await message.answer(get_text("generating_build", user.language))
    
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
    try:
        build = await generator.generate_random_build(config, language=user.language)
        
        if not build:
            await loading_msg.edit_text(get_text("error", user.language))
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
                    callback_data=f"regenerate_build:{budget}"
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
        logger.error(f"Error generating build: {e}", exc_info=True)
        await loading_msg.edit_text(get_text("error", user.language))
        await state.clear()


@router.callback_query(F.data.startswith("regenerate_build:"))
async def regenerate_build(callback: CallbackQuery, user_service, api_client):
    """Regenerate a build with the same budget."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    budget = int(callback.data.split(":")[1])
    
    # Show loading message
    await callback.message.edit_text(get_text("generating_build", user.language))
    
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
    try:
        build = await generator.generate_random_build(config, language=user.language)
        
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
                    callback_data=f"regenerate_build:{budget}"
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
        logger.error(f"Error regenerating build: {e}", exc_info=True)
        await callback.message.edit_text(get_text("error", user.language))
        await callback.answer()


@router.callback_query(F.data == "save_dynamic_build")
async def save_dynamic_build(callback: CallbackQuery, db: Database, user_service, state: FSMContext):
    """Initiate save process for generated build."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    
    # Check if we have build data
    if user.user_id not in temp_build_data:
        await callback.answer(get_text("error", user.language))
        return
    
    # Ask for build name
    text = get_text("enter_build_name", user.language)
    await callback.message.edit_text(text)
    await state.set_state(DynamicBuildStates.waiting_for_build_name)
    await callback.answer()


@router.message(DynamicBuildStates.waiting_for_build_name)
async def save_build_with_name(message: Message, db: Database, user_service, state: FSMContext):
    """Save the build with user-provided name."""
    user = await user_service.get_or_create_user(message.from_user.id)
    build_name = message.text.strip()
    
    if user.user_id not in temp_build_data:
        await message.answer(get_text("error", user.language))
        await state.clear()
        return
    
    build_data = temp_build_data[user.user_id]
    generated_build = build_data["build"]
    
    # Note: Dynamic builds use tarkov.dev IDs which are strings, not DB integer IDs
    # For now, we cannot save dynamic builds as they don't map to our DB structure
    # This would require a complete redesign of the build storage system
    
    error_text = (
        "⚠️ Сохранение динамических сборок временно недоступно.\n\n"
        "Вы можете:\n"
        "• Сделать скриншот сборки\n"
        "• Записать характеристики\n"
        "• Использовать экспорт (в будущих версиях)"
        if user.language == "ru"
        else "⚠️ Saving dynamic builds is temporarily unavailable.\n\n"
        "You can:\n"
        "• Take a screenshot\n"
        "• Write down the stats\n"
        "• Use export (in future versions)"
    )
    
    await message.answer(error_text)
    await state.clear()
    
    # TODO: Implement proper dynamic build saving with tarkov_id mapping
    # This requires:
    # 1. New table for dynamic builds with tarkov_id references
    # 2. Mapping service between tarkov_id and DB IDs
    # 3. Export/import functionality for sharing


@router.callback_query(F.data == "cancel_build")
async def cancel_build(callback: CallbackQuery, user_service, state: FSMContext):
    """Cancel build generation."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    
    # Clean up temp data
    if user.user_id in temp_build_data:
        del temp_build_data[user.user_id]
    
    await callback.message.edit_text(get_text("back", user.language))
    await state.clear()
    await callback.answer()


async def format_generated_build(build, budget: int, language: str, tier_eval: TierEvaluator) -> str:
    """Format generated build for display."""
    text = f"**🎲 {get_text('build_generated', language)}**\n\n"
    text += f"🔫 **{build.weapon_name}**\n"
    text += f"{get_text('build_tier', language, tier=build.tier_rating.value)}\n\n"
    
    # Tier description
    tier_desc = tier_eval.get_tier_description(build.tier_rating, language)
    text += f"{tier_desc}\n\n"
    
    # Weapon characteristics
    weapon_props = build.weapon_data.get("properties", {})
    text += f"📊 **{get_text('weapon_characteristics', language)}:**\n\n"
    
    # Caliber
    if weapon_props.get("caliber"):
        text += f"  • {get_text('caliber', language)}: **{weapon_props['caliber']}**\n"
    
    # Fire rate
    if weapon_props.get("fireRate"):
        text += f"  • {get_text('fire_rate', language)}: **{weapon_props['fireRate']}** RPM\n"
    
    # Weapon price and trader info
    weapon_price = build.weapon_data.get("avg24hPrice", 0) or 0
    if weapon_price:
        text += f"  • 🏪 {get_text('weapon_price', language)}: **{weapon_price:,} ₽**\n"
    
    # Show weapon trader availability
    weapon_traders = build.weapon_data.get("buyFor", [])
    if weapon_traders:
        for trader_info in weapon_traders[:3]:  # Show up to 3 traders
            trader_name = trader_info.get("vendor", {}).get("name", "Unknown")
            price = trader_info.get("price", 0)
            trader_level = trader_info.get("vendor", {}).get("minLevel")
            currency = trader_info.get("currency", "RUB")
            
            if trader_name != "Flea Market":
                level_text = f" (Lvl {trader_level})" if trader_level else ""
                text += f"  • 🤝 {trader_name}{level_text}: {price:,} {currency}\n"
    
    # Base stats for comparison
    base_ergo = weapon_props.get("ergonomics", 0)
    base_recoil_v = weapon_props.get("recoilVertical", 0)
    base_recoil_h = weapon_props.get("recoilHorizontal", 0)
    
    text += "\n"
    
    # Build stats (with weapon + mods) - show improvement
    text += f"⚔️ **{get_text('final_stats', language)}:**\n"
    
    if build.ergonomics and base_ergo:
        ergo_diff = build.ergonomics - base_ergo
        ergo_sign = "📈" if ergo_diff > 0 else "➡️" if ergo_diff == 0 else "📉"
        ergo_change = f" {ergo_sign} +{ergo_diff}" if ergo_diff > 0 else f" {ergo_sign} {ergo_diff}" if ergo_diff < 0 else ""
        ergo_bar = "█" * min(int(build.ergonomics / 10), 10)
        text += f"  • {get_text('ergonomics_stat', language)}: **{build.ergonomics}**{ergo_change} {ergo_bar}\n"
    elif build.ergonomics:
        ergo_bar = "█" * min(int(build.ergonomics / 10), 10)
        text += f"  • {get_text('ergonomics_stat', language)}: **{build.ergonomics}** {ergo_bar}\n"
    
    if build.recoil_vertical and base_recoil_v:
        recoil_v_diff = build.recoil_vertical - base_recoil_v
        recoil_sign = "📉" if recoil_v_diff < 0 else "➡️" if recoil_v_diff == 0 else "📈"
        recoil_change = f" {recoil_sign} {recoil_v_diff:+d}" if recoil_v_diff != 0 else ""
        text += f"  • {get_text('vertical_recoil', language)}: **{build.recoil_vertical}**{recoil_change}\n"
    elif build.recoil_vertical:
        text += f"  • {get_text('vertical_recoil', language)}: **{build.recoil_vertical}**\n"
    
    if build.recoil_horizontal and base_recoil_h:
        recoil_h_diff = build.recoil_horizontal - base_recoil_h
        recoil_sign = "📉" if recoil_h_diff < 0 else "➡️" if recoil_h_diff == 0 else "📈"
        recoil_change = f" {recoil_sign} {recoil_h_diff:+d}" if recoil_h_diff != 0 else ""
        text += f"  • {get_text('horizontal_recoil', language)}: **{build.recoil_horizontal}**{recoil_change}\n"
    elif build.recoil_horizontal:
        text += f"  • {get_text('horizontal_recoil', language)}: **{build.recoil_horizontal}**\n"
    
    text += "\n"
    
    # Budget info
    text += f"💰 **{get_text('budget_title', language)}:**\n"
    if budget and budget > 0:
        text += f"  • {get_text('spent', language)}: **{build.total_cost:,} ₽** / {budget:,} ₽\n"
        text += f"  • {get_text('remaining', language)}: **{build.remaining_budget:,} ₽**\n\n"
    else:
        text += f"  • {get_text('spent', language)}: **{build.total_cost:,} ₽**\n"
        text += f"  • {get_text('budget_title', language)}: {get_text('no_budget_limit', language)}\n\n"
    
    # Availability
    if build.available_from:
        sources = ", ".join(build.available_from)
        text += f"\n{get_text('build_available_from', language, sources=sources)}\n"
    
    # Modules with trader info
    if build.modules:
        text += f"\n{get_text('build_modules_list', language)}\n"
        count = 0
        for slot_name, module_data in build.modules.items():
            if count >= 10:  # Limit to 10 modules for display
                remaining = len(build.modules) - 10
                text += f"  ... {'и ещё' if language == 'ru' else 'and'} {remaining} {'модулей' if language == 'ru' else 'more modules'}\n"
                break
            
            module_name = module_data.get("shortName") or module_data.get("name", slot_name)
            module_price = module_data.get("avg24hPrice", 0) or 0
            
            # Get best trader for this module
            traders = module_data.get("buyFor", [])
            trader_info_text = ""
            
            if traders:
                # Find best trader (not flea market)
                best_trader = None
                for trader in traders:
                    trader_name = trader.get("vendor", {}).get("name", "")
                    if trader_name and trader_name != "Flea Market":
                        best_trader = trader
                        break
                
                if best_trader:
                    trader_name = best_trader.get("vendor", {}).get("name", "")
                    trader_level = best_trader.get("vendor", {}).get("minLevel")
                    trader_price = best_trader.get("price", 0)
                    
                    # Translate trader name
                    trader_name_key = trader_name.lower().replace(" ", "")
                    if trader_name_key in ["prapor", "therapist", "fence", "skier", "peacekeeper", "mechanic", "ragman", "jaeger"]:
                        trader_name_localized = get_text(trader_name_key, language)
                    else:
                        trader_name_localized = trader_name
                    
                    if trader_level:
                        trader_info_text = f" | {trader_name_localized} Lvl{trader_level} ({trader_price:,}₽)"
                    else:
                        trader_info_text = f" | {trader_name_localized} ({trader_price:,}₽)"
            
            text += f"  • {module_name}{trader_info_text}\n"
            count += 1
    
    # Improvement suggestions
    suggestions = tier_eval.get_improvement_suggestions(
        tier=build.tier_rating,
        ergonomics=build.ergonomics,
        recoil_vertical=build.recoil_vertical,
        has_sight=any("sight" in s.lower() for s in build.modules.keys()),
        has_stock=any("stock" in s.lower() for s in build.modules.keys()),
        has_grip=any("grip" in s.lower() for s in build.modules.keys()),
        language=language
    )
    
    if suggestions and build.tier_rating.value in ["C", "D"]:
        text += f"\n💡 **{'Рекомендации' if language == 'ru' else 'Suggestions'}:**\n"
        for suggestion in suggestions[:3]:  # Limit to 3 suggestions
            text += f"{suggestion}\n"
    
    return text
