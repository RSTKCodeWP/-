"""Test quest build optimization algorithm."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_clients import TarkovAPIClient
from services.quest_build_service import QuestBuildService

async def test():
    """Test quest build optimization."""
    api = TarkovAPIClient()
    service = QuestBuildService(api)
    
    try:
        print("=" * 70)
        print("Тест оптимизации квестовой сборки")
        print("=" * 70)
        
        # Get quest tasks
        print("\n1. Загрузка квестов...")
        tasks = await api.get_weapon_build_tasks(lang="ru")
        
        # Test on Gunsmith Part 1 (simpler requirements)
        target_quest = None
        for task in tasks:
            if "Часть 1" in task.get('name', ''):
                target_quest = task
                break
        
        if not target_quest:
            # Fallback to first quest
            target_quest = tasks[0]
        
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
            print(f"     • {req.name} {req.compare_method} {req.value}")
        
        # Generate optimized build
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
        print(f"   Базовая цена: {weapon.get('avg24hPrice', 0):,}₽")
        
        if modules:
            print(f"\n🔧 Установлено модулей: {len(modules)}")
            for i, mod in enumerate(modules[:15], 1):
                mod_name = mod.get('name', 'Unknown')
                mod_price = mod.get('price', 0)
                mod_slot = mod.get('slot')
                
                slot_info = f" ({mod_slot})" if mod_slot else ""
                print(f"   {i}. {mod_name}{slot_info}")
                print(f"      Цена: {mod_price:,}₽")
                
                # Show bonuses if available
                if mod.get('ergonomics'):
                    print(f"      Эргономика: {mod['ergonomics']:+}")
                if mod.get('recoilModifier'):
                    print(f"      Отдача: {mod['recoilModifier']:+}%")
            
            if len(modules) > 15:
                print(f"   ... и ещё {len(modules) - 15} модулей")
        
        print(f"\n📊 Характеристики после оптимизации:")
        
        # Check each requirement
        for req in requirements.requirements:
            if req.value == 0 and req.compare_method == '>=':
                continue
            
            stat_value = stats.get(req.name, 0)
            is_met = service._check_single_requirement(stat_value, req)
            status = "✅" if is_met else "❌"
            
            print(f"   {status} {req.name}: {stat_value:.1f} ({req.compare_method} {req.value})")
        
        print(f"\n💰 Общая стоимость: {build['total_cost']:,}₽")
        
        if meets_req:
            print("\n✅ ВСЕ ТРЕБОВАНИЯ КВЕСТА ВЫПОЛНЕНЫ!")
        else:
            print("\n⚠️ Не все требования выполнены")
            print("   Возможно, требуются модули из определённых слотов")
        
        print("\n" + "=" * 70)
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await api.close()

if __name__ == "__main__":
    asyncio.run(test())
