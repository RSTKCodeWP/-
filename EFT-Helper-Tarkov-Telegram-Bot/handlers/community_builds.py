"""Community builds handler for v3.0."""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import Database, UserBuild
from localization import get_text

logger = logging.getLogger(__name__)

router = Router()


class CommunityStates(StatesGroup):
    """States for community builds interaction."""
    viewing_builds = State()


@router.message(F.text.in_([get_text("community_builds", "ru"), get_text("community_builds", "en")]))
async def show_community_builds(message: Message, db: Database, user_service):
    """Show community builds list."""
    user = await user_service.get_or_create_user(message.from_user.id)
    
    # Get public builds
    builds = await db.get_public_builds(limit=20)
    
    if not builds:
        await message.answer(get_text("no_community_builds", user.language))
        return
    
    text = f"**{get_text('community_builds_title', user.language)}**\n\n"
    text += get_text("community_builds_desc", user.language) + "\n\n"
    
    # Create inline keyboard with build buttons
    buttons = []
    for build in builds:
        # Get weapon name
        weapon = await db.get_weapon_by_id(build.weapon_id)
        weapon_name = weapon.name_ru if user.language == "ru" else weapon.name_en if weapon else "Unknown"
        
        button_text = f"{build.tier_rating.value} | {build.name} ({weapon_name}) | 👍 {build.likes}"
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"community_build:{build.id}"
        )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@router.message(F.text.in_([get_text("my_builds", "ru"), get_text("my_builds", "en")]))
async def show_my_builds(message: Message, db: Database, user_service):
    """Show user's saved builds."""
    user = await user_service.get_or_create_user(message.from_user.id)
    
    # Get user's builds
    builds = await db.get_user_builds(user.user_id, limit=50)
    
    if not builds:
        await message.answer(get_text("no_saved_builds", user.language))
        return
    
    text = f"**{get_text('my_builds_title', user.language)}**\n\n"
    
    # Create inline keyboard with build buttons
    buttons = []
    for build in builds:
        # Get weapon name
        weapon = await db.get_weapon_by_id(build.weapon_id)
        weapon_name = weapon.name_ru if user.language == "ru" else weapon.name_en if weapon else "Unknown"
        
        status_icon = "🌐" if build.is_public else "🔒"
        button_text = f"{status_icon} {build.tier_rating.value} | {build.name} ({weapon_name})"
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"my_build:{build.id}"
        )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@router.callback_query(F.data.startswith("community_build:"))
async def show_community_build_detail(callback: CallbackQuery, db: Database, user_service):
    """Show detailed view of a community build."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    build_id = int(callback.data.split(":")[1])
    
    build = await db.get_user_build_by_id(build_id)
    if not build:
        await callback.answer(get_text("error", user.language))
        return
    
    # Get weapon details
    weapon = await db.get_weapon_by_id(build.weapon_id)
    weapon_name = weapon.name_ru if user.language == "ru" else weapon.name_en if weapon else "Unknown"
    
    # Format build details
    text = f"**{build.tier_rating.value} | {build.name}**\n\n"
    text += f"🔫 {weapon_name}\n"
    text += f"{get_text('build_by_user', user.language, user_id=build.user_id)}\n"
    text += f"{get_text('build_likes', user.language, count=build.likes)}\n\n"
    
    # Stats
    text += f"{get_text('build_stats', user.language)}\n"
    if build.ergonomics:
        text += get_text("build_ergonomics", user.language, value=build.ergonomics) + "\n"
    if build.recoil_vertical:
        text += get_text("build_recoil_v", user.language, value=build.recoil_vertical) + "\n"
    text += f"\n💰 {get_text('build_total_cost', user.language, cost=build.total_cost)}\n"
    
    # Modules
    if build.modules:
        modules = await db.get_modules_by_ids(build.modules)
        text += f"\n{get_text('build_modules_list', user.language)}\n"
        for module in modules[:10]:  # Limit to 10 modules
            module_name = module.name_ru if user.language == "ru" else module.name_en
            text += f"  • {module_name}\n"
    
    # Action buttons
    buttons = [
        [
            InlineKeyboardButton(
                text=get_text("like_build", user.language),
                callback_data=f"like_build:{build.id}"
            ),
            InlineKeyboardButton(
                text=get_text("copy_build", user.language),
                callback_data=f"copy_build:{build.id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=get_text("back", user.language),
                callback_data="back_to_community"
            )
        ]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("my_build:"))
async def show_my_build_detail(callback: CallbackQuery, db: Database, user_service):
    """Show detailed view of user's own build."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    build_id = int(callback.data.split(":")[1])
    
    build = await db.get_user_build_by_id(build_id)
    if not build or build.user_id != user.user_id:
        await callback.answer(get_text("error", user.language))
        return
    
    # Get weapon details
    weapon = await db.get_weapon_by_id(build.weapon_id)
    weapon_name = weapon.name_ru if user.language == "ru" else weapon.name_en if weapon else "Unknown"
    
    # Format build details
    status = "🌐 " + get_text("make_public", user.language) if not build.is_public else "🔒 " + get_text("make_private", user.language)
    text = f"**{build.tier_rating.value} | {build.name}**\n\n"
    text += f"🔫 {weapon_name}\n"
    text += f"Status: {'Public' if build.is_public else 'Private'}\n"
    text += f"{get_text('build_likes', user.language, count=build.likes)}\n\n"
    
    # Stats
    text += f"{get_text('build_stats', user.language)}\n"
    if build.ergonomics:
        text += get_text("build_ergonomics", user.language, value=build.ergonomics) + "\n"
    if build.recoil_vertical:
        text += get_text("build_recoil_v", user.language, value=build.recoil_vertical) + "\n"
    text += f"\n💰 {get_text('build_total_cost', user.language, cost=build.total_cost)}\n"
    
    # Modules
    if build.modules:
        modules = await db.get_modules_by_ids(build.modules)
        text += f"\n{get_text('build_modules_list', user.language)}\n"
        for module in modules[:10]:
            module_name = module.name_ru if user.language == "ru" else module.name_en
            text += f"  • {module_name}\n"
    
    # Action buttons
    visibility_text = get_text("make_public", user.language) if not build.is_public else get_text("make_private", user.language)
    buttons = [
        [
            InlineKeyboardButton(
                text=visibility_text,
                callback_data=f"toggle_visibility:{build.id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=get_text("delete_build", user.language),
                callback_data=f"delete_build_confirm:{build.id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=get_text("back", user.language),
                callback_data="back_to_my_builds"
            )
        ]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("like_build:"))
async def like_build(callback: CallbackQuery, db: Database, user_service):
    """Like a community build."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    build_id = int(callback.data.split(":")[1])
    
    await db.increment_build_likes(build_id)
    await callback.answer(get_text("build_liked", user.language))


@router.callback_query(F.data.startswith("copy_build:"))
async def copy_build(callback: CallbackQuery, db: Database, user_service):
    """Copy a community build to user's collection."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    build_id = int(callback.data.split(":")[1])
    
    # Get the original build
    original = await db.get_user_build_by_id(build_id)
    if not original:
        await callback.answer(get_text("error", user.language))
        return
    
    # Create a copy for the user
    from database import UserBuild
    copied_build = UserBuild(
        id=0,  # Will be auto-generated
        user_id=user.user_id,
        weapon_id=original.weapon_id,
        name=f"{original.name} (Copy)",
        modules=original.modules.copy(),
        total_cost=original.total_cost,
        tier_rating=original.tier_rating,
        ergonomics=original.ergonomics,
        recoil_vertical=original.recoil_vertical,
        recoil_horizontal=original.recoil_horizontal,
        is_public=False
    )
    
    await db.create_user_build(copied_build)
    await callback.answer(get_text("build_copied", user.language))


@router.callback_query(F.data.startswith("toggle_visibility:"))
async def toggle_build_visibility(callback: CallbackQuery, db: Database, user_service):
    """Toggle build public/private status."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    build_id = int(callback.data.split(":")[1])
    
    build = await db.get_user_build_by_id(build_id)
    if not build or build.user_id != user.user_id:
        await callback.answer(get_text("error", user.language))
        return
    
    # Toggle visibility
    new_status = not build.is_public
    await db.update_user_build_visibility(build_id, new_status)
    
    message = get_text("build_published", user.language) if new_status else get_text("build_unpublished", user.language)
    await callback.answer(message)
    
    # Refresh the display
    await show_my_build_detail(callback, db, user_service)


@router.callback_query(F.data.startswith("delete_build_confirm:"))
async def confirm_delete_build(callback: CallbackQuery, user_service):
    """Confirm build deletion."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    build_id = callback.data.split(":")[1]
    
    text = get_text("confirm_delete", user.language)
    buttons = [
        [
            InlineKeyboardButton(
                text=get_text("yes", user.language),
                callback_data=f"delete_build_yes:{build_id}"
            ),
            InlineKeyboardButton(
                text=get_text("no", user.language),
                callback_data=f"my_build:{build_id}"
            )
        ]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("delete_build_yes:"))
async def delete_build(callback: CallbackQuery, db: Database, user_service):
    """Delete a build."""
    user = await user_service.get_or_create_user(callback.from_user.id)
    build_id = int(callback.data.split(":")[1])
    
    await db.delete_user_build(build_id, user.user_id)
    
    await callback.message.edit_text(get_text("build_deleted", user.language))
    await callback.answer()


@router.callback_query(F.data == "back_to_community")
async def back_to_community(callback: CallbackQuery, db: Database, user_service):
    """Go back to community builds list."""
    # Simulate message to reuse the handler
    callback.message.text = get_text("community_builds", "ru")
    await show_community_builds(callback.message, db, user_service)
    await callback.answer()


@router.callback_query(F.data == "back_to_my_builds")
async def back_to_my_builds(callback: CallbackQuery, db: Database, user_service):
    """Go back to my builds list."""
    # Simulate message to reuse the handler
    callback.message.text = get_text("my_builds", "ru")
    await show_my_builds(callback.message, db, user_service)
    await callback.answer()
