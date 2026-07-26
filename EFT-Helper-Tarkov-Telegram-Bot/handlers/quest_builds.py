"""Quest build generation handlers."""
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from localization import get_text

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data.startswith("build_quest:"))
async def generate_quest_build(callback: CallbackQuery, user_service, api_client):
    """Generate a build for quest requirements."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    quest_id = callback.data.split(":")[1]
    
    # Show loading message
    loading_text = "⏳ Генерирую сборку..." if user.language == "ru" else "⏳ Generating build..."
    await callback.message.edit_text(loading_text)
    
    try:
        # Get quest data with requirements
        tasks = await api_client.get_weapon_build_tasks(lang=user.language)
        quest_data = None
        for task in tasks:
            if task.get("id") == quest_id:
                quest_data = task
                break
        
        if not quest_data:
            error_text = get_text("error", user.language)
            await callback.message.edit_text(error_text)
            await callback.answer()
            return
        
        # Find buildWeapon objective
        objectives = quest_data.get("objectives", [])
        build_objective = None
        for obj in objectives:
            if obj.get('type') == 'buildWeapon':
                build_objective = obj
                break
        
        if not build_objective:
            error_text = "❌ Квест не требует сборки оружия" if user.language == "ru" else "❌ Quest doesn't require weapon build"
            await callback.message.edit_text(error_text)
            await callback.answer()
            return
        
        # Parse requirements
        from services.quest_build_service import QuestBuildService
        quest_service = QuestBuildService(api_client)
        
        requirements = quest_service.parse_quest_requirements(build_objective)
        if not requirements:
            error_text = "❌ Не удалось получить требования квеста" if user.language == "ru" else "❌ Failed to get quest requirements"
            await callback.message.edit_text(error_text)
            await callback.answer()
            return
        
        # Generate build
        build_result = await quest_service.generate_quest_build(requirements, user.language)
        
        if not build_result:
            error_text = "❌ Не удалось сгенерировать сборку" if user.language == "ru" else "❌ Failed to generate build"
            await callback.message.edit_text(error_text)
            await callback.answer()
            return
        
        # Format result
        quest_name = quest_data.get("name", "Unknown Quest")
        weapon = build_result['weapon']
        weapon_name = weapon.get('name', 'Unknown')
        stats = build_result['stats']
        meets_requirements = build_result['meets_requirements']
        
        text = f"📜 **{quest_name}**\n\n"
        text += f"🔫 **{weapon_name}**\n\n"
        
        # Show requirements
        text += quest_service.format_requirements_text(requirements, user.language)
        text += "\n"
        
        # Show current stats
        text += f"📊 **{'Текущие характеристики' if user.language == 'ru' else 'Current Stats'}:**\n"
        
        important_stats = {
            'ergonomics': 'Эргономика' if user.language == 'ru' else 'Ergonomics',
            'recoil': 'Отдача' if user.language == 'ru' else 'Recoil',
            'durability': 'Прочность' if user.language == 'ru' else 'Durability',
            'weight': 'Вес' if user.language == 'ru' else 'Weight',
            'height': 'Высота' if user.language == 'ru' else 'Height',
            'width': 'Ширина' if user.language == 'ru' else 'Width'
        }
        
        for key, label in important_stats.items():
            if key in stats:
                value = stats[key]
                # Find requirement for this stat
                req = next((r for r in requirements.requirements if r.name == key), None)
                if req:
                    if req.compare_method == '>=':
                        status = "✅" if value >= req.value else "❌"
                    elif req.compare_method == '<=':
                        status = "✅" if value <= req.value else "❌"
                    else:
                        status = "•"
                    
                    text += f"  {status} {label}: {value:.0f} ({req.compare_method} {req.value:.0f})\n"
        
        text += "\n"
        
        # Show modules if any
        modules = build_result.get('modules', [])
        if modules:
            text += f"🔧 **{'Установленные модули' if user.language == 'ru' else 'Installed Modules'}:**\n"
            for i, mod in enumerate(modules[:15], 1):  # Limit to 15 modules
                mod_name = mod.get('name', 'Unknown')
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
                
                text += f"  {i}. {mod_name}\n"
                text += f"     💰 {mod_price:,}₽ | {trader_info}\n"
            
            if len(modules) > 15:
                text += f"  ... {'и ещё' if user.language == 'ru' else 'and'} {len(modules) - 15} {'модулей' if user.language == 'ru' else 'more modules'}\n"
            text += "\n"
        
        if meets_requirements:
            text += "✅ " + ("Все требования выполнены!" if user.language == "ru" else "All requirements met!")
        else:
            text += "⚠️ " + ("Базовое оружие не соответствует требованиям" if user.language == "ru" else "Base weapon doesn't meet requirements")
            text += "\n" + ("Требуется установка модулей" if user.language == "ru" else "Mods installation required")
        
        text += f"\n\n💰 {'Стоимость' if user.language == 'ru' else 'Cost'}: {build_result['total_cost']:,}₽"
        
        if modules:
            text += f" ({'Оружие' if user.language == 'ru' else 'Weapon'}: {build_result['weapon'].get('avg24hPrice', 0):,}₽ + {'модули' if user.language == 'ru' else 'mods'}: {sum(m.get('price', 0) for m in modules):,}₽)"
        
        # Add button to go back
        back_text = "« Назад" if user.language == "ru" else "« Back"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=back_text,
                callback_data=f"quest_detail:{quest_id}"
            )]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error generating quest build: {e}", exc_info=True)
        error_text = get_text("error", user.language)
        await callback.message.edit_text(error_text)
        await callback.answer()
