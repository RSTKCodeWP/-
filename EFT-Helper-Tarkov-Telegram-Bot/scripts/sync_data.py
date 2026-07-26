"""
Unified script for synchronizing data from tarkov.dev API.
Заменяет: sync_tarkov_data.py, populate_db.py, auto_sync_builds.py
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database
from api_clients import TarkovAPIClient
from services import SyncService


async def sync_from_api():
    """Sync all data from tarkov.dev API."""
    print("=" * 60)
    print("  EFT Helper - Синхронизация с tarkov.dev API")
    print("=" * 60)
    print()
    
    # Initialize components
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "eft_helper.db")
    db = Database(db_path)
    await db.init_db()
    
    api_client = TarkovAPIClient()
    sync_service = SyncService(db, api_client)
    
    try:
        print("📊 Начало синхронизации...\n")
        
        # Sync all data
        results = await sync_service.sync_all()
        
        print("\n" + "=" * 60)
        print("✅ Синхронизация завершена!")
        print("=" * 60)
        print("\n📊 Итого загружено:")
        print(f"   • Торговцы: {results['traders']}")
        print(f"   • Оружие: {results['weapons']}")
        print(f"   • Модули: {results['modules']}")
        print("\n💡 Примечания:")
        print("   • Данные кэшируются на 24 часа")
        print("   • Русские названия будут добавлены позднее")
        print("   • Сборки создаются вручную или через populate_sample_data.py")
        print("\n" + "=" * 60)
        
    finally:
        await api_client.close()


async def populate_sample_data():
    """Populate database with sample test data."""
    from scripts import populate_db
    await populate_db.main()


async def main():
    """Main function with user choice."""
    print("=" * 60)
    print("  EFT Helper - Управление данными")
    print("=" * 60)
    print()
    print("Выберите действие:")
    print("  1. Синхронизация с tarkov.dev API (актуальные данные)")
    print("  2. Заполнить тестовыми данными (быстрый старт)")
    print("  3. Оба варианта (API + тестовые сборки)")
    print()
    
    choice = input("Ваш выбор (1/2/3): ").strip()
    
    if choice == "1":
        await sync_from_api()
    elif choice == "2":
        await populate_sample_data()
    elif choice == "3":
        await sync_from_api()
        print("\n")
        await populate_sample_data()
    else:
        print("❌ Неверный выбор")


if __name__ == "__main__":
    asyncio.run(main())
