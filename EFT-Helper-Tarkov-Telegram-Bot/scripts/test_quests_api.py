"""Test script to verify quest loading from API."""
import asyncio
import sys
import os
import locale

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_clients import TarkovAPIClient


async def test_quests():
    """Test loading quests from API."""
    print("=" * 60)
    print("  Test zagruzki kvestov iz API")
    print("=" * 60)
    print()
    
    client = TarkovAPIClient()
    
    try:
        print("Loading ALL quests from tarkov.dev API...")
        all_tasks = await client.get_all_tasks()
        
        if not all_tasks:
            print("ERROR: Failed to load quests")
            return
        
        print(f"SUCCESS: Loaded {len(all_tasks)} total quests")
        print()
        
        print("Filtering weapon build related quests...")
        build_tasks = await client.get_weapon_build_tasks()
        
        print(f"SUCCESS: Found {len(build_tasks)} build quests")
        print()
        
        # Group by trader
        traders = {}
        for task in build_tasks:
            trader_data = task.get("trader")
            if not trader_data:
                continue
            trader_name = trader_data.get("name", "Unknown")
            if trader_name not in traders:
                traders[trader_name] = []
            traders[trader_name].append(task)
        
        print("Build quests by trader:")
        for trader_name in sorted(traders.keys()):
            print(f"  {trader_name}: {len(traders[trader_name])} quests")
        print()
        
        # Show all build quests
        print("All build quests:")
        for i, task in enumerate(build_tasks, 1):
            name = task.get("name", "Unknown")
            trader_data = task.get("trader", {})
            trader_name = trader_data.get("name", "Unknown") if trader_data else "Unknown"
            level = task.get("minPlayerLevel", "?")
            print(f"  {i}. {name} ({trader_name}, Lvl {level})")
        
        print()
        print("=" * 60)
        print(f"SUCCESS: Test completed: {len(build_tasks)}/{len(all_tasks)} build quests")
        print("=" * 60)
        
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_quests())
