"""Script to load all meta builds from meta_builds_data.py into database."""
import asyncio
import aiosqlite
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database, BuildCategory
from database.meta_builds_data import META_BUILDS


async def load_meta_builds():
    """Load all meta builds from META_BUILDS into database."""
    print("="*60)
    print("  Загрузка мета-сборок в базу данных")
    print("="*60)
    print()
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "eft_helper.db")
    db = Database(db_path)
    await db.init_db()
    
    added_count = 0
    skipped_count = 0
    
    async with aiosqlite.connect(db.db_path) as conn:
        for weapon_name, builds in META_BUILDS.items():
            # Try to find weapon in database
            async with conn.execute(
                "SELECT id FROM weapons WHERE name_en LIKE ? OR name_ru LIKE ? LIMIT 1",
                (f"%{weapon_name}%", f"%{weapon_name}%")
            ) as cursor:
                weapon_row = await cursor.fetchone()
            
            if not weapon_row:
                print(f"⚠️  Пропущено: {weapon_name} (оружие не найдено в БД)")
                skipped_count += len(builds)
                continue
            
            weapon_id = weapon_row[0]
            
            for build_type, build_data in builds.items():
                name_ru = build_data.get("name_ru", f"{weapon_name} {build_type}")
                name_en = build_data.get("name_en", f"{weapon_name} {build_type}")
                
                # Check if build already exists
                async with conn.execute(
                    "SELECT id FROM builds WHERE weapon_id = ? AND name_en = ?",
                    (weapon_id, name_en)
                ) as cursor:
                    existing = await cursor.fetchone()
                
                if existing:
                    print(f"⏭️  Уже существует: {name_en}")
                    skipped_count += 1
                    continue
                
                # Insert new build
                estimated_cost = build_data.get("estimated_cost", 100000)
                min_loyalty = build_data.get("min_loyalty", 2)
                
                await conn.execute(
                    """INSERT INTO builds 
                    (weapon_id, category, name_ru, name_en, total_cost, min_loyalty_level, modules, planner_link)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (weapon_id, BuildCategory.META.value, name_ru, name_en, 
                     estimated_cost, min_loyalty, json.dumps([]), None)
                )
                
                print(f"✅ Добавлено: {name_en} (стоимость: {estimated_cost:,} ₽)")
                added_count += 1
        
        await conn.commit()
    
    print()
    print("="*60)
    print(f"✅ Загрузка завершена!")
    print(f"   • Добавлено: {added_count}")
    print(f"   • Пропущено: {skipped_count}")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(load_meta_builds())
