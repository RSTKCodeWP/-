"""Portfolio handler for CoinFlow bot."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..localization import get_text
from ..utils.logger import setup_logger

logger = setup_logger('portfolio_handler')


class PortfolioHandler:
    """Handler for portfolio management."""
    
    def __init__(self, bot):
        """Initialize portfolio handler."""
        self.bot = bot
    
    async def show_portfolio_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main portfolio menu."""
        user_id = update.effective_user.id
        user = self.bot.db.get_user(user_id)
        
        # Get portfolio summary
        summary = self.bot.portfolio_service.get_portfolio_summary(user_id)
        
        keyboard = [
            [
                InlineKeyboardButton(get_text(user.lang, 'portfolio_view'), callback_data='portfolio_view'),
                InlineKeyboardButton(get_text(user.lang, 'portfolio_add'), callback_data='portfolio_add')
            ],
            [
                InlineKeyboardButton('🔄 Rebalance', callback_data='portfolio_rebalance'),
                InlineKeyboardButton(get_text(user.lang, 'portfolio_export'), callback_data='portfolio_export')
            ],
            [
                InlineKeyboardButton(get_text(user.lang, 'portfolio_summary'), callback_data='portfolio_summary'),
                InlineKeyboardButton(get_text(user.lang, 'portfolio_chart'), callback_data='portfolio_chart')
            ],
            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='back_main')]
        ]
        
        # Build message
        if summary['total_items'] == 0:
            message = get_text(user.lang, 'portfolio_empty')
        else:
            message = get_text(user.lang, 'portfolio_menu')
            message += f"\n\n📊 {get_text(user.lang, 'portfolio_total_value')}: ${summary['total_value_usd']:.2f}"
            message += f"\n💰 В рублях: ₽{summary['total_value_rub']:.2f}"
            message += f"\n📦 Активов: {summary['total_items']}"
            
            if summary.get('total_profit_loss_usd'):
                pl_emoji = '📈' if summary['total_profit_loss_usd'] > 0 else '📉'
                message += f"\n{pl_emoji} {get_text(user.lang, 'portfolio_profit_loss')}: "
                message += f"${summary['total_profit_loss_usd']:.2f} ({summary['total_profit_loss_pct']:.2f}%)"
        
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
    
    async def show_add_asset_type(self, query, user):
        """Show asset type selection."""
        keyboard = [
            [
                InlineKeyboardButton(get_text(user.lang, 'portfolio_type_crypto'), callback_data='portfolio_add_crypto'),
                InlineKeyboardButton(get_text(user.lang, 'portfolio_type_stock'), callback_data='portfolio_add_stock')
            ],
            [
                InlineKeyboardButton(get_text(user.lang, 'portfolio_type_fiat'), callback_data='portfolio_add_fiat'),
                InlineKeyboardButton(get_text(user.lang, 'portfolio_type_cs2'), callback_data='portfolio_add_cs2')
            ],
            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='portfolio_menu')]
        ]
        
        await query.edit_message_text(
            get_text(user.lang, 'portfolio_select_type'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_asset_selection(self, query, user, asset_type: str):
        """Show asset selection based on type."""
        keyboard = []
        
        if asset_type == 'crypto':
            # Show popular cryptocurrencies
            cryptos = ['BTC', 'ETH', 'BNB', 'SOL', 'USDT', 'USDC', 'XRP', 'ADA', 'DOGE']
            for i in range(0, len(cryptos), 3):
                row = [
                    InlineKeyboardButton(crypto, callback_data=f'portfolio_select_crypto_{crypto}')
                    for crypto in cryptos[i:i+3]
                ]
                keyboard.append(row)
        
        elif asset_type == 'stock':
            # Show stock categories
            keyboard = [
                [InlineKeyboardButton('🌍 Global Stocks', callback_data='portfolio_stocks_global')],
                [InlineKeyboardButton('🇷🇺 Russian Stocks', callback_data='portfolio_stocks_russian')]
            ]
        
        elif asset_type == 'fiat':
            # Show popular fiat currencies
            fiats = ['USD', 'EUR', 'RUB', 'GBP', 'JPY', 'CNY']
            for i in range(0, len(fiats), 3):
                row = [
                    InlineKeyboardButton(fiat, callback_data=f'portfolio_select_fiat_{fiat}')
                    for fiat in fiats[i:i+3]
                ]
                keyboard.append(row)
        
        elif asset_type == 'cs2':
            # Redirect to CS2 category selection
            await self.bot.cs2_handler.show_cs2_menu(query, context=None, for_portfolio=True)
            return
        
        keyboard.append([InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='portfolio_add')])
        
        await query.edit_message_text(
            f"📦 Select {asset_type}:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_global_stocks(self, query, user):
        """Show global stocks for portfolio."""
        keyboard = []
        stocks = list(self.bot.stock_service.GLOBAL_STOCKS.keys())[:15]  # Top 15
        
        for i in range(0, len(stocks), 2):
            row = [
                InlineKeyboardButton(
                    f"{stock} - {self.bot.stock_service.GLOBAL_STOCKS[stock][:20]}",
                    callback_data=f'portfolio_select_stock_global_{stock}'
                )
                for stock in stocks[i:i+2]
            ]
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='portfolio_add_stock')])
        
        await query.edit_message_text(
            '🌍 Select Global Stock:',
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_russian_stocks(self, query, user):
        """Show Russian stocks for portfolio."""
        keyboard = []
        stocks = list(self.bot.stock_service.RUSSIAN_STOCKS.keys())
        
        for i in range(0, len(stocks), 2):
            row = [
                InlineKeyboardButton(
                    f"{stock} - {self.bot.stock_service.RUSSIAN_STOCKS[stock][:20]}",
                    callback_data=f'portfolio_select_stock_russian_{stock}'
                )
                for stock in stocks[i:i+2]
            ]
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='portfolio_add_stock')])
        
        await query.edit_message_text(
            '🇷🇺 Select Russian Stock:',
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_asset_selected(self, query, user, asset_type: str, asset_symbol: str):
        """Handle asset selection - ask for quantity."""
        # Store in context
        context_key = f'portfolio_add_{user.telegram_id}'
        self.bot.temp_storage[context_key] = {
            'asset_type': asset_type,
            'asset_symbol': asset_symbol
        }
        
        # Get asset name
        asset_name = asset_symbol
        if asset_type == 'stock':
            if asset_symbol in self.bot.stock_service.GLOBAL_STOCKS:
                asset_name = self.bot.stock_service.GLOBAL_STOCKS[asset_symbol]
            elif asset_symbol in self.bot.stock_service.RUSSIAN_STOCKS:
                asset_name = self.bot.stock_service.RUSSIAN_STOCKS[asset_symbol]
        
        # Show quantity selection
        keyboard = [
            [
                InlineKeyboardButton('1', callback_data=f'portfolio_qty_1'),
                InlineKeyboardButton('5', callback_data=f'portfolio_qty_5'),
                InlineKeyboardButton('10', callback_data=f'portfolio_qty_10')
            ],
            [
                InlineKeyboardButton('50', callback_data=f'portfolio_qty_50'),
                InlineKeyboardButton('100', callback_data=f'portfolio_qty_100'),
                InlineKeyboardButton('1000', callback_data=f'portfolio_qty_1000')
            ],
            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='portfolio_add')]
        ]
        
        message = get_text(user.lang, 'portfolio_enter_quantity', asset=asset_name)
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_quantity_selected(self, query, user, quantity: float):
        """Handle quantity selection and add to portfolio."""
        context_key = f'portfolio_add_{user.telegram_id}'
        
        if context_key not in self.bot.temp_storage:
            await query.answer('⚠️ Session expired. Please start again.')
            await self.show_portfolio_menu(query, None)
            return
        
        data = self.bot.temp_storage[context_key]
        asset_type = data['asset_type']
        asset_symbol = data['asset_symbol']
        
        # Add to portfolio
        result = self.bot.portfolio_service.add_asset(
            user_id=user.telegram_id,
            asset_type=asset_type,
            asset_symbol=asset_symbol,
            quantity=quantity
        )
        
        # Clear temp storage
        del self.bot.temp_storage[context_key]
        
        if result['success']:
            message = get_text(user.lang, 'portfolio_added', 
                             quantity=quantity, 
                             asset=result['item']['asset_name'])
            await query.answer(message[:200])
        else:
            message = get_text(user.lang, 'portfolio_error', error=result.get('error', 'Unknown'))
            await query.answer(message[:200])
        
        # Show portfolio menu
        await self.show_portfolio_menu(query, None)
    
    async def show_portfolio_items(self, query, user):
        """Show all portfolio items."""
        portfolio = self.bot.portfolio_service.get_portfolio(user.telegram_id)
        
        if not portfolio:
            await query.edit_message_text(
                get_text(user.lang, 'portfolio_empty'),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(get_text(user.lang, 'portfolio_add'), callback_data='portfolio_add')],
                    [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='portfolio_menu')]
                ]),
                parse_mode='Markdown'
            )
            return
        
        # Build keyboard with items
        keyboard = []
        for item in portfolio[:10]:  # Show first 10
            name = item['asset_name'][:30]
            value = item.get('current_value_usd', 0) or 0
            keyboard.append([
                InlineKeyboardButton(
                    f"{name} - ${value:.2f}",
                    callback_data=f"portfolio_item_{item['id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='portfolio_menu')])
        
        message = f"💼 *{get_text(user.lang, 'portfolio_view')}*\n\n"
        message += f"📊 Total: {len(portfolio)} items"
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_item_details(self, query, user, item_id: int):
        """Show details of a portfolio item."""
        portfolio = self.bot.portfolio_service.get_portfolio(user.telegram_id)
        item = next((i for i in portfolio if i['id'] == item_id), None)
        
        if not item:
            await query.answer('❌ Item not found')
            await self.show_portfolio_items(query, user)
            return
        
        # Build message
        price = item.get('current_price_usd', 0) or 0
        value = item.get('current_value_usd', 0) or 0
        
        message = get_text(user.lang, 'portfolio_item_details',
                          name=item['asset_name'],
                          quantity=item['quantity'],
                          price=price,
                          value=value)
        
        # Add profit/loss if available
        if item.get('profit_loss_usd'):
            pl_emoji = '📈' if item['profit_loss_usd'] > 0 else '📉'
            message += f"\n{pl_emoji} P/L: ${item['profit_loss_usd']:.2f} ({item['profit_loss_pct']:.2f}%)"
        
        keyboard = [
            [
                InlineKeyboardButton(get_text(user.lang, 'portfolio_delete'), 
                                   callback_data=f'portfolio_delete_{item_id}')
            ],
            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='portfolio_view')]
        ]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_delete_item(self, query, user, item_id: int):
        """Handle portfolio item deletion."""
        # Show confirmation
        keyboard = [
            [
                InlineKeyboardButton('✅ Yes', callback_data=f'portfolio_delete_confirm_{item_id}'),
                InlineKeyboardButton('❌ No', callback_data=f'portfolio_item_{item_id}')
            ]
        ]
        
        await query.edit_message_text(
            get_text(user.lang, 'portfolio_confirm_delete', asset='this item'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_delete_confirm(self, query, user, item_id: int):
        """Confirm deletion of portfolio item."""
        result = self.bot.portfolio_service.delete_asset(user.telegram_id, item_id)
        
        if result['success']:
            await query.answer(get_text(user.lang, 'portfolio_deleted'))
        else:
            await query.answer(get_text(user.lang, 'portfolio_error', error=result.get('error', 'Unknown')))
        
        await self.show_portfolio_items(query, user)
    
    async def show_portfolio_summary(self, query, user):
        """Show detailed portfolio summary."""
        summary = self.bot.portfolio_service.get_portfolio_summary(user.telegram_id)
        
        if summary['total_items'] == 0:
            await query.edit_message_text(
                get_text(user.lang, 'portfolio_empty'),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='portfolio_menu')]
                ]),
                parse_mode='Markdown'
            )
            return
        
        # Build detailed summary
        message = f"📊 *{get_text(user.lang, 'portfolio_summary')}*\n\n"
        message += f"💰 {get_text(user.lang, 'portfolio_total_value')}:\n"
        message += f"  • ${summary['total_value_usd']:.2f} USD\n"
        message += f"  • ₽{summary['total_value_rub']:.2f} RUB\n\n"
        
        if summary.get('total_profit_loss_usd'):
            pl_emoji = '📈' if summary['total_profit_loss_usd'] > 0 else '📉'
            message += f"{pl_emoji} {get_text(user.lang, 'portfolio_profit_loss')}:\n"
            message += f"  • ${summary['total_profit_loss_usd']:.2f}\n"
            message += f"  • {summary['total_profit_loss_pct']:.2f}%\n\n"
        
        message += f"📊 {get_text(user.lang, 'portfolio_distribution')}:\n"
        for asset_type, data in summary['by_type'].items():
            emoji = {'crypto': '💰', 'stock': '📈', 'fiat': '💵', 'cs2': '🎮'}.get(asset_type, '📦')
            message += f"{emoji} {asset_type.title()}: {data['count']} ({data['percentage']:.1f}%)\n"
        
        keyboard = [
            [InlineKeyboardButton('📊 Show Chart', callback_data='portfolio_chart')],
            [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='portfolio_menu')]
        ]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_portfolio_chart(self, query, user):
        """Show portfolio distribution pie chart."""
        await query.answer()
        await query.edit_message_text('📊 Generating chart...')
        
        try:
            summary = self.bot.portfolio_service.get_portfolio_summary(user.telegram_id)
            
            if summary['total_items'] == 0:
                await query.edit_message_text(
                    get_text(user.lang, 'portfolio_empty'),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='portfolio_menu')]
                    ]),
                    parse_mode='Markdown'
                )
                return
            
            # Get user theme preference
            theme = getattr(user, 'chart_theme', 'light')
            
            # Generate chart
            chart_bytes = self.bot.chart_generator.generate_portfolio_pie_chart(summary, theme)
            
            if not chart_bytes:
                await query.edit_message_text(
                    '❌ Error generating chart',
                    parse_mode='Markdown'
                )
                return
            
            # Send chart
            caption = f"📊 {get_text(user.lang, 'portfolio_distribution')}\n"
            caption += f"💰 Total: ${summary['total_value_usd']:.2f}\n"
            caption += f"💵 RUB: ₽{summary['total_value_rub']:.2f}"
            
            await query.message.reply_photo(
                photo=chart_bytes,
                caption=caption,
                parse_mode='Markdown'
            )
            
            # Return to summary
            await self.show_portfolio_summary(query, user)
            
        except Exception as e:
            logger.error(f"Error showing portfolio chart: {e}")
            await query.edit_message_text(
                "❌ Error generating chart",
                parse_mode='Markdown'
            )
    
    async def show_rebalance_menu(self, query, user):
        """Show rebalancing options menu."""
        await query.answer()
        
        keyboard = [
            [InlineKeyboardButton(
                "📋 Preset Strategies",
                callback_data='rebalance_presets'
            )],
            [InlineKeyboardButton(
                "🎯 Custom Allocation",
                callback_data='rebalance_custom'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'back'),
                callback_data='portfolio_menu'
            )]
        ]
        
        message = (
            "🔄 **Portfolio Rebalancing**\n\n"
            "Optimize your portfolio allocation:\n\n"
            "📋 **Preset Strategies:**\n"
            "• Conservative (40% BTC, 30% ETH, 30% USDT)\n"
            "• Balanced (50% BTC, 30% ETH, 20% others)\n"
            "• Aggressive (diversified altcoins)\n\n"
            "🎯 **Custom Allocation:**\n"
            "Set your own target percentages\n\n"
            "_Bot will analyze your portfolio and suggest trades_"
        )
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_preset_strategies(self, query, user):
        """Show preset allocation strategies."""
        await query.answer()
        
        presets = self.bot.rebalance_service.get_preset_allocations()
        
        keyboard = []
        for key, preset in presets.items():
            keyboard.append([InlineKeyboardButton(
                f"{preset['name']}",
                callback_data=f'rebalance_apply_{key}'
            )])
        
        keyboard.append([InlineKeyboardButton(
            get_text(user.lang, 'back'),
            callback_data='portfolio_rebalance'
        )])
        
        message = "📋 **Preset Allocation Strategies**\n\n"
        
        for key, preset in presets.items():
            message += f"**{preset['name']}**\n"
            message += f"_{preset['description']}_\n"
            message += "Allocation:\n"
            for symbol, pct in preset['allocation'].items():
                message += f"• {symbol}: {pct}%\n"
            message += "\n"
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def apply_rebalancing_strategy(self, query, user, strategy_name: str):
        """Apply rebalancing strategy and show recommendations."""
        await query.answer()
        await query.edit_message_text(
            f"🔄 Analyzing portfolio for {strategy_name} strategy...",
            parse_mode='Markdown'
        )
        
        try:
            # Get preset allocation
            presets = self.bot.rebalance_service.get_preset_allocations()
            strategy = presets.get(strategy_name)
            
            if not strategy:
                await query.edit_message_text(
                    "❌ Strategy not found",
                    parse_mode='Markdown'
                )
                return
            
            target_allocation = strategy['allocation']
            
            # Get rebalancing plan
            result = self.bot.rebalance_service.get_rebalancing_plan(
                user.telegram_id,
                target_allocation
            )
            
            if not result.get('success'):
                await query.edit_message_text(
                    f"❌ Error: {result.get('error', 'Unknown error')}",
                    parse_mode='Markdown'
                )
                return
            
            rebalancing = result['rebalancing']
            
            if not rebalancing['needs_rebalancing']:
                message = (
                    f"✅ **Portfolio Already Balanced!**\n\n"
                    f"Strategy: {strategy['name']}\n"
                    f"Total Value: ${rebalancing['portfolio_value']:,.2f}\n\n"
                    f"Your portfolio is already within target allocation.\n"
                    f"Total deviation: {rebalancing['total_deviation']}%"
                )
            else:
                message = f"🔄 **Rebalancing Plan: {strategy['name']}**\n\n"
                message += f"💰 Portfolio Value: ${rebalancing['portfolio_value']:,.2f}\n"
                message += f"📊 Total Deviation: {rebalancing['total_deviation']}%\n\n"
                message += "**Recommended Actions:**\n\n"
                
                for rec in rebalancing['recommendations']:
                    message += f"{rec['emoji']} **{rec['symbol']}**: {rec['action']}\n"
                    message += f"Current: {rec['current_weight']}% → Target: {rec['target_weight']}%\n"
                    message += f"Adjust: ${rec['value_adjustment']:,.2f}\n\n"
                
                # Calculate costs
                costs = self.bot.rebalance_service.calculate_rebalancing_cost(
                    rebalancing['recommendations']
                )
                
                message += f"**Estimated Costs:**\n"
                message += f"Trade Value: ${costs['total_trade_value']:,.2f}\n"
                message += f"Fees (~{costs['fee_percentage']}%): ${costs['estimated_fees']:,.2f}\n\n"
                message += "_⚠️ This is a recommendation only. Execute trades manually._"
            
            keyboard = [
                [InlineKeyboardButton(
                    "🔄 Try Another Strategy",
                    callback_data='rebalance_presets'
                )],
                [InlineKeyboardButton(
                    get_text(user.lang, 'back'),
                    callback_data='portfolio_menu'
                )]
            ]
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            logger.info(f"Rebalancing plan generated for user {user.telegram_id} with strategy {strategy_name}")
            
        except Exception as e:
            logger.error(f"Error applying rebalancing strategy: {e}")
            await query.edit_message_text(
                "❌ Error generating rebalancing plan",
                parse_mode='Markdown'
            )
