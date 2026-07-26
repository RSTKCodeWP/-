"""Check weapon properties from tarkov.dev API to find category info."""
import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_clients import TarkovAPIClient

async def check_weapon_properties():
    """Check all available properties for weapons."""
    api = TarkovAPIClient()
    output_file = "weapon_properties_report.txt"
    
    try:
        print("=" * 70)
        print("Проверка свойств оружия из tarkov.dev API")
        print("=" * 70)
        
        # Open file for writing
        f = open(output_file, 'w', encoding='utf-8')
        
        # Get weapons
        weapons_en = await api.get_all_weapons(lang="en")
        
        if not weapons_en:
            print("❌ Не удалось получить данные")
            f.close()
            return
        
        print(f"\n✅ Получено оружия: {len(weapons_en)}")
        f.write("=" * 70 + "\n")
        f.write("Проверка свойств оружия из tarkov.dev API\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"✅ Получено оружия: {len(weapons_en)}\n")
        
        # Get examples of different weapon types
        examples = {
            "Пистолет": ["PM", "Glock 17", "M9A3"],
            "ПП": ["MP5", "PP-19-01", "Kedr"],
            "Автомат": ["AK-74M", "M4A1", "HK 416A5"],
            "DMR": ["SVD", "SR-25", "RSASS"],
            "Снайперская": ["SV-98", "M700", "Mosin"],
            "Дробовик": ["MP-153", "Saiga-12", "MP-133"],
            "Пулемет": ["PKM", "RPK-16", "M249"]
        }
        
        for category, weapon_names in examples.items():
            f.write(f"\n{'='*70}\n")
            f.write(f"📌 {category}\n")
            f.write('='*70 + "\n")
            
            for weapon_name in weapon_names:
                # Find weapon
                weapon = None
                for w in weapons_en:
                    name = w.get("shortName", w.get("name", ""))
                    if weapon_name.lower() in name.lower():
                        weapon = w
                        break
                
                if not weapon:
                    f.write(f"\n⚠️  {weapon_name} - не найдено\n")
                    continue
                
                f.write(f"\n🔫 {weapon.get('shortName', weapon.get('name'))}\n")
                f.write(f"   ID: {weapon.get('id')}\n")
                f.write(f"   Types: {weapon.get('types', [])}\n")
                
                # Check for category-related fields
                if 'category' in weapon:
                    f.write(f"   category: {weapon.get('category')}\n")
                
                if 'categoryName' in weapon:
                    f.write(f"   categoryName: {weapon.get('categoryName')}\n")
                
                properties = weapon.get('properties', {})
                if properties:
                    f.write(f"   Properties keys: {list(properties.keys())[:10]}\n")
                    
                    # Check specific fields
                    for field in ['weaponType', 'class', 'type', 'category']:
                        if field in properties:
                            f.write(f"   properties.{field}: {properties.get(field)}\n")
                
                # Check if name contains hints
                name_full = weapon.get('name', '')
                f.write(f"   Full name: {name_full}\n")
        
        # Show full structure of one weapon
        f.write("\n" + "="*70 + "\n")
        f.write("ПОЛНАЯ СТРУКТУРА ОДНОГО ОРУЖИЯ (M4A1):\n")
        f.write("="*70 + "\n")
        
        m4 = None
        for w in weapons_en:
            if "M4A1" in w.get("shortName", ""):
                m4 = w
                break
        
        if m4:
            f.write(json.dumps(m4, indent=2, ensure_ascii=False) + "\n")
        
        f.close()
        print(f"\n✅ Отчет сохранен в файл: {output_file}")
        
    finally:
        await api.close()

if __name__ == "__main__":
    asyncio.run(check_weapon_properties())
