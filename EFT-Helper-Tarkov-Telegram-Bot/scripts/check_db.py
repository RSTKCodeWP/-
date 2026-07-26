"""Скрипт проверки содержимого базы данных."""
import asyncio
import aiosqlite
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def check_database():
    """Проверка содержимого базы данных."""
    import os
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "eft_helper.db")
    
    print("=" * 60)
    print("  Проверка базы данных EFT Helper")
    print("=" * 60)
    print()
    
    try:
        async with aiosqlite.connect(db_path) as db:
            # Проверка таблиц
            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ) as cursor:
                tables = await cursor.fetchall()
            
            print("📊 Таблицы в базе данных:")
            for table in tables:
                print(f"   - {table[0]}")
            print()
            
            # Проверка содержимого каждой таблицы
            print("📈 Количество записей:")
            
            # Оружие
            async with db.execute("SELECT COUNT(*) FROM weapons") as cursor:
                weapons_count = (await cursor.fetchone())[0]
            print(f"   🔫 Оружие: {weapons_count}")
            
            if weapons_count > 0:
                async with db.execute("SELECT name_ru, category FROM weapons LIMIT 5") as cursor:
                    weapons = await cursor.fetchall()
                print("      Примеры:")
                for weapon in weapons:
                    print(f"        • {weapon[0]} ({weapon[1]})")
            
            # Модули
            async with db.execute("SELECT COUNT(*) FROM modules") as cursor:
                modules_count = (await cursor.fetchone())[0]
            print(f"\n   🔧 Модули: {modules_count}")
            
            # Сборки
            async with db.execute("SELECT COUNT(*) FROM builds") as cursor:
                builds_count = (await cursor.fetchone())[0]
            print(f"   📦 Сборки: {builds_count}")
            
            if builds_count > 0:
                async with db.execute(
                    "SELECT b.id, w.name_ru, b.category FROM builds b "
                    "JOIN weapons w ON b.weapon_id = w.id LIMIT 5"
                ) as cursor:
                    builds = await cursor.fetchall()
                print("      Примеры сборок:")
                for build in builds:
                    print(f"        • {build[1]} - {build[2]}")
            
            # Торговцы
            async with db.execute("SELECT COUNT(*) FROM traders") as cursor:
                traders_count = (await cursor.fetchone())[0]
            print(f"\n   🤝 Торговцы: {traders_count}")
            
            if traders_count > 0:
                async with db.execute("SELECT name FROM traders") as cursor:
                    traders = await cursor.fetchall()
                print("      Список:")
                for trader in traders:
                    print(f"        • {trader[0]}")
            
            # Квесты
            async with db.execute("SELECT COUNT(*) FROM quests") as cursor:
                quests_count = (await cursor.fetchone())[0]
            print(f"\n   📜 Квесты: {quests_count}")
            
            # Пользователи
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                users_count = (await cursor.fetchone())[0]
            print(f"   👥 Пользователи: {users_count}")
            
            print()
            print("=" * 60)
            
            # Итог
            if weapons_count == 0 or traders_count == 0:
                print("⚠️  База данных пуста!")
                print("   Запустите: python populate_db.py")
            else:
                print("✅ База данных заполнена и готова к работе!")
            
            print("=" * 60)
            
    except Exception as e:
        print(f"❌ Ошибка при проверке базы данных: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Главная функция."""
    await check_database()
    input("\nНажмите Enter для выхода...")


if __name__ == "__main__":
    asyncio.run(main())
