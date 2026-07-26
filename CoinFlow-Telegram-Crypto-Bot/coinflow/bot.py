"""Main bot class for CoinFlow."""

from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, InlineQueryHandler
from telegram import InlineQueryResultArticle, InputTextMessageContent
from apscheduler.schedulers.background import BackgroundScheduler
import re
from .database import DatabaseRepository
from .services import CurrencyConverter, Calculator, ChartGenerator, PredictionGenerator, AlertManager, StockService, CS2MarketService, PortfolioService, ExportService, NewsService, ReportService, GoogleSheetsService, NotionService, VoiceService, AIService, AnalyticsService, TradingSignalsService, RebalanceService, SmartAlertsService
from .handlers import CommandHandlers, MessageHandlers, CallbackHandlers, StocksHandler, CS2Handler, PortfolioHandler, ExportHandler, NewsHandler, ReportHandler, DashboardHandler, AIHandler, AnalyticsHandler, TradingHandler, AdminHandler
from .config import config
from .utils import setup_logger, Metrics
from .localization import get_text

logger = setup_logger('bot', config.LOG_FILE, config.LOG_LEVEL, config.LOG_MAX_BYTES, config.LOG_BACKUP_COUNT)


class CoinFlowBot:
    """Main CoinFlow bot class."""
    
    def __init__(self):
        """Initialize bot with all services."""
        logger.info("Initializing CoinFlow Bot v2.0...")
        
        # Database
        self.db = DatabaseRepository(config.DATABASE_URL)
        logger.info("Database initialized")
        
        # Services
        self.converter = CurrencyConverter(cache_ttl=config.CACHE_TTL_SECONDS)
        self.converter.bot = self  # Circular reference for user settings
        
        self.calculator = Calculator(self.converter)
        self.chart_generator = ChartGenerator(dpi=config.CHART_DPI)
        
        # Initialize AI service first (needed by prediction generator)
        self.ai_service = AIService(
            ollama_url=config.OLLAMA_URL,
            text_model=config.OLLAMA_TEXT_MODEL,
            vision_model=config.OLLAMA_VISION_MODEL
        )
        
        self.prediction_generator = PredictionGenerator(dpi=config.CHART_DPI, db=self.db, ai_service=self.ai_service)
        self.alert_manager = AlertManager(self.db)
        self.stock_service = StockService(cache_ttl=config.CACHE_TTL_SECONDS)
        self.cs2_service = CS2MarketService(cache_ttl=config.CACHE_TTL_SECONDS)
        self.portfolio_service = PortfolioService(self.db, self.converter, self.stock_service, self.cs2_service)
        self.export_service = ExportService(self.db)
        self.news_service = NewsService(cache_ttl=config.CACHE_TTL_SECONDS)
        self.report_service = ReportService(self.db, self.converter, self.portfolio_service, self.chart_generator)
        self.sheets_service = GoogleSheetsService(self.db)
        self.notion_service = NotionService(self.db)
        self.voice_service = VoiceService()
        self.analytics_service = AnalyticsService(self.converter, self.stock_service)
        self.trading_service = TradingSignalsService(self.stock_service)
        self.rebalance_service = RebalanceService(self.db, self.portfolio_service)
        self.smart_alerts_service = SmartAlertsService(self.db, self.stock_service, self.analytics_service)
        
        # Metrics
        self.metrics = Metrics()
        
        # Temporary storage for multi-step operations
        self.temp_storage = {}
        
        # Handlers
        self.command_handlers = CommandHandlers(self)
        self.message_handlers = MessageHandlers(self)
        self.callback_handlers = CallbackHandlers(self)
        self.stocks_handler = StocksHandler(self)
        self.cs2_handler = CS2Handler(self)
        self.portfolio_handler = PortfolioHandler(self)
        self.export_handler = ExportHandler(self)
        self.news_handler = NewsHandler(self)
        self.report_handler = ReportHandler(self)
        self.dashboard_handler = DashboardHandler(self)
        self.ai_handler = AIHandler(self)
        self.analytics_handler = AnalyticsHandler(self)
        self.trading_handler = TradingHandler(self)
        self.admin_handler = AdminHandler(self)
        
        logger.info("All services initialized")
        
        # Currency lists
        self.popular_currencies = ['USD', 'EUR', 'RUB', 'CNY', 'GBP', 'JPY', 'BTC', 'ETH', 'USDT', 'TON', 'NOT', 'PEPE']
        self.fiat_currencies = [
            'USD', 'EUR', 'RUB', 'CNY', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'KRW',
            'INR', 'BRL', 'MXN', 'TRY', 'SEK', 'NOK', 'DKK', 'PLN', 'THB', 'IDR',
            'HUF', 'CZK', 'ILS', 'CLP', 'PHP', 'AED', 'SAR', 'MYR', 'RON', 'SGD'
        ]
        self.crypto_currencies = [
            # Top crypto
            'BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'XRP', 'ADA', 'AVAX', 'DOT', 'MATIC',
            # Meme coins
            'DOGE', 'SHIB', 'PEPE', 'FLOKI', 'BONK', 'WIF',
            # Popular altcoins
            'TON', 'NOT', 'TRX', 'LINK', 'UNI', 'ATOM', 'LTC', 'XLM', 'BCH', 'ALGO',
            'VET', 'FIL', 'HBAR', 'APE', 'NEAR', 'QNT', 'AAVE', 'GRT', 'XTZ', 'SAND',
            # DeFi & Layer 2
            'ARB', 'OP', 'IMX', 'LDO', 'MKR', 'CRV'
        ]
    
    def get_main_menu_keyboard(self, lang: str) -> ReplyKeyboardMarkup:
        """Create main menu keyboard."""
        return ReplyKeyboardMarkup([
            [get_text(lang, 'quick_convert')],
            [get_text(lang, 'rate_charts'), get_text(lang, 'rate_prediction')],
            [get_text(lang, 'compare_rates'), get_text(lang, 'calculator')],
            [get_text(lang, 'stocks'), get_text(lang, 'cs2_skins')],
            [get_text(lang, 'portfolio'), get_text(lang, 'export')],
            [get_text(lang, 'news'), get_text(lang, 'reports_btn')],
            [get_text(lang, 'analytics'), get_text(lang, 'trading_signals')],
            [get_text(lang, 'notifications'), get_text(lang, 'favorites')],
            [get_text(lang, 'history'), get_text(lang, 'stats_btn')],
            [get_text(lang, 'settings'), get_text(lang, 'about_btn')]
        ], resize_keyboard=True)
    
    def get_currency_selection_keyboard(self, lang: str, selection_type: str = 'popular') -> InlineKeyboardMarkup:
        """Create currency selection inline keyboard."""
        keyboard = []
        
        # Category buttons
        keyboard.append([
            InlineKeyboardButton(get_text(lang, 'popular'), callback_data='cat_popular'),
            InlineKeyboardButton(get_text(lang, 'fiat'), callback_data='cat_fiat'),
            InlineKeyboardButton(get_text(lang, 'crypto'), callback_data='cat_crypto')
        ])
        
        # Currency list
        if selection_type == 'popular':
            currencies = self.popular_currencies
        elif selection_type == 'fiat':
            currencies = self.fiat_currencies[:20]
        elif selection_type == 'crypto':
            currencies = self.crypto_currencies[:20]
        else:
            currencies = self.popular_currencies
        
        # 3 currencies per row
        row = []
        for curr in currencies:
            row.append(InlineKeyboardButton(curr, callback_data=f'curr_{curr}'))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        # Back button
        keyboard.append([InlineKeyboardButton(get_text(lang, 'back'), callback_data='back_main')])
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_amount_presets_keyboard(self, lang: str) -> InlineKeyboardMarkup:
        """Create amount preset keyboard."""
        keyboard = [
            [InlineKeyboardButton('10', callback_data='amt_10'),
             InlineKeyboardButton('50', callback_data='amt_50'),
             InlineKeyboardButton('100', callback_data='amt_100')],
            [InlineKeyboardButton('500', callback_data='amt_500'),
             InlineKeyboardButton('1000', callback_data='amt_1000'),
             InlineKeyboardButton('5000', callback_data='amt_5000')],
            [InlineKeyboardButton('💬 Custom', callback_data='amt_custom'),
             InlineKeyboardButton(get_text(lang, 'back'), callback_data='back_main')]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def inline_query(self, update, context):
        """Handle inline queries for quick conversions."""
        query = update.inline_query.query
        
        if not query:
            return
        
        # Parse: "100 USD to EUR"
        match = re.match(r'(\d+\.?\d*)\s*([A-Z]{3})\s*(?:to|in)\s*([A-Z]{3})', query, re.I)
        if match:
            amount, from_curr, to_curr = match.groups()
            amount = float(amount)
            from_curr = from_curr.upper()
            to_curr = to_curr.upper()
            
            result = self.converter.convert(amount, from_curr, to_curr)
            
            if result:
                results = [InlineQueryResultArticle(
                    id='1',
                    title=f'{amount} {from_curr} = {result:.2f} {to_curr}',
                    description=f'Current rate: 1 {from_curr} = {result/amount:.6f} {to_curr}',
                    input_message_content=InputTextMessageContent(
                        f'💱 {amount} {from_curr} = **{result:.2f} {to_curr}**',
                        parse_mode='Markdown'
                    )
                )]
                await update.inline_query.answer(results, cache_time=30)


def check_all_alerts(context, bot: CoinFlowBot):
    """Background task to check all price alerts."""
    try:
        logger.info("Checking price alerts...")
        
        # Get all unique alert pairs
        all_alerts = bot.alert_manager.get_all_alerts()
        pairs_to_check = {}
        
        for user_id, alert in all_alerts:
            pair = alert['pair']
            if pair not in pairs_to_check:
                pairs_to_check[pair] = []
            pairs_to_check[pair].append((user_id, alert))
        
        # Check each pair
        for pair, user_alerts in pairs_to_check.items():
            try:
                # Get current price
                if pair in bot.converter.crypto_symbols:
                    current_price = bot.converter.get_crypto_rate_aggregated(pair, 'USDT', user_alerts[0][0])
                    
                    if current_price:
                        # Check alerts for each user
                        for user_id, alert in user_alerts:
                            triggered = bot.alert_manager.check_alerts(user_id, pair, current_price)
                            
                            # Send notifications
                            for t_alert in triggered:
                                try:
                                    user = bot.db.get_user(user_id)
                                    if user:
                                        context.bot.send_message(
                                            chat_id=user_id,
                                            text=get_text(user.lang, 'alert_triggered',
                                                        pair=t_alert['pair'],
                                                        condition=t_alert['condition'],
                                                        target=t_alert['target'],
                                                        current=current_price),
                                            parse_mode='Markdown'
                                        )
                                        bot.metrics.log_alert(user_id)
                                        logger.info(f"Alert sent to user {user_id} for {pair}")
                                except Exception as e:
                                    logger.error(f"Error sending alert to user {user_id}: {e}")
            except Exception as e:
                logger.error(f"Error checking pair {pair}: {e}")
        
        logger.info("Alert check completed")
    except Exception as e:
        logger.error(f"Alert check error: {e}")


async def validate_predictions(context, bot):
    """Validate predictions by comparing with actual prices."""
    try:
        logger.info("Validating predictions...")
        
        # Get predictions that need validation
        predictions = bot.db.get_predictions_to_validate()
        
        if not predictions:
            return
        
        for pred in predictions:
            try:
                # Get current price
                rate = bot.converter.get_rate(pred.asset_symbol, 'USD')
                
                if rate and rate > 0:
                    # Update prediction with actual price
                    bot.db.update_prediction_accuracy(pred.id, rate)
                    logger.info(f"Updated prediction {pred.id} for {pred.asset_symbol}: predicted=${pred.predicted_price:.2f}, actual=${rate:.2f}")
            except Exception as e:
                logger.error(f"Error validating prediction {pred.id}: {e}")
        
        logger.info(f"Validated {len(predictions)} predictions")
    except Exception as e:
        logger.error(f"Error in prediction validation: {e}")


async def check_news_notifications(context, bot):
    """Check for new news and send notifications to subscribed users."""
    try:
        logger.info("Checking news notifications...")
        
        # Get all active subscriptions
        subscriptions = bot.db.get_all_active_subscriptions()
        
        if not subscriptions:
            return
        
        # Group by user
        user_subs = {}
        for sub in subscriptions:
            if sub.user_id not in user_subs:
                user_subs[sub.user_id] = {}
            user_subs[sub.user_id][sub.asset_symbol] = sub.categories
        
        # Fetch latest news
        all_news = await bot.news_service.fetch_news(max_age_hours=1)
        
        # Send notifications to users
        for user_id, subs_dict in user_subs.items():
            user = bot.db.get_user(user_id)
            if not user:
                continue
            
            # Get relevant news for this user
            relevant_news = []
            for item in all_news:
                for asset, categories in subs_dict.items():
                    if asset in item.assets:
                        if not categories or item.category in categories:
                            relevant_news.append(item)
                            break
            
            # Send news items
            sent_count = 0
            for item in relevant_news[:3]:  # Max 3 items per check
                try:
                    message = bot.news_service.format_news_message(item, user.lang)
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Error sending news to user {user_id}: {e}")
                    continue
            
            if sent_count > 0:
                logger.info(f"Sent {sent_count} news items to user {user_id}")
        
    except Exception as e:
        logger.error(f"Error in news notification check: {e}")


async def initialize_ai_service(bot):
    """Initialize AI service and check cloud models availability."""
    logger.info("Checking AI service availability...")
    is_available = await bot.ai_service.check_availability(auto_pull=False)
    
    if is_available:
        logger.info("✅ AI service is ready!")
        logger.info(f"  - Text model: {bot.ai_service.text_model}")
        if bot.ai_service.vision_available:
            logger.info(f"  - Vision model: {bot.ai_service.vision_model}")
        else:
            logger.warning("⚠️ Vision model not available - chart analysis will be limited")
    else:
        logger.warning("⚠️ AI service is not available. Bot will work without AI features.")
        logger.warning("To enable AI: Install Ollama from https://ollama.ai and pull required models")
        logger.info(f"  Required models: {bot.ai_service.text_model}, {bot.ai_service.vision_model}")


def setup_bot():
    """Setup and return bot application."""
    # Create bot instance
    bot = CoinFlowBot()
    
    # Create Application
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # Initialize AI service asynchronously
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.run_until_complete(initialize_ai_service(bot))
    
    # Add command handlers
    app.add_handler(CommandHandler("start", bot.command_handlers.start))
    app.add_handler(CommandHandler("admin", bot.command_handlers.admin_command))  # Hidden admin command
    
    # Add message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.message_handlers.handle_message))
    
    # Add voice message handler
    app.add_handler(MessageHandler(filters.VOICE, bot.message_handlers.handle_voice))
    
    # Add callback query handler
    app.add_handler(CallbackQueryHandler(bot.callback_handlers.handle_callback))
    
    # Add inline query handler
    app.add_handler(InlineQueryHandler(bot.inline_query))
    
    # Setup background scheduler for alerts and news
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        check_all_alerts,
        'interval',
        minutes=config.ALERT_CHECK_INTERVAL,
        kwargs={'context': app, 'bot': bot}
    )
    scheduler.add_job(
        check_news_notifications,
        'interval',
        minutes=15,  # Check news every 15 minutes
        kwargs={'context': app, 'bot': bot}
    )
    scheduler.add_job(
        validate_predictions,
        'interval',
        hours=6,  # Validate predictions every 6 hours
        kwargs={'context': app, 'bot': bot}
    )
    scheduler.start()
    
    logger.info("Bot setup completed")
    
    return app
