"""
Owner Panel - Расширенная админ-панель для ВЛАДЕЛЬЦА бота.

Функции:
- Авторизация по OWNER_ID из .env
- Управление функциями бота (вкл/выкл модулей)
- Рассылка сообщений
- Статус системы
- Глобальные настройки
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func

from app.config import settings
from app.database.session import get_session
from app.database.models import Chat, User, PrivateChat

logger = logging.getLogger(__name__)

router = Router()


# ============================================================================
# Состояние функций бота (runtime, сбрасывается при перезапуске)
# ============================================================================

class BotFeatures:
    """Управление функциями бота в runtime."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_features()
        return cls._instance
    
    def _init_features(self):
        """Инициализация состояния функций из настроек."""
        self.features: Dict[str, bool] = {
            "voice_recognition": settings.voice_recognition_enabled,
            "content_download": settings.content_download_enabled,
            "toxicity_analysis": settings.toxicity_analysis_enabled,
            "rate_limit": settings.rate_limit_enabled,
            "web_search": settings.ollama_web_search_enabled,
            "games": True,  # Игры всегда включены по умолчанию
            "vision": True,  # Анализ изображений
            "random_responses": True,  # Случайные ответы
            "summarizer": True,  # Пересказ контента
        }
    
    def toggle(self, feature: str) -> bool:
        """Переключить функцию. Возвращает новое состояние."""
        if feature in self.features:
            self.features[feature] = not self.features[feature]
            return self.features[feature]
        return False
    
    def get(self, feature: str) -> bool:
        """Получить состояние функции."""
        return self.features.get(feature, False)
    
    def set(self, feature: str, value: bool):
        """Установить состояние функции."""
        if feature in self.features:
            self.features[feature] = value
    
    def get_all(self) -> Dict[str, bool]:
        """Получить все функции."""
        return self.features.copy()


# Глобальный экземпляр
bot_features = BotFeatures()


# ============================================================================
# Названия функций
# ============================================================================

FEATURE_NAMES = {
    "voice_recognition": "🎤 Распознавание голоса",
    "content_download": "📥 Загрузка контента",
    "rate_limit": "⏱ Rate Limiting",
    "web_search": "🌐 Веб-поиск",
    "games": "🎮 Игры",
    "vision": "👁 Анализ изображений",
    "random_responses": "🎲 Случайные ответы",
    "summarizer": "📝 Пересказ контента",
}


# ============================================================================
# FSM States
# ============================================================================

class OwnerStates(StatesGroup):
    """FSM состояния для панели владельца."""
    waiting_broadcast_text = State()  # Legacy, now accepts any content
    waiting_broadcast_confirm = State()
    waiting_broadcast_content = State()  # New: any content type
    waiting_voice_percent = State()  # Ввод процента для голоса
    waiting_video_percent = State()  # Ввод процента для видео


# ============================================================================
# Проверка владельца
# ============================================================================

def is_owner(user_id: int) -> bool:
    """
    Проверка, является ли пользователь владельцем бота или SDOC.
    
    Доступ к админке имеют:
    - Owner бота (OWNER_ID из .env)
    - Владелец SDOC (SDOC_OWNER_ID из .env)
    """
    if user_id == settings.owner_id:
        return True
    if user_id == settings.sdoc_owner_id:
        return True
    return False


# ============================================================================
# Главное меню владельца
# ============================================================================


# ============================================================================
# Команда /owner - главная точка входа
# ============================================================================

@router.message(Command("owner"))
async def cmd_owner(msg: Message):
    """
    /owner - панель владельца бота.
    Доступна только пользователю с OWNER_ID из .env
    """
    if msg.chat.type != 'private':
        await msg.reply("🔒 Панель владельца доступна только в личных сообщениях.")
        return
    
    if not is_owner(msg.from_user.id):
        await msg.answer("⛔ Доступ запрещён. Эта команда только для владельца бота.")
        logger.warning(f"Unauthorized /owner access attempt by user {msg.from_user.id}")
        return
    
    kb = build_owner_main_menu()
    
    await msg.answer(
        "👑 <b>Панель владельца</b>\n\n"
        f"Привет, босс! ID: <code>{msg.from_user.id}</code>\n\n"
        "Выбери раздел:",
        reply_markup=kb.as_markup()
    )


# ============================================================================
# Возврат в главное меню
# ============================================================================

@router.callback_query(F.data == "owner_main")
async def cb_owner_main(callback: CallbackQuery):
    """Возврат в главное меню владельца."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = build_owner_main_menu()
    
    await callback.message.edit_text(
        "👑 <b>Панель владельца</b>\n\n"
        f"ID: <code>{callback.from_user.id}</code>\n\n"
        "Выбери раздел:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


# ============================================================================
# Управление функциями
# ============================================================================

def build_features_menu() -> InlineKeyboardBuilder:
    """Построить меню функций."""
    kb = InlineKeyboardBuilder()
    
    features = bot_features.get_all()
    
    for feature_id, enabled in features.items():
        name = FEATURE_NAMES.get(feature_id, feature_id)
        status = "✅" if enabled else "❌"
        kb.button(
            text=f"{status} {name}",
            callback_data=f"owner_toggle_{feature_id}"
        )
    
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(1)
    return kb


@router.callback_query(F.data == "owner_features")
async def cb_owner_features(callback: CallbackQuery):
    """Показать меню управления функциями."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = build_features_menu()
    
    await callback.message.edit_text(
        "⚙️ <b>Управление функциями</b>\n\n"
        "Нажми на функцию, чтобы включить/выключить.\n"
        "✅ = включено, ❌ = выключено\n\n"
        "⚠️ Изменения действуют до перезапуска бота.",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("owner_toggle_"))
async def cb_toggle_feature(callback: CallbackQuery):
    """Переключить функцию."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    feature_id = callback.data.replace("owner_toggle_", "")
    new_state = bot_features.toggle(feature_id)
    
    feature_name = FEATURE_NAMES.get(feature_id, feature_id)
    status = "включена ✅" if new_state else "выключена ❌"
    
    await callback.answer(f"{feature_name} {status}", show_alert=True)
    
    # Обновить меню
    kb = build_features_menu()
    await callback.message.edit_reply_markup(reply_markup=kb.as_markup())


# ============================================================================
# Статус системы
# ============================================================================

@router.callback_query(F.data == "owner_status")
async def cb_owner_status(callback: CallbackQuery, bot: Bot):
    """Показать статус системы."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer("Загружаю статус...", show_alert=False)
    
    # Собираем статистику
    async with get_session()() as session:
        # Количество чатов
        chats_count = await session.scalar(select(func.count(Chat.id)))
        
        # Количество пользователей
        users_count = await session.scalar(select(func.count(User.id)))
        
        # Количество приватных чатов
        private_count = await session.scalar(
            select(func.count(PrivateChat.user_id))
            .where(PrivateChat.is_blocked == False)
        )
    
    # Проверка сервисов
    services_status = []
    has_critical_issues = False
    
    # Ollama - реальная проверка доступности
    try:
        from app.services.ollama_client import is_ollama_available, check_model_available
        ollama_ok = await is_ollama_available()
        if ollama_ok:
            # Проверяем основную модель
            model_ok = await check_model_available(settings.ollama_base_model)
            if model_ok:
                services_status.append(f"✅ Ollama ({settings.ollama_base_model})")
            else:
                # Проверяем fallback
                if settings.ollama_fallback_enabled:
                    fallback_ok = await check_model_available(settings.ollama_fallback_model)
                    if fallback_ok:
                        services_status.append(f"⚠️ Ollama (fallback: {settings.ollama_fallback_model})")
                    else:
                        services_status.append("❌ Ollama (модели недоступны)")
                        has_critical_issues = True
                else:
                    services_status.append(f"❌ Ollama (модель {settings.ollama_base_model} недоступна)")
                    has_critical_issues = True
        else:
            services_status.append("❌ Ollama (сервер недоступен)")
            has_critical_issues = True
    except Exception as e:
        services_status.append(f"❌ Ollama ({e})")
        has_critical_issues = True
    
    # Redis
    if settings.redis_enabled:
        try:
            from app.services.redis_client import redis_client
            if redis_client._client:
                services_status.append("✅ Redis")
            else:
                services_status.append("⚠️ Redis (не подключен)")
        except Exception:
            services_status.append("❌ Redis")
    else:
        services_status.append("⏸ Redis (отключен)")
    
    # ChromaDB
    try:
        from app.services.vector_db import vector_db
        if vector_db.client:
            # Пробуем сделать heartbeat запрос
            try:
                vector_db.client.heartbeat()
                services_status.append("✅ ChromaDB")
            except Exception:
                services_status.append("⚠️ ChromaDB (нет связи)")
                has_critical_issues = True
        else:
            services_status.append("⚠️ ChromaDB (не инициализирован)")
            has_critical_issues = True
    except Exception as e:
        services_status.append(f"❌ ChromaDB ({e})")
        has_critical_issues = True
    
    # Whisper (faster-whisper)
    if settings.voice_recognition_enabled:
        try:
            from app.services.voice_recognition import is_available
            if is_available():
                services_status.append("✅ Whisper")
            else:
                services_status.append("⚠️ Whisper (не загружен)")
        except Exception:
            services_status.append("❌ Whisper")
    else:
        services_status.append("⏸ Whisper (отключен)")
    
    # Формируем текст
    text = (
        "📊 <b>Статус системы</b>\n\n"
        f"<b>Статистика:</b>\n"
        f"├ Групп: {chats_count or 0}\n"
        f"├ Пользователей: {users_count or 0}\n"
        f"└ Приватных чатов: {private_count or 0}\n\n"
        f"<b>Сервисы:</b>\n"
    )
    
    for status in services_status:
        text += f"├ {status}\n"
    
    # Определяем используется ли fallback
    using_fallback = False
    try:
        from app.services.ollama_client import check_model_available
        primary_ok = await check_model_available(settings.ollama_base_model)
        if not primary_ok and settings.ollama_fallback_enabled:
            fallback_ok = await check_model_available(settings.ollama_fallback_model)
            if fallback_ok:
                using_fallback = True
    except Exception:
        pass
    
    # Текущий режим работы
    if using_fallback:
        text += f"\n🔄 <b>РЕЖИМ: FALLBACK</b>\n"
        text += f"├ Используется: {settings.ollama_fallback_model}\n"
        text += f"└ Основная недоступна: {settings.ollama_base_model}\n"
    else:
        text += f"\n✅ <b>РЕЖИМ: ОСНОВНОЙ</b>\n"
        text += f"└ Используется: {settings.ollama_base_model}\n"
    
    text += f"\n<b>Настроенные модели:</b>\n"
    text += f"├ Base: {settings.ollama_base_model}\n"
    text += f"├ Vision: {settings.ollama_vision_model}\n"
    text += f"└ Memory: {settings.ollama_memory_model}\n"
    
    if settings.ollama_fallback_enabled:
        text += f"\n<b>Fallback модели (резерв):</b>\n"
        text += f"├ Base: {settings.ollama_fallback_model}\n"
        text += f"├ Vision: {settings.ollama_fallback_vision_model}\n"
        text += f"└ Memory: {settings.ollama_fallback_memory_model}\n"
    else:
        text += f"\n⏸ <b>Fallback отключен</b>\n"
    
    # Предупреждение о критических проблемах
    if has_critical_issues:
        text += "\n⚠️ <b>Есть критические проблемы!</b>"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Обновить", callback_data="owner_status")
    if has_critical_issues:
        kb.button(text="🔔 Тест уведомления", callback_data="owner_test_notify")
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(2)
    
    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        # Игнорируем ошибку "message is not modified"
        await callback.answer("Статус не изменился", show_alert=False)


@router.callback_query(F.data == "owner_test_notify")
async def cb_owner_test_notify(callback: CallbackQuery):
    """Тестовое уведомление о проблемах."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    try:
        from app.services.ollama_client import notify_owner_service_down
        await notify_owner_service_down("Тест", "Это тестовое уведомление о проблемах с сервисами")
        await callback.answer("✅ Уведомление отправлено!", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# ============================================================================
# Управление чатами
# ============================================================================

@router.callback_query(F.data == "owner_chats")
async def cb_owner_chats(callback: CallbackQuery, bot: Bot):
    """Показать список чатов."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    async with get_session()() as session:
        result = await session.execute(
            select(Chat).order_by(Chat.created_at.desc()).limit(20)
        )
        chats = result.scalars().all()
    
    if not chats:
        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 Назад", callback_data="owner_main")
        
        await callback.message.edit_text(
            "💬 <b>Чаты</b>\n\nНет подключенных чатов.",
            reply_markup=kb.as_markup()
        )
        await callback.answer()
        return
    
    kb = InlineKeyboardBuilder()
    
    for chat in chats:
        title = chat.title[:25] + "..." if len(chat.title) > 25 else chat.title
        kb.button(text=f"💬 {title}", callback_data=f"owner_chat_{chat.id}")
    
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(1)
    
    await callback.message.edit_text(
        f"💬 <b>Управление чатами</b>\n\n"
        f"Всего чатов: {len(chats)}\n"
        f"Выбери чат для управления:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("owner_chat_"))
async def cb_owner_chat_detail(callback: CallbackQuery, bot: Bot):
    """Детали чата."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[2])
    
    async with get_session()() as session:
        chat = await session.get(Chat, chat_id)
    
    if not chat:
        await callback.answer("Чат не найден", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🚪 Покинуть чат", callback_data=f"owner_leavechat:{chat_id}")
    kb.button(text="🔙 К списку", callback_data="owner_chats")
    kb.adjust(1)
    
    text = (
        f"💬 <b>{chat.title}</b>\n\n"
        f"ID: <code>{chat.id}</code>\n"
        f"Тип: {'Форум' if chat.is_forum else 'Группа'}\n"
        f"Добавлен: {chat.created_at.strftime('%d.%m.%Y') if chat.created_at else 'N/A'}\n"
    )
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("owner_leavechat:"))
async def cb_owner_leave_chat(callback: CallbackQuery, bot: Bot):
    """Покинуть чат."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split(":")[1])
    
    try:
        await bot.leave_chat(chat_id)
        
        # Удалить из БД
        async with get_session()() as session:
            chat = await session.get(Chat, chat_id)
            if chat:
                await session.delete(chat)
                await session.commit()
        
        await callback.answer("✅ Бот покинул чат", show_alert=True)
        
        # Вернуться к списку
        await cb_owner_chats(callback, bot)
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)


# ============================================================================
# Рассылка (интеграция с broadcast)
# ============================================================================

@router.callback_query(F.data == "owner_broadcast")
async def cb_owner_broadcast(callback: CallbackQuery, state: FSMContext):
    """Меню рассылки."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 В ЛС бота", callback_data="owner_bc_target_private")
    kb.button(text="👥 В группы", callback_data="owner_bc_target_groups")
    kb.button(text="🌍 Везде", callback_data="owner_bc_target_all")
    kb.button(text="📢 Полный мастер", callback_data="owner_bc_wizard")
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(3, 1, 1)
    
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "Выбери куда отправить:\n\n"
        "• <b>В ЛС бота</b> - пользователям, которые писали боту\n"
        "• <b>В группы</b> - во все группы где есть бот\n"
        "• <b>Везде</b> - и в ЛС, и в группы\n\n"
        "После выбора просто отправь контент (текст/фото/видео/кружочек/GIF)",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("owner_bc_target_"))
async def cb_owner_bc_target(callback: CallbackQuery, state: FSMContext):
    """Выбор цели рассылки."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    target = callback.data.replace("owner_bc_target_", "")
    await state.update_data(broadcast_target=target)
    await state.set_state(OwnerStates.waiting_broadcast_content)
    
    target_labels = {
        "private": "👤 в ЛС бота",
        "groups": "👥 в группы",
        "all": "🌍 везде"
    }
    
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data="owner_broadcast")
    
    await callback.message.edit_text(
        f"📢 <b>Рассылка</b>\n\n"
        f"Цель: {target_labels.get(target, target)}\n\n"
        "Отправь контент для рассылки:\n"
        "• Текст\n"
        "• Фото (с подписью)\n"
        "• Видео (с подписью)\n"
        "• Кружочек\n"
        "• GIF",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.message(OwnerStates.waiting_broadcast_content)
async def handle_broadcast_content(msg: Message, state: FSMContext, bot: Bot):
    """Обработка любого контента для рассылки."""
    if not is_owner(msg.from_user.id):
        return
    
    # Auto-detect content type
    content_type = None
    content_data = None
    caption = None
    file_id = None
    
    if msg.video_note:
        content_type = "video_note"
        file_id = msg.video_note.file_id
    elif msg.video:
        content_type = "video"
        file_id = msg.video.file_id
        caption = msg.caption
    elif msg.animation:
        content_type = "animation"
        file_id = msg.animation.file_id
        caption = msg.caption
    elif msg.photo:
        content_type = "photo"
        file_id = msg.photo[-1].file_id
        caption = msg.caption
    elif msg.text:
        content_type = "text"
        content_data = msg.text
    else:
        await msg.reply("❌ Отправь текст, фото, видео, кружочек или GIF.")
        return
    
    data = await state.get_data()
    target = data.get("broadcast_target", "groups")
    
    await state.update_data(
        broadcast_content_type=content_type,
        broadcast_text=content_data,
        broadcast_file_id=file_id,
        broadcast_caption=caption
    )
    await state.set_state(OwnerStates.waiting_broadcast_confirm)
    
    # Получить количество получателей в зависимости от цели
    async with get_session()() as session:
        groups_count = await session.scalar(select(func.count(Chat.id)))
        private_count = await session.scalar(
            select(func.count(PrivateChat.user_id))
            .where(PrivateChat.is_blocked == False)
        )
    
    if target == "private":
        recipients_text = f"{private_count or 0} пользователей (ЛС)"
    elif target == "groups":
        recipients_text = f"{groups_count or 0} групп"
    else:  # all
        recipients_text = f"{(private_count or 0) + (groups_count or 0)} ({private_count or 0} ЛС + {groups_count or 0} групп)"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 Отправить", callback_data="owner_bc_send")
    kb.button(text="❌ Отмена", callback_data="owner_broadcast")
    kb.adjust(2)
    
    # Build preview based on content type
    type_labels = {
        "text": "�� Текст",
        "photo": "🖼 Фото",
        "video": "🎬 Видео",
        "video_note": "⚪ Кружочек",
        "animation": "🎞 GIF"
    }
    type_label = type_labels.get(content_type, content_type)
    
    if content_type == "text":
        preview = content_data[:300] + "..." if len(content_data) > 300 else content_data
        preview_text = f"<b>Текст:</b>\n{preview}"
    elif caption:
        preview_text = f"<b>Тип:</b> {type_label}\n<b>Подпись:</b> {caption[:200]}"
    else:
        preview_text = f"<b>Тип:</b> {type_label}"
    
    await msg.answer(
        f"📢 <b>Подтверждение рассылки</b>\n\n"
        f"{preview_text}\n\n"
        f"<b>Получатели:</b> {recipients_text}\n\n"
        f"Подтвердить отправку?",
        reply_markup=kb.as_markup()
    )


@router.callback_query(F.data == "owner_bc_send")
async def cb_owner_bc_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Отправить рассылку."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    data = await state.get_data()
    text = data.get("broadcast_text")
    target = data.get("broadcast_target", "groups")
    
    if not text:
        await callback.answer("❌ Текст не найден", show_alert=True)
        await state.clear()
        return
    
    await callback.answer("🚀 Отправка...", show_alert=False)
    
    await callback.message.edit_text("📢 <b>Рассылка в процессе...</b>\n\n⏳ Подождите...")
    
    # Получить ID получателей в зависимости от цели
    chat_ids = []
    async with get_session()() as session:
        if target in ("groups", "all"):
            result = await session.execute(select(Chat.id))
            chat_ids.extend([row[0] for row in result.all()])
        
        if target in ("private", "all"):
            result = await session.execute(
                select(PrivateChat.user_id).where(PrivateChat.is_blocked == False)
            )
            chat_ids.extend([row[0] for row in result.all()])
    
    sent = 0
    failed = 0
    
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id=chat_id, text=text)
            sent += 1
        except Exception as e:
            logger.warning(f"Failed to send broadcast to {chat_id}: {e}")
            failed += 1
        
        await asyncio.sleep(0.05)  # Flood protection
    
    await state.clear()
    
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 Ещё рассылка", callback_data="owner_broadcast")
    kb.button(text="🔙 Главное меню", callback_data="owner_main")
    kb.adjust(2)
    
    await callback.message.edit_text(
        f"📢 <b>Рассылка завершена!</b>\n\n"
        f"✅ Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}\n"
        f"📊 Всего: {sent + failed}",
        reply_markup=kb.as_markup()
    )


@router.callback_query(F.data == "owner_bc_wizard")
async def cb_owner_bc_wizard(callback: CallbackQuery):
    """Перенаправление на полный мастер рассылки."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📢 <b>Полный мастер рассылки</b>\n\n"
        "Используй команду /broadcast для запуска пошагового мастера "
        "с выбором типа контента (текст, фото, видео, кружочек)."
    )
    await callback.answer()


# ============================================================================
# Настройки
# ============================================================================

@router.callback_query(F.data == "owner_settings")
async def cb_owner_settings(callback: CallbackQuery):
    """Показать настройки."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🛡️ Антиспам", callback_data="owner_antispam")
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(1)
    
    text = (
        "🔧 <b>Текущие настройки</b>\n\n"
        f"<b>Telegram:</b>\n"
        f"├ Owner ID: <code>{settings.owner_id}</code>\n\n"
        f"<b>Ollama:</b>\n"
        f"├ URL: {settings.ollama_base_url}\n"
        f"├ Модель: {settings.ollama_base_model}\n"
        f"├ Vision: {settings.ollama_vision_model}\n"
        f"├ Memory: {settings.ollama_memory_model}\n"
        f"├ Timeout: {settings.ollama_timeout}s\n\n"
        f"<b>Лимиты:</b>\n"
        f"├ Rate limit: {settings.rate_limit_requests}/{settings.rate_limit_window}s\n\n"
        f"<b>Медиа:</b>\n"
        f"├ Whisper: {settings.whisper_model}\n"
        f"├ Голос: {'✅' if settings.voice_recognition_enabled else '❌'}\n"
        f"├ Загрузка: {'✅' if settings.content_download_enabled else '❌'}\n\n"
        f"Нажми <b>Антиспам</b> для настройки лимитов запросов."
    )
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# ============================================================================
# Persona Management
# ============================================================================

@router.callback_query(F.data == "owner_persona_menu")
async def cb_owner_persona_menu(callback: CallbackQuery, bot: Bot):
    """Меню управления персоной Олега."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    # Load personas from JSON
    import json
    from pathlib import Path
    
    personas_path = Path("app/data/personas.json")
    try:
        with open(personas_path, "r", encoding="utf-8") as f:
            personas_data = json.load(f)
            personas = personas_data.get("personas", {})
    except Exception as e:
        logger.error(f"Failed to load personas: {e}")
        await callback.answer("Ошибка загрузки персон", show_alert=True)
        return
    
    # Get current persona for SDOC chat
    current_persona = "oleg"  # default
    if settings.sdoc_chat_id:
        async with get_session()() as session:
            chat = await session.get(Chat, settings.sdoc_chat_id)
            if chat:
                current_persona = chat.persona
    
    kb = InlineKeyboardBuilder()
    
    # Sort personas: oleg and oleg_legacy first, then others
    priority_personas = ["oleg", "oleg_legacy"]
    other_personas = [p for p in personas.keys() if p not in priority_personas]
    sorted_personas = priority_personas + sorted(other_personas)
    
    for persona_id in sorted_personas:
        if persona_id not in personas:
            continue
        persona_info = personas[persona_id]
        is_current = "✅ " if persona_id == current_persona else ""
        kb.button(
            text=f"{is_current}{persona_info['name']}", 
            callback_data=f"owner_set_persona:{persona_id}"
        )
    
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(2, 2, 2, 2, 1, 1)  # 2 per row for main personas, then others
    
    text = (
        "🎭 <b>Персона Олега</b>\n\n"
        f"Текущая: <b>{personas.get(current_persona, {}).get('name', 'Unknown')}</b>\n\n"
        "<b>Основные персоны:</b>\n"
        f"{'✅' if current_persona == 'oleg' else '○'} <b>Олег (Default)</b> — дерзкий техно-чувак\n"
        f"{'✅' if current_persona == 'oleg_legacy' else '○'} <b>Олег Кузнецов (Legacy)</b> — живой человек с сетапом\n\n"
        "<b>Альтернативные:</b>\n"
    )
    
    for persona_id in other_personas:
        if persona_id not in personas:
            continue
        persona_info = personas[persona_id]
        marker = "✅" if persona_id == current_persona else "○"
        text += f"{marker} {persona_info['name']}\n"
    
    text += "\n<i>Выбери персону для изменения личности Олега</i>"
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# ============================================================================
# Антиспам настройки
# ============================================================================

@router.callback_query(F.data == "owner_antispam")
async def cb_owner_antispam(callback: CallbackQuery):
    """Меню настроек антиспама."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    from app.services.token_limiter import token_limiter
    
    stats = token_limiter.get_stats()
    
    kb = InlineKeyboardBuilder()
    # Burst лимит
    kb.button(text="➖", callback_data="owner_as_burst_dec")
    kb.button(text=f"⚡ Burst: {stats['burst_limit']}/мин", callback_data="owner_as_noop")
    kb.button(text="➕", callback_data="owner_as_burst_inc")
    # Часовой лимит
    kb.button(text="➖", callback_data="owner_as_hourly_dec")
    kb.button(text=f"⏱ Час: {stats['hourly_limit']}/час", callback_data="owner_as_noop")
    kb.button(text="➕", callback_data="owner_as_hourly_inc")
    # Действия
    kb.button(text="🔄 Сбросить статистику", callback_data="owner_as_reset_stats")
    kb.button(text="🔙 Назад", callback_data="owner_settings")
    kb.adjust(3, 3, 1, 1)
    
    text = (
        "🛡️ <b>Настройки антиспама</b>\n\n"
        f"<b>Текущие лимиты:</b>\n"
        f"├ ⚡ Burst: <b>{stats['burst_limit']}</b> запросов/минуту\n"
        f"└ ⏱ Часовой: <b>{stats['hourly_limit']}</b> запросов/час\n\n"
        f"<b>Статистика:</b>\n"
        f"├ Пользователей: {stats['total_users']}\n"
        f"├ В whitelist: {stats['whitelisted']}\n"
        f"└ Заблокировано: {stats['total_blocked']}\n\n"
        "Используй ➖/➕ для изменения лимитов."
    )
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "owner_as_noop")
async def cb_owner_as_noop(callback: CallbackQuery):
    """Пустой callback для кнопок-индикаторов."""
    await callback.answer()


@router.callback_query(F.data == "owner_as_burst_dec")
async def cb_owner_as_burst_dec(callback: CallbackQuery):
    """Уменьшить burst лимит."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    from app.services.token_limiter import token_limiter
    
    new_limit = max(1, token_limiter.burst_limit - 1)
    token_limiter.set_burst_limit(new_limit)
    await callback.answer(f"Burst: {new_limit}/мин")
    await cb_owner_antispam(callback)


@router.callback_query(F.data == "owner_as_burst_inc")
async def cb_owner_as_burst_inc(callback: CallbackQuery):
    """Увеличить burst лимит."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    from app.services.token_limiter import token_limiter
    
    new_limit = min(30, token_limiter.burst_limit + 1)
    token_limiter.set_burst_limit(new_limit)
    await callback.answer(f"Burst: {new_limit}/мин")
    await cb_owner_antispam(callback)


@router.callback_query(F.data == "owner_as_hourly_dec")
async def cb_owner_as_hourly_dec(callback: CallbackQuery):
    """Уменьшить часовой лимит."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    from app.services.token_limiter import token_limiter
    
    new_limit = max(10, token_limiter.hourly_limit - 10)
    token_limiter.set_hourly_limit(new_limit)
    await callback.answer(f"Часовой: {new_limit}/час")
    await cb_owner_antispam(callback)


@router.callback_query(F.data == "owner_as_hourly_inc")
async def cb_owner_as_hourly_inc(callback: CallbackQuery):
    """Увеличить часовой лимит."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    from app.services.token_limiter import token_limiter
    
    new_limit = min(500, token_limiter.hourly_limit + 10)
    token_limiter.set_hourly_limit(new_limit)
    await callback.answer(f"Часовой: {new_limit}/час")
    await cb_owner_antispam(callback)


@router.callback_query(F.data == "owner_as_reset_stats")
async def cb_owner_as_reset_stats(callback: CallbackQuery):
    """Сбросить статистику антиспама."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    from app.services.token_limiter import token_limiter
    
    token_limiter.users.clear()
    token_limiter.total_blocked = 0
    
    await callback.answer("✅ Статистика сброшена!", show_alert=True)
    await cb_owner_antispam(callback)


# ============================================================================
# Экспорт функции проверки состояния функций
# ============================================================================

def is_feature_enabled(feature: str) -> bool:
    """
    Проверить, включена ли функция.
    Используется в других модулях для проверки состояния.
    """
    return bot_features.get(feature)


# ============================================================================
# Экстренные действия
# ============================================================================

@router.callback_query(F.data == "owner_emergency")
async def cb_owner_emergency(callback: CallbackQuery):
    """Экстренные действия."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔴 Выключить все функции", callback_data="owner_em_disable_all")
    kb.button(text="🟢 Включить все функции", callback_data="owner_em_enable_all")
    kb.button(text="🗑 Вайп (выборочный)", callback_data="owner_wipe_menu")
    kb.button(text="🔄 Перезапуск бота", callback_data="owner_em_restart")
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "🚨 <b>Экстренные действия</b>\n\n"
        "⚠️ Используй с осторожностью!",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "owner_em_disable_all")
async def cb_disable_all_features(callback: CallbackQuery):
    """Выключить все функции."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    for feature in bot_features.features:
        bot_features.set(feature, False)
    
    await callback.answer("🔴 Все функции выключены!", show_alert=True)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🟢 Включить все", callback_data="owner_em_enable_all")
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "🔴 <b>Все функции выключены</b>\n\n"
        "Бот работает в минимальном режиме.",
        reply_markup=kb.as_markup()
    )


@router.callback_query(F.data == "owner_em_enable_all")
async def cb_enable_all_features(callback: CallbackQuery):
    """Включить все функции."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    for feature in bot_features.features:
        bot_features.set(feature, True)
    
    await callback.answer("🟢 Все функции включены!", show_alert=True)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад", callback_data="owner_main")
    
    await callback.message.edit_text(
        "🟢 <b>Все функции включены</b>\n\n"
        "Бот работает в полном режиме.",
        reply_markup=kb.as_markup()
    )


@router.callback_query(F.data == "owner_em_restart")
async def cb_owner_restart(callback: CallbackQuery):
    """Перезапуск бота."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, перезапустить", callback_data="owner_em_restart_confirm")
    kb.button(text="❌ Отмена", callback_data="owner_main")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "⚠️ <b>Подтверждение перезапуска</b>\n\n"
        "Бот будет перезапущен.\n"
        "Все текущие операции будут прерваны.\n\n"
        "Продолжить?",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "owner_em_restart_confirm")
async def cb_owner_restart_confirm(callback: CallbackQuery):
    """Подтверждение перезапуска."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔄 <b>Перезапуск бота...</b>\n\n"
        "Бот будет недоступен несколько секунд."
    )
    await callback.answer("Перезапуск инициирован", show_alert=True)
    
    logger.warning(f"Bot restart requested by owner {callback.from_user.id}")
    
    import sys
    sys.exit(0)


# ============================================================================
# ВАЙП ПАМЯТИ И БАЗЫ ДАННЫХ
# ============================================================================

@router.callback_query(F.data == "owner_wipe_confirm")
async def cb_owner_wipe_confirm(callback: CallbackQuery):
    """Перенаправление на меню выборочного вайпа."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    # Перенаправляем на новое меню вайпа
    await cb_owner_wipe_menu(callback)


@router.callback_query(F.data == "owner_wipe_execute")
async def cb_owner_wipe_execute(callback: CallbackQuery):
    """Выполнение вайпа."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    # Сразу отвечаем на callback чтобы не протух
    await callback.answer("⏳ Выполняется...")
    
    await callback.message.edit_text("🗑 <b>Выполняется вайп...</b>\n\n⏳ Подождите...")
    
    results = []
    
    # 1. Очистка ChromaDB (память)
    try:
        from app.services.vector_db import vector_db
        if vector_db.client:
            # Получаем все коллекции и удаляем их
            collections = vector_db.client.list_collections()
            for col in collections:
                vector_db.client.delete_collection(col.name)
            results.append(f"✅ ChromaDB: удалено {len(collections)} коллекций")
        else:
            results.append("⚠️ ChromaDB: не инициализирована")
    except Exception as e:
        results.append(f"❌ ChromaDB: {str(e)[:50]}")
    
    # 2. Очистка базы данных
    try:
        from app.database.session import get_session
        from app.database.models import (
            User, MessageLog, GameStat, Wallet, Achievement, UserAchievement,
            TradeOffer, Auction, Bid, Quest, UserQuest, Guild, GuildMember,
            TeamWar, TeamWarParticipant, DuoTeam, DuoStat, GlobalStats,
            UserQuestionHistory, Chat, Admin, PrivateChat,
            PendingVerification, GameChallenge, UserBalance,
            Tournament, TournamentScore,
            UserElo, NotificationConfig
        )
        from sqlalchemy import delete
        
        async with get_session()() as session:
            # Порядок важен из-за foreign keys
            tables_to_clear = [
                (TournamentScore, "TournamentScore"),
                (Tournament, "Tournament"),
                (NotificationConfig, "NotificationConfig"),
                (UserBalance, "UserBalance"),
                (GameChallenge, "GameChallenge"),
                (PendingVerification, "PendingVerification"),
                (PrivateChat, "PrivateChat"),
                (Admin, "Admin"),
                (UserQuestionHistory, "UserQuestionHistory"),
                (GlobalStats, "GlobalStats"),
                (DuoStat, "DuoStat"),
                (DuoTeam, "DuoTeam"),
                (TeamWarParticipant, "TeamWarParticipant"),
                (TeamWar, "TeamWar"),
                (GuildMember, "GuildMember"),
                (Guild, "Guild"),
                (UserQuest, "UserQuest"),
                (Quest, "Quest"),
                (Bid, "Bid"),
                (Auction, "Auction"),
                (TradeOffer, "TradeOffer"),
                (UserAchievement, "UserAchievement"),
                (Achievement, "Achievement"),
                (Wallet, "Wallet"),
                (GameStat, "GameStat"),
                (MessageLog, "MessageLog"),
                (StickerPack, "StickerPack"),
                (Chat, "Chat"),
                (User, "User"),
                (UserElo, "UserElo"),
            ]
            
            deleted_count = 0
            for model, name in tables_to_clear:
                try:
                    result = await session.execute(delete(model))
                    deleted_count += result.rowcount
                except Exception as e:
                    logger.warning(f"Ошибка при очистке {name}: {e}")
            
            await session.commit()
            results.append(f"✅ База данных: очищено {len(tables_to_clear)} таблиц")
            
    except Exception as e:
        results.append(f"❌ База данных: {str(e)[:50]}")
        logger.error(f"Ошибка при вайпе БД: {e}")
    
    # 3. Восстановление дефолтных знаний
    try:
        from app.services.vector_db import vector_db
        from app.config import settings
        
        if vector_db.client:
            # Переинициализируем коллекцию
            collection_name = settings.chromadb_collection_name
            load_result = vector_db.load_default_knowledge(collection_name)
            
            if load_result.get("error"):
                results.append(f"⚠️ Дефолтные знания: {load_result['error']}")
            else:
                results.append(f"✅ Дефолтные знания: загружено {load_result['loaded']} фактов (v{load_result.get('version', '?')})")
        else:
            results.append("⚠️ Дефолтные знания: ChromaDB не инициализирована")
    except Exception as e:
        results.append(f"❌ Дефолтные знания: {str(e)[:50]}")
    
    logger.warning(f"WIPE executed by owner {callback.from_user.id}")
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад", callback_data="owner_main")
    
    await callback.message.edit_text(
        "🗑 <b>ВАЙП ЗАВЕРШЁН</b>\n\n"
        "<b>Результаты:</b>\n" +
        "\n".join(results) +
        "\n\n✅ Бот готов к работе с чистого листа!\n"
        "📚 Дефолтные знания восстановлены.",
        reply_markup=kb.as_markup()
    )


# ============================================================================
# Список групп и топ пользователей
# ============================================================================

# Хранилище замученных групп (в памяти, сбрасывается при перезапуске)
_muted_groups: set[int] = set()


def is_group_muted(chat_id: int) -> bool:
    """Проверить, замучена ли группа."""
    return chat_id in _muted_groups


@router.callback_query(F.data == "owner_groups_list")
async def cb_owner_groups_list(callback: CallbackQuery):
    """Показать список всех групп где есть бот."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    async_session = get_session()
    async with async_session() as session:
        # Получаем все чаты
        result = await session.execute(select(Chat))
        chats = result.scalars().all()
    
    if not chats:
        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 Назад", callback_data="owner_main")
        await callback.message.edit_text(
            "📭 Бот пока не добавлен ни в одну группу",
            reply_markup=kb.as_markup()
        )
        await callback.answer()
        return
    
    text = f"👥 <b>Список групп ({len(chats)})</b>\n\n"
    text += "Нажми на группу для управления:\n\n"
    
    kb = InlineKeyboardBuilder()
    for chat in chats[:15]:  # Показываем первые 15
        muted = "🔇" if is_group_muted(chat.id) else ""
        forum_icon = "📋" if chat.is_forum else "💬"
        title = chat.title[:25] + "..." if len(chat.title) > 25 else chat.title
        kb.button(text=f"{muted}{forum_icon} {title}", callback_data=f"owner_group:{chat.id}")
    
    if len(chats) > 15:
        text += f"\n... и ещё {len(chats) - 15} групп"
    
    kb.button(text="🔄 Обновить", callback_data="owner_groups_list")
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("owner_group:"))
async def cb_owner_group_actions(callback: CallbackQuery):
    """Показать действия для конкретной группы."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split(":")[1])
    
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(select(Chat).filter_by(id=chat_id))
        chat = result.scalars().first()
    
    if not chat:
        await callback.answer("Группа не найдена", show_alert=True)
        return
    
    muted = is_group_muted(chat_id)
    mute_text = "🔊 Размутить" if muted else "🔇 Замутить"
    
    text = f"⚙️ <b>Управление группой</b>\n\n"
    text += f"📋 <b>Название:</b> {chat.title}\n"
    text += f"🆔 <b>ID:</b> <code>{chat.id}</code>\n"
    text += f"📌 <b>Форум:</b> {'Да' if chat.is_forum else 'Нет'}\n"
    text += f"🔇 <b>Мут:</b> {'Да' if muted else 'Нет'}\n"
    
    kb = InlineKeyboardBuilder()
    kb.button(text=mute_text, callback_data=f"owner_mute_group:{chat_id}")
    kb.button(text="🚪 Выйти из группы", callback_data=f"owner_leave_group:{chat_id}")
    kb.button(text="🔙 К списку", callback_data="owner_groups_list")
    kb.adjust(2, 1)
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("owner_mute_group:"))
async def cb_owner_mute_group(callback: CallbackQuery):
    """Замутить/размутить группу."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split(":")[1])
    
    if chat_id in _muted_groups:
        _muted_groups.remove(chat_id)
        await callback.answer("🔊 Группа размучена!", show_alert=True)
    else:
        _muted_groups.add(chat_id)
        await callback.answer("🔇 Группа замучена! Бот не будет отвечать.", show_alert=True)
    
    # Возвращаемся к действиям группы
    await cb_owner_group_actions(callback)


@router.callback_query(F.data.startswith("owner_leave_group:"))
async def cb_owner_leave_group(callback: CallbackQuery):
    """Подтверждение выхода из группы."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split(":")[1])
    
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(select(Chat).filter_by(id=chat_id))
        chat = result.scalars().first()
    
    title = chat.title if chat else f"ID: {chat_id}"
    
    text = f"⚠️ <b>Подтверждение выхода</b>\n\n"
    text += f"Ты уверен, что хочешь выйти из группы?\n"
    text += f"<b>{title}</b>\n\n"
    text += "Это действие нельзя отменить!"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, выйти", callback_data=f"owner_leave_confirm:{chat_id}")
    kb.button(text="❌ Отмена", callback_data=f"owner_group:{chat_id}")
    kb.adjust(2)
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("owner_leave_confirm:"))
async def cb_owner_leave_confirm(callback: CallbackQuery):
    """Выполнить выход из группы."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split(":")[1])
    
    try:
        await callback.bot.leave_chat(chat_id)
        
        # Удаляем из БД
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(select(Chat).filter_by(id=chat_id))
            chat = result.scalars().first()
            if chat:
                await session.delete(chat)
                await session.commit()
        
        # Удаляем из мута если был
        _muted_groups.discard(chat_id)
        
        await callback.answer("🚪 Бот вышел из группы!", show_alert=True)
        
        # Возвращаемся к списку групп
        await cb_owner_groups_list(callback)
        
    except Exception as e:
        logger.error(f"Failed to leave chat {chat_id}: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "owner_top_users")
async def cb_owner_top_users(callback: CallbackQuery):
    """Показать топ пользователей бота."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    async_session = get_session()
    async with async_session() as session:
        from app.database.models import GameStat, MessageLog
        
        # Топ по количеству сообщений (самые активные)
        msg_result = await session.execute(
            select(
                MessageLog.user_id,
                MessageLog.username,
                func.count(MessageLog.id).label('msg_count')
            )
            .group_by(MessageLog.user_id, MessageLog.username)
            .order_by(func.count(MessageLog.id).desc())
            .limit(10)
        )
        top_active = msg_result.all()
        
        # Топ по репутации
        rep_result = await session.execute(
            select(User).order_by(User.reputation_score.desc()).limit(10)
        )
        top_rep = rep_result.scalars().all()
        
        # Общее количество пользователей
        count_result = await session.execute(select(func.count(User.id)))
        total_users = count_result.scalar()
    
    text = f"🏆 <b>Топ пользователей</b>\n"
    text += f"📊 Всего: {total_users} пользователей\n\n"
    
    text += "<b>💬 Топ по активности (сообщения):</b>\n"
    for i, row in enumerate(top_active, 1):
        name = f"@{row.username}" if row.username else f"id:{row.user_id}"
        text += f"{i}. {name} — {row.msg_count:,} сообщений\n"
    
    text += "\n<b>🎖 Топ по репутации:</b>\n"
    for i, user in enumerate(top_rep, 1):
        name = f"@{user.username}" if user.username else user.first_name or f"id:{user.tg_user_id}"
        text += f"{i}. {name} — {user.reputation_score} очков\n"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Обновить", callback_data="owner_top_users")
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(2)
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "owner_stats")
async def cb_owner_stats(callback: CallbackQuery):
    """Показать общую статистику бота."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer("📊 Загружаю статистику...", show_alert=False)
    
    async_session = get_session()
    async with async_session() as session:
        from app.database.models import GameStat, MessageLog
        from datetime import timedelta
        
        # Общее количество пользователей
        total_users = await session.scalar(select(func.count(User.id)))
        
        # Количество групп
        total_groups = await session.scalar(select(func.count(Chat.id)))
        
        # Количество приватных чатов
        total_private = await session.scalar(
            select(func.count(PrivateChat.user_id))
            .where(PrivateChat.is_blocked == False)
        )
        
        # Всего сообщений
        total_messages = await session.scalar(select(func.count(MessageLog.id)))
        
        # Сообщений за сегодня
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        messages_today = await session.scalar(
            select(func.count(MessageLog.id))
            .where(MessageLog.created_at >= today)
        )
        
        # Сообщений за неделю
        week_ago = today - timedelta(days=7)
        messages_week = await session.scalar(
            select(func.count(MessageLog.id))
            .where(MessageLog.created_at >= week_ago)
        )
        
        # Активных пользователей сегодня (уникальные user_id в сообщениях)
        active_today = await session.scalar(
            select(func.count(func.distinct(MessageLog.user_id)))
            .where(MessageLog.created_at >= today)
        )
        
        # Игровая статистика
        total_players = await session.scalar(select(func.count(GameStat.user_id)))
        
        # Сумма всех размеров
        total_size = await session.scalar(select(func.sum(GameStat.size_cm))) or 0
        
        # Всего PvP побед
        total_pvp_wins = await session.scalar(select(func.sum(GameStat.pvp_wins))) or 0
        
        # Всего grow операций
        total_grows = await session.scalar(select(func.sum(GameStat.grow_count))) or 0
    
    text = "📈 <b>Общая статистика бота</b>\n\n"
    
    text += "<b>👥 Пользователи:</b>\n"
    text += f"├ Всего: {total_users or 0}\n"
    text += f"├ Активных сегодня: {active_today or 0}\n"
    text += f"└ Приватных чатов: {total_private or 0}\n\n"
    
    text += "<b>💬 Сообщения:</b>\n"
    text += f"├ Всего: {total_messages or 0:,}\n"
    text += f"├ За сегодня: {messages_today or 0:,}\n"
    text += f"└ За неделю: {messages_week or 0:,}\n\n"
    
    text += "<b>👥 Группы:</b>\n"
    text += f"└ Всего: {total_groups or 0}\n\n"
    
    text += "<b>🎮 Игры:</b>\n"
    text += f"├ Игроков: {total_players or 0}\n"
    text += f"├ Общий размер: {total_size:,} см\n"
    text += f"├ PvP побед: {total_pvp_wins:,}\n"
    text += f"└ Grow операций: {total_grows:,}\n"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Обновить", callback_data="owner_stats")
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(2)
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# ============================================================================
# Обновление главного меню с экстренными действиями
# ============================================================================

def build_owner_main_menu() -> InlineKeyboardBuilder:
    """Построить главное меню владельца."""
    kb = InlineKeyboardBuilder()
    
    kb.button(text="⚙️ Функции бота", callback_data="owner_features")
    kb.button(text="🎭 Персона", callback_data="owner_persona")
    kb.button(text="🎤 Формат ответов", callback_data="owner_format_menu")
    kb.button(text="📢 Рассылка", callback_data="owner_broadcast")
    kb.button(text="📊 Статус системы", callback_data="owner_status")
    kb.button(text="📈 Общая статистика", callback_data="owner_stats")
    kb.button(text="💬 Управление чатами", callback_data="owner_chats")
    kb.button(text="👥 Список групп", callback_data="owner_groups_list")
    kb.button(text="🏆 Топ пользователей", callback_data="owner_top_users")
    kb.button(text="👤 Управление юзерами", callback_data="owner_users")
    kb.button(text="🔧 Настройки", callback_data="owner_settings")
    kb.button(text="🚨 Экстренные действия", callback_data="owner_emergency")
    
    kb.adjust(2, 2, 2, 2, 2, 2)
    return kb


# ============================================================================
# Управление персоной (глобальная личность бота)
# ============================================================================

@router.callback_query(F.data == "owner_persona")
async def cb_owner_persona(callback: CallbackQuery):
    """Меню управления персоной бота."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    from app.services.ollama_client import (
        get_global_persona, get_random_mode, PERSONA_NAMES, RANDOM_INTERVALS
    )
    
    current_persona = get_global_persona()
    current_name = PERSONA_NAMES.get(current_persona, current_persona)
    random_enabled, random_interval, _ = get_random_mode()
    
    if random_enabled:
        interval_name = RANDOM_INTERVALS.get(random_interval, random_interval)
        mode_text = f"🎲 <b>Рандом</b> ({interval_name})\n<b>Сейчас:</b> {current_name}"
    else:
        mode_text = f"<b>Текущая:</b> {current_name}"
    
    text = (
        f"🎭 <b>Персона бота</b>\n\n"
        f"{mode_text}\n\n"
        "<b>Доступные персоны:</b>\n"
        "• 😎 <b>Олег</b> — дерзкий, уверенный, подкалывает\n"
        "• 👔 <b>Олег Кузнецов</b> — живой человек, Senior DevOps\n"
        "• 🎳 <b>The Dude</b> — расслабленный, философский\n"
        "• ☭ <b>Сталин</b> — авторитарный, советская риторика\n"
        "• 🌸 <b>Аниме-тян</b> — кавайная, милая, с эмодзи\n"
        "• 🇺🇸 <b>Трамп</b> — MAKE HARDWARE GREAT AGAIN\n"
        "• 🇷🇺 <b>Путин</b> — гарант стабильности FPS\n"
        "• 🐘 <b>Поздняков</b> — МЖГ, степашки, база\n"
        "• 🇿 <b>Z-Гик</b> — военкор технического фронта\n\n"
        "Персона применяется <b>глобально</b> ко всем чатам."
    )
    
    kb = InlineKeyboardBuilder()
    
    # Кнопка рандомного режима
    random_status = "✓ " if random_enabled else ""
    kb.button(text=f"{random_status}🎲 Рандом", callback_data="owner_persona_random")
    
    # Кнопки выбора персоны
    for persona_code, persona_name in PERSONA_NAMES.items():
        selected = "✓ " if persona_code == current_persona and not random_enabled else ""
        kb.button(
            text=f"{selected}{persona_name}",
            callback_data=f"owner_set_persona:{persona_code}"
        )
    
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "owner_persona_random")
async def cb_owner_persona_random(callback: CallbackQuery):
    """Меню настройки рандомного режима персоны."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    from app.services.ollama_client import get_random_mode, get_random_excluded, RANDOM_INTERVALS, PERSONA_NAMES
    
    random_enabled, current_interval, excluded = get_random_mode()
    
    # Список исключённых
    excluded_names = [PERSONA_NAMES.get(p, p) for p in excluded] if excluded else ["нет"]
    excluded_text = ", ".join(excluded_names)
    
    # Сколько персон участвует
    active_count = len(PERSONA_NAMES) - len(excluded)
    
    text = (
        "🎲 <b>Рандомный режим персоны</b>\n\n"
        f"<b>Статус:</b> {'✅ Включён' if random_enabled else '❌ Выключен'}\n"
        f"<b>Интервал:</b> {RANDOM_INTERVALS.get(current_interval, current_interval)}\n"
        f"<b>Участвует:</b> {active_count} из {len(PERSONA_NAMES)} персон\n"
        f"<b>Исключены:</b> {excluded_text}\n\n"
        "<b>Интервалы смены:</b>\n"
        "• 🎲 <b>Каждое сообщение</b> — новая персона на каждый ответ\n"
        "• ⏰ <b>Раз в час</b> — смена каждый час\n"
        "• 🌓 <b>Раз в 12 часов</b> — утром и вечером\n"
        "• 📅 <b>Раз в день</b> — новая персона каждый день"
    )
    
    kb = InlineKeyboardBuilder()
    
    # Кнопка вкл/выкл
    if random_enabled:
        kb.button(text="❌ Выключить рандом", callback_data="owner_random_toggle:off")
    else:
        kb.button(text="✅ Включить рандом", callback_data="owner_random_toggle:on")
    
    # Кнопка исключений
    kb.button(text="🚫 Исключения", callback_data="owner_random_exclude")
    
    # Кнопки интервалов
    for interval_code, interval_name in RANDOM_INTERVALS.items():
        selected = "✓ " if interval_code == current_interval else ""
        kb.button(
            text=f"{selected}{interval_name}",
            callback_data=f"owner_random_interval:{interval_code}"
        )
    
    kb.button(text="🔙 К персонам", callback_data="owner_persona")
    kb.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "owner_random_exclude")
async def cb_owner_random_exclude(callback: CallbackQuery):
    """Меню исключения персон из рандома."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    from app.services.ollama_client import get_random_excluded, PERSONA_NAMES
    
    excluded = get_random_excluded()
    
    text = (
        "🚫 <b>Исключения из рандома</b>\n\n"
        "Выбери персоны, которые <b>НЕ</b> будут участвовать в рандоме.\n\n"
        "✓ = участвует в рандоме\n"
        "✗ = исключена из рандома"
    )
    
    kb = InlineKeyboardBuilder()
    
    for persona_code, persona_name in PERSONA_NAMES.items():
        is_excluded = persona_code in excluded
        status = "✗ " if is_excluded else "✓ "
        kb.button(
            text=f"{status}{persona_name}",
            callback_data=f"owner_toggle_exclude:{persona_code}"
        )
    
    kb.button(text="🔙 Назад", callback_data="owner_persona_random")
    kb.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("owner_toggle_exclude:"))
async def cb_owner_toggle_exclude(callback: CallbackQuery):
    """Переключить исключение персоны из рандома."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    persona_code = callback.data.split(":")[1]
    
    from app.services.ollama_client import toggle_random_excluded, PERSONA_NAMES, get_random_excluded
    
    # Проверяем, не последняя ли это персона
    excluded = get_random_excluded()
    if persona_code not in excluded and len(excluded) >= len(PERSONA_NAMES) - 1:
        await callback.answer("⚠️ Нельзя исключить все персоны!", show_alert=True)
        return
    
    is_now_excluded = toggle_random_excluded(persona_code)
    persona_name = PERSONA_NAMES.get(persona_code, persona_code)
    
    status = "исключена" if is_now_excluded else "включена"
    await callback.answer(f"{persona_name} {status}", show_alert=False)
    logger.info(f"Persona {persona_code} {'excluded from' if is_now_excluded else 'included in'} random by owner {callback.from_user.id}")
    
    await cb_owner_random_exclude(callback)


@router.callback_query(F.data.startswith("owner_random_toggle:"))
async def cb_owner_random_toggle(callback: CallbackQuery):
    """Включить/выключить рандомный режим."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    action = callback.data.split(":")[1]
    enabled = action == "on"
    
    from app.services.ollama_client import set_random_mode, get_random_mode
    
    _, current_interval, _ = get_random_mode()
    set_random_mode(enabled, current_interval)
    
    status = "включён" if enabled else "выключен"
    await callback.answer(f"🎲 Рандом {status}", show_alert=True)
    logger.info(f"Random mode {'enabled' if enabled else 'disabled'} by owner {callback.from_user.id}")
    
    await cb_owner_persona_random(callback)


@router.callback_query(F.data.startswith("owner_random_interval:"))
async def cb_owner_random_interval(callback: CallbackQuery):
    """Установить интервал рандомной смены."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    interval = callback.data.split(":")[1]
    
    from app.services.ollama_client import set_random_mode, get_random_mode, RANDOM_INTERVALS
    
    random_enabled, _, _ = get_random_mode()
    
    if set_random_mode(random_enabled, interval):
        interval_name = RANDOM_INTERVALS.get(interval, interval)
        await callback.answer(f"⏰ Интервал: {interval_name}", show_alert=True)
        logger.info(f"Random interval set to {interval} by owner {callback.from_user.id}")
    else:
        await callback.answer("❌ Неизвестный интервал", show_alert=True)
        return
    
    await cb_owner_persona_random(callback)


@router.callback_query(F.data.startswith("owner_set_persona:"))
async def cb_owner_set_persona(callback: CallbackQuery):
    """Установить персону бота."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    persona_code = callback.data.split(":")[1]
    
    from app.services.ollama_client import set_global_persona, set_random_mode, PERSONA_NAMES
    
    # Выключаем рандом при выборе конкретной персоны
    set_random_mode(False)
    
    if set_global_persona(persona_code):
        persona_name = PERSONA_NAMES.get(persona_code, persona_code)
        await callback.answer(f"✅ Персона изменена: {persona_name}", show_alert=True)
        logger.info(f"Persona changed to {persona_code} by owner {callback.from_user.id}")
    else:
        await callback.answer("❌ Неизвестная персона", show_alert=True)
        return
    
    # Обновляем меню
    await cb_owner_persona(callback)


# ============================================================================
# Управление пользователями
# ============================================================================

class UserManagementStates(StatesGroup):
    """FSM состояния для управления пользователями."""
    waiting_user_search = State()
    waiting_coins_amount = State()  # Ожидание суммы монет


@router.callback_query(F.data == "owner_users")
async def cb_owner_users(callback: CallbackQuery):
    """Меню управления пользователями."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    async_session = get_session()
    async with async_session() as session:
        total_users = await session.scalar(select(func.count(User.id)))
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔍 Поиск пользователя", callback_data="owner_user_search")
    kb.button(text="🏆 Топ активных", callback_data="owner_top_users")
    kb.button(text="📋 Последние юзеры", callback_data="owner_users_recent")
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(1)
    
    await callback.message.edit_text(
        f"👤 <b>Управление пользователями</b>\n\n"
        f"📊 Всего пользователей: {total_users or 0}\n\n"
        "Выбери действие:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "owner_user_search")
async def cb_owner_user_search(callback: CallbackQuery, state: FSMContext):
    """Начать поиск пользователя."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await state.set_state(UserManagementStates.waiting_user_search)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data="owner_users")
    
    await callback.message.edit_text(
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Отправь:\n"
        "• @username\n"
        "• ID пользователя\n"
        "• Часть имени",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.message(UserManagementStates.waiting_user_search)
async def handle_user_search(msg: Message, state: FSMContext):
    """Обработка поиска пользователя."""
    if not is_owner(msg.from_user.id):
        return
    
    await state.clear()
    query = msg.text.strip()
    
    async_session = get_session()
    async with async_session() as session:
        users = []
        
        # Поиск по ID
        if query.isdigit():
            result = await session.execute(
                select(User).where(User.tg_user_id == int(query))
            )
            users = list(result.scalars().all())
        
        # Поиск по username
        if not users and query.startswith("@"):
            username = query[1:]
            result = await session.execute(
                select(User).where(User.username.ilike(f"%{username}%"))
            )
            users = list(result.scalars().all())
        
        # Поиск по имени
        if not users:
            result = await session.execute(
                select(User).where(
                    (User.first_name.ilike(f"%{query}%")) |
                    (User.username.ilike(f"%{query}%"))
                ).limit(10)
            )
            users = list(result.scalars().all())
    
    if not users:
        kb = InlineKeyboardBuilder()
        kb.button(text="🔍 Искать снова", callback_data="owner_user_search")
        kb.button(text="🔙 Назад", callback_data="owner_users")
        kb.adjust(1)
        
        await msg.answer(
            f"❌ Пользователь не найден: <code>{query}</code>",
            reply_markup=kb.as_markup()
        )
        return
    
    if len(users) == 1:
        # Показать профиль сразу
        await show_user_profile(msg, users[0])
    else:
        # Показать список
        kb = InlineKeyboardBuilder()
        for user in users[:10]:
            name = f"@{user.username}" if user.username else user.first_name or f"id:{user.tg_user_id}"
            kb.button(text=name, callback_data=f"owner_user:{user.tg_user_id}")
        kb.button(text="🔙 Назад", callback_data="owner_users")
        kb.adjust(1)
        
        await msg.answer(
            f"🔍 Найдено {len(users)} пользователей:",
            reply_markup=kb.as_markup()
        )


async def show_user_profile(msg_or_callback, user: User, edit: bool = False):
    """Показать профиль пользователя."""
    async_session = get_session()
    async with async_session() as session:
        from app.database.models import GameStat, MessageLog
        
        # Статистика сообщений
        msg_count = await session.scalar(
            select(func.count(MessageLog.id))
            .where(MessageLog.user_id == user.tg_user_id)
        )
        
        # Игровая статистика
        game_stat = await session.scalar(
            select(GameStat).where(GameStat.tg_user_id == user.tg_user_id)
        )
    
    name = f"@{user.username}" if user.username else user.first_name or "Без имени"
    
    # Получаем общий баланс по всем чатам
    total_balance = 0
    async_session = get_session()
    async with async_session() as session:
        from app.database.models import UserBalance
        balances = await session.execute(
            select(UserBalance).where(UserBalance.user_id == user.tg_user_id)
        )
        for bal in balances.scalars():
            total_balance += bal.balance
    
    text = f"👤 <b>Профиль пользователя</b>\n\n"
    text += f"<b>Имя:</b> {user.first_name or 'N/A'}\n"
    text += f"<b>Username:</b> @{user.username or 'N/A'}\n"
    text += f"<b>ID:</b> <code>{user.tg_user_id}</code>\n"
    text += f"<b>Репутация:</b> {user.reputation_score}\n"
    text += f"<b>💰 Баланс:</b> {total_balance:,} монет\n"
    text += f"<b>Сообщений:</b> {msg_count or 0:,}\n"
    
    if game_stat:
        text += f"\n<b>🎮 Игровая статистика:</b>\n"
        text += f"├ Размер: {game_stat.size_cm} см\n"
        text += f"├ PvP побед: {game_stat.pvp_wins}\n"
        text += f"└ Grow: {game_stat.grow_count}\n"
    
    text += f"\n<b>Создан:</b> {user.created_at.strftime('%d.%m.%Y %H:%M') if user.created_at else 'N/A'}"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 Выдать монеты", callback_data=f"owner_user_coins:{user.tg_user_id}")
    kb.button(text="🔄 Сбросить репутацию", callback_data=f"owner_user_reset_rep:{user.tg_user_id}")
    kb.button(text="🎮 Сбросить игру", callback_data=f"owner_user_reset_game:{user.tg_user_id}")
    kb.button(text="🗑 Удалить юзера", callback_data=f"owner_user_delete:{user.tg_user_id}")
    kb.button(text="🔙 Назад", callback_data="owner_users")
    kb.adjust(1, 2, 1, 1)
    
    if edit and hasattr(msg_or_callback, 'message'):
        await msg_or_callback.message.edit_text(text, reply_markup=kb.as_markup())
    else:
        await msg_or_callback.answer(text, reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("owner_user:"))
async def cb_owner_user_profile(callback: CallbackQuery):
    """Показать профиль пользователя по callback."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    tg_user_id = int(callback.data.split(":")[1])
    
    async_session = get_session()
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.tg_user_id == tg_user_id)
        )
    
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    
    await show_user_profile(callback, user, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("owner_user_reset_rep:"))
async def cb_owner_reset_reputation(callback: CallbackQuery):
    """Сбросить репутацию пользователя."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    tg_user_id = int(callback.data.split(":")[1])
    
    async_session = get_session()
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.tg_user_id == tg_user_id)
        )
        if user:
            user.reputation_score = 0
            await session.commit()
    
    await callback.answer("✅ Репутация сброшена!", show_alert=True)
    
    # Обновить профиль
    if user:
        await show_user_profile(callback, user, edit=True)


@router.callback_query(F.data.startswith("owner_user_reset_game:"))
async def cb_owner_reset_game(callback: CallbackQuery):
    """Сбросить игровую статистику пользователя."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    tg_user_id = int(callback.data.split(":")[1])
    
    async_session = get_session()
    async with async_session() as session:
        from app.database.models import GameStat
        
        game_stat = await session.scalar(
            select(GameStat).where(GameStat.tg_user_id == tg_user_id)
        )
        if game_stat:
            game_stat.size_cm = 0
            game_stat.pvp_wins = 0
            game_stat.grow_count = 0
            game_stat.casino_jackpots = 0
            await session.commit()
    
    await callback.answer("✅ Игровая статистика сброшена!", show_alert=True)
    
    # Обновить профиль
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.tg_user_id == tg_user_id)
        )
    if user:
        await show_user_profile(callback, user, edit=True)


@router.callback_query(F.data.startswith("owner_user_delete:"))
async def cb_owner_delete_user(callback: CallbackQuery):
    """Подтверждение удаления пользователя."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    tg_user_id = int(callback.data.split(":")[1])
    
    kb = InlineKeyboardBuilder()
    kb.button(text="⚠️ Да, удалить", callback_data=f"owner_user_delete_confirm:{tg_user_id}")
    kb.button(text="❌ Отмена", callback_data=f"owner_user:{tg_user_id}")
    kb.adjust(2)
    
    await callback.message.edit_text(
        f"⚠️ <b>Подтверждение удаления</b>\n\n"
        f"Удалить пользователя <code>{tg_user_id}</code>?\n\n"
        "Это удалит все данные пользователя!",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("owner_user_delete_confirm:"))
async def cb_owner_delete_user_confirm(callback: CallbackQuery):
    """Выполнить удаление пользователя."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    tg_user_id = int(callback.data.split(":")[1])
    
    async_session = get_session()
    async with async_session() as session:
        from app.database.models import GameStat, MessageLog
        from sqlalchemy import delete
        
        # Удаляем связанные данные
        await session.execute(delete(GameStat).where(GameStat.tg_user_id == tg_user_id))
        await session.execute(delete(MessageLog).where(MessageLog.user_id == tg_user_id))
        
        # Удаляем пользователя
        user = await session.scalar(select(User).where(User.tg_user_id == tg_user_id))
        if user:
            await session.delete(user)
        
        await session.commit()
    
    await callback.answer("✅ Пользователь удалён!", show_alert=True)
    
    # Вернуться к списку
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 К управлению", callback_data="owner_users")
    
    await callback.message.edit_text(
        f"✅ Пользователь <code>{tg_user_id}</code> удалён.",
        reply_markup=kb.as_markup()
    )


@router.callback_query(F.data.startswith("owner_user_coins:"))
async def cb_owner_user_coins(callback: CallbackQuery, state: FSMContext):
    """Меню выдачи монет пользователю."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    tg_user_id = int(callback.data.split(":")[1])
    
    # Сохраняем ID пользователя в состояние
    await state.update_data(coins_target_user=tg_user_id)
    await state.set_state(UserManagementStates.waiting_coins_amount)
    
    kb = InlineKeyboardBuilder()
    # Быстрые кнопки
    for amount in [100, 500, 1000, 5000, 10000]:
        kb.button(text=f"+{amount:,}", callback_data=f"owner_coins_quick:{tg_user_id}:{amount}")
    kb.button(text="❌ Отмена", callback_data=f"owner_user:{tg_user_id}")
    kb.adjust(3, 2, 1)
    
    await callback.message.edit_text(
        f"💰 <b>Выдача монет</b>\n\n"
        f"Пользователь: <code>{tg_user_id}</code>\n\n"
        "Выбери сумму или введи число (можно отрицательное для снятия):",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("owner_coins_quick:"))
async def cb_owner_coins_quick(callback: CallbackQuery, state: FSMContext):
    """Быстрая выдача монет по кнопке."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    parts = callback.data.split(":")
    tg_user_id = int(parts[1])
    amount = int(parts[2])
    
    await state.clear()
    await _give_coins_to_user(callback, tg_user_id, amount)


@router.message(UserManagementStates.waiting_coins_amount)
async def handle_coins_amount(msg: Message, state: FSMContext):
    """Обработка введённой суммы монет."""
    if not is_owner(msg.from_user.id):
        return
    
    data = await state.get_data()
    tg_user_id = data.get("coins_target_user")
    
    if not tg_user_id:
        await state.clear()
        await msg.reply("❌ Ошибка: пользователь не найден")
        return
    
    try:
        amount = int(msg.text.strip().replace(",", "").replace(" ", ""))
    except ValueError:
        await msg.reply("❌ Введи число (например: 1000 или -500)")
        return
    
    await state.clear()
    await _give_coins_to_user(msg, tg_user_id, amount, is_message=True)


async def _give_coins_to_user(msg_or_callback, tg_user_id: int, amount: int, is_message: bool = False):
    """Выдать/снять монеты пользователю."""
    from app.database.models import Wallet
    
    async_session = get_session()
    async with async_session() as session:
        # Получаем пользователя
        user = await session.scalar(select(User).where(User.tg_user_id == tg_user_id))
        if not user:
            text = "❌ Пользователь не найден"
            if is_message:
                await msg_or_callback.reply(text)
            else:
                await msg_or_callback.answer(text, show_alert=True)
            return
        
        # Получаем или создаём Wallet (глобальный баланс, используется играми)
        wallet = await session.scalar(
            select(Wallet).where(Wallet.user_id == user.id)
        )
        
        if not wallet:
            wallet = Wallet(user_id=user.id, balance=100)  # Стартовый баланс
            session.add(wallet)
        
        old_balance = wallet.balance
        wallet.balance += amount
        
        # Не даём уйти в минус
        if wallet.balance < 0:
            wallet.balance = 0
        
        await session.commit()
        new_balance = wallet.balance
    
    action = "выдано" if amount > 0 else "снято"
    
    name = f"@{user.username}" if user.username else user.first_name or f"id:{tg_user_id}"
    text = (
        f"✅ <b>Монеты {action}!</b>\n\n"
        f"👤 {name}\n"
        f"💰 {old_balance:,} → {new_balance:,} ({amount:+,})"
    )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 К профилю", callback_data=f"owner_user:{tg_user_id}")
    kb.button(text="🔙 К управлению", callback_data="owner_users")
    kb.adjust(2)
    
    if is_message:
        await msg_or_callback.reply(text, reply_markup=kb.as_markup())
    else:
        await msg_or_callback.message.edit_text(text, reply_markup=kb.as_markup())
        await msg_or_callback.answer()
    
    logger.info(f"Owner gave {amount} coins to user {tg_user_id} (new balance: {new_balance})")


@router.callback_query(F.data == "owner_users_recent")
async def cb_owner_users_recent(callback: CallbackQuery):
    """Показать последних зарегистрированных пользователей."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(15)
        )
        users = result.scalars().all()
    
    if not users:
        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 Назад", callback_data="owner_users")
        await callback.message.edit_text(
            "📭 Нет пользователей",
            reply_markup=kb.as_markup()
        )
        await callback.answer()
        return
    
    text = "📋 <b>Последние пользователи</b>\n\n"
    
    kb = InlineKeyboardBuilder()
    for user in users:
        name = f"@{user.username}" if user.username else user.first_name or f"id:{user.tg_user_id}"
        date = user.created_at.strftime('%d.%m') if user.created_at else "?"
        kb.button(text=f"{date} {name}", callback_data=f"owner_user:{user.tg_user_id}")
    
    kb.button(text="🔙 Назад", callback_data="owner_users")
    kb.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()

# ============================================================================
# РАСШИРЕННОЕ МЕНЮ ВАЙПА (Selective Wipe)
# ============================================================================

@router.callback_query(F.data == "owner_wipe_menu")
async def cb_owner_wipe_menu(callback: CallbackQuery):
    """Меню выборочного вайпа."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🧠 RAG память (ChromaDB)", callback_data="owner_wipe_rag")
    kb.button(text="🎮 Игровая статистика", callback_data="owner_wipe_games")
    kb.button(text="📝 Логи сообщений", callback_data="owner_wipe_messages")
    kb.button(text="👥 Пользователи и чаты", callback_data="owner_wipe_users")
    kb.button(text="🏆 Достижения и квесты", callback_data="owner_wipe_achievements")
    kb.button(text="⚠️ ВСЁ СРАЗУ", callback_data="owner_wipe_all_confirm")
    kb.button(text="🔙 Назад", callback_data="owner_emergency")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "🗑 <b>Выборочный вайп</b>\n\n"
        "Выбери что хочешь сбросить:\n\n"
        "• <b>RAG память</b> — векторная БД (ChromaDB)\n"
        "• <b>Игровая статистика</b> — размеры, PvP, казино\n"
        "• <b>Логи сообщений</b> — история сообщений\n"
        "• <b>Пользователи и чаты</b> — все юзеры и группы\n"
        "• <b>Достижения и квесты</b> — прогресс игроков\n\n"
        "⚠️ Действия необратимы!",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "owner_wipe_rag")
async def cb_owner_wipe_rag(callback: CallbackQuery):
    """Подтверждение вайпа RAG памяти."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🧠 Вайп + восстановить дефолт", callback_data="owner_wipe_rag_exec:restore")
    kb.button(text="🗑 Полный вайп (без дефолта)", callback_data="owner_wipe_rag_exec:clean")
    kb.button(text="❌ Отмена", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "🧠 <b>Вайп RAG памяти (ChromaDB)</b>\n\n"
        "Это удалит всю векторную память бота:\n"
        "• Запомненные факты из чатов\n"
        "• Контекст разговоров\n"
        "• Выученную информацию\n\n"
        "Выбери режим:\n"
        "• <b>С восстановлением</b> — загрузит дефолтные знания\n"
        "• <b>Полный вайп</b> — оставит память пустой",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("owner_wipe_rag_exec:"))
async def cb_owner_wipe_rag_exec(callback: CallbackQuery):
    """Выполнение вайпа RAG памяти."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    # Сразу отвечаем на callback чтобы не протух (Telegram даёт ~30 сек)
    await callback.answer("⏳ Выполняется...")
    
    mode = callback.data.split(":")[1]  # restore или clean
    restore_default = mode == "restore"
    
    await callback.message.edit_text("🧠 <b>Вайп RAG памяти...</b>\n\n⏳ Подождите...")
    
    results = []
    
    try:
        from app.services.vector_db import vector_db
        if vector_db.client:
            collections = vector_db.client.list_collections()
            for col in collections:
                vector_db.client.delete_collection(col.name)
            results.append(f"✅ Удалено {len(collections)} коллекций")
        else:
            results.append("⚠️ ChromaDB не инициализирована")
    except Exception as e:
        results.append(f"❌ Ошибка: {str(e)[:50]}")

    
    if restore_default:
        try:
            from app.services.vector_db import vector_db
            from app.config import settings
            if vector_db.client:
                collection_name = settings.chromadb_collection_name
                load_result = vector_db.load_default_knowledge(collection_name)
                if load_result.get("error"):
                    results.append(f"⚠️ Дефолт: {load_result['error']}")
                else:
                    results.append(f"✅ Загружено {load_result['loaded']} дефолтных фактов")
        except Exception as e:
            results.append(f"❌ Дефолт: {str(e)[:50]}")
    
    logger.warning(f"RAG WIPE executed by owner {callback.from_user.id}, restore={restore_default}")
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 К меню вайпа", callback_data="owner_wipe_menu")
    kb.button(text="🏠 Главное меню", callback_data="owner_main")
    kb.adjust(2)
    
    await callback.message.edit_text(
        "🧠 <b>Вайп RAG памяти завершён</b>\n\n" +
        "\n".join(results),
        reply_markup=kb.as_markup()
    )


@router.callback_query(F.data == "owner_wipe_games")
async def cb_owner_wipe_games(callback: CallbackQuery):
    """Подтверждение вайпа игровой статистики."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, сбросить игры", callback_data="owner_wipe_games_exec")
    kb.button(text="❌ Отмена", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "🎮 <b>Вайп игровой статистики</b>\n\n"
        "Это удалит:\n"
        "• Все размеры игроков\n"
        "• PvP статистику и победы\n"
        "• Казино джекпоты\n"
        "• ELO рейтинги и лиги\n"
        "• Кошельки и балансы\n\n"
        "⚠️ Все игроки начнут с нуля!",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "owner_wipe_games_exec")
async def cb_owner_wipe_games_exec(callback: CallbackQuery):
    """Выполнение вайпа игровой статистики."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer("⏳ Выполняется...")
    await callback.message.edit_text("🎮 <b>Вайп игр...</b>\n\n⏳ Подождите...")
    
    results = []
    
    try:
        from app.database.models import GameStat, Wallet, UserElo
        from sqlalchemy import delete
        
        async with get_session()() as session:
            r1 = await session.execute(delete(GameStat))
            r2 = await session.execute(delete(Wallet))
            try:
                r3 = await session.execute(delete(UserElo))
                results.append(f"✅ UserElo: {r3.rowcount}")
            except Exception:
                pass
            await session.commit()
            results.append(f"✅ GameStat: {r1.rowcount} записей")
            results.append(f"✅ Wallet: {r2.rowcount} записей")
    except Exception as e:
        results.append(f"❌ Ошибка: {str(e)[:50]}")

    
    logger.warning(f"GAMES WIPE executed by owner {callback.from_user.id}")
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 К меню вайпа", callback_data="owner_wipe_menu")
    kb.button(text="🏠 Главное меню", callback_data="owner_main")
    kb.adjust(2)
    
    await callback.message.edit_text(
        "🎮 <b>Вайп игр завершён</b>\n\n" +
        "\n".join(results),
        reply_markup=kb.as_markup()
    )


@router.callback_query(F.data == "owner_wipe_messages")
async def cb_owner_wipe_messages(callback: CallbackQuery):
    """Подтверждение вайпа логов сообщений."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, очистить логи", callback_data="owner_wipe_messages_exec")
    kb.button(text="❌ Отмена", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "📝 <b>Вайп логов сообщений</b>\n\n"
        "Это удалит:\n"
        "• Историю всех сообщений\n"
        "• Историю вопросов пользователей\n\n"
        "⚠️ Статистика активности будет потеряна!",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "owner_wipe_messages_exec")
async def cb_owner_wipe_messages_exec(callback: CallbackQuery):
    """Выполнение вайпа логов."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer("⏳ Выполняется...")
    
    results = []
    try:
        from app.database.models import MessageLog, UserQuestionHistory
        from sqlalchemy import delete
        
        async with get_session()() as session:
            r1 = await session.execute(delete(MessageLog))
            r2 = await session.execute(delete(UserQuestionHistory))
            await session.commit()
            results.append(f"✅ Сообщений: {r1.rowcount}")
            results.append(f"✅ История вопросов: {r2.rowcount}")
    except Exception as e:
        results.append(f"❌ Ошибка: {str(e)[:50]}")

    
    logger.warning(f"MESSAGES WIPE executed by owner {callback.from_user.id}")
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 К меню вайпа", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "📝 <b>Вайп логов завершён</b>\n\n" + "\n".join(results),
        reply_markup=kb.as_markup()
    )


@router.callback_query(F.data == "owner_wipe_users")
async def cb_owner_wipe_users(callback: CallbackQuery):
    """Подтверждение вайпа пользователей."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="⚠️ Да, удалить всех", callback_data="owner_wipe_users_exec")
    kb.button(text="❌ Отмена", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "👥 <b>Вайп пользователей и чатов</b>\n\n"
        "Это удалит:\n"
        "• Всех пользователей\n"
        "• Все группы/чаты\n"
        "• Приватные чаты\n"
        "• Админов и блеклисты\n\n"
        "⚠️ <b>ОПАСНО!</b> Бот забудет всех!",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "owner_wipe_users_exec")
async def cb_owner_wipe_users_exec(callback: CallbackQuery):
    """Выполнение вайпа пользователей."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer("⏳ Выполняется...")
    
    results = []
    try:
        from app.database.models import User, Chat, PrivateChat, Admin
        from sqlalchemy import delete
        
        async with get_session()() as session:
            # Порядок важен из-за FK
            r1 = await session.execute(delete(Admin))
            r3 = await session.execute(delete(PrivateChat))
            r4 = await session.execute(delete(Chat))
            # User удаляем последним (много FK ссылаются на него)
            await session.commit()
            results.append(f"✅ Админы: {r1.rowcount}")
            results.append(f"✅ Блеклист: {r2.rowcount}")
            results.append(f"✅ Приватные чаты: {r3.rowcount}")
            results.append(f"✅ Группы: {r4.rowcount}")
    except Exception as e:
        results.append(f"❌ Ошибка: {str(e)[:50]}")

    
    logger.warning(f"USERS WIPE executed by owner {callback.from_user.id}")
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 К меню вайпа", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "👥 <b>Вайп пользователей завершён</b>\n\n" + "\n".join(results),
        reply_markup=kb.as_markup()
    )


@router.callback_query(F.data == "owner_wipe_achievements")
async def cb_owner_wipe_achievements(callback: CallbackQuery):
    """Подтверждение вайпа достижений."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, сбросить прогресс", callback_data="owner_wipe_achievements_exec")
    kb.button(text="❌ Отмена", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "🏆 <b>Вайп достижений и квестов</b>\n\n"
        "Это удалит:\n"
        "• Все достижения пользователей\n"
        "• Прогресс квестов\n"
        "• Гильдии и участников\n"
        "• Турниры и рейтинги\n\n"
        "⚠️ Весь прогресс будет потерян!",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "owner_wipe_achievements_exec")
async def cb_owner_wipe_achievements_exec(callback: CallbackQuery):
    """Выполнение вайпа достижений."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    results = []
    try:
        from app.database.models import (
            UserAchievement, Achievement, UserQuest, Quest,
            GuildMember, Guild, TournamentScore, Tournament,
            UserReputation, ReputationHistory
        )
        from sqlalchemy import delete
        
        async with get_session()() as session:
            tables = [
                (TournamentScore, "TournamentScore"),
                (Tournament, "Tournament"),
                (ReputationHistory, "ReputationHistory"),
                (UserReputation, "UserReputation"),
                (UserAchievement, "UserAchievement"),
                (Achievement, "Achievement"),
                (UserQuest, "UserQuest"),
                (Quest, "Quest"),
                (GuildMember, "GuildMember"),
                (Guild, "Guild"),
            ]
            for model, name in tables:
                try:
                    r = await session.execute(delete(model))
                    results.append(f"✅ {name}: {r.rowcount}")
                except Exception as e:
                    results.append(f"⚠️ {name}: {str(e)[:30]}")
            await session.commit()
    except Exception as e:
        results.append(f"❌ Ошибка: {str(e)[:50]}")

    
    logger.warning(f"ACHIEVEMENTS WIPE executed by owner {callback.from_user.id}")
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 К меню вайпа", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "🏆 <b>Вайп достижений завершён</b>\n\n" + "\n".join(results),
        reply_markup=kb.as_markup()
    )
    await callback.answer("Готово!", show_alert=True)


@router.callback_query(F.data == "owner_wipe_all_confirm")
async def cb_owner_wipe_all_confirm(callback: CallbackQuery):
    """Финальное подтверждение полного вайпа."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="⚠️ ДА, УДАЛИТЬ ВСЁ", callback_data="owner_wipe_execute")
    kb.button(text="❌ Отмена", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "🗑 <b>ПОЛНЫЙ ВАЙП</b>\n\n"
        "⚠️ <b>ВНИМАНИЕ!</b> Это действие:\n"
        "• Удалит ВСЮ память бота (ChromaDB)\n"
        "• Очистит ВСЕ таблицы базы данных\n"
        "• Удалит всех пользователей, чаты, статистику\n"
        "• Удалит все цитаты, достижения, квесты\n\n"
        "❗ <b>ЭТО ДЕЙСТВИЕ НЕОБРАТИМО!</b>\n\n"
        "Ты уверен?",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


# ============================================================================
# Формат ответов (голос/видео)
# ============================================================================

@router.callback_query(F.data == "owner_format_menu")
async def cb_owner_format_menu(callback: CallbackQuery):
    """Меню настройки формата ответов."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    from app.services.ollama_client import get_global_voice_chance, get_global_video_chance
    
    voice_pct = int(get_global_voice_chance() * 100)
    video_pct = int(get_global_video_chance() * 100)
    
    kb = InlineKeyboardBuilder()
    kb.button(text=f"🎤 Голос: {voice_pct}%", callback_data="owner_voice_menu")
    kb.button(text=f"🎬 Видео: {video_pct}%", callback_data="owner_video_menu")
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "🎤 <b>Формат ответов</b>\n\n"
        "Глобальные настройки формата ответов Олега:\n\n"
        "• <b>Голос</b> — шанс ответить голосовым сообщением\n"
        "• <b>Видео</b> — шанс ответить видеосообщением (кружочком)\n\n"
        "Приоритет: Видео → Голос → Текст",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "owner_voice_menu")
async def cb_owner_voice_menu(callback: CallbackQuery):
    """Меню настройки голоса."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    for pct in [0, 10, 25, 50, 75, 100]:
        label = "Выкл" if pct == 0 else f"{pct}%"
        kb.button(text=label, callback_data=f"owner_setvoice_{pct}")
    kb.button(text="✏️ Свой %", callback_data="owner_voice_custom")
    kb.button(text="🔙 Назад", callback_data="owner_format_menu")
    kb.adjust(3, 3, 1, 1)
    
    await callback.message.edit_text(
        "🎤 <b>Шанс голосового ответа</b>\n\n"
        "Выбери вероятность голосового ответа:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("owner_setvoice_"))
async def cb_owner_set_voice(callback: CallbackQuery):
    """Установить шанс голоса."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    pct = int(callback.data.split("_")[2])
    
    from app.services.ollama_client import set_global_voice_chance
    set_global_voice_chance(pct / 100.0)
    
    await callback.answer(f"✅ Голос установлен на {pct}%", show_alert=True)
    await cb_owner_format_menu(callback)


@router.callback_query(F.data == "owner_voice_custom")
async def cb_owner_voice_custom(callback: CallbackQuery, state: FSMContext):
    """Запросить ввод своего процента для голоса."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await state.set_state(OwnerStates.waiting_voice_percent)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data="owner_voice_menu")
    
    await callback.message.edit_text(
        "🎤 <b>Свой процент для голоса</b>\n\n"
        "Введи число от 0 до 100:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.message(OwnerStates.waiting_voice_percent)
async def handle_voice_percent(msg: Message, state: FSMContext):
    """Обработка ввода процента для голоса."""
    if not is_owner(msg.from_user.id):
        return
    
    try:
        pct = int(msg.text.strip())
        if not 0 <= pct <= 100:
            raise ValueError
        
        from app.services.ollama_client import set_global_voice_chance
        set_global_voice_chance(pct / 100.0)
        
        await msg.answer(f"✅ Голос установлен на {pct}%")
        await state.clear()
        
        # Показываем меню формата
        from app.services.ollama_client import get_global_voice_chance, get_global_video_chance
        voice_pct = int(get_global_voice_chance() * 100)
        video_pct = int(get_global_video_chance() * 100)
        
        kb = InlineKeyboardBuilder()
        kb.button(text=f"🎤 Голос: {voice_pct}%", callback_data="owner_voice_menu")
        kb.button(text=f"🎬 Видео: {video_pct}%", callback_data="owner_video_menu")
        kb.button(text="🔙 Назад", callback_data="owner_main")
        kb.adjust(1)
        
        await msg.answer(
            "🎤 <b>Формат ответов</b>\n\n"
            "Глобальные настройки формата ответов Олега:\n\n"
            "• <b>Голос</b> — шанс ответить голосовым сообщением\n"
            "• <b>Видео</b> — шанс ответить видеосообщением (кружочком)\n\n"
            "Приоритет: Видео → Голос → Текст",
            reply_markup=kb.as_markup()
        )
    except ValueError:
        await msg.answer("❌ Введи число от 0 до 100")


@router.callback_query(F.data == "owner_video_menu")
async def cb_owner_video_menu(callback: CallbackQuery):
    """Меню настройки видео."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    for pct in [0, 10, 25, 50, 75, 100]:
        label = "Выкл" if pct == 0 else f"{pct}%"
        kb.button(text=label, callback_data=f"owner_setvideo_{pct}")
    kb.button(text="✏️ Свой %", callback_data="owner_video_custom")
    kb.button(text="🔙 Назад", callback_data="owner_format_menu")
    kb.adjust(3, 3, 1, 1)
    
    await callback.message.edit_text(
        "🎬 <b>Шанс видео-ответа</b>\n\n"
        "Выбери вероятность видео-ответа (кружочка):",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("owner_setvideo_"))
async def cb_owner_set_video(callback: CallbackQuery):
    """Установить шанс видео."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    pct = int(callback.data.split("_")[2])
    
    from app.services.ollama_client import set_global_video_chance
    set_global_video_chance(pct / 100.0)
    
    await callback.answer(f"✅ Видео установлено на {pct}%", show_alert=True)
    await cb_owner_format_menu(callback)


@router.callback_query(F.data == "owner_video_custom")
async def cb_owner_video_custom(callback: CallbackQuery, state: FSMContext):
    """Запросить ввод своего процента для видео."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await state.set_state(OwnerStates.waiting_video_percent)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data="owner_video_menu")
    
    await callback.message.edit_text(
        "🎬 <b>Свой процент для видео</b>\n\n"
        "Введи число от 0 до 100:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.message(OwnerStates.waiting_video_percent)
async def handle_video_percent(msg: Message, state: FSMContext):
    """Обработка ввода процента для видео."""
    if not is_owner(msg.from_user.id):
        return
    
    try:
        pct = int(msg.text.strip())
        if not 0 <= pct <= 100:
            raise ValueError
        
        from app.services.ollama_client import set_global_video_chance
        set_global_video_chance(pct / 100.0)
        
        await msg.answer(f"✅ Видео установлено на {pct}%")
        await state.clear()
        
        # Показываем меню формата
        from app.services.ollama_client import get_global_voice_chance, get_global_video_chance
        voice_pct = int(get_global_voice_chance() * 100)
        video_pct = int(get_global_video_chance() * 100)
        
        kb = InlineKeyboardBuilder()
        kb.button(text=f"🎤 Голос: {voice_pct}%", callback_data="owner_voice_menu")
        kb.button(text=f"🎬 Видео: {video_pct}%", callback_data="owner_video_menu")
        kb.button(text="🔙 Назад", callback_data="owner_main")
        kb.adjust(1)
        
        await msg.answer(
            "🎤 <b>Формат ответов</b>\n\n"
            "Глобальные настройки формата ответов Олега:\n\n"
            "• <b>Голос</b> — шанс ответить голосовым сообщением\n"
            "• <b>Видео</b> — шанс ответить видеосообщением (кружочком)\n\n"
            "Приоритет: Видео → Голос → Текст",
            reply_markup=kb.as_markup()
        )
    except ValueError:
        await msg.answer("❌ Введи число от 0 до 100")
