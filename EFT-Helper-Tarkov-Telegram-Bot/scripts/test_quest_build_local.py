"""Test quest build generation locally without Telegram."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_clients import TarkovAPIClient
from services.quest_build_service import QuestBuildService

async def test():
    """Test quest build generation."""
    api = TarkovAPIClient()
    service = QuestBuildService(api)
    
    try:
        print("=" * 70)
        print("Тест генерации квестовой сборки")
        print("=" * 70)
        
        # Get quest tasks
        print("\n1. Загрузка квестов Механика...")
        tasks = await api.get_weapon_build_tasks(lang="ru")
        
        if not tasks:
            print("❌ Нет квестов!")
            return
        
        # Test first quest (Gunsmith Part 1)
        quest = tasks[0]
        print(f"\n2. Квест: {quest.get('name')}")
        
        # Get buildWeapon objective
        objectives = quest.get('objectives', [])
        build_obj = None
        for obj in objectives:
            if obj.get('type') == 'buildWeapon':
                build_obj = obj
                break
        
        if not build_obj:
            print("❌ Нет buildWeapon objective!")
            return
        
        # Parse requirements
        print("\n3. Парсинг требований...")
        requirements = service.parse_quest_requirements(build_obj)
        
        if not requirements:
            print("❌ Не удалось распарсить требования!")
            return
        
        print(f"\n   Оружие: {requirements.weapon_name}")
        print(f"   Требования:")
        for req in requirements.requirements:
            # Skip zero requirements
            if req.value == 0 and req.compare_method == '>=':
                continue
            print(f"     • {req.name} {req.compare_method} {req.value}")
        
        # Generate build
        print("\n4. Генерация сборки...")
        build = await service.generate_quest_build(requirements, "ru")
        
        if not build:
            print("❌ Не удалось сгенерировать сборку!")
            return
        
        # Display results
        print("\n" + "=" * 70)
        print("РЕЗУЛЬТАТ")
        print("=" * 70)
        
        weapon = build['weapon']
        modules = build.get('modules', [])
        stats = build['stats']
        meets_req = build['meets_requirements']
        
        print(f"\n🔫 Оружие: {weapon.get('name')}")
        print(f"   Цена: {weapon.get('avg24hPrice', 0):,}₽")
        
        if modules:
            print(f"\n🔧 Установлено модулей: {len(modules)}")
            for i, mod in enumerate(modules[:10], 1):
                print(f"   {i}. {mod['name']} - {mod['price']:,}₽")
            if len(modules) > 10:
                print(f"   ... и ещё {len(modules) - 10} модулей")
        else:
            print("\n⚠️ Нет модулей в default preset")
        
        print(f"\n📊 Характеристики:")
        print(f"   Эргономика: {stats['ergonomics']:.0f}")
        print(f"   Отдача: {stats['recoil']:.0f}")
        print(f"   Прочность: {stats['durability']:.0f}")
        print(f"   Вес: {stats['weight']:.2f} кг")
        
        print(f"\n💰 Общая стоимость: {build['total_cost']:,}₽")
        
        if meets_req:
            print("\n✅ Все требования выполнены!")
        else:
            print("\n❌ Не все требования выполнены")
            print("   Нужны дополнительные модули")
        
        print("\n" + "=" * 70)
        
    finally:
        await api.close()

if __name__ == "__main__":
    asyncio.run(test())
