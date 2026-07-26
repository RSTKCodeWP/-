"""Check available magazines for AK-105 and their ergonomics."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_clients import TarkovAPIClient

async def test():
    """Check magazines."""
    api = TarkovAPIClient()
    
    try:
        # AK-105 weapon ID
        weapon_id = "5ac66d9b5acfc4001633997a"
        
        print("=" * 70)
        print("Доступные магазины для AK-105")
        print("=" * 70)
        
        details = await api.get_weapon_details(weapon_id)
        props = details.get('properties', {})
        slots = props.get('slots', [])
        
        # Find magazine slot
        mag_slot = None
        for slot in slots:
            if 'magazine' in slot.get('name', '').lower():
                mag_slot = slot
                break
        
        if not mag_slot:
            print("❌ Слот Magazine не найден!")
            return
        
        filters = mag_slot.get('filters', {})
        allowed_items = filters.get('allowedItems', [])
        
        print(f"\nНайдено магазинов: {len(allowed_items)}")
        print("\n" + "=" * 70)
        
        # Filter magazines with capacity >= 60
        suitable_mags = []
        for item in allowed_items:
            props = item.get('properties', {})
            capacity = props.get('capacity', 0)
            ergonomics = props.get('ergonomics', 0)
            price = item.get('avg24hPrice') or 0
            
            if capacity >= 60:
                suitable_mags.append({
                    'name': item.get('name'),
                    'capacity': capacity,
                    'ergonomics': ergonomics,
                    'price': price
                })
        
        # Sort by ergonomics (best first)
        suitable_mags.sort(key=lambda x: x['ergonomics'], reverse=True)
        
        print(f"\nМагазины с емкостью ≥60 патронов:\n")
        for i, mag in enumerate(suitable_mags, 1):
            ergo_str = f"{mag['ergonomics']:+}" if mag['ergonomics'] else "0"
            print(f"{i}. {mag['name']}")
            print(f"   Емкость: {mag['capacity']} патронов")
            print(f"   Эргономика: {ergo_str}")
            print(f"   Цена: {mag['price']:,}₽")
            print()
        
        if suitable_mags:
            best = suitable_mags[0]
            print(f"✅ Лучший выбор: {best['name']}")
            print(f"   Эргономика: {best['ergonomics']:+}")
        
        print("=" * 70)
        
    finally:
        await api.close()

if __name__ == "__main__":
    asyncio.run(test())
