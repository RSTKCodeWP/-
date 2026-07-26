"""Export handler for CoinFlow bot."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from io import BytesIO
from ..localization import get_text
from ..utils.logger import setup_logger

logger = setup_logger('export_handler')


class ExportHandler:
    """Handler for data export."""
    
    def __init__(self, bot):
        """Initialize export handler."""
        self.bot = bot
    
    async def show_export_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show export menu."""
        user_id = update.effective_user.id
        user = self.bot.db.get_user(user_id)
        
        keyboard = [
            [InlineKeyboardButton(get_text(user.lang, 'export_portfolio'), callback_data='export_portfolio')],
            [InlineKeyboardButton(get_text(user.lang, 'export_alerts'), callback_data='export_alerts')],
            [InlineKeyboardButton(get_text(user.lang, 'export_history'), callback_data='export_history')],
            [InlineKeyboardButton(get_text(user.lang, 'export_all'), callback_data='export_all')],
            [InlineKeyboardButton('📊 Google Sheets', callback_data='export_sheets_menu')],
            [InlineKeyboardButton('📝 Notion', callback_data='export_notion_menu')],
            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='back_main')]
        ]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                get_text(user.lang, 'export_menu'),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                get_text(user.lang, 'export_menu'),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    async def handle_export_portfolio(self, query, user):
        """Export portfolio to CSV."""
        await query.answer()
        await query.edit_message_text(get_text(user.lang, 'export_generating'))
        
        try:
            # Get portfolio data
            portfolio_data = self.bot.portfolio_service.get_portfolio(user.telegram_id)
            
            if not portfolio_data:
                await query.edit_message_text(
                    get_text(user.lang, 'portfolio_empty'),
                    parse_mode='Markdown'
                )
                return
            
            # Generate CSV
            csv_data = self.bot.export_service.export_portfolio_csv(user.telegram_id, portfolio_data)
            
            if not csv_data:
                await query.edit_message_text(
                    get_text(user.lang, 'export_error', error='Failed to generate CSV'),
                    parse_mode='Markdown'
                )
                return
            
            # Send file
            filename = self.bot.export_service.get_export_filename(user.telegram_id, 'portfolio')
            file_buffer = BytesIO(csv_data.encode('utf-8'))
            file_buffer.name = filename
            
            await query.edit_message_text(get_text(user.lang, 'export_ready'))
            await query.message.reply_document(
                document=file_buffer,
                filename=filename,
                caption=f"📊 {get_text(user.lang, 'export_portfolio')}"
            )
            
            logger.info(f"Exported portfolio for user {user.telegram_id}")
            
        except Exception as e:
            logger.error(f"Error exporting portfolio: {e}")
            await query.edit_message_text(
                get_text(user.lang, 'export_error', error=str(e)),
                parse_mode='Markdown'
            )
    
    async def handle_export_alerts(self, query, user):
        """Export alerts to CSV."""
        await query.answer()
        await query.edit_message_text(get_text(user.lang, 'export_generating'))
        
        try:
            # Generate CSV
            csv_data = self.bot.export_service.export_alerts_csv(user.telegram_id)
            
            if not csv_data or csv_data == "Pair,Condition,Target Price,Created Date\n":
                await query.edit_message_text(
                    get_text(user.lang, 'no_alerts'),
                    parse_mode='Markdown'
                )
                return
            
            # Send file
            filename = self.bot.export_service.get_export_filename(user.telegram_id, 'alerts')
            file_buffer = BytesIO(csv_data.encode('utf-8'))
            file_buffer.name = filename
            
            await query.edit_message_text(get_text(user.lang, 'export_ready'))
            await query.message.reply_document(
                document=file_buffer,
                filename=filename,
                caption=f"🔔 {get_text(user.lang, 'export_alerts')}"
            )
            
            logger.info(f"Exported alerts for user {user.telegram_id}")
            
        except Exception as e:
            logger.error(f"Error exporting alerts: {e}")
            await query.edit_message_text(
                get_text(user.lang, 'export_error', error=str(e)),
                parse_mode='Markdown'
            )
    
    async def handle_export_history(self, query, user):
        """Export conversion history to CSV."""
        await query.answer()
        await query.edit_message_text(get_text(user.lang, 'export_generating'))
        
        try:
            # Generate CSV
            csv_data = self.bot.export_service.export_history_csv(user.telegram_id)
            
            if not csv_data or csv_data == "From Currency,To Currency,Amount,Result,Rate,Timestamp\n":
                await query.edit_message_text(
                    get_text(user.lang, 'history_empty'),
                    parse_mode='Markdown'
                )
                return
            
            # Send file
            filename = self.bot.export_service.get_export_filename(user.telegram_id, 'history')
            file_buffer = BytesIO(csv_data.encode('utf-8'))
            file_buffer.name = filename
            
            await query.edit_message_text(get_text(user.lang, 'export_ready'))
            await query.message.reply_document(
                document=file_buffer,
                filename=filename,
                caption=f"📜 {get_text(user.lang, 'export_history')}"
            )
            
            logger.info(f"Exported history for user {user.telegram_id}")
            
        except Exception as e:
            logger.error(f"Error exporting history: {e}")
            await query.edit_message_text(
                get_text(user.lang, 'export_error', error=str(e)),
                parse_mode='Markdown'
            )
    
    async def handle_export_all(self, query, user):
        """Export all data to ZIP archive."""
        await query.answer()
        await query.edit_message_text(get_text(user.lang, 'export_generating'))
        
        try:
            # Get portfolio data for ZIP
            portfolio_data = self.bot.portfolio_service.get_portfolio(user.telegram_id)
            
            # Generate ZIP
            zip_data = self.bot.export_service.create_export_zip(user.telegram_id, portfolio_data)
            
            if not zip_data:
                await query.edit_message_text(
                    get_text(user.lang, 'export_error', error='Failed to generate ZIP'),
                    parse_mode='Markdown'
                )
                return
            
            # Send file
            filename = self.bot.export_service.get_export_filename(user.telegram_id, 'all')
            file_buffer = BytesIO(zip_data)
            file_buffer.name = filename
            
            await query.edit_message_text(get_text(user.lang, 'export_ready'))
            await query.message.reply_document(
                document=file_buffer,
                filename=filename,
                caption=f"📦 {get_text(user.lang, 'export_all')}\n\nContents: Portfolio, Alerts, History, Favorites, User Info"
            )
            
            logger.info(f"Exported all data for user {user.telegram_id}")
            
        except Exception as e:
            logger.error(f"Error exporting all data: {e}")
            await query.edit_message_text(
                get_text(user.lang, 'export_error', error=str(e)),
                parse_mode='Markdown'
            )
    
    async def show_sheets_menu(self, query, user):
        """Show Google Sheets export menu."""
        await query.answer()
        
        if not self.bot.sheets_service.is_available():
            await query.edit_message_text(
                "❌ **Google Sheets Not Available**\n\n"
                "Google API libraries are not installed.\n\n"
                "Install with: `pip install google-auth google-auth-oauthlib google-api-python-client`",
                parse_mode='Markdown'
            )
            return
        
        keyboard = [
            [InlineKeyboardButton('💼 Portfolio to Sheets', callback_data='export_sheets_portfolio')],
            [InlineKeyboardButton('📋 History to Sheets', callback_data='export_sheets_history')],
            [InlineKeyboardButton('🔑 Authorize Google', callback_data='export_sheets_auth')],
            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='export_menu')]
        ]
        
        await query.edit_message_text(
            "📊 **Google Sheets Export**\n\n"
            "Export your data directly to Google Sheets.\n\n"
            "⚠️ Note: Authorization requires OAuth setup.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_sheets_auth(self, query, user):
        """Show Google Sheets authorization instructions."""
        await query.answer()
        await query.edit_message_text(
            "🔑 **Google Sheets Authorization**\n\n"
            "To export to Google Sheets, you need to:\n\n"
            "1. Set up OAuth2 credentials in Google Cloud Console\n"
            "2. Enable Google Sheets API\n"
            "3. Complete OAuth flow\n\n"
            "_OAuth integration requires additional setup._\n\n"
            "For now, use CSV export and import to Sheets manually.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='export_sheets_menu')]
            ])
        )
    
    async def show_notion_menu(self, query, user):
        """Show Notion export menu."""
        await query.answer()
        
        if not self.bot.notion_service.is_available():
            await query.edit_message_text(
                "❌ **Notion Not Available**\n\n"
                "Notion client library is not installed.\n\n"
                "Install with: `pip install notion-client`",
                parse_mode='Markdown'
            )
            return
        
        keyboard = [
            [InlineKeyboardButton('💼 Portfolio to Notion', callback_data='export_notion_portfolio')],
            [InlineKeyboardButton('📋 History to Notion', callback_data='export_notion_history')],
            [InlineKeyboardButton('🔑 Setup Instructions', callback_data='export_notion_setup')],
            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='export_menu')]
        ]
        
        await query.edit_message_text(
            "📝 **Notion Export**\n\n"
            "Export your data to Notion databases.\n\n"
            "⚠️ Note: Requires Notion API token and page ID.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_notion_setup(self, query, user):
        """Show Notion setup instructions."""
        await query.answer()
        await query.edit_message_text(
            "🔑 **Notion Setup Instructions**\n\n"
            "1. Go to https://www.notion.so/my-integrations\n"
            "2. Click 'New integration'\n"
            "3. Copy your 'Internal Integration Token'\n"
            "4. Share a Notion page with your integration\n"
            "5. Copy the page ID from the URL\n\n"
            "_Token storage requires secure implementation._\n\n"
            "For now, use CSV export and import to Notion manually.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='export_notion_menu')]
            ])
        )
