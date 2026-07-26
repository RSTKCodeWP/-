"""AI Assistant service using Qwen3 cloud models via Ollama for intelligent bot control."""

import asyncio
import json
import re
import base64
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime
import aiohttp
from ..utils.logger import setup_logger

logger = setup_logger('ai_service')


class AIService:
    """Service for AI assistant powered by Qwen3 cloud models with bot command interpretation."""
    
    def __init__(self, ollama_url: str = "http://localhost:11434", 
                 text_model: str = "qwen3-coder:480b-cloud",
                 vision_model: str = "qwen3-vl:235b-cloud"):
        """
        Initialize AI service with Qwen3 cloud models.
        
        Args:
            ollama_url: Ollama API endpoint
            text_model: Text model name (default: qwen3-coder:480b-cloud)
            vision_model: Vision model name (default: qwen3-vl:235b-cloud)
        """
        self.ollama_url = ollama_url
        self.text_model = text_model
        self.vision_model = vision_model
        self.available = False
        self.vision_available = False
        self.context_limit = 32768  # Cloud models have larger context
        self.conversation_history = {}  # Store conversation per user
        
        logger.info(f"AI Service initialized with cloud models:")
        logger.info(f"  - Text: {text_model}")
        logger.info(f"  - Vision: {vision_model}")
    
    async def check_availability(self, auto_pull: bool = False) -> bool:
        """
        Check if Ollama service is available with cloud models.
        
        Args:
            auto_pull: Automatically pull model if not found (not recommended for cloud models)
        
        Returns:
            True if available, False otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.ollama_url}/api/tags", timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        # Check if models are available
                        data = await response.json()
                        models = data.get('models', [])
                        model_names = [m.get('name', '') for m in models]
                        
                        # Check text model
                        if self.text_model in model_names:
                            logger.info(f"✅ Text model {self.text_model} is available")
                            self.available = True
                        else:
                            logger.warning(f"⚠️ Text model {self.text_model} not found in Ollama")
                            if auto_pull:
                                logger.info(f"Attempting to pull {self.text_model}...")
                                await self._pull_model(self.text_model)
                            self.available = False
                        
                        # Check vision model
                        if self.vision_model in model_names:
                            logger.info(f"✅ Vision model {self.vision_model} is available")
                            self.vision_available = True
                        else:
                            logger.warning(f"⚠️ Vision model {self.vision_model} not found in Ollama")
                            self.vision_available = False
                        
                        return self.available
                    else:
                        logger.error(f"Ollama API returned status {response.status}")
                        return False
        except aiohttp.ClientConnectorError:
            logger.error(f"Cannot connect to Ollama at {self.ollama_url}. Is Ollama running?")
            logger.error(f"Make sure Ollama is running and accessible at {self.ollama_url}")
            self.available = False
            return False
        except Exception as e:
            logger.error(f"Error checking Ollama availability: {e}")
            self.available = False
            return False
    
    async def _pull_model(self, model_name: str) -> bool:
        """
        Pull a model from Ollama.
        
        Args:
            model_name: Name of the model to pull
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"📥 Downloading {model_name} model...")
            logger.warning(f"⚠️ Cloud models are very large and may be expensive to run!")
            logger.info(f"⏳ This may take significant time. Please be patient...")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_url}/api/pull",
                    json={'name': model_name},
                    timeout=aiohttp.ClientTimeout(total=3600)  # 1 hour for large cloud models
                ) as response:
                    if response.status == 200:
                        # Show progress by reading stream
                        last_status = None
                        async for line in response.content:
                            try:
                                data = json.loads(line.decode('utf-8'))
                                status = data.get('status', '')
                                if status and status != last_status:
                                    logger.info(f"📦 {status}")
                                    last_status = status
                            except:
                                pass
                        
                        logger.info(f"✅ Model {model_name} downloaded successfully!")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Failed to pull model (HTTP {response.status}): {error_text}")
                        return False
        except asyncio.TimeoutError:
            logger.error(f"❌ Model download timeout.")
            return False
        except Exception as e:
            logger.error(f"❌ Error pulling model: {e}")
            return False
    
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, 
                      temperature: float = 0.7, max_tokens: int = 800) -> Dict:
        """
        Generate response from AI model.
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Max tokens to generate
        
        Returns:
            Response dict with text and metadata
        """
        if not self.available:
            await self.check_availability()
            if not self.available:
                return {
                    'success': False,
                    'error': 'AI service not available',
                    'message': 'Ollama is not running or model not installed'
                }
        
        try:
            payload = {
                "model": self.text_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            if system_prompt:
                payload["system"] = system_prompt
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        # Parse JSON ignoring Content-Type header
                        # (Ollama returns valid JSON with text/plain Content-Type)
                        try:
                            data = await response.json(content_type=None)
                            
                            return {
                                'success': True,
                                'text': data.get('response', '').strip(),
                                'model': data.get('model'),
                                'total_duration': data.get('total_duration', 0) / 1e9,  # Convert to seconds
                                'eval_count': data.get('eval_count', 0)
                            }
                        except json.JSONDecodeError:
                            # If JSON parsing fails, try as text
                            error_text = await response.text()
                            logger.error(f"Ollama returned non-JSON response: {error_text}")
                            
                            # Check if model not found
                            if 'not found' in error_text.lower() or 'model' in error_text.lower():
                                return {
                                    'success': False,
                                    'error': 'model_not_found',
                                    'message': f'Model {self.text_model} not found. Please run: ollama pull {self.text_model}'
                                }
                            
                            return {
                                'success': False,
                                'error': 'invalid_response',
                                'message': f'Ollama returned unexpected response: {error_text[:200]}'
                            }
                    else:
                        error_text = await response.text()
                        logger.error(f"Ollama API error (HTTP {response.status}): {error_text}")
                        return {
                            'success': False,
                            'error': f"API error: {response.status}",
                            'message': error_text
                        }
        
        except asyncio.TimeoutError:
            logger.error("Ollama request timeout")
            return {
                'success': False,
                'error': 'timeout',
                'message': 'Request took too long'
            }
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return {
                'success': False,
                'error': 'exception',
                'message': str(e)
            }
    
    async def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> Dict:
        """
        Chat with AI using conversation history.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
        
        Returns:
            Response dict
        """
        if not self.available:
            await self.check_availability()
            if not self.available:
                return {
                    'success': False,
                    'error': 'AI service not available'
                }
        
        try:
            payload = {
                "model": self.text_model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_url}/api/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=90)
                ) as response:
                    if response.status == 200:
                        # Parse JSON ignoring Content-Type header
                        try:
                            data = await response.json(content_type=None)
                            
                            return {
                                'success': True,
                                'message': data.get('message', {}),
                                'text': data.get('message', {}).get('content', '').strip(),
                                'total_duration': data.get('total_duration', 0) / 1e9
                            }
                        except json.JSONDecodeError:
                            error_text = await response.text()
                            logger.error(f"Ollama chat returned non-JSON: {error_text}")
                            return {
                                'success': False,
                                'error': 'invalid_response',
                                'message': f'Unexpected response format: {error_text[:200]}'
                            }
                    else:
                        error_text = await response.text()
                        logger.error(f"Ollama chat API error (HTTP {response.status}): {error_text}")
                        return {
                            'success': False,
                            'error': f"API error: {response.status}",
                            'message': error_text
                        }
        
        except asyncio.TimeoutError:
            logger.error("Ollama chat request timeout")
            return {
                'success': False,
                'error': 'timeout',
                'message': 'Chat request took too long'
            }
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return {
                'success': False,
                'error': 'exception',
                'message': str(e)
            }
    
    async def analyze_market(self, asset: str, price: float, change_24h: float, 
                           user_query: str = None) -> str:
        """
        Analyze market data for an asset.
        
        Args:
            asset: Asset symbol
            price: Current price
            change_24h: 24h change percentage
            user_query: Optional user question
        
        Returns:
            AI analysis text
        """
        system_prompt = (
            "You are a financial assistant helping users understand cryptocurrency, stock, and fiat currency markets. "
            "You can analyze Bitcoin (BTC), Ethereum (ETH), major stocks (AAPL, TSLA, MSFT, SBER.ME, GAZP.ME, etc.), "
            "and fiat currencies (USD, EUR, RUB, etc.). "
            "Provide brief, clear explanations. Be helpful but remind users this is not financial advice."
        )
        
        prompt = f"""Analyze this market data:
Asset: {asset}
Current Price: ${price:,.2f}
24h Change: {change_24h:+.2f}%

"""
        if user_query:
            prompt += f"User question: {user_query}\n\n"
        
        prompt += "Provide a detailed analysis (3-5 sentences)."
        
        result = await self.generate(prompt, system_prompt=system_prompt, temperature=0.5, max_tokens=800)
        
        if result.get('success'):
            return result['text']
        else:
            return "AI analysis unavailable."
    
    async def analyze_portfolio(self, portfolio_data: Dict, user_query: str = None) -> str:
        """
        Analyze user's portfolio.
        
        Args:
            portfolio_data: Portfolio information
            user_query: Optional user question
        
        Returns:
            AI analysis text
        """
        system_prompt = (
            "You are a financial portfolio advisor. Provide helpful insights about portfolio composition, "
            "diversification, and risk. Keep responses concise. Remind users this is not financial advice."
        )
        
        total_value = portfolio_data.get('total_value', 0)
        items = portfolio_data.get('items', [])
        
        prompt = f"""Analyze this portfolio:
Total Value: ${total_value:,.2f}
Number of Assets: {len(items)}

Assets breakdown:
"""
        for item in items[:10]:  # Limit to top 10
            prompt += f"- {item['symbol']}: ${item.get('value', 0):,.2f} ({item.get('percentage', 0):.1f}%)\n"
        
        if user_query:
            prompt += f"\nUser question: {user_query}\n"
        
        prompt += "\nProvide detailed portfolio analysis (4-6 sentences)."
        
        result = await self.generate(prompt, system_prompt=system_prompt, temperature=0.6, max_tokens=800)
        
        if result.get('success'):
            return result['text']
        else:
            return "AI analysis unavailable."
    
    async def interpret_user_message(self, message: str, user_lang: str = 'en', news_context: Optional[List] = None) -> Dict[str, Any]:
        """
        Interpret user message and extract command or provide text response.
        
        Args:
            message: User's message
            user_lang: User's language (en/ru)
            news_context: Optional list of recent news items for context
        
        Returns:
            Dict with 'type' ('command' or 'text'), 'action', 'params', and 'response'
        """
        # Get current date and time
        now = datetime.now()
        current_date = now.strftime('%Y-%m-%d')
        current_time = now.strftime('%H:%M')
        current_year = now.year
        
        # Build news context string
        news_str = ""
        if news_context:
            news_str = "\n\nLatest financial news:\n"
            for idx, news in enumerate(news_context[:5], 1):
                news_str += f"{idx}. {news.get('title', 'N/A')}\n"
        
        system_prompt = (
            "You are an intelligent assistant for CoinFlow Bot. Your job is to interpret user requests and either:\n"
            "1. Extract a bot command if user wants to use a feature (forecast, chart, convert, compare, etc.)\n"
            "2. Provide a helpful text response if they're asking a general question\n\n"
            f"CURRENT CONTEXT:\n"
            f"Today's date: {current_date}\n"
            f"Current time: {current_time}\n"
            f"Year: {current_year}\n"
            f"{news_str}\n"
            "Available bot commands:\n"
            "- FORECAST <symbol>: Show AI price forecast for cryptocurrencies (BTC, ETH, etc.) and stocks (AAPL, TSLA, SBER.ME, etc.)\n"
            "- CHART <symbol> <days>: Show price chart for crypto, stocks, or fiat currencies (days: 7, 30, 90, 365)\n"
            "- CONVERT <amount> <from> <to>: Convert between crypto, fiat, or calculate stock value\n"
            "- COMPARE <symbol>: Compare prices across exchanges\n"
            "- STATS: Show user statistics\n"
            "- NEWS: Show crypto and market news\n"
            "- HELP: Show help information\n\n"
            "Supported assets:\n"
            "- Cryptocurrencies: BTC, ETH, BNB, SOL, XRP, ADA, DOGE, MATIC, DOT, AVAX, etc.\n"
            "- Stocks: AAPL, MSFT, TSLA, NVDA, GOOGL (US), SBER.ME, GAZP.ME, LKOH.ME (Russian)\n"
            "- Fiat: USD, EUR, RUB, CNY, GBP, JPY, etc.\n\n"
            "If user wants to use a feature, respond with JSON: {\"command\": \"FORECAST\", \"symbol\": \"AAPL\"}\n"
            "If user asks a question, respond normally without JSON.\n\n"
            "IMPORTANT: Always respond in the user's language. "
            "Language: " + ('Russian' if user_lang == 'ru' else 'English')
        )
        
        result = await self.generate(message, system_prompt=system_prompt, temperature=0.3, max_tokens=300)
        
        if not result.get('success'):
            return {'type': 'error', 'response': 'AI service unavailable'}
        
        response_text = result['text']
        
        # Try to parse JSON command
        command = self._extract_command(response_text)
        
        if command:
            return {
                'type': 'command',
                'action': command.get('command', '').upper(),
                'params': command,
                'response': None
            }
        else:
            return {
                'type': 'text',
                'action': None,
                'params': None,
                'response': response_text
            }
    
    def _extract_command(self, text: str) -> Optional[Dict]:
        """
        Extract JSON command from AI response.
        
        Args:
            text: AI response text
        
        Returns:
            Parsed command dict or None
        """
        try:
            # Try to find JSON in response
            json_match = re.search(r'\{[^}]+\}', text)
            if json_match:
                command = json.loads(json_match.group())
                if 'command' in command:
                    return command
        except:
            pass
        
        # Fallback: pattern matching for common requests
        text_lower = text.lower()
        
        # Forecast patterns
        if any(word in text_lower for word in ['forecast', 'прогноз', 'prediction', 'predict']):
            # Check for crypto
            symbols = re.findall(r'\b(BTC|ETH|BNB|SOL|XRP|ADA|DOGE|MATIC|DOT|AVAX)\b', text.upper())
            if symbols:
                return {'command': 'FORECAST', 'symbol': symbols[0]}
            # Check for stocks
            stock_symbols = re.findall(r'\b(AAPL|MSFT|TSLA|NVDA|GOOGL|AMZN|META|SBER|GAZP|LKOH)\b', text.upper())
            if stock_symbols:
                # Add .ME for Russian stocks
                symbol = stock_symbols[0]
                if symbol in ['SBER', 'GAZP', 'LKOH', 'GMKN', 'YNDX', 'ROSN']:
                    symbol = f"{symbol}.ME"
                return {'command': 'FORECAST', 'symbol': symbol, 'type': 'stock'}
        
        # Chart patterns
        if any(word in text_lower for word in ['chart', 'график', 'graph']):
            # Check for crypto
            symbols = re.findall(r'\b(BTC|ETH|BNB|SOL|XRP|ADA|DOGE|MATIC|DOT|AVAX|CNY|USD|EUR|RUB)\b', text.upper())
            days_match = re.search(r'(\d+)\s*(day|days|дней|день)', text_lower)
            days = int(days_match.group(1)) if days_match else 30
            if symbols:
                return {'command': 'CHART', 'symbol': symbols[0], 'days': days}
            # Check for stocks
            stock_symbols = re.findall(r'\b(AAPL|MSFT|TSLA|NVDA|GOOGL|AMZN|META|SBER|GAZP|LKOH|APPLE|TESLA|MICROSOFT|СБЕР|ГАЗПРОМ)\b', text.upper())
            if stock_symbols:
                symbol = stock_symbols[0]
                # Map common names to tickers
                name_map = {'APPLE': 'AAPL', 'TESLA': 'TSLA', 'MICROSOFT': 'MSFT', 'СБЕР': 'SBER', 'ГАЗПРОМ': 'GAZP'}
                symbol = name_map.get(symbol, symbol)
                if symbol in ['SBER', 'GAZP', 'LKOH', 'GMKN', 'YNDX', 'ROSN']:
                    symbol = f"{symbol}.ME"
                return {'command': 'CHART', 'symbol': symbol, 'days': days, 'type': 'stock'}
        
        # Compare patterns
        if any(word in text_lower for word in ['compare', 'сравни', 'comparison']):
            symbols = re.findall(r'\b(BTC|ETH|BNB|SOL|XRP|ADA|DOGE)\b', text.upper())
            if symbols:
                return {'command': 'COMPARE', 'symbol': symbols[0]}
        
        # Convert patterns
        convert_match = re.search(r'(\d+\.?\d*)\s*([A-Z]{3})\s*(?:to|в|in)\s*([A-Z]{3})', text.upper())
        if convert_match:
            return {
                'command': 'CONVERT',
                'amount': float(convert_match.group(1)),
                'from': convert_match.group(2),
                'to': convert_match.group(3)
            }
        
        return None
    
    async def explain_forecast(self, symbol: str, forecast_data: Dict, model_type: str = 'ARIMA', 
                               user_lang: str = 'en') -> str:
        """
        Explain ARIMA/LinReg forecast in simple terms using Qwen3-8B.
        
        Args:
            symbol: Cryptocurrency symbol
            forecast_data: Forecast statistics from prediction service
            model_type: 'ARIMA' or 'LINEAR'
            user_lang: User language
        
        Returns:
            AI explanation text
        """
        system_prompt = (
            "You are a financial education assistant. Explain cryptocurrency price forecasts in simple, "
            "easy-to-understand language. Your audience may not know technical analysis. "
            f"Language: {'Russian' if user_lang == 'ru' else 'English'}. "
            "Keep explanations to 3-4 sentences. Always end with a disclaimer."
        )
        
        current = forecast_data.get('current', 0)
        predicted = forecast_data.get('predicted', 0)
        change = forecast_data.get('change', 0)
        trend = forecast_data.get('trend', 'Unknown')
        confidence = forecast_data.get('confidence', 'medium')
        days_analyzed = forecast_data.get('days_analyzed', 90)
        
        model_description = (
            "ARIMA (AutoRegressive Integrated Moving Average) - a statistical model that identifies patterns in time series"
            if model_type == 'ARIMA' else
            "Linear Regression - a mathematical model that finds trends in historical data"
        )
        
        prompt = f"""Explain this {symbol} price forecast:

Model: {model_type} ({model_description})
Current Price: ${current:,.2f}
7-Day Forecast: ${predicted:,.2f}
Expected Change: {change:+.2f}%
Trend: {trend}
Confidence: {confidence}
Data analyzed: {days_analyzed} days of historical prices

Explain:
1. Why the model predicts this trend (in simple terms)
2. What this means for {symbol}
3. Key disclaimer

Keep it educational and informative."""
        
        result = await self.generate(prompt, system_prompt=system_prompt, temperature=0.6, max_tokens=600)
        
        if result.get('success'):
            return result['text']
        else:
            return (
                f"The {model_type} model analyzed {days_analyzed} days of {symbol} price history and "
                f"predicts a {change:+.2f}% change over the next 7 days. This is based on statistical patterns, "
                f"not financial advice."
            )
    
    async def answer_question(self, question: str, context: str = None, user_lang: str = 'en', news_context: Optional[List] = None) -> str:
        """
        Answer user's question about finance/crypto.
        
        Args:
            question: User's question
            context: Optional context
            user_lang: User language
            news_context: Optional list of recent news for context
        
        Returns:
            AI answer
        """
        # Get current date and time
        now = datetime.now()
        current_date = now.strftime('%Y-%m-%d')
        current_time = now.strftime('%H:%M')
        current_year = now.year
        
        # Build news context
        news_str = ""
        if news_context:
            news_str = "\n\nLatest financial news (use this to provide current market context):\n"
            for idx, news in enumerate(news_context[:5], 1):
                news_str += f"{idx}. {news.get('title', 'N/A')}\n"
        
        system_prompt = (
            "You are a helpful financial assistant for CoinFlow Bot. "
            "Answer questions about cryptocurrencies, stocks, and financial markets. "
            "Be concise, accurate, and friendly. Always remind users that this is educational, not financial advice. \n\n"
            f"CURRENT CONTEXT:\n"
            f"Today's date: {current_date}\n"
            f"Current time: {current_time}\n"
            f"Year: {current_year}\n"
            f"{news_str}\n"
            f"Language: {'Russian' if user_lang == 'ru' else 'English'}."
        )
        
        prompt = question
        if context:
            prompt = f"Context: {context}\n\nQuestion: {question}"
        
        result = await self.generate(prompt, system_prompt=system_prompt, temperature=0.7, max_tokens=3000)
        
        if result.get('success'):
            return result['text']
        else:
            return "Sorry, I couldn't generate a response. Please try again."
    
    async def suggest_action(self, user_intent: str, bot_features: List[str]) -> str:
        """
        Suggest bot actions based on user intent.
        
        Args:
            user_intent: What user wants to do
            bot_features: Available bot features
        
        Returns:
            Suggestion text
        """
        system_prompt = (
            "You are an assistant helping users navigate CoinFlow Bot. "
            "Suggest which bot features to use based on what the user wants to do. "
            "Be brief and direct."
        )
        
        prompt = f"""User wants to: {user_intent}

Available features: {', '.join(bot_features)}

Suggest 1-2 most relevant features and explain briefly how they help."""
        
        result = await self.generate(prompt, system_prompt=system_prompt, temperature=0.5, max_tokens=150)
        
        if result.get('success'):
            return result['text']
        else:
            return "Try using the main menu buttons to explore bot features."
    
    async def get_text_response(self, prompt: str, system_prompt: Optional[str] = None, 
                                temperature: float = 0.7, max_tokens: int = 1000) -> str:
        """
        Get text response from qwen3-coder cloud model.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instructions
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Max tokens to generate
        
        Returns:
            Text response from AI
        """
        result = await self.generate(prompt, system_prompt, temperature, max_tokens)
        
        if result.get('success'):
            return result['text']
        else:
            logger.warning(f"Text generation failed: {result.get('error')}")
            return "AI service is currently unavailable. Please try again later."
    
    async def get_vision_analysis(self, image_path: str, prompt: str, 
                                  temperature: float = 0.7) -> str:
        """
        Analyze image using qwen3-vl vision model.
        
        Args:
            image_path: Path to image file
            prompt: Analysis prompt
            temperature: Sampling temperature
        
        Returns:
            Vision analysis text
        """
        if not self.vision_available:
            logger.warning("Vision model not available")
            return "Vision analysis is currently unavailable."
        
        try:
            # Read and encode image
            with open(image_path, 'rb') as image_file:
                image_data = image_file.read()
                image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Prepare payload for vision model
            payload = {
                "model": self.vision_model,
                "prompt": prompt,
                "images": [image_base64],
                "stream": False,
                "options": {
                    "temperature": temperature
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)  # Vision models can be slower
                ) as response:
                    if response.status == 200:
                        # Parse JSON ignoring Content-Type header
                        try:
                            data = await response.json(content_type=None)
                            return data.get('response', '').strip()
                        except json.JSONDecodeError:
                            error_text = await response.text()
                            logger.error(f"Vision API returned non-JSON: {error_text}")
                            
                            if 'not found' in error_text.lower():
                                return f"Vision model {self.vision_model} not found. Please install it first."
                            
                            return "Failed to analyze image: Unexpected response format."
                    else:
                        error_text = await response.text()
                        logger.error(f"Vision API error (HTTP {response.status}): {error_text}")
                        return "Failed to analyze image."
        
        except FileNotFoundError:
            logger.error(f"Image file not found: {image_path}")
            return "Image file not found."
        except Exception as e:
            logger.error(f"Error in vision analysis: {e}")
            return "Error analyzing image."
