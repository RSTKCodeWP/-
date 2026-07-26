"""Глобальный слушатель сообщений из всех топиков супергруппы."""

import logging
from aiogram import Router, F
from aiogram.types import Message
from typing import Optional, List, Dict

from app.services.vector_db import vector_db
from app.utils import utc_now

logger = logging.getLogger(__name__)

router = Router()


class TopicListener:
    """
    Глобальный слушатель сообщений из всех топиков.
    
    Обрабатывает сообщения из любого топика супергруппы и сохраняет
    их в RAG с привязкой к chat_id и topic_id для меж-топикового восприятия.
    
    Сохраняет только релевантные сообщения:
    - Сообщения где бот упомянут
    - Ответы бота
    - Сообщения в активном диалоге с ботом
    """
    
    COLLECTION_NAME = "chat_messages"
    
    # Время активного диалога после упоминания бота (секунды)
    ACTIVE_DIALOG_TIMEOUT = 300  # 5 минут
    
    def __init__(self):
        self._vector_db = vector_db
        # Словарь активных диалогов: {chat_id: timestamp последнего упоминания бота}
        self._active_dialogs: Dict[int, float] = {}
    
    async def is_message_relevant(self, message: Message) -> bool:
        """
        Проверяет, является ли сообщение релевантным для сохранения в RAG.
        
        Релевантные сообщения:
        1. Сообщения от бота (его ответы)
        2. Сообщения где бот упомянут (@username или "олег")
        3. Сообщения в активном диалоге (в течение 5 минут после упоминания бота)
        4. Реплаи на сообщения бота
        
        Args:
            message: Сообщение Telegram
            
        Returns:
            True если сообщение релевантно и должно быть сохранено
        """
        import time
        import re
        
        # Сохраняем только сообщения из групп/супергрупп
        if message.chat.type not in ("group", "supergroup"):
            return False
        
        if not message.text:
            return False
        
        chat_id = message.chat.id
        current_time = time.time()
        
        # 1. Сообщения от бота всегда релевантны
        if message.from_user and message.from_user.is_bot:
            # Обновляем время активного диалога
            self._active_dialogs[chat_id] = current_time
            logger.debug(f"[RAG RELEVANCE] YES - bot message, chat={chat_id}")
            return True
        
        # 2. Проверяем упоминание бота
        text_lower = message.text.lower()
        
        # Проверка @username
        if message.entities:
            for entity in message.entities:
                if entity.type == "mention":
                    mention_text = message.text[entity.offset:entity.offset + entity.length]
                    # Получаем username бота
                    bot_username = None
                    try:
                        bot_username = message.bot._me.username if message.bot._me else None
                    except:
                        pass
                    
                    if bot_username and mention_text.lower() == f"@{bot_username.lower()}":
                        self._active_dialogs[chat_id] = current_time
                        logger.debug(f"[RAG RELEVANCE] YES - bot mentioned @{bot_username}, chat={chat_id}")
                        return True
        
        # Проверка "олег" в тексте
        oleg_triggers = ["олег", "олега", "олегу", "олегом", "олеге", "oleg"]
        for trigger in oleg_triggers:
            if re.search(rf'\b{trigger}\b', text_lower):
                self._active_dialogs[chat_id] = current_time
                logger.debug(f"[RAG RELEVANCE] YES - trigger '{trigger}', chat={chat_id}")
                return True
        
        # 3. Проверяем реплай на сообщение бота
        if message.reply_to_message:
            if message.reply_to_message.from_user and message.reply_to_message.from_user.is_bot:
                self._active_dialogs[chat_id] = current_time
                logger.debug(f"[RAG RELEVANCE] YES - reply to bot, chat={chat_id}")
                return True
        
        # 4. Проверяем активный диалог
        last_mention_time = self._active_dialogs.get(chat_id)
        if last_mention_time:
            time_since_mention = current_time - last_mention_time
            if time_since_mention <= self.ACTIVE_DIALOG_TIMEOUT:
                logger.debug(
                    f"[RAG RELEVANCE] YES - active dialog ({time_since_mention:.0f}s ago), "
                    f"chat={chat_id}"
                )
                return True
            else:
                # Диалог неактивен, удаляем из словаря
                del self._active_dialogs[chat_id]
                logger.debug(
                    f"[RAG RELEVANCE] NO - dialog expired ({time_since_mention:.0f}s ago), "
                    f"chat={chat_id}"
                )
        
        logger.debug(f"[RAG RELEVANCE] NO - not relevant, chat={chat_id}")
        return False
    
    def extract_topic_id(self, message: Message) -> Optional[int]:
        """
        Извлекает topic_id из сообщения.
        
        Args:
            message: Сообщение Telegram
            
        Returns:
            topic_id или None если сообщение не в топике
        """
        return getattr(message, 'message_thread_id', None)
    
    async def store_to_rag(self, message: Message) -> None:
        """
        Сохраняет сообщение в RAG с привязкой к топику.
        
        Args:
            message: Сообщение Telegram
        """
        if not message.text:
            return
        
        chat_id = message.chat.id
        topic_id = self.extract_topic_id(message)
        user_id = message.from_user.id if message.from_user else 0
        username = message.from_user.username if message.from_user else None
        
        try:
            self._vector_db.store_message(
                collection_name=self.COLLECTION_NAME,
                text=message.text,
                chat_id=chat_id,
                topic_id=topic_id,
                user_id=user_id,
                username=username,
                message_id=message.message_id
            )
            logger.debug(
                f"Сообщение сохранено в RAG: chat={chat_id}, topic={topic_id}, "
                f"user={username or user_id}"
            )
        except Exception as e:
            logger.error(f"Ошибка при сохранении сообщения в RAG: {e}")
    
    def get_cross_topic_context(self, chat_id: int, query: str, n_results: int = 5) -> List[Dict]:
        """
        Получает контекст из всех топиков чата (cross-topic retrieval).
        
        Args:
            chat_id: ID чата
            query: Запрос для поиска релевантного контекста
            n_results: Количество результатов
            
        Returns:
            Список релевантных сообщений из всех топиков чата
        """
        try:
            return self._vector_db.search_cross_topic(
                collection_name=self.COLLECTION_NAME,
                query=query,
                chat_id=chat_id,
                n_results=n_results
            )
        except Exception as e:
            logger.error(f"Ошибка при получении cross-topic контекста: {e}")
            return []
    
    def format_context_with_topic_info(self, facts: List[Dict]) -> str:
        """
        Форматирует контекст с информацией о топиках.
        
        Args:
            facts: Список фактов из RAG
            
        Returns:
            Отформатированная строка контекста с указанием топиков
        """
        if not facts:
            return ""
        
        context_parts = []
        for fact in facts:
            metadata = fact.get('metadata', {})
            topic_id = metadata.get('topic_id', -1)
            username = metadata.get('username', 'Unknown')
            text = fact.get('text', '')
            
            # Форматируем с указанием топика
            topic_label = f"[Topic {topic_id}]" if topic_id != -1 else "[General]"
            context_parts.append(f"{topic_label} @{username}: {text}")
        
        return "\n".join(context_parts)
    
    async def on_message(self, message: Message) -> None:
        """
        Обрабатывает сообщение из любого топика.
        
        Args:
            message: Сообщение Telegram
        """
        # Сохраняем только текстовые сообщения из групп/супергрупп
        if message.chat.type not in ("group", "supergroup"):
            return
        
        if not message.text:
            return
        
        await self.store_to_rag(message)


# Глобальный экземпляр слушателя
topic_listener = TopicListener()


@router.message(F.text)
async def handle_all_messages(message: Message):
    """
    Глобальный обработчик всех текстовых сообщений для RAG.
    
    Сохраняет только релевантные сообщения:
    - Сообщения где бот упомянут (@username, "олег")
    - Ответы бота
    - Сообщения в активном диалоге с ботом (в течение 5 минут после упоминания)
    
    Этот обработчик должен быть зарегистрирован с низким приоритетом,
    чтобы не блокировать другие обработчики.
    """
    # Логируем все входящие сообщения для отладки топиков
    topic_id = getattr(message, 'message_thread_id', None)
    logger.debug(
        f"[TOPIC LISTENER] Получено сообщение: chat_id={message.chat.id}, "
        f"topic_id={topic_id}, chat_type={message.chat.type}, "
        f"is_forum={message.chat.is_forum}, text={message.text[:50] if message.text else 'empty'}..."
    )
    
    # Проверяем релевантность сообщения перед сохранением
    if await topic_listener.is_message_relevant(message):
        await topic_listener.on_message(message)
    else:
        logger.debug(f"[TOPIC LISTENER] Сообщение не релевантно, пропускаем сохранение в RAG")
