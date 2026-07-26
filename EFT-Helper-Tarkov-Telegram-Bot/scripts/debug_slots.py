"""Debug script to check weapon slots and available modules."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_clients import TarkovAPIClient

async def test():
    """Check what slots and modules API returns."""
    api = TarkovAPIClient()
    
    try:
        # AK-102 weapon ID
        weapon_id = "5ac66d015acfc400180ae6e4"
        
        print("=" * 70)
        print("Проверка слотов и модулей AK-102")
        print("=" * 70)
        
        details = await api.get_weapon_details(weapon_id)
        
        if not details:
            print("❌ Не удалось загрузить детали оружия!")
            return
        
        props = details.get('properties', {})
        slots = props.get('slots', [])
        
        print(f"\nНайдено слотов: {len(slots)}")
        print("\n" + "=" * 70)
        
        for i, slot in enumerate(slots, 1):
            slot_name = slot.get('name', 'Unknown')
            slot_id = slot.get('nameId', 'unknown')
            required = slot.get('required', False)
            
            print(f"\n{i}. {slot_name} (ID: {slot_id})")
            print(f"   Required: {required}")
            
            filters = slot.get('filters', {})
            allowed_items = filters.get('allowedItems', [])
            
            print(f"   Доступно модулей: {len(allowed_items)}")
            
            # Show first 5 modules with their properties
            for j, item in enumerate(allowed_items[:5], 1):
                item_name = item.get('name', 'Unknown')
                item_price = item.get('avg24hPrice') or 0
                
                print(f"\n     {j}. {item_name}")
                print(f"        Цена: {item_price:,}₽")
                
                # Check for properties
                item_props = item.get('properties', {})
                if item_props:
                    ergo = item_props.get('ergonomics', 0)
                    recoil_mod = item_props.get('recoilModifier', 0)
                    
                    if ergo:
                        print(f"        Эргономика: {ergo:+}")
                    if recoil_mod:
                        print(f"        Модификатор отдачи: {recoil_mod:+}%")
                else:
                    print(f"        ⚠️ Нет properties!")
            
            if len(allowed_items) > 5:
                print(f"\n     ... и ещё {len(allowed_items) - 5} модулей")
        
        print("\n" + "=" * 70)
        
    finally:
        await api.close()

if __name__ == "__main__":
    asyncio.run(test())
