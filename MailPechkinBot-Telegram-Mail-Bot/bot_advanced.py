"""
Расширенная версия Telegram-бота для работы с временной почтой
Включает все продвинутые функции
"""

import logging
import os
import asyncio
from datetime import datetime
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
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from tempmail import TempMail
from database import Database
from code_extractor import CodeExtractor
from qr_generator import QRGenerator

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Инициализация
db = Database()
scheduler = AsyncIOScheduler()

# ID админа (установите ваш Telegram ID)
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Создает главную клавиатуру"""
    keyboard = [
        [KeyboardButton("📧 Создать почту"), KeyboardButton("📬 Проверить почту")],
        [KeyboardButton("📮 Мои email"), KeyboardButton("🗑️ Удалить почту")],
        [KeyboardButton("⭐ Избранное"), KeyboardButton("📜 История")],
        [KeyboardButton("⚙️ Настройки"), KeyboardButton("ℹ️ Инфо")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # Инициализируем настройки пользователя
    db.get_user_settings(user.id)
    
    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "🚀 Я продвинутый бот для временной почты с множеством функций:\n\n"
        "✨ <b>Основные возможности:</b>\n"
        "📧 Множественные email-адреса\n"
        "🔐 Автоматическое извлечение кодов\n"
        "📬 Автопроверка с уведомлениями\n"
        "⭐ Избранные письма\n"
        "📜 История сообщений\n"
        "📱 QR-коды для email\n"
        "🔍 Поиск по письмам\n"
        "⚙️ Гибкие настройки\n\n"
        "Используй кнопки ниже для управления! 👇"
    )
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard()
    )


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (кнопок)"""
    text = update.message.text
    
    handlers = {
        "📧 Создать почту": create_email_handler,
        "📬 Проверить почту": check_email_handler,
        "📮 Мои email": my_emails_handler,
        "🗑️ Удалить почту": delete_email_handler,
        "⭐ Избранное": favorites_handler,
        "📜 История": history_handler,
        "⚙️ Настройки": settings_handler,
        "ℹ️ Инфо": info_handler,
    }
    
    handler = handlers.get(text)
    if handler:
        await handler(update, context)
    else:
        await update.message.reply_text(
            "Используйте кнопки ниже для управления ботом.",
            reply_markup=get_main_keyboard()
        )


async def create_email_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создание нового email с выбором домена"""
    user_id = update.effective_user.id
    settings = db.get_user_settings(user_id)
    
    # Показываем кнопки выбора домена
    keyboard = [
        [InlineKeyboardButton("📧 @1secmail.com", callback_data="domain_1secmail.com")],
        [InlineKeyboardButton("📧 @1secmail.org", callback_data="domain_1secmail.org")],
        [InlineKeyboardButton("📧 @1secmail.net", callback_data="domain_1secmail.net")],
        [InlineKeyboardButton("⚡ Быстрое создание", callback_data=f"domain_{settings['preferred_domain']}")]
    ]
    
    text = (
        "📧 <b>Создание email-адреса</b>\n\n"
        "Выберите домен для нового email:\n\n"
        f"💡 Ваш предпочитаемый домен: <code>{settings['preferred_domain']}</code>"
    )
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def domain_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора домена"""
    query = update.callback_query
    await query.answer()
    
    domain = query.data.split("_")[1]
    user_id = update.effective_user.id
    
    await query.edit_message_text("⏳ Генерирую новый email-адрес...")
    
    try:
        async with TempMail() as temp_mail:
            username = temp_mail.generate_username()
            email = f"{username}@{domain}"
            
            db.set_user_email(user_id, email)
            
            # Генерируем QR-код
            qr_bio = QRGenerator.generate_fancy_qr(email)
            
            text = (
                "✅ <b>Email успешно создан!</b>\n\n"
                f"📧 Адрес: <code>{email}</code>\n\n"
                "📱 QR-код отправлен отдельным сообщением\n"
                "🔐 Коды подтверждения будут автоматически извлечены\n\n"
                "Используйте «📬 Проверить почту» для просмотра писем"
            )
            
            await query.edit_message_text(text, parse_mode=ParseMode.HTML)
            
            # Отправляем QR-код
            await context.bot.send_photo(
                chat_id=user_id,
                photo=qr_bio,
                caption=f"📱 QR-код для: <code>{email}</code>",
                parse_mode=ParseMode.HTML
            )
            
    except Exception as e:
        logger.error(f"Ошибка при создании email: {e}")
        await query.edit_message_text(
            "❌ Произошла ошибка при создании email.\n"
            "Попробуйте еще раз."
        )


async def check_email_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка почты с извлечением кодов"""
    user_id = update.effective_user.id
    email = db.get_user_email(user_id)
    
    if not email:
        await update.message.reply_text(
            "❌ У вас нет активного email-адреса.\n\n"
            "Создайте новый, нажав «📧 Создать почту»",
            reply_markup=get_main_keyboard()
        )
        return
    
    msg = await update.message.reply_text("⏳ Проверяю входящие письма...")
    
    try:
        async with TempMail() as temp_mail:
            messages = await temp_mail.get_messages(email)
            
            if not messages:
                await msg.edit_text(
                    f"📭 <b>Входящих писем пока нет</b>\n\n"
                    f"📧 Email: <code>{email}</code>\n\n"
                    f"Используйте этот адрес для регистрации, "
                    f"затем снова нажмите «📬 Проверить почту»",
                    parse_mode=ParseMode.HTML
                )
                return
            
            # Создаем кнопки для писем
            keyboard = []
            for msg_data in messages[:15]:
                msg_id = msg_data.get("id")
                subject = msg_data.get("subject", "Без темы")[:40]
                from_email = msg_data.get("from", "")[:30]
                
                # Проверяем, есть ли письмо в истории
                button_text = f"📩 {subject} | {from_email}"
                keyboard.append([
                    InlineKeyboardButton(button_text, callback_data=f"read_{msg_id}")
                ])
            
            keyboard.append([
                InlineKeyboardButton("🔄 Обновить", callback_data="refresh_emails"),
                InlineKeyboardButton("📜 В историю", callback_data="save_all_history")
            ])
            
            text = (
                f"📬 <b>Входящие письма: {len(messages)}</b>\n\n"
                f"📧 Email: <code>{email}</code>\n\n"
                f"Нажмите на письмо для просмотра:"
            )
            
            await msg.edit_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except Exception as e:
        logger.error(f"Ошибка при проверке почты: {e}")
        await msg.edit_text("❌ Ошибка при проверке почты. Попробуйте позже.")


async def read_message_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Чтение письма с извлечением кода"""
    query = update.callback_query
    await query.answer()
    
    message_id = int(query.data.split("_")[1])
    user_id = update.effective_user.id
    email = db.get_user_email(user_id)
    
    if not email:
        await query.edit_message_text("❌ Email не найден.")
        return
    
    await query.edit_message_text("⏳ Загружаю письмо...")
    
    try:
        async with TempMail() as temp_mail:
            message = await temp_mail.read_message(email, message_id)
            
            if not message:
                await query.edit_message_text("❌ Не удалось загрузить письмо.")
                return
            
            subject = message.get("subject", "Без темы")
            from_email = message.get("from", "Неизвестный")
            date = message.get("date", "")
            body = message.get("textBody", message.get("htmlBody", "Пустое письмо"))
            
            # Сохраняем в историю
            db.add_message_to_history(user_id, email, message_id, subject, from_email, date, body)
            
            # Извлекаем код
            code = CodeExtractor.find_best_code(body)
            
            # Ограничиваем длину
            max_length = 2500
            if len(body) > max_length:
                body = body[:max_length] + "\n\n... (письмо обрезано)"
            
            text = f"📧 <b>Тема:</b> {subject}\n"
            text += f"👤 <b>От:</b> {from_email}\n"
            text += f"📅 <b>Дата:</b> {date}\n"
            
            if code:
                text += f"\n🔐 <b>КОД:</b> <code>{code}</code> 👈 Нажми для копирования\n"
            
            text += f"\n{'='*30}\n\n{body}"
            
            keyboard = [
                [InlineKeyboardButton("⭐ В избранное", callback_data=f"fav_{message_id}")],
                [InlineKeyboardButton("◀️ К списку", callback_data="refresh_emails")]
            ]
            
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except Exception as e:
        logger.error(f"Ошибка при чтении письма: {e}")
        await query.edit_message_text("❌ Ошибка при чтении письма.")


async def my_emails_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ всех активных email пользователя"""
    user_id = update.effective_user.id
    emails = db.get_all_active_emails(user_id)
    
    if not emails:
        await update.message.reply_text(
            "❌ У вас нет активных email-адресов.\n\n"
            "Создайте новый, нажав «📧 Создать почту»",
            reply_markup=get_main_keyboard()
        )
        return
    
    text = "📮 <b>Ваши активные email-адреса:</b>\n\n"
    
    keyboard = []
    for idx, email_data in enumerate(emails, 1):
        email = email_data['email']
        created = email_data['created_at']
        
        text += f"{idx}. <code>{email}</code>\n"
        text += f"   📅 Создан: {created}\n\n"
        
        keyboard.append([
            InlineKeyboardButton(f"📋 {email[:25]}...", callback_data=f"copy_{email}"),
            InlineKeyboardButton("📱 QR", callback_data=f"qr_{email}")
        ])
    
    keyboard.append([InlineKeyboardButton("➕ Добавить еще", callback_data="add_more_email")])
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def qr_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация QR-кода для email"""
    query = update.callback_query
    await query.answer("Генерирую QR-код...")
    
    email = query.data.split("_", 1)[1]
    
    try:
        qr_bio = QRGenerator.generate_fancy_qr(email)
        
        await context.bot.send_photo(
            chat_id=query.from_user.id,
            photo=qr_bio,
            caption=f"📱 QR-код для: <code>{email}</code>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Ошибка генерации QR: {e}")
        await query.answer("❌ Ошибка генерации QR-кода", show_alert=True)


async def favorites_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ избранных писем"""
    user_id = update.effective_user.id
    favorites = db.get_favorites(user_id)
    
    if not favorites:
        await update.message.reply_text(
            "⭐ У вас пока нет избранных писем.\n\n"
            "Добавляйте важные письма в избранное при просмотре!",
            reply_markup=get_main_keyboard()
        )
        return
    
    text = f"⭐ <b>Избранные письма ({len(favorites)}):</b>\n\n"
    
    keyboard = []
    for fav in favorites[:20]:
        subject = fav['subject'][:30]
        from_email = fav['from_email'][:25]
        
        button_text = f"⭐ {subject} | {from_email}"
        keyboard.append([
            InlineKeyboardButton(button_text, callback_data=f"view_fav_{fav['id']}")
        ])
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ истории писем"""
    user_id = update.effective_user.id
    history = db.get_message_history(user_id, limit=30)
    
    if not history:
        await update.message.reply_text(
            "📜 История писем пуста.\n\n"
            "Письма автоматически сохраняются при просмотре.",
            reply_markup=get_main_keyboard()
        )
        return
    
    text = f"📜 <b>История писем ({len(history)}):</b>\n\n"
    
    keyboard = []
    for msg in history[:25]:
        subject = msg['subject'][:30]
        from_email = msg['from_email'][:25]
        star = "⭐" if msg['is_favorite'] else "📧"
        
        button_text = f"{star} {subject} | {from_email}"
        keyboard.append([
            InlineKeyboardButton(button_text, callback_data=f"view_hist_{msg['id']}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("🗑️ Очистить историю", callback_data="clear_history")
    ])
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ настроек пользователя"""
    user_id = update.effective_user.id
    settings = db.get_user_settings(user_id)
    
    auto_status = "✅ Включена" if settings['auto_check'] else "❌ Выключена"
    
    text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"🔄 Автопроверка: {auto_status}\n"
        f"⏱️ Интервал: {settings['check_interval']} мин\n"
        f"📧 Домен: {settings['preferred_domain']}\n"
        f"🌐 Язык: {settings['language'].upper()}\n"
    )
    
    keyboard = [
        [InlineKeyboardButton(
            "🔄 Автопроверка: " + ("✅" if settings['auto_check'] else "❌"),
            callback_data="toggle_auto_check"
        )],
        [
            InlineKeyboardButton("⏱️ 1 мин", callback_data="interval_1"),
            InlineKeyboardButton("⏱️ 5 мин", callback_data="interval_5"),
            InlineKeyboardButton("⏱️ 10 мин", callback_data="interval_10")
        ],
        [
            InlineKeyboardButton("📧 .com", callback_data="pref_1secmail.com"),
            InlineKeyboardButton("📧 .org", callback_data="pref_1secmail.org"),
            InlineKeyboardButton("📧 .net", callback_data="pref_1secmail.net")
        ]
    ]
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def toggle_auto_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключение автопроверки"""
    query = update.callback_query
    user_id = query.from_user.id
    
    settings = db.get_user_settings(user_id)
    new_value = 0 if settings['auto_check'] else 1
    
    db.update_user_settings(user_id, auto_check=new_value)
    
    status = "включена" if new_value else "выключена"
    await query.answer(f"✅ Автопроверка {status}", show_alert=True)
    
    # Обновляем сообщение
    await settings_handler(query, context)


async def info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ информации о боте"""
    stats = db.get_stats()
    
    info_text = (
        "ℹ️ <b>О боте</b>\n\n"
        "🚀 Продвинутый бот для временной почты\n"
        "🔐 Автоматическое извлечение кодов\n"
        "📬 Автопроверка с уведомлениями\n"
        "⭐ Избранное и история\n"
        "📱 QR-коды для email\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"📧 Email создано: {stats['total_emails']}\n"
        f"✅ Активных: {stats['active_emails']}\n"
        f"📨 Писем обработано: {stats.get('total_messages', 0)}\n"
    )
    
    await update.message.reply_text(
        info_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard()
    )


async def delete_email_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление email"""
    user_id = update.effective_user.id
    email = db.get_user_email(user_id)
    
    if not email:
        await update.message.reply_text(
            "❌ У вас нет активного email для удаления.",
            reply_markup=get_main_keyboard()
        )
        return
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data="confirm_delete"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_delete")
        ]
    ]
    
    text = (
        f"🗑️ <b>Подтверждение удаления</b>\n\n"
        f"Удалить email?\n\n"
        f"📧 <code>{email}</code>"
    )
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def refresh_emails_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обновление списка писем"""
    query = update.callback_query
    await query.answer("Обновляю...")
    
    user_id = query.from_user.id
    email = db.get_user_email(user_id)
    
    if not email:
        await query.edit_message_text("❌ Email не найден.")
        return
    
    # Вызываем обработчик проверки
    # Создаем фейковый update для callback
    class FakeMessage:
        text = "📬 Проверить почту"
        
    class FakeUpdate:
        message = FakeMessage()
        effective_user = query.from_user
        
    fake_update = FakeUpdate()
    await check_email_handler(fake_update, context)


async def confirm_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления"""
    query = update.callback_query
    await query.answer("Email удален")
    
    user_id = query.from_user.id
    db.delete_user_email(user_id)
    
    await query.edit_message_text(
        "✅ Email успешно удален!\n\n"
        "Создайте новый, нажав «📧 Создать почту»",
        parse_mode=ParseMode.HTML
    )


async def cancel_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена удаления"""
    query = update.callback_query
    await query.answer("Отменено")
    await query.edit_message_text("❌ Удаление отменено.")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка. Попробуйте позже.",
            reply_markup=get_main_keyboard()
        )


def main():
    """Главная функция"""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token:
        raise ValueError("Не найден TELEGRAM_BOT_TOKEN!")
    
    application = Application.builder().token(token).build()
    
    # Команды
    application.add_handler(CommandHandler("start", start_command))
    
    # Текстовые сообщения
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Callbacks
    application.add_handler(CallbackQueryHandler(domain_callback, pattern="^domain_"))
    application.add_handler(CallbackQueryHandler(read_message_callback, pattern="^read_"))
    application.add_handler(CallbackQueryHandler(qr_callback, pattern="^qr_"))
    application.add_handler(CallbackQueryHandler(refresh_emails_callback, pattern="^refresh_emails$"))
    application.add_handler(CallbackQueryHandler(toggle_auto_check_callback, pattern="^toggle_auto_check$"))
    application.add_handler(CallbackQueryHandler(confirm_delete_callback, pattern="^confirm_delete$"))
    application.add_handler(CallbackQueryHandler(cancel_delete_callback, pattern="^cancel_delete$"))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запуск планировщика
    scheduler.start()
    
    logger.info("🚀 Расширенный бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
