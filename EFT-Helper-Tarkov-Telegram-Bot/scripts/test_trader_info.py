"""Test trader information display in quest builds."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_clients import TarkovAPIClient
from services.quest_build_service import QuestBuildService

async def test():
    """Test trader info."""
    api = TarkovAPIClient()
    service = QuestBuildService(api)
    
    try:
        print("=" * 70)
        print("Тест отображения информации о торговцах")
        print("=" * 70)
        
        # Get quest tasks
        tasks = await api.get_weapon_build_tasks(lang="ru")
        
        # Find Gunsmith Part 10
        target_quest = None
        for task in tasks:
            if "Часть 10" in task.get('name', ''):
                target_quest = task
                break
        
        if not target_quest:
            print("❌ Квест не найден!")
            return
        
        print(f"\n✅ Квест найден: {target_quest.get('name')}")
        
        # Get buildWeapon objective
        objectives = target_quest.get('objectives', [])
        build_obj = None
        for obj in objectives:
            if obj.get('type') == 'buildWeapon':
                build_obj = obj
                break
        
        # Parse requirements
        requirements = service.parse_quest_requirements(build_obj)
        
        # Generate build
        print("\n⏳ Генерация сборки...")
        build = await service.generate_quest_build(requirements, "ru")
        
        if not build:
            print("❌ Не удалось сгенерировать сборку!")
            return
        
        print("\n" + "=" * 70)
        print("РЕЗУЛЬТАТ: Информация о торговцах")
        print("=" * 70)
        
        weapon = build['weapon']
        modules = build.get('modules', [])
        
        print(f"\n🔫 Оружие: {weapon.get('name')}")
        print(f"\n🔧 Модули ({len(modules)}):\n")
        
        for i, mod in enumerate(modules[:10], 1):
            name = mod.get('name', 'Unknown')
            price = mod.get('price', 0)
            trader = mod.get('trader', 'Unknown')
            level = mod.get('trader_level', '?')
            trader_price = mod.get('trader_price', 0)
            
            print(f"{i}. {name}")
            print(f"   💰 Барахолка: {price:,}₽")
            
            if trader != 'Flea Market' and trader_price > 0:
                print(f"   👤 {trader} (LL{level}): {trader_price:,}₽")
            elif trader == 'Flea Market':
                print(f"   🏪 Только на барахолке")
            else:
                print(f"   ⚠️ Торговец: {trader}")
            print()
        
        if len(modules) > 10:
            print(f"... и ещё {len(modules) - 10} модулей")
        
        print("=" * 70)
        
    finally:
        await api.close()

if __name__ == "__main__":
    asyncio.run(test())
