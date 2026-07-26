"""
Broadcast Wizard - Admin broadcast system with FSM.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7

This module provides a step-by-step wizard for admins to send broadcasts
to users and groups with flood protection.
"""

import asyncio
import logging
from typing import Optional, List, Any
from dataclasses import dataclass
from enum import Enum

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ContentType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.database.session import get_session
from app.database.models import Chat, PrivateChat, User
from app.config import settings
from app.handlers.admin_commands import SUPER_ADMINS

logger = logging.getLogger(__name__)

router = Router()


# ============================================================================
# Constants and Configuration
# ============================================================================

# Flood protection delay between messages (Requirements 13.6)
FLOOD_DELAY = 0.05  # 50ms between messages

# Content type options (Requirements 13.1)
class BroadcastContentType(str, Enum):
    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    VIDEO_NOTE = "video_note"  # Кружочек


# Recipient options (Requirements 13.2)
class BroadcastRecipients(str, Enum):
    PRIVATE = "private"  # ЛС Бота
    GROUPS = "groups"    # Группы
    ALL = "all"          # Везде


CONTENT_TYPE_LABELS = {
    BroadcastContentType.TEXT: "📝 Текст",
    BroadcastContentType.PHOTO: "🖼 Фото",
    BroadcastContentType.VIDEO: "🎬 Видео",
    BroadcastContentType.VIDEO_NOTE: "⚪ Кружочек",
}

RECIPIENTS_LABELS = {
    BroadcastRecipients.PRIVATE: "👤 ЛС Бота",
    BroadcastRecipients.GROUPS: "👥 Группы",
    BroadcastRecipients.ALL: "🌍 Везде",
}


# ============================================================================
# FSM States (Requirements 13.1, 13.2, 13.3, 13.4, 13.5)
# ============================================================================

class BroadcastStates(StatesGroup):
    """FSM states for broadcast wizard."""
    waiting_content_type = State()   # Step 1: Select content type (legacy)
    waiting_recipients = State()      # Step 2: Select recipients
    waiting_content = State()         # Step 3: Send content
    waiting_confirmation = State()    # Step 4: Confirm and send
    # Simplified flow
    quick_waiting_content = State()   # Quick: just send content
    quick_waiting_recipients = State() # Quick: select recipients after content


# ============================================================================
# Admin Access Control (Requirements 13.7)
# ============================================================================

def is_admin(user_id: int) -> bool:
    """
    Check if user is an admin allowed to use broadcast.
    
    **Property 18: Broadcast Admin Access Control**
    **Validates: Requirements 13.7**
    
    Access is granted if and only if the user's ID is in the admin list.
    """
    # Check if user is bot owner
    if user_id == settings.owner_id:
        return True
    # Check if user is in SUPER_ADMINS list
    return user_id in SUPER_ADMINS


# ============================================================================
# Broadcast Data Storage
# ============================================================================

@dataclass
class BroadcastData:
    """Data structure for broadcast wizard state."""
    content_type: Optional[BroadcastContentType] = None
    recipients: Optional[BroadcastRecipients] = None
    content: Optional[Any] = None
    caption: Optional[str] = None
    file_id: Optional[str] = None


# ============================================================================
# Broadcast Sender (Requirements 13.6)
# ============================================================================

class BroadcastSender:
    """
    Handles sending broadcasts with flood protection.
    
    Requirements: 13.6
    Uses asyncio.sleep(0.05) between messages to avoid Telegram flood limits.
    """
    
    @staticmethod
    async def get_private_chat_ids() -> List[int]:
        """Get all private chat user IDs."""
        async with get_session()() as session:
            result = await session.execute(
                select(PrivateChat.user_id).where(PrivateChat.is_blocked == False)
            )
            return [row[0] for row in result.all()]
    
    @staticmethod
    async def get_group_chat_ids() -> List[int]:
        """Get all group chat IDs."""
        async with get_session()() as session:
            result = await session.execute(select(Chat.id))
            return [row[0] for row in result.all()]
    
    @staticmethod
    async def send_broadcast(
        bot: Bot,
        content_type: BroadcastContentType,
        recipients: BroadcastRecipients,
        content: Any,
        caption: Optional[str] = None,
        file_id: Optional[str] = None
    ) -> tuple[int, int]:
        """
        Send broadcast to recipients with flood protection.
        
        Returns: (sent_count, failed_count)
        
        Requirements: 13.6
        """
        chat_ids = []
        
        # Gather recipient IDs based on selection
        if recipients == BroadcastRecipients.PRIVATE:
            chat_ids = await BroadcastSender.get_private_chat_ids()
        elif recipients == BroadcastRecipients.GROUPS:
            chat_ids = await BroadcastSender.get_group_chat_ids()
        elif recipients == BroadcastRecipients.ALL:
            private_ids = await BroadcastSender.get_private_chat_ids()
            group_ids = await BroadcastSender.get_group_chat_ids()
            chat_ids = private_ids + group_ids
        
        sent_count = 0
        failed_count = 0
        
        for chat_id in chat_ids:
            try:
                if content_type == BroadcastContentType.TEXT:
                    await bot.send_message(chat_id=chat_id, text=content)
                elif content_type == BroadcastContentType.PHOTO:
                    await bot.send_photo(chat_id=chat_id, photo=file_id, caption=caption)
                elif content_type == BroadcastContentType.VIDEO:
                    await bot.send_video(chat_id=chat_id, video=file_id, caption=caption)
                elif content_type == BroadcastContentType.VIDEO_NOTE:
                    await bot.send_video_note(chat_id=chat_id, video_note=file_id)
                
                sent_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to send broadcast to {chat_id}: {e}")
                failed_count += 1
            
            # Flood protection (Requirements 13.6)
            await asyncio.sleep(FLOOD_DELAY)
        
        return sent_count, failed_count


# ============================================================================
# Keyboard Builders
# ============================================================================

def build_content_type_keyboard() -> InlineKeyboardBuilder:
    """Build keyboard for content type selection (Requirements 13.1)."""
    keyboard = InlineKeyboardBuilder()
    
    for ct in BroadcastContentType:
        keyboard.button(
            text=CONTENT_TYPE_LABELS[ct],
            callback_data=f"bc_type_{ct.value}"
        )
    
    keyboard.button(text="❌ Отмена", callback_data="bc_cancel")
    keyboard.adjust(2, 2, 1)
    return keyboard


def build_recipients_keyboard() -> InlineKeyboardBuilder:
    """Build keyboard for recipients selection (Requirements 13.2)."""
    keyboard = InlineKeyboardBuilder()
    
    for r in BroadcastRecipients:
        keyboard.button(
            text=RECIPIENTS_LABELS[r],
            callback_data=f"bc_recipients_{r.value}"
        )
    
    keyboard.button(text="🔙 Назад", callback_data="bc_back_type")
    keyboard.button(text="❌ Отмена", callback_data="bc_cancel")
    keyboard.adjust(3, 2)
    return keyboard


def build_confirmation_keyboard() -> InlineKeyboardBuilder:
    """Build keyboard for confirmation (Requirements 13.5)."""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🚀 ОТПРАВИТЬ", callback_data="bc_confirm_send")
    keyboard.button(text="🔙 Назад", callback_data="bc_back_content")
    keyboard.button(text="❌ Отмена", callback_data="bc_cancel")
    keyboard.adjust(1, 2)
    return keyboard


# ============================================================================
# Command Handler (Requirements 13.7)
# ============================================================================

@router.message(Command("broadcast"))
async def cmd_broadcast(msg: Message, state: FSMContext):
    """
    /broadcast command - start broadcast wizard.
    
    Requirements: 13.7
    Only admins can access this command.
    """
    # Check if in private chat
    if msg.chat.type != 'private':
        await msg.reply("Рассылка доступна только в личных сообщениях.")
        return
    
    # Admin access check (Requirements 13.7)
    if not is_admin(msg.from_user.id):
        logger.warning(f"Unauthorized broadcast attempt by user {msg.from_user.id}")
        await msg.answer("⛔ Доступ запрещён. Эта команда только для администраторов.")
        return
    
    # Start wizard - Step 1: Content Type (Requirements 13.1)
    await state.set_state(BroadcastStates.waiting_content_type)
    
    keyboard = build_content_type_keyboard()
    await msg.answer(
        "📢 <b>Мастер рассылки</b>\n\n"
        "<b>Шаг 1/4:</b> Выберите тип контента:",
        reply_markup=keyboard.as_markup()
    )


@router.message(Command("bc"))
async def cmd_quick_broadcast(msg: Message, state: FSMContext):
    """
    /bc command - quick broadcast (auto-detect content type).
    
    Just send any content and it will auto-detect the type.
    """
    if msg.chat.type != 'private':
        await msg.reply("Рассылка доступна только в ЛС.")
        return
    
    if not is_admin(msg.from_user.id):
        await msg.answer("⛔ Доступ запрещён.")
        return
    
    await state.set_state(BroadcastStates.quick_waiting_content)
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="❌ Отмена", callback_data="bc_cancel")
    
    await msg.answer(
        "📢 <b>Быстрая рассылка</b>\n\n"
        "Просто отправь контент (текст, фото, видео или кружочек).\n"
        "Тип определится автоматически.",
        reply_markup=keyboard.as_markup()
    )


@router.message(BroadcastStates.quick_waiting_content)
async def handle_quick_content(msg: Message, state: FSMContext):
    """Handle quick broadcast content - auto-detect type."""
    if not is_admin(msg.from_user.id):
        return
    
    # Auto-detect content type
    content_type = None
    content = None
    caption = None
    file_id = None
    
    if msg.video_note:
        content_type = BroadcastContentType.VIDEO_NOTE
        file_id = msg.video_note.file_id
        content = "video_note"
    elif msg.video:
        content_type = BroadcastContentType.VIDEO
        file_id = msg.video.file_id
        caption = msg.caption
        content = "video"
    elif msg.photo:
        content_type = BroadcastContentType.PHOTO
        file_id = msg.photo[-1].file_id
        caption = msg.caption
        content = "photo"
    elif msg.text:
        content_type = BroadcastContentType.TEXT
        content = msg.text
    elif msg.animation:
        # GIF support
        content_type = BroadcastContentType.VIDEO
        file_id = msg.animation.file_id
        caption = msg.caption
        content = "animation"
    elif msg.document:
        # Document with caption
        await msg.reply("📎 Документы пока не поддерживаются. Отправь фото, видео или текст.")
        return
    else:
        await msg.reply("❌ Не могу определить тип контента. Отправь текст, фото, видео или кружочек.")
        return
    
    # Save content
    await state.update_data(
        content_type=content_type.value,
        content=content,
        caption=caption,
        file_id=file_id
    )
    await state.set_state(BroadcastStates.quick_waiting_recipients)
    
    # Show recipients selection
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="👤 ЛС Бота", callback_data="qbc_private")
    keyboard.button(text="👥 Группы", callback_data="qbc_groups")
    keyboard.button(text="🌍 Везде", callback_data="qbc_all")
    keyboard.button(text="❌ Отмена", callback_data="bc_cancel")
    keyboard.adjust(3, 1)
    
    preview = f"Тип: {CONTENT_TYPE_LABELS[content_type]}"
    if caption:
        preview += f"\nПодпись: {caption[:50]}..."
    elif content_type == BroadcastContentType.TEXT:
        preview += f"\nТекст: {content[:50]}..."
    
    await msg.answer(
        f"📢 <b>Быстрая рассылка</b>\n\n"
        f"{preview}\n\n"
        f"Куда отправить?",
        reply_markup=keyboard.as_markup()
    )


@router.callback_query(F.data.startswith("qbc_"))
async def cb_quick_recipients(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Handle quick broadcast recipients selection and send."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    recipients_map = {
        "qbc_private": BroadcastRecipients.PRIVATE,
        "qbc_groups": BroadcastRecipients.GROUPS,
        "qbc_all": BroadcastRecipients.ALL,
    }
    
    recipients = recipients_map.get(callback.data)
    if not recipients:
        await callback.answer("Неизвестный выбор", show_alert=True)
        return
    
    data = await state.get_data()
    content_type = BroadcastContentType(data['content_type'])
    content = data.get('content')
    caption = data.get('caption')
    file_id = data.get('file_id')
    
    await callback.answer("🚀 Отправка...")
    
    await callback.message.edit_text(
        "📢 <b>Рассылка...</b>\n\n⏳ Подождите..."
    )
    
    # Send
    sent_count, failed_count = await BroadcastSender.send_broadcast(
        bot=bot,
        content_type=content_type,
        recipients=recipients,
        content=content,
        caption=caption,
        file_id=file_id
    )
    
    await state.clear()
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📢 Ещё рассылка", callback_data="bc_quick_new")
    
    await callback.message.edit_text(
        f"📢 <b>Готово!</b>\n\n"
        f"✅ Отправлено: {sent_count}\n"
        f"❌ Ошибок: {failed_count}",
        reply_markup=keyboard.as_markup()
    )


@router.callback_query(F.data == "bc_quick_new")
async def cb_quick_new(callback: CallbackQuery, state: FSMContext):
    """Start new quick broadcast."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await state.set_state(BroadcastStates.quick_waiting_content)
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="❌ Отмена", callback_data="bc_cancel")
    
    await callback.message.edit_text(
        "📢 <b>Быстрая рассылка</b>\n\n"
        "Просто отправь контент (текст, фото, видео или кружочек).",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


# ============================================================================
# Step 1: Content Type Selection (Requirements 13.1)
# ============================================================================

@router.callback_query(F.data.startswith("bc_type_"))
async def cb_select_content_type(callback: CallbackQuery, state: FSMContext):
    """Handle content type selection."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    content_type_value = callback.data.split("_")[2]
    content_type = BroadcastContentType(content_type_value)
    
    await state.update_data(content_type=content_type.value)
    await state.set_state(BroadcastStates.waiting_recipients)
    
    # Step 2: Recipients (Requirements 13.2)
    keyboard = build_recipients_keyboard()
    await callback.message.edit_text(
        "📢 <b>Мастер рассылки</b>\n\n"
        f"Тип контента: {CONTENT_TYPE_LABELS[content_type]}\n\n"
        "<b>Шаг 2/4:</b> Выберите получателей:",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


# ============================================================================
# Step 2: Recipients Selection (Requirements 13.2)
# ============================================================================

@router.callback_query(F.data.startswith("bc_recipients_"))
async def cb_select_recipients(callback: CallbackQuery, state: FSMContext):
    """Handle recipients selection."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    recipients_value = callback.data.split("_")[2]
    recipients = BroadcastRecipients(recipients_value)
    
    data = await state.get_data()
    content_type = BroadcastContentType(data['content_type'])
    
    await state.update_data(recipients=recipients.value)
    await state.set_state(BroadcastStates.waiting_content)
    
    # Step 3: Content (Requirements 13.3)
    content_instruction = {
        BroadcastContentType.TEXT: "Отправьте текст сообщения:",
        BroadcastContentType.PHOTO: "Отправьте фото (можно с подписью):",
        BroadcastContentType.VIDEO: "Отправьте видео (можно с подписью):",
        BroadcastContentType.VIDEO_NOTE: "Отправьте кружочек (видеосообщение):",
    }
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Назад", callback_data="bc_back_recipients")
    keyboard.button(text="❌ Отмена", callback_data="bc_cancel")
    keyboard.adjust(2)
    
    await callback.message.edit_text(
        "📢 <b>Мастер рассылки</b>\n\n"
        f"Тип контента: {CONTENT_TYPE_LABELS[content_type]}\n"
        f"Получатели: {RECIPIENTS_LABELS[recipients]}\n\n"
        f"<b>Шаг 3/4:</b> {content_instruction[content_type]}",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


# ============================================================================
# Step 3: Content Input (Requirements 13.3)
# ============================================================================

@router.message(BroadcastStates.waiting_content)
async def handle_broadcast_content(msg: Message, state: FSMContext):
    """Handle content input for broadcast."""
    if not is_admin(msg.from_user.id):
        return
    
    data = await state.get_data()
    content_type = BroadcastContentType(data['content_type'])
    recipients = BroadcastRecipients(data['recipients'])
    
    # Validate content type matches
    content = None
    caption = None
    file_id = None
    
    if content_type == BroadcastContentType.TEXT:
        if not msg.text:
            await msg.reply("❌ Пожалуйста, отправьте текстовое сообщение.")
            return
        content = msg.text
        
    elif content_type == BroadcastContentType.PHOTO:
        if not msg.photo:
            await msg.reply("❌ Пожалуйста, отправьте фото.")
            return
        file_id = msg.photo[-1].file_id  # Largest photo
        caption = msg.caption
        content = "photo"
        
    elif content_type == BroadcastContentType.VIDEO:
        if not msg.video:
            await msg.reply("❌ Пожалуйста, отправьте видео.")
            return
        file_id = msg.video.file_id
        caption = msg.caption
        content = "video"
        
    elif content_type == BroadcastContentType.VIDEO_NOTE:
        if not msg.video_note:
            await msg.reply("❌ Пожалуйста, отправьте кружочек (видеосообщение).")
            return
        file_id = msg.video_note.file_id
        content = "video_note"
    
    # Save content data
    await state.update_data(content=content, caption=caption, file_id=file_id)
    await state.set_state(BroadcastStates.waiting_confirmation)
    
    # Step 4: Confirmation (Requirements 13.4, 13.5)
    keyboard = build_confirmation_keyboard()
    
    preview_text = (
        "📢 <b>Мастер рассылки</b>\n\n"
        f"Тип контента: {CONTENT_TYPE_LABELS[content_type]}\n"
        f"Получатели: {RECIPIENTS_LABELS[recipients]}\n\n"
        "<b>Шаг 4/4:</b> Предпросмотр\n\n"
    )
    
    if content_type == BroadcastContentType.TEXT:
        preview_text += f"<b>Текст:</b>\n{content[:500]}{'...' if len(content) > 500 else ''}"
    elif caption:
        preview_text += f"<b>Подпись:</b>\n{caption[:200]}{'...' if len(caption) > 200 else ''}"
    else:
        preview_text += "<i>Контент без подписи</i>"
    
    preview_text += "\n\n⚠️ Подтвердите отправку рассылки:"
    
    await msg.answer(preview_text, reply_markup=keyboard.as_markup())


# ============================================================================
# Step 4: Confirmation and Send (Requirements 13.5, 13.6)
# ============================================================================

@router.callback_query(F.data == "bc_confirm_send")
async def cb_confirm_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Confirm and send broadcast."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    data = await state.get_data()
    content_type = BroadcastContentType(data['content_type'])
    recipients = BroadcastRecipients(data['recipients'])
    content = data.get('content')
    caption = data.get('caption')
    file_id = data.get('file_id')
    
    await callback.answer("🚀 Отправка рассылки...", show_alert=False)
    
    # Update message to show progress
    await callback.message.edit_text(
        "📢 <b>Рассылка в процессе...</b>\n\n"
        "⏳ Пожалуйста, подождите..."
    )
    
    # Send broadcast (Requirements 13.6)
    sent_count, failed_count = await BroadcastSender.send_broadcast(
        bot=bot,
        content_type=content_type,
        recipients=recipients,
        content=content,
        caption=caption,
        file_id=file_id
    )
    
    # Clear state
    await state.clear()
    
    # Show results
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📢 Новая рассылка", callback_data="bc_new")
    
    await callback.message.edit_text(
        "📢 <b>Рассылка завершена!</b>\n\n"
        f"✅ Успешно отправлено: {sent_count}\n"
        f"❌ Ошибок: {failed_count}\n"
        f"📊 Всего: {sent_count + failed_count}",
        reply_markup=keyboard.as_markup()
    )


# ============================================================================
# Navigation Callbacks
# ============================================================================

@router.callback_query(F.data == "bc_back_type")
async def cb_back_to_type(callback: CallbackQuery, state: FSMContext):
    """Go back to content type selection."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await state.set_state(BroadcastStates.waiting_content_type)
    
    keyboard = build_content_type_keyboard()
    await callback.message.edit_text(
        "📢 <b>Мастер рассылки</b>\n\n"
        "<b>Шаг 1/4:</b> Выберите тип контента:",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "bc_back_recipients")
async def cb_back_to_recipients(callback: CallbackQuery, state: FSMContext):
    """Go back to recipients selection."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    data = await state.get_data()
    content_type = BroadcastContentType(data['content_type'])
    
    await state.set_state(BroadcastStates.waiting_recipients)
    
    keyboard = build_recipients_keyboard()
    await callback.message.edit_text(
        "📢 <b>Мастер рассылки</b>\n\n"
        f"Тип контента: {CONTENT_TYPE_LABELS[content_type]}\n\n"
        "<b>Шаг 2/4:</b> Выберите получателей:",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "bc_back_content")
async def cb_back_to_content(callback: CallbackQuery, state: FSMContext):
    """Go back to content input."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    data = await state.get_data()
    content_type = BroadcastContentType(data['content_type'])
    recipients = BroadcastRecipients(data['recipients'])
    
    await state.set_state(BroadcastStates.waiting_content)
    
    content_instruction = {
        BroadcastContentType.TEXT: "Отправьте текст сообщения:",
        BroadcastContentType.PHOTO: "Отправьте фото (можно с подписью):",
        BroadcastContentType.VIDEO: "Отправьте видео (можно с подписью):",
        BroadcastContentType.VIDEO_NOTE: "Отправьте кружочек (видеосообщение):",
    }
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Назад", callback_data="bc_back_recipients")
    keyboard.button(text="❌ Отмена", callback_data="bc_cancel")
    keyboard.adjust(2)
    
    await callback.message.edit_text(
        "📢 <b>Мастер рассылки</b>\n\n"
        f"Тип контента: {CONTENT_TYPE_LABELS[content_type]}\n"
        f"Получатели: {RECIPIENTS_LABELS[recipients]}\n\n"
        f"<b>Шаг 3/4:</b> {content_instruction[content_type]}",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "bc_cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancel broadcast wizard."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await state.clear()
    
    await callback.message.edit_text(
        "📢 <b>Рассылка отменена</b>\n\n"
        "Используйте /broadcast чтобы начать заново."
    )
    await callback.answer()


@router.callback_query(F.data == "bc_new")
async def cb_new_broadcast(callback: CallbackQuery, state: FSMContext):
    """Start new broadcast wizard."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await state.set_state(BroadcastStates.waiting_content_type)
    
    keyboard = build_content_type_keyboard()
    await callback.message.edit_text(
        "📢 <b>Мастер рассылки</b>\n\n"
        "<b>Шаг 1/4:</b> Выберите тип контента:",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()
