"""Скрипт миграции базы данных для добавления новых полей."""
import asyncio
import aiosqlite
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def migrate_database():
    """Миграция базы данных для версии 2.0 - добавление новых полей и удаление устаревших."""
    import os
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "eft_helper.db")
    
    print("🔄 Начало миграции базы данных для версии 2.0...")
    
    async with aiosqlite.connect(db_path) as db:
        migrations_applied = []
        
        # Миграция 1: Добавление trader_levels в users
        async with db.execute("PRAGMA table_info(users)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
        
        if "trader_levels" not in column_names:
            print("📝 Добавление колонки trader_levels в таблицу users...")
            await db.execute("ALTER TABLE users ADD COLUMN trader_levels TEXT")
            
            default_trader_levels = json.dumps({
                "prapor": 1,
                "therapist": 1,
                "fence": 1,
                "skier": 1,
                "peacekeeper": 1,
                "mechanic": 1,
                "ragman": 1,
                "jaeger": 1
            })
            
            await db.execute(
                "UPDATE users SET trader_levels = ?",
                (default_trader_levels,)
            )
            migrations_applied.append("trader_levels в users")
        
        # Миграция 2: Добавление flea_price в weapons
        async with db.execute("PRAGMA table_info(weapons)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
        
        if "flea_price" not in column_names:
            print("📝 Добавление колонки flea_price в таблицу weapons...")
            await db.execute("ALTER TABLE weapons ADD COLUMN flea_price INTEGER")
            migrations_applied.append("flea_price в weapons")
        
        # Миграция 3: Добавление flea_price в modules
        async with db.execute("PRAGMA table_info(modules)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
        
        if "flea_price" not in column_names:
            print("📝 Добавление колонки flea_price в таблицу modules...")
            await db.execute("ALTER TABLE modules ADD COLUMN flea_price INTEGER")
            migrations_applied.append("flea_price в modules")
        
        # Миграция 4: Добавление velocity в weapons
        async with db.execute("PRAGMA table_info(weapons)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
        
        if "velocity" not in column_names:
            print("📝 Добавление колонки velocity в таблицу weapons...")
            await db.execute("ALTER TABLE weapons ADD COLUMN velocity INTEGER")
            migrations_applied.append("velocity в weapons")
        
        # Миграция 5: Добавление default_width и default_height в weapons
        async with db.execute("PRAGMA table_info(weapons)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
        
        if "default_width" not in column_names:
            print("📝 Добавление колонки default_width в таблицу weapons...")
            await db.execute("ALTER TABLE weapons ADD COLUMN default_width INTEGER")
            migrations_applied.append("default_width в weapons")
        
        if "default_height" not in column_names:
            print("📝 Добавление колонки default_height в таблицу weapons...")
            await db.execute("ALTER TABLE weapons ADD COLUMN default_height INTEGER")
            migrations_applied.append("default_height в weapons")
        
        # Миграция 6: Удаление planner_link из builds (создание новой таблицы без этого поля)
        async with db.execute("PRAGMA table_info(builds)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
        
        if "planner_link" in column_names:
            print("📝 Удаление устаревшего поля planner_link из таблицы builds...")
            
            # Создаем новую таблицу без planner_link
            await db.execute("""
                CREATE TABLE builds_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    weapon_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    name_ru TEXT,
                    name_en TEXT,
                    quest_name_ru TEXT,
                    quest_name_en TEXT,
                    total_cost INTEGER DEFAULT 0,
                    min_loyalty_level INTEGER DEFAULT 1,
                    modules TEXT,
                    FOREIGN KEY (weapon_id) REFERENCES weapons (id)
                )
            """)
            
            # Копируем данные (без planner_link)
            await db.execute("""
                INSERT INTO builds_new 
                (id, weapon_id, category, name_ru, name_en, quest_name_ru, quest_name_en, 
                 total_cost, min_loyalty_level, modules)
                SELECT id, weapon_id, category, name_ru, name_en, quest_name_ru, quest_name_en,
                       total_cost, min_loyalty_level, modules
                FROM builds
            """)
            
            # Удаляем старую таблицу и переименовываем новую
            await db.execute("DROP TABLE builds")
            await db.execute("ALTER TABLE builds_new RENAME TO builds")
            
            migrations_applied.append("удаление planner_link из builds")
        
        # Миграция 7: Обновление таблицы traders для локализации
        async with db.execute("PRAGMA table_info(traders)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
        
        if "name_ru" not in column_names:
            print("📝 Добавление локализации в таблицу traders...")
            await db.execute("ALTER TABLE traders ADD COLUMN name_ru TEXT")
            await db.execute("ALTER TABLE traders ADD COLUMN name_en TEXT")
            
            # Обновляем существующие записи
            await db.execute("UPDATE traders SET name_ru = name, name_en = name")
            
            migrations_applied.append("локализация traders")
        
        await db.commit()
        
        if migrations_applied:
            print("\n✅ Миграция завершена успешно!")
            print("   Применены следующие миграции:")
            for migration in migrations_applied:
                print(f"   - {migration}")
        else:
            print("✅ Все миграции уже применены. База данных актуальна.")


async def main():
    """Главная функция."""
    print("=" * 60)
    print("  EFT Helper - Миграция базы данных")
    print("=" * 60)
    print()
    
    try:
        await migrate_database()
    except Exception as e:
        print(f"❌ Ошибка при миграции: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 60)
    input("\nНажмите Enter для выхода...")


if __name__ == "__main__":
    asyncio.run(main())
