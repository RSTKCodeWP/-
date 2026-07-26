"""Test magazine capacity optimization for Gunsmith Part 10."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_clients import TarkovAPIClient
from services.quest_build_service import QuestBuildService

async def test():
    """Test magazine capacity optimization."""
    api = TarkovAPIClient()
    service = QuestBuildService(api)
    
    try:
        print("=" * 70)
        print("Тест оптимизации емкости магазина (Квест 10)")
        print("=" * 70)
        
        # Get quest tasks
        print("\n1. Загрузка квестов...")
        tasks = await api.get_weapon_build_tasks(lang="ru")
        
        # Find Gunsmith Part 10
        target_quest = None
        for task in tasks:
            if "Часть 10" in task.get('name', ''):
                target_quest = task
                break
        
        if not target_quest:
            print("❌ Квест 'Часть 10' не найден!")
            return
        
        quest_name = target_quest.get('name')
        print(f"\n2. Тестируем квест: {quest_name}")
        
        # Get buildWeapon objective
        objectives = target_quest.get('objectives', [])
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
            if req.value == 0 and req.compare_method == '>=':
                continue
            if req.name == 'magazineCapacity':
                print(f"     • ⭐ {req.name} {req.compare_method} {req.value} (ГЛАВНОЕ ТРЕБОВАНИЕ)")
            else:
                print(f"     • {req.name} {req.compare_method} {req.value}")
        
        # Generate build
        print("\n4. Генерация оптимизированной сборки...")
        build = await service.generate_quest_build(requirements, "ru")
        
        if not build:
            print("❌ Не удалось сгенерировать сборку!")
            return
        
        # Display results
        print("\n" + "=" * 70)
        print("РЕЗУЛЬТАТ ОПТИМИЗАЦИИ")
        print("=" * 70)
        
        weapon = build['weapon']
        modules = build.get('modules', [])
        stats = build['stats']
        meets_req = build['meets_requirements']
        
        print(f"\n🔫 Оружие: {weapon.get('name')}")
        
        # Find magazine
        magazine = None
        for mod in modules:
            if 'magazine' in mod.get('name', '').lower() or 'магазин' in mod.get('name', '').lower():
                magazine = mod
                break
        
        if magazine:
            print(f"\n📦 Выбранный магазин:")
            print(f"   {magazine.get('name')}")
            print(f"   Цена: {magazine.get('price', 0):,}₽")
        
        print(f"\n📊 Характеристики:")
        
        # Check magazineCapacity specifically
        mag_req = next((r for r in requirements.requirements if r.name == 'magazineCapacity'), None)
        if mag_req:
            mag_capacity = stats.get('magazineCapacity', 0)
            is_met = service._check_single_requirement(mag_capacity, mag_req)
            status = "✅" if is_met else "❌"
            
            print(f"   {status} Емкость магазина: {mag_capacity:.0f} ({mag_req.compare_method} {mag_req.value:.0f})")
        
        # Show other important stats
        for req in requirements.requirements:
            if req.name in ['ergonomics', 'recoil', 'durability'] and req.value > 0:
                stat_value = stats.get(req.name, 0)
                is_met = service._check_single_requirement(stat_value, req)
                status = "✅" if is_met else "❌"
                print(f"   {status} {req.name}: {stat_value:.0f} ({req.compare_method} {req.value})")
        
        print(f"\n💰 Общая стоимость: {build['total_cost']:,}₽")
        
        if meets_req:
            print("\n✅ ВСЕ ТРЕБОВАНИЯ КВЕСТА ВЫПОЛНЕНЫ!")
        else:
            print("\n⚠️ Не все требования выполнены")
        
        print("\n" + "=" * 70)
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await api.close()

if __name__ == "__main__":
    asyncio.run(test())
