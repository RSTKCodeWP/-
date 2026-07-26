"""Tier list handlers for the EFT Helper bot."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from database import Database, TierRating
from localization import get_text
from keyboards import get_tier_selection_keyboard


router = Router()


@router.message(F.text.in_([get_text("best_weapons", "ru"), get_text("best_weapons", "en")]))
async def show_tier_selection(message: Message, db: Database):
    """Show tier selection."""
    user = await db.get_or_create_user(message.from_user.id)
    
    text = get_text("best_weapons_title", user.language)
    keyboard = get_tier_selection_keyboard(user.language)
    
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("tier:"))
async def show_tier_weapons(callback: CallbackQuery, db: Database):
    """Show weapons for selected tier."""
    user = await db.get_or_create_user(callback.from_user.id)
    tier = callback.data.split(":")[1]
    
    # Get all weapons and filter by tier
    all_weapons = await db.get_all_weapons()
    tier_weapons = [w for w in all_weapons if w.tier_rating and w.tier_rating.value == tier]
    
    if not tier_weapons:
        await callback.message.edit_text(get_text("no_tier_weapons", user.language))
        await callback.answer()
        return
    
    # Format weapons list
    tier_name = get_text(f"tier_{tier.lower()}", user.language)
    text = f"{tier_name}\n\n"
    
    # Group by category
    from collections import defaultdict
    by_category = defaultdict(list)
    for weapon in tier_weapons:
        by_category[weapon.category].append(weapon)
    
    for category, weapons in sorted(by_category.items()):
        category_name = get_text(category.value, user.language)
        text += f"\n**{category_name}:**\n"
        for weapon in weapons:
            weapon_name = weapon.name_ru if user.language == "ru" else weapon.name_en
            text += f"  • {weapon_name}\n"
    
    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()
