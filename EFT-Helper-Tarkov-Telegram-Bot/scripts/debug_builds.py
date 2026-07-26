"""Debug script to check builds in database."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import Database


async def main():
    db = Database("data/eft_helper.db")
    
    print("=" * 80)
    print("Проверка сборок в базе данных")
    print("=" * 80)
    
    # Get all builds
    builds = await db.get_random_build()
    
    if not builds:
        print("❌ Сборок не найдено!")
        return
    
    print(f"\n📦 Случайная сборка:")
    print(f"  ID: {builds.id}")
    print(f"  Weapon ID: {builds.weapon_id}")
    print(f"  Category: {builds.category.value}")
    print(f"  Name RU: {builds.name_ru}")
    print(f"  Name EN: {builds.name_en}")
    print(f"  Total Cost: {builds.total_cost}")
    print(f"  Min Loyalty Level: {builds.min_loyalty_level}")
    print(f"  Modules: {builds.modules}")
    print(f"  Number of modules: {len(builds.modules)}")
    
    # Get weapon
    weapon = await db.get_weapon_by_id(builds.weapon_id)
    if weapon:
        print(f"\n🔫 Оружие:")
        print(f"  Name RU: {weapon.name_ru}")
        print(f"  Name EN: {weapon.name_en}")
        print(f"  Caliber: {weapon.caliber}")
        print(f"  Ergonomics: {weapon.ergonomics}")
        print(f"  Recoil V: {weapon.recoil_vertical}")
        print(f"  Recoil H: {weapon.recoil_horizontal}")
        print(f"  Fire Rate: {weapon.fire_rate}")
        print(f"  Effective Range: {weapon.effective_range}")
    else:
        print("❌ Оружие не найдено!")
    
    # Get modules
    if builds.modules:
        modules = await db.get_modules_by_ids(builds.modules)
        print(f"\n🔧 Модули ({len(modules)} из {len(builds.modules)}):")
        for i, module in enumerate(modules, 1):
            print(f"  {i}. {module.name_ru} ({module.name_en})")
            print(f"     Price: {module.price}, Trader: {module.trader}, LL: {module.loyalty_level}")
    else:
        print("\n⚠️  У сборки нет модулей!")
    
    # Check meta builds
    meta_builds = await db.get_meta_builds()
    print(f"\n📊 Мета-сборки: {len(meta_builds)}")
    for build in meta_builds[:3]:
        print(f"  - {build.name_ru}: {len(build.modules)} модулей")
    
    # Check quest builds
    quest_builds = await db.get_quest_builds()
    print(f"\n📜 Квестовые сборки: {len(quest_builds)}")
    for build in quest_builds[:3]:
        print(f"  - {build.quest_name_ru}: {len(build.modules)} модулей")


if __name__ == "__main__":
    asyncio.run(main())
