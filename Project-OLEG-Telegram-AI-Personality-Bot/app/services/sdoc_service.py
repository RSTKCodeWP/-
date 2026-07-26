"""
SDOC Service - Интеграция Олега с группой Steam Deck OC.

Олег — резидент СДОС. Это его родной дом.
- Работает только в SDOC и ЛС
- Знает админов/приписочников
- Собирает локальные мемы
- Понимает структуру топиков
"""

import json
from datetime import datetime
from typing import Optional

from aiogram import Bot
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import GroupAdmin, GroupMeme, SDOCTopic
from app.database.session import async_session
import logging

logger = logging.getLogger(__name__)
from app.utils import utc_now


# Топики SDOC (захардкожены, но можно обновлять из БД)
SDOC_TOPICS = {
    1: {"name": "Добро пожаловать новичок", "category": "meta", "keywords": ["новичок", "привет", "начать"]},
    5: {"name": "Правила", "category": "meta", "keywords": ["правила", "бан", "нельзя"]},
    8: {"name": "Разгон и оптимизация", "category": "tech", "keywords": ["разгон", "оптимизация", "fps", "частота", "undervolt"]},
    13: {"name": "Полезное", "category": "tech", "keywords": ["гайд", "инструкция", "как", "полезное"]},
    65: {"name": "Файлы", "category": "tech", "keywords": ["файл", "скачать", "софт", "утилита"]},
    1121: {"name": "Мемасы", "category": "fun", "keywords": ["мем", "смешно", "лол"]},
    4803: {"name": "Скриншоты и тесты игр", "category": "tech", "keywords": ["скрин", "тест", "бенчмарк", "fps"]},
    20309: {"name": "Эмуляторы", "category": "tech", "keywords": ["эмулятор", "ретро", "ps2", "switch", "yuzu"]},
    24345: {"name": "Фотки из Иваново", "category": "fun", "keywords": ["фото", "иваново", "фотка"]},
    45881: {"name": "Реверсинг", "category": "tech", "keywords": ["реверс", "хак", "взлом", "патч"]},
    96969: {"name": "Мастерская Стим Декера", "category": "tech", "keywords": ["мод", "кастом", "корпус", "кнопки"]},
    112472: {"name": "Музыка в качалке", "category": "fun", "keywords": ["музыка", "трек", "песня"]},
    739723: {"name": "Лудка", "category": "fun", "keywords": ["игра", "лудка", "казино", "ставка"]},
    865592: {"name": "Барахолка", "category": "trade", "keywords": ["продам", "куплю", "обмен", "цена"]},
    889461: {"name": "Фонд цитат имени Синицы с яйцами", "category": "fun", "keywords": ["цитата", "синица", "фонд"]},
    1132961: {"name": "Качалка (оффтоп)", "category": "fun", "keywords": ["оффтоп", "качалка", "флуд"]},
}


class SDOCService:
    """Сервис для работы с группой SDOC."""
    
    def __init__(self):
        self._chat_id: Optional[int] = settings.sdoc_chat_id
        self._admins_cache: dict[int, dict] = {}  # user_id -> admin info
        self._last_sync: Optional[datetime] = None
    
    @property
    def chat_id(self) -> Optional[int]:
        """ID чата SDOC."""
        return self._chat_id
    
    @chat_id.setter
    def chat_id(self, value: int):
        """Установить ID чата SDOC (при первом сообщении из группы)."""
        self._chat_id = value
    
    def is_sdoc_chat(self, chat_id: int) -> bool:
        """Проверить, является ли чат группой SDOC."""
        if self._chat_id and chat_id == self._chat_id:
            return True
        return False
    
    def is_allowed_chat(self, chat_id: int, is_private: bool = False) -> bool:
        """
        Проверить, разрешён ли чат для Олега.
        
        В эксклюзивном режиме: только SDOC и ЛС.
        """
        if not settings.sdoc_exclusive_mode:
            return True
        
        if is_private:
            return True
        
        if self._chat_id and chat_id == self._chat_id:
            return True
        
        return False
    
    def is_sdoc_owner(self, user_id: int) -> bool:
        """Проверить, является ли пользователь владельцем SDOC."""
        return user_id == settings.sdoc_owner_id
    
    def has_admin_access(self, user_id: int) -> bool:
        """
        Проверить, есть ли у пользователя доступ к админке.
        
        Доступ имеют: owner бота и владелец SDOC.
        """
        if settings.owner_id and user_id == settings.owner_id:
            return True
        if user_id == settings.sdoc_owner_id:
            return True
        return False
    
    async def sync_admins(self, bot: Bot, chat_id: int) -> int:
        """
        Синхронизировать список админов группы с Telegram.
        
        Returns:
            Количество синхронизированных админов.
        """
        try:
            admins = await bot.get_chat_administrators(chat_id)
            
            async with async_session() as session:
                # Деактивируем всех текущих админов
                await session.execute(
                    delete(GroupAdmin).where(GroupAdmin.chat_id == chat_id)
                )
                
                count = 0
                for admin in admins:
                    if isinstance(admin, (ChatMemberAdministrator, ChatMemberOwner)):
                        role = "creator" if isinstance(admin, ChatMemberOwner) else "administrator"
                        title = getattr(admin, 'custom_title', None)
                        
                        group_admin = GroupAdmin(
                            chat_id=chat_id,
                            user_id=admin.user.id,
                            username=admin.user.username,
                            first_name=admin.user.first_name,
                            last_name=admin.user.last_name,
                            title=title,
                            role=role,
                            is_active=True,
                            synced_at=utc_now()
                        )
                        session.add(group_admin)
                        
                        # Кэшируем
                        self._admins_cache[admin.user.id] = {
                            "username": admin.user.username,
                            "first_name": admin.user.first_name,
                            "title": title,
                            "role": role
                        }
                        count += 1
                
                await session.commit()
                self._last_sync = utc_now()
                logger.info(f"Синхронизировано {count} админов SDOC")
                return count
                
        except Exception as e:
            logger.error(f"Ошибка синхронизации админов: {e}")
            return 0
    
    async def get_admins(self) -> list[dict]:
        """Получить список админов группы."""
        async with async_session() as session:
            result = await session.execute(
                select(GroupAdmin)
                .where(GroupAdmin.chat_id == self._chat_id)
                .where(GroupAdmin.is_active == True)
            )
            admins = result.scalars().all()
            return [
                {
                    "user_id": a.user_id,
                    "username": a.username,
                    "first_name": a.first_name,
                    "title": a.title,
                    "role": a.role
                }
                for a in admins
            ]
    
    def get_admin_name(self, user_id: int) -> Optional[str]:
        """Получить имя админа по ID (из кэша)."""
        if user_id in self._admins_cache:
            admin = self._admins_cache[user_id]
            return admin.get("title") or admin.get("first_name") or admin.get("username")
        return None
    
    def is_admin(self, user_id: int) -> bool:
        """Проверить, является ли пользователь админом группы."""
        return user_id in self._admins_cache
    
    async def add_meme(
        self,
        chat_id: int,
        meme_type: str,
        content: str,
        context: Optional[str] = None,
        author_user_id: Optional[int] = None,
        author_name: Optional[str] = None
    ) -> bool:
        """
        Добавить локальный мем/прикол в базу.
        
        Args:
            meme_type: quote, joke, reference, nickname
        """
        try:
            async with async_session() as session:
                meme = GroupMeme(
                    chat_id=chat_id,
                    meme_type=meme_type,
                    content=content,
                    context=context,
                    author_user_id=author_user_id,
                    author_name=author_name
                )
                session.add(meme)
                await session.commit()
                logger.info(f"Добавлен мем: {meme_type} - {content[:50]}...")
                return True
        except Exception as e:
            logger.error(f"Ошибка добавления мема: {e}")
            return False
    
    async def get_memes(self, chat_id: int, meme_type: Optional[str] = None) -> list[dict]:
        """Получить мемы группы."""
        async with async_session() as session:
            query = select(GroupMeme).where(
                GroupMeme.chat_id == chat_id,
                GroupMeme.is_active == True
            )
            if meme_type:
                query = query.where(GroupMeme.meme_type == meme_type)
            
            result = await session.execute(query)
            memes = result.scalars().all()
            return [
                {
                    "type": m.meme_type,
                    "content": m.content,
                    "context": m.context,
                    "author": m.author_name,
                    "usage_count": m.usage_count
                }
                for m in memes
            ]
    
    def get_topic_by_keywords(self, text: str) -> Optional[dict]:
        """
        Найти подходящий топик по ключевым словам в тексте.
        
        Returns:
            {"id": topic_id, "name": name, "category": category} или None
        """
        text_lower = text.lower()
        for topic_id, info in SDOC_TOPICS.items():
            for keyword in info.get("keywords", []):
                if keyword in text_lower:
                    return {
                        "id": topic_id,
                        "name": info["name"],
                        "category": info["category"]
                    }
        return None
    
    def get_topic_link(self, topic_id: int) -> str:
        """Получить ссылку на топик."""
        return f"https://t.me/{settings.sdoc_chat_username}/{topic_id}"
    
    def get_topics_summary(self) -> str:
        """Получить краткую сводку по топикам для промпта."""
        tech = []
        fun = []
        other = []
        
        for topic_id, info in SDOC_TOPICS.items():
            entry = f"{info['name']} (/{topic_id})"
            if info["category"] == "tech":
                tech.append(entry)
            elif info["category"] == "fun":
                fun.append(entry)
            else:
                other.append(entry)
        
        return f"""Технические: {', '.join(tech[:5])}...
Развлечения: {', '.join(fun[:4])}...
Прочее: {', '.join(other)}"""


# Глобальный экземпляр сервиса
sdoc_service = SDOCService()


async def init_sdoc_topics(chat_id: int):
    """Инициализировать топики SDOC в базе данных."""
    try:
        async with async_session() as session:
            for topic_id, info in SDOC_TOPICS.items():
                existing = await session.execute(
                    select(SDOCTopic).where(
                        SDOCTopic.chat_id == chat_id,
                        SDOCTopic.topic_id == topic_id
                    )
                )
                if not existing.scalar_one_or_none():
                    topic = SDOCTopic(
                        chat_id=chat_id,
                        topic_id=topic_id,
                        name=info["name"],
                        category=info["category"],
                        keywords=json.dumps(info.get("keywords", []), ensure_ascii=False)
                    )
                    session.add(topic)
            
            await session.commit()
            logger.info(f"Инициализировано {len(SDOC_TOPICS)} топиков SDOC")
    except Exception as e:
        logger.error(f"Ошибка инициализации топиков: {e}")
