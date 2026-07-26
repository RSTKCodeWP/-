"""Debug why ergonomics drops from 57 to 30."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_clients import TarkovAPIClient
from services.quest_build_service import QuestBuildService

async def test():
    """Debug ergonomics drop."""
    api = TarkovAPIClient()
    service = QuestBuildService(api)
    
    try:
        print("=" * 70)
        print("Отладка падения эргономики")
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
            return
        
        # Get buildWeapon objective
        objectives = target_quest.get('objectives', [])
        build_obj = None
        for obj in objectives:
            if obj.get('type') == 'buildWeapon':
                build_obj = obj
                break
        
        # Parse requirements
        requirements = service.parse_quest_requirements(build_obj)
        weapon_id = requirements.weapon_id
        
        print(f"\n1. Загрузка деталей оружия: {weapon_id}")
        weapon_details = await api.get_weapon_details(weapon_id)
        
        if not weapon_details:
            print("❌ Не удалось загрузить детали!")
            return
        
        props = weapon_details.get('properties', {})
        
        print(f"\n2. Базовая эргономика оружия: {props.get('ergonomics', 0)}")
        
        # Get default preset
        default_preset = props.get('defaultPreset')
        if default_preset:
            contained_items = default_preset.get('containsItems', [])
            
            print(f"\n3. Модули из defaultPreset: {len(contained_items)}")
            
            preset_ergo = props.get('ergonomics', 0)
            for item in contained_items:
                item_data = item.get('item')
                if item_data:
                    item_props = item_data.get('properties', {})
                    ergo = item_props.get('ergonomics', 0)
                    if ergo:
                        preset_ergo += ergo
                        print(f"   {item_data.get('name')}: {ergo:+} эргономики")
            
            print(f"\n4. Итоговая эргономика preset: {preset_ergo}")
        
        # Now generate build
        print(f"\n5. Запуск оптимизации...")
        build = await service.generate_quest_build(requirements, "ru")
        
        if build:
            final_ergo = build['stats'].get('ergonomics', 0)
            print(f"\n6. Эргономика после оптимизации: {final_ergo}")
            
            print(f"\n📊 Модули в финальной сборке: {len(build['modules'])}")
            for mod in build['modules']:
                print(f"   - {mod.get('name')} (slot: {mod.get('slot')})")
            
            if final_ergo < preset_ergo:
                print(f"\n⚠️ ПРОБЛЕМА: эргономика УПАЛА с {preset_ergo} до {final_ergo}!")
                print(f"   Разница: {final_ergo - preset_ergo}")
        
    finally:
        await api.close()

if __name__ == "__main__":
    asyncio.run(test())
