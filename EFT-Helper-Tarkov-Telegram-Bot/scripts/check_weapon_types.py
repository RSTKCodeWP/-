"""Check what weapon types are returned by tarkov.dev API."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_clients import TarkovAPIClient
from collections import Counter

async def check_weapon_types():
    """Check all weapon types from API."""
    api = TarkovAPIClient()
    
    try:
        print("=" * 70)
        print("Проверка типов оружия из tarkov.dev API")
        print("=" * 70)
        
        # Get all weapons
        weapons_en = await api.get_all_weapons(lang="en")
        
        if not weapons_en:
            print("❌ Не удалось получить данные оружия")
            return
        
        print(f"\n✅ Получено оружия: {len(weapons_en)}")
        
        # Collect all weapon types
        all_types = []
        weapon_by_type = {}
        
        for weapon in weapons_en:
            name = weapon.get("shortName", weapon.get("name", "Unknown"))
            types = weapon.get("types", [])
            
            for weapon_type in types:
                all_types.append(weapon_type)
                if weapon_type not in weapon_by_type:
                    weapon_by_type[weapon_type] = []
                weapon_by_type[weapon_type].append(name)
        
        # Count types
        type_counts = Counter(all_types)
        
        print("\n" + "=" * 70)
        print("ТИПЫ ОРУЖИЯ И ИХ КОЛИЧЕСТВО:")
        print("=" * 70)
        
        for weapon_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"\n📌 {weapon_type}: {count} единиц")
            # Show first 5 examples
            examples = weapon_by_type[weapon_type][:5]
            for example in examples:
                print(f"   - {example}")
            if len(weapon_by_type[weapon_type]) > 5:
                print(f"   ... и еще {len(weapon_by_type[weapon_type]) - 5}")
        
        print("\n" + "=" * 70)
        print(f"ВСЕГО УНИКАЛЬНЫХ ТИПОВ: {len(type_counts)}")
        print("=" * 70)
        
        # Show current mapping
        print("\n" + "=" * 70)
        print("ТЕКУЩИЙ МАППИНГ В sync_service.py:")
        print("=" * 70)
        print("""
CATEGORY_MAPPING = {
    "pistol": WeaponCategory.PISTOL,
    "smg": WeaponCategory.SMG,
    "assault-rifle": WeaponCategory.ASSAULT_RIFLE,
    "assault-carbine": WeaponCategory.ASSAULT_RIFLE,
    "marksman-rifle": WeaponCategory.DMR,
    "sniper-rifle": WeaponCategory.SNIPER,
    "shotgun": WeaponCategory.SHOTGUN,
    "machine-gun": WeaponCategory.LMG,
}
        """)
        
        # Find unmapped types
        mapped_types = {
            "pistol", "smg", "assault-rifle", "assault-carbine",
            "marksman-rifle", "sniper-rifle", "shotgun", "machine-gun"
        }
        
        unmapped_types = set(all_types) - mapped_types
        
        if unmapped_types:
            print("\n" + "=" * 70)
            print("⚠️  НЕОПРЕДЕЛЕННЫЕ ТИПЫ (попадут в ASSAULT_RIFLE по умолчанию):")
            print("=" * 70)
            for weapon_type in sorted(unmapped_types):
                count = type_counts[weapon_type]
                print(f"   - {weapon_type}: {count} единиц")
                examples = weapon_by_type[weapon_type][:3]
                for example in examples:
                    print(f"       • {example}")
        
    finally:
        await api.close()

if __name__ == "__main__":
    asyncio.run(check_weapon_types())
