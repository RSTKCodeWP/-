"""AI Assistant handler for CoinFlow bot."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..localization import get_text
from ..utils.logger import setup_logger

logger = setup_logger('ai_handler')


class AIHandler:
    """Handler for AI assistant interactions."""
    
    def __init__(self, bot):
        """Initialize AI handler."""
        self.bot = bot
        self.conversation_context = {}  # Store conversation history per user
    
    async def show_ai_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show AI assistant menu."""
        user_id = update.effective_user.id
        user = self.bot.db.get_user(user_id)
        
        # Check if AI is available
        is_available = await self.bot.ai_service.check_availability()
        
        if not is_available:
            keyboard = [
                [InlineKeyboardButton(
                    "📖 Setup Instructions",
                    callback_data='ai_setup'
                )],
                [InlineKeyboardButton(
                    get_text(user.lang, 'back'),
                    callback_data='back_main'
                )]
            ]
            
            message = (
                "🤖 **AI Assistant**\n\n"
                "⚠️ AI service is not available.\n\n"
                "**Setup Required:**\n"
                "1. Install Ollama: https://ollama.ai\n"
                "2. Run: `ollama pull llama3.2:3b`\n"
                "3. Start Ollama service\n\n"
                "Once setup is complete, the AI assistant will be ready!"
            )
        else:
            keyboard = [
                [InlineKeyboardButton(
                    "💬 Ask Question",
                    callback_data='ai_ask'
                )],
                [InlineKeyboardButton(
                    "📊 Analyze Market",
                    callback_data='ai_market'
                )],
                [InlineKeyboardButton(
                    "💼 Portfolio Insights",
                    callback_data='ai_portfolio'
                )],
                [InlineKeyboardButton(
                    "💡 Get Suggestions",
                    callback_data='ai_suggest'
                )],
                [InlineKeyboardButton(
                    get_text(user.lang, 'back'),
                    callback_data='back_main'
                )]
            ]
            
            message = (
                "🤖 **AI Assistant (Llama 3.2 3B)**\n\n"
                "✅ AI service is online and ready!\n\n"
                "**What can I help you with?**\n\n"
                "💬 **Ask Question**: Get answers about crypto, stocks, markets\n"
                "📊 **Analyze Market**: AI analysis of current prices and trends\n"
                "💼 **Portfolio Insights**: Get AI analysis of your portfolio\n"
                "💡 **Get Suggestions**: Find the right bot feature for your needs\n\n"
                "_Powered by local Llama 3.2 3B model_"
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
    
    async def show_setup_instructions(self, query, user):
        """Show AI setup instructions."""
        await query.answer()
        
        message = (
            "📖 **AI Assistant Setup**\n\n"
            "**Step 1: Install Ollama**\n"
            "Visit: https://ollama.ai\n"
            "Download and install for your OS\n\n"
            "**Step 2: Pull Model**\n"
            "```\n"
            "ollama pull llama3.2:3b\n"
            "```\n\n"
            "**Step 3: Start Service**\n"
            "Ollama runs automatically after installation.\n"
            "Default endpoint: http://localhost:11434\n\n"
            "**Step 4: Verify**\n"
            "```\n"
            "ollama list\n"
            "```\n"
            "You should see `llama3.2:3b` in the list.\n\n"
            "**Optional: Configure**\n"
            "Set `OLLAMA_URL` in `.env` if using custom endpoint."
        )
        
        keyboard = [
            [InlineKeyboardButton(
                "🔄 Check Again",
                callback_data='ai_menu'
            )],
            [InlineKeyboardButton(
                get_text(user.lang, 'back'),
                callback_data='back_main'
            )]
        ]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_ask_question(self, query, user):
        """Handle ask question flow."""
        await query.answer()
        
        # Store state for next message
        self.bot.temp_storage[user.telegram_id] = {
            'action': 'ai_question',
            'timestamp': query.message.date
        }
        
        await query.edit_message_text(
            "💬 **Ask AI Assistant**\n\n"
            "Type your question about:\n"
            "• Cryptocurrencies\n"
            "• Stock markets\n"
            "• Financial concepts\n"
            "• Trading strategies\n\n"
            "Example: _\"What is Bitcoin halving?\"_\n\n"
            "Send /cancel to return to menu.",
            parse_mode='Markdown'
        )
    
    async def process_question(self, update: Update, question: str):
        """Process user question."""
        user_id = update.effective_user.id
        user = self.bot.db.get_user(user_id)
        
        # Show typing action
        await update.message.chat.send_action('typing')
        
        # Show processing message
        processing_msg = await update.message.reply_text(
            get_text(user.lang, 'ai_thinking'),
            parse_mode='Markdown'
        )
        
        try:
            # Get AI response
            answer = await self.bot.ai_service.answer_question(question)
            
            await processing_msg.edit_text(
                f"💬 **Question:**\n_{question}_\n\n"
                f"🤖 **AI Answer:**\n{answer}\n\n"
                f"_⚠️ This is educational information, not financial advice._",
                parse_mode='Markdown'
            )
            
            logger.info(f"AI answered question for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error processing AI question: {e}")
            await processing_msg.edit_text(
                "❌ Error processing your question. Please try again.",
                parse_mode='Markdown'
            )
    
    async def handle_market_analysis(self, query, user):
        """Show market analysis options."""
        await query.answer()
        
        keyboard = [
            [InlineKeyboardButton("BTC", callback_data='ai_analyze_BTC'),
             InlineKeyboardButton("ETH", callback_data='ai_analyze_ETH')],
            [InlineKeyboardButton("BNB", callback_data='ai_analyze_BNB'),
             InlineKeyboardButton("SOL", callback_data='ai_analyze_SOL')],
            [InlineKeyboardButton("XRP", callback_data='ai_analyze_XRP'),
             InlineKeyboardButton("ADA", callback_data='ai_analyze_ADA')],
            [InlineKeyboardButton(
                get_text(user.lang, 'back'),
                callback_data='ai_menu'
            )]
        ]
        
        await query.edit_message_text(
            "📊 **Market Analysis**\n\n"
            "Select an asset to analyze:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def perform_market_analysis(self, query, user, asset: str):
        """Perform AI market analysis."""
        await query.answer()
        
        # Show typing action
        await query.message.chat.send_action('typing')
        
        await query.edit_message_text(
            get_text(user.lang, 'ai_generating'),
            parse_mode='Markdown'
        )
        
        try:
            # Get current price
            rate = self.bot.converter.get_crypto_rate_aggregated(asset, 'USDT')
            
            if not rate:
                await query.edit_message_text(
                    f"❌ Could not fetch {asset} price.",
                    parse_mode='Markdown'
                )
                return
            
            # Get 24h change (mock for now, would need historical data)
            change_24h = 0.0  # TODO: Calculate from historical data
            
            # Get AI analysis
            analysis = await self.bot.ai_service.analyze_market(asset, rate, change_24h)
            
            await query.edit_message_text(
                f"📊 **{asset} Market Analysis**\n\n"
                f"💰 Current Price: ${rate:,.2f}\n"
                f"📈 24h Change: {change_24h:+.2f}%\n\n"
                f"🤖 **AI Analysis:**\n{analysis}\n\n"
                f"_⚠️ This is not financial advice._",
                parse_mode='Markdown'
            )
            
            logger.info(f"AI analyzed {asset} for user {user.telegram_id}")
            
        except Exception as e:
            logger.error(f"Error in market analysis: {e}")
            await query.edit_message_text(
                "❌ Error performing analysis.",
                parse_mode='Markdown'
            )
    
    async def handle_portfolio_insights(self, query, user):
        """Provide AI insights on user's portfolio."""
        await query.answer()
        
        # Show typing action
        await query.message.chat.send_action('typing')
        
        await query.edit_message_text(
            get_text(user.lang, 'ai_generating'),
            parse_mode='Markdown'
        )
        
        try:
            # Get portfolio data
            portfolio_items = self.bot.db.get_portfolio_items(user.telegram_id)
            
            if not portfolio_items:
                await query.edit_message_text(
                    "💼 **Portfolio Empty**\n\n"
                    "You don't have any items in your portfolio yet.\n"
                    "Add some assets first using the Portfolio menu!",
                    parse_mode='Markdown'
                )
                return
            
            # Calculate portfolio value and prepare data
            total_value = 0
            items_data = []
            
            for item in portfolio_items:
                value = 0
                
                if item.asset_type == 'crypto':
                    rate = self.bot.converter.get_crypto_rate_aggregated(item.asset_symbol, 'USDT')
                    if rate:
                        value = float(item.quantity) * rate
                elif item.asset_type == 'stock':
                    stock_data = self.bot.stock_service.get_stock_info(item.asset_symbol)
                    if stock_data and stock_data.get('price'):
                        value = float(item.quantity) * stock_data['price']
                
                total_value += value
                items_data.append({
                    'symbol': item.asset_symbol,
                    'value': value,
                    'percentage': 0  # Will calculate after
                })
            
            # Calculate percentages
            for item in items_data:
                if total_value > 0:
                    item['percentage'] = (item['value'] / total_value) * 100
            
            # Sort by value
            items_data.sort(key=lambda x: x['value'], reverse=True)
            
            portfolio_data = {
                'total_value': total_value,
                'items': items_data
            }
            
            # Get AI insights
            insights = await self.bot.ai_service.analyze_portfolio(portfolio_data)
            
            await query.edit_message_text(
                f"💼 **Portfolio AI Insights**\n\n"
                f"📊 Total Value: ${total_value:,.2f}\n"
                f"📦 Assets: {len(items_data)}\n\n"
                f"🤖 **AI Analysis:**\n{insights}\n\n"
                f"_⚠️ This is educational analysis, not financial advice._",
                parse_mode='Markdown'
            )
            
            logger.info(f"AI analyzed portfolio for user {user.telegram_id}")
            
        except Exception as e:
            logger.error(f"Error analyzing portfolio: {e}")
            await query.edit_message_text(
                "❌ Error analyzing portfolio.",
                parse_mode='Markdown'
            )
    
    async def handle_suggestions(self, query, user):
        """Get AI suggestions for bot features."""
        await query.answer()
        
        # Store state for next message
        self.bot.temp_storage[user.telegram_id] = {
            'action': 'ai_suggest',
            'timestamp': query.message.date
        }
        
        await query.edit_message_text(
            "💡 **Get AI Suggestions**\n\n"
            "Tell me what you want to do, and I'll suggest which bot features to use.\n\n"
            "Example:\n"
            "_\"I want to track Bitcoin price\"_\n"
            "_\"How do I save my favorite currencies?\"_\n"
            "_\"I need to see crypto charts\"_\n\n"
            "Send /cancel to return to menu.",
            parse_mode='Markdown'
        )
    
    async def process_suggestion_request(self, update: Update, user_intent: str):
        """Process suggestion request."""
        user_id = update.effective_user.id
        user = self.bot.db.get_user(user_id)
        
        # Show typing action
        await update.message.chat.send_action('typing')
        
        processing_msg = await update.message.reply_text(get_text(user.lang, 'ai_generating'))
        
        try:
            bot_features = [
                "Quick Convert", "Rate Charts", "Rate Forecast", "Compare Rates",
                "Stocks", "CS2 Skins", "Portfolio", "Export", "Calculator",
                "Notifications", "Favorites", "History", "Stats", "News", "Reports"
            ]
            
            suggestion = await self.bot.ai_service.suggest_action(user_intent, bot_features)
            
            await processing_msg.edit_text(
                f"💡 **Your Goal:**\n_{user_intent}_\n\n"
                f"🤖 **AI Suggestion:**\n{suggestion}",
                parse_mode='Markdown'
            )
            
            logger.info(f"AI provided suggestion for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error processing suggestion: {e}")
            await processing_msg.edit_text(
                "❌ Error processing your request.",
                parse_mode='Markdown'
            )
