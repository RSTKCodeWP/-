"""
Главный модуль Telegram-бота для работы с временной почтой
Управление через Reply-кнопки (постоянная клавиатура)
"""

import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from telegram.constants import ParseMode
from dotenv import load_dotenv

from provider_manager import ProviderManager
from database import Database
from admin import AdminPanel

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Инициализация базы данных
db = Database()

# Инициализация админ-панели
admin_ids = []
try:
    admin_id = os.getenv("ADMIN_ID")
    if admin_id:
        admin_ids = [int(admin_id)]
        logger.info(f"Админ ID загружен: {admin_ids}")
except Exception as e:
    logger.warning(f"Не удалось загрузить ADMIN_ID: {e}")

admin_panel = AdminPanel(admin_ids) if admin_ids else None


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Создает главную Reply-клавиатуру бота"""
    keyboard = [
        [KeyboardButton("📧 Создать новую почту"), KeyboardButton("📬 Проверить почту")],
        [KeyboardButton("📮 Мой email"), KeyboardButton("🗑️ Удалить почту")],
        [KeyboardButton("⚙️ Настройки"), KeyboardButton("ℹ️ Информация")],
        [KeyboardButton("❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Добавляем пользователя в базу данных
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Я бот для создания временных email-адресов.\n"
        "С моей помощью ты можешь:\n\n"
        "📧 Генерировать временные email-адреса\n"
        "📬 Получать входящие письма и коды подтверждения\n"
        "🗑️ Управлять своей временной почтой\n\n"
        "Используй кнопки ниже для управления! 👇"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard()
    )


async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик сообщения для рассылки"""
    user_id = update.effective_user.id
    
    # Проверяем, ожидается ли сообщение для рассылки
    if not context.user_data.get('awaiting_broadcast'):
        return False
    
    if not admin_panel or not admin_panel.is_admin(user_id):
        return False
    
    # Очищаем флаг
    context.user_data['awaiting_broadcast'] = False
    
    try:
        # Определяем тип сообщения
        message_text = None
        photo_id = None
        video_id = None
        document_id = None
        caption = None
        
        if update.message.photo:
            photo_id = update.message.photo[-1].file_id
            caption = update.message.caption
        elif update.message.video:
            video_id = update.message.video.file_id
            caption = update.message.caption
        elif update.message.document:
            document_id = update.message.document.file_id
            caption = update.message.caption
        elif update.message.text:
            message_text = update.message.text
        else:
            await update.message.reply_text("❌ Неподдерживаемый тип сообщения")
            return True
        
        # Сохраняем данные для рассылки
        context.user_data['broadcast_data'] = {
            'message': message_text,
            'photo_id': photo_id,
            'video_id': video_id,
            'document_id': document_id,
            'caption': caption
        }
        
        # Получаем количество пользователей
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM users")
            user_count = cursor.fetchone()['count']
        
        # Создаем кнопки подтверждения
        keyboard = [
            [InlineKeyboardButton("✅ Отправить всем", callback_data="broadcast_confirm")],
            [InlineKeyboardButton("❌ Отмена", callback_data="broadcast_cancel")]
        ]
        
        # Отправляем предпросмотр с той же медиа
        if photo_id:
            # Показываем реальную подпись или сообщаем, что ее нет
            caption_preview = caption if caption else "(без подписи)"
            preview_text = (
                f"📢 <b>ПРЕДПРОСМОТР РАССЫЛКИ</b>\n\n"
                f"👥 Получателей: {user_count}\n"
                f"{'='*30}\n\n"
                f"{caption_preview}\n\n"
                f"{'='*30}\n"
                f"Подтвердите отправку:"
            )
            await update.message.reply_photo(
                photo=photo_id,
                caption=preview_text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        elif video_id:
            caption_preview = caption if caption else "(без подписи)"
            preview_text = (
                f"📢 <b>ПРЕДПРОСМОТР РАССЫЛКИ</b>\n\n"
                f"👥 Получателей: {user_count}\n"
                f"{'='*30}\n\n"
                f"{caption_preview}\n\n"
                f"{'='*30}\n"
                f"Подтвердите отправку:"
            )
            await update.message.reply_video(
                video=video_id,
                caption=preview_text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        elif document_id:
            caption_preview = caption if caption else "(без подписи)"
            preview_text = (
                f"📢 <b>ПРЕДПРОСМОТР РАССЫЛКИ</b>\n\n"
                f"👥 Получателей: {user_count}\n"
                f"{'='*30}\n\n"
                f"{caption_preview}\n\n"
                f"{'='*30}\n"
                f"Подтвердите отправку:"
            )
            await update.message.reply_document(
                document=document_id,
                caption=preview_text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            # Для текста показываем само сообщение + кнопки
            full_preview = (
                f"📢 <b>ПРЕДПРОСМОТР РАССЫЛКИ</b>\n\n"
                f"👥 Получателей: {user_count}\n"
                f"{'='*30}\n\n"
                f"{message_text}\n\n"
                f"{'='*30}\n"
                f"Подтвердите отправку:"
            )
            await update.message.reply_text(
                full_preview,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
    except Exception as e:
        logger.error(f"Ошибка при подготовке рассылки: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    return True


async def handle_media_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик медиа-сообщений (фото, видео, документы)"""
    # Проверяем, не ожидается ли рассылка
    await handle_broadcast_message(update, context)


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (нажатий на кнопки)"""
    # Сначала проверяем, не ожидается ли рассылка
    if await handle_broadcast_message(update, context):
        return
    
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "📧 Создать новую почту":
        await create_email_handler(update, context)
    
    elif text == "📬 Проверить почту":
        await check_email_handler(update, context)
    
    elif text == "📮 Мой email":
        await my_email_handler(update, context)
    
    elif text == "🗑️ Удалить почту":
        await delete_email_handler(update, context)
    
    elif text == "⚙️ Настройки":
        await settings_handler(update, context)
    
    elif text == "ℹ️ Информация":
        await info_handler(update, context)
    
    elif text == "❓ Помощь":
        await help_handler(update, context)
    
    else:
        await update.message.reply_text(
            "Используйте кнопки ниже для управления ботом.",
            reply_markup=get_main_keyboard()
        )
        return


async def create_email_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик создания нового email"""
    user_id = update.effective_user.id
    
    msg = await update.message.reply_text("⏳ Генерирую новый email-адрес...")
    
    try:
        async with ProviderManager() as provider_manager:
            # Получаем предпочитаемый провайдер пользователя
            preferred_provider = db.get_user_preferred_provider(user_id)
            
            # Генерируем email с токенами
            email, provider_name, auth_token, auth_password = await provider_manager.generate_email(preferred_provider)
            
            # Сохраняем email с информацией о провайдере и токенами
            db.set_user_email(user_id, email, provider_name, auth_token, auth_password)
            
            text = (
                "✅ <b>Email успешно создан!</b>\n\n"
                f"📧 Ваш адрес: <code>{email}</code>\n"
                f"🔧 Провайдер: <b>{provider_name}</b>\n\n"
                "Используйте этот адрес для регистрации на сайтах.\n"
                "Нажмите на адрес, чтобы скопировать его.\n\n"
                "Для проверки входящих писем нажмите кнопку «📬 Проверить почту»."
            )
            
            await msg.edit_text(text, parse_mode=ParseMode.HTML)
            
    except Exception as e:
        logger.error(f"Ошибка при создании email: {e}")
        await msg.edit_text(
            "❌ Произошла ошибка при создании email.\n"
            f"Детали: {str(e)}\n\n"
            "Попробуйте еще раз, нажав кнопку «📧 Создать новую почту»."
        )


async def check_email_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик проверки почты"""
    user_id = update.effective_user.id
    email = db.get_user_email(user_id)
    
    if not email:
        await update.message.reply_text(
            "❌ У вас нет активного email-адреса.\n\n"
            "Сначала создайте новый email, нажав кнопку «📧 Создать новую почту».",
            reply_markup=get_main_keyboard()
        )
        return
    
    msg = await update.message.reply_text("⏳ Проверяю входящие письма...")
    
    try:
        async with ProviderManager() as provider_manager:
            # Получаем полную информацию о email включая токены
            email_info = db.get_user_email_full_info(user_id)
            auth_token = email_info.get('auth_token') if email_info else None
            auth_password = email_info.get('auth_password') if email_info else None
            provider_name = email_info.get('provider') if email_info else None
            
            messages = await provider_manager.get_messages(email, auth_token, auth_password, provider_name)
            
            if not messages:
                await msg.edit_text(
                    f"📭 <b>Входящих писем пока нет.</b>\n\n"
                    f"📧 Ваш email: <code>{email}</code>\n\n"
                    f"Используйте этот адрес для регистрации на сайтах, "
                    f"затем снова нажмите кнопку «📬 Проверить почту».",
                    parse_mode=ParseMode.HTML
                )
                return
            
            # Создаем Inline-кнопки для каждого письма
            keyboard = []
            for msg_data in messages[:10]:
                msg_id = msg_data.get("id")
                subject = msg_data.get("subject", "Без темы")[:30]
                from_email = msg_data.get("from", "")[:25]
                
                button_text = f"📩 {subject} | {from_email}"
                keyboard.append([
                    InlineKeyboardButton(button_text, callback_data=f"read_{msg_id}")
                ])
            
            # Кнопка обновления
            keyboard.append([InlineKeyboardButton("🔄 Обновить список", callback_data="refresh_emails")])
            
            # Получаем информацию о провайдере
            email_with_provider = db.get_user_email_with_provider(user_id)
            provider_name = email_with_provider[1] if email_with_provider else "Unknown"
            
            text = (
                f"📬 <b>Входящие письма: {len(messages)}</b>\n\n"
                f"📧 Email: <code>{email}</code>\n"
                f"🔧 Провайдер: <b>{provider_name}</b>\n\n"
                f"Нажмите на письмо для просмотра содержимого:"
            )
            
            await msg.edit_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except Exception as e:
        logger.error(f"Ошибка при проверке почты: {e}")
        await msg.edit_text(
            "❌ Произошла ошибка при проверке почты.\n"
            "Попробуйте еще раз, нажав кнопку «📬 Проверить почту»."
        )


async def my_email_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Мой email'"""
    user_id = update.effective_user.id
    email_with_provider = db.get_user_email_with_provider(user_id)
    
    if email_with_provider:
        email, provider = email_with_provider
        text = (
            f"📮 <b>Ваш текущий email:</b>\n\n"
            f"<code>{email}</code>\n"
            f"🔧 Провайдер: <b>{provider}</b>\n\n"
            f"Нажмите на адрес для копирования.\n\n"
            f"Используйте этот адрес для регистрации на сайтах, "
            f"затем нажмите «📬 Проверить почту» для получения писем."
        )
        await update.message.reply_text(
            text, 
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_keyboard()
        )
    else:
        text = (
            "❌ У вас пока нет активного email-адреса.\n\n"
            "Нажмите кнопку «📧 Создать новую почту» для генерации."
        )
        await update.message.reply_text(
            text,
            reply_markup=get_main_keyboard()
        )


async def delete_email_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки удаления email"""
    user_id = update.effective_user.id
    email = db.get_user_email(user_id)
    
    if not email:
        await update.message.reply_text(
            "❌ У вас нет активного email-адреса для удаления.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Inline-кнопки для подтверждения
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data="confirm_delete"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_delete")
        ]
    ]
    
    text = (
        f"🗑️ <b>Подтверждение удаления</b>\n\n"
        f"Вы действительно хотите удалить email?\n\n"
        f"📧 <code>{email}</code>\n\n"
        f"⚠️ После удаления все письма будут потеряны!"
    )
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки информации о боте"""
    stats = db.get_stats()
    
    info_text = (
        "ℹ️ <b>О боте</b>\n\n"
        "Этот бот позволяет создавать временные email-адреса "
        "для получения кодов подтверждения и регистрации на сайтах.\n\n"
        "🔹 <b>Поддерживаемые провайдеры:</b>\n"
        "  • Mail.tm (приоритет 1 - самый надежный)\n"
        "  • TempMail.lol (приоритет 2)\n"
        "  • 1SecMail (приоритет 3)\n\n"
        "🔄 <b>Автоматическое переключение:</b>\n"
        "При недоступности одного сервиса бот автоматически\n"
        "использует альтернативный провайдер.\n\n"
        f"📊 <b>Статистика бота:</b>\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"📧 Всего email создано: {stats['total_emails']}\n"
        f"✅ Активных email: {stats['active_emails']}\n\n"
        "⚠️ <b>Важно знать:</b>\n"
        "• Письма хранятся ограниченное время\n"
        "• Не используйте для важной информации\n"
        "• Email-адреса публичные и временные"
    )
    
    await update.message.reply_text(
        info_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard()
    )


async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки настроек"""
    user_id = update.effective_user.id
    current_provider = db.get_user_preferred_provider(user_id)
    
    # Создаем inline-кнопки для выбора провайдера
    keyboard = [
        [InlineKeyboardButton(f"{'✅' if current_provider == 'Mail.tm' else '⚪️'} Mail.tm (Приоритет 1)", callback_data="set_provider_Mail.tm")],
        [InlineKeyboardButton(f"{'✅' if current_provider == 'TempMail.lol' else '⚪️'} TempMail.lol (Приоритет 2)", callback_data="set_provider_TempMail.lol")],
        [InlineKeyboardButton(f"{'✅' if current_provider == '1SecMail' else '⚪️'} 1SecMail (Приоритет 3)", callback_data="set_provider_1SecMail")],
        [InlineKeyboardButton("🔄 Авто (по приоритету)", callback_data="set_provider_auto")]
    ]
    
    settings_text = (
        "⚙️ <b>Настройки бота</b>\n\n"
        f"<b>Текущий провайдер:</b> {current_provider or 'Авто'}\n\n"
        "Выберите предпочитаемый провайдер для создания email-адресов:\n\n"
        "• <b>Mail.tm</b> - самый надежный, поддерживает JWT авторизацию\n"
        "• <b>TempMail.lol</b> - быстрый и стабильный сервис\n"
        "• <b>1SecMail</b> - простой сервис, может блокировать письма от Yandex\n\n"
        "При выборе 'Авто' бот будет автоматически использовать доступные провайдеры по приоритету."
    )
    
    await update.message.reply_text(
        settings_text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки помощи"""
    help_text = (
        "❓ <b>Как пользоваться ботом:</b>\n\n"
        "1️⃣ Нажми <b>«📧 Создать новую почту»</b> для генерации временного email\n"
        "2️⃣ Используй полученный адрес для регистрации на нужном сайте\n"
        "3️⃣ Нажми <b>«📬 Проверить почту»</b> для получения писем\n"
        "4️⃣ Выбери нужное письмо из списка для просмотра содержимого\n\n"
        "📮 Кнопка <b>«Мой email»</b> показывает текущий активный адрес\n"
        "🗑️ Кнопка <b>«Удалить почту»</b> удаляет текущий email\n"
        "⚙️ Кнопка <b>«Настройки»</b> позволяет выбрать провайдер\n\n"
        "⚠️ <b>Важно знать:</b>\n"
        "• Письма хранятся временно (несколько часов)\n"
        "• Один пользователь = один активный email\n"
        "• При создании нового email старый автоматически удаляется\n"
        "• Не используйте для важной информации!"
    )
    
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard()
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /admin"""
    if not admin_panel:
        await update.message.reply_text("❌ Админ-панель не настроена")
        return
    
    await admin_panel.show_admin_panel(update, context)


async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик детальной статистики"""
    query = update.callback_query
    await query.answer()
    
    if not admin_panel or not admin_panel.is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Доступ запрещен")
        return
    
    stats = db.get_stats()
    
    # Получаем дополнительную статистику
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Статистика по провайдерам
        cursor.execute("""
            SELECT provider, COUNT(*) as count 
            FROM user_emails 
            WHERE is_active = 1
            GROUP BY provider
        """)
        provider_stats = cursor.fetchall()
        
        # Последние зарегистрированные пользователи
        cursor.execute("""
            SELECT COUNT(*) as new_users
            FROM users
            WHERE created_at >= datetime('now', '-24 hours')
        """)
        new_users_24h = cursor.fetchone()['new_users']
    
    provider_text = "\n".join([f"  • {row['provider']}: {row['count']}" for row in provider_stats])
    
    text = (
        "📊 <b>ДЕТАЛЬНАЯ СТАТИСТИКА</b>\n\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"🆕 Новых за 24 часа: {new_users_24h}\n\n"
        f"📧 Всего email создано: {stats['total_emails']}\n"
        f"✅ Активных email: {stats['active_emails']}\n\n"
        f"<b>По провайдерам:</b>\n{provider_text}\n\n"
        f"📨 Писем обработано: {stats.get('total_messages', 0)}"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик списка пользователей"""
    query = update.callback_query
    await query.answer()
    
    if not admin_panel or not admin_panel.is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Доступ запрещен")
        return
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.user_id, u.username, u.first_name, 
                   ue.email, ue.provider, u.created_at
            FROM users u
            LEFT JOIN user_emails ue ON u.user_id = ue.user_id AND ue.is_active = 1
            ORDER BY u.created_at DESC
            LIMIT 20
        """)
        users = cursor.fetchall()
    
    if not users:
        text = "👥 <b>СПИСОК ПОЛЬЗОВАТЕЛЕЙ</b>\n\nПользователей пока нет."
    else:
        text = "👥 <b>СПИСОК ПОЛЬЗОВАТЕЛЕЙ</b> (последние 20):\n\n"
        for user in users:
            username = user['username'] or 'N/A'
            name = user['first_name'] or 'N/A'
            email = user['email'] or 'нет email'
            provider = user['provider'] or ''
            text += f"• {name} (@{username})\n"
            text += f"  ID: <code>{user['user_id']}</code>\n"
            text += f"  Email: {email[:30]}... [{provider}]\n\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик рассылки"""
    query = update.callback_query
    await query.answer()
    
    if not admin_panel or not admin_panel.is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Доступ запрещен")
        return
    
    text = (
        "📢 <b>РАССЫЛКА СООБЩЕНИЙ</b>\n\n"
        "Отправьте сообщение для рассылки:\n\n"
        "• <b>Текст</b> - просто напишите сообщение\n"
        "• 🖼️ <b>Фото</b> - отправьте фото (можно с подписью)\n"
        "• 🎥 <b>Видео</b> - отправьте видео (можно с подписью)\n"
        "• 📄 <b>Документ</b> - отправьте файл (можно с подписью)\n\n"
        "⚠️ Сообщение будет отправлено ВСЕМ пользователям!\n\n"
        "Для отмены используйте /cancel"
    )
    
    # Устанавливаем состояние ожидания сообщения для рассылки
    context.user_data['awaiting_broadcast'] = True
    
    await query.edit_message_text(text, parse_mode=ParseMode.HTML)


async def admin_cleanup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик очистки БД"""
    query = update.callback_query
    await query.answer()
    
    if not admin_panel or not admin_panel.is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Доступ запрещен")
        return
    
    keyboard = [
        [InlineKeyboardButton("🗑️ Удалить неактивные email", callback_data="admin_cleanup_confirm")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]
    ]
    
    text = (
        "🗑️ <b>ОЧИСТКА БАЗЫ ДАННЫХ</b>\n\n"
        "Выберите действие:\n\n"
        "• Удалить неактивные email - удалит все деактивированные email-адреса\n\n"
        "⚠️ Это действие необратимо!"
    )
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_cleanup_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение очистки БД"""
    query = update.callback_query
    await query.answer("Очистка...")
    
    if not admin_panel or not admin_panel.is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Доступ запрещен")
        return
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_emails WHERE is_active = 0")
        deleted = cursor.rowcount
        conn.commit()
    
    text = f"✅ Очистка завершена!\n\nУдалено неактивных email: {deleted}"
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def broadcast_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение и отправка рассылки"""
    query = update.callback_query
    await query.answer("Отправляю...")
    
    if not admin_panel or not admin_panel.is_admin(update.effective_user.id):
        await query.edit_message_caption(caption="❌ Доступ запрещен")
        return
    
    broadcast_data = context.user_data.get('broadcast_data')
    if not broadcast_data:
        await query.edit_message_caption(caption="❌ Данные рассылки не найдены")
        return
    
    try:
        # Обновляем сообщение
        await query.edit_message_caption(
            caption="⏳ Отправляю рассылку...",
            parse_mode=ParseMode.HTML
        )
        
        # Отправляем рассылку
        success, failed = await admin_panel.broadcast_message(
            context,
            message=broadcast_data.get('message'),
            photo_id=broadcast_data.get('photo_id'),
            video_id=broadcast_data.get('video_id'),
            document_id=broadcast_data.get('document_id'),
            caption=broadcast_data.get('caption')
        )
        
        result_text = (
            f"✅ <b>Рассылка завершена!</b>\n\n"
            f"✅ Успешно: {success}\n"
            f"❌ Ошибок: {failed}"
        )
        
        await query.edit_message_caption(
            caption=result_text,
            parse_mode=ParseMode.HTML
        )
        
        # Очищаем данные
        context.user_data.pop('broadcast_data', None)
        
    except Exception as e:
        logger.error(f"Ошибка при рассылке: {e}")
        try:
            await query.edit_message_caption(
                caption=f"❌ Ошибка при рассылке: {str(e)}",
                parse_mode=ParseMode.HTML
            )
        except:
            await query.message.reply_text(f"❌ Ошибка при рассылке: {str(e)}")


async def broadcast_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена рассылки"""
    query = update.callback_query
    await query.answer("Отменено")
    
    if not admin_panel or not admin_panel.is_admin(update.effective_user.id):
        await query.edit_message_caption(caption="❌ Доступ запрещен")
        return
    
    # Очищаем данные
    context.user_data.pop('broadcast_data', None)
    
    try:
        await query.edit_message_caption(
            caption="❌ Рассылка отменена",
            parse_mode=ParseMode.HTML
        )
    except:
        await query.message.reply_text("❌ Рассылка отменена")


async def admin_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню админ-панели"""
    query = update.callback_query
    await query.answer()
    
    if not admin_panel or not admin_panel.is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Доступ запрещен")
        return
    
    stats = db.get_stats()
    
    text = (
        "👑 <b>АДМИН-ПАНЕЛЬ</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"📧 Всего email: {stats['total_emails']}\n"
        f"✅ Активных email: {stats['active_emails']}\n"
        f"📨 Писем обработано: {stats.get('total_messages', 0)}\n\n"
        "Выберите действие:"
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 Детальная статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Список пользователей", callback_data="admin_users")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🗑️ Очистка БД", callback_data="admin_cleanup")],
    ]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# === Callback-обработчики для Inline-кнопок ===

async def read_message_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик чтения письма"""
    query = update.callback_query
    await query.answer()
    
    message_id = query.data.split("_")[1]
    user_id = update.effective_user.id
    email = db.get_user_email(user_id)
    
    if not email:
        await query.edit_message_text(
            "❌ Email не найден.",
        )
        return
    
    await query.edit_message_text("⏳ Загружаю письмо...")
    
    try:
        async with ProviderManager() as provider_manager:
            # Получаем полную информацию о email включая токены
            email_info = db.get_user_email_full_info(user_id)
            auth_token = email_info.get('auth_token') if email_info else None
            auth_password = email_info.get('auth_password') if email_info else None
            provider_name = email_info.get('provider') if email_info else None
            
            message = await provider_manager.read_message(email, message_id, auth_token, auth_password, provider_name)
            
            if not message:
                await query.edit_message_text("❌ Не удалось загрузить письмо.")
                return
            
            text = provider_manager.format_message_full(message)
            
            keyboard = [
                [InlineKeyboardButton("◀️ К списку писем", callback_data="refresh_emails")]
            ]
            
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except Exception as e:
        logger.error(f"Ошибка при чтении письма: {e}")
        await query.edit_message_text("❌ Произошла ошибка при чтении письма.")


async def refresh_emails_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик обновления списка писем"""
    query = update.callback_query
    await query.answer("Обновляю...")
    
    user_id = update.effective_user.id
    email = db.get_user_email(user_id)
    
    if not email:
        await query.edit_message_text("❌ Email не найден.")
        return
    
    await query.edit_message_text("⏳ Проверяю входящие письма...")
    
    try:
        async with ProviderManager() as provider_manager:
            # Получаем полную информацию о email включая токены
            email_info = db.get_user_email_full_info(user_id)
            auth_token = email_info.get('auth_token') if email_info else None
            auth_password = email_info.get('auth_password') if email_info else None
            provider_name = email_info.get('provider') if email_info else None
            
            messages = await provider_manager.get_messages(email, auth_token, auth_password, provider_name)
            
            if not messages:
                await query.edit_message_text(
                    f"📭 <b>Входящих писем пока нет.</b>\n\n"
                    f"📧 Email: <code>{email}</code>\n\n"
                    f"Используйте кнопку «📬 Проверить почту» для повторной проверки.",
                    parse_mode=ParseMode.HTML
                )
                return
            
            keyboard = []
            for msg_data in messages[:10]:
                msg_id = msg_data.get("id")
                subject = msg_data.get("subject", "Без темы")[:30]
                from_email = msg_data.get("from", "")[:25]
                
                button_text = f"📩 {subject} | {from_email}"
                keyboard.append([
                    InlineKeyboardButton(button_text, callback_data=f"read_{msg_id}")
                ])
            
            keyboard.append([InlineKeyboardButton("🔄 Обновить список", callback_data="refresh_emails")])
            
            # Получаем информацию о провайдере
            email_with_provider = db.get_user_email_with_provider(user_id)
            provider_name = email_with_provider[1] if email_with_provider else "Unknown"
            
            text = (
                f"📬 <b>Входящие письма: {len(messages)}</b>\n\n"
                f"📧 Email: <code>{email}</code>\n"
                f"🔧 Провайдер: <b>{provider_name}</b>\n\n"
                f"Нажмите на письмо для просмотра:"
            )
            
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except Exception as e:
        logger.error(f"Ошибка при обновлении писем: {e}")
        await query.edit_message_text("❌ Произошла ошибка при обновлении.")


async def confirm_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик подтверждения удаления"""
    query = update.callback_query
    await query.answer("Email удален")
    
    user_id = update.effective_user.id
    db.delete_user_email(user_id)
    
    await query.edit_message_text(
        "✅ <b>Email успешно удален!</b>\n\n"
        "Вы можете создать новый email-адрес, нажав кнопку «📧 Создать новую почту».",
        parse_mode=ParseMode.HTML
    )


async def cancel_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик отмены удаления"""
    query = update.callback_query
    await query.answer("Отменено")
    
    await query.edit_message_text(
        "❌ Удаление отменено.\n\n"
        "Ваш email сохранен. Используйте кнопки для управления."
    )


async def set_provider_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора провайдера"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    provider = query.data.replace("set_provider_", "")
    
    if provider == "auto":
        db.set_user_preferred_provider(user_id, None)
        await query.answer("✅ Включен автоматический выбор провайдера")
        provider_text = "Авто (по приоритету)"
    else:
        db.set_user_preferred_provider(user_id, provider)
        await query.answer(f"✅ Провайдер изменен на {provider}")
        provider_text = provider
    
    # Обновляем сообщение с настройками
    keyboard = [
        [InlineKeyboardButton(f"{'✅' if provider == 'Mail.tm' else '⚪️'} Mail.tm (Приоритет 1)", callback_data="set_provider_Mail.tm")],
        [InlineKeyboardButton(f"{'✅' if provider == 'TempMail.lol' else '⚪️'} TempMail.lol (Приоритет 2)", callback_data="set_provider_TempMail.lol")],
        [InlineKeyboardButton(f"{'✅' if provider == '1SecMail' else '⚪️'} 1SecMail (Приоритет 3)", callback_data="set_provider_1SecMail")],
        [InlineKeyboardButton("🔄 Авто (по приоритету)", callback_data="set_provider_auto")]
    ]
    
    settings_text = (
        "⚙️ <b>Настройки бота</b>\n\n"
        f"<b>Текущий провайдер:</b> {provider_text}\n\n"
        "Выберите предпочитаемый провайдер для создания email-адресов:\n\n"
        "• <b>Mail.tm</b> - самый надежный, поддерживает JWT авторизацию\n"
        "• <b>TempMail.lol</b> - быстрый и стабильный сервис\n"
        "• <b>1SecMail</b> - простой сервис, может блокировать письма от Yandex\n\n"
        "При выборе 'Авто' бот будет автоматически использовать доступные провайдеры по приоритету."
    )
    
    await query.edit_message_text(
        settings_text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Произошла ошибка: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка при обработке запроса.\n"
            "Попробуйте позже или обратитесь к разработчику.",
            reply_markup=get_main_keyboard()
        )


def main():
    """Главная функция запуска бота"""
    import asyncio
    import sys
    
    # Исправление для Python 3.14+: создаем event loop если его нет
    if sys.version_info >= (3, 10):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token:
        raise ValueError(
            "Не найден TELEGRAM_BOT_TOKEN!\n"
            "Создайте файл .env и добавьте строку:\n"
            "TELEGRAM_BOT_TOKEN=ваш_токен"
        )
    
    application = Application.builder().token(token).build()
    
    # Регистрируем обработчик команды /start
    application.add_handler(CommandHandler("start", start_command))
    
    # Регистрируем команду /admin (если админ-панель настроена)
    if admin_panel:
        application.add_handler(CommandHandler("admin", admin_command))
        logger.info("Админ-панель активирована")
    
    # Регистрируем обработчик текстовых сообщений (кнопок)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Регистрируем обработчики медиа (для рассылки)
    application.add_handler(MessageHandler(filters.PHOTO, handle_media_message))
    application.add_handler(MessageHandler(filters.VIDEO, handle_media_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_media_message))
    
    # Регистрируем callback-обработчики для Inline-кнопок
    application.add_handler(CallbackQueryHandler(read_message_callback, pattern="^read_"))
    application.add_handler(CallbackQueryHandler(refresh_emails_callback, pattern="^refresh_emails$"))
    application.add_handler(CallbackQueryHandler(confirm_delete_callback, pattern="^confirm_delete$"))
    application.add_handler(CallbackQueryHandler(cancel_delete_callback, pattern="^cancel_delete$"))
    application.add_handler(CallbackQueryHandler(set_provider_callback, pattern="^set_provider_"))
    
    # Регистрируем callback-обработчики для админ-панели
    if admin_panel:
        application.add_handler(CallbackQueryHandler(admin_stats_callback, pattern="^admin_stats$"))
        application.add_handler(CallbackQueryHandler(admin_users_callback, pattern="^admin_users$"))
        application.add_handler(CallbackQueryHandler(admin_broadcast_callback, pattern="^admin_broadcast$"))
        application.add_handler(CallbackQueryHandler(admin_cleanup_callback, pattern="^admin_cleanup$"))
        application.add_handler(CallbackQueryHandler(admin_cleanup_confirm_callback, pattern="^admin_cleanup_confirm$"))
        application.add_handler(CallbackQueryHandler(broadcast_confirm_callback, pattern="^broadcast_confirm$"))
        application.add_handler(CallbackQueryHandler(broadcast_cancel_callback, pattern="^broadcast_cancel$"))
        application.add_handler(CallbackQueryHandler(admin_back_callback, pattern="^admin_back$"))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    logger.info("Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
