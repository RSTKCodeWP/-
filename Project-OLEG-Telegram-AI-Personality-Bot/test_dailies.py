import asyncio
import logging
import os
from datetime import datetime, timedelta
from app.config import settings

# ВАЖНО: Переопределяем URL БД ДО импорта других модулей, которые могут инициализировать движок
settings.database_url = "sqlite+aiosqlite:///:memory:"

from app.services.dailies import dailies_service
from app.database.session import init_db, get_session
from app.database.models import Chat, MessageLog, User, GameStat, Base
from sqlalchemy import select
from app.utils import utc_now

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def setup_test_db():
    """Создает временную БД и наполняет её данными для теста."""
    await init_db()
    
    async_session = get_session()
    async with async_session() as session:
        # 1. Создаем чат
        chat_id = -100123456789
        chat = Chat(
            id=chat_id,
            title="Test Tech Chat",
            is_forum=True,
            summary_topic_id=1,
            persona="oleg",
            reactions_enabled=True,
            auto_reply_chance=0.1
        )
        session.add(chat)
        
        # 2. Создаем пользователя
        user = User(
            tg_user_id=123456,
            username="test_user",
            first_name="Test",
            status="active"
        )
        session.add(user)
        await session.flush()
        
        # 3. Создаем статистику роста
        gs = GameStat(
            user_id=user.id,
            tg_user_id=user.tg_user_id,
            username=user.username,
            size_cm=105,
            grow_history=[
                {"date": (utc_now() - timedelta(days=2)).strftime("%Y-%m-%d"), "size": 90, "change": 5},
                {"date": (utc_now() - timedelta(days=1)).strftime("%Y-%m-%d"), "size": 95, "change": 5},
                {"date": utc_now().strftime("%Y-%m-%d"), "size": 105, "change": 10}
            ]
        )
        session.add(gs)
        
        # 4. Добавляем сообщения за сегодня
        now = utc_now()
        messages = [
            "Привет всем! Как там RTX 5090?",
            "Олег, ты опять тупишь?",
            "База — это когда пиво холодное.",
            "Кто-нибудь знает, как настроить Arch Linux?",
            "Я сегодня купил новый проц, 9800X3D просто пушка!",
            "Чехия — отличная страна для айтишников.",
            "Нашел баг в коде, пойду костыль вставлю.",
            "@test_user, ты что творишь?",
            "Смешной мем: [ссылка]",
            "Погнали в бар!",
            "Нужно перекатиться на Rust.",
            "Кто завтра идет на митап?",
            "AMD опять рвет Интел в играх.",
            "Где взять нормальный конфиг для nvim?"
        ]
        
        for i, t in enumerate(messages):
            msg = MessageLog(
                chat_id=chat_id,
                message_id=100 + i,
                user_id=user.tg_user_id,
                username=user.username,
                text=t,
                created_at=now - timedelta(minutes=i*15)
            )
            session.add(msg)
            
        await session.commit()
        return chat_id

async def test_dailies():
    """
    Тестирование генерации дейликов во временной БД.
    """
    logger.info("Setting up test database...")
    chat_id = await setup_test_db()
    
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(select(Chat).filter_by(id=chat_id))
        chat = result.scalar_one()
        
        logger.info(f"Testing dailies for chat: {chat.title} ({chat_id})")
        logger.info(f"Current persona: {chat.persona}")

        output = []
        output.append(f"TEST RESULTS FOR CHAT: {chat.title} ({chat_id})")
        output.append(f"PERSONA: {chat.persona}")
        output.append("DATE: " + utc_now().strftime("%d.%m.%Y %H:%M"))
        output.append("="*50 + "\n")

        # 1. Тест Саммари (за сегодня)
        logger.info("Generating #dailysummary...")
        summary_msgs = await dailies_service.get_morning_messages(chat_id, session, for_today=True)
        for msg in summary_msgs:
            section = "\n--- SUMMARY MESSAGE ---\n"
            text_content = msg.get("text")
            output.append(section + text_content)
            if msg.get("photo"):
                output.append("[Photo attached (Growth Chart Generated)]")

        # 2. Тест Статистики и Цитаты
        logger.info("Generating #dailystats and #dailyquote...")
        evening_msgs = await dailies_service.get_evening_messages(chat_id, session)
        for msg in evening_msgs:
            section = "\n--- EVENING MESSAGE ---\n"
            text_content = msg.get("text")
            output.append(section + text_content)
            if msg.get("photo"):
                output.append(f"[Photo attached: Chart generated]")

        # Write to file
        with open("test_output.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(output))
        
        logger.info("Results written to test_output.txt")
        print("\nSUCCESS: Results written to test_output.txt")

if __name__ == "__main__":
    asyncio.run(test_dailies())
