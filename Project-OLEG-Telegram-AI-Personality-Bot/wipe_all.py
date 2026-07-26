#!/usr/bin/env python3
"""
Полный вайп базы данных и векторной памяти.
Сбрасывает всё к начальному состоянию и восстанавливает дефолтные знания.

Использование:
    python wipe_all.py              # Вайп + восстановление дефолтных знаний
    python wipe_all.py --no-restore # Вайп без восстановления
    python wipe_all.py -y           # Без подтверждения
"""

import asyncio
import shutil
import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()


def get_chromadb_path() -> Path:
    """Получить путь к ChromaDB из переменных окружения."""
    return Path(os.getenv("CHROMADB_PERSIST_DIR", "./data/chromadb"))


def get_collection_name() -> str:
    """Получить название коллекции из переменных окружения."""
    return os.getenv("CHROMADB_COLLECTION_NAME", "oleg_kb")


def get_database_url() -> str:
    """Получить URL базы данных из переменных окружения."""
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/bot.db")


async def wipe_database():
    """Сбросить все таблицы в базе данных."""
    print("🗄️  Сброс базы данных...")
    
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    
    database_url = get_database_url()
    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Сбрасываем active_topic_id для всех чатов
            await session.execute(text("UPDATE chats SET active_topic_id = NULL"))
            print("   ✅ active_topic_id сброшен")
        except Exception as e:
            print(f"   ⚠️  Ошибка сброса active_topic_id: {e}")
        
        try:
            # Очищаем таблицу сообщений
            result = await session.execute(text("DELETE FROM messages"))
            print(f"   ✅ Удалено сообщений: {result.rowcount}")
        except Exception as e:
            print(f"   ⚠️  Ошибка очистки messages: {e}")
        
        try:
            # Очищаем историю вопросов
            result = await session.execute(text("DELETE FROM user_question_history"))
            print(f"   ✅ Удалено записей истории: {result.rowcount}")
        except Exception as e:
            print(f"   ⚠️  Ошибка очистки user_question_history: {e}")
        
        await session.commit()
    
    await engine.dispose()
    print("   ✅ База данных очищена")


def wipe_vector_memory():
    """Удалить векторную базу данных (ChromaDB)."""
    print("🧠 Сброс векторной памяти...")
    
    chromadb_path = get_chromadb_path()
    
    if chromadb_path.exists():
        shutil.rmtree(chromadb_path)
        print(f"   ✅ Удалена директория: {chromadb_path}")
    else:
        print(f"   ℹ️  Директория не существует: {chromadb_path}")
    
    # Создаём пустую директорию
    chromadb_path.mkdir(parents=True, exist_ok=True)
    print(f"   ✅ Создана пустая директория: {chromadb_path}")


def restore_default_knowledge():
    """Восстановить дефолтные знания в RAG."""
    print("📚 Восстановление дефолтных знаний...")
    
    try:
        from app.services.vector_db import vector_db
        
        if not vector_db.client:
            # Переинициализируем после вайпа
            vector_db.init_db()
        
        if not vector_db.client:
            print("   ⚠️  ChromaDB не инициализирована, пропускаем восстановление")
            return
        
        collection_name = get_collection_name()
        result = vector_db.load_default_knowledge(collection_name)
        
        if result.get("error"):
            print(f"   ⚠️  Ошибка: {result['error']}")
        else:
            print(f"   ✅ Загружено {result['loaded']} фактов из {result['categories']} категорий")
            print(f"   📌 Версия базы знаний: {result.get('version', 'unknown')}")
            
    except ImportError as e:
        print(f"   ⚠️  Не удалось импортировать vector_db: {e}")
    except Exception as e:
        print(f"   ❌ Ошибка восстановления: {e}")


async def main(skip_confirm: bool = False, restore_knowledge: bool = True):
    print("=" * 50)
    print("🔥 ПОЛНЫЙ ВАЙП ДАННЫХ БОТА")
    print("=" * 50)
    print()
    
    if restore_knowledge:
        print("ℹ️  После вайпа будут восстановлены дефолтные знания")
    else:
        print("⚠️  Дефолтные знания НЕ будут восстановлены (--no-restore)")
    print()
    
    # Подтверждение
    if not skip_confirm:
        confirm = input("Вы уверены? Это удалит ВСЕ данные! (yes/no): ")
        if confirm.lower() != "yes":
            print("❌ Отменено")
            return
    
    print()
    
    # Вайп векторной памяти
    wipe_vector_memory()
    
    # Вайп базы данных
    await wipe_database()
    
    # Восстановление дефолтных знаний
    if restore_knowledge:
        print()
        restore_default_knowledge()
    
    print()
    print("=" * 50)
    print("✅ ВАЙП ЗАВЕРШЁН")
    print("=" * 50)
    print()
    print("Перезапустите бота для применения изменений.")


if __name__ == "__main__":
    import sys
    skip = "--yes" in sys.argv or "-y" in sys.argv
    no_restore = "--no-restore" in sys.argv
    asyncio.run(main(skip_confirm=skip, restore_knowledge=not no_restore))
