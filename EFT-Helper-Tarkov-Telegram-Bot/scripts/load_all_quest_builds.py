"""Load all quest builds from quest_builds_data.py into database."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database, BuildCategory
from database.quest_builds_data import get_all_quests
import json


async def load_quest_builds():
    """Load all quest builds into database."""
    print("=" * 60)
    print("  Загрузка квестовых сборок")
    print("=" * 60)
    print()
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "eft_helper.db")
    db = Database(db_path)
    await db.init_db()
    
    quests = get_all_quests()
    
    print(f"📋 Найдено {len(quests)} квестов\n")
    
    import aiosqlite
    async with aiosqlite.connect(db.db_path) as conn:
        added_count = 0
        updated_count = 0
        
        for quest_id, quest_data in quests.items():
            weapon_name = quest_data.get("weapon", "Unknown")
            name_ru = quest_data.get("name_ru", quest_id)
            name_en = quest_data.get("name_en", quest_id)
            
            # Find weapon in database
            async with conn.execute(
                "SELECT id FROM weapons WHERE name_en LIKE ? OR name_ru LIKE ? LIMIT 1",
                (f"%{weapon_name}%", f"%{weapon_name}%")
            ) as cursor:
                weapon_row = await cursor.fetchone()
            
            if not weapon_row:
                print(f"  ⚠️  Оружие не найдено: {weapon_name} (пропущено: {name_ru})")
                continue
            
            weapon_id = weapon_row[0]
            
            # Check if quest build already exists
            async with conn.execute(
                "SELECT id FROM builds WHERE weapon_id = ? AND quest_name_en = ?",
                (weapon_id, name_en)
            ) as cursor:
                existing = await cursor.fetchone()
            
            # Calculate approximate cost (placeholder)
            estimated_cost = 150000  # Base quest build cost
            
            if existing:
                # Update existing
                await conn.execute(
                    """UPDATE builds SET 
                    name_ru = ?, name_en = ?, quest_name_ru = ?, quest_name_en = ?,
                    category = ?, total_cost = ?, min_loyalty_level = ?
                    WHERE id = ?""",
                    (name_ru, name_en, name_ru, name_en, 
                     BuildCategory.QUEST.value, estimated_cost, 2, existing[0])
                )
                print(f"  🔄 Обновлено: {name_ru}")
                updated_count += 1
            else:
                # Insert new
                await conn.execute(
                    """INSERT INTO builds 
                    (weapon_id, category, name_ru, name_en, quest_name_ru, quest_name_en,
                     total_cost, min_loyalty_level, modules, planner_link)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (weapon_id, BuildCategory.QUEST.value, name_ru, name_en, 
                     name_ru, name_en, estimated_cost, 2, 
                     json.dumps([]), None)
                )
                print(f"  ✅ Добавлено: {name_ru}")
                added_count += 1
        
        await conn.commit()
    
    print()
    print("=" * 60)
    print("📊 Результат:")
    print(f"   ✅ Добавлено: {added_count}")
    print(f"   🔄 Обновлено: {updated_count}")
    print(f"   📦 Всего квестов: {len(quests)}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(load_quest_builds())
