"""Dashboard handler for CoinFlow bot."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..localization import get_text
from ..utils.logger import setup_logger
from ..config import config

logger = setup_logger('dashboard_handler')


class DashboardHandler:
    """Handler for web dashboard."""
    
    def __init__(self, bot):
        """Initialize dashboard handler."""
        self.bot = bot
        self.webapp_url = config.WEBAPP_URL if hasattr(config, 'WEBAPP_URL') else "http://localhost:8000"
    
    async def show_dashboard_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show dashboard menu."""
        user_id = update.effective_user.id
        user = self.bot.db.get_user(user_id)
        
        keyboard = [
            [InlineKeyboardButton(
                "🌐 Open Web Dashboard", 
                web_app={"url": self.webapp_url}
            )],
            [InlineKeyboardButton(
                "📊 Dashboard Features",
                callback_data='dashboard_features'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'back'),
                callback_data='back_main'
            )]
        ]
        
        message = (
            "🌐 **Web Dashboard**\n\n"
            "Access your CoinFlow dashboard in your browser:\n\n"
            "📊 **Features:**\n"
            "• Real-time crypto prices\n"
            "• Portfolio visualization\n"
            "• Conversion history\n"
            "• Statistics & analytics\n"
            "• Interactive charts\n\n"
            "Click the button below to open the dashboard!"
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    async def show_dashboard_features(self, query, user):
        """Show detailed dashboard features."""
        await query.answer()
        
        message = (
            "📊 **Dashboard Features**\n\n"
            "**Live Data:**\n"
            "• Real-time cryptocurrency prices\n"
            "• Auto-refresh every 30 seconds\n"
            "• Multi-exchange aggregation\n\n"
            "**Portfolio:**\n"
            "• View all your assets\n"
            "• Track quantities and values\n"
            "• Purchase history\n\n"
            "**Analytics:**\n"
            "• Conversion statistics\n"
            "• Activity history\n"
            "• Alert monitoring\n\n"
            "**Interface:**\n"
            "• Responsive design\n"
            "• Dark/Light theme support\n"
            "• Mobile-friendly\n"
            "• Telegram Web App integration"
        )
        
        keyboard = [
            [InlineKeyboardButton(
                "🌐 Open Dashboard",
                web_app={"url": self.webapp_url}
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'back'),
                callback_data='dashboard_menu'
            )]
        ]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
