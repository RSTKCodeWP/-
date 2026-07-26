"""Script to populate the database with sample data for testing."""
import asyncio
import aiosqlite
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database, WeaponCategory, BuildCategory, TierRating


async def populate_sample_data(db: Database):
    """Populate database with sample EFT data."""
    
    async with aiosqlite.connect(db.db_path) as conn:
        # Clear existing data (except users)
        print("   🗑️  Очистка старых данных...")
        await conn.execute("DELETE FROM builds")
        await conn.execute("DELETE FROM modules")
        await conn.execute("DELETE FROM weapons")
        await conn.execute("DELETE FROM traders")
        await conn.execute("DELETE FROM quests")
        await conn.commit()
        
        # Add traders
        print("   👥 Добавление торговцев...")
        traders = [
            ("Prapor", "🔫"),
            ("Therapist", "💊"),
            ("Fence", "🗑️"),
            ("Skier", "💼"),
            ("Peacekeeper", "🤝"),
            ("Mechanic", "🔧"),
            ("Ragman", "👕"),
            ("Jaeger", "🌲")
        ]
        
        for trader_name, emoji in traders:
            await conn.execute(
                "INSERT OR IGNORE INTO traders (name, emoji) VALUES (?, ?)",
                (trader_name, emoji)
            )
        await conn.commit()
        
        # Add weapons with characteristics
        print("   🔫 Добавление оружия...")
        # Format: name_ru, name_en, category, tier_rating, base_price, caliber, ergonomics, recoil_v, recoil_h, fire_rate, eff_range
        weapons = [
            ("AK-74N", "AK-74N", WeaponCategory.ASSAULT_RIFLE.value, TierRating.A_TIER.value, 35000, "5.45x39mm", 42, 180, 85, 650, 400),
            ("AK-74M", "AK-74M", WeaponCategory.ASSAULT_RIFLE.value, TierRating.A_TIER.value, 42000, "5.45x39mm", 45, 175, 82, 650, 400),
            ("AKM", "AKM", WeaponCategory.ASSAULT_RIFLE.value, TierRating.B_TIER.value, 38000, "7.62x39mm", 38, 230, 110, 600, 400),
            ("M4A1", "M4A1", WeaponCategory.ASSAULT_RIFLE.value, TierRating.S_TIER.value, 65000, "5.56x45mm", 55, 120, 65, 800, 400),
            ("HK 416", "HK 416", WeaponCategory.ASSAULT_RIFLE.value, TierRating.S_TIER.value, 72000, "5.56x45mm", 58, 110, 62, 850, 400),
            ("MP-153", "MP-153", WeaponCategory.SHOTGUN.value, TierRating.B_TIER.value, 15000, "12ga", 35, 280, 150, 30, 50),
            ("MP5", "MP5", WeaponCategory.SMG.value, TierRating.A_TIER.value, 28000, "9x19mm", 65, 95, 48, 800, 100),
            ("PP-19-01 Витязь", "PP-19-01 Vityaz", WeaponCategory.SMG.value, TierRating.B_TIER.value, 22000, "9x19mm", 58, 105, 52, 700, 100),
            ("СВД", "SVD", WeaponCategory.DMR.value, TierRating.A_TIER.value, 55000, "7.62x54mmR", 22, 320, 160, 600, 800),
            ("Мосин", "Mosin", WeaponCategory.SNIPER.value, TierRating.C_TIER.value, 25000, "7.62x54mmR", 15, 380, 180, 30, 800),
            ("СВ-98", "SV-98", WeaponCategory.SNIPER.value, TierRating.B_TIER.value, 48000, "7.62x54mmR", 18, 350, 170, 30, 800),
            ("ПМ", "PM", WeaponCategory.PISTOL.value, TierRating.D_TIER.value, 5000, "9x18mm", 75, 140, 75, 30, 50),
            ("Glock 17", "Glock 17", WeaponCategory.PISTOL.value, TierRating.B_TIER.value, 12000, "9x19mm", 85, 95, 50, 30, 100),
            ("ПКМ", "PKM", WeaponCategory.LMG.value, TierRating.A_TIER.value, 95000, "7.62x54mmR", 25, 280, 145, 650, 600),
        ]
        
        for weapon in weapons:
            await conn.execute(
                """INSERT INTO weapons 
                (name_ru, name_en, category, tier_rating, base_price, caliber, ergonomics, 
                 recoil_vertical, recoil_horizontal, fire_rate, effective_range) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                weapon
            )
        await conn.commit()
        
        # Add modules
        print("   🔧 Добавление модулей...")
        modules = [
            # AK-74N modules
            ("Цевье Zenit B-10M", "Zenit B-10M handguard", 12500, "Skier", 2, "handguard"),
            ("Приклад Zenit PT-1", "Zenit PT-1 stock", 28000, "Skier", 3, "stock"),
            ("Прицел ПКА", "PKA sight", 8500, "Prapor", 2, "sight"),
            ("Рукоять RK-3", "RK-3 grip", 4200, "Mechanic", 1, "grip"),
            ("Глушитель PBS-4", "PBS-4 suppressor", 32000, "Prapor", 3, "muzzle"),
            
            # M4A1 modules
            ("Цевье Daniel Defense RIS II", "Daniel Defense RIS II rail", 45000, "Peacekeeper", 3, "handguard"),
            ("Приклад Magpul MOE", "Magpul MOE stock", 18000, "Mechanic", 2, "stock"),
            ("Прицел EOTech EXPS3", "EOTech EXPS3 sight", 42000, "Peacekeeper", 3, "sight"),
            ("Рукоять Magpul RVG", "Magpul RVG grip", 6500, "Mechanic", 2, "grip"),
            ("Глушитель SilencerCo Saker 556", "SilencerCo Saker 556", 58000, "Peacekeeper", 4, "muzzle"),
            
            # MP-153 modules
            ("Приклад GK-02", "GK-02 stock", 8500, "Jaeger", 2, "stock"),
            ("Цевье Magpul", "Magpul handguard", 15000, "Mechanic", 2, "handguard"),
            ("Коллиматор", "Red dot sight", 5500, "Prapor", 1, "sight"),
            
            # MP5 modules
            ("Цевье Navy", "Navy handguard", 12000, "Mechanic", 2, "handguard"),
            ("Приклад A3", "A3 stock", 9500, "Mechanic", 2, "stock"),
            ("Глушитель SD", "SD suppressor", 38000, "Peacekeeper", 3, "muzzle"),
            
            # SVD modules
            ("Приклад модерн", "Modern stock", 25000, "Jaeger", 3, "stock"),
            ("Оптика ПСО-1", "PSO-1 scope", 18000, "Prapor", 2, "sight"),
            ("Глушитель СВД", "SVD suppressor", 45000, "Jaeger", 4, "muzzle"),
        ]
        
        for module in modules:
            await conn.execute(
                "INSERT INTO modules (name_ru, name_en, price, trader, loyalty_level, slot_type) VALUES (?, ?, ?, ?, ?, ?)",
                module
            )
        await conn.commit()
        
        # Add builds
        print("   📦 Добавление сборок...")
        builds = [
            # AK-74N Meta Build
            {
                "weapon_id": 1,
                "category": BuildCategory.META.value,
                "name_ru": "Мета сборка AK-74N",
                "name_en": "AK-74N Meta Build",
                "total_cost": 120200,
                "min_loyalty_level": 3,
                "modules": json.dumps([1, 2, 3, 4, 5]),
                "planner_link": "https://tarkov-builds.com/example1"
            },
            # AK-74N Quest Build
            {
                "weapon_id": 1,
                "category": BuildCategory.QUEST.value,
                "name_ru": "Квестовая AK-74N",
                "name_en": "Quest AK-74N",
                "quest_name_ru": "Оружейник - Часть 4",
                "quest_name_en": "Gunsmith - Part 4",
                "total_cost": 85000,
                "min_loyalty_level": 2,
                "modules": json.dumps([1, 3, 4]),
                "planner_link": "https://tarkov-builds.com/example2"
            },
            # M4A1 Meta Build
            {
                "weapon_id": 4,
                "category": BuildCategory.META.value,
                "name_ru": "Мета сборка M4A1",
                "name_en": "M4A1 Meta Build",
                "total_cost": 234500,
                "min_loyalty_level": 4,
                "modules": json.dumps([6, 7, 8, 9, 10]),
                "planner_link": "https://tarkov-builds.com/example3"
            },
            # MP-153 Budget Build
            {
                "weapon_id": 6,
                "category": BuildCategory.RANDOM.value,
                "name_ru": "Бюджетная MP-153",
                "name_en": "Budget MP-153",
                "total_cost": 44000,
                "min_loyalty_level": 2,
                "modules": json.dumps([11, 12, 13]),
                "planner_link": None
            },
            # MP5 Quest Build
            {
                "weapon_id": 7,
                "category": BuildCategory.QUEST.value,
                "name_ru": "MP5 для квеста",
                "name_en": "Quest MP5",
                "quest_name_ru": "Каратель - Часть 5",
                "quest_name_en": "The Punisher - Part 5",
                "total_cost": 87500,
                "min_loyalty_level": 3,
                "modules": json.dumps([14, 15, 16]),
                "planner_link": "https://tarkov-builds.com/example4"
            },
            # SVD Meta Build
            {
                "weapon_id": 9,
                "category": BuildCategory.META.value,
                "name_ru": "Мета СВД",
                "name_en": "Meta SVD",
                "total_cost": 143000,
                "min_loyalty_level": 4,
                "modules": json.dumps([17, 18, 19]),
                "planner_link": "https://tarkov-builds.com/example5"
            },
        ]
        
        for build in builds:
            await conn.execute(
                """INSERT INTO builds 
                (weapon_id, category, name_ru, name_en, quest_name_ru, quest_name_en, 
                total_cost, min_loyalty_level, modules, planner_link) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    build["weapon_id"],
                    build["category"],
                    build.get("name_ru"),
                    build.get("name_en"),
                    build.get("quest_name_ru"),
                    build.get("quest_name_en"),
                    build["total_cost"],
                    build["min_loyalty_level"],
                    build["modules"],
                    build.get("planner_link")
                )
            )
        await conn.commit()
        
        # Add quests
        print("   📜 Добавление квестов...")
        quests = [
            {
                "name_ru": "Оружейник - Часть 4",
                "name_en": "Gunsmith - Part 4",
                "description_ru": "Собрать AK-74N с определенными характеристиками для Механика",
                "description_en": "Build an AK-74N with specific stats for Mechanic",
                "required_builds": json.dumps([2])
            },
            {
                "name_ru": "Каратель - Часть 5",
                "name_en": "The Punisher - Part 5",
                "description_ru": "Убить PMC с использованием MP5 с глушителем",
                "description_en": "Kill PMCs using suppressed MP5",
                "required_builds": json.dumps([5])
            }
        ]
        
        for quest in quests:
            await conn.execute(
                """INSERT INTO quests 
                (name_ru, name_en, description_ru, description_en, required_builds) 
                VALUES (?, ?, ?, ?, ?)""",
                (
                    quest["name_ru"],
                    quest["name_en"],
                    quest["description_ru"],
                    quest["description_en"],
                    quest["required_builds"]
                )
            )
        
        await conn.commit()
        print("✅ Тестовые данные успешно добавлены!")
        return True


async def main():
    """Main function to run the population script."""
    print("="*60)
    print("  EFT Helper - Заполнение базы данных")
    print("="*60)
    print()
    
    # Database path relative to root
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "eft_helper.db")
    db = Database(db_path)
    await db.init_db()
    
    success = await populate_sample_data(db)
    
    if success:
        # Automatically load all quest builds
        print("\n" + "="*60)
        print("📋 Автоматическая загрузка квестовых сборок...")
        print("="*60)
        
        from database.quest_builds_data import get_all_quests
        import aiosqlite
        from database import BuildCategory
        
        quests = get_all_quests()
        quest_added = 0
        
        async with aiosqlite.connect(db.db_path) as conn:
            for quest_id, quest_data in quests.items():
                weapon_name = quest_data.get("weapon", "Unknown")
                name_ru = quest_data.get("name_ru", quest_id)
                name_en = quest_data.get("name_en", quest_id)
                
                async with conn.execute(
                    "SELECT id FROM weapons WHERE name_en LIKE ? OR name_ru LIKE ? LIMIT 1",
                    (f"%{weapon_name}%", f"%{weapon_name}%")
                ) as cursor:
                    weapon_row = await cursor.fetchone()
                
                if not weapon_row:
                    continue
                
                weapon_id = weapon_row[0]
                
                async with conn.execute(
                    "SELECT id FROM builds WHERE weapon_id = ? AND quest_name_en = ?",
                    (weapon_id, name_en)
                ) as cursor:
                    existing = await cursor.fetchone()
                
                if not existing:
                    await conn.execute(
                        """INSERT INTO builds 
                        (weapon_id, category, name_ru, name_en, quest_name_ru, quest_name_en,
                         total_cost, min_loyalty_level, modules, planner_link)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (weapon_id, BuildCategory.QUEST.value, name_ru, name_en, 
                         name_ru, name_en, 150000, 2, json.dumps([]), None)
                    )
                    quest_added += 1
            
            await conn.commit()
        
        print(f"\n✅ Загружено квестовых сборок: {quest_added} из {len(quests)}")
        
        print("\n📊 База данных заполнена:")
        print("   • 14 оружий")
        print("   • 19 модулей")
        print("   • 6 сборок")
        print("   • 8 торговцев")
        print(f"   • {quest_added} квестов")
        print("\n🎮 Бот готов к использованию!")
    else:
        print("\n❌ Ошибка при заполнении базы данных")
    
    print("="*60)
    return success


if __name__ == "__main__":
    asyncio.run(main())
