"""Test script to check quest objectives structure."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_clients import TarkovAPIClient

async def main():
    """Test quest objectives parsing."""
    api = TarkovAPIClient()
    
    try:
        print("Fetching Gunsmith quests...\n")
        
        # Get weapon build tasks
        tasks = await api.get_weapon_build_tasks(lang="ru")
        
        print(f"Found {len(tasks)} weapon build quests\n")
        print("="*70)
        
        # Show first 3 quests with detailed objectives
        for i, task in enumerate(tasks[:3], 1):
            print(f"\n{i}. {task.get('name')}")
            print(f"   ID: {task.get('id')}")
            print(f"   Level: {task.get('minPlayerLevel')}")
            
            objectives = task.get('objectives', [])
            print(f"\n   Objectives ({len(objectives)}):")
            
            for j, obj in enumerate(objectives, 1):
                obj_type = obj.get('type', 'unknown')
                description = obj.get('description', 'No description')
                optional = obj.get('optional', False)
                
                print(f"     {j}. Type: {obj_type}")
                print(f"        Description: {description}")
                print(f"        Optional: {optional}")
                
                # Check if there's target/count data
                target = obj.get('target', [])
                count = obj.get('count')
                if target:
                    print(f"        Target: {target}")
                if count:
                    print(f"        Count: {count}")
                print()
            
            print("-"*70)
        
        print("\n\nChecking if objectives contain weapon requirements...")
        
        # Look for buildWeapon type objectives
        for task in tasks:
            objectives = task.get('objectives', [])
            for obj in objectives:
                if 'buildweapon' in obj.get('type', '').lower():
                    print(f"\n✅ Found buildWeapon objective in: {task.get('name')}")
                    print(f"   Full objective: {obj}")
                    break
        
    finally:
        await api.close()

if __name__ == "__main__":
    asyncio.run(main())
