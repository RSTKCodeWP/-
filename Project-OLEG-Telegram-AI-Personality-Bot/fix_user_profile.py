#!/usr/bin/env python3
"""
Скрипт для очистки профиля пользователя от неправильных данных.
Использование: python fix_user_profile.py <username>

Работает напрямую с ChromaDB без импорта app модулей.
"""

import sys
import chromadb
from chromadb.config import Settings

# Путь к ChromaDB (такой же как в app)
CHROMA_PATH = "./data/chroma_db"

# Известные чаты где может быть профиль
KNOWN_CHAT_IDS = [
    -1002175322045,  # Основной чат (из логов)
    1034818952,      # Возможно личка
]


def find_and_clear_profile(username: str):
    """Найти и очистить профиль пользователя по username."""
    username = username.lstrip('@').lower()
    print(f"Ищу профиль @{username}...")
    
    # Подключаемся к ChromaDB
    client = chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False)
    )
    
    found = False
    
    # Получаем список всех коллекций
    collections = client.list_collections()
    print(f"Найдено коллекций: {len(collections)}")
    
    for coll in collections:
        coll_name = coll.name
        if "user_profiles" not in coll_name:
            continue
            
        print(f"\nПроверяю коллекцию: {coll_name}")
        
        try:
            collection = client.get_collection(coll_name)
            
            # Получаем все записи с type=profile
            results = collection.get(
                where={"type": "profile"},
                include=["metadatas", "documents"]
            )
            
            if not results or not results.get('ids'):
                print(f"   Пусто")
                continue
            
            for i, doc_id in enumerate(results['ids']):
                meta = results['metadatas'][i] if results.get('metadatas') else {}
                doc = results['documents'][i] if results.get('documents') else ""
                
                stored_username = meta.get('username', '').lower()
                user_id = meta.get('user_id')
                
                if stored_username == username:
                    found = True
                    print(f"\n✅ Найден профиль:")
                    print(f"   Collection: {coll_name}")
                    print(f"   Doc ID: {doc_id}")
                    print(f"   User ID: {user_id}")
                    print(f"   Username: @{stored_username}")
                    print(f"   Данные: {doc[:300]}...")
                    
                    # Удаляем профиль
                    print(f"\n🗑 Удаляю профиль...")
                    try:
                        collection.delete(ids=[doc_id])
                        print(f"   ✅ Профиль удалён")
                    except Exception as e:
                        print(f"   ❌ Ошибка удаления: {e}")
                    
        except Exception as e:
            print(f"   Ошибка: {e}")
    
    if not found:
        print(f"\n❌ Профиль @{username} не найден в ChromaDB")
    else:
        print(f"\n✅ Готово! Профиль @{username} очищен.")
        print("Новые данные будут собираться заново из сообщений.")
        print("\n⚠️ Не забудь перезапустить бота чтобы очистить кэш в памяти!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python fix_user_profile.py <username>")
        print("Пример: python fix_user_profile.py @Ox58657a7a")
        sys.exit(1)
    
    username = sys.argv[1]
    find_and_clear_profile(username)
