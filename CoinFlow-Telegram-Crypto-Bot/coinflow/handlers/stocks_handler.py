"""Handler for stock market features."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import matplotlib.pyplot as plt
import io
from datetime import datetime
from ..localization import get_text
from ..utils.logger import setup_logger

logger = setup_logger('stocks_handler')


class StocksHandler:
    """Handler for stock market queries."""
    
    def __init__(self, bot):
        self.bot = bot
        self.stock_service = bot.stock_service
    
    async def show_stocks_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main stocks menu (now unified without separate CBR section)."""
        user_id = update.effective_user.id
        user = self.bot.db.get_or_create_user(user_id)
        
        keyboard = [
            [InlineKeyboardButton(
                get_text(user.lang, 'stocks_global'), 
                callback_data='stocks_global'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'stocks_russian'), 
                callback_data='stocks_russian'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'back'), 
                callback_data='back_main'
            )]
        ]
        
        message_text = (
            f"📊 **{get_text(user.lang, 'stocks_menu')}**\n\n"
            "Выберите категорию акций для просмотра:\n"
            "• **Global Stocks** - Apple, Microsoft, Tesla, etc.\n"
            "• **Russian Stocks** - Сбербанк, Газпром, Лукойл, etc.\n\n"
            "_ЦБ РФ курсы доступны как альтернативный источник для фиатных валют_"
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    async def show_global_stocks(self, query, user):
        """Show list of global stocks."""
        stocks = list(self.stock_service.GLOBAL_STOCKS.keys())
        
        keyboard = []
        row = []
        for i, ticker in enumerate(stocks[:24]):  # Show top 24
            row.append(InlineKeyboardButton(ticker, callback_data=f'stock_global_{ticker}'))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='stocks_menu')])
        
        await query.edit_message_text(
            get_text(user.lang, 'stocks_global_select'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_russian_stocks(self, query, user):
        """Show list of Russian stocks (MOEX)."""
        keyboard = []
        
        # Add Russian stocks
        stocks = list(self.stock_service.RUSSIAN_STOCKS.keys())[:18]
        row = []
        for ticker in stocks:
            row.append(InlineKeyboardButton(ticker, callback_data=f'stock_russian_{ticker}'))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='stocks_menu')])
        
        await query.edit_message_text(
            get_text(user.lang, 'stocks_russian_select'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_cbr_rates(self, query, user):
        """Show CBR exchange rates (now integrated, not separate menu)."""
        keyboard = []
        
        # Add CBR currencies
        cbr_currencies = list(self.stock_service.CBR_CURRENCIES.keys())
        row = []
        for currency in cbr_currencies:
            row.append(InlineKeyboardButton(currency, callback_data=f'cbr_{currency}'))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton(get_text(user.lang, 'back'), callback_data='stocks_menu')])
        
        message_text = (
            "💱 **Официальные курсы ЦБ РФ**\n\n"
            "Выберите валюту для просмотра официального курса:\n\n"
            "_Эти курсы используются как альтернативный источник данных\n"
            "для конвертации с участием рубля (RUB)_"
        )
        
        await query.edit_message_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_global_stock_info(self, query, user, ticker: str):
        """Show detailed info for global stock."""
        await query.edit_message_text(
            f"📊 {get_text(user.lang, 'loading')}...",
            parse_mode='Markdown'
        )
        
        # Get stock data
        stock_data = self.stock_service.get_global_stock(ticker)
        
        if not stock_data:
            await query.edit_message_text(
                get_text(user.lang, 'stock_error', ticker=ticker),
                parse_mode='Markdown'
            )
            return
        
        # Format message
        change_emoji = '📈' if stock_data['change_pct'] >= 0 else '📉'
        sign = '+' if stock_data['change_pct'] >= 0 else ''
        
        message = (
            f"📊 **{stock_data['name']}** ({ticker})\n\n"
            f"💰 **Price:** ${stock_data['price']:.2f}\n"
            f"{change_emoji} **24h Change:** {sign}{stock_data['change_pct']:.2f}% "
            f"({sign}${stock_data['change_usd']:.2f})\n\n"
            f"📊 **Market Cap:** ${stock_data['market_cap']:,.0f}\n"
            f"📦 **Volume:** {stock_data['volume']:,}\n\n"
            f"⏰ Updated: {datetime.fromisoformat(stock_data['timestamp']).strftime('%H:%M')}"
        )
        
        # Create keyboard with chart option
        keyboard = [
            [InlineKeyboardButton(
                get_text(user.lang, 'show_chart'), 
                callback_data=f'stock_chart_global_{ticker}'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'back'), 
                callback_data='stocks_global'
            )]
        ]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_russian_stock_info(self, query, user, ticker: str):
        """Show detailed info for Russian stock."""
        await query.edit_message_text(
            f"📊 {get_text(user.lang, 'loading')}...",
            parse_mode='Markdown'
        )
        
        # Get stock data
        stock_data = self.stock_service.get_russian_stock(ticker)
        
        if not stock_data:
            await query.edit_message_text(
                get_text(user.lang, 'stock_error', ticker=ticker),
                parse_mode='Markdown'
            )
            return
        
        # Format message
        change_emoji = '📈' if stock_data['change_pct'] >= 0 else '📉'
        sign = '+' if stock_data['change_pct'] >= 0 else ''
        
        message = (
            f"📊 **{stock_data['name']}** ({ticker})\n\n"
            f"💰 **Цена:** {stock_data['price']:.2f} ₽\n"
            f"{change_emoji} **Изменение за день:** {sign}{stock_data['change_pct']:.2f}% "
            f"({sign}{stock_data['change_rub']:.2f} ₽)\n\n"
            f"📦 **Объём торгов:** {stock_data['volume']:,}\n\n"
            f"⏰ Обновлено: {datetime.fromisoformat(stock_data['timestamp']).strftime('%H:%M')}"
        )
        
        # Create keyboard
        keyboard = [
            [InlineKeyboardButton(
                get_text(user.lang, 'show_chart'),
                callback_data=f'stock_chart_russian_{ticker}'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'back'), 
                callback_data='stocks_russian'
            )]
        ]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_cbr_rate(self, query, user, currency: str):
        """Show CBR exchange rate."""
        await query.edit_message_text(
            f"💱 {get_text(user.lang, 'loading')}...",
            parse_mode='Markdown'
        )
        
        # Get CBR rate
        rate_data = self.stock_service.get_cbr_rate(currency)
        
        if not rate_data:
            await query.edit_message_text(
                get_text(user.lang, 'cbr_error', currency=currency),
                parse_mode='Markdown'
            )
            return
        
        # Format message
        change_emoji = '📈' if rate_data['change_pct'] >= 0 else '📉'
        sign = '+' if rate_data['change_pct'] >= 0 else ''
        
        nominal_text = ''
        if rate_data['nominal'] > 1:
            nominal_text = f" (за {rate_data['nominal']} {currency})"
        
        message = (
            f"💱 **{rate_data['name']}**\n\n"
            f"🏦 **Курс ЦБ РФ{nominal_text}:** {rate_data['rate']:.4f} ₽\n"
            f"{change_emoji} **Изменение:** {sign}{rate_data['change_pct']:.2f}% "
            f"({sign}{rate_data['change']:.4f} ₽)\n\n"
            f"📅 Дата: {rate_data['date'][:10]}\n"
            f"⏰ Обновлено: {datetime.fromisoformat(rate_data['timestamp']).strftime('%H:%M')}\n\n"
            f"ℹ️ _Официальный курс Центрального Банка РФ_"
        )
        
        # Create keyboard
        keyboard = [
            [InlineKeyboardButton(
                get_text(user.lang, 'show_chart'),
                callback_data=f'cbr_chart_{currency}'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'back'), 
                callback_data='cbr_rates'
            )]
        ]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def show_stock_chart(self, query, user, ticker: str, chart_type: str = 'global', period: int = 30):
        """Generate and show stock chart."""
        await query.edit_message_text(
            f"📊 {get_text(user.lang, 'loading')}...",
            parse_mode='Markdown'
        )
        
        try:
            # Get user theme preference
            theme = getattr(user, 'chart_theme', 'light')
            
            # Add .ME suffix for Russian stocks
            if chart_type == 'russian':
                ticker_full = f"{ticker}.ME"
            else:
                ticker_full = ticker
            
            # Generate chart using ChartGenerator
            chart_bytes, stats = self.bot.chart_generator.generate_stock_chart(ticker_full, period, theme)
            
            if not chart_bytes:
                await query.edit_message_text(
                    get_text(user.lang, 'no_data_available'),
                    parse_mode='Markdown'
                )
                return
            
            # Create caption
            caption = (
                f"📊 **{ticker}** ({period} days)\n\n"
                f"💰 Current: **${stats['current']:.2f}**\n"
                f"📈 High: ${stats['high']:.2f}\n"
                f"📉 Low: ${stats['low']:.2f}\n"
                f"📊 Average: ${stats['avg']:.2f}"
            )
            
            # Send chart
            await query.message.reply_photo(
                photo=chart_bytes,
                caption=caption,
                parse_mode='Markdown'
            )
            
            # Update original message
            back_callback = 'stocks_global' if chart_type == 'global' else 'stocks_russian'
            keyboard = [
                [InlineKeyboardButton(
                    get_text(user.lang, 'back'), 
                    callback_data=back_callback
                )]
            ]
            await query.edit_message_text(
                get_text(user.lang, 'chart_sent'),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error generating stock chart: {e}")
            await query.edit_message_text(
                get_text(user.lang, 'service_unavailable'),
                parse_mode='Markdown'
            )
    
    async def show_cbr_chart(self, query, user, currency: str, period: int = 30):
        """Generate and show CBR rate chart."""
        await query.edit_message_text(
            f"📊 {get_text(user.lang, 'loading')}...",
            parse_mode='Markdown'
        )
        
        try:
            # Get user theme preference
            theme = getattr(user, 'chart_theme', 'light')
            
            # Generate chart using ChartGenerator
            chart_bytes, stats = await self.bot.chart_generator.generate_cbr_chart(currency, period, theme)
            
            if not chart_bytes:
                await query.edit_message_text(
                    get_text(user.lang, 'no_data_available'),
                    parse_mode='Markdown'
                )
                return
            
            # Create caption
            caption = (
                f"💵 **CBR Rate: {currency}/RUB** ({period} days)\n\n"
                f"💰 Current: **{stats['current']:.4f} ₽**\n"
                f"📈 High: {stats['high']:.4f} ₽\n"
                f"📉 Low: {stats['low']:.4f} ₽\n"
                f"📊 Average: {stats['avg']:.4f} ₽"
            )
            
            # Send chart
            await query.message.reply_photo(
                photo=chart_bytes,
                caption=caption,
                parse_mode='Markdown'
            )
            
            # Update original message
            keyboard = [
                [InlineKeyboardButton(
                    get_text(user.lang, 'back'), 
                    callback_data='cbr_rates'
                )]
            ]
            await query.edit_message_text(
                get_text(user.lang, 'chart_sent'),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error generating CBR chart: {e}")
            await query.edit_message_text(
                get_text(user.lang, 'service_unavailable'),
                parse_mode='Markdown'
            )
