import re
import logging
import time
from typing import Any
from aiogram import BaseMiddleware
from aiogram.types import Message
from aiogram import types
from datetime import datetime

from app.database.session import get_session
from app.database.models import MessageLog, User
from sqlalchemy import select, update
from app.utils import utc_now
from app.config import settings

logger = logging.getLogger(__name__)

LINK_RE = re.compile(r"https?:\/\/\S+", re.IGNORECASE)


class MessageLoggerMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data: dict[str, Any]):
        start_time = time.time()
        
        # Record update for health check
        if settings.metrics_enabled:
            try:
                from app.services.metrics_server import record_update_received
                record_update_received()
            except Exception:
                pass  # Don't fail on health tracking errors
        
        if isinstance(event, types.Message) and event.chat:
            # Логируем входящее сообщение
            user_tag = f"@{event.from_user.username}" if event.from_user and event.from_user.username else f"id:{event.from_user.id if event.from_user else 'unknown'}"
            topic_id = getattr(event, 'message_thread_id', None)
            is_forum = getattr(event.chat, 'is_forum', False)
            text_preview = (event.text or event.caption or "")[:50]
            
            # Для команд логируем на INFO уровне
            if event.text and event.text.startswith("/"):
                logger.info(
                    f"[CMD IN] chat={event.chat.id} | user={user_tag} | "
                    f"cmd={text_preview}"
                )
            else:
                logger.debug(
                    f"[MSG IN] chat={event.chat.id} | type={event.chat.type} | "
                    f"forum={is_forum} | topic={topic_id} | user={user_tag} | "
                    f"msg_id={event.message_id}"
                )
            text = event.text or event.caption or ""
            links = LINK_RE.findall(text) if text else []
            async_session = get_session()
            async with async_session() as session:
                # upsert user by tg_user_id
                res = await session.execute(select(User).where(User.tg_user_id == event.from_user.id))
                user = res.scalars().first()
                if not user:
                    user = User(
                        tg_user_id=event.from_user.id,
                        username=event.from_user.username,
                        first_name=event.from_user.first_name,
                        last_name=event.from_user.last_name,
                    )
                    session.add(user)
                else:
                    # best-effort update username
                    await session.execute(
                        update(User)
                        .where(User.tg_user_id == event.from_user.id)
                        .values(username=event.from_user.username)
                    )

                ml = MessageLog(
                    chat_id=event.chat.id,
                    message_id=event.message_id,
                    user_id=event.from_user.id,
                    username=event.from_user.username,
                    text=text,
                    has_link=bool(links),
                    links="\n".join(links) if links else None,
                    topic_id=getattr(event, 'message_thread_id', None),  # ID топика в форуме
                    created_at=utc_now(),
                )
                session.add(ml)
                try:
                    await session.commit()
                except Exception:
                    await session.rollback()
            
            # Extract facts ONLY when user directly interacts with Oleg (replies, mentions, or DM)
            if text and len(text) >= 10 and event.from_user:
                # Check if this is a direct interaction with the bot
                is_direct_interaction = False
                
                # 1. Private message (DM)
                if event.chat.type == "private":
                    is_direct_interaction = True
                
                # 2. Reply to bot's message
                elif event.reply_to_message and event.reply_to_message.from_user:
                    bot_info = await event.bot.get_me()
                    if event.reply_to_message.from_user.id == bot_info.id:
                        is_direct_interaction = True
                
                # 3. Bot mentioned in text
                elif event.text:
                    bot_info = await event.bot.get_me()
                    text_lower = event.text.lower()
                    # Check for @username mention
                    if bot_info.username and f"@{bot_info.username.lower()}" in text_lower:
                        is_direct_interaction = True
                    # Check for "олег" mentions
                    oleg_triggers = ["олег", "олега", "олегу", "олегом", "олеге", "oleg"]
                    for trigger in oleg_triggers:
                        if re.search(rf'\b{trigger}\b', text_lower):
                            is_direct_interaction = True
                            break
                
                # Only extract facts if user is directly interacting with Oleg
                if is_direct_interaction:
                    import asyncio
                    from app.services.ollama_client import extract_facts_from_message, store_fact_to_memory
                    from app.services.user_memory import user_memory
                    
                    async def extract_facts_background():
                        try:
                            user_info = {"username": event.from_user.username} if event.from_user.username else {}
                            topic_id = getattr(event, 'message_thread_id', None)
                            new_facts = await extract_facts_from_message(text, event.chat.id, user_info, topic_id=topic_id)
                            if new_facts:
                                for fact in new_facts:
                                    await store_fact_to_memory(fact['text'], event.chat.id, fact['metadata'], topic_id=topic_id)
                                await user_memory.update_profile_from_facts(
                                    event.chat.id, event.from_user.id, event.from_user.username, new_facts
                                )
                                logger.debug(f"[FACTS] Extracted {len(new_facts)} facts from direct interaction in chat {event.chat.id}")
                        except Exception as e:
                            logger.debug(f"Background fact extraction failed: {e}")
                    
                    asyncio.create_task(extract_facts_background())

            # Track message metrics
            try:
                from app.services.metrics import track_message_processed
                chat_type = event.chat.type if event.chat else "unknown"
                await track_message_processed(chat_type)
            except Exception:
                pass

        # Выполняем обработчик и замеряем время
        try:
            result = await handler(event, data)
            duration = time.time() - start_time
            
            if duration > 5.0:
                logger.warning(
                    f"[MSG SLOW] chat={event.chat.id if event.chat else 'N/A'} | "
                    f"msg_id={event.message_id if hasattr(event, 'message_id') else 'N/A'} | "
                    f"time={duration:.2f}s"
                )
            
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"[MSG ERROR] chat={event.chat.id if event.chat else 'N/A'} | "
                f"msg_id={event.message_id if hasattr(event, 'message_id') else 'N/A'} | "
                f"time={duration:.2f}s | error={type(e).__name__}: {e}"
            )
            raise
