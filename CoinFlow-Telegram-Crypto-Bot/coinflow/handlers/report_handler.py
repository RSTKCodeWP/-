"""Report handler for CoinFlow bot."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..localization import get_text
from ..utils.logger import setup_logger

logger = setup_logger('report_handler')


class ReportHandler:
    """Handler for analytics reports."""
    
    def __init__(self, bot):
        """Initialize report handler."""
        self.bot = bot
    
    async def show_report_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main report menu."""
        user_id = update.effective_user.id
        user = self.bot.db.get_user(user_id)
        
        keyboard = [
            [InlineKeyboardButton(get_text(user.lang, 'report_weekly'), callback_data='report_generate_weekly')],
            [InlineKeyboardButton(get_text(user.lang, 'report_portfolio'), callback_data='report_generate_portfolio')],
            [InlineKeyboardButton(get_text(user.lang, 'report_subscribe'), callback_data='report_subscribe_menu')],
            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='back_main')]
        ]
        
        message = get_text(user.lang, 'reports_menu')
        
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
    
    async def generate_weekly_report(self, query, user):
        """Generate and send weekly digest."""
        await query.answer()
        await query.edit_message_text(get_text(user.lang, 'report_generating'))
        
        try:
            # Generate report
            report_data = await self.bot.report_service.generate_weekly_digest(user.telegram_id, user.lang)
            
            if not report_data:
                await query.edit_message_text(
                    get_text(user.lang, 'report_no_data'),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='report_menu')]
                    ]),
                    parse_mode='Markdown'
                )
                return
            
            # Send report text
            await query.message.reply_text(
                report_data['text'],
                parse_mode='Markdown'
            )
            
            # Send chart if available
            if report_data.get('image'):
                await query.message.reply_photo(
                    photo=report_data['image'],
                    caption=get_text(user.lang, 'report_ready')
                )
            
            # Show menu again
            await query.edit_message_text(
                get_text(user.lang, 'report_ready'),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='report_menu')]
                ]),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error generating weekly report: {e}")
            await query.edit_message_text(
                f"❌ {get_text(user.lang, 'error_occurred')}: {str(e)}",
                parse_mode='Markdown'
            )
    
    async def generate_portfolio_report(self, query, user):
        """Generate and send portfolio report."""
        await query.answer()
        await query.edit_message_text(get_text(user.lang, 'report_generating'))
        
        try:
            # Generate report
            report_data = await self.bot.report_service.generate_portfolio_report(user.telegram_id, user.lang)
            
            if not report_data:
                await query.edit_message_text(
                    get_text(user.lang, 'report_no_data'),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='report_menu')]
                    ]),
                    parse_mode='Markdown'
                )
                return
            
            # Send report
            await query.message.reply_text(
                report_data['text'],
                parse_mode='Markdown'
            )
            
            # Show menu again
            await query.edit_message_text(
                get_text(user.lang, 'report_ready'),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='report_menu')]
                ]),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error generating portfolio report: {e}")
            await query.edit_message_text(
                f"❌ {get_text(user.lang, 'error_occurred')}: {str(e)}",
                parse_mode='Markdown'
            )
    
    async def show_subscribe_menu(self, query, user):
        """Show report subscription menu."""
        await query.answer()
        
        keyboard = [
            [InlineKeyboardButton('📅 Weekly Digest', callback_data='report_sub_weekly')],
            [InlineKeyboardButton('📆 Monthly Digest', callback_data='report_sub_monthly')],
            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='report_menu')]
        ]
        
        await query.edit_message_text(
            "🔔 **Subscribe to Automated Reports**\n\nChoose report frequency:" if user.lang == 'en' else 
            "🔔 **Подписка на автоматические отчеты**\n\nВыберите частоту отчетов:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_subscribe(self, query, user, report_type: str):
        """Handle report subscription."""
        await query.answer()
        
        try:
            # Check if subscription exists
            existing = self.bot.db.get_report_subscriptions(user.telegram_id, enabled_only=False)
            
            for sub in existing:
                if sub.report_type == report_type:
                    # Update existing
                    self.bot.db.update_report_subscription(sub.id, enabled=True)
                    await query.edit_message_text(
                        get_text(user.lang, 'report_subscription_updated'),
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='report_menu')]
                        ]),
                        parse_mode='Markdown'
                    )
                    return
            
            # Create new subscription
            frequency = 'weekly' if report_type == 'weekly' else 'monthly'
            delivery_day = 1  # Monday for weekly, 1st for monthly
            
            self.bot.db.add_report_subscription(
                user.telegram_id,
                report_type=report_type,
                frequency=frequency,
                delivery_day=delivery_day
            )
            
            await query.edit_message_text(
                get_text(user.lang, 'report_subscription_created', report_type=report_type),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='report_menu')]
                ]),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error creating report subscription: {e}")
            await query.edit_message_text(
                f"❌ {get_text(user.lang, 'error_occurred')}: {str(e)}",
                parse_mode='Markdown'
            )
