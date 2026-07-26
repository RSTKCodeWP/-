"""Analytics handler for CoinFlow bot."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..localization import get_text
from ..utils.logger import setup_logger

logger = setup_logger('analytics_handler')


class AnalyticsHandler:
    """Handler for advanced analytics features."""
    
    def __init__(self, bot):
        """Initialize analytics handler."""
        self.bot = bot
    
    async def show_analytics_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show analytics menu."""
        user_id = update.effective_user.id
        user = self.bot.db.get_user(user_id)
        
        keyboard = [
            [InlineKeyboardButton(
                "📊 Asset Analytics",
                callback_data='analytics_asset'
            )],
            [InlineKeyboardButton(
                "🔗 Correlation Analysis",
                callback_data='analytics_correlation'
            )],
            [InlineKeyboardButton(
                "💼 Portfolio Analytics",
                callback_data='analytics_portfolio'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'back'),
                callback_data='back_main'
            )]
        ]
        
        message = (
            "📊 **Advanced Analytics**\n\n"
            "Choose analysis type:\n\n"
            "📊 **Asset Analytics**\n"
            "• Volatility analysis\n"
            "• Sharpe ratio\n"
            "• Maximum drawdown\n"
            "• Risk metrics (VaR, CVaR)\n\n"
            "🔗 **Correlation Analysis**\n"
            "• Compare two assets\n"
            "• Correlation coefficient\n"
            "• Relationship strength\n\n"
            "💼 **Portfolio Analytics**\n"
            "• Portfolio risk metrics\n"
            "• Diversification analysis\n"
            "• Performance metrics"
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
    
    async def show_asset_selection(self, query, user, analysis_type: str):
        """Show asset selection for analytics."""
        await query.answer()
        
        # Popular assets for analytics
        keyboard = [
            [InlineKeyboardButton("BTC", callback_data=f'{analysis_type}_BTC'),
             InlineKeyboardButton("ETH", callback_data=f'{analysis_type}_ETH')],
            [InlineKeyboardButton("AAPL", callback_data=f'{analysis_type}_AAPL'),
             InlineKeyboardButton("TSLA", callback_data=f'{analysis_type}_TSLA')],
            [InlineKeyboardButton("MSFT", callback_data=f'{analysis_type}_MSFT'),
             InlineKeyboardButton("GOOGL", callback_data=f'{analysis_type}_GOOGL')],
            [InlineKeyboardButton(
                get_text(user.lang, 'back'),
                callback_data='analytics_menu'
            )]
        ]
        
        await query.edit_message_text(
            "📊 **Select Asset**\n\nChoose asset for analysis:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def perform_asset_analytics(self, query, user, symbol: str):
        """Perform comprehensive analytics on asset."""
        await query.answer()
        await query.edit_message_text(
            f"🔍 Analyzing {symbol}...",
            parse_mode='Markdown'
        )
        
        try:
            # Determine asset type
            asset_type = 'stock' if symbol in ['AAPL', 'TSLA', 'MSFT', 'GOOGL', 'NVDA'] else 'crypto'
            
            # Get analytics
            result = await self.bot.analytics_service.get_asset_analytics(
                symbol, 
                asset_type=asset_type,
                period_days=30
            )
            
            if not result.get('success'):
                await query.edit_message_text(
                    f"❌ Error: {result.get('error', 'Unknown error')}",
                    parse_mode='Markdown'
                )
                return
            
            # Format response
            volatility = result.get('volatility', {})
            sharpe = result.get('sharpe_ratio', {})
            drawdown = result.get('max_drawdown', {})
            
            message = f"📊 **{symbol} Analytics** (30 days)\n\n"
            message += f"💰 Current Price: ${result.get('current_price', 0):,.2f}\n\n"
            
            if volatility.get('success'):
                message += "**📈 Volatility:**\n"
                message += f"• Daily: {volatility.get('volatility', 0)}%\n"
                message += f"• Annualized: {volatility.get('annualized_volatility', 0)}%\n"
                if volatility.get('rolling_volatility'):
                    message += f"• 30-day Rolling: {volatility.get('rolling_volatility')}%\n"
                message += "\n"
            
            if sharpe.get('success'):
                message += "**📊 Sharpe Ratio:**\n"
                message += f"• Ratio: {sharpe.get('sharpe_ratio', 0)}\n"
                message += f"• Annual Return: {sharpe.get('annual_return', 0)}%\n"
                message += f"• Annual Volatility: {sharpe.get('annual_volatility', 0)}%\n\n"
            
            if drawdown.get('success'):
                message += "**📉 Drawdown:**\n"
                message += f"• Maximum: {drawdown.get('max_drawdown', 0)}%\n"
                message += f"• Current: {drawdown.get('current_drawdown', 0)}%\n\n"
            
            message += "_Risk metrics help assess investment risk and performance_"
            
            keyboard = [
                [InlineKeyboardButton(
                    "🎯 Trading Signals",
                    callback_data=f'signals_{symbol}'
                )],
                [InlineKeyboardButton(
                    get_text(user.lang, 'back'),
                    callback_data='analytics_menu'
                )]
            ]
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            logger.info(f"Analytics performed for {symbol} by user {user.telegram_id}")
            
        except Exception as e:
            logger.error(f"Error in asset analytics: {e}")
            await query.edit_message_text(
                "❌ Error performing analysis",
                parse_mode='Markdown'
            )
    
    async def show_correlation_selection(self, query, user):
        """Show correlation analysis setup."""
        await query.answer()
        
        # Store state for next step
        self.bot.temp_storage[user.telegram_id] = {
            'action': 'correlation_asset1',
            'timestamp': query.message.date
        }
        
        keyboard = [
            [InlineKeyboardButton("BTC", callback_data='corr1_BTC'),
             InlineKeyboardButton("ETH", callback_data='corr1_ETH')],
            [InlineKeyboardButton("AAPL", callback_data='corr1_AAPL'),
             InlineKeyboardButton("TSLA", callback_data='corr1_TSLA')],
            [InlineKeyboardButton(
                get_text(user.lang, 'back'),
                callback_data='analytics_menu'
            )]
        ]
        
        await query.edit_message_text(
            "🔗 **Correlation Analysis**\n\n"
            "Step 1/2: Select first asset",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_correlation_asset1(self, query, user, symbol: str):
        """Handle first asset selection for correlation."""
        await query.answer()
        
        # Store first asset
        self.bot.temp_storage[user.telegram_id] = {
            'action': 'correlation_asset2',
            'asset1': symbol,
            'timestamp': query.message.date
        }
        
        keyboard = [
            [InlineKeyboardButton("BTC", callback_data='corr2_BTC'),
             InlineKeyboardButton("ETH", callback_data='corr2_ETH')],
            [InlineKeyboardButton("AAPL", callback_data='corr2_AAPL'),
             InlineKeyboardButton("TSLA", callback_data='corr2_TSLA')],
            [InlineKeyboardButton(
                get_text(user.lang, 'back'),
                callback_data='analytics_menu'
            )]
        ]
        
        await query.edit_message_text(
            f"🔗 **Correlation Analysis**\n\n"
            f"Selected: {symbol}\n"
            f"Step 2/2: Select second asset",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def perform_correlation_analysis(self, query, user, symbol2: str):
        """Perform correlation analysis between two assets."""
        await query.answer()
        
        temp_data = self.bot.temp_storage.get(user.telegram_id, {})
        symbol1 = temp_data.get('asset1')
        
        if not symbol1:
            await query.edit_message_text(
                "❌ Error: First asset not selected",
                parse_mode='Markdown'
            )
            return
        
        await query.edit_message_text(
            f"🔍 Analyzing correlation between {symbol1} and {symbol2}...",
            parse_mode='Markdown'
        )
        
        try:
            result = await self.bot.analytics_service.compare_assets_correlation(
                symbol1, symbol2, period_days=30
            )
            
            if not result.get('success'):
                await query.edit_message_text(
                    f"❌ Error: {result.get('error', 'Unknown error')}",
                    parse_mode='Markdown'
                )
                return
            
            correlation = result.get('correlation', 0)
            strength = result.get('strength', 'Unknown')
            direction = result.get('direction', 'neutral')
            
            # Emoji based on correlation
            if abs(correlation) >= 0.7:
                emoji = "🔴" if correlation > 0 else "🔵"
            elif abs(correlation) >= 0.4:
                emoji = "🟡"
            else:
                emoji = "⚪"
            
            message = (
                f"🔗 **Correlation Analysis**\n\n"
                f"**Assets:** {symbol1} vs {symbol2}\n"
                f"**Period:** 30 days\n\n"
                f"{emoji} **Correlation:** {correlation}\n"
                f"**Strength:** {strength}\n"
                f"**Direction:** {direction.capitalize()}\n\n"
                f"**Interpretation:**\n{result.get('interpretation', 'N/A')}\n\n"
                f"_Correlation ranges from -1 (opposite) to +1 (same direction)_"
            )
            
            keyboard = [
                [InlineKeyboardButton(
                    "🔄 New Analysis",
                    callback_data='analytics_correlation'
                )],
                [InlineKeyboardButton(
                    get_text(user.lang, 'back'),
                    callback_data='analytics_menu'
                )]
            ]
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            # Clear temp storage
            if user.telegram_id in self.bot.temp_storage:
                del self.bot.temp_storage[user.telegram_id]
            
            logger.info(f"Correlation analysis: {symbol1} vs {symbol2} for user {user.telegram_id}")
            
        except Exception as e:
            logger.error(f"Error in correlation analysis: {e}")
            await query.edit_message_text(
                "❌ Error performing correlation analysis",
                parse_mode='Markdown'
            )
