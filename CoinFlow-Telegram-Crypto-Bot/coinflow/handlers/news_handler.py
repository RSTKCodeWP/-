"""News handler for CoinFlow bot."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..localization import get_text
from ..utils.logger import setup_logger

logger = setup_logger('news_handler')


class NewsHandler:
    """Handler for crypto news notifications."""
    
    def __init__(self, bot):
        """Initialize news handler."""
        self.bot = bot
    
    async def show_news_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main news menu."""
        user_id = update.effective_user.id
        user = self.bot.db.get_user(user_id)
        
        # Get user subscriptions
        subscriptions = self.bot.db.get_news_subscriptions(user_id)
        
        keyboard = [
            [InlineKeyboardButton(get_text(user.lang, 'news_latest'), callback_data='news_latest')],
            [InlineKeyboardButton(get_text(user.lang, 'news_subscriptions'), callback_data='news_subscriptions')],
            [InlineKeyboardButton(get_text(user.lang, 'news_subscribe'), callback_data='news_subscribe')],
            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='back_main')]
        ]
        
        message = f"📰 **{get_text(user.lang, 'news_menu_title')}**\n\n"
        message += f"{get_text(user.lang, 'news_menu_desc')}\n\n"
        message += f"📊 {get_text(user.lang, 'active_subscriptions')}: {len(subscriptions)}"
        
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
    
    async def show_latest_news(self, query, user):
        """Show latest news for user subscriptions."""
        await query.answer()
        await query.edit_message_text('📰 Fetching latest news...')
        
        try:
            # Get user subscriptions
            subscriptions = self.bot.db.get_news_subscriptions(user.telegram_id)
            
            if not subscriptions:
                await query.edit_message_text(
                    get_text(user.lang, 'news_no_subscriptions'),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(get_text(user.lang, 'news_subscribe'), callback_data='news_subscribe')],
                        [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='news_menu')]
                    ]),
                    parse_mode='Markdown'
                )
                return
            
            # Build subscriptions dict for news service
            user_subs = {}
            for sub in subscriptions:
                user_subs[sub.asset_symbol] = sub.categories
            
            # Get latest news
            news_items = await self.bot.news_service.get_latest_for_user(user_subs, max_items=5)
            
            if not news_items:
                await query.edit_message_text(
                    get_text(user.lang, 'news_none_found'),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='news_menu')]
                    ]),
                    parse_mode='Markdown'
                )
                return
            
            # Send news items
            for item in news_items:
                message = self.bot.news_service.format_news_message(item, user.lang)
                try:
                    await query.message.reply_text(message, parse_mode='Markdown', disable_web_page_preview=True)
                except Exception as e:
                    logger.error(f"Error sending news item: {e}")
                    continue
            
            # Show menu again
            await query.edit_message_text(
                f"📰 {get_text(user.lang, 'news_sent', count=len(news_items))}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='news_menu')]
                ]),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error showing latest news: {e}")
            await query.edit_message_text(
                f"❌ {get_text(user.lang, 'error_occurred')}: {str(e)}",
                parse_mode='Markdown'
            )
    
    async def show_subscriptions(self, query, user):
        """Show user's news subscriptions."""
        await query.answer()
        
        subscriptions = self.bot.db.get_news_subscriptions(user.telegram_id, enabled_only=False)
        
        if not subscriptions:
            await query.edit_message_text(
                get_text(user.lang, 'news_no_subscriptions'),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(get_text(user.lang, 'news_subscribe'), callback_data='news_subscribe')],
                    [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='news_menu')]
                ]),
                parse_mode='Markdown'
            )
            return
        
        message = f"📊 **{get_text(user.lang, 'your_subscriptions')}**\n\n"
        
        keyboard = []
        for sub in subscriptions:
            status = '✅' if sub.enabled else '❌'
            categories = ', '.join(sub.categories) if sub.categories else 'All'
            message += f"{status} **{sub.asset_symbol}** - {categories} ({sub.frequency})\n"
            keyboard.append([
                InlineKeyboardButton(
                    f"{'🔕' if sub.enabled else '🔔'} {sub.asset_symbol}",
                    callback_data=f'news_toggle_{sub.id}'
                ),
                InlineKeyboardButton('🗑️', callback_data=f'news_delete_{sub.id}')
            ])
        
        keyboard.append([InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='news_menu')])
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_subscribe_assets(self, query, user):
        """Show asset selection for subscription."""
        await query.answer()
        
        assets = ['BTC', 'ETH', 'BNB', 'SOL', 'ADA', 'XRP', 'DOGE', 'DOT', 'MATIC', 'AVAX', 'LINK', 'UNI']
        
        keyboard = []
        row = []
        for asset in assets:
            row.append(InlineKeyboardButton(asset, callback_data=f'news_select_{asset}'))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='news_menu')])
        
        await query.edit_message_text(
            get_text(user.lang, 'news_select_asset'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_asset_selected(self, query, user, asset: str):
        """Handle asset selection for subscription."""
        await query.answer()
        
        # Show category selection
        keyboard = [
            [InlineKeyboardButton('📰 All News', callback_data=f'news_cat_{asset}_all')],
            [
                InlineKeyboardButton('🚨 Hacks', callback_data=f'news_cat_{asset}_hack'),
                InlineKeyboardButton('🎉 Listings', callback_data=f'news_cat_{asset}_listing')
            ],
            [
                InlineKeyboardButton('🔄 Updates', callback_data=f'news_cat_{asset}_update'),
                InlineKeyboardButton('⚖️ Regulations', callback_data=f'news_cat_{asset}_regulation')
            ],
            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='news_subscribe')]
        ]
        
        await query.edit_message_text(
            f"📰 **{asset}**\n\n{get_text(user.lang, 'news_select_categories')}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_category_selected(self, query, user, asset: str, category: str):
        """Handle category selection and create subscription."""
        await query.answer()
        
        try:
            categories = [] if category == 'all' else [category]
            
            # Check if subscription already exists
            existing = self.bot.db.get_news_subscriptions(user.telegram_id, enabled_only=False)
            for sub in existing:
                if sub.asset_symbol == asset:
                    # Update existing
                    self.bot.db.update_news_subscription(sub.id, categories=categories, enabled=True)
                    await query.edit_message_text(
                        f"✅ {get_text(user.lang, 'news_subscription_updated', asset=asset)}",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='news_menu')]
                        ]),
                        parse_mode='Markdown'
                    )
                    return
            
            # Create new subscription
            self.bot.db.add_news_subscription(user.telegram_id, asset, categories)
            
            await query.edit_message_text(
                f"✅ {get_text(user.lang, 'news_subscription_created', asset=asset)}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='news_menu')]
                ]),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error creating subscription: {e}")
            await query.edit_message_text(
                f"❌ {get_text(user.lang, 'error_occurred')}: {str(e)}",
                parse_mode='Markdown'
            )
    
    async def handle_toggle_subscription(self, query, user, subscription_id: int):
        """Toggle subscription on/off."""
        await query.answer()
        
        try:
            sub = self.bot.db.get_news_subscription(subscription_id)
            if not sub or sub.user_id != user.telegram_id:
                await query.answer("❌ Subscription not found", show_alert=True)
                return
            
            new_status = not sub.enabled
            self.bot.db.update_news_subscription(subscription_id, enabled=new_status)
            
            await query.answer(f"{'✅ Enabled' if new_status else '🔕 Disabled'}")
            await self.show_subscriptions(query, user)
            
        except Exception as e:
            logger.error(f"Error toggling subscription: {e}")
            await query.answer(f"❌ Error: {str(e)}", show_alert=True)
    
    async def handle_delete_subscription(self, query, user, subscription_id: int):
        """Delete subscription."""
        await query.answer()
        
        try:
            sub = self.bot.db.get_news_subscription(subscription_id)
            if not sub or sub.user_id != user.telegram_id:
                await query.answer("❌ Subscription not found", show_alert=True)
                return
            
            self.bot.db.delete_news_subscription(subscription_id)
            
            await query.answer("🗑️ Subscription deleted")
            await self.show_subscriptions(query, user)
            
        except Exception as e:
            logger.error(f"Error deleting subscription: {e}")
            await query.answer(f"❌ Error: {str(e)}", show_alert=True)
