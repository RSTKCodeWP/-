"""Trading signals handler for CoinFlow bot."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..localization import get_text
from ..utils.logger import setup_logger

logger = setup_logger('trading_handler')


class TradingHandler:
    """Handler for trading signals."""
    
    def __init__(self, bot):
        """Initialize trading handler."""
        self.bot = bot
    
    async def show_signals_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show trading signals menu."""
        user_id = update.effective_user.id
        user = self.bot.db.get_user(user_id)
        
        keyboard = [
            [InlineKeyboardButton("BTC", callback_data='signal_BTC'),
             InlineKeyboardButton("ETH", callback_data='signal_ETH')],
            [InlineKeyboardButton("AAPL", callback_data='signal_AAPL'),
             InlineKeyboardButton("TSLA", callback_data='signal_TSLA')],
            [InlineKeyboardButton("MSFT", callback_data='signal_MSFT'),
             InlineKeyboardButton("GOOGL", callback_data='signal_GOOGL')],
            [InlineKeyboardButton(
                get_text(user.lang, 'back'),
                callback_data='back_main'
            )]
        ]
        
        message = (
            "🎯 **Trading Signals**\n\n"
            "Get technical analysis and trading signals:\n\n"
            "**Indicators:**\n"
            "• RSI (Relative Strength Index)\n"
            "• MACD (Moving Average Convergence Divergence)\n"
            "• Moving Averages (SMA 20/50)\n"
            "• Bollinger Bands\n\n"
            "**Signals:** BUY / SELL / NEUTRAL\n\n"
            "Select asset to analyze:"
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
    
    async def show_trading_signals(self, query, user, symbol: str):
        """Show comprehensive trading signals for asset."""
        await query.answer()
        await query.edit_message_text(
            f"🎯 Analyzing {symbol} signals...",
            parse_mode='Markdown'
        )
        
        try:
            # Get trading signals
            result = await self.bot.trading_service.get_trading_signals(symbol, period_days=60)
            
            if not result.get('success'):
                await query.edit_message_text(
                    f"❌ Error: {result.get('error', 'Unknown error')}",
                    parse_mode='Markdown'
                )
                return
            
            # Format signals
            overall_signal = result.get('overall_signal', 'NEUTRAL')
            confidence = result.get('confidence', 0)
            current_price = result.get('current_price', 0)
            
            # Signal emoji
            if overall_signal == 'BUY':
                signal_emoji = "🟢"
            elif overall_signal == 'SELL':
                signal_emoji = "🔴"
            else:
                signal_emoji = "🟡"
            
            message = f"🎯 **{symbol} Trading Signals**\n\n"
            message += f"💰 Price: ${current_price:,.2f}\n"
            message += f"{signal_emoji} **Overall: {overall_signal}**\n"
            message += f"📊 Confidence: {confidence}%\n\n"
            
            # RSI
            rsi = result.get('rsi')
            if rsi:
                rsi_emoji = "🟢" if rsi['signal'] == 'BUY' else "🔴" if rsi['signal'] == 'SELL' else "🟡"
                message += f"**RSI (14):** {rsi_emoji} {rsi['value']}\n"
                message += f"_{rsi['interpretation']}_\n\n"
            
            # MACD
            macd = result.get('macd')
            if macd:
                macd_emoji = "🟢" if macd['signal'] == 'BUY' else "🔴" if macd['signal'] == 'SELL' else "🟡"
                message += f"**MACD:** {macd_emoji}\n"
                message += f"Line: {macd['macd_line']}\n"
                message += f"Signal: {macd['signal_line']}\n"
                message += f"_{macd['interpretation']}_\n\n"
            
            # Moving Averages
            ma = result.get('moving_averages')
            if ma:
                ma_emoji = "🟢" if ma['signal'] == 'BUY' else "🔴" if ma['signal'] == 'SELL' else "🟡"
                message += f"**Moving Averages:** {ma_emoji}\n"
                message += f"SMA 20: ${ma['sma_short']:,.2f}\n"
                message += f"SMA 50: ${ma['sma_long']:,.2f}\n"
                message += f"_{ma['interpretation']}_\n\n"
            
            # Bollinger Bands
            bb = result.get('bollinger_bands')
            if bb:
                bb_emoji = "🟢" if bb['signal'] == 'BUY' else "🔴" if bb['signal'] == 'SELL' else "🟡"
                message += f"**Bollinger Bands:** {bb_emoji}\n"
                message += f"Upper: ${bb['upper_band']:,.2f}\n"
                message += f"Lower: ${bb['lower_band']:,.2f}\n"
                message += f"Position: {bb['position']}%\n"
                message += f"_{bb['interpretation']}_\n\n"
            
            # Summary
            message += f"**Summary:**\n"
            message += f"🟢 Bullish: {result.get('bullish_indicators', 0)}\n"
            message += f"🔴 Bearish: {result.get('bearish_indicators', 0)}\n"
            message += f"🟡 Neutral: {result.get('neutral_indicators', 0)}\n\n"
            
            message += "_⚠️ Signals are for educational purposes only. Not financial advice._"
            
            keyboard = [
                [InlineKeyboardButton(
                    "📊 Analytics",
                    callback_data=f'analyze_{symbol}'
                )],
                [InlineKeyboardButton(
                    "🔄 Refresh",
                    callback_data=f'signal_{symbol}'
                )],
                [InlineKeyboardButton(
                    get_text(user.lang, 'back'),
                    callback_data='signals_menu'
                )]
            ]
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            logger.info(f"Trading signals shown for {symbol} to user {user.telegram_id}")
            
        except Exception as e:
            logger.error(f"Error showing trading signals: {e}")
            await query.edit_message_text(
                "❌ Error getting trading signals",
                parse_mode='Markdown'
            )
    
    async def show_indicator_details(self, query, user, symbol: str, indicator: str):
        """Show detailed info about specific indicator."""
        await query.answer()
        
        # Indicator explanations
        explanations = {
            'rsi': (
                "**RSI (Relative Strength Index)**\n\n"
                "Measures momentum on scale 0-100:\n"
                "• > 70: Overbought (potential SELL)\n"
                "• < 30: Oversold (potential BUY)\n"
                "• 30-70: Normal range\n\n"
                "Best for: Identifying overbought/oversold conditions"
            ),
            'macd': (
                "**MACD (Moving Average Convergence Divergence)**\n\n"
                "Shows relationship between 2 moving averages:\n"
                "• MACD above Signal: Bullish\n"
                "• MACD below Signal: Bearish\n"
                "• Crossovers: Strong signals\n\n"
                "Best for: Trend following, momentum"
            ),
            'ma': (
                "**Moving Averages (SMA)**\n\n"
                "Average price over period:\n"
                "• Short MA > Long MA: Bullish (Golden Cross)\n"
                "• Short MA < Long MA: Bearish (Death Cross)\n"
                "• Price vs MA: Support/Resistance\n\n"
                "Best for: Trend identification"
            ),
            'bb': (
                "**Bollinger Bands**\n\n"
                "Price envelope around moving average:\n"
                "• Price at Upper Band: Overbought\n"
                "• Price at Lower Band: Oversold\n"
                "• Band Width: Volatility measure\n\n"
                "Best for: Volatility, reversal points"
            )
        }
        
        message = explanations.get(indicator, "Indicator info not available")
        
        keyboard = [
            [InlineKeyboardButton(
                "🔙 Back to Signals",
                callback_data=f'signal_{symbol}'
            )]
        ]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
