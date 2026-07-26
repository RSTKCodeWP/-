"""Load all modules from tarkov.dev API."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database
from api_clients import TarkovAPIClient
from services.sync_service import SyncService


async def main():
    """Sync modules from API."""
    print("=" * 80)
    print("  ЗАГРУЗКА МОДУЛЕЙ ИЗ TARKOV.DEV API")
    print("=" * 80)
    print()
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "eft_helper.db")
    db = Database(db_path)
    await db.init_db()
    
    api_client = TarkovAPIClient()
    sync_service = SyncService(db, api_client)
    
    try:
        print("📡 Загружаем модули из API...")
        print("   Это займет около минуты...\n")
        
        # Load modules
        module_count = await sync_service.sync_modules()
        
        print(f"\n✅ Загружено модулей: {module_count}")
        
        # Also load weapons
        print("\n📡 Загружаем оружие из API...")
        weapon_count = await sync_service.sync_weapons()
        print(f"✅ Загружено оружия: {weapon_count}")
        
        # Check database
        import aiosqlite
        async with aiosqlite.connect(db.db_path) as conn:
            async with conn.execute("SELECT COUNT(*) FROM modules") as cursor:
                total_modules = (await cursor.fetchone())[0]
            
            async with conn.execute("SELECT COUNT(*) FROM weapons") as cursor:
                total_weapons = (await cursor.fetchone())[0]
            
            async with conn.execute(
                "SELECT slot_type, COUNT(*) FROM modules GROUP BY slot_type"
            ) as cursor:
                module_types = await cursor.fetchall()
        
        print("\n" + "=" * 80)
        print("📊 ИТОГОВАЯ СТАТИСТИКА")
        print("=" * 80)
        print(f"Всего оружия в БД: {total_weapons}")
        print(f"Всего модулей в БД: {total_modules}")
        print(f"\nТипы модулей:")
        for slot_type, count in module_types:
            print(f"  • {slot_type:15} {count:>5} шт.")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await api_client.close()


if __name__ == "__main__":
    asyncio.run(main())
