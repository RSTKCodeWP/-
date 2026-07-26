"""Test loading weapon preset with modules."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_clients import TarkovAPIClient

async def test():
    """Test loading weapon preset."""
    api = TarkovAPIClient()
    
    try:
        print("=" * 70)
        print("Тест загрузки preset оружия")
        print("=" * 70)
        
        # Test with SR-25 (from quest)
        weapon_id = "5df24cf80dee1b22f862e9bc"  # SR-25
        
        print(f"\n1. Загрузка деталей оружия ID: {weapon_id}")
        details = await api.get_weapon_details(weapon_id)
        
        if not details:
            print("❌ Не удалось загрузить детали!")
            return
        
        print(f"\n✅ Оружие: {details.get('name')}")
        
        props = details.get('properties', {})
        preset = props.get('defaultPreset')
        
        if not preset:
            print("\n❌ Нет defaultPreset!")
            return
        
        print(f"\n2. Default Preset:")
        print(f"   ID: {preset.get('id')}")
        print(f"   Name: {preset.get('name')}")
        
        contained_items = preset.get('containsItems', [])
        
        if not contained_items:
            print("\n❌ containsItems пуст!")
            print(f"   Весь preset: {preset}")
            return
        
        print(f"\n3. Найдено модулей в preset: {len(contained_items)}")
        print("\n   Модули:")
        
        total_price = 0
        for i, container in enumerate(contained_items[:20], 1):
            item = container.get('item', {})
            count = container.get('count', 1)
            
            name = item.get('name', 'Unknown')
            price = item.get('avg24hPrice') or 0
            total_price += price * count
            
            item_props = item.get('properties', {})
            ergo = item_props.get('ergonomics', 0)
            recoil_mod = item_props.get('recoilModifier', 0)
            
            print(f"   {i}. {name}")
            print(f"      Цена: {price:,}₽ x{count}")
            if ergo:
                print(f"      Эргономика: {ergo:+}")
            if recoil_mod:
                print(f"      Модификатор отдачи: {recoil_mod:+}%")
        
        if len(contained_items) > 20:
            print(f"   ... и ещё {len(contained_items) - 20} модулей")
        
        print(f"\n💰 Общая стоимость модулей: {total_price:,}₽")
        
        # Base weapon stats
        print(f"\n4. Базовые характеристики:")
        print(f"   Эргономика: {props.get('ergonomics', 0)}")
        print(f"   Вертикальная отдача: {props.get('recoilVertical', 0)}")
        print(f"   Горизонтальная отдача: {props.get('recoilHorizontal', 0)}")
        
        print("\n" + "=" * 70)
        print("✅ Тест завершён успешно!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await api.close()

if __name__ == "__main__":
    asyncio.run(test())
