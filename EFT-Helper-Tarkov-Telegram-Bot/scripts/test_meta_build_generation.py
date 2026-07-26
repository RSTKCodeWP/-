"""Test meta build generation from API presets."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.build_service import BuildService
from database import Database
from database.config import settings

async def test():
    """Test meta build generation."""
    db = Database("data/eft_helper.db")
    await db.init_db()
    
    service = BuildService(db, None)
    
    print("=" * 70)
    print("Тест генерации метасборок")
    print("=" * 70)
    
    # Test weapons from META_BUILDS
    test_weapons = [
        "AK-74M",
        "M4A1", 
        "HK 416",
        "AKM"
    ]
    
    for weapon_name in test_weapons:
        print(f"\n{'='*70}")
        print(f"Тестируем: {weapon_name}")
        print('='*70)
        
        result = await service.generate_meta_build_from_preset(weapon_name, "ru")
        
        if not result:
            print(f"❌ Не удалось сгенерировать сборку для {weapon_name}")
            continue
        
        weapon = result['weapon']
        modules = result['modules']
        preset_name = result['preset_name']
        total_cost = result['total_cost']
        
        print(f"\n✅ Сборка успешно сгенерирована!")
        print(f"\n🔫 Оружие: {weapon.get('name')}")
        print(f"📦 Preset: {preset_name}")
        print(f"💰 Стоимость: {total_cost:,}₽")
        print(f"\n🔧 Модулей: {len(modules)}")
        
        if modules:
            print("\nПервые 5 модулей:")
            for i, mod in enumerate(modules[:5], 1):
                name = mod.get('name', 'Unknown')
                slot = mod.get('slot', 'Unknown')
                price = mod.get('price', 0)
                trader = mod.get('trader', 'Unknown')
                level = mod.get('trader_level', '?')
                
                # Only show slot if it's determined
                slot_text = f"[{slot}] " if slot and slot != 'Unknown' else ""
                print(f"  {i}. {slot_text}{name}")
                print(f"     💰 {price:,}₽ | 👤 {trader} (LL{level})")
    
    print("\n" + "=" * 70)
    print("✅ Тест завершен")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test())
