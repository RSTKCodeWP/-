"""
SDOC Filter Middleware - Олег работает только в SDOC и ЛС.

В эксклюзивном режиме игнорирует сообщения из других групп.
При добавлении в чужую группу — молча выходит.
"""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, ChatMemberUpdated

from app.config import settings
import logging

logger = logging.getLogger(__name__)
from app.services.sdoc_service import sdoc_service


async def register_sdoc_chat(bot: Bot, chat_id: int, chat_title: str, is_forum: bool = False):
    """Зарегистрировать группу SDOC в базе данных."""
    try:
        from app.database.session import async_session
        from app.database.models import Chat
        from sqlalchemy import select
        
        async with async_session() as session:
            result = await session.execute(
                select(Chat).where(Chat.id == chat_id)
            )
            existing_chat = result.scalar_one_or_none()
            
            if not existing_chat:
                new_chat = Chat(
                    id=chat_id,
                    title=chat_title,
                    is_forum=is_forum,
                    owner_user_id=settings.sdoc_owner_id
                )
                session.add(new_chat)
                await session.commit()
                logger.info(f"Группа SDOC зарегистрирована: {chat_title} ({chat_id})")
                return True
    except Exception as e:
        logger.error(f"Ошибка регистрации SDOC: {e}")
    return False


class SDOCFilterMiddleware(BaseMiddleware):
    """
    Middleware для фильтрации сообщений по чату.
    
    Олег работает только в SDOC и ЛС.
    """
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Пропускаем если эксклюзивный режим выключен
        if not settings.sdoc_exclusive_mode:
            return await handler(event, data)
        
        chat = event.chat
        is_private = chat.type == "private"
        
        # ЛС всегда разрешены
        if is_private:
            return await handler(event, data)
        
        # Проверяем, это SDOC?
        chat_id = chat.id
        
        # Если chat_id SDOC ещё не известен, пробуем определить по username
        if not sdoc_service.chat_id:
            if chat.username and chat.username.lower() == settings.sdoc_chat_username.lower():
                sdoc_service.chat_id = chat_id
                logger.info(f"SDOC chat_id определён: {chat_id}")
                
                # Регистрируем группу в базе данных
                bot: Bot = data.get("bot")
                if bot:
                    is_forum = getattr(chat, 'is_forum', False)
                    await register_sdoc_chat(bot, chat_id, chat.title or "Steam Deck OC", is_forum)
                    
                    # Синхронизируем админов
                    try:
                        count = await sdoc_service.sync_admins(bot, chat_id)
                        logger.info(f"Синхронизировано {count} админов SDOC")
                    except Exception as e:
                        logger.warning(f"Не удалось синхронизировать админов: {e}")
        
        # Проверяем разрешён ли чат
        if sdoc_service.is_allowed_chat(chat_id, is_private):
            return await handler(event, data)
        
        # Чат не разрешён — игнорируем сообщение
        logger.debug(f"Игнорируем сообщение из чата {chat_id} ({chat.title})")
        return None


class SDOCAutoLeaveMiddleware(BaseMiddleware):
    """
    Middleware для автоматического выхода из чужих групп.
    
    Срабатывает при добавлении бота в группу.
    """
    
    async def __call__(
        self,
        handler: Callable[[ChatMemberUpdated, Dict[str, Any]], Awaitable[Any]],
        event: ChatMemberUpdated,
        data: Dict[str, Any]
    ) -> Any:
        # Пропускаем если эксклюзивный режим выключен
        if not settings.sdoc_exclusive_mode:
            return await handler(event, data)
        
        # Проверяем, это событие добавления бота?
        if event.new_chat_member and event.new_chat_member.user.id == event.bot.id:
            chat = event.chat
            chat_id = chat.id
            
            # Если это не SDOC — выходим
            is_sdoc = False
            if sdoc_service.chat_id and chat_id == sdoc_service.chat_id:
                is_sdoc = True
            elif chat.username and chat.username.lower() == settings.sdoc_chat_username.lower():
                is_sdoc = True
                sdoc_service.chat_id = chat_id
            
            if not is_sdoc:
                logger.warning(f"Бот добавлен в чужую группу {chat_id} ({chat.title}), выходим...")
                try:
                    bot: Bot = data.get("bot")
                    if bot:
                        await bot.leave_chat(chat_id)
                        logger.info(f"Вышли из группы {chat_id}")
                except Exception as e:
                    logger.error(f"Ошибка выхода из группы: {e}")
                return None
        
        return await handler(event, data)
