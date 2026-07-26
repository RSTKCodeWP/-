"""Fix builds by adding actual module IDs based on part names."""
import asyncio
import aiosqlite
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database, BuildCategory
from database.meta_builds_data import META_BUILDS


async def find_module_by_name(conn, part_name: str) -> int:
    """Try to find module ID by part name."""
    # Try exact match first
    async with conn.execute(
        "SELECT id FROM modules WHERE name_en LIKE ? OR name_ru LIKE ? LIMIT 1",
        (f"%{part_name}%", f"%{part_name}%")
    ) as cursor:
        row = await cursor.fetchone()
        if row:
            return row[0]
    
    # Try partial match
    words = part_name.split()
    for word in words:
        if len(word) > 3:  # Skip short words
            async with conn.execute(
                "SELECT id FROM modules WHERE name_en LIKE ? OR name_ru LIKE ? LIMIT 1",
                (f"%{word}%", f"%{word}%")
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row[0]
    
    return None


async def fix_builds():
    """Update builds with module IDs."""
    print("="*80)
    print("  Исправление сборок - добавление модулей")
    print("="*80)
    print()
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "eft_helper.db")
    db = Database(db_path)
    
    updated_count = 0
    failed_count = 0
    
    async with aiosqlite.connect(db.db_path) as conn:
        # Get all modules for reference
        async with conn.execute("SELECT id, name_en, name_ru FROM modules") as cursor:
            all_modules = await cursor.fetchall()
            print(f"📦 Всего модулей в базе: {len(all_modules)}\n")
        
        for weapon_name, builds in META_BUILDS.items():
            # Find weapon
            async with conn.execute(
                "SELECT id FROM weapons WHERE name_en LIKE ? OR name_ru LIKE ? LIMIT 1",
                (f"%{weapon_name}%", f"%{weapon_name}%")
            ) as cursor:
                weapon_row = await cursor.fetchone()
            
            if not weapon_row:
                print(f"⚠️  Оружие не найдено: {weapon_name}")
                continue
            
            weapon_id = weapon_row[0]
            
            for build_type, build_data in builds.items():
                name_en = build_data.get("name_en", f"{weapon_name} {build_type}")
                parts = build_data.get("parts", [])
                
                # Find existing build
                async with conn.execute(
                    "SELECT id, modules FROM builds WHERE weapon_id = ? AND name_en = ?",
                    (weapon_id, name_en)
                ) as cursor:
                    build_row = await cursor.fetchone()
                
                if not build_row:
                    print(f"⚠️  Сборка не найдена: {name_en}")
                    failed_count += 1
                    continue
                
                build_id = build_row[0]
                current_modules = json.loads(build_row[1]) if build_row[1] else []
                
                # If already has modules, skip
                if current_modules:
                    print(f"⏭️  Уже имеет модули: {name_en}")
                    continue
                
                # Find module IDs for parts
                module_ids = []
                parts_found = 0
                parts_missing = 0
                
                for part_name in parts:
                    module_id = await find_module_by_name(conn, part_name)
                    if module_id:
                        module_ids.append(module_id)
                        parts_found += 1
                    else:
                        parts_missing += 1
                
                # Update build with module IDs
                if module_ids:
                    # Calculate total cost
                    total_cost = 0
                    max_loyalty = 1
                    
                    for module_id in module_ids:
                        async with conn.execute(
                            "SELECT price, loyalty_level FROM modules WHERE id = ?",
                            (module_id,)
                        ) as cursor:
                            mod_row = await cursor.fetchone()
                            if mod_row:
                                total_cost += mod_row[0]
                                max_loyalty = max(max_loyalty, mod_row[1])
                    
                    await conn.execute(
                        "UPDATE builds SET modules = ?, total_cost = ?, min_loyalty_level = ? WHERE id = ?",
                        (json.dumps(module_ids), total_cost, max_loyalty, build_id)
                    )
                    
                    print(f"✅ {name_en}")
                    print(f"   Модулей: {len(module_ids)}/{len(parts)} (найдено: {parts_found}, не найдено: {parts_missing})")
                    print(f"   Стоимость: {total_cost:,} ₽, Мин LL: {max_loyalty}")
                    updated_count += 1
                else:
                    print(f"❌ {name_en} - модули не найдены")
                    failed_count += 1
        
        await conn.commit()
    
    print()
    print("="*80)
    print(f"✅ Обновление завершено!")
    print(f"   • Обновлено сборок: {updated_count}")
    print(f"   • Не удалось обновить: {failed_count}")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(fix_builds())
