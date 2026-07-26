"""Message handlers for CoinFlow bot."""

from telegram import Update
from telegram.ext import ContextTypes
from ..localization import get_text
from ..utils.logger import setup_logger

logger = setup_logger('messages')


class MessageHandlers:
    """Handlers for text messages."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle voice messages."""
        user_id = update.effective_user.id
        user = self.bot.db.get_user(user_id)
        
        # Check if voice service is available
        if not self.bot.voice_service.is_available():
            # Determine specific error
            if not self.bot.voice_service.ffmpeg_available:
                error_key = 'voice_ffmpeg_missing'
            else:
                error_key = 'voice_not_available'
            
            await update.message.reply_text(
                get_text(user.lang, error_key),
                parse_mode='Markdown'
            )
            return
        
        try:
            # Show typing action to indicate processing
            await update.message.chat.send_action('typing')
            
            # Show processing message
            processing_msg = await update.message.reply_text(
                get_text(user.lang, 'voice_processing')
            )
            
            # Get voice file
            voice = update.message.voice
            voice_file = await context.bot.get_file(voice.file_id)
            
            # Download voice data
            voice_bytes = await voice_file.download_as_bytearray()
            
            # Process voice message
            result = await self.bot.voice_service.process_voice_message(
                bytes(voice_bytes),
                language=user.lang
            )
            
            if not result.get('success'):
                # Map error codes to localized messages
                error_code = result.get('error', 'unknown')
                error_map = {
                    'ffmpeg_missing': 'voice_ffmpeg_missing',
                    'speechrecognition_missing': 'voice_speechrecognition_missing',
                    'pydub_missing': 'voice_pydub_missing',
                    'conversion_failed': 'voice_conversion_failed',
                    'speech_not_understood': 'voice_not_understood',
                    'api_error': 'voice_api_error',
                }
                
                localization_key = error_map.get(error_code, 'voice_conversion_failed')
                await processing_msg.edit_text(
                    get_text(user.lang, localization_key),
                    parse_mode='Markdown'
                )
                return
            
            # Get recognized text
            recognized_text = result.get('text', '')
            
            # Show typing action for AI processing
            await update.message.chat.send_action('typing')
            
            # Show recognized text
            await processing_msg.edit_text(
                f"{get_text(user.lang, 'voice_recognized', text=recognized_text)}\n\n{get_text(user.lang, 'ai_generating')}",
                parse_mode='Markdown'
            )
            
            # Use AI to interpret the voice command
            try:
                interpretation = await self.bot.ai_service.interpret_user_message(recognized_text, user.lang)
                
                if interpretation['type'] == 'error':
                    await processing_msg.edit_text(
                        f"🎤 **Распознано:** _{recognized_text}_\n\n"
                        f"⚠️ AI сервис недоступен. Попробуйте текстовую команду.",
                        parse_mode='Markdown'
                    )
                    return
                
                # If it's a command, execute it
                if interpretation['type'] == 'command':
                    action = interpretation['action']
                    params = interpretation['params']
                    
                    if action == 'CONVERT':
                        amount = params.get('amount', 1)
                        from_curr = params.get('from', 'USD')
                        to_curr = params.get('to', 'EUR')
                        
                        # Execute conversion with voice context
                        await self._execute_voice_convert(update, processing_msg, user, recognized_text, amount, from_curr, to_curr)
                    
                    elif action == 'FORECAST':
                        symbol = params.get('symbol', 'BTC')
                        await processing_msg.edit_text(
                            f"🎤 **Распознано:** _{recognized_text}_\n\n"
                            f"🔮 Генерирую прогноз для {symbol}...",
                            parse_mode='Markdown'
                        )
                        await self.execute_forecast_command(update, user, symbol)
                    
                    elif action == 'CHART':
                        symbol = params.get('symbol', 'BTC')
                        days = params.get('days', 30)
                        await processing_msg.edit_text(
                            f"🎤 **Распознано:** _{recognized_text}_\n\n"
                            f"📊 Генерирую график {symbol}...",
                            parse_mode='Markdown'
                        )
                        await self.execute_chart_command(update, user, symbol, days)
                    
                    else:
                        # Unknown command - send text response
                        await processing_msg.edit_text(
                            f"🎤 **Распознано:** _{recognized_text}_\n\n"
                            f"🤖 {interpretation.get('response', 'Команда выполнена')}",
                            parse_mode='Markdown'
                        )
                
                # If it's a text response (question/greeting)
                else:
                    await processing_msg.edit_text(
                        f"🎤 **Распознано:** _{recognized_text}_\n\n"
                        f"🤖 {interpretation['response']}",
                        parse_mode='Markdown'
                    )
            
            except Exception as e:
                logger.error(f"Error processing voice with AI: {e}")
                await processing_msg.edit_text(
                    f"🎤 **Распознано:** _{recognized_text}_\n\n"
                    f"❌ Ошибка обработки. Попробуйте ещё раз.",
                    parse_mode='Markdown'
                )
        
        except Exception as e:
            logger.error(f"Error handling voice message: {e}")
            await update.message.reply_text(
                f"❌ Error processing voice message: {str(e)}",
                parse_mode='Markdown'
            )
    
    async def _execute_voice_convert(self, update, processing_msg, user, recognized_text, amount, from_curr, to_curr):
        """Execute conversion from voice command."""
        try:
            amount = float(amount)
            rate = self.bot.converter.get_rate(from_curr, to_curr, user.telegram_id)
            
            if not rate or not isinstance(rate, (int, float)):
                await processing_msg.edit_text(
                    f"🎤 **Распознано:** _{recognized_text}_\n\n"
                    f"❌ Не могу получить курс {from_curr} к {to_curr}.",
                    parse_mode='Markdown'
                )
                return
            
            rate = float(rate)
            result = amount * rate
            
            # Save to database
            self.bot.db.add_conversion(user.telegram_id, from_curr, to_curr, amount, result, rate)
            
            # Send result
            await processing_msg.edit_text(
                f"🎤 **Распознано:** _{recognized_text}_\n\n"
                f"💱 **{amount:,.2f} {from_curr}** = **{result:,.2f} {to_curr}**\n\n"
                f"📊 Курс: 1 {from_curr} = {rate:.6f} {to_curr}",
                parse_mode='Markdown'
            )
            
            self.bot.metrics.log_conversion(user.telegram_id)
            logger.info(f"Voice conversion: {amount} {from_curr} -> {to_curr}")
            
        except Exception as e:
            logger.error(f"Error in voice conversion: {e}")
            await processing_msg.edit_text(
                f"🎤 **Распознано:** _{recognized_text}_\n\n"
                f"❌ Ошибка конвертации.",
                parse_mode='Markdown'
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all text messages."""
        user_id = update.effective_user.id
        
        # Check if admin is creating announcement
        user_state = self.bot.temp_storage.get(user_id, {})
        if user_state.get('state') == 'awaiting_announcement_content':
            await self.bot.admin_handler.handle_announcement_content(update, context)
        text = update.message.text
        
        user = self.bot.db.get_or_create_user(user_id)
        
        # Language selection
        if 'English' in text:
            self.bot.db.update_user(user_id, lang='en')
            user = self.bot.db.get_user(user_id)
            await update.message.reply_text(
                get_text('en', 'language_set'),
                reply_markup=self.bot.get_main_menu_keyboard('en'),
                parse_mode='Markdown'
            )
            return
        elif 'Русский' in text:
            self.bot.db.update_user(user_id, lang='ru')
            user = self.bot.db.get_user(user_id)
            await update.message.reply_text(
                get_text('ru', 'language_set'),
                reply_markup=self.bot.get_main_menu_keyboard('ru'),
                parse_mode='Markdown'
            )
            return
        
        # Main menu items
        if text == get_text(user.lang, 'quick_convert'):
            await self.bot.callback_handlers.start_conversion(update, user, context)
        elif text == get_text(user.lang, 'rate_charts'):
            await self.bot.callback_handlers.start_chart_selection(update, user, context)
        elif text == get_text(user.lang, 'rate_prediction'):
            await self.bot.callback_handlers.start_prediction_selection(update, user, context)
        elif text == get_text(user.lang, 'compare_rates'):
            await self.bot.callback_handlers.start_comparison_selection(update, user, context)
        elif text == get_text(user.lang, 'calculator'):
            await update.message.reply_text(
                get_text(user.lang, 'calculator_mode'),
                parse_mode='Markdown'
            )
            context.user_data['state'] = 'calculator'
        elif text == get_text(user.lang, 'stocks'):
            await self.bot.stocks_handler.show_stocks_menu(update, context)
        elif text == get_text(user.lang, 'cs2_skins'):
            await self.bot.cs2_handler.show_cs2_menu(update, context)
        elif text == get_text(user.lang, 'portfolio'):
            await self.bot.portfolio_handler.show_portfolio_menu(update, context)
        elif text == get_text(user.lang, 'export'):
            await self.bot.export_handler.show_export_menu(update, context)
        elif text == get_text(user.lang, 'news'):
            await self.bot.news_handler.show_news_menu(update, context)
        elif text == get_text(user.lang, 'reports_btn'):
            await self.bot.report_handler.show_report_menu(update, context)
        elif text == get_text(user.lang, 'analytics'):
            await self.bot.analytics_handler.show_analytics_menu(update, context)
        elif text == get_text(user.lang, 'trading_signals'):
            await self.bot.trading_handler.show_signals_menu(update, context)
        elif text == get_text(user.lang, 'notifications'):
            await self.show_alerts(update, context)
        elif text == get_text(user.lang, 'favorites'):
            await self.show_favorites(update, context)
        elif text == get_text(user.lang, 'history'):
            await self.show_history(update, context)
        elif text == get_text(user.lang, 'stats_btn'):
            await self.show_stats(update, context)
        elif text == get_text(user.lang, 'settings'):
            await self.show_settings(update, context)
        elif text == get_text(user.lang, 'about_btn'):
            await update.message.reply_text(
                get_text(user.lang, 'about_text'),
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        elif context.user_data.get('state') == 'calculator':
            # Calculator mode
            result = self.bot.calculator.calculate(text, user_id)
            if result:
                await update.message.reply_text(get_text(user.lang, 'calc_result', result=result))
                self.bot.metrics.log_calculation(user_id)
            else:
                await update.message.reply_text(get_text(user.lang, 'error', msg='Invalid expression'))
        elif context.user_data.get('state') == 'enter_amount':
            # Amount entry for conversion
            try:
                amount = float(text.replace(',', '.'))
                await self.bot.callback_handlers.perform_conversion(update, context, amount, user)
            except:
                await update.message.reply_text(get_text(user.lang, 'invalid_amount'))
        else:
            # Check if waiting for AI input
            temp_data = self.bot.temp_storage.get(user_id)
            if temp_data and temp_data.get('action') == 'ai_question':
                await self.bot.ai_handler.process_question(update, text)
                del self.bot.temp_storage[user_id]
                return
            elif temp_data and temp_data.get('action') == 'ai_suggest':
                await self.bot.ai_handler.process_suggestion_request(update, text)
                del self.bot.temp_storage[user_id]
                return
            # Check if waiting for CS2 search input
            elif temp_data and temp_data.get('state') == 'awaiting_cs2_search':
                await self.bot.cs2_handler.handle_search_query(update, context, text)
                del self.bot.temp_storage[user_id]
                return
            
            # AI Chat mode - Default behavior for non-command messages
            await self.handle_ai_chat(update, context, text, user)
    
    async def show_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show conversion history."""
        user_id = update.effective_user.id
        user = self.bot.db.get_user(user_id)
        
        history = self.bot.db.get_conversion_history(user_id, limit=10)
        
        if not history:
            await update.message.reply_text(get_text(user.lang, 'history_empty'))
            return
        
        history_text = ""
        for h in history:
            history_text += f"• {h.amount} {h.from_currency} → {h.result:.2f} {h.to_currency}\n"
            history_text += f"  _{h.timestamp.strftime('%d.%m.%Y %H:%M')}_\n\n"
        
        await update.message.reply_text(
            get_text(user.lang, 'history_list', history=history_text),
            parse_mode='Markdown'
        )
    
    async def show_favorites(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show favorite currencies."""
        user_id = update.effective_user.id
        user = self.bot.db.get_user(user_id)
        
        favorites = self.bot.db.get_favorites(user_id)
        
        if not favorites:
            await update.message.reply_text(get_text(user.lang, 'favorites_empty'))
            return
        
        favorites_text = ", ".join(favorites)
        await update.message.reply_text(
            get_text(user.lang, 'favorites_list', favorites=favorites_text),
            parse_mode='Markdown'
        )
    
    async def show_alerts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show active alerts."""
        user_id = update.effective_user.id
        user = self.bot.db.get_user(user_id)
        
        alerts = self.bot.alert_manager.get_alerts(user_id)
        
        if not alerts:
            await update.message.reply_text(get_text(user.lang, 'no_alerts'))
            return
        
        alert_text = '\n'.join([
            f"{i+1}. {a['pair']} {a['condition']} ${a['target']}"
            for i, a in enumerate(alerts)
        ])
        
        await update.message.reply_text(
            get_text(user.lang, 'alerts_list', alerts=alert_text),
            parse_mode='Markdown'
        )
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user statistics and crypto market data."""
        user_id = update.effective_user.id
        user = self.bot.db.get_user(user_id)
        
        # Get user stats
        stats = self.bot.db.get_user_stats(user_id)
        popular_pairs = self.bot.db.get_popular_pairs(user_id, days=30, limit=5)
        
        stats_text = (
            f"📊 **Your Statistics**\n\n"
            f"💱 Total conversions: {stats['total_conversions']}\n"
            f"🔔 Active alerts: {stats['total_alerts']}\n"
            f"⭐ Favorite currencies: {stats['favorites_count']}\n"
        )
        
        if popular_pairs:
            stats_text += "\n**Most used pairs (last 30 days):**\n"
            for from_curr, to_curr, count in popular_pairs:
                stats_text += f"• {from_curr} → {to_curr}: {count}x\n"
        
        # Add crypto market data
        stats_text += "\n\n📈 **Live Crypto Prices:**\n"
        
        # Fetch prices for popular cryptos
        popular_cryptos = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP']
        crypto_data = []
        
        for crypto in popular_cryptos:
            try:
                price = self.bot.converter.get_crypto_rate_aggregated(crypto, 'USDT', user_id)
                if price and price > 0:
                    crypto_data.append(f"• **{crypto}:** ${price:,.2f}")
            except Exception as e:
                logger.debug(f"Error fetching price for {crypto}: {e}")
        
        if crypto_data:
            stats_text += "\n".join(crypto_data)
            stats_text += "\n\n_Real-time prices from major exchanges_"
        else:
            stats_text += "_Unable to fetch crypto prices at the moment_\n"
        
        # Add model accuracy comparison
        stats_text += "\n\n🎯 **Forecast Model Accuracy:**\n"
        
        # Get accuracy for BTC (most commonly predicted)
        accuracy_stats = self.bot.prediction_generator.get_accuracy_comparison('BTC', days=30)
        
        if accuracy_stats:
            arima = accuracy_stats.get('arima', {})
            linreg = accuracy_stats.get('linreg', {})
            
            if arima.get('count', 0) > 0:
                stats_text += f"\n📊 **ARIMA Model** (BTC)\n"
                stats_text += f"• Predictions: {arima['count']}\n"
                stats_text += f"• Avg Error: ${arima['avg_mae']:.2f}\n"
                stats_text += f"• Accuracy: {100 - arima['avg_mape']:.1f}%\n"
            
            if linreg.get('count', 0) > 0:
                stats_text += f"\n📊 **Linear Regression** (BTC)\n"
                stats_text += f"• Predictions: {linreg['count']}\n"
                stats_text += f"• Avg Error: ${linreg['avg_mae']:.2f}\n"
                stats_text += f"• Accuracy: {100 - linreg['avg_mape']:.1f}%\n"
            
            if arima.get('count', 0) > 0 and linreg.get('count', 0) > 0:
                # Show which is better
                better = 'ARIMA' if arima['avg_mape'] < linreg['avg_mape'] else 'Linear Regression'
                stats_text += f"\n🏆 **Best Model:** {better}\n"
        else:
            stats_text += "_No forecast history yet. Generate predictions to see accuracy stats!_\n"
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    
    async def show_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show settings menu with interactive options."""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        user_id = update.effective_user.id
        user = self.bot.db.get_user(user_id)
        
        # Get user preferences
        current_lang = user.lang if user else 'en'
        lang_emoji = '🇬🇧' if current_lang == 'en' else '🇷🇺'
        
        # Get chart theme
        current_theme = user.chart_theme if user and hasattr(user, 'chart_theme') else 'light'
        theme_emoji = '☀️' if current_theme == 'light' else '🌙' if current_theme == 'dark' else '🔄'
        
        # Get alerts count
        alerts = self.bot.alert_manager.get_alerts(user_id)
        alerts_count = len(alerts) if alerts else 0
        
        # Create settings menu
        settings_text = (
            f"⚙️ **Settings & Preferences**\n\n"
            f"👤 **User ID:** `{user_id}`\n"
            f"🌍 **Language:** {lang_emoji} {current_lang.upper()}\n"
            f"🎨 **Chart Theme:** {theme_emoji} {current_theme.title()}\n"
            f"🔔 **Active Alerts:** {alerts_count}\n\n"
            f"**Available Options:**\n"
            f"• Change language\n"
            f"• Change chart theme\n"
            f"• Manage alerts\n"
            f"• View bot statistics\n\n"
            f"Select an option below:"
        )
        
        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton('🇬🇧 English', callback_data='settings_lang_en'),
                InlineKeyboardButton('🇷🇺 Русский', callback_data='settings_lang_ru')
            ],
            [
                InlineKeyboardButton('🎨 Chart Theme', callback_data='settings_theme')
            ],
            [
                InlineKeyboardButton('🔔 Manage Alerts', callback_data='settings_alerts'),
                InlineKeyboardButton('📊 Bot Stats', callback_data='settings_stats')
            ],
            [
                InlineKeyboardButton('ℹ️ About', callback_data='settings_about'),
                InlineKeyboardButton('◀️ Back to Menu', callback_data='back_main')
            ]
        ]
        
        await update.message.reply_text(
            settings_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_ai_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                            text: str, user):
        """Handle AI chat interaction and command execution."""
        # Show typing indicator
        await update.message.chat.send_action('typing')
        
        try:
            # Fetch latest news for context
            news_context = None
            try:
                latest_news = await self.bot.news_service.fetch_news(max_age_hours=24)
                if latest_news:
                    news_context = [{'title': news.title} for news in latest_news[:5]]
            except Exception as e:
                logger.debug(f"Failed to fetch news context: {e}")
            
            # Interpret user message with Qwen3-8B
            interpretation = await self.bot.ai_service.interpret_user_message(text, user.lang, news_context)
            
            if interpretation['type'] == 'error':
                await update.message.reply_text(
                    "🤖 AI service is currently unavailable. Please try again later.",
                    parse_mode='Markdown'
                )
                return
            
            # If it's a command, execute it
            if interpretation['type'] == 'command':
                action = interpretation['action']
                params = interpretation['params']
                
                if action == 'FORECAST':
                    symbol = params.get('symbol', 'BTC')
                    await self.execute_forecast_command(update, user, symbol)
                
                elif action == 'CHART':
                    symbol = params.get('symbol', 'BTC')
                    days = params.get('days', 30)
                    await self.execute_chart_command(update, user, symbol, days)
                
                elif action == 'COMPARE':
                    symbol = params.get('symbol', 'BTC')
                    await self.execute_compare_command(update, user, symbol)
                
                elif action == 'CONVERT':
                    amount = params.get('amount', 1)
                    from_curr = params.get('from', 'USD')
                    to_curr = params.get('to', 'EUR')
                    await self.execute_convert_command(update, user, amount, from_curr, to_curr)
                
                elif action == 'STATS':
                    await self.show_stats(update, context)
                
                elif action == 'NEWS':
                    await self.bot.news_handler.show_news_menu(update, context)
                
                elif action == 'HELP':
                    await self.bot.command_handlers.help_command(update, context)
                
                else:
                    # Unknown command - send text response
                    await update.message.reply_text(
                        interpretation['response'] or "I understood your request but couldn't execute it.",
                        parse_mode='Markdown'
                    )
            
            # If it's a text response, send it
            else:
                await update.message.reply_text(
                    f"🤖 {interpretation['response']}",
                    parse_mode='Markdown'
                )
            
        except Exception as e:
            logger.error(f"Error in AI chat: {e}")
            await update.message.reply_text(
                "❌ Sorry, I encountered an error. Please try again.",
                parse_mode='Markdown'
            )
    
    async def execute_forecast_command(self, update: Update, user, symbol: str):
        """Execute forecast command via AI."""
        processing_msg = await update.message.reply_text(
            f"🔮 Generating AI forecast for {symbol}...\n\nAnalyzing 90 days of data...",
            parse_mode='Markdown'
        )
        
        try:
            model = user.prediction_model or 'arima'
            pred_data, stats = self.bot.prediction_generator.generate_prediction(
                f"{symbol}-USD", model, 90
            )
            
            if stats and 'error' in stats:
                await processing_msg.edit_text(
                    f"❌ **Unable to generate forecast for {symbol}**\n\n"
                    f"Reason: {stats.get('error', 'unknown')}\n\n"
                    f"Please try another cryptocurrency.",
                    parse_mode='Markdown'
                )
                return
            
            if pred_data and stats:
                current = stats.get('current', 0)
                predicted = stats.get('predicted', 0)
                
                if current <= 0 or predicted <= 0:
                    await processing_msg.edit_text(
                        f"❌ Invalid forecast data for {symbol}.",
                        parse_mode='Markdown'
                    )
                    return
                
                # Get AI explanation
                explanation = await self.bot.ai_service.explain_forecast(
                    symbol, stats, model.upper(), user.lang
                )
                
                # Send chart with explanation
                caption = (
                    f"🔮 **{symbol}/USD AI Forecast**\n\n"
                    f"📊 **Current Price:** ${current:.2f}\n"
                    f"🎯 **7-Day Forecast:** ${predicted:.2f}\n"
                    f"📈 **Expected Change:** {stats.get('change', 0):+.2f}%\n\n"
                    f"🤖 **AI Explanation:**\n_{explanation}_\n\n"
                    f"⚠️ _Not financial advice._"
                )
                
                await update.message.reply_photo(
                    photo=pred_data,
                    caption=caption,
                    parse_mode='Markdown'
                )
                await processing_msg.delete()
                
            else:
                await processing_msg.edit_text(
                    f"❌ Failed to generate forecast for {symbol}.",
                    parse_mode='Markdown'
                )
        
        except Exception as e:
            logger.error(f"Error executing forecast: {e}")
            await processing_msg.edit_text(
                f"❌ Error generating forecast: {str(e)}",
                parse_mode='Markdown'
            )
    
    async def execute_chart_command(self, update: Update, user, symbol: str, days: int = 30):
        """Execute chart command via AI."""
        processing_msg = await update.message.reply_text(
            f"📊 Generating chart for {symbol}...\n\nPlease wait...",
            parse_mode='Markdown'
        )
        
        try:
            chart_data, stats = self.bot.chart_generator.generate_chart(
                f"{symbol}-USD", days
            )
            
            if chart_data and stats:
                caption = (
                    f"📊 **{symbol}/USD Chart** ({days} days)\n\n"
                    f"💰 Current: **${stats.get('current', 0):.2f}**\n"
                    f"📈 High: ${stats.get('high', 0):.2f}\n"
                    f"📉 Low: ${stats.get('low', 0):.2f}\n"
                    f"📊 Average: ${stats.get('avg', 0):.2f}"
                )
                
                await update.message.reply_photo(
                    photo=chart_data,
                    caption=caption,
                    parse_mode='Markdown'
                )
                await processing_msg.delete()
            else:
                await processing_msg.edit_text(
                    f"❌ Chart generation failed for {symbol}.",
                    parse_mode='Markdown'
                )
        
        except Exception as e:
            logger.error(f"Error executing chart: {e}")
            await processing_msg.edit_text(
                f"❌ Error: {str(e)}",
                parse_mode='Markdown'
            )
    
    async def execute_compare_command(self, update: Update, user, symbol: str):
        """Execute compare command via AI."""
        processing_msg = await update.message.reply_text(
            f"⚖️ Comparing prices for {symbol}...\n\nChecking 5+ exchanges...",
            parse_mode='Markdown'
        )
        
        try:
            rates = self.bot.converter.get_all_crypto_rates(symbol, 'USDT', user.telegram_id)
            
            if not rates:
                await processing_msg.edit_text(
                    f"❌ No price data available for {symbol}.",
                    parse_mode='Markdown'
                )
                return
            
            prices = [r[1] for r in rates]
            avg = sum(prices) / len(prices)
            high = max(prices)
            low = min(prices)
            high_ex = [ex for ex, rate in rates if rate == high][0]
            low_ex = [ex for ex, rate in rates if rate == low][0]
            spread = ((high - low) / avg) * 100
            
            rate_lines = []
            for ex, rate in sorted(rates, key=lambda x: x[1]):
                if rate == low:
                    rate_lines.append(f"✅ **{ex}:** ${rate:.2f} _← Best!_")
                else:
                    rate_lines.append(f"• **{ex}:** ${rate:.2f}")
            
            # Format rate lines
            rates_text = "".join([line + '\n' for line in rate_lines])
            
            result_text = (
                f"⚖️ **{symbol}/USDT Comparison**\n\n"
                f"📊 **Live Prices:**\n"
                f"{rates_text}\n"
                f"📈 **Statistics:**\n"
                f"💰 Average: **${avg:.2f}**\n"
                f"📈 Highest: ${high:.2f} ({high_ex})\n"
                f"📉 Lowest: ${low:.2f} ({low_ex})\n"
                f"📊 Spread: {spread:.2f}%\n\n"
                f"💡 **Best price:** {low_ex}"
            )
            
            await processing_msg.edit_text(result_text, parse_mode='Markdown')
        
        except Exception as e:
            logger.error(f"Error executing compare: {e}")
            await processing_msg.edit_text(
                f"❌ Error: {str(e)}",
                parse_mode='Markdown'
            )
    
    async def execute_convert_command(self, update: Update, user, amount: float, 
                                     from_curr: str, to_curr: str):
        """Execute convert command via AI."""
        try:
            # Ensure amount is float
            amount = float(amount)
            
            rate = self.bot.converter.get_rate(from_curr, to_curr, user.telegram_id)
            
            if not rate or not isinstance(rate, (int, float)):
                await update.message.reply_text(
                    f"❌ Unable to get rate for {from_curr} to {to_curr}.",
                    parse_mode='Markdown'
                )
                return
            
            # Ensure rate is float
            rate = float(rate)
            result = amount * rate
            
            # Save to database
            self.bot.db.add_conversion(user.telegram_id, from_curr, to_curr, amount, result, rate)
            
            await update.message.reply_text(
                f"💱 **Conversion Result**\n\n"
                f"{amount:,.2f} {from_curr} = **{result:,.2f} {to_curr}**\n\n"
                f"📊 Rate: 1 {from_curr} = {rate:.6f} {to_curr}",
                parse_mode='Markdown'
            )
        
        except ValueError as e:
            logger.error(f"Invalid number in conversion: {e}")
            await update.message.reply_text(
                f"❌ Invalid amount or rate value.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error executing convert: {e}")
            await update.message.reply_text(
                f"❌ Conversion error. Please try again.",
                parse_mode='Markdown'
            )
