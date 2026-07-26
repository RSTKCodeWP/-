"""Build handlers for the EFT Helper bot."""
import logging
import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import Database, BuildCategory
from localization import get_text
from keyboards import get_builds_list_keyboard
from utils.formatters import format_build_card
from utils.localization_helpers import localize_trader_name

logger = logging.getLogger(__name__)


router = Router()


@router.message(F.text.in_([get_text("random_build", "ru"), get_text("random_build", "en")]))
async def show_random_build(message: Message, user_service, ai_gen_service=None, random_build_service=None):
    """Generate random build with AI using tier variety (v5.3)."""
    user = await user_service.get_or_create_user(message.from_user.id)
    
    # Use AI generation if available
    if ai_gen_service:
        try:
            # Select random tier
            from services.ai_generation_service import AIGenerationService
            selected_tier = ai_gen_service._select_random_tier()
            
            # Show loading with tier info
            loading_text = get_text("random_build_with_tier", user.language, tier=selected_tier)
            loading_msg = await message.answer(loading_text)
            
            # Get random weapon from database
            from database import Database
            db = Database()
            all_weapons = await db.get_all_weapons()
            
            if not all_weapons:
                error_text = "❌ Нет оружия в базе" if user.language == "ru" else "❌ No weapons in database"
                await loading_msg.edit_text(error_text)
                return
            
            import random
            weapon = random.choice(all_weapons)
            weapon_name = weapon.name_ru if user.language == "ru" else weapon.name_en
            
            # Generate build with AI
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
                await loading_msg.edit_text(error_text)
                return
            
            # Format build with tier display
            from utils.formatters import format_ai_build_with_tier
            tier = build_data.get("tier", selected_tier)
            formatted_build = format_ai_build_with_tier(build_data["text"], tier, user.language)
            
            # Send build result
            await loading_msg.edit_text(formatted_build, parse_mode="Markdown")
            return
            
        except Exception as e:
            logger.error(f"Error in AI random build generation: {e}", exc_info=True)
            # Fall through to legacy method
    
    # Fallback to legacy random build service
    if random_build_service:
        loading_msg = await message.answer(get_text("generating_random", user.language))
        
        try:
            build_data = await random_build_service.generate_random_build_for_random_weapon(lang=user.language)
            
            if not build_data:
                error_text = (
                    "⚠️ Не удалось сгенерировать сборку. Попробуйте позже или обновите данные через /sync."
                    if user.language == "ru"
                    else "⚠️ Failed to generate build. Try again later or update data via /sync."
                )
                await loading_msg.edit_text(error_text)
                return
            
            # Format build information
            build_text, total_cost = random_build_service.format_build_info(build_data, user.language)
            
            await loading_msg.edit_text(build_text, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Error generating random build: {e}", exc_info=True)
            error_text = (
            "⚠️ Не удалось сгенерировать сборку. Попробуйте позже или обновите данные через /sync."
            if user.language == "ru"
            else "⚠️ Failed to generate build. Try again later or update data via /sync."
        )
        await loading_msg.edit_text(error_text)


@router.message(F.text.in_([get_text("truly_random_build", "ru"), get_text("truly_random_build", "en")]))
async def show_truly_random_build(message: Message, user_service, random_build_service):
    """Show truly random build with compatibility checks."""
    user = await user_service.get_or_create_user(message.from_user.id)
    
    # Show loading message
    loading_msg = await message.answer(get_text("generating_truly_random", user.language))
    
    # Generate truly random build with user's language
    build_data = await random_build_service.generate_random_build_for_random_weapon(lang=user.language)
    
    if not build_data:
        await loading_msg.edit_text(get_text("error", user.language))
        return
    
    # Format build information
    build_text, total_cost = random_build_service.format_build_info(build_data, user.language)
    
    await loading_msg.edit_text(build_text, parse_mode="Markdown")


# Meta builds handler removed in v5.3 - meta builds now generated via AI through search
# Users can now generate meta builds by:
# 1. Searching for a weapon via "Search Weapon" button
# 2. Selecting the weapon
# 3. Clicking "Generate Meta Build" button


@router.message(F.text.in_([get_text("quest_builds", "ru"), get_text("quest_builds", "en")]))
async def show_quest_builds(message: Message, user_service, api_client):
    """Show quest-related builds with interactive buttons."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    user = await user_service.get_or_create_user(message.from_user.id)
    
    # Show loading message
    loading_msg = await message.answer(get_text("loading_quests", user.language))
    
    try:
        # Get only weapon build quests from API with user's language
        tasks = await api_client.get_weapon_build_tasks(lang=user.language)
    except Exception as e:
        logger.error(f"Error fetching weapon build tasks: {e}", exc_info=True)
        error_text = get_text("error", user.language) + "\n\n💡 " + (
            "Проверьте подключение к интернету и повторите попытку." if user.language == "ru" 
            else "Check your internet connection and try again."
        )
        await loading_msg.edit_text(error_text)
        return
    
    if not tasks:
        no_quests_text = get_text("no_quest_builds", user.language)
        no_quests_text += "\n\n💡 " + (
            "Квесты загружаются из Tarkov.dev API. Убедитесь в наличии интернет-соединения." if user.language == "ru" 
            else "Quests are loaded from Tarkov.dev API. Ensure you have an internet connection."
        )
        await loading_msg.edit_text(no_quests_text)
        return
    
    # Group quests by trader
    traders = {}
    for task in tasks:
        trader_data = task.get("trader")
        if not trader_data:
            continue
        trader_name = trader_data.get("name", "Unknown")
        if trader_name not in traders:
            traders[trader_name] = []
        traders[trader_name].append(task)
    
    # Format quest list
    text = f"**{get_text('quest_builds_title', user.language)}**\n\n"
    text += get_text("select_quest", user.language)
    
    # Create inline keyboard with quest buttons
    buttons = []
    trader_emoji = {
        "Prapor": "🔫",
        "Therapist": "💊",
        "Fence": "🤝",
        "Skier": "⛷️",
        "Peacekeeper": "🕊️",
        "Mechanic": "🔧",
        "Ragman": "👔",
        "Jaeger": "🌲",
        "Lightkeeper": "💡"
    }
    
    for trader_name in sorted(traders.keys()):
        trader_tasks = traders[trader_name]
        emoji = trader_emoji.get(trader_name, "👤")
        
        for task in sorted(trader_tasks, key=lambda t: t.get("minPlayerLevel", 0)):
            name = task.get("name", "Unknown Quest")
            level = task.get("minPlayerLevel", "?")
            task_id = task.get("id", "")
            button_text = f"{emoji} {name} (Lvl {level})"
            buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"quest_detail:{task_id}"
            )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await loading_msg.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")


@router.message(F.text.in_([get_text("all_quest_builds", "ru"), get_text("all_quest_builds", "en")]))
async def show_all_quest_builds(message: Message, user_service, api_client):
    """Show all quest builds."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    user = await user_service.get_or_create_user(message.from_user.id)
    
    # Show loading message
    loading_msg = await message.answer(get_text("loading_quests", user.language))
    
    # Get only weapon build quests from API with user's language
    tasks = await api_client.get_weapon_build_tasks(lang=user.language)
    
    if not tasks:
        await loading_msg.edit_text(get_text("no_quest_builds", user.language))
        return
    
    # Group quests by trader
    traders = {}
    for task in tasks:
        trader_data = task.get("trader")
        if not trader_data:
            continue
        trader_name = trader_data.get("name", "Unknown")
        if trader_name not in traders:
            traders[trader_name] = []
        traders[trader_name].append(task)
    
    # Format quest list
    text = f"**{get_text('all_quest_builds_title', user.language)}**\n\n"
    text += get_text("select_quest", user.language)
    
    # Create inline keyboard with quest buttons
    buttons = []
    trader_emoji = {
        "Prapor": "🔫",
        "Therapist": "💊",
        "Fence": "🤝",
        "Skier": "⛷️",
        "Peacekeeper": "🕊️",
        "Mechanic": "🔧",
        "Ragman": "👔",
        "Jaeger": "🌲",
        "Lightkeeper": "💡"
    }
    
    for trader_name in sorted(traders.keys()):
        trader_tasks = traders[trader_name]
        emoji = trader_emoji.get(trader_name, "👤")
        
        for task in sorted(trader_tasks, key=lambda t: t.get("minPlayerLevel", 0)):
            name = task.get("name", "Unknown Quest")
            level = task.get("minPlayerLevel", "?")
            task_id = task.get("id", "")
            button_text = f"{emoji} {name} (Lvl {level})"
            buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"quest_detail:{task_id}"
            )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await loading_msg.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")


@router.callback_query(F.data.startswith("build:"))
async def show_build_by_type(callback: CallbackQuery, db: Database):
    """Show build by type and weapon."""
    user = await db.get_or_create_user(callback.from_user.id)
    parts = callback.data.split(":")
    build_type = parts[1]
    weapon_id = int(parts[2])
    
    # Handle random builds separately - don't use static builds table
    if build_type == "random":
        # Random builds should use dynamic generation from main menu
        message_text = (
            "🎲 Для случайной сборки используйте кнопку **\"Случайная сборка\"** в главном меню.\n\n"
            "Она генерирует совершенно новую сборку каждый раз, не используя готовые шаблоны."
            if user.language == "ru"
            else "🎲 For random builds, use the **\"Random Build\"** button in the main menu.\n\n"
            "It generates a completely new build each time without using templates."
        )
        await callback.message.edit_text(message_text, parse_mode="Markdown")
        await callback.answer()
        return
    
    # Constructor and budget builds are handled by budget_constructor.py router
    if build_type in ["constructor", "budget"]:
        # These callbacks are handled by budget_constructor router
        return
    
    # Get builds by weapon and category (only for meta, loyalty)
    category_map = {
        "meta": BuildCategory.META,
        "loyalty": BuildCategory.LOYALTY
    }
    
    category = category_map.get(build_type)
    if not category:
        await callback.answer(get_text("error", user.language))
        return
    
    builds = await db.get_builds_by_weapon(weapon_id, category)
    
    if not builds:
        await callback.message.edit_text(get_text("no_builds_found", user.language))
        await callback.answer()
        return
    
    # Pick first build for non-random types
    build = builds[0]
    
    # Format and show build card
    weapon = await db.get_weapon_by_id(build.weapon_id)
    modules = await db.get_modules_by_ids(build.modules)
    
    # Check if weapon exists
    if not weapon:
        error_text = get_text("weapon_not_found", user.language)
        await callback.message.edit_text(error_text)
        await callback.answer()
        return
    
    build_text = await format_build_card(build, weapon, modules, user.language)
    
    keyboard_buttons = [
        [
            InlineKeyboardButton(
                text=get_text("regenerate_btn", user.language),
                callback_data=f"regenerate:{build.id}"
            )
        ]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(build_text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("quest_detail:"))
async def show_quest_detail(callback: CallbackQuery, user_service, api_client, build_service, db: Database):
    """Show quest details and recommended build."""
    from utils.formatters import format_build_card
    
    user = await user_service.get_or_create_user(callback.from_user.id)
    quest_id = callback.data.split(":")[1]
    
    # Get weapon build tasks from API to find the specific one with user's language
    tasks = await api_client.get_weapon_build_tasks(lang=user.language)
    quest_data = None
    for task in tasks:
        if task.get("id") == quest_id:
            quest_data = task
            break
    
    if not quest_data:
        await callback.answer(get_text("error", user.language))
        return
    
    # Format quest details
    name = quest_data.get("name", "Unknown Quest")
    trader_data = quest_data.get("trader", {})
    trader_name = trader_data.get("name", "Unknown") if trader_data else "Unknown"
    level = quest_data.get("minPlayerLevel", "?")
    experience = quest_data.get("experience", 0)
    map_data = quest_data.get("map")
    map_name = map_data.get("name") if map_data else "Any"
    
    objectives = quest_data.get("objectives", [])
    task_requirements = quest_data.get("taskRequirements", [])
    
    text = f"📜 **{name}**\n\n"
    text += f"**{get_text('quest_trader', user.language)}:** {trader_name}\n"
    text += f"**{get_text('quest_level', user.language)}:** {level}\n"
    text += f"**{get_text('quest_experience', user.language)}:** {experience} XP\n"
    if map_name and map_name != "Any":
        text += f"**{get_text('quest_map', user.language)}:** {map_name}\n"
    text += "\n"
    
    if task_requirements:
        text += f"📋 **{get_text('quest_required_tasks', user.language)}:**\n"
        for req in task_requirements[:5]:  # Limit to 5 requirements
            req_task = req.get("task", {})
            req_name = req_task.get("name", "Unknown")
            text += f"  • {req_name}\n"
        text += "\n"
    
    # Check for buildWeapon objectives and parse requirements
    from services.quest_build_service import QuestBuildService
    quest_service = QuestBuildService(api_client)
    
    build_objective = None
    for obj in objectives:
        if obj.get('type') == 'buildWeapon':
            build_objective = obj
            break
    
    has_build_requirements = False
    if build_objective:
        requirements = quest_service.parse_quest_requirements(build_objective)
        if requirements:
            has_build_requirements = True
            # Show requirements
            text += quest_service.format_requirements_text(requirements, user.language)
            text += "\n"
    
    if objectives:
        text += f"🎯 **{get_text('quest_objectives', user.language)}:**\n"
        for i, obj in enumerate(objectives[:10], 1):  # Limit to 10 objectives
            description = obj.get("description", "No description")
            obj_type = obj.get("type", "")
            optional = obj.get("optional", False)
            optional_mark = f" ({get_text('quest_optional', user.language)})" if optional else ""
            text += f"  {i}. {description}{optional_mark}\n"
        if len(objectives) > 10:
            text += f"  ... {get_text('quest_and_more', user.language)} {len(objectives) - 10} {get_text('quest_more_objectives', user.language)}\n"
        text += "\n"
    
    # Add button to generate build if quest has build requirements
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = None
    if has_build_requirements:
        build_text = "🔧 Собрать сборку" if user.language == "ru" else "🔧 Build Weapon"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=build_text,
                callback_data=f"build_quest:{quest_id}"
            )]
        ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("show_build:"))
async def show_specific_build(callback: CallbackQuery, db: Database):
    """Show specific build by ID."""
    user = await db.get_or_create_user(callback.from_user.id)
    build_id = int(callback.data.split(":")[1])
    
    build = await db.get_build_by_id(build_id)
    
    if not build:
        await callback.answer(get_text("error", user.language))
        return
    
    # Format and show build card
    weapon = await db.get_weapon_by_id(build.weapon_id)
    modules = await db.get_modules_by_ids(build.modules)
    
    # Check if weapon exists
    if not weapon:
        error_text = get_text("weapon_not_found", user.language)
        await callback.message.edit_text(error_text)
        await callback.answer()
        return
    
    build_text = await format_build_card(build, weapon, modules, user.language)
    await callback.message.edit_text(build_text, parse_mode="Markdown")
    await callback.answer()
