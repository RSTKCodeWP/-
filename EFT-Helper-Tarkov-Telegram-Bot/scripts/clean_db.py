"""Очистка базы данных от старых невалидных данных."""
import asyncio
import aiosqlite
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def clean_database():
    """Очистка старых данных."""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "eft_helper.db")
    
    print("=" * 60)
    print("  Очистка базы данных")
    print("=" * 60)
    print()
    
    async with aiosqlite.connect(db_path) as db:
        # 1. Удалить старые сборки
        print("🗑️  Удаление старых сборок...")
        await db.execute("DELETE FROM builds")
        await db.commit()
        print("✅ Сборки удалены")
        
        # 2. Удалить дубликаты оружия (оставить только с API)
        print("\n🔄 Удаление дубликатов оружия...")
        
        # Получить все оружия
        async with db.execute("SELECT id, name_en FROM weapons ORDER BY id") as cursor:
            weapons = await cursor.fetchall()
        
        seen = set()
        to_delete = []
        for weapon_id, name in weapons:
            if name in seen:
                to_delete.append(weapon_id)
            else:
                seen.add(name)
        
        # Удалить дубликаты
        for weapon_id in to_delete:
            await db.execute("DELETE FROM weapons WHERE id = ?", (weapon_id,))
        
        await db.commit()
        print(f"✅ Удалено {len(to_delete)} дубликатов оружия")
        
        # 3. Статистика
        print("\n📊 Текущее состояние:")
        
        async with db.execute("SELECT COUNT(*) FROM weapons") as cursor:
            weapons_count = (await cursor.fetchone())[0]
        print(f"   🔫 Оружие: {weapons_count}")
        
        async with db.execute("SELECT COUNT(*) FROM modules") as cursor:
            modules_count = (await cursor.fetchone())[0]
        print(f"   🔧 Модули: {modules_count}")
        
        async with db.execute("SELECT COUNT(*) FROM builds") as cursor:
            builds_count = (await cursor.fetchone())[0]
        print(f"   📦 Сборки: {builds_count}")
        
        async with db.execute("SELECT COUNT(*) FROM quests") as cursor:
            quests_count = (await cursor.fetchone())[0]
        print(f"   📜 Квесты: {quests_count}")
    
    print()
    print("=" * 60)
    print("✅ Очистка завершена!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(clean_database())
