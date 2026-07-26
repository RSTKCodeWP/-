"""Central AI assistant service - handles all user messages and voice input."""
import logging
from typing import Optional, Dict, List
from aiogram.types import Message
from api_clients import TarkovAPIClient
from database import Database
from localization import get_text
from .ai_generation_service import AIGenerationService

logger = logging.getLogger(__name__)


class AIAssistant:
    """Nikita Buyanov AI Assistant - central message handler."""
    
    def __init__(
        self,
        api_client: TarkovAPIClient,
        db: Database,
        ai_generation_service: AIGenerationService,
        news_service=None
    ):
        self.api = api_client
        self.db = db
        self.ai_gen = ai_generation_service
        self.news_service = news_service
        self.fallback_enabled = True
    
    async def handle_message(self, message: Message, user_language: str = "ru") -> str:
        """
        Handle incoming text message.
        
        Args:
            message: Telegram message object
            user_language: User's language preference
            
        Returns:
            Response text to send to user
        """
        user_id = message.from_user.id
        user_text = message.text
        
        logger.info(f"AI Assistant handling message from user {user_id}: {user_text[:50]}...")
        
        # Check if Ollama is available
        ollama_available = await self.ai_gen.check_ollama_available()
        
        if not ollama_available:
            logger.warning("Ollama not available, using fallback")
            return await self._fallback_response(user_text, user_id, user_language)
        
        # Try AI generation
        try:
            # Detect if this is a quest info request (v5.3)
            if self._is_quest_info_request(user_text, user_language):
                return await self._handle_quest_info(user_text, user_id, user_language)
            
            # Detect if this is a build request
            if self._is_build_request(user_text, user_language):
                # Send generating indicator
                indicator_text = get_text("ai_generating", user_language)
                await message.answer(indicator_text)
                
                build_data = await self.ai_gen.generate_build(
                    user_text,
                    user_id,
                    user_language
                )
                
                if build_data and build_data.get("text"):
                    return build_data["text"]
                else:
                    logger.warning("AI generation returned no result")
                    return await self._fallback_response(user_text, user_id, user_language)
            
            # General conversation/questions
            # Send generating indicator
            indicator_text = get_text("ai_generating", user_language)
            await message.answer(indicator_text)
            
            response = await self._handle_general_query(user_text, user_id, user_language)
            return response
            
        except Exception as e:
            logger.error(f"Error in AI assistant: {e}", exc_info=True)
            return await self._fallback_response(user_text, user_id, user_language)
    
    async def handle_voice(self, message: Message, voice_file_path: str, user_language: str = "ru") -> str:
        """
        Handle incoming voice message.
        
        Args:
            message: Telegram message object
            voice_file_path: Path to downloaded voice file
            user_language: User's language preference
            
        Returns:
            Response text to send to user
        """
        user_id = message.from_user.id
        
        logger.info(f"AI Assistant handling voice message from user {user_id}")
        
        try:
            # Import voice transcriber
            from utils.voice_transcriber import VoiceTranscriber
            
            transcriber = VoiceTranscriber()
            
            # Transcribe voice to text
            transcribed_text = await transcriber.transcribe(voice_file_path, user_language)
            
            if not transcribed_text:
                return get_text("voice_transcription_failed", user_language)
            
            logger.info(f"Transcribed voice: {transcribed_text}")
            
            # Create a mock message object with transcribed text
            class MockMessage:
                def __init__(self, text, from_user, bot, chat):
                    self.text = text
                    self.from_user = from_user
                    self.bot = bot
                    self.chat = chat
                
                async def answer(self, text, **kwargs):
                    """Mock answer method - does nothing for voice messages."""
                    pass
            
            mock_message = MockMessage(transcribed_text, message.from_user, message.bot, message.chat)
            
            # Handle as text message
            response = await self.handle_message(mock_message, user_language)
            
            # Prepend transcription
            transcription_prefix = get_text("voice_transcribed", user_language, text=transcribed_text)
            return f"{transcription_prefix}\n\n{response}"
            
        except ImportError:
            logger.error("Voice transcriber not available")
            return get_text("voice_not_supported", user_language)
        except Exception as e:
            logger.error(f"Error handling voice: {e}", exc_info=True)
            return get_text("voice_processing_error", user_language)
    
    def _is_news_request(self, text: str, language: str) -> bool:
        """Check if message is a news request."""
        text_lower = text.lower()
        
        news_keywords_ru = [
            "новост", "новинк", "что нового", "последние новости",
            "обновлен", "патч", "вайп", "что случилось", "что изменилось"
        ]
        
        news_keywords_en = [
            "news", "update", "patch", "wipe", "what's new", "latest",
            "changelog", "what happened", "what changed"
        ]
        
        keywords = news_keywords_ru if language == "ru" else news_keywords_en
        
        return any(keyword in text_lower for keyword in keywords)
    
    def _is_quest_info_request(self, text: str, language: str) -> bool:
        """Check if message is asking about quest information (v5.3)."""
        text_lower = text.lower()
        
        quest_keywords_ru = [
            "квест", "задани", "задача", "как пройти", "как выполнить",
            "что нужно", "цели квеста", "награда", "оружейник"
        ]
        
        quest_keywords_en = [
            "quest", "task", "mission", "how to complete", "how to pass",
            "what do i need", "objectives", "reward", "gunsmith"
        ]
        
        # Check for quest-related keywords
        keywords = quest_keywords_ru if language == "ru" else quest_keywords_en
        has_quest_keyword = any(keyword in text_lower for keyword in keywords)
        
        # But exclude if it's a build request for quest
        build_keywords = ["сборк", "build"] if language == "ru" else ["build"]
        is_build_request = any(bk in text_lower for bk in build_keywords)
        
        return has_quest_keyword and not is_build_request
    
    def _is_build_request(self, text: str, language: str) -> bool:
        """Check if message is a build request."""
        text_lower = text.lower()
        
        build_keywords_ru = [
            "сборк", "сделай", "собери", "покажи", "нужна", "хочу",
            "построй", "создай", "подбери", "рекомендуй"
        ]
        
        build_keywords_en = [
            "build", "make", "create", "show", "need", "want",
            "recommend", "suggest", "assemble"
        ]
        
        keywords = build_keywords_ru if language == "ru" else build_keywords_en
        
        return any(keyword in text_lower for keyword in keywords)
    
    async def _handle_quest_info(self, text: str, user_id: int, language: str) -> str:
        """Handle quest information requests (v5.3)."""
        from .context_builder import ContextBuilder
        context_builder = ContextBuilder(self.api, self.db)
        
        # Try to extract quest name from text
        quest_name = self._extract_quest_name(text, language)
        
        if quest_name:
            # Get detailed quest info
            quest_info = await context_builder.build_quest_info_context(quest_name, language)
            
            if "not found" in quest_info.lower():
                # Quest not found, use AI to help
                return await self._handle_general_query(text, user_id, language)
            
            # Format response with quest info
            if language == "ru":
                response = f"🤖 Никита Буянов:\n\n{quest_info}"
            else:
                response = f"🤖 Nikita Buyanov:\n\n{quest_info}"
            
            return response
        else:
            # No specific quest name found, let AI handle it
            return await self._handle_general_query(text, user_id, language)
    
    def _extract_quest_name(self, text: str, language: str) -> Optional[str]:
        """Extract quest name from user text."""
        import re
        
        # Common quest name patterns
        gunsmith_patterns = [
            r"оружейник[а-я]*\s*(\d+)",  # Russian: Оружейник 1, etc.
            r"gunsmith[\s-]*(\d+)",       # English: Gunsmith 1, etc.
        ]
        
        for pattern in gunsmith_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                number = match.group(1)
                return f"Gunsmith - Part {number}" if language == "en" else f"Оружейник - Часть {number}"
        
        # Try to find quoted quest names
        quote_patterns = [r'"([^"]+)"', r"'([^']+)'"]
        for pattern in quote_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        return None
    
    async def _handle_general_query(self, text: str, user_id: int, language: str) -> str:
        """Handle general conversation/questions."""
        # Check if Ollama is available
        ollama_available = await self.ai_gen.check_ollama_available()
        
        if not ollama_available:
            return get_text("ai_not_available", language)
        
        # Build context for general query
        from .context_builder import ContextBuilder
        context_builder = ContextBuilder(self.api, self.db)
        
        user_context = await context_builder.build_user_context(user_id)
        
        # Get latest news from Telegram for context
        news_context = ""
        if self.news_service:
            try:
                # Get all recent news - AI analyzes everything
                all_news = await self.news_service.get_latest_news(lang=language, limit=15)
                if all_news:
                    logger.info(f"Fetched {len(all_news)} news items for AI context")
                    
                    news_list = "\n\n".join([
                        f"{i+1}. {item['title']}\n   Дата: {item['date']}\n   {item['description']}\n   Link: {item['link']}"
                        for i, item in enumerate(all_news)
                    ])
                    if language == "ru":
                        news_context = f"\n\nПОСЛЕДНИЕ НОВОСТИ ИЗ TELEGRAM @escapefromtarkovRU ({len(all_news)} постов):\n\n{news_list}\n"
                    else:
                        news_context = f"\n\nLATEST NEWS FROM TELEGRAM @escapefromtarkovEN ({len(all_news)} posts):\n\n{news_list}\n"
            except Exception as e:
                logger.error(f"Failed to fetch news: {e}")
        
        # Check if question is about quests/tasks and add quest context
        text_lower = text.lower()
        quest_keywords = ["квест", "задание", "задача", "оружейник", "gunsmith", "quest", "task", "mission"] if language == "ru" else ["quest", "task", "mission", "gunsmith"]
        is_quest_question = any(kw in text_lower for kw in quest_keywords)
        
        # Check if question is about news/release/updates
        if language == "ru":
            news_keywords = ["релиз", "выход", "release", "вайп", "wipe", "обновлен", "патч", "patch", "update", 
                           "новост", "news", "когда", "when", "дата", "date", "steam", "версия", "version"]
        else:
            news_keywords = ["release", "wipe", "update", "patch", "news", "when", "date", "steam", "version", "launch"]
        
        is_news_question = any(kw in text_lower for kw in news_keywords)
        logger.info(f"Question about news/release: {is_news_question}")
        
        quest_context = ""
        if is_quest_question:
            # Try to extract quest name
            quest_name = self._extract_quest_name(text, language)
            if quest_name:
                quest_context = await context_builder.build_quest_info_context(quest_name, language)
            else:
                # Provide general quest context
                quest_context = await context_builder.build_quest_context(language=language)
        
        # Prepare quest context section (avoid backslash in f-string expressions)
        quest_context_section = ""
        if quest_context:
            quest_context_section = f"Информация о квестах из API:\n{quest_context}\n\n"
        
        # Create prompt for general conversation
        news_emphasis = ""
        if is_news_question and news_context:
            news_emphasis = "\n\n⚠️ ВНИМАНИЕ! Игрок СПРАШИВАЕТ О НОВОСТЯХ/РЕЛИЗЕ! ОБЯЗАТЕЛЬНО ИСПОЛЬЗУЙ ИНФОРМАЦИЮ ИЗ НОВОСТЕЙ ВЫШЕ! ⚠️\n"
        
        if language == "ru":
            prompt = f"""Ты — Никита Буянов, главный разработчик Escape from Tarkov.
Отвечай на вопросы игроков дружелюбно и профессионально на РУССКОМ языке.

КРИТИЧЕСКИ ВАЖНО:
- ОТВЕЧАЙ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ
- НЕ ПОКАЗЫВАЙ ID предметов
- ВСЯ информация о квестах берется ИЗ API tarkov.dev

ПРАВИЛА ДЛЯ НОВОСТЕЙ:
1. ЕСЛИ в контексте НИЖЕ ЕСТЬ новости - ОБЯЗАТЕЛЬНО используй их!
2. ЕСЛИ в новостях указана ДАТА РЕЛИЗА - ОБЯЗАТЕЛЬНО сообщи ее!
3. ЕСЛИ в новостях есть Steam/релиз - ОБЯЗАТЕЛЬНО упомяни это!
4. ЕСЛИ новостей НЕТ - только тогда скажи что не знаешь
5. НЕ ВЫДУМЫВАЙ ИНФОРМАЦИЮ - ТОЛЬКО ИЗ КОНТЕКСТА!

Информация о пользователе:
{user_context}{news_context}
{news_emphasis}
{quest_context_section}Вопрос игрока: {text}

Твой ответ на русском (ИСПОЛЬЗУЙ ИНФОРМАЦИЮ ИЗ НОВОСТЕЙ):"""
        else:
            quest_context_section_en = ""
            if quest_context:
                quest_context_section_en = f"Quest information from API:\n{quest_context}\n\n"
            
            news_emphasis_en = ""
            if is_news_question and news_context:
                news_emphasis_en = "\n\n⚠️ ATTENTION! Player is ASKING ABOUT NEWS/RELEASE! YOU MUST USE INFORMATION FROM NEWS ABOVE! ⚠️\n"
            
            prompt = f"""You are Nikita Buyanov, lead developer of Escape from Tarkov.
Answer player questions in a friendly and professional manner in ENGLISH.

CRITICALLY IMPORTANT:
- RESPOND ONLY IN ENGLISH
- DO NOT SHOW item IDs
- ALL quest information comes FROM tarkov.dev API

RULES FOR NEWS:
1. IF there ARE news in context BELOW - YOU MUST use them!
2. IF news mention RELEASE DATE - YOU MUST tell it!
3. IF news mention Steam/release - YOU MUST mention it!
4. IF there are NO news - only then say you don't know
5. DO NOT MAKE UP information - ONLY FROM CONTEXT!

User information:
{user_context}{news_context}
{news_emphasis_en}
{quest_context_section_en}Player's question: {text}

Your response in English (USE INFORMATION FROM NEWS):"""
        
        try:
            response = await self.ai_gen._call_ollama(prompt)
            if response:
                return f"🤖 Никита Буянов:\n{response}" if language == "ru" else f"🤖 Nikita Buyanov:\n{response}"
            else:
                return get_text("ai_no_response", language)
        except Exception as e:
            logger.error(f"Error in general question: {e}")
            return get_text("ai_error", language)
    
    async def _fallback_response(self, text: str, user_id: int, language: str) -> str:
        # Basic fallback message without Markdown to avoid parsing errors
        if language == "ru":
            fallback_text = "Ассистент недоступен. Используйте меню для работы с ботом."
        else:
            fallback_text = "Assistant is not available. Use menu to work with the bot."
        
        # Try to provide relevant menu suggestions based on keywords
        text_lower = text.lower()
        
        suggestions = []
        
        if any(kw in text_lower for kw in ["сборк", "build", "оружи", "weapon"]):
            if language == "ru":
                suggestions.append("Поиск оружия")
                suggestions.append("Случайная сборка")
            else:
                suggestions.append("Search weapon")
                suggestions.append("Random build")
        
        if any(kw in text_lower for kw in ["квест", "quest", "оружейник", "gunsmith"]):
            if language == "ru":
                suggestions.append("Квесты")
            else:
                suggestions.append("Quests")
        
        if any(kw in text_lower for kw in ["мета", "meta", "лучш", "best"]):
            if language == "ru":
                suggestions.append("Лучшее оружие")
            else:
                suggestions.append("Best weapons")
        
        if suggestions:
            header = "\n\nВозможно, вы ищете:" if language == "ru" else "\n\nMaybe you're looking for:"
            suggestions_text = "\n".join(f"• {s}" for s in suggestions)
            return f"{fallback_text}{header}\n{suggestions_text}"
        
        return fallback_text
    
    async def generate_quest_build_response(
        self, 
        quest_name: str, 
        user_id: int, 
        language: str = "ru"
    ) -> str:
        """
        Generate build response for a specific quest.
        
        Args:
            quest_name: Name of the quest
            user_id: Telegram user ID
            language: User's language preference
            
        Returns:
            Formatted response with quest build
        """
        ollama_available = await self.ai_gen.check_ollama_available()
        
        if not ollama_available:
            logger.warning("Ollama not available for quest build")
            # Fallback to existing quest build logic would go here
            return get_text("ai_not_available", language)
        
        try:
            build_data = await self.ai_gen.generate_quest_build(
                quest_name,
                user_id,
                language
            )
            
            if build_data and build_data.get("text"):
                return build_data["text"]
            else:
                return get_text("quest_build_failed", language)
                
        except Exception as e:
            logger.error(f"Error generating quest build: {e}", exc_info=True)
            return get_text("ai_error", language)
    
    async def generate_meta_build_response(
        self,
        weapon_name: Optional[str],
        user_id: int,
        language: str = "ru"
    ) -> str:
        """
        Generate meta build response.
        
        Args:
            weapon_name: Optional specific weapon name
            user_id: Telegram user ID
            language: User's language preference
            
        Returns:
            Formatted response with meta build
        """
        if weapon_name:
            request = get_text("meta_build_request", language, weapon=weapon_name)
        else:
            request = get_text("meta_build_request_general", language)
        
        return await self.handle_message(
            type('obj', (object,), {
                'text': request,
                'from_user': type('obj', (object,), {'id': user_id})()
            })(),
            language
        )
