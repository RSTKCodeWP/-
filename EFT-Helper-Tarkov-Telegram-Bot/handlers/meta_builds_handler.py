"""Handler for meta builds generation from API presets."""
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from localization import get_text
from database.meta_builds_data import META_BUILDS

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data.startswith("meta_build:"))
async def generate_meta_build(callback: CallbackQuery, user_service, build_service):
    """Generate meta build from weapon preset."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    
    # Parse callback data
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer(get_text("error", user.language))
        return
    
    weapon_name = parts[1]
    build_type = parts[2]
    
    # Get build info from META_BUILDS
    builds = META_BUILDS.get(weapon_name, {})
    build_info = builds.get(build_type)
    
    if not build_info:
        error_text = "❌ Сборка не найдена" if user.language == "ru" else "❌ Build not found"
        await callback.message.edit_text(error_text)
        await callback.answer()
        return
    
    # Show loading message
    loading_text = "⏳ Генерирую сборку..." if user.language == "ru" else "⏳ Generating build..."
    await callback.message.edit_text(loading_text)
    
    try:
        # Generate build from API preset
        build_data = await build_service.generate_meta_build_from_preset(weapon_name, user.language)
        
        if not build_data:
            error_text = "❌ Не удалось сгенерировать сборку" if user.language == "ru" else "❌ Failed to generate build"
            await callback.message.edit_text(error_text)
            await callback.answer()
            return
        
        # Format result
        weapon = build_data['weapon']
        modules = build_data.get('modules', [])
        preset_name = build_data.get('preset_name', 'Default')
        total_cost = build_data.get('total_cost', 0)
        
        # Build display text
        text = f"🏆 **{build_info.get('name_ru' if user.language == 'ru' else 'name_en')}**\n\n"
        text += f"🔫 **{weapon.get('name')}**\n"
        text += f"📦 Preset: {preset_name}\n\n"
        
        # Description
        description = build_info.get('description_ru' if user.language == 'ru' else 'description_en', '')
        if description:
            text += f"📝 {description}\n\n"
        
        # Show modules
        if modules:
            text += f"🔧 **{'Модули' if user.language == 'ru' else 'Modules'} ({len(modules)}):**\n\n"
            for i, mod in enumerate(modules[:15], 1):
                mod_name = mod.get('name', 'Unknown')
                mod_slot = mod.get('slot', '')
                mod_price = mod.get('price', 0)
                trader = mod.get('trader', 'Flea Market')
                trader_level = mod.get('trader_level', 15)
                
                # Translate trader name if needed
                from utils.localization_helpers import localize_trader_name
                trader_localized = localize_trader_name(trader, user.language)
                
                # Format trader info
                if trader == 'Flea Market':
                    trader_info = f"🏪 {trader_localized}"
                else:
                    trader_info = f"👤 {trader_localized} (LL{trader_level})"
                
                # Format slot info - only show if determined
                slot_text = f"[{mod_slot}] " if mod_slot and mod_slot != 'Unknown' else ""
                
                text += f"  {i}. {slot_text}{mod_name}\n"
                text += f"     💰 {mod_price:,}₽ | {trader_info}\n"
            
            if len(modules) > 15:
                text += f"\n  ... {'и ещё' if user.language == 'ru' else 'and'} {len(modules) - 15} {'модулей' if user.language == 'ru' else 'more modules'}\n"
            
            text += "\n"
        
        # Total cost and loyalty
        text += f"💰 **{'Стоимость' if user.language == 'ru' else 'Total Cost'}:** {total_cost:,}₽\n"
        
        min_loyalty = build_info.get('min_loyalty', 1)
        text += f"⭐ **{'Мин. уровень лояльности' if user.language == 'ru' else 'Min Loyalty Level'}:** {min_loyalty}\n"
        
        # Back button
        back_text = "« Назад к списку" if user.language == "ru" else "« Back to list"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=back_text,
                callback_data="back_to_meta_list"
            )]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error generating meta build: {e}", exc_info=True)
        error_text = get_text("error", user.language)
        await callback.message.edit_text(error_text)
        await callback.answer()


@router.callback_query(F.data == "back_to_meta_list")
async def back_to_meta_list(callback: CallbackQuery, user_service):
    """Go back to meta builds list."""
    from database.meta_builds_data import get_all_meta_builds
    
    user = await user_service.get_or_create_user(callback.from_user.id)
    
    # Get all meta builds
    all_builds = get_all_meta_builds()
    
    text = "🏆 " + ("Мета сборки" if user.language == "ru" else "Meta Builds") + "\n\n"
    text += ("Лучшие сборки для оружия с оптимальными характеристиками" if user.language == "ru" 
             else "Best weapon builds with optimal characteristics")
    
    # Create buttons
    buttons = []
    for build_data in all_builds[:20]:
        weapon = build_data['weapon']
        build_type = build_data['type']
        name = build_data.get('name_ru' if user.language == 'ru' else 'name_en', f"{weapon} {build_type}")
        
        buttons.append([
            InlineKeyboardButton(
                text=name,
                callback_data=f"meta_build:{weapon}:{build_type}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()
