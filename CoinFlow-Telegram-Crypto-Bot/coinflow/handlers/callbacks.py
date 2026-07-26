"""Callback query handlers for CoinFlow bot."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime
from ..localization import get_text
from ..utils.logger import setup_logger

logger = setup_logger('callbacks')


class CallbackHandlers:
    """Handlers for inline keyboard callbacks."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main callback query handler."""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        user = self.bot.db.get_or_create_user(user_id)
        
        # Category selection
        if data.startswith('cat_'):
            category = data.split('_')[1]
            keyboard = self.bot.get_currency_selection_keyboard(user.lang, category)
            await query.edit_message_reply_markup(reply_markup=keyboard)
        
        # Currency selection
        elif data.startswith('curr_'):
            currency = data.split('_')[1]
            await self.handle_currency_selection(query, context, user, currency)
        
        # Amount selection
        elif data.startswith('amt_'):
            if data == 'amt_custom':
                context.user_data['state'] = 'enter_amount'
                await query.edit_message_text(get_text(user.lang, 'enter_amount'), parse_mode='Markdown')
            else:
                amount = float(data.split('_')[1])
                await self.perform_conversion_callback(query, context, amount, user)
        
        # Favorite toggle
        elif data.startswith('fav_'):
            currency = data.split('_')[1]
            await self.toggle_favorite(query, user, currency)
        
        # Period selection for charts
        elif data.startswith('period_'):
            period = int(data.split('_')[1])
            chart_type = context.user_data.get('chart_type', 'crypto')
            
            if chart_type == 'crypto':
                pair = context.user_data.get('chart_pair', 'BTC')
                await self.generate_chart(query, user, pair, period)
            elif chart_type == 'stock':
                ticker = context.user_data.get('chart_ticker')
                stock_type = context.user_data.get('stock_type', 'global')
                await self.bot.stocks_handler.show_stock_chart(query, user, ticker, stock_type, period)
            elif chart_type == 'cbr':
                currency = context.user_data.get('chart_currency')
                await self.bot.stocks_handler.show_cbr_chart(query, user, currency, period)
        
        # Chart type selection
        elif data.startswith('chart_type_'):
            chart_type = data.replace('chart_type_', '')
            await self.handle_chart_type_selection(query, user, context, chart_type)
        
        # Chart stock market selection
        elif data.startswith('chart_stocks_'):
            market_type = data.replace('chart_stocks_', '')
            await self.show_chart_stock_selection(query, user, context, market_type)
        
        # Chart CBR currency selection
        elif data.startswith('chart_cbr_'):
            currency = data.replace('chart_cbr_', '')
            context.user_data['chart_currency'] = currency
            context.user_data['chart_type'] = 'cbr'
            await self.show_period_selection(query, user, context, currency)
        
        # Chart stock ticker selection
        elif data.startswith('chart_stock_'):
            ticker = data.replace('chart_stock_', '')
            context.user_data['chart_ticker'] = ticker
            await self.show_period_selection(query, user, context, ticker)
        
        # Back to chart type selection
        elif data == 'back_chart_type':
            await self.start_chart_selection_callback(query, user, context)
        
        # Conversion type selection
        elif data.startswith('convert_type_'):
            convert_type = data.replace('convert_type_', '')
            await self.handle_conversion_type_selection(query, user, context, convert_type)
        
        # Prediction type selection
        elif data.startswith('prediction_type_'):
            prediction_type = data.replace('prediction_type_', '')
            await self.handle_prediction_type_selection(query, user, context, prediction_type)
        
        # Prediction stock market selection
        elif data.startswith('prediction_stocks_'):
            market_type = data.replace('prediction_stocks_', '')
            await self.show_prediction_stock_selection(query, user, context, market_type)
        
        # Prediction CBR currency selection
        elif data.startswith('prediction_cbr_'):
            currency = data.replace('prediction_cbr_', '')
            context.user_data['prediction_asset'] = currency
            context.user_data['prediction_type'] = 'cbr'
            context.user_data['state'] = 'select_prediction'
            await self.generate_prediction(query, context, user, currency)
        
        # Prediction stock ticker selection
        elif data.startswith('prediction_stock_'):
            ticker = data.replace('prediction_stock_', '')
            context.user_data['prediction_asset'] = ticker
            context.user_data['state'] = 'select_prediction'
            await self.generate_prediction(query, context, user, ticker)
        
        # Settings callbacks
        elif data.startswith('settings_'):
            await self.handle_settings_callback(query, user, data)
        
        # Stocks callbacks
        elif data == 'stocks_menu':
            await self.bot.stocks_handler.show_stocks_menu(query, None)
        elif data == 'stocks_global':
            await self.bot.stocks_handler.show_global_stocks(query, user)
        elif data == 'stocks_russian':
            await self.bot.stocks_handler.show_russian_stocks(query, user)
        elif data == 'cbr_rates':
            await self.bot.stocks_handler.show_cbr_rates(query, user)
        elif data.startswith('stock_global_'):
            ticker = data.replace('stock_global_', '')
            await self.bot.stocks_handler.show_global_stock_info(query, user, ticker)
        elif data.startswith('stock_russian_'):
            ticker = data.replace('stock_russian_', '')
            await self.bot.stocks_handler.show_russian_stock_info(query, user, ticker)
        elif data.startswith('cbr_'):
            currency = data.replace('cbr_', '')
            await self.bot.stocks_handler.show_cbr_rate(query, user, currency)
        elif data.startswith('stock_chart_global_'):
            ticker = data.replace('stock_chart_global_', '')
            await self.bot.stocks_handler.show_stock_chart(query, user, ticker, 'global')
        elif data.startswith('stock_chart_russian_'):
            ticker = data.replace('stock_chart_russian_', '')
            await self.bot.stocks_handler.show_stock_chart(query, user, ticker, 'russian')
        elif data.startswith('cbr_chart_'):
            currency = data.replace('cbr_chart_', '')
            await self.bot.stocks_handler.show_cbr_chart(query, user, currency)
        
        # CS2 callbacks
        elif data.startswith('cs2_'):
            await self.bot.cs2_handler.handle_cs2_callback(query, user, data)
        
        # Portfolio callbacks
        elif data == 'portfolio_menu':
            await self.bot.portfolio_handler.show_portfolio_menu(query, context)
        elif data == 'portfolio_add':
            await self.bot.portfolio_handler.show_add_asset_type(query, user)
        elif data == 'portfolio_view':
            await self.bot.portfolio_handler.show_portfolio_items(query, user)
        elif data == 'portfolio_summary':
            await self.bot.portfolio_handler.show_portfolio_summary(query, user)
        elif data == 'portfolio_chart':
            await self.bot.portfolio_handler.show_portfolio_chart(query, user)
        elif data.startswith('portfolio_add_'):
            asset_type = data.replace('portfolio_add_', '')
            await self.bot.portfolio_handler.show_asset_selection(query, user, asset_type)
        elif data.startswith('portfolio_select_crypto_'):
            crypto = data.replace('portfolio_select_crypto_', '')
            await self.bot.portfolio_handler.handle_asset_selected(query, user, 'crypto', crypto)
        elif data.startswith('portfolio_select_fiat_'):
            fiat = data.replace('portfolio_select_fiat_', '')
            await self.bot.portfolio_handler.handle_asset_selected(query, user, 'fiat', fiat)
        elif data.startswith('portfolio_select_stock_global_'):
            stock = data.replace('portfolio_select_stock_global_', '')
            await self.bot.portfolio_handler.handle_asset_selected(query, user, 'stock', stock)
        elif data.startswith('portfolio_select_stock_russian_'):
            stock = data.replace('portfolio_select_stock_russian_', '')
            await self.bot.portfolio_handler.handle_asset_selected(query, user, 'stock', stock)
        elif data == 'portfolio_stocks_global':
            await self.bot.portfolio_handler.show_global_stocks(query, user)
        elif data == 'portfolio_stocks_russian':
            await self.bot.portfolio_handler.show_russian_stocks(query, user)
        elif data.startswith('portfolio_qty_'):
            qty = float(data.replace('portfolio_qty_', ''))
            await self.bot.portfolio_handler.handle_quantity_selected(query, user, qty)
        elif data.startswith('portfolio_item_'):
            item_id = int(data.replace('portfolio_item_', ''))
            await self.bot.portfolio_handler.show_item_details(query, user, item_id)
        elif data.startswith('portfolio_delete_confirm_'):
            item_id = int(data.replace('portfolio_delete_confirm_', ''))
            await self.bot.portfolio_handler.handle_delete_confirm(query, user, item_id)
        elif data.startswith('portfolio_remove_'):
            item_id = int(data.replace('portfolio_remove_', ''))
            await self.bot.portfolio_handler.confirm_remove_item(query, user, item_id)
        elif data == 'portfolio_rebalance':
            await self.bot.portfolio_handler.show_rebalance_menu(query, user)
        elif data == 'rebalance_presets':
            await self.bot.portfolio_handler.show_preset_strategies(query, user)
        elif data.startswith('rebalance_apply_'):
            strategy = data.replace('rebalance_apply_', '')
            await self.bot.portfolio_handler.apply_rebalancing_strategy(query, user, strategy)
        elif data == 'rebalance_custom':
            await query.answer("Custom allocation coming soon!", show_alert=True)
        
        # Export callbacks
        elif data == 'export_menu':
            await self.bot.export_handler.show_export_menu(query, context)
        elif data == 'export_portfolio':
            await self.bot.export_handler.handle_export_portfolio(query, user)
        elif data == 'export_alerts':
            await self.bot.export_handler.handle_export_alerts(query, user)
        elif data == 'export_history':
            await self.bot.export_handler.handle_export_history(query, user)
        elif data == 'export_all':
            await self.bot.export_handler.handle_export_all(query, user)
        elif data == 'export_sheets_menu':
            await self.bot.export_handler.show_sheets_menu(query, user)
        elif data == 'export_sheets_auth':
            await self.bot.export_handler.handle_sheets_auth(query, user)
        elif data == 'export_notion_menu':
            await self.bot.export_handler.show_notion_menu(query, user)
        elif data == 'export_notion_setup':
            await self.bot.export_handler.handle_notion_setup(query, user)
        
        # News callbacks
        elif data == 'news_menu':
            await self.bot.news_handler.show_news_menu(query, context)
        elif data == 'news_latest':
            await self.bot.news_handler.show_latest_news(query, user)
        elif data == 'news_subscriptions':
            await self.bot.news_handler.show_subscriptions(query, user)
        elif data == 'news_subscribe':
            await self.bot.news_handler.show_subscribe_assets(query, user)
        elif data.startswith('news_select_'):
            asset = data.replace('news_select_', '')
            await self.bot.news_handler.handle_asset_selected(query, user, asset)
        elif data.startswith('news_cat_'):
            parts = data.replace('news_cat_', '').split('_')
            asset = parts[0]
            category = parts[1] if len(parts) > 1 else 'all'
            await self.bot.news_handler.handle_category_selected(query, user, asset, category)
        elif data.startswith('news_toggle_'):
            sub_id = int(data.replace('news_toggle_', ''))
            await self.bot.news_handler.handle_toggle_subscription(query, user, sub_id)
        elif data.startswith('news_delete_'):
            sub_id = int(data.replace('news_delete_', ''))
            await self.bot.news_handler.handle_delete_subscription(query, user, sub_id)
        
        # Report callbacks
        elif data == 'reports_menu':
            await self.bot.report_handler.show_report_menu(query, context)
        elif data == 'report_generate':
            await self.bot.report_handler.generate_report(query, user)
        elif data == 'report_weekly':
            await self.bot.report_handler.generate_weekly_report(query, user)
        elif data == 'report_portfolio':
            await self.bot.report_handler.generate_portfolio_report(query, user)
        elif data == 'report_subscribe':
            await self.bot.report_handler.show_subscribe_options(query, user)
        elif data.startswith('report_sub_'):
            report_type = data.replace('report_sub_', '')
            await self.bot.report_handler.subscribe_to_report(query, user, report_type)
        
        # Dashboard callbacks
        elif data == 'dashboard_menu':
            await self.bot.dashboard_handler.show_dashboard_menu(query, context)
        elif data == 'dashboard_features':
            await self.bot.dashboard_handler.show_dashboard_features(query, user)
        
        # AI Assistant callbacks
        elif data == 'ai_menu':
            await self.bot.ai_handler.show_ai_menu(query, context)
        elif data == 'ai_setup':
            await self.bot.ai_handler.show_setup_instructions(query, user)
        elif data == 'ai_ask':
            await self.bot.ai_handler.handle_ask_question(query, user)
        elif data == 'ai_market':
            await self.bot.ai_handler.handle_market_analysis(query, user)
        elif data.startswith('ai_analyze_'):
            asset = data.replace('ai_analyze_', '')
            await self.bot.ai_handler.perform_market_analysis(query, user, asset)
        elif data == 'ai_portfolio':
            await self.bot.ai_handler.handle_portfolio_insights(query, user)
        elif data == 'ai_suggest':
            await self.bot.ai_handler.handle_suggestions(query, user)
        
        # Analytics callbacks
        elif data == 'analytics_menu':
            await self.bot.analytics_handler.show_analytics_menu(query, context)
        elif data == 'analytics_asset':
            await self.bot.analytics_handler.show_asset_selection(query, user, 'analyze')
        elif data.startswith('analyze_'):
            symbol = data.replace('analyze_', '')
            await self.bot.analytics_handler.perform_asset_analytics(query, user, symbol)
        elif data == 'analytics_correlation':
            await self.bot.analytics_handler.show_correlation_selection(query, user)
        elif data.startswith('corr1_'):
            symbol = data.replace('corr1_', '')
            await self.bot.analytics_handler.handle_correlation_asset1(query, user, symbol)
        elif data.startswith('corr2_'):
            symbol = data.replace('corr2_', '')
            await self.bot.analytics_handler.perform_correlation_analysis(query, user, symbol)
        elif data == 'analytics_portfolio':
            # TODO: Implement portfolio analytics
            await query.answer("Portfolio analytics coming soon!", show_alert=True)
        
        # Trading signals callbacks
        elif data == 'signals_menu':
            await self.bot.trading_handler.show_signals_menu(query, context)
        elif data.startswith('signal_'):
            symbol = data.replace('signal_', '')
            await self.bot.trading_handler.show_trading_signals(query, user, symbol)
        elif data.startswith('signals_'):
            symbol = data.replace('signals_', '')
            await self.bot.trading_handler.show_signals_menu(query, context)
        
        # Admin panel callbacks
        elif data == 'admin_panel':
            await self.bot.admin_handler.show_admin_panel(query, user)
        elif data == 'admin_stats':
            await self.bot.admin_handler.show_statistics(query, user)
        elif data == 'admin_announce_create':
            await self.bot.admin_handler.start_announcement_creation(query, user)
        elif data == 'admin_announce_send':
            await self.bot.admin_handler.broadcast_announcement(query, user)
        elif data == 'admin_announce_history':
            await self.bot.admin_handler.show_announcements_history(query, user)
        elif data == 'admin_users':
            await query.answer("User management coming soon!", show_alert=True)
        
        # Back to main
        elif data == 'back_main':
            await query.message.reply_text(
                get_text(user.lang, 'main_menu'),
                reply_markup=self.bot.get_main_menu_keyboard(user.lang),
                parse_mode='Markdown'
            )
    
    async def handle_currency_selection(self, query, context, user, currency):
        """Handle currency selection based on state."""
        state = context.user_data.get('state', 'select_from')
        
        if state == 'select_from':
            context.user_data['from_currency'] = currency
            context.user_data['state'] = 'select_to'
            await query.edit_message_text(
                get_text(user.lang, 'select_to_currency') + f" (From: {currency})",
                reply_markup=self.bot.get_currency_selection_keyboard(user.lang, 'popular'),
                parse_mode='Markdown'
            )
        elif state == 'select_to':
            context.user_data['to_currency'] = currency
            from_curr = context.user_data.get('from_currency', 'BTC')
            context.user_data['state'] = 'select_amount'
            await query.edit_message_text(
                get_text(user.lang, 'enter_amount') + f" ({from_curr} → {currency})",
                reply_markup=self.bot.get_amount_presets_keyboard(user.lang),
                parse_mode='Markdown'
            )
        elif state == 'select_chart':
            context.user_data['chart_pair'] = currency
            await self.show_period_selection(query, user, currency)
        elif state == 'select_prediction':
            await self.generate_prediction(query, context, user, currency)
        elif state == 'select_compare':
            await self.compare_rates(query, user, currency)
    
    async def start_conversion(self, update, user, context):
        """Start conversion flow - show currency type selection."""
        context.user_data['state'] = 'select_conversion_type'
        
        keyboard = [
            [InlineKeyboardButton(
                get_text(user.lang, 'crypto_rates'),
                callback_data='convert_type_crypto'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'fiat_currencies'),
                callback_data='convert_type_fiat'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'cbr_rates'),
                callback_data='convert_type_cbr'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'popular_pairs'),
                callback_data='convert_type_popular'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'back'),
                callback_data='back_main'
            )]
        ]
        
        await update.message.reply_text(
            get_text(user.lang, 'select_conversion_type'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_conversion_type_selection(self, query, user, context, convert_type: str):
        """Handle conversion type selection."""
        context.user_data['conversion_type'] = convert_type
        
        if convert_type == 'crypto':
            # Show crypto currency selection
            context.user_data['state'] = 'select_from'
            await query.edit_message_text(
                get_text(user.lang, 'select_from_currency'),
                reply_markup=self.bot.get_currency_selection_keyboard(user.lang, 'crypto'),
                parse_mode='Markdown'
            )
        
        elif convert_type == 'fiat':
            # Show fiat currency selection
            context.user_data['state'] = 'select_from'
            await query.edit_message_text(
                get_text(user.lang, 'select_from_currency'),
                reply_markup=self.bot.get_currency_selection_keyboard(user.lang, 'fiat'),
                parse_mode='Markdown'
            )
        
        elif convert_type == 'cbr':
            # Show CBR rates view (no conversion, just display)
            await self.show_cbr_rates_list(query, user)
        
        elif convert_type == 'popular':
            # Show popular pairs selection
            context.user_data['state'] = 'select_from'
            await query.edit_message_text(
                get_text(user.lang, 'select_from_currency'),
                reply_markup=self.bot.get_currency_selection_keyboard(user.lang, 'popular'),
                parse_mode='Markdown'
            )
    
    async def show_cbr_rates_list(self, query, user):
        """Show list of CBR exchange rates."""
        from ..services.stock_service import StockService
        
        message = f"💵 **{get_text(user.lang, 'cbr_rates')}**\n\n"
        message += f"🇷🇺 {get_text(user.lang, 'cbr_official_rates')}\n\n"
        
        currencies = list(StockService.CBR_CURRENCIES.keys())
        
        # Fetch current rates
        for currency in currencies:
            rate_data = self.bot.stock_service.get_cbr_rate(currency)
            if rate_data:
                change_emoji = '📈' if rate_data['change_pct'] >= 0 else '📉'
                sign = '+' if rate_data['change_pct'] >= 0 else ''
                message += f"{change_emoji} **{currency}/RUB:** {rate_data['rate']:.4f} ₽ ({sign}{rate_data['change_pct']:.2f}%)\n"
        
        # Add buttons for detailed view
        keyboard = []
        row = []
        for currency in currencies:
            row.append(InlineKeyboardButton(currency, callback_data=f'cbr_{currency}'))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton(
            get_text(user.lang, 'back'),
            callback_data='back_main'
        )])
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def start_chart_selection(self, update, user, context):
        """Start chart selection flow - show asset type selection."""
        context.user_data['state'] = 'select_chart_type'
        
        keyboard = [
            [InlineKeyboardButton(
                get_text(user.lang, 'crypto_rates'),
                callback_data='chart_type_crypto'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'stocks'),
                callback_data='chart_type_stocks'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'cbr_rates'),
                callback_data='chart_type_cbr'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'back'),
                callback_data='back_main'
            )]
        ]
        
        await update.message.reply_text(
            get_text(user.lang, 'select_chart_type'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def start_prediction_selection(self, update, user, context):
        """Start prediction selection flow - show asset type selection."""
        context.user_data['state'] = 'select_prediction_type'
        
        keyboard = [
            [InlineKeyboardButton(
                get_text(user.lang, 'crypto_rates'),
                callback_data='prediction_type_crypto'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'stocks'),
                callback_data='prediction_type_stocks'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'cbr_rates'),
                callback_data='prediction_type_cbr'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'back'),
                callback_data='back_main'
            )]
        ]
        
        await update.message.reply_text(
            get_text(user.lang, 'select_prediction_type'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_prediction_type_selection(self, query, user, context, prediction_type: str):
        """Handle prediction type selection (crypto, stocks, cbr)."""
        context.user_data['prediction_type'] = prediction_type
        
        if prediction_type == 'crypto':
            # Show cryptocurrency selection
            context.user_data['state'] = 'select_prediction'
            await query.edit_message_text(
                get_text(user.lang, 'select_currency_prediction'),
                reply_markup=self.bot.get_currency_selection_keyboard(user.lang, 'crypto'),
                parse_mode='Markdown'
            )
        
        elif prediction_type == 'stocks':
            # Show stock market selection (global/russian)
            keyboard = [
                [InlineKeyboardButton(
                    get_text(user.lang, 'stocks_global'),
                    callback_data='prediction_stocks_global'
                )],
                [InlineKeyboardButton(
                    get_text(user.lang, 'stocks_russian'),
                    callback_data='prediction_stocks_russian'
                )],
                [InlineKeyboardButton(
                    get_text(user.lang, 'back'),
                    callback_data='back_prediction_type'
                )]
            ]
            await query.edit_message_text(
                get_text(user.lang, 'select_stock_market'),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif prediction_type == 'cbr':
            # Show CBR currencies selection
            from ..services.stock_service import StockService
            currencies = list(StockService.CBR_CURRENCIES.keys())
            
            keyboard = []
            row = []
            for currency in currencies:
                row.append(InlineKeyboardButton(currency, callback_data=f'prediction_cbr_{currency}'))
                if len(row) == 4:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            
            keyboard.append([InlineKeyboardButton(
                get_text(user.lang, 'back'),
                callback_data='back_prediction_type'
            )])
            
            await query.edit_message_text(
                get_text(user.lang, 'cbr_rates_select'),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    async def show_prediction_stock_selection(self, query, user, context, market_type: str):
        """Show stock selection for predictions."""
        context.user_data['stock_type'] = market_type
        context.user_data['prediction_type'] = 'stock'
        
        if market_type == 'global':
            stocks = list(self.bot.stock_service.GLOBAL_STOCKS.keys())[:24]
        else:
            stocks = list(self.bot.stock_service.RUSSIAN_STOCKS.keys())[:18]
        
        keyboard = []
        row = []
        for ticker in stocks:
            row.append(InlineKeyboardButton(ticker, callback_data=f'prediction_stock_{ticker}'))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton(
            get_text(user.lang, 'back'),
            callback_data='prediction_type_stocks'
        )])
        
        select_key = 'stocks_global_select' if market_type == 'global' else 'stocks_russian_select'
        await query.edit_message_text(
            get_text(user.lang, select_key),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def start_comparison_selection(self, update, user, context):
        """Start comparison selection flow."""
        context.user_data['state'] = 'select_compare'
        await update.message.reply_text(
            get_text(user.lang, 'select_currency_compare'),
            reply_markup=self.bot.get_currency_selection_keyboard(user.lang, 'crypto'),
            parse_mode='Markdown'
        )
    
    async def perform_conversion(self, update, context, amount, user):
        """Perform currency conversion."""
        from_curr = context.user_data.get('from_currency')
        to_curr = context.user_data.get('to_currency')
        
        # Validate currencies
        if not from_curr or not to_curr:
            await update.message.reply_text(
                get_text(user.lang, 'error', msg='Please select currencies first'),
                parse_mode='Markdown',
                reply_markup=self.bot.get_main_menu_keyboard(user.lang)
            )
            context.user_data.clear()
            return
        
        result = self.bot.converter.convert(amount, from_curr, to_curr, user.telegram_id)
        
        if result:
            rate = self.bot.converter.get_rate(from_curr, to_curr, user.telegram_id)
            
            # Save to history
            self.bot.db.add_conversion(user.telegram_id, from_curr, to_curr, amount, result, rate)
            self.bot.metrics.log_conversion(user.telegram_id)
            
            await update.message.reply_text(
                get_text(user.lang, 'conversion_result',
                        amount=amount, from_curr=from_curr,
                        result=f"{result:.2f}", to_curr=to_curr,
                        rate=f"{rate:.6f}",
                        time=datetime.now().strftime('%H:%M')),
                parse_mode='Markdown',
                reply_markup=self.bot.get_main_menu_keyboard(user.lang)
            )
        else:
            await update.message.reply_text(
                get_text(user.lang, 'rate_unavailable'),
                reply_markup=self.bot.get_main_menu_keyboard(user.lang)
            )
        
        context.user_data.clear()
    
    async def perform_conversion_callback(self, query, context, amount, user):
        """Perform conversion from callback."""
        from_curr = context.user_data.get('from_currency')
        to_curr = context.user_data.get('to_currency')
        
        # Validate currencies
        if not from_curr or not to_curr:
            await query.edit_message_text(
                get_text(user.lang, 'error', msg='Please select currencies first'),
                parse_mode='Markdown'
            )
            context.user_data.clear()
            return
        
        result = self.bot.converter.convert(amount, from_curr, to_curr, user.telegram_id)
        
        if result:
            rate = self.bot.converter.get_rate(from_curr, to_curr, user.telegram_id)
            
            # Save to history
            self.bot.db.add_conversion(user.telegram_id, from_curr, to_curr, amount, result, rate)
            self.bot.metrics.log_conversion(user.telegram_id)
            
            await query.edit_message_text(
                get_text(user.lang, 'conversion_result',
                        amount=amount, from_curr=from_curr,
                        result=f"{result:.2f}", to_curr=to_curr,
                        rate=f"{rate:.6f}",
                        time=datetime.now().strftime('%H:%M')),
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(get_text(user.lang, 'rate_unavailable'))
        
        context.user_data.clear()
    
    async def show_period_selection(self, query, user, currency):
        """Show period selection for charts."""
        keyboard = [
            [InlineKeyboardButton('7 days', callback_data='period_7'),
             InlineKeyboardButton('30 days', callback_data='period_30')],
            [InlineKeyboardButton('90 days', callback_data='period_90'),
             InlineKeyboardButton('1 year', callback_data='period_365')],
            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='back_main')]
        ]
        await query.edit_message_text(
            f"📊 **Chart for 1 {currency}**\n\nSelect time period:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_chart_type_selection(self, query, user, context, chart_type: str):
        """Handle chart type selection (crypto, stocks, cbr)."""
        context.user_data['chart_type'] = chart_type
        
        if chart_type == 'crypto':
            # Show cryptocurrency selection
            await query.edit_message_text(
                get_text(user.lang, 'select_currency_chart'),
                reply_markup=self.bot.get_currency_selection_keyboard(user.lang, 'crypto'),
                parse_mode='Markdown'
            )
        
        elif chart_type == 'stocks':
            # Show stock market selection (global/russian)
            keyboard = [
                [InlineKeyboardButton(
                    get_text(user.lang, 'stocks_global'),
                    callback_data='chart_stocks_global'
                )],
                [InlineKeyboardButton(
                    get_text(user.lang, 'stocks_russian'),
                    callback_data='chart_stocks_russian'
                )],
                [InlineKeyboardButton(
                    get_text(user.lang, 'back'),
                    callback_data='back_chart_type'
                )]
            ]
            await query.edit_message_text(
                get_text(user.lang, 'select_stock_market'),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif chart_type == 'cbr':
            # Show CBR currencies selection
            from ..services.stock_service import StockService
            currencies = list(StockService.CBR_CURRENCIES.keys())
            
            keyboard = []
            row = []
            for currency in currencies:
                row.append(InlineKeyboardButton(currency, callback_data=f'chart_cbr_{currency}'))
                if len(row) == 4:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            
            keyboard.append([InlineKeyboardButton(
                get_text(user.lang, 'back'),
                callback_data='back_chart_type'
            )])
            
            await query.edit_message_text(
                get_text(user.lang, 'cbr_rates_select'),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    async def start_chart_selection_callback(self, query, user, context):
        """Start chart selection from callback."""
        context.user_data['state'] = 'select_chart_type'
        
        keyboard = [
            [InlineKeyboardButton(
                get_text(user.lang, 'crypto_rates'),
                callback_data='chart_type_crypto'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'stocks'),
                callback_data='chart_type_stocks'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'cbr_rates'),
                callback_data='chart_type_cbr'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'back'),
                callback_data='back_main'
            )]
        ]
        
        await query.edit_message_text(
            get_text(user.lang, 'select_chart_type'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_chart_stock_selection(self, query, user, context, market_type: str):
        """Show stock selection for charts."""
        context.user_data['stock_type'] = market_type
        context.user_data['chart_type'] = 'stock'
        
        if market_type == 'global':
            stocks = list(self.bot.stock_service.GLOBAL_STOCKS.keys())[:24]
        else:
            stocks = list(self.bot.stock_service.RUSSIAN_STOCKS.keys())[:18]
        
        keyboard = []
        row = []
        for ticker in stocks:
            row.append(InlineKeyboardButton(ticker, callback_data=f'chart_stock_{ticker}'))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton(
            get_text(user.lang, 'back'),
            callback_data='chart_type_stocks'
        )])
        
        select_key = 'stocks_global_select' if market_type == 'global' else 'stocks_russian_select'
        await query.edit_message_text(
            get_text(user.lang, select_key),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_period_selection(self, query, user, context, asset: str):
        """Show period selection for chart."""
        keyboard = [
            [InlineKeyboardButton('7 days', callback_data='period_7'),
             InlineKeyboardButton('30 days', callback_data='period_30')],
            [InlineKeyboardButton('90 days', callback_data='period_90'),
             InlineKeyboardButton('1 year', callback_data='period_365')],
            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='back_chart_type')]
        ]
        
        chart_type = context.user_data.get('chart_type', 'crypto')
        if chart_type == 'cbr':
            title = f"💵 **CBR Rate: {asset}/RUB**"
        elif chart_type == 'stock':
            title = f"📊 **Stock: {asset}**"
        else:
            title = f"📊 **Chart for {asset}**"
        
        await query.edit_message_text(
            f"{title}\n\nSelect time period:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def generate_chart(self, query, user, pair, period=30):
        """Generate chart for pair (price of 1 unit)."""
        await query.edit_message_text(f"📊 Generating chart for **1 {pair}**...\n\nPlease wait...", parse_mode='Markdown')
        
        chart_data, stats = self.bot.chart_generator.generate_chart(f"{pair}-USD", period)
        
        if chart_data and stats:
            # Format stats for 1 unit
            caption = (
                f"📊 **{pair}/USD Chart** ({period} days)\n\n"
                f"💰 Current price: **${stats.get('current', 0):.2f}**\n"
                f"📈 High: ${stats.get('high', 0):.2f}\n"
                f"📉 Low: ${stats.get('low', 0):.2f}\n"
                f"📊 Average: ${stats.get('avg', 0):.2f}\n\n"
                f"_Price shown for 1 {pair}_"
            )
            await query.message.reply_photo(
                photo=chart_data,
                caption=caption,
                parse_mode='Markdown'
            )
            self.bot.metrics.log_chart(user.telegram_id)
        else:
            await query.edit_message_text('❌ Chart generation failed. Please try again.', parse_mode='Markdown')
    
    async def generate_prediction(self, query, context, user, pair):
        """Generate prediction for asset (crypto, stock, or CBR)."""
        user_context = context.user_data
        prediction_type = user_context.get('prediction_type', 'crypto')
        
        await query.edit_message_text(f"🔮 Generating AI forecast for **{pair}**...\n\nAnalyzing 90 days of data...", parse_mode='Markdown')
        
        model = user.prediction_model or 'arima'
        
        # Generate prediction based on asset type
        if prediction_type == 'cbr':
            pred_data, stats = await self.bot.prediction_generator.generate_cbr_prediction(pair, model, 90)
        elif prediction_type == 'stock':
            stock_type = user_context.get('stock_type', 'global')
            ticker = f"{pair}.ME" if stock_type == 'russian' and not pair.endswith('.ME') else pair
            pred_data, stats = self.bot.prediction_generator.generate_stock_prediction(ticker, model, 90)
        else:  # crypto
            pred_data, stats = self.bot.prediction_generator.generate_prediction(f"{pair}-USD", model, 90)
        
        # Check for errors in stats
        if stats and 'error' in stats:
            error_type = stats.get('error')
            if error_type == 'no_data':
                await query.edit_message_text(
                    f"❌ **No Data Available**\n\n"
                    f"Unable to fetch historical data for {pair}.\n\n"
                    f"This cryptocurrency may not be available on Yahoo Finance.\n\n"
                    f"Please try another cryptocurrency.",
                    parse_mode='Markdown'
                )
            elif error_type == 'insufficient_data':
                days_available = stats.get('days_available', 0)
                await query.edit_message_text(
                    f"❌ **Insufficient Historical Data**\n\n"
                    f"Not enough data for **{pair}** to generate a reliable forecast.\n\n"
                    f"📊 Available: {days_available} days\n"
                    f"📊 Required: At least 30 days\n\n"
                    f"Please try a more established cryptocurrency.",
                    parse_mode='Markdown'
                )
            elif error_type in ['invalid_price', 'invalid_forecast', 'forecast_failed']:
                await query.edit_message_text(
                    f"❌ **Forecast Generation Failed**\n\n"
                    f"Unable to generate a reliable forecast for {pair}.\n\n"
                    f"The data may be invalid or unstable.\n\n"
                    f"Please try again later or select another cryptocurrency.",
                    parse_mode='Markdown'
                )
            else:
                error_msg = stats.get('message', 'Unknown error')
                await query.edit_message_text(
                    f"❌ **Error**\n\n"
                    f"Failed to generate forecast for {pair}.\n\n"
                    f"Error: {error_msg}\n\n"
                    f"Please try again later.",
                    parse_mode='Markdown'
                )
            return
        
        if pred_data and stats:
            # Validate stats to prevent $0.00 display
            current = stats.get('current', 0)
            predicted = stats.get('predicted', 0)
            
            if current <= 0 or predicted <= 0:
                await query.edit_message_text(
                    f"❌ **Invalid Forecast Data**\n\n"
                    f"Generated forecast contains invalid values for {pair}.\n\n"
                    f"Please try again later.",
                    parse_mode='Markdown'
                )
                return
            
            # Format prediction caption based on asset type
            if prediction_type == 'cbr':
                asset_label = f"{pair}/RUB"
                price_symbol = '₽'
            elif prediction_type == 'stock':
                asset_label = pair
                price_symbol = '$'
            else:  # crypto
                asset_label = f"{pair}/USD"
                price_symbol = '$'
            
            caption = (
                f"🔮 **{asset_label} AI Forecast**\n\n"
                f"📊 **Current Price:** {price_symbol}{current:.2f}\n"
                f"🎯 **7-Day Forecast:** {price_symbol}{predicted:.2f}\n"
                f"📈 **Expected Change:** {stats.get('change', 0):+.2f}%\n"
                f"📉 **Trend:** {stats.get('trend', 'Unknown')}\n\n"
                f"🤖 **Model:** {stats.get('model', model.upper())}\n"
                f"🎲 **Confidence:** {stats.get('confidence', 'Medium').capitalize()}\n"
                f"📅 **Forecast Date:** {stats.get('forecast_date', 'N/A')}\n\n"
                f"📊 **Based on:** {stats.get('days_analyzed', 90)} days of {stats.get('data_source', 'Yahoo Finance')} data\n\n"
                f"⚠️ _This is NOT financial advice. Forecasts are based on mathematical models and do not account for market news or events._"
            )
            await query.message.reply_photo(
                photo=pred_data,
                caption=caption,
                parse_mode='Markdown'
            )
            self.bot.metrics.log_prediction(user.telegram_id)
            
            # Save prediction for accuracy tracking
            try:
                self.bot.prediction_generator.save_prediction(
                    user_id=user.telegram_id,
                    pair=f"{pair}-USD",
                    predicted_price=predicted,
                    model_type=stats.get('model_type', model),
                    forecast_days=stats.get('forecast_days', 7)
                )
            except Exception as e:
                logger.error(f"Failed to save prediction: {e}")
        else:
            await query.edit_message_text(
                f"❌ **Forecast Generation Failed**\n\n"
                f"Unable to generate forecast for {pair}.\n\n"
                f"Please try again later or select another cryptocurrency.",
                parse_mode='Markdown'
            )
    
    async def compare_rates(self, query, user, symbol):
        """Compare rates across exchanges (for 1 unit)."""
        # Show explanatory message first
        intro_text = (
            f"⚖️ **Compare Live Prices for {symbol}**\n\n"
            f"💡 **What is this?**\n"
            f"This feature compares real-time prices for 1 {symbol} across 5+ major cryptocurrency exchanges.\n\n"
            f"🎯 **Why is it useful?**\n"
            f"• Find the best exchange to buy or sell\n"
            f"• See price differences between platforms\n"
            f"• Spot arbitrage opportunities\n\n"
            f"🔄 Fetching data from exchanges..."
        )
        await query.edit_message_text(intro_text, parse_mode='Markdown')
        
        rates = self.bot.converter.get_all_crypto_rates(symbol, 'USDT', user.telegram_id)
        
        if not rates or len(rates) == 0:
            await query.edit_message_text(
                f"❌ **No Data Available**\n\n"
                f"Unable to fetch price data for {symbol}/USDT from exchanges.\n\n"
                f"**Possible reasons:**\n"
                f"• {symbol} may not be listed on major exchanges\n"
                f"• Temporary API issues\n"
                f"• Network connectivity problems\n\n"
                f"Please try again later or select a more popular cryptocurrency.",
                parse_mode='Markdown'
            )
            return
        
        # Calculate statistics
        prices = [r[1] for r in rates]
        avg = sum(prices) / len(prices)
        high = max(prices)
        low = min(prices)
        high_ex = [ex for ex, rate in rates if rate == high][0]
        low_ex = [ex for ex, rate in rates if rate == low][0]
        spread = ((high - low) / avg) * 100
        diff_vs_avg = high - low
        
        # Format rates with highlighting for best/worst prices
        rate_lines = []
        for ex, rate in sorted(rates, key=lambda x: x[1], reverse=True):
            if rate == low:
                # Best price (lowest)
                rate_lines.append(f"✅ **{ex}:** ${rate:.2f} _← Best price!_")
            elif rate == high:
                # Worst price (highest)
                rate_lines.append(f"⚠️ **{ex}:** ${rate:.2f}")
            else:
                rate_lines.append(f"• **{ex}:** ${rate:.2f}")
        
        rate_text = '\n'.join(rate_lines)
        
        # Create comprehensive result
        result_text = (
            f"⚖️ **{symbol}/USDT Price Comparison**\n\n"
            f"📊 **Live Prices (for 1 {symbol}):**\n"
            f"{rate_text}\n\n"
            f"📈 **Market Statistics:**\n"
            f"💰 Average Price: **${avg:.2f}**\n"
            f"📈 Highest: ${high:.2f} ({high_ex})\n"
            f"📉 Lowest: ${low:.2f} ({low_ex})\n"
            f"📊 Price Spread: {spread:.2f}% (${diff_vs_avg:.2f})\n\n"
            f"💡 **Recommendation:**\n"
            f"Buy on **{low_ex}** for the best price!\n"
            f"You save ${diff_vs_avg:.2f} vs highest price.\n\n"
            f"_Updated: {self.bot.converter.cache.cache.get(f'{symbol}_USDT', {}).get('timestamp', 'just now')}_"
        )
        
        await query.edit_message_text(result_text, parse_mode='Markdown')
        self.bot.metrics.log_comparison(user.telegram_id)
    
    async def toggle_favorite(self, query, user, currency):
        """Toggle currency in favorites."""
        if self.bot.db.is_favorite(user.telegram_id, currency):
            self.bot.db.remove_favorite(user.telegram_id, currency)
            await query.answer(get_text(user.lang, 'favorite_removed', currency=currency))
        else:
            self.bot.db.add_favorite(user.telegram_id, currency)
            await query.answer(get_text(user.lang, 'favorite_added', currency=currency))
    
    async def handle_settings_callback(self, query, user, data):
        """Handle settings menu callbacks."""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        if data == 'settings_lang_en':
            # Change language to English
            self.bot.db.update_user(user.telegram_id, lang='en')
            await query.answer('✅ Language set: English!')
            try:
                await query.edit_message_text(
                    f"⚙️ **Settings Updated**\n\n"
                    f"🌍 Language changed to: 🇬🇧 English\n\n"
                    f"All messages will now be displayed in English.",
                    parse_mode='Markdown'
                )
            except telegram.error.BadRequest:
                pass  # Message not modified
            # Show main menu in new language
            await query.message.reply_text(
                get_text('en', 'main_menu'),
                reply_markup=self.bot.get_main_menu_keyboard('en'),
                parse_mode='Markdown'
            )
        
        elif data == 'settings_lang_ru':
            # Change language to Russian
            self.bot.db.update_user(user.telegram_id, lang='ru')
            await query.answer('✅ Язык установлен: Русский!')
            try:
                await query.edit_message_text(
                    f"⚙️ **Настройки обновлены**\n\n"
                    f"🌍 Язык изменён на: 🇷🇺 Русский\n\n"
                    f"Все сообщения теперь будут отображаться на русском языке.",
                    parse_mode='Markdown'
                )
            except telegram.error.BadRequest:
                pass  # Message not modified
            # Show main menu in new language
            await query.message.reply_text(
                get_text('ru', 'main_menu'),
                reply_markup=self.bot.get_main_menu_keyboard('ru'),
                parse_mode='Markdown'
            )
        
        elif data == 'settings_theme':
            # Show theme selection
            keyboard = [
                [
                    InlineKeyboardButton('☀️ Light', callback_data='settings_theme_light'),
                    InlineKeyboardButton('🌙 Dark', callback_data='settings_theme_dark')
                ],
                [
                    InlineKeyboardButton('🔄 Auto', callback_data='settings_theme_auto')
                ],
                [
                    InlineKeyboardButton('◀️ Back', callback_data='settings_back')
                ]
            ]
            
            current_theme = user.chart_theme if hasattr(user, 'chart_theme') else 'light'
            theme_emoji = '☀️' if current_theme == 'light' else '🌙' if current_theme == 'dark' else '🔄'
            
            await query.edit_message_text(
                f"🎨 **Chart Theme Settings**\n\n"
                f"Current theme: {theme_emoji} {current_theme.title()}\n\n"
                f"Select a theme for charts and visualizations:\n"
                f"• ☀️ **Light** - White background, ideal for day use\n"
                f"• 🌙 **Dark** - Dark background, easier on the eyes\n"
                f"• 🔄 **Auto** - Matches system settings (coming soon)",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith('settings_theme_'):
            theme = data.replace('settings_theme_', '')
            self.bot.db.update_user(user.telegram_id, chart_theme=theme)
            
            theme_emoji = '☀️' if theme == 'light' else '🌙' if theme == 'dark' else '🔄'
            theme_name = get_text(user.lang, f'theme_{theme}')
            
            await query.answer(get_text(user.lang, 'theme_changed', theme=theme_name))
            await query.edit_message_text(
                f"✅ **Theme Updated**\n\n"
                f"🎨 Chart theme changed to: {theme_emoji} {theme.title()}\n\n"
                f"All charts and visualizations will now use the {theme} theme.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton('◀️ Back to Settings', callback_data='settings_back')]
                ]),
                parse_mode='Markdown'
            )
        
        elif data == 'settings_back':
            # Return to settings menu
            from ..handlers.messages import MessageHandlers
            message_handler = MessageHandlers(self.bot)
            # Create a fake update object to reuse show_settings
            class FakeUpdate:
                def __init__(self, message):
                    self.effective_user = message.from_user
                    self.message = message
            
            fake_update = FakeUpdate(query.message)
            await message_handler.show_settings(fake_update, None)
        
        elif data == 'settings_alerts':
            # Show alerts management
            alerts = self.bot.alert_manager.get_alerts(user.telegram_id)
            
            if not alerts:
                await query.edit_message_text(
                    f"🔔 **Alert Management**\n\n"
                    f"You have no active price alerts.\n\n"
                    f"Price alerts notify you when a cryptocurrency reaches your target price.\n\n"
                    f"_Feature coming soon: Set alerts via bot commands!_",
                    parse_mode='Markdown'
                )
            else:
                alert_text = '\n'.join([
                    f"{i+1}. **{a['pair']}** {a['condition']} ${a['target']}"
                    for i, a in enumerate(alerts)
                ])
                
                await query.edit_message_text(
                    f"🔔 **Your Active Alerts**\n\n"
                    f"{alert_text}\n\n"
                    f"You will be notified when prices reach your targets.\n\n"
                    f"_To remove alerts, use /cancel or contact support_",
                    parse_mode='Markdown'
                )
        
        elif data == 'settings_stats':
            # Show bot statistics
            bot_stats = self.bot.metrics.get_stats_text()
            
            await query.edit_message_text(
                f"📊 **Bot Statistics**\n\n"
                f"{bot_stats}\n\n"
                f"_These are global statistics for all users_",
                parse_mode='Markdown'
            )
        
        elif data == 'settings_about':
            # Show about information
            await query.edit_message_text(
                get_text(user.lang, 'about_text'),
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
