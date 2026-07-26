"""
Модуль админ-панели для управления ботом
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from database import Database
import logging

logger = logging.getLogger(__name__)


class AdminPanel:
    """Класс для работы с админ-панелью"""
    
    def __init__(self, admin_ids: list):
        self.admin_ids = admin_ids
        self.db = Database()
    
    def is_admin(self, user_id: int) -> bool:
        """Проверяет, является ли пользователь админом"""
        return user_id in self.admin_ids
    
    async def show_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает админ-панель"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ У вас нет доступа к админ-панели")
            return
        
        stats = self.db.get_stats()
        
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
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def broadcast_message(self, context: ContextTypes.DEFAULT_TYPE, message: str = None, 
                               photo_id: str = None, video_id: str = None, 
                               document_id: str = None, caption: str = None):
        """Рассылка сообщения всем пользователям
        
        Args:
            context: Контекст бота
            message: Текстовое сообщение
            photo_id: ID фотографии
            video_id: ID видео
            document_id: ID документа
            caption: Подпись к медиа
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users")
            users = cursor.fetchall()
        
        success = 0
        failed = 0
        
        for user in users:
            try:
                if photo_id:
                    await context.bot.send_photo(
                        chat_id=user['user_id'],
                        photo=photo_id,
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
                elif video_id:
                    await context.bot.send_video(
                        chat_id=user['user_id'],
                        video=video_id,
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
                elif document_id:
                    await context.bot.send_document(
                        chat_id=user['user_id'],
                        document=document_id,
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
                else:
                    await context.bot.send_message(
                        chat_id=user['user_id'],
                        text=message,
                        parse_mode=ParseMode.HTML
                    )
                success += 1
            except Exception as e:
                logger.error(f"Ошибка отправки пользователю {user['user_id']}: {e}")
                failed += 1
        
        return success, failed
