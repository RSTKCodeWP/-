"""
Dailies Service for OLEG v6.0 Fortress Update.

Manages daily scheduled messages including:
- Evening summary (#dailysummary) at 20:00 Moscow time
- Evening quote (#dailyquote) at 21:00 Moscow time
- Evening stats (#dailystats) at 21:00 Moscow time

Features:
- LLM-generated chat summary
- Mood analysis
- Activity comparison with previous day
- Interesting quotes of the day
- Hot topics with links
- Toxicity thermometer

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
"""

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func, and_, extract, desc
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Minimum activity threshold for sending summary (Requirement 13.5)
MIN_ACTIVITY_FOR_SUMMARY = 1  # At least 1 message to send summary

# Quote categories for variety
QUOTE_CATEGORIES = {
    "philosophy": [
        "Если долго смотреть в монитор, монитор начинает смотреть в тебя.",
        "Код работает — не трогай. Не работает — тоже не трогай.",
        "Лучший код — тот, который не пришлось писать.",
        "Проблема не в том, что ты не знаешь. Проблема в том, что ты уверен в том, чего не знаешь.",
        "Оптимист верит, что мы живём в лучшем из миров. Пессимист боится, что так оно и есть.",
        "Единственная настоящая ошибка — та, из которой мы ничего не извлекли.",
        "Сложность — враг надёжности.",
        "Простота — это не когда нечего добавить, а когда нечего убрать.",
    ],
    "it_wisdom": [
        "В продакшене работает — значит работает. Почему — вопрос философский.",
        "Документация как секс: когда хорошая — очень хорошая, когда плохая — лучше, чем ничего.",
        "Первое правило отладки: это не баг, это фича. Второе правило: см. первое.",
        "Legacy код — это код, который приносит деньги.",
        "Хороший программист — ленивый программист. Он автоматизирует всё.",
        "git push --force — и пусть весь мир подождёт.",
        "Работает? Коммить. Не работает? Тоже коммить, но с припиской WIP.",
        "Лучшая оптимизация — удалить код.",
        "Любая достаточно сложная система содержит баг. Любая простая — два.",
        "Код ревью: искусство вежливо сказать 'какого хрена'.",
    ],
    "life": [
        "Не все, кто бродит, потерялись. Некоторые просто прокрастинируют.",
        "План — это список вещей, которые пойдут не так.",
        "Дедлайн — лучшая мотивация. Особенно вчерашний.",
        "Кофе не решает проблемы, но и чай не решает.",
        "Если не можешь объяснить просто — значит сам не понял.",
        "Опыт — это когда вместо новых ошибок делаешь старые, но быстрее.",
        "Перфекционизм — это прокрастинация в красивой обёртке.",
        "Иногда лучшее решение — пойти поспать.",
        "Сегодня не тот день, когда я буду разбираться с этим. Завтра тоже.",
    ],
    "motivation": [
        "Сделай или не сделай. Пробовать — это для слабаков.",
        "Каждый эксперт когда-то был новичком, который не сдался.",
        "Маленький прогресс — тоже прогресс.",
        "Не сравнивай свой первый шаг с чьим-то сотым.",
        "Ошибки — это просто данные для следующей итерации.",
        "Начни. Остальное приложится.",
        "Лучше сделать на 80% сегодня, чем на 100% никогда.",
        "Усталость — временная. Результат — постоянный.",
    ],
    "absurd": [
        "Если код работает с первого раза — проверь, тот ли файл ты запустил.",
        "Вселенная стремится к хаосу. Твой код — часть вселенной.",
        "Баги не исчезают. Они мигрируют.",
        "Понедельник — это пятница в параллельной вселенной.",
        "Кто понял жизнь, тот не спешит.",
        "Иногда тишина — лучший ответ. Особенно в чате в 3 ночи.",
        "Всё временно. Кроме временных решений.",
        "Если что-то выглядит глупо, но работает — это не глупо. Это legacy.",
    ],
    "oleg_style": [
        "Хуй с ним, работает и ладно.",
        "Не баг, а неожиданное поведение.",
        "Сегодня я добрый. Завтра — посмотрим.",
        "Если ты это читаешь — значит ещё не всё потеряно.",
        "Главное — не паниковать. Ну, или паниковать эффективно.",
        "Было сложно, стало просто. Шучу, всё ещё сложно.",
        "Ты справишься. Или нет. Но попробовать стоит.",
        "Жизнь коротка. Пиши понятный код.",
        "Отдыхай, пока можешь. Дедлайны вечны.",
    ],
}

# Flattened list for backward compatibility
DEFAULT_WISDOM_QUOTES = [
    quote for quotes in QUOTE_CATEGORIES.values() for quote in quotes
]


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class DailiesConfig:
    """
    Configuration for daily messages per chat.
    
    Attributes:
        chat_id: Telegram chat ID
        summary_enabled: Whether morning summary is enabled
        quote_enabled: Whether evening quote is enabled
        stats_enabled: Whether evening stats are enabled
        summary_time_hour: Hour for summary (Moscow time)
        quote_time_hour: Hour for quote/stats (Moscow time)
    """
    chat_id: int
    summary_enabled: bool = True
    quote_enabled: bool = True
    stats_enabled: bool = True
    summary_time_hour: int = 20  # 20:00 Moscow (evening summary)
    quote_time_hour: int = 21   # 21:00 Moscow (Requirement 13.2, 13.3)


@dataclass
class DailySummary:
    """
    Daily summary data structure.
    
    Attributes:
        chat_id: Telegram chat ID
        date: Date of the summary
        message_count: Total messages yesterday
        active_users: Number of active users
        new_members: Number of new members
        moderation_actions: Count of moderation actions
        top_messages: List of top messages (by reactions)
        has_activity: Whether there was any activity
        toxicity_score: Average toxicity score (0-100)
        toxicity_incidents: Number of toxicity incidents
        hot_topics: List of hot topics with message links
        peak_hour: Hour with most activity
        top_chatters: List of most active users
        # Enhanced fields
        llm_summary: LLM-generated summary of discussions
        mood_score: Overall chat mood (0-100, 50=neutral)
        mood_label: Mood description
        interesting_quotes: Notable/funny messages
        activity_change: Percentage change vs previous day
        prev_message_count: Previous day message count for comparison
    """
    chat_id: int
    date: datetime
    message_count: int = 0
    active_users: int = 0
    new_members: int = 0
    moderation_actions: int = 0
    top_messages: List[Dict[str, Any]] = field(default_factory=list)
    has_activity: bool = False
    # Toxicity & topics
    toxicity_score: float = 0.0
    toxicity_incidents: int = 0
    hot_topics: List[Dict[str, Any]] = field(default_factory=list)
    peak_hour: Optional[int] = None
    top_chatters: List[Dict[str, Any]] = field(default_factory=list)
    # Enhanced fields
    llm_summary: Optional[str] = None
    mood_score: float = 50.0
    mood_label: str = "Нейтрально"
    interesting_quotes: List[Dict[str, Any]] = field(default_factory=list)
    activity_change: Optional[float] = None
    prev_message_count: int = 0


@dataclass
class DailyQuote:
    """
    Daily quote data structure.
    
    Attributes:
        text: Quote text
        author: Quote author (if from Golden Fund)
        is_from_golden_fund: Whether quote is from Golden Fund
        sticker_file_id: Sticker file ID if available
    """
    text: str
    author: Optional[str] = None
    is_from_golden_fund: bool = False
    sticker_file_id: Optional[str] = None


@dataclass
class DailyStats:
    """
    Daily game statistics data structure.
    
    Attributes:
        chat_id: Telegram chat ID
        date: Date of the stats
        top_growers: List of top growers (username, growth)
        top_losers: List of top losers (username, loss)
        tournament_standings: Current tournament standings
        chart_data: PNG chart data
    """
    chat_id: int
    date: datetime
    top_growers: List[Dict[str, Any]] = field(default_factory=list)
    top_losers: List[Dict[str, Any]] = field(default_factory=list)
    tournament_standings: List[Dict[str, Any]] = field(default_factory=list)
    chart_data: Optional[bytes] = None


# ============================================================================
# Dailies Service
# ============================================================================

class DailiesService:
    """
    Service for managing daily scheduled messages.
    
    Features:
    - Morning summary at 09:00 Moscow (Requirement 13.1)
    - Evening quote at 21:00 Moscow (Requirement 13.2)
    - Evening stats at 21:00 Moscow (Requirement 13.3)
    - Chat-specific settings (Requirement 13.4)
    - Skip summary on no activity (Requirement 13.5)
    
    Properties:
    - Property 33: Daily message respect settings
    - Property 34: Skip summary on no activity
    """
    
    def __init__(self):
        """Initialize DailiesService."""
        self._golden_fund_service = None
    
    @property
    def golden_fund_service(self):
        """Lazy load golden fund service to avoid circular imports."""
        if self._golden_fund_service is None:
            try:
                from app.services.golden_fund import golden_fund_service
                self._golden_fund_service = golden_fund_service
            except Exception as e:
                logger.warning(f"Failed to load golden fund service: {e}")
        return self._golden_fund_service
    
    # =========================================================================
    # Configuration Methods
    # =========================================================================
    
    async def get_config(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> DailiesConfig:
        """
        Get dailies configuration for a chat.
        
        Property 33: Daily message respect settings
        *For any* chat with specific daily message types disabled,
        those messages SHALL NOT be sent.
        
        Requirement 13.4: WHEN sending daily messages THEN the Dailies
        System SHALL respect chat-specific settings for enabled/disabled
        daily messages.
        
        Args:
            chat_id: Telegram chat ID
            session: Optional database session
            
        Returns:
            DailiesConfig for the chat
        """
        from app.database.models import DailiesConfig as DailiesConfigModel
        from app.database.session import get_session
        
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            # Get dailies config from database
            result = await session.execute(
                select(DailiesConfigModel).filter_by(chat_id=chat_id)
            )
            db_config = result.scalar_one_or_none()
            
            if db_config is None:
                # Return default config for chats without explicit settings
                return DailiesConfig(chat_id=chat_id)
            
            # Map database model to dataclass
            return DailiesConfig(
                chat_id=chat_id,
                summary_enabled=db_config.summary_enabled,
                quote_enabled=db_config.quote_enabled,
                stats_enabled=db_config.stats_enabled,
                summary_time_hour=db_config.summary_time_hour,
                quote_time_hour=db_config.quote_time_hour,
            )
            
        except Exception as e:
            logger.warning(f"Failed to get dailies config for chat {chat_id}: {e}")
            # Return default config on error
            return DailiesConfig(chat_id=chat_id)
            
        finally:
            if close_session:
                await session.close()
    
    async def update_config(
        self,
        chat_id: int,
        summary_enabled: Optional[bool] = None,
        quote_enabled: Optional[bool] = None,
        stats_enabled: Optional[bool] = None,
        session: Optional[AsyncSession] = None
    ) -> DailiesConfig:
        """
        Update dailies configuration for a chat.
        
        Requirement 13.4: Respect chat-specific settings for enabled/disabled
        daily messages.
        
        Args:
            chat_id: Telegram chat ID
            summary_enabled: Enable/disable morning summary
            quote_enabled: Enable/disable evening quote
            stats_enabled: Enable/disable evening stats
            session: Optional database session
            
        Returns:
            Updated DailiesConfig
        """
        from app.database.models import DailiesConfig as DailiesConfigModel
        from app.database.session import get_session
        
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            # Get or create config
            result = await session.execute(
                select(DailiesConfigModel).filter_by(chat_id=chat_id)
            )
            db_config = result.scalar_one_or_none()
            
            if db_config is None:
                # Create new config
                db_config = DailiesConfigModel(chat_id=chat_id)
                session.add(db_config)
            
            # Update fields if provided
            if summary_enabled is not None:
                db_config.summary_enabled = summary_enabled
            if quote_enabled is not None:
                db_config.quote_enabled = quote_enabled
            if stats_enabled is not None:
                db_config.stats_enabled = stats_enabled
            
            await session.commit()
            
            # Return updated config as dataclass
            return DailiesConfig(
                chat_id=chat_id,
                summary_enabled=db_config.summary_enabled,
                quote_enabled=db_config.quote_enabled,
                stats_enabled=db_config.stats_enabled,
                summary_time_hour=db_config.summary_time_hour,
                quote_time_hour=db_config.quote_time_hour,
            )
            
        except Exception as e:
            logger.error(f"Failed to update dailies config for chat {chat_id}: {e}")
            if session:
                await session.rollback()
            # Return current config on error
            return await self.get_config(chat_id, session)
            
        finally:
            if close_session:
                await session.close()
    
    def should_send_message(
        self,
        config: DailiesConfig,
        message_type: str
    ) -> bool:
        """
        Check if a specific daily message type should be sent.
        
        Property 33: Daily message respect settings
        *For any* chat with specific daily message types disabled,
        those messages SHALL NOT be sent.
        
        Args:
            config: Chat's dailies configuration
            message_type: Type of message ('summary', 'quote', 'stats')
            
        Returns:
            True if message should be sent, False otherwise
        """
        if message_type == 'summary':
            return config.summary_enabled
        elif message_type == 'quote':
            return config.quote_enabled
        elif message_type == 'stats':
            return config.stats_enabled
        return False
    
    # =========================================================================
    # Summary Generation (Requirement 13.1)
    # =========================================================================
    
    async def generate_summary(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None,
        for_today: bool = True
    ) -> Optional[DailySummary]:
        """
        Generate daily summary for a chat.
        
        Args:
            chat_id: Telegram chat ID
            session: Optional database session
            for_today: If True, summarizes today so far. If False, summarizes yesterday.
            
        Returns:
            DailySummary if there was activity, None otherwise
        """
        from app.database.models import MessageLog, User
        from app.database.session import get_session
        from app.utils import utc_now
        
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            now = utc_now()
            if for_today:
                # Today so far (from 00:00 UTC)
                start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = now
            else:
                # Full yesterday
                start_time = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Count messages
            message_count_result = await session.execute(
                select(func.count(MessageLog.id)).filter(
                    MessageLog.chat_id == chat_id,
                    MessageLog.created_at >= start_time,
                    MessageLog.created_at < end_time
                )
            )
            message_count = message_count_result.scalar() or 0
            
            # Property 34: Skip if no activity
            if message_count < MIN_ACTIVITY_FOR_SUMMARY:
                logger.debug(f"Skipping summary for chat {chat_id}: no activity")
                return DailySummary(
                    chat_id=chat_id,
                    date=start_time,
                    message_count=0,
                    has_activity=False
                )
            
            # Count active users
            active_users_result = await session.execute(
                select(func.count(func.distinct(MessageLog.user_id))).filter(
                    MessageLog.chat_id == chat_id,
                    MessageLog.created_at >= start_time,
                    MessageLog.created_at < end_time
                )
            )
            active_users = active_users_result.scalar() or 0
            
            # Count new members (users created in range)
            new_members_result = await session.execute(
                select(func.count(User.id)).filter(
                    User.created_at >= start_time,
                    User.created_at < end_time
                )
            )
            new_members = new_members_result.scalar() or 0
            
            moderation_actions = 0
            
            # Toxicity & incidents
            toxicity_score, toxicity_incidents = await self._calculate_toxicity_from_messages(
                chat_id, start_time, end_time, session
            )
            
            # Peak activity hour
            peak_hour_result = await session.execute(
                select(
                    extract('hour', MessageLog.created_at).label('hour'),
                    func.count(MessageLog.id).label('cnt')
                ).filter(
                    MessageLog.chat_id == chat_id,
                    MessageLog.created_at >= start_time,
                    MessageLog.created_at < end_time
                ).group_by(
                    extract('hour', MessageLog.created_at)
                ).order_by(
                    desc('cnt')
                ).limit(1)
            )
            peak_row = peak_hour_result.first()
            peak_hour = int(peak_row[0]) if peak_row else None
            
            # Top chatters
            top_chatters_result = await session.execute(
                select(
                    MessageLog.username,
                    MessageLog.user_id,
                    func.count(MessageLog.id).label('msg_count')
                ).filter(
                    MessageLog.chat_id == chat_id,
                    MessageLog.created_at >= start_time,
                    MessageLog.created_at < end_time
                ).group_by(
                    MessageLog.user_id, MessageLog.username
                ).order_by(
                    desc('msg_count')
                ).limit(5)
            )
            top_chatters = [
                {
                    "username": row.username or f"User {row.user_id}",
                    "user_id": row.user_id,
                    "count": row.msg_count
                }
                for row in top_chatters_result.all()
            ]
            
            # Hot topics
            hot_topics = await self._extract_hot_topics(
                chat_id, start_time, end_time, session
            )
            
            # Activity comparison with previous period
            prev_start = start_time - (end_time - start_time)
            prev_count_result = await session.execute(
                select(func.count(MessageLog.id)).filter(
                    MessageLog.chat_id == chat_id,
                    MessageLog.created_at >= prev_start,
                    MessageLog.created_at < start_time
                )
            )
            prev_message_count = prev_count_result.scalar() or 0
            
            activity_change = None
            if prev_message_count > 0:
                activity_change = ((message_count - prev_message_count) / prev_message_count) * 100
            
            # Interesting quotes
            interesting_quotes = await self._extract_interesting_quotes(
                chat_id, start_time, end_time, session
            )
            
            # Mood analysis
            mood_score, mood_label = await self._analyze_chat_mood(
                chat_id, start_time, end_time, session, toxicity_score
            )
            
            # LLM Summary
            llm_summary = await self._generate_llm_summary(
                chat_id, start_time, end_time, session,
                message_count, hot_topics, top_chatters
            )
            
            return DailySummary(
                chat_id=chat_id,
                date=start_time,
                message_count=message_count,
                active_users=active_users,
                new_members=new_members,
                moderation_actions=moderation_actions,
                has_activity=True,
                toxicity_score=toxicity_score,
                toxicity_incidents=toxicity_incidents,
                hot_topics=hot_topics,
                peak_hour=peak_hour,
                top_chatters=top_chatters,
                llm_summary=llm_summary,
                mood_score=mood_score,
                mood_label=mood_label,
                interesting_quotes=interesting_quotes,
                activity_change=activity_change,
                prev_message_count=prev_message_count,
            )
            
        except Exception as e:
            logger.error(f"Failed to generate summary for chat {chat_id}: {e}")
            return None
            
        finally:
            if close_session:
                await session.close()
    
    async def _extract_hot_topics(
        self,
        chat_id: int,
        start_time: datetime,
        end_time: datetime,
        session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Extract hot topics from messages using LLM clustering.
        
        Uses LLM to identify and group discussion topics, then finds
        representative messages for each topic.
        
        Args:
            chat_id: Telegram chat ID
            start_time: Start of time range
            end_time: End of time range
            session: Database session
            
        Returns:
            List of hot topics with message links and counts
        """
        from app.database.models import MessageLog
        import re
        import json
        
        try:
            # Get messages with text
            messages_result = await session.execute(
                select(MessageLog).filter(
                    MessageLog.chat_id == chat_id,
                    MessageLog.created_at >= start_time,
                    MessageLog.created_at < end_time,
                    MessageLog.text.isnot(None)
                ).order_by(MessageLog.created_at.desc()).limit(500)
            )
            messages = messages_result.scalars().all()
            
            if not messages or len(messages) < 10:
                return []
            
            # Prepare messages sample for LLM
            messages_sample = []
            for msg in messages[:200]:
                if msg.text and len(msg.text) > 5:
                    messages_sample.append({
                        "id": msg.message_id,
                        "text": msg.text[:200],
                        "user": msg.username or "user"
                    })
            
            if len(messages_sample) < 10:
                return []
            
            # Use LLM to extract topics
            try:
                from app.services.ollama_client import _ollama_chat
                
                sample_text = "\n".join([
                    f"[{m['id']}] {m['user']}: {m['text']}" 
                    for m in messages_sample[:100]
                ])
                
                prompt = f"""Проанализируй сообщения чата и выдели 5-8 основных тем обсуждения.

Сообщения:
{sample_text}

Для каждой темы укажи:
1. Краткое название темы (2-4 слова) с эмодзи
2. Примерное количество сообщений по теме
3. ID одного характерного сообщения из списка

Ответь СТРОГО в JSON формате:
[
  {{"topic": "😂 Смешные моменты", "count": 45, "msg_id": 12345}},
  {{"topic": "🔧 Технические проблемы", "count": 30, "msg_id": 12346}}
]

Только JSON, без пояснений!"""

                llm_messages = [
                    {"role": "system", "content": "Ты анализируешь чаты и выделяешь темы. Отвечай только JSON."},
                    {"role": "user", "content": prompt}
                ]
                
                response = await _ollama_chat(llm_messages, temperature=0.3)
                
                # Parse JSON response
                # Try to extract JSON from response
                json_match = re.search(r'\[.*\]', response, re.DOTALL)
                if json_match:
                    topics_data = json.loads(json_match.group())
                else:
                    topics_data = json.loads(response)
                
                hot_topics = []
                for item in topics_data[:8]:
                    topic_text = item.get("topic", "Тема")
                    msg_id = item.get("msg_id")
                    
                    # Verify if msg_id exists in our sample, if not/missing, try to find a relevant message
                    if not msg_id or not any(m.message_id == msg_id for m in messages):
                        # Try to find a message containing part of the topic keywords
                        # Split topic into words and find a message containing them
                        topic_words = [w.lower() for w in re.findall(r'\w+', topic_text) if len(w) > 3]
                        found_msg = None
                        
                        if topic_words:
                            for msg in messages:
                                if not msg.text: continue
                                text_lower = msg.text.lower()
                                # If any significant word from topic is in message
                                if any(w in text_lower for w in topic_words):
                                    found_msg = msg
                                    break
                        
                        if found_msg:
                            msg_id = found_msg.message_id
                        elif messages:
                            # Fallback to random message from sample if we can't match
                            # Better than no link? Maybe not. Let's leave it None if we can't match.
                            pass

                    topic = {
                        "keyword": topic_text,
                        "mentions": item.get("count", 10),
                        "message_id": msg_id,
                        "chat_id": chat_id
                    }
                    hot_topics.append(topic)
                
                return hot_topics
                
            except Exception as llm_error:
                logger.debug(f"LLM topic extraction failed: {llm_error}, falling back to keywords")
                # Fallback to keyword extraction
                return await self._extract_hot_topics_fallback(messages, chat_id)
            
        except Exception as e:
            logger.warning(f"Failed to extract hot topics: {e}")
            return []
    
    async def _extract_hot_topics_fallback(
        self,
        messages: List,
        chat_id: int
    ) -> List[Dict[str, Any]]:
        """Fallback keyword-based topic extraction."""
        from collections import Counter
        import re
        
        stop_words = {
            'это', 'как', 'что', 'для', 'все', 'они', 'его', 'она', 'так',
            'уже', 'или', 'если', 'есть', 'было', 'быть', 'был', 'была',
            'были', 'будет', 'будут', 'очень', 'просто', 'можно', 'нужно',
            'там', 'тут', 'здесь', 'когда', 'потом', 'тоже', 'только',
            'ещё', 'еще', 'вот', 'чтобы', 'этот', 'этого', 'этом', 'этой',
            'надо', 'меня', 'тебя', 'нахуй', 'сука', 'блять', 'хуй',
        }
        
        word_messages = {}
        word_counts = Counter()
        
        for msg in messages:
            if not msg.text:
                continue
            words = re.findall(r'[а-яёa-z]{4,}', msg.text.lower())
            seen = set()
            for word in words:
                if word not in stop_words and word not in seen:
                    seen.add(word)
                    word_counts[word] += 1
                    if word not in word_messages:
                        word_messages[word] = msg
        
        hot_topics = []
        for word, count in word_counts.most_common(5):
            if count < 5:
                continue
            msg = word_messages.get(word)
            hot_topics.append({
                "keyword": word.capitalize(),
                "mentions": count,
                "message_id": msg.message_id if msg else None,
                "chat_id": chat_id
            })
        
        return hot_topics
    
    async def _extract_interesting_quotes(
        self,
        chat_id: int,
        start_time: datetime,
        end_time: datetime,
        session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Extract interesting/funny messages from the day.
        
        Looks for messages with certain patterns that indicate humor or interest.
        """
        from app.database.models import MessageLog
        
        try:
            # Get messages with text
            messages_result = await session.execute(
                select(MessageLog).filter(
                    MessageLog.chat_id == chat_id,
                    MessageLog.created_at >= start_time,
                    MessageLog.created_at < end_time,
                    MessageLog.text.isnot(None)
                ).order_by(MessageLog.created_at.desc()).limit(300)
            )
            messages = messages_result.scalars().all()
            
            if not messages:
                return []
            
            interesting = []
            
            for msg in messages:
                if not msg.text or len(msg.text) < 15 or len(msg.text) > 200:
                    continue
                
                text_lower = msg.text.lower()
                score = 0
                
                # Humor indicators
                if any(x in text_lower for x in ['😂', '🤣', 'хахах', 'лол', 'ахах', 'ржу']):
                    score += 2
                if any(x in text_lower for x in ['блять', 'пиздец', 'ебать', 'охуе']):
                    score += 1  # Expressive
                if '?' in msg.text and '!' in msg.text:
                    score += 1  # Emotional
                if msg.text.count('!') >= 2:
                    score += 1
                # Avoid boring messages
                if any(x in text_lower for x in ['привет', 'пока', 'спасибо', 'ок', 'да', 'нет']):
                    score -= 2
                if len(msg.text) < 30:
                    score -= 1
                
                if score >= 2:
                    interesting.append({
                        "text": msg.text[:150] + ("..." if len(msg.text) > 150 else ""),
                        "username": msg.username or f"User {msg.user_id}",
                        "message_id": msg.message_id,
                        "score": score
                    })
            
            # Sort by score and take top 3
            interesting.sort(key=lambda x: x["score"], reverse=True)
            return interesting[:3]
            
        except Exception as e:
            logger.warning(f"Failed to extract interesting quotes: {e}")
            return []
    
    async def _calculate_toxicity_from_messages(
        self,
        chat_id: int,
        start_time: datetime,
        end_time: datetime,
        session: AsyncSession
    ) -> tuple[float, int]:
        """
        Calculate toxicity score from message content as fallback.
        
        Returns:
            (toxicity_score 0-100, incident_count)
        """
        from app.database.models import MessageLog
        import re
        
        try:
            messages_result = await session.execute(
                select(MessageLog.text).filter(
                    MessageLog.chat_id == chat_id,
                    MessageLog.created_at >= start_time,
                    MessageLog.created_at < end_time,
                    MessageLog.text.isnot(None)
                ).limit(500)
            )
            texts = [row[0] for row in messages_result.all() if row[0]]
            
            if not texts:
                return 0.0, 0
            
            # Toxic patterns (Russian mat and aggressive words)
            toxic_patterns = [
                r'\b[хx][уy][йиеяюёijey]\w*',
                r'\b[пp][иiе][зz][дd]\w*',
                r'\b[бb][лl][яa]\w*',
                r'\b[еe][бb]\w*',
                r'\b[сc][уy][кk]\w*',
                r'\b[мm][уy][дd][аa]\w*',
                r'\bf+u+c+k+\w*',
                r'\bs+h+i+t+\w*',
                r'\b(убью|сдохни|урод|дебил|идиот|кретин|даун|лох)\b',
            ]
            
            toxic_count = 0
            incident_messages = 0
            
            for text in texts:
                text_lower = text.lower()
                is_toxic = False
                for pattern in toxic_patterns:
                    if re.search(pattern, text_lower, re.IGNORECASE):
                        toxic_count += 1
                        is_toxic = True
                        break
                if is_toxic:
                    incident_messages += 1
            
            # Calculate score (0-100)
            total = len(texts)
            toxicity_ratio = toxic_count / total if total > 0 else 0
            toxicity_score = min(100, toxicity_ratio * 100)
            
            return toxicity_score, incident_messages
            
        except Exception as e:
            logger.warning(f"Failed to calculate toxicity from messages: {e}")
            return 0.0, 0

    async def _analyze_chat_mood(
        self,
        chat_id: int,
        start_time: datetime,
        end_time: datetime,
        session: AsyncSession,
        toxicity_score: float
    ) -> tuple[float, str]:
        """
        Analyze overall chat mood based on message patterns.
        
        Returns:
            (mood_score, mood_label) where score is 0-100 (50=neutral)
        """
        from app.database.models import MessageLog
        
        try:
            messages_result = await session.execute(
                select(MessageLog.text).filter(
                    MessageLog.chat_id == chat_id,
                    MessageLog.created_at >= start_time,
                    MessageLog.created_at < end_time,
                    MessageLog.text.isnot(None)
                ).limit(200)
            )
            texts = [row[0] for row in messages_result.all() if row[0]]
            
            if not texts:
                return 50.0, "Нейтрально"
            
            positive_count = 0
            negative_count = 0
            
            positive_markers = ['😊', '😄', '🥰', '❤️', '👍', '🎉', '😁', 'круто', 'класс', 
                              'отлично', 'супер', 'спасибо', 'молодец', 'красава', 'топ']
            negative_markers = ['😢', '😭', '😤', '😡', '👎', '💔', 'плохо', 'ужас', 
                              'отстой', 'хуйня', 'пиздец', 'блять', 'дерьмо']
            
            for text in texts:
                text_lower = text.lower()
                if any(m in text_lower for m in positive_markers):
                    positive_count += 1
                if any(m in text_lower for m in negative_markers):
                    negative_count += 1
            
            total = len(texts)
            positive_ratio = positive_count / total if total > 0 else 0
            negative_ratio = negative_count / total if total > 0 else 0
            
            # Calculate mood score (0-100, 50 is neutral)
            # Toxicity also affects mood negatively
            base_mood = 50 + (positive_ratio * 40) - (negative_ratio * 30) - (toxicity_score * 0.2)
            mood_score = max(0, min(100, base_mood))
            
            # Determine label
            if mood_score >= 75:
                mood_label = "Райский сад 🌸"
            elif mood_score >= 60:
                mood_label = "Лампово 🍺"
            elif mood_score >= 45:
                mood_label = "Стабильное болото 🐸"
            elif mood_score >= 30:
                mood_label = "Духота 📉"
            else:
                mood_label = "Токсичный полигон ☢️"
            
            return mood_score, mood_label
            
        except Exception as e:
            logger.warning(f"Failed to analyze mood: {e}")
            return 50.0, "Нейтрально"
    
    async def _generate_llm_summary(
        self,
        chat_id: int,
        start_time: datetime,
        end_time: datetime,
        session: AsyncSession,
        message_count: int,
        hot_topics: List[Dict[str, Any]],
        top_chatters: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Generate LLM-based summary of chat discussions.
        """
        from app.database.models import MessageLog
        
        try:
            # Get sample of messages for context
            messages_result = await session.execute(
                select(MessageLog.text, MessageLog.username).filter(
                    MessageLog.chat_id == chat_id,
                    MessageLog.created_at >= start_time,
                    MessageLog.created_at < end_time,
                    MessageLog.text.isnot(None)
                ).order_by(func.random()).limit(100)
            )
            messages = messages_result.all()
            
            if len(messages) < 5:
                return None
            
            # Build context
            topics_str = ", ".join([t["keyword"] for t in hot_topics[:5]]) if hot_topics else "разное"
            chatters_str = ", ".join([c["username"] for c in top_chatters[:3]]) if top_chatters else "участники"
            
            sample_texts = [f"{m.username}: {m.text[:150]}" for m in messages[:40] if m.text]
            messages_sample = "\n".join(sample_texts)
            
            from app.services.ollama_client import _ollama_chat
            
            prompt = f"""Сделай краткий и дерзкий пересказ обсуждений в чате за сегодня.

СТАТИСТИКА:
- Сообщений: {message_count}
- Главные темы: {topics_str}
- Топ болтунов: {chatters_str}

СООБЩЕНИЯ ДЛЯ АНАЛИЗА:
{messages_sample}

ТРЕБОВАНИЯ:
- Максимум 2-4 предложения
- Стиль Олега: ироничный, шарящий в ИТ, немного циничный, но свой в доску
- Никаких "сегодня участники обсуждали" — пиши сразу суть
- Можно использовать сленг (тачка, затык, база, соя, челик)
- Если обсуждали пиво, железо или Чехию — обязательно упомяни в своём стиле

Ответь ТОЛЬКО пересказом, без вступлений и кавычек."""

            messages_for_llm = [
                {"role": "system", "content": "Ты Олег — дерзкий ИТ-эксперт. Делаешь краткие и едкие пересказы чатов. Твой юмор — база."},
                {"role": "user", "content": prompt}
            ]
            
            summary = await _ollama_chat(messages_for_llm, temperature=0.8)
            
            # Clean and validate
            summary = summary.strip().strip('"')
            if len(summary) < 15 or len(summary) > 500:
                return None
            
            return summary
            
        except Exception as e:
            logger.debug(f"Failed to generate LLM summary: {e}")
            return None
    
    def _get_toxicity_emoji(self, score: float) -> str:
        """Get toxicity thermometer emoji based on score."""
        if score < 20:
            return "🟢"  # Green - very chill
        elif score < 40:
            return "🟡"  # Yellow - mild
        elif score < 60:
            return "🟠"  # Orange - warming up
        elif score < 80:
            return "🔴"  # Red - hot
        else:
            return "🔥"  # Fire - toxic
    
    def _get_toxicity_label(self, score: float) -> str:
        """Get toxicity label based on score."""
        if score < 20:
            return "Чилл 😎"
        elif score < 40:
            return "Спокойно"
        elif score < 60:
            return "Бурно"
        elif score < 80:
            return "Горячо 🌶️"
        else:
            return "Токсично ☢️"
    
    def should_skip_summary(self, summary: Optional[DailySummary]) -> bool:
        """
        Check if summary should be skipped due to no activity.
        
        Property 34: Skip summary on no activity
        *For any* chat with zero messages in the past 24 hours,
        the daily summary SHALL be skipped.
        
        Args:
            summary: Generated summary or None
            
        Returns:
            True if summary should be skipped, False otherwise
        """
        if summary is None:
            return True
        return not summary.has_activity
    
    def format_morning_summary(self, summary: DailySummary) -> str:
        """
        Format morning summary (yesterday's recap).
        
        Distinct style from evening summary to avoid repetition.
        Focuses on "Briefing" style.
        """
        date_str = summary.date.strftime("%d.%m")
        
        lines = [
            f"☕️ #morningbriefing за {date_str}",
            "",
        ]
        
        # LLM Summary (shorter intro)
        if summary.llm_summary:
            lines.append(f"{summary.llm_summary}")
            lines.append("")
        
        lines.append("📉 ИТОГИ ВЧЕРА:")
        lines.append(f"• Сообщений: {summary.message_count}")
        lines.append(f"• Актив: {summary.active_users} чел.")
        
        if summary.new_members > 0:
            lines.append(f"• Новых: +{summary.new_members}")
            
        # Highlight top discussion only
        if summary.hot_topics:
            top_topic = summary.hot_topics[0]
            keyword = top_topic['keyword']
            msg_id = top_topic.get('message_id')
            
            lines.append("")
            lines.append("🔥 ГЛАВНАЯ ТЕМА:")
            if msg_id and summary.chat_id:
                chat_id_str = str(abs(summary.chat_id))
                if chat_id_str.startswith("100"):
                    chat_id_str = chat_id_str[3:]
                link = f"https://t.me/c/{chat_id_str}/{msg_id}"
                lines.append(f'👉 <a href="{link}">{keyword}</a>')
            else:
                lines.append(f"👉 {keyword}")

        # Mood (simple emoji)
        lines.append("")
        lines.append(f"Вайб вчерашнего дня: {summary.mood_label}")
        
        lines.append("")
        lines.append("Всем продуктивного дня! 🚀")
        
        return "\n".join(lines)

    def format_summary(self, summary: DailySummary) -> str:
        """
        Format daily summary for display.
        
        Enhanced evening summary with LLM insights, mood, quotes, and comparisons.
        """
        date_str = summary.date.strftime("%d.%m.%Y")
        
        lines = [
            f"🌆 #dailysummary за {date_str}",
            "",
        ]
        
        # LLM Summary at the top (if available)
        if summary.llm_summary:
            lines.append(f"📝 {summary.llm_summary}")
            lines.append("")
        
        # Stats with comparison
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("📈 ЦИФРЫ ДНЯ")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        
        # Message count with trend
        trend = ""
        if summary.activity_change is not None:
            if summary.activity_change > 10:
                trend = f" 📈 +{summary.activity_change:.0f}%"
            elif summary.activity_change < -10:
                trend = f" 📉 {summary.activity_change:.0f}%"
            elif summary.activity_change != 0:
                trend = f" → {summary.activity_change:+.0f}%"
        
        lines.append(f"💬 Сообщений: {summary.message_count}{trend}")
        lines.append(f"👥 Активных: {summary.active_users}")
        
        if summary.peak_hour is not None:
            lines.append(f"⏰ Пик: {summary.peak_hour}:00")
        
        if summary.new_members > 0:
            lines.append(f"🆕 Новичков: {summary.new_members}")
        
        # Mood & Toxicity combined
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🎭 ВАЙБ ЧАТА")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        
        # Mood bar
        mood_filled = int(summary.mood_score / 10)
        mood_bar = "█" * mood_filled + "░" * (10 - mood_filled)
        lines.append(f"😊 [{mood_bar}] {summary.mood_label}")
        
        # Toxicity (compact)
        toxicity_emoji = self._get_toxicity_emoji(summary.toxicity_score)
        toxicity_label = self._get_toxicity_label(summary.toxicity_score)
        # Remove percentage and "Incidents" to avoid confusion
        lines.append(f"{toxicity_emoji} Токсичность: {toxicity_label}")
        
        # Top chatters (compact)
        if summary.top_chatters:
            lines.append("")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("🏆 БОЛТУНЫ ДНЯ")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            medals = ["🥇", "🥈", "🥉"]
            for i, chatter in enumerate(summary.top_chatters[:3]):
                medal = medals[i] if i < len(medals) else f"{i+1}."
                lines.append(f"{medal} {chatter['username']} — {chatter['count']}")
        
        # Hot topics with links
        if summary.hot_topics:
            lines.append("")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("🔥 ОБСУЖДАЛИ")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            for topic in summary.hot_topics[:5]:
                keyword = topic['keyword']
                mentions = topic['mentions']
                msg_id = topic.get('message_id')
                
                if msg_id and summary.chat_id:
                    chat_id_str = str(abs(summary.chat_id))
                    if chat_id_str.startswith("100"):
                        chat_id_str = chat_id_str[3:]
                    link = f"https://t.me/c/{chat_id_str}/{msg_id}"
                    lines.append(f'• <a href="{link}">{keyword}</a> ({mentions})')
                else:
                    lines.append(f"• {keyword} ({mentions})")
        
        # Footer
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(self._get_summary_footer())
        
        return "\n".join(lines)
    
    def _get_summary_footer(self) -> str:
        """Get contextual footer for summary."""
        footers = [
            "Хорошего вечера! 🌙",
            "Отдыхайте! 😴",
            "До завтра! 👋",
            "Спокойной ночи! 🌃",
            "Завтра новый день! ✨",
        ]
        return random.choice(footers)
    
    # =========================================================================
    # Quote Selection (Requirement 13.2)
    # =========================================================================
    
    async def select_daily_quote(
        self,
        chat_id: Optional[int] = None,
        session: Optional[AsyncSession] = None
    ) -> DailyQuote:
        """
        Select a daily quote (from Golden Fund or LLM-generated).
        """
        roll = random.random()
        
        # 30% chance: Try Golden Fund first
        if roll < 0.3 and self.golden_fund_service:
            try:
                golden_quote = await self.golden_fund_service.get_random_golden_quote(
                    chat_id=chat_id
                )
                
                if golden_quote:
                    return DailyQuote(
                        text=golden_quote.text,
                        author=golden_quote.username,
                        is_from_golden_fund=True,
                        sticker_file_id=golden_quote.sticker_file_id
                    )
            except Exception as e:
                logger.warning(f"Failed to get golden quote: {e}")
        
        # Get active names and persona for personalization
        active_names = []
        persona = "oleg"
        
        if chat_id:
            try:
                from app.services.ollama_client import recent_active_usernames
                active_names = await recent_active_usernames(chat_id, hours=24, limit=10)
                
                # Fetch persona from BotConfig
                from app.database.models import BotConfig
                from sqlalchemy import select
                
                close_session = False
                if session is None:
                    from app.database.session import get_session
                    async_session = get_session()
                    session = async_session()
                    close_session = True
                
                result = await session.execute(
                    select(BotConfig.persona).filter_by(chat_id=chat_id)
                )
                db_persona = result.scalar_one_or_none()
                if db_persona:
                    persona = db_persona
                
                if close_session:
                    await session.close()
            except Exception as e:
                logger.warning(f"Failed to fetch context for quote: {e}")

        # 70% chance: Generate unique quote via LLM
        llm_quote = await self._generate_llm_quote(active_names, persona)
        if llm_quote:
            return DailyQuote(
                text=llm_quote,
                author="Олег",
                is_from_golden_fund=False,
                sticker_file_id=None
            )
        
        # Fallback: Pick from categorized quotes
        return self._select_category_quote()
    
    def _select_category_quote(self) -> DailyQuote:
        """
        Select a quote from predefined categories based on day/mood.
        
        Uses day of week to vary categories:
        - Monday: motivation
        - Tuesday: it_wisdom  
        - Wednesday: philosophy
        - Thursday: life
        - Friday: oleg_style
        - Saturday: absurd
        - Sunday: random category
        """
        from datetime import datetime
        
        day_categories = {
            0: "motivation",    # Monday - need motivation
            1: "it_wisdom",     # Tuesday - tech day
            2: "philosophy",    # Wednesday - mid-week thoughts
            3: "life",          # Thursday - life wisdom
            4: "oleg_style",    # Friday - Oleg mode
            5: "absurd",        # Saturday - weird stuff
            6: None,            # Sunday - random
        }
        
        weekday = datetime.now().weekday()
        category = day_categories.get(weekday)
        
        if category and category in QUOTE_CATEGORIES:
            quotes = QUOTE_CATEGORIES[category]
        else:
            # Random category on Sunday or fallback
            category = random.choice(list(QUOTE_CATEGORIES.keys()))
            quotes = QUOTE_CATEGORIES[category]
        
        quote_text = random.choice(quotes)
        
        return DailyQuote(
            text=quote_text,
            author=None,
            is_from_golden_fund=False,
            sticker_file_id=None
        )
    
    async def _generate_llm_quote(self, active_names: List[str] = None, persona: str = "oleg") -> Optional[str]:
        """
        Generate a unique daily quote using LLM based on persona.
        
        Returns:
            Generated quote text or None if generation fails
        """
        try:
            from app.services.ollama_client import _ollama_chat, get_static_system_prompt
            from datetime import datetime
            
            # Context about active users
            users_context = ""
            if active_names:
                users_context = f"Активные участники чата: {', '.join(['@' + n for n in active_names])}."
            
            # Get persona-specific base instructions
            persona_base = get_static_system_prompt(persona)
            
            prompt = f"""Придумай одну мемную, абсурдную или ироничную 'цитату дня' для чата. 
{users_context}

ТРЕБОВАНИЯ:
- ТВОЙ СТИЛЬ: Используй характер и манеру речи выбранной личности (см. системные инструкции ниже).
- ТЕМА: Постирония, мемы, жизненный абсурд.
- Избегай скучной ИТ-тематики (баги, код, прод — это скучно), если только это не часть твоей личности.
- Можешь упомянуть кого-то из списка участников в смешном или странном контексте (но не обидно).
- Максимум 1-2 коротких предложения.
- Никакой мотивации и 'мудрости'. Только угар и база.

Ответь ТОЛЬКО фразой, без вступлений, кавычек и лишних слов."""

            messages = [
                {"role": "system", "content": persona_base},
                {"role": "system", "content": "Ты мастер постиронии и мемных цитат. Твои фразы заставляют чат орать или задумываться об абсурдности бытия."},
                {"role": "user", "content": prompt}
            ]
            
            quote = await _ollama_chat(messages, temperature=0.95)
            
            if not quote:
                return None
            
            # Clean up the quote
            quote = quote.strip().strip('"\'«»„"')
            
            # Remove common prefixes LLM might add
            bad_prefixes = ["цитата:", "мысль:", "фраза:", "ответ:", "—", "-"]
            for prefix in bad_prefixes:
                if quote.lower().startswith(prefix):
                    quote = quote[len(prefix):].strip()
            
            # Validate length
            if len(quote) < 10 or len(quote) > 300:
                return None
            
            return quote
            
        except Exception as e:
            logger.debug(f"Failed to generate LLM quote: {e}")
            return None
            if len(quote) < 10 or len(quote) > 300:
                return None
            
            return quote
            
        except Exception as e:
            logger.debug(f"Failed to generate LLM quote: {e}")
            return None
            
            quote = await _ollama_chat(messages, temperature=0.95)
            
            if not quote:
                return None
            
            # Clean up the quote
            quote = quote.strip().strip('"\'«»„"')
            
            # Remove common prefixes LLM might add
            bad_prefixes = ["цитата:", "мысль:", "фраза:", "ответ:", "—", "-"]
            for prefix in bad_prefixes:
                if quote.lower().startswith(prefix):
                    quote = quote[len(prefix):].strip()
            
            # Validate length
            if len(quote) < 10 or len(quote) > 250:
                return None
            
            return quote
            
        except Exception as e:
            logger.debug(f"Failed to generate LLM quote: {e}")
            return None
    
    def format_quote(self, quote: DailyQuote) -> str:
        """
        Format daily quote for display.
        
        Requirement 13.2: Send a #dailyquote message.
        """
        # Pick a random header emoji for variety
        header_emojis = ["💭", "🌙", "✨", "🔮", "💡", "🎯", "⚡"]
        header = random.choice(header_emojis)
        
        lines = [f"{header} #dailyquote", ""]
        
        if quote.is_from_golden_fund and quote.author:
            lines.append(f'«{quote.text}»')
            lines.append(f"— {quote.author}")
            lines.append("")
            lines.append("🏆 <b>Из Золотого Фонда</b>")
        elif quote.author == "Олег":
            # LLM-generated quote
            lines.append(f'«{quote.text}»')
            lines.append("")
            lines.append("🤖 <b>База от Олега</b>")
        else:
            lines.append(f'«{quote.text}»')
            # Add day-based footer
            lines.append("")
            lines.append(f"💡 {self._get_quote_footer()}")
        
        return "\n".join(lines)
    
    def _get_quote_footer(self) -> str:
        """Get a contextual footer based on day of week."""
        from datetime import datetime
        
        footers = {
            0: "Понедельник — день тяжёлый, но база вечна.",
            1: "Вторник — это как понедельник, только ты уже смирился.",
            2: "Среда — экватор абсурда пройден.",
            3: "Четверг — почти пятница, держись за мемы.",
            4: "Пятница! Деплоим и в бар! 🍻",
            5: "Суббота. Время чиллить и не думать.",
            6: "Воскресенье. Завтра опять этот цирк... 😅",
        }
        
        weekday = datetime.now().weekday()
        return footers.get(weekday, "Живи так, чтобы Олег гордился.")
    
    # =========================================================================
    # Stats Aggregation (Requirement 13.3)
    # =========================================================================
    
    async def aggregate_daily_stats(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> DailyStats:
        """
        Aggregate daily game statistics.
        
        Requirement 13.3: WHEN the time reaches 21:00 Moscow time
        THEN the Dailies System SHALL send a #dailystats message
        with game statistics.
        """
        from app.database.models import GameStat, User, GameHistory
        from app.database.session import get_session
        from app.utils import utc_now
        
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            now = utc_now()
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Get top growers (by size_cm) - get top 10 for the chart
            top_growers_result = await session.execute(
                select(GameStat)
                .order_by(GameStat.size_cm.desc())
                .limit(10)
            )
            top_growers_stats = top_growers_result.scalars().all()
            
            top_growers = [
                {
                    "username": gs.username or f"User {gs.tg_user_id}",
                    "size": gs.size_cm
                }
                for gs in top_growers_stats[:5]
            ]
            
            # Generate chart
            chart_data = None
            try:
                from app.services.top_chart import top_chart_generator
                chart_data = top_chart_generator.generate_top10_chart(top_growers_stats)
            except Exception as e:
                logger.warning(f"Failed to generate top chart: {e}")
            
            # ===== Game Stats =====
            # Big winners today
            winners_result = await session.execute(
                select(GameHistory.user_id, func.sum(GameHistory.result_amount).label('total_win'))
                .filter(GameHistory.played_at >= start_of_day, GameHistory.result_amount > 0)
                .group_by(GameHistory.user_id)
                .order_by(desc('total_win'))
                .limit(3)
            )
            big_winners = []
            for row in winners_result.all():
                user_res = await session.execute(select(User).filter(User.id == row.user_id))
                user = user_res.scalar()
                if user:
                    big_winners.append({
                        "username": user.username or user.first_name or f"ID:{user.tg_user_id}",
                        "amount": row.total_win
                    })
            
            # Most active gamblers
            gamblers_result = await session.execute(
                select(GameHistory.user_id, func.count(GameHistory.id).label('games_count'))
                .filter(GameHistory.played_at >= start_of_day)
                .group_by(GameHistory.user_id)
                .order_by(desc('games_count'))
                .limit(3)
            )
            top_gamblers = []
            for row in gamblers_result.all():
                user_res = await session.execute(select(User).filter(User.id == row.user_id))
                user = user_res.scalar()
                if user:
                    top_gamblers.append({
                        "username": user.username or user.first_name or f"ID:{user.tg_user_id}",
                        "count": row.games_count
                    })
            
            # Get top losers (lowest size_cm, but > 0)
            top_losers_result = await session.execute(
                select(GameStat)
                .filter(GameStat.size_cm > 0)
                .order_by(GameStat.size_cm.asc())
                .limit(3)
            )
            top_losers = [
                {
                    "username": gs.username or f"User {gs.tg_user_id}",
                    "size": gs.size_cm
                }
                for gs in top_losers_result.scalars().all()
            ]
            
            # Get tournament standings
            tournament_standings = []
            try:
                from app.services.tournaments import tournament_service, TournamentType
                
                daily_tournament = await tournament_service.get_current_tournament(
                    TournamentType.DAILY, session
                )
                
                if daily_tournament:
                    for discipline, standings in daily_tournament.standings.items():
                        for standing in standings[:3]:
                            tournament_standings.append({
                                "discipline": discipline.value,
                                "username": standing.username or f"User {standing.user_id}",
                                "score": standing.score,
                                "rank": standing.rank
                            })
            except Exception as e:
                logger.warning(f"Failed to get tournament standings: {e}")
            
            ds = DailyStats(
                chat_id=chat_id,
                date=now,
                top_growers=top_growers,
                top_losers=top_losers,
                tournament_standings=tournament_standings,
                chart_data=chart_data
            )
            # Add extra fields to the dataclass instance dynamically
            ds.big_winners = big_winners
            ds.top_gamblers = top_gamblers
            return ds
            
        except Exception as e:
            logger.error(f"Failed to aggregate stats for chat {chat_id}: {e}")
            return DailyStats(chat_id=chat_id, date=utc_now())
            
        finally:
            if close_session:
                await session.close()
    
    def format_stats(self, stats: DailyStats) -> str:
        """
        Format daily stats for display.
        
        Requirement 13.3: Send a #dailystats message with game statistics.
        """
        lines = [
            "📈 #dailystats",
            "━━━━━━━━━━━━━━━━━━━━",
            ""
        ]
        
        # Top growers
        if stats.top_growers:
            lines.append("🌱 ТОП ГРОВЕРОВ:")
            medals = ["🥇", "🥈", "🥉", "4.", "5."]
            for i, grower in enumerate(stats.top_growers[:5]):
                medal = medals[i] if i < len(medals) else f"{i+1}."
                lines.append(f"  {medal} {grower['username']}: {grower['size']} см")
            lines.append("")
        
        # Big winners
        big_winners = getattr(stats, 'big_winners', [])
        if big_winners:
            lines.append("💰 ТОП ВЫИГРЫШИ:")
            for i, w in enumerate(big_winners, 1):
                medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
                lines.append(f"  {medal} {w['username']}: {w['amount']} 🪙")
            lines.append("")
            
        # Top gamblers
        top_gamblers = getattr(stats, 'top_gamblers', [])
        if top_gamblers:
            lines.append("🎰 ИГРОМАНЫ ДНЯ:")
            for i, g in enumerate(top_gamblers, 1):
                lines.append(f"  {i}. {g['username']} — {g['count']} игр")
            lines.append("")
        
        # Tournament standings
        if stats.tournament_standings:
            lines.append("🏆 ТУРНИР ДНЯ:")
            disciplines = {}
            for s in stats.tournament_standings:
                d = s['discipline']
                if d not in disciplines: disciplines[d] = []
                disciplines[d].append(s)
            
            for d, st in disciplines.items():
                lines.append(f"  [{d.upper()}]")
                for s in st[:3]:
                    medal = ["🥇", "🥈", "🥉"][s['rank']-1] if s['rank'] <= 3 else f"{s['rank']}."
                    lines.append(f"    {medal} {s['username']}: {s['score']}")
            lines.append("")
            
        # Top losers
        if stats.top_losers:
            lines.append("📉 МАЛЕНЬКИЕ ПИПИСЬКИ:")
            for i, loser in enumerate(stats.top_losers[:3], 1):
                lines.append(f"  {i}. {loser['username']}: {loser['size']} см")
            lines.append("")
        
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        if stats.chart_data:
            lines.append("Смотри график роста выше! ☝️")
        else:
            lines.append("Играйте больше! 🎮")
        
        return "\n".join(lines)
    
    # =========================================================================
    # Combined Daily Messages
    # =========================================================================
    
    async def get_morning_messages(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None,
        for_today: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all morning messages for a chat.
        
        Args:
            chat_id: Telegram chat ID
            session: Optional database session
            for_today: Whether to summarize today so far
            
        Returns:
            List of message dicts {"text": str, "photo": bytes (optional)}
        """
        messages = []
        
        config = await self.get_config(chat_id, session)
        
        # Check if summary is enabled (Property 33)
        if self.should_send_message(config, 'summary'):
            summary = await self.generate_summary(chat_id, session, for_today=for_today)
            
            # Check if should skip due to no activity (Property 34)
            if not self.should_skip_summary(summary):
                if not for_today:
                    # Morning briefing (yesterday's recap)
                    messages.append({"text": self.format_morning_summary(summary)})
                else:
                    # Evening summary (today's recap)
                    messages.append({"text": self.format_summary(summary)})
        
        return messages
    
    async def get_evening_messages(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all evening messages for a chat.
        
        Requirements 13.2, 13.3: Evening quote and stats at 21:00 Moscow.
        
        Args:
            chat_id: Telegram chat ID
            session: Optional database session
            
        Returns:
            List of message dicts {"text": str, "photo": bytes (optional)}
        """
        messages = []
        
        config = await self.get_config(chat_id, session)
        
        # Check if quote is enabled (Property 33)
        if self.should_send_message(config, 'quote'):
            quote = await self.select_daily_quote(chat_id, session)
            messages.append({"text": self.format_quote(quote)})
        
        # Check if stats is enabled (Property 33)
        if self.should_send_message(config, 'stats'):
            stats = await self.aggregate_daily_stats(chat_id, session)
            messages.append({
                "text": self.format_stats(stats),
                "photo": stats.chart_data
            })
        
        return messages


# Global service instance
dailies_service = DailiesService()
