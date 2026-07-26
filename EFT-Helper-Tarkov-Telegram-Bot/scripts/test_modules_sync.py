"""Test script to check modules API sync."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_clients import TarkovAPIClient

async def main():
    """Test weapons and modules loading from API."""
    api = TarkovAPIClient()
    
    try:
        print("Clearing cache and testing API limits...\n")
        api.cache.clear()
        
        print("Testing weapons API...")
        weapons_en = await api.get_all_weapons('en')
        print(f"✅ Weapons fetched: {len(weapons_en)}")
        
        print("\nTesting modules API...")
        mods_en = await api.get_all_mods('en')
        print(f"✅ Modules fetched: {len(mods_en)}")
        
        print(f"\n" + "="*50)
        print(f"TOTAL: {len(weapons_en)} weapons + {len(mods_en)} modules")
        print("="*50)
        
    finally:
        await api.close()

if __name__ == "__main__":
    asyncio.run(main())
