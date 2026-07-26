"""Quick script to populate database with all available data."""
import asyncio
import aiosqlite
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database, BuildCategory, WeaponCategory, TierRating
from database.meta_builds_data import META_BUILDS


async def quick_populate():
    """Quickly populate database with comprehensive weapon and build data."""
    print("="*60)
    print("  БЫСТРОЕ ЗАПОЛНЕНИЕ БАЗЫ ДАННЫХ")
    print("="*60)
    print()
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "eft_helper.db")
    db = Database(db_path)
    await db.init_db()
    
    async with aiosqlite.connect(db.db_path) as conn:
        # 1. Add many more weapons
        print("🔫 Добавление оружия...")
        weapons = [
            # Assault Rifles
            ("АК-74Н", "AK-74N", "assault_rifle", "A", 35000, "5.45x39мм", 42, 180, 85, 650, 400),
            ("АК-74М", "AK-74M", "assault_rifle", "A", 42000, "5.45x39мм", 45, 175, 82, 650, 400),
            ("АКМ", "AKM", "assault_rifle", "B", 38000, "7.62x39мм", 38, 230, 110, 600, 400),
            ("АК-103", "AK-103", "assault_rifle", "B", 45000, "7.62x39мм", 40, 220, 105, 600, 400),
            ("АК-104", "AK-104", "assault_rifle", "B", 42000, "7.62x39мм", 42, 210, 100, 600, 350),
            ("M4A1", "M4A1", "assault_rifle", "S", 65000, "5.56x45мм", 55, 120, 65, 800, 400),
            ("HK 416", "HK 416", "assault_rifle", "S", 72000, "5.56x45мм", 58, 110, 62, 850, 400),
            ("ADAR 2-15", "ADAR 2-15", "assault_rifle", "C", 28000, "5.56x45мм", 48, 150, 75, 800, 400),
            ("TX-15", "TX-15", "assault_rifle", "B", 52000, "5.56x45мм", 52, 130, 68, 800, 400),
            ("АС ВАЛ", "AS VAL", "assault_rifle", "A", 65000, "9x39мм", 48, 180, 90, 900, 300),
            ("ВСС Винторез", "VSS Vintorez", "dmr", "A", 58000, "9x39мм", 42, 210, 105, 900, 400),
            
            # SMGs
            ("МП5", "MP5", "smg", "A", 28000, "9x19мм", 65, 95, 48, 800, 100),
            ("МПХ", "MPX", "smg", "A", 32000, "9x19мм", 68, 90, 45, 850, 100),
            ("ПП-19-01 Витязь", "PP-19-01 Vityaz", "smg", "B", 22000, "9x19мм", 58, 105, 52, 700, 100),
            ("PP-91 Кедр", "PP-91 Kedr", "smg", "C", 12000, "9x18мм", 62, 110, 58, 900, 80),
            ("ППШ-41", "PPSh-41", "smg", "D", 18000, "7.62x25мм", 35, 180, 95, 1000, 100),
            ("П90", "P90", "smg", "S", 48000, "5.7x28мм", 75, 75, 40, 900, 150),
            ("UMP 45", "UMP 45", "smg", "B", 26000, ".45 ACP", 55, 120, 62, 600, 100),
            ("Вектор 45", "Vector 45", "smg", "S", 58000, ".45 ACP", 72, 68, 35, 1100, 100),
            
            # Shotguns
            ("МР-153", "MP-153", "shotgun", "B", 15000, "12к", 35, 280, 150, 30, 50),
            ("МР-155", "MP-155", "shotgun", "B", 18000, "12к", 38, 270, 145, 30, 50),
            ("Сайга-12", "Saiga-12", "shotgun", "A", 35000, "12к", 42, 250, 135, 400, 50),
            ("МР-133", "MP-133", "shotgun", "C", 12000, "12к", 32, 290, 155, 30, 50),
            ("МР-43-1С", "MP-43-1S", "shotgun", "D", 8000, "12к/20к", 25, 320, 170, 30, 40),
            
            # DMRs
            ("СВД", "SVD", "dmr", "A", 55000, "7.62x54ммR", 22, 320, 160, 600, 800),
            ("СВДС", "SVDS", "dmr", "A", 62000, "7.62x54ммR", 25, 310, 155, 600, 800),
            ("SR-25", "SR-25", "dmr", "S", 85000, "7.62x51мм", 35, 240, 125, 700, 800),
            ("М1А", "M1A", "dmr", "A", 68000, "7.62x51мм", 32, 260, 135, 700, 800),
            ("RSASS", "RSASS", "dmr", "S", 95000, "7.62x51мм", 38, 230, 120, 700, 800),
            
            # Sniper Rifles
            ("Мосин", "Mosin", "sniper", "C", 25000, "7.62x54ммR", 15, 380, 180, 30, 800),
            ("СВ-98", "SV-98", "sniper", "B", 48000, "7.62x54ммR", 18, 350, 170, 30, 800),
            ("Т-5000М", "T-5000M", "sniper", "A", 85000, "7.62x51мм", 20, 340, 165, 30, 900),
            ("DVL-10", "DVL-10", "sniper", "S", 125000, "7.62x51мм", 25, 320, 155, 30, 900),
            ("М700", "M700", "sniper", "B", 72000, "7.62x51мм", 22, 330, 160, 30, 850),
            ("AXMC", "AXMC", "sniper", "S", 185000, ".338 Lapua", 28, 380, 185, 30, 1200),
            
            # Pistols
            ("ПМ", "PM", "pistol", "D", 5000, "9x18мм", 75, 140, 75, 30, 50),
            ("АПС", "APS", "pistol", "C", 8000, "9x18мм", 68, 150, 80, 750, 50),
            ("Glock 17", "Glock 17", "pistol", "B", 12000, "9x19мм", 85, 95, 50, 30, 100),
            ("Glock 18C", "Glock 18C", "pistol", "A", 18000, "9x19мм", 82, 105, 55, 1200, 100),
            ("М9А3", "M9A3", "pistol", "B", 14000, "9x19мм", 80, 100, 52, 30, 100),
            ("М45А1", "M45A1", "pistol", "B", 16000, ".45 ACP", 78, 115, 60, 30, 100),
            ("SR-1MP", "SR-1MP", "pistol", "A", 22000, "9x21мм", 88, 85, 45, 30, 150),
            ("ТТ", "TT", "pistol", "D", 6000, "7.62x25мм", 70, 155, 82, 30, 80),
            ("Стечкин", "Stechkin APS", "pistol", "C", 9000, "9x18мм", 65, 160, 85, 750, 50),
            ("FN Five-seveN", "FN Five-seveN", "pistol", "A", 24000, "5.7x28мм", 90, 78, 42, 30, 150),
            
            # LMGs
            ("ПКМ", "PKM", "lmg", "A", 95000, "7.62x54ммR", 25, 280, 145, 650, 600),
            ("РПК-16", "RPK-16", "lmg", "A", 85000, "5.45x39мм", 32, 200, 100, 650, 500),
        ]
        
        weapon_count = 0
        for weapon in weapons:
            try:
                await conn.execute(
                    """INSERT OR IGNORE INTO weapons 
                    (name_ru, name_en, category, tier_rating, base_price, caliber, ergonomics, 
                     recoil_vertical, recoil_horizontal, fire_rate, effective_range) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    weapon
                )
                weapon_count += 1
            except:
                pass
        await conn.commit()
        print(f"   ✅ Добавлено оружия: {weapon_count}")
        
        # 2. Add meta builds from META_BUILDS
        print("⚔️  Добавление мета-сборок...")
        meta_count = 0
        
        for weapon_name, builds in META_BUILDS.items():
            async with conn.execute(
                "SELECT id FROM weapons WHERE name_en LIKE ? OR name_ru LIKE ? LIMIT 1",
                (f"%{weapon_name}%", f"%{weapon_name}%")
            ) as cursor:
                weapon_row = await cursor.fetchone()
            
            if not weapon_row:
                continue
            
            weapon_id = weapon_row[0]
            
            for build_type, build_data in builds.items():
                name_ru = build_data.get("name_ru", f"{weapon_name} {build_type}")
                name_en = build_data.get("name_en", f"{weapon_name} {build_type}")
                
                async with conn.execute(
                    "SELECT id FROM builds WHERE weapon_id = ? AND name_en = ?",
                    (weapon_id, name_en)
                ) as cursor:
                    existing = await cursor.fetchone()
                
                if existing:
                    continue
                
                estimated_cost = build_data.get("estimated_cost", 100000)
                min_loyalty = build_data.get("min_loyalty", 2)
                
                await conn.execute(
                    """INSERT INTO builds 
                    (weapon_id, category, name_ru, name_en, total_cost, min_loyalty_level, modules, planner_link)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (weapon_id, BuildCategory.META.value, name_ru, name_en, 
                     estimated_cost, min_loyalty, json.dumps([]), None)
                )
                meta_count += 1
        
        await conn.commit()
        print(f"   ✅ Добавлено мета-сборок: {meta_count}")
        
        # 3. Add some basic modules
        print("🔧 Добавление модулей...")
        modules = [
            ("Приклад базовый", "Basic stock", 5000, "Prapor", 1, "stock", 5500),
            ("Прицел коллиматор", "Red dot sight", 8000, "Prapor", 1, "sight", 8500),
            ("Рукоять базовая", "Basic grip", 3000, "Mechanic", 1, "grip", 3500),
            ("Цевье стандарт", "Standard handguard", 6000, "Mechanic", 1, "handguard", 6500),
            ("Глушитель универсальный", "Universal suppressor", 35000, "Peacekeeper", 2, "muzzle", 38000),
            ("Магазин расширенный", "Extended magazine", 12000, "Mechanic", 2, "magazine", 13000),
        ]
        
        module_count = 0
        for module in modules:
            try:
                await conn.execute(
                    """INSERT OR IGNORE INTO modules 
                    (name_ru, name_en, price, trader, loyalty_level, slot_type, flea_price) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    module
                )
                module_count += 1
            except:
                pass
        await conn.commit()
        print(f"   ✅ Добавлено модулей: {module_count}")
        
        # Count totals
        async with conn.execute("SELECT COUNT(*) FROM weapons") as cursor:
            total_weapons = (await cursor.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM builds WHERE category = 'meta'") as cursor:
            total_meta = (await cursor.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM builds") as cursor:
            total_builds = (await cursor.fetchone())[0]
    
    print()
    print("="*60)
    print("✅ БАЗА ДАННЫХ ЗАПОЛНЕНА!")
    print("="*60)
    print(f"\n📊 Итого в базе:")
    print(f"   • Оружие: {total_weapons}")
    print(f"   • Все сборки: {total_builds}")
    print(f"   • Мета-сборки: {total_meta}")
    print(f"   • Модули: {module_count}")
    print()
    print("🎮 Теперь перезапустите бота и попробуйте:")
    print("   1. 🔍 Поиск оружия - теперь доступно 50+ вариантов")
    print("   2. ⚔️ Мета-сборки - добавлены все из meta_builds_data.py")
    print("   3. 🎲 Случайная сборка - работает с полным списком оружия")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(quick_populate())
