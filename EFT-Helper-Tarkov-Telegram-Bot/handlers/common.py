"""Common handlers for the EFT Helper bot."""
import os
import tempfile
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from database import Database
from localization import get_text
from keyboards import get_main_menu_keyboard, get_language_selection_keyboard


router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, db: Database):
    """Handle /start command."""
    # Check if user exists
    user = await db.get_user(message.from_user.id)
    
    if not user:
        # New user - show language selection
        text = get_text("select_language", "ru")  # Bilingual text
        keyboard = get_language_selection_keyboard()
        await message.answer(text, reply_markup=keyboard)
    else:
        # Existing user - show main menu
        welcome_text = get_text("welcome", user.language)
        keyboard = get_main_menu_keyboard(user.language)
        await message.answer(welcome_text, reply_markup=keyboard)


@router.message(F.text.in_([get_text("main_menu", "ru"), get_text("main_menu", "en")]))
async def show_main_menu(message: Message, user_service):
    """Show main menu."""
    user = await user_service.get_or_create_user(message.from_user.id)
    
    menu_text = get_text("welcome", user.language)
    keyboard = get_main_menu_keyboard(user.language)
    
    await message.answer(menu_text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("lang:"))
async def handle_language_selection(callback: CallbackQuery, db: Database):
    """Handle language selection for new users."""
    # Extract language code
    language = callback.data.split(":")[1]  # "ru" or "en"
    
    # Create user with selected language
    await db.create_user(callback.from_user.id, language=language)
    
    # Send confirmation and show main menu
    welcome_text = get_text("language_selected", language)
    await callback.message.edit_text(welcome_text)
    
    # Show main menu
    menu_text = get_text("welcome", language)
    keyboard = get_main_menu_keyboard(language)
    await callback.message.answer(menu_text, reply_markup=keyboard)
    
    await callback.answer()


@router.message(F.text & ~F.text.startswith("/") & ~F.text.in_([
    get_text("main_menu", "ru"), get_text("main_menu", "en"),
    get_text("search_weapon", "ru"), get_text("search_weapon", "en"),
    get_text("random_build", "ru"), get_text("random_build", "en"),
    get_text("all_quest_builds", "ru"), get_text("all_quest_builds", "en"),
    get_text("best_weapons", "ru"), get_text("best_weapons", "en"),
    get_text("settings", "ru"), get_text("settings", "en"),
    get_text("loyalty_build_menu", "ru"), get_text("loyalty_build_menu", "en"),
    get_text("budget_build_menu", "ru"), get_text("budget_build_menu", "en"),
]))
async def handle_text_message(message: Message, user_service, ai_assistant=None):
    """Handle all non-menu text messages and route to AI assistant."""
    # Get or create user
    user = await user_service.get_or_create_user(message.from_user.id)
    
    # Route to AI assistant if available
    if ai_assistant:
        try:
            # Show typing indicator
            await message.bot.send_chat_action(message.chat.id, "typing")
            
            # Get response from AI assistant
            response = await ai_assistant.handle_message(message, user.language)
            
            # Send response
            await message.answer(response, parse_mode="Markdown")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in AI assistant: {e}", exc_info=True)
            await message.answer(get_text("ai_error", user.language))
    else:
        # Fallback if AI assistant not available
        await message.answer(get_text("ai_not_available", user.language))


@router.message(F.voice)
async def handle_voice_message(message: Message, user_service, ai_assistant=None):
    """Handle voice messages."""
    # Get or create user
    user = await user_service.get_or_create_user(message.from_user.id)
    
    # Check if AI assistant is available
    if not ai_assistant:
        await message.answer(get_text("voice_not_supported", user.language))
        return
    
    try:
        # Show processing indicator
        processing_msg = await message.answer(get_text("voice_processing", user.language))
        await message.bot.send_chat_action(message.chat.id, "typing")
        
        # Download voice file
        voice_file = await message.bot.get_file(message.voice.file_id)
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_file:
            temp_path = temp_file.name
            await message.bot.download_file(voice_file.file_path, temp_path)
        
        try:
            # Process voice message
            response = await ai_assistant.handle_voice(message, temp_path, user.language)
            
            # Delete processing message
            await processing_msg.delete()
            
            # Send response
            await message.answer(response, parse_mode="Markdown")
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error handling voice message: {e}", exc_info=True)
        await message.answer(get_text("voice_processing_error", user.language))
