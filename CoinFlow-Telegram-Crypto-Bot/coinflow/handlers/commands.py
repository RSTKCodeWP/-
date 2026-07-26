"""Command handlers for CoinFlow bot."""

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from ..localization import get_text
from ..utils.logger import setup_logger

logger = setup_logger('commands')


class CommandHandlers:
    """Handlers for bot commands."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user_id = update.effective_user.id
        user = self.bot.db.get_user(user_id)
        
        if not user:
            # New user - show language selection
            keyboard = ReplyKeyboardMarkup([['English 🇬🇧', 'Русский 🇷🇺']], resize_keyboard=True)
            await update.message.reply_text(
                get_text('en', 'welcome_new'),
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            # Create user with default settings
            self.bot.db.create_user(user_id, lang='en')
            logger.info(f"New user: {user_id}")
        else:
            # Existing user - show main menu
            await update.message.reply_text(
                get_text(user.lang, 'welcome_back'),
                reply_markup=self.bot.get_main_menu_keyboard(user.lang),
                parse_mode='Markdown'
            )
            logger.info(f"User {user_id} started bot")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        user_id = update.effective_user.id
        user = self.bot.db.get_or_create_user(user_id)
        
        help_text = (
            "🆘 *CoinFlow Bot v3.1.0 - Help*\n\n"
            "*💱 Basic Features:*\n"
            "• Quick currency conversion\n"
            "• 60+ currencies (fiat + crypto)\n"
            "• Real-time rates from exchanges\n"
            "• Historical charts\n"
            "• Price forecasting (ARIMA, Linear)\n"
            "• Price alerts & notifications\n\n"
            "*📊 Advanced Features:*\n"
            "• Analytics: Volatility, Sharpe, Correlation\n"
            "• Trading Signals: RSI, MACD, MA, Bollinger\n"
            "• Portfolio tracking & rebalancing\n"
            "• Smart Alerts with ML predictions\n"
            "• AI Assistant (Llama 3.2 3B)\n\n"
            "*📈 Markets:*\n"
            "• Global stocks (Yahoo Finance)\n"
            "• Russian stocks (MOEX) + CBR rates\n"
            "• CS2 items (Steam, Skinport)\n\n"
            "*🤖 Commands:*\n"
            "/start - Main menu\n"
            "/help - This help\n"
            "/stats - Your statistics\n"
            "/history - Conversion history\n"
            "/favorites - Favorite currencies\n"
            "/cancel - Cancel operation\n\n"
            "Use menu buttons for easy navigation! 👇"
        )
        await update.message.reply_text(
            help_text, 
            parse_mode='Markdown',
            reply_markup=self.bot.get_main_menu_keyboard(user.lang)
        )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command."""
        user_id = update.effective_user.id
        user = self.bot.db.get_or_create_user(user_id)
        
        stats = self.bot.db.get_user_stats(user_id)
        popular_pairs = self.bot.db.get_popular_pairs(user_id, days=30, limit=5)
        
        stats_text = (
            f"📊 *Your Statistics*\n\n"
            f"💱 Total conversions: {stats['total_conversions']}\n"
            f"🔔 Active alerts: {stats['total_alerts']}\n"
            f"⭐ Favorite currencies: {stats['favorites_count']}\n"
        )
        
        if popular_pairs:
            stats_text += "\n*Most used pairs (last 30 days):*\n"
            for from_curr, to_curr, count in popular_pairs:
                stats_text += f"• {from_curr} → {to_curr}: {count}x\n"
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    
    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /history command."""
        user_id = update.effective_user.id
        await self.bot.message_handlers.show_history(update, context)
    
    async def favorites_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /favorites command."""
        user_id = update.effective_user.id
        await self.bot.message_handlers.show_favorites(update, context)
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel command."""
        user_id = update.effective_user.id
        user = self.bot.db.get_or_create_user(user_id)
        
        await update.message.reply_text(
            get_text(user.lang, 'main_menu'),
            reply_markup=self.bot.get_main_menu_keyboard(user.lang),
            parse_mode='Markdown'
        )
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /admin command."""
        user_id = update.effective_user.id
        user = self.bot.db.get_or_create_user(user_id)
        
        if not self.bot.admin_handler.is_admin(user_id):
            await update.message.reply_text("❌ Access denied")
            return
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        stats = self.bot.admin_handler.get_bot_statistics()
        
        keyboard = [
            [InlineKeyboardButton("📊 Statistics", callback_data='admin_stats')],
            [InlineKeyboardButton("📢 Create Announcement", callback_data='admin_announce_create')],
            [InlineKeyboardButton("📋 Announcements History", callback_data='admin_announce_history')],
            [InlineKeyboardButton("👥 User Management", callback_data='admin_users')],
        ]
        
        message = (
            "🔐 **Admin Panel**\n\n"
            f"Total Users: {stats['total_users']}\n"
            f"Active Users (24h): {stats['active_24h']}\n"
            f"Active Users (7d): {stats['active_7d']}\n"
            f"Total Conversions: {stats['total_conversions']}\n"
            f"Total Alerts: {stats['total_alerts']}\n"
            f"Announcements Sent: {stats['total_announcements']}"
        )
        
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
