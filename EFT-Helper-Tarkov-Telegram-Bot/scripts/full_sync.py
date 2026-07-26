"""Full synchronization with tarkov.dev API - loads all data."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database
from api_clients import TarkovAPIClient
from services.sync_service import SyncService


async def main():
    """Full sync of all data from tarkov.dev API."""
    print("=" * 80)
    print("  ПОЛНАЯ СИНХРОНИЗАЦИЯ С TARKOV.DEV API")
    print("=" * 80)
    print()
    
    # Initialize database and API client
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "eft_helper.db")
    db = Database(db_path)
    await db.init_db()
    
    api_client = TarkovAPIClient()
    sync_service = SyncService(db, api_client)
    
    try:
        print("📡 Начинаем загрузку данных из tarkov.dev API...")
        print("   Это может занять несколько минут...\n")
        
        # Perform full sync
        results = await sync_service.sync_all()
        
        print("\n" + "=" * 80)
        print("✅ СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА!")
        print("=" * 80)
        print(f"📊 Статистика:")
        print(f"   • Торговцы: {results.get('traders', 0)}")
        print(f"   • Оружие: {results.get('weapons', 0)}")
        print(f"   • Модули: {results.get('modules', 0)}")
        print(f"   • Квестовые сборки: {results.get('quest_builds', 0)}")
        print("=" * 80)
        
        # Check database stats
        print("\n📦 Проверка содержимого базы данных...")
        
        import aiosqlite
        async with aiosqlite.connect(db.db_path) as conn:
            # Count weapons
            async with conn.execute("SELECT COUNT(*) FROM weapons") as cursor:
                weapon_count = (await cursor.fetchone())[0]
            
            # Count modules
            async with conn.execute("SELECT COUNT(*) FROM modules") as cursor:
                module_count = (await cursor.fetchone())[0]
            
            # Count builds
            async with conn.execute("SELECT COUNT(*) FROM builds") as cursor:
                build_count = (await cursor.fetchone())[0]
            
            # Count traders
            async with conn.execute("SELECT COUNT(*) FROM traders") as cursor:
                trader_count = (await cursor.fetchone())[0]
            
            # Sample weapons with characteristics
            async with conn.execute(
                """SELECT name_en, caliber, ergonomics, recoil_vertical 
                   FROM weapons 
                   WHERE ergonomics IS NOT NULL 
                   LIMIT 5"""
            ) as cursor:
                sample_weapons = await cursor.fetchall()
        
        print(f"   • Оружие в БД: {weapon_count}")
        print(f"   • Модули в БД: {module_count}")
        print(f"   • Сборки в БД: {build_count}")
        print(f"   • Торговцы в БД: {trader_count}")
        
        if sample_weapons:
            print(f"\n📊 Примеры оружия с характеристиками:")
            for weapon in sample_weapons:
                name, caliber, ergo, recoil = weapon
                print(f"   • {name}: {caliber}, Эрго: {ergo}, Отдача: {recoil}")
        
        print("\n" + "=" * 80)
        print("🎉 Готово! Теперь в базе данных полный набор оружия и модулей.")
        print("=" * 80)
        
    finally:
        await api_client.close()


if __name__ == "__main__":
    asyncio.run(main())
