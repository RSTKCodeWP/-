"""Settings handlers for the EFT Helper bot."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import Database
from localization import get_text
from keyboards import get_settings_keyboard, get_main_menu_keyboard


router = Router()


@router.message(F.text.in_([get_text("settings", "ru"), get_text("settings", "en")]))
async def show_settings(message: Message, db: Database):
    """Show settings menu."""
    user = await db.get_or_create_user(message.from_user.id)
    
    current_lang = "🇷🇺 Русский" if user.language == "ru" else "🇬🇧 English"
    text = get_text("settings_title", language=user.language) + "\n\n"
    text += get_text("current_language", language=user.language, language_name=current_lang) + "\n\n"
    text += get_text("change_language", language=user.language)
    
    # Create inline keyboard for language selection
    inline_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🇷🇺 Русский" + (" ✅" if user.language == "ru" else ""),
                    callback_data="settings_lang:ru"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🇬🇧 English" + (" ✅" if user.language == "en" else ""),
                    callback_data="settings_lang:en"
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("back", user.language),
                    callback_data="back_to_menu"
                )
            ]
        ]
    )
    
    await message.answer(text, reply_markup=inline_keyboard)


@router.message(F.text.in_([get_text("lang_ru", "ru"), get_text("lang_ru", "en")]))
async def set_language_ru(message: Message, db: Database):
    """Set language to Russian."""
    await db.update_user_language(message.from_user.id, "ru")
    
    text = get_text("language_changed", language="ru", language_name="🇷🇺 Русский")
    keyboard = get_main_menu_keyboard("ru")
    
    await message.answer(text, reply_markup=keyboard)


@router.message(F.text.in_([get_text("lang_en", "ru"), get_text("lang_en", "en")]))
async def set_language_en(message: Message, db: Database):
    """Set language to English."""
    await db.update_user_language(message.from_user.id, "en")
    
    text = get_text("language_changed", language="en", language_name="🇬🇧 English")
    keyboard = get_main_menu_keyboard("en")
    
    await message.answer(text, reply_markup=keyboard)


@router.message(F.text.in_([get_text("back", "ru"), get_text("back", "en")]))
async def back_to_menu(message: Message, db: Database):
    """Go back to main menu."""
    user = await db.get_or_create_user(message.from_user.id)
    
    text = get_text("welcome", user.language)
    keyboard = get_main_menu_keyboard(user.language)
    
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("settings_lang:"))
async def handle_settings_language_change(callback: CallbackQuery, db: Database):
    """Handle language change from settings."""
    # Extract language code
    language = callback.data.split(":")[1]  # "ru" or "en"
    
    # Update user language
    await db.update_user_language(callback.from_user.id, language)
    
    # Update the inline keyboard to show the new selection
    inline_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🇷🇺 Русский" + (" ✅" if language == "ru" else ""),
                    callback_data="settings_lang:ru"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🇬🇧 English" + (" ✅" if language == "en" else ""),
                    callback_data="settings_lang:en"
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("back", language),
                    callback_data="back_to_menu"
                )
            ]
        ]
    )
    
    # Update the message
    current_lang = "🇷🇺 Русский" if language == "ru" else "🇬🇧 English"
    text = get_text("settings_title", language=language) + "\n\n"
    text += get_text("current_language", language=language, language_name=current_lang) + "\n\n"
    text += get_text("change_language", language=language)
    
    await callback.message.edit_text(text, reply_markup=inline_keyboard)
    
    # Show confirmation
    lang_name = "🇷🇺 Русский" if language == "ru" else "🇬🇧 English"
    await callback.answer(get_text("language_changed", language, language_name=lang_name), show_alert=True)


@router.callback_query(F.data == "back_to_menu")
async def callback_back_to_menu(callback: CallbackQuery, db: Database):
    """Handle back to menu callback."""
    user = await db.get_or_create_user(callback.from_user.id)
    
    text = get_text("welcome", user.language)
    keyboard = get_main_menu_keyboard(user.language)
    
    await callback.message.answer(text, reply_markup=keyboard)
    await callback.message.delete()
    await callback.answer()
