"""Admin panel handlers for statistics and broadcasting."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from utils.admin import is_admin
from services.admin_service import AdminService
from localization import get_text
import logging

logger = logging.getLogger(__name__)

router = Router()


class BroadcastStates(StatesGroup):
    """States for broadcast creation."""
    waiting_for_content = State()
    waiting_for_media = State()
    preview = State()


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Get admin panel main keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="📢 Создать рассылку", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="admin:close")]
    ])
    return keyboard


def get_broadcast_type_keyboard() -> InlineKeyboardMarkup:
    """Get broadcast type selection keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Все пользователи", callback_data="broadcast:all")],
        [InlineKeyboardButton(text="🔥 Активные (7 дней)", callback_data="broadcast:active")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:panel")]
    ])
    return keyboard


def get_broadcast_content_keyboard() -> InlineKeyboardMarkup:
    """Get broadcast content type keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Только текст", callback_data="content:text_only")],
        [InlineKeyboardButton(text="🖼 Добавить медиа", callback_data="content:with_media")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:panel")]
    ])
    return keyboard


def get_media_type_keyboard() -> InlineKeyboardMarkup:
    """Get media type selection keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼 Фото", callback_data="media:photo")],
        [InlineKeyboardButton(text="🎥 Видео", callback_data="media:video")],
        [InlineKeyboardButton(text="📄 Документ", callback_data="media:document")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:panel")]
    ])
    return keyboard


def get_preview_keyboard() -> InlineKeyboardMarkup:
    """Get preview confirmation keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить", callback_data="preview:send")],
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="preview:edit_text")],
        [InlineKeyboardButton(text="🔄 Изменить медиа", callback_data="preview:edit_media")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:panel")]
    ])
    return keyboard


@router.message(Command("admin"))
async def cmd_admin(message: Message, db):
    """Show admin panel."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ панели.")
        return
    
    text = (
        "🔧 <b>Админ панель</b>\n\n"
        "Выберите действие:"
    )
    
    await message.answer(text, reply_markup=get_admin_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "admin:panel")
async def show_admin_panel(callback: CallbackQuery, state: FSMContext):
    """Show admin panel."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    await state.clear()
    
    text = (
        "🔧 <b>Админ панель</b>\n\n"
        "Выберите действие:"
    )
    
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "admin:stats")
async def show_statistics(callback: CallbackQuery, db):
    """Show bot statistics."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    await callback.answer("📊 Загрузка статистики...")
    
    admin_service = AdminService(db)
    stats = await admin_service.get_statistics()
    
    text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"├ Всего: {stats['total_users']}\n"
        f"├ Активных (24ч): {stats['active_users_24h']}\n"
        f"└ Активных (7д): {stats['active_users_7d']}\n\n"
        f"🔫 <b>Контент:</b>\n"
        f"├ Оружие: {stats['total_weapons']}\n"
        f"├ Модули: {stats['total_modules']}\n"
        f"├ Сборки: {stats['total_builds']}\n"
        f"├ Комьюнити сборок: {stats['community_builds']}\n"
        f"└ Пользовательских сборок: {stats['user_builds']}\n\n"
        f"🌍 <b>Языки:</b>\n"
    )
    
    for lang, count in stats['language_distribution'].items():
        percentage = (count / stats['total_users'] * 100) if stats['total_users'] > 0 else 0
        text += f"├ {lang.upper()}: {count} ({percentage:.1f}%)\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:panel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "admin:broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Start broadcast creation."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    text = (
        "📢 <b>Создание рассылки</b>\n\n"
        "Выберите аудиторию для рассылки:"
    )
    
    await callback.message.edit_text(text, reply_markup=get_broadcast_type_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("broadcast:"))
async def select_broadcast_audience(callback: CallbackQuery, state: FSMContext):
    """Select broadcast audience."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    audience = callback.data.split(":")[1]
    await state.update_data(audience=audience)
    
    text = (
        "📝 <b>Настройка рассылки</b>\n\n"
        "Выберите тип контента:"
    )
    
    await callback.message.edit_text(text, reply_markup=get_broadcast_content_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "content:text_only")
async def text_only_broadcast(callback: CallbackQuery, state: FSMContext):
    """Start text-only broadcast."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    await state.update_data(has_media=False)
    await state.set_state(BroadcastStates.waiting_for_content)
    
    text = (
        "✍️ <b>Введите текст рассылки</b>\n\n"
        "Поддерживается HTML форматирование:\n"
        "• <code>&lt;b&gt;жирный&lt;/b&gt;</code>\n"
        "• <code>&lt;i&gt;курсив&lt;/i&gt;</code>\n"
        "• <code>&lt;code&gt;код&lt;/code&gt;</code>\n"
        "• <code>&lt;a href='url'&gt;ссылка&lt;/a&gt;</code>\n\n"
        "Отправьте /cancel для отмены"
    )
    
    await callback.message.edit_text(text, parse_mode="HTML")


@router.callback_query(F.data == "content:with_media")
async def with_media_broadcast(callback: CallbackQuery, state: FSMContext):
    """Start broadcast with media."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    await state.update_data(has_media=True)
    
    text = (
        "🎨 <b>Выберите тип медиа:</b>"
    )
    
    await callback.message.edit_text(text, reply_markup=get_media_type_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("media:"))
async def select_media_type(callback: CallbackQuery, state: FSMContext):
    """Select media type."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    media_type = callback.data.split(":")[1]
    await state.update_data(media_type=media_type)
    await state.set_state(BroadcastStates.waiting_for_media)
    
    media_names = {
        "photo": get_text("media_photo", "ru"),
        "video": get_text("media_video", "ru"),
        "document": get_text("media_document", "ru")
    }
    
    text = (
        f"📤 <b>Отправьте {media_names[media_type]}</b>\n\n"
        "После отправки медиа, вы сможете добавить текст.\n\n"
        "Отправьте /cancel для отмены"
    )
    
    await callback.message.edit_text(text, parse_mode="HTML")


@router.message(BroadcastStates.waiting_for_media, F.photo | F.video | F.document)
async def receive_media(message: Message, state: FSMContext):
    """Receive media for broadcast."""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    media_type = data.get("media_type")
    
    # Save media file_id
    if media_type == "photo" and message.photo:
        file_id = message.photo[-1].file_id
    elif media_type == "video" and message.video:
        file_id = message.video.file_id
    elif media_type == "document" and message.document:
        file_id = message.document.file_id
    else:
        await message.answer("❌ Неверный тип медиа. Попробуйте снова.")
        return
    
    await state.update_data(media_file_id=file_id)
    await state.set_state(BroadcastStates.waiting_for_content)
    
    text = (
        "✍️ <b>Введите текст для рассылки</b>\n\n"
        "Поддерживается HTML форматирование:\n"
        "• <code>&lt;b&gt;жирный&lt;/b&gt;</code>\n"
        "• <code>&lt;i&gt;курсив&lt;/i&gt;</code>\n"
        "• <code>&lt;code&gt;код&lt;/code&gt;</code>\n"
        "• <code>&lt;a href='url'&gt;ссылка&lt;/a&gt;</code>\n\n"
        "Можете оставить пустым, если текст не нужен.\n"
        "Отправьте /cancel для отмены"
    )
    
    await message.answer(text, parse_mode="HTML")


@router.message(BroadcastStates.waiting_for_content, F.text)
async def receive_text_content(message: Message, state: FSMContext):
    """Receive text content for broadcast."""
    if not is_admin(message.from_user.id):
        return
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Создание рассылки отменено.", reply_markup=get_admin_keyboard())
        return
    
    await state.update_data(text_content=message.text)
    await state.set_state(BroadcastStates.preview)
    
    # Show preview
    data = await state.get_data()
    await show_broadcast_preview(message, data)


async def show_broadcast_preview(message: Message, data: dict):
    """Show broadcast preview."""
    text_content = data.get("text_content", "")
    has_media = data.get("has_media", False)
    media_type = data.get("media_type")
    media_file_id = data.get("media_file_id")
    audience = data.get("audience")
    
    audience_text = "всем пользователям" if audience == "all" else "активным пользователям (7 дней)"
    
    preview_text = (
        f"👀 <b>Предпросмотр рассылки</b>\n\n"
        f"📢 Аудитория: {audience_text}\n"
        f"{'🎨 С медиа' if has_media else '📝 Без медиа'}\n\n"
        f"{'─' * 30}\n\n"
    )
    
    # Send preview
    if has_media and media_file_id:
        caption = text_content if text_content else None
        try:
            if media_type == "photo":
                await message.answer_photo(
                    photo=media_file_id,
                    caption=preview_text + (caption or "(без текста)"),
                    parse_mode="HTML"
                )
            elif media_type == "video":
                await message.answer_video(
                    video=media_file_id,
                    caption=preview_text + (caption or "(без текста)"),
                    parse_mode="HTML"
                )
            elif media_type == "document":
                await message.answer_document(
                    document=media_file_id,
                    caption=preview_text + (caption or "(без текста)"),
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"Error sending preview: {e}")
            await message.answer("❌ Ошибка при отправке предпросмотра")
            return
    else:
        await message.answer(preview_text + text_content, parse_mode="HTML")
    
    await message.answer(
        "Что делаем дальше?",
        reply_markup=get_preview_keyboard()
    )


@router.callback_query(F.data == "preview:send", BroadcastStates.preview)
async def send_broadcast(callback: CallbackQuery, state: FSMContext, db):
    """Send broadcast to users."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    data = await state.get_data()
    audience = data.get("audience")
    text_content = data.get("text_content", "")
    has_media = data.get("has_media", False)
    media_type = data.get("media_type")
    media_file_id = data.get("media_file_id")
    
    # Get user list
    admin_service = AdminService(db)
    if audience == "all":
        user_ids = await admin_service.get_all_user_ids()
    else:  # active
        user_ids = await admin_service.get_active_user_ids(days=7)
    
    await callback.message.edit_text(
        f"📤 <b>Отправка рассылки...</b>\n\nПользователей: {len(user_ids)}",
        parse_mode="HTML"
    )
    
    # Send to users
    from aiogram import Bot
    bot: Bot = callback.bot
    
    success_count = 0
    failed_count = 0
    
    for user_id in user_ids:
        try:
            if has_media and media_file_id:
                if media_type == "photo":
                    await bot.send_photo(user_id, photo=media_file_id, caption=text_content, parse_mode="HTML")
                elif media_type == "video":
                    await bot.send_video(user_id, video=media_file_id, caption=text_content, parse_mode="HTML")
                elif media_type == "document":
                    await bot.send_document(user_id, document=media_file_id, caption=text_content, parse_mode="HTML")
            else:
                await bot.send_message(user_id, text=text_content, parse_mode="HTML")
            
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to {user_id}: {e}")
            failed_count += 1
    
    await state.clear()
    
    result_text = (
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📊 Результаты:\n"
        f"├ Отправлено: {success_count}\n"
        f"└ Ошибок: {failed_count}"
    )
    
    await callback.message.edit_text(result_text, reply_markup=get_admin_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "preview:edit_text", BroadcastStates.preview)
async def edit_broadcast_text(callback: CallbackQuery, state: FSMContext):
    """Edit broadcast text."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    await state.set_state(BroadcastStates.waiting_for_content)
    
    await callback.message.answer(
        "✍️ <b>Введите новый текст рассылки:</b>\n\n"
        "Отправьте /cancel для отмены",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "preview:edit_media", BroadcastStates.preview)
async def edit_broadcast_media(callback: CallbackQuery, state: FSMContext):
    """Edit broadcast media."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    await state.set_state(BroadcastStates.waiting_for_media)
    
    data = await state.get_data()
    media_type = data.get("media_type", "photo")
    
    media_names = {
        "photo": get_text("media_photo", "ru"),
        "video": get_text("media_video", "ru"),
        "document": get_text("media_document", "ru")
    }
    
    await callback.message.answer(
        f"📤 <b>Отправьте новое {media_names[media_type]}:</b>\n\n"
        "Отправьте /cancel для отмены",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin:close")
async def close_admin_panel(callback: CallbackQuery):
    """Close admin panel."""
    await callback.message.delete()
    await callback.answer("✅ Панель закрыта")


@router.message(Command("cancel"))
async def cancel_broadcast(message: Message, state: FSMContext):
    """Cancel broadcast creation."""
    if not is_admin(message.from_user.id):
        return
    
    current_state = await state.get_state()
    if current_state is None:
        return
    
    await state.clear()
    await message.answer(
        "❌ Действие отменено.",
        reply_markup=get_admin_keyboard()
    )
