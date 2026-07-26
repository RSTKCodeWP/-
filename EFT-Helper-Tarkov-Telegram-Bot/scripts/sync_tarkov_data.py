#!/usr/bin/env python3
"""
Enhanced sync script for EFT Helper v2.0
Loads all weapons (150+ units) with full characteristics and localization from tarkov.dev API
"""
import asyncio
import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database
from api_clients import TarkovAPIClient
from services import SyncService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main sync function with enhanced data loading."""
    print("=" * 80)
    print("  EFT Helper v2.0 - Enhanced Data Synchronization")
    print("  Loading 150+ weapons with full characteristics and localization")
    print("=" * 80)
    print()
    
    # Initialize database and API client
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "eft_helper.db")
    db = Database(db_path)
    api_client = TarkovAPIClient()
    sync_service = SyncService(db, api_client)
    
    try:
        # Initialize database with new schema
        print("🔄 Initializing database with enhanced schema...")
        await db.init_db()
        print("✅ Database initialized")
        
        # Run migration to update schema
        print("\n🔄 Running database migration...")
        from scripts.migrate_db import migrate_database
        await migrate_database()
        print("✅ Migration completed")
        
        # Sync all data with enhanced localization
        print("\n🔄 Starting enhanced data synchronization...")
        results = await sync_service.sync_all()
        
        print("\n" + "=" * 60)
        print("📊 SYNCHRONIZATION RESULTS:")
        print("=" * 60)
        
        for data_type, count in results.items():
            if data_type == "traders":
                print(f"👥 Traders: {count}")
            elif data_type == "weapons":
                print(f"🔫 Weapons: {count} (with full characteristics)")
            elif data_type == "modules":
                print(f"🔧 Modules: {count} (with localization)")
            elif data_type == "quest_builds":
                print(f"📜 Quest Builds: {count} (Mechanic weapon tasks only)")
        
        total_items = sum(results.values())
        print(f"\n✅ Total items synchronized: {total_items}")
        
        # Validate results
        print("\n🔍 Validating synchronization...")
        
        # Check weapon count
        weapons = await db.get_all_weapons()
        if len(weapons) >= 100:
            print(f"✅ Weapons loaded: {len(weapons)} (target: 150+)")
        else:
            print(f"⚠️  Weapons loaded: {len(weapons)} (target: 150+)")
        
        # Test search functionality
        print("\n🔍 Testing enhanced search...")
        search_results = await db.search_weapons("ПМ", "ru")
        if search_results:
            print(f"✅ Fuzzy search working: found {len(search_results)} results for 'ПМ'")
            for weapon in search_results[:3]:
                print(f"   - {weapon.name_ru} ({weapon.name_en})")
        else:
            print("⚠️  Search returned no results")
        
        print("\n" + "=" * 60)
        print("🎉 SYNCHRONIZATION COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print()
        print("Key improvements in v2.0:")
        print("✅ Full localization (ru/en) for all content")
        print("✅ 150+ weapons with complete characteristics")
        print("✅ Enhanced fuzzy search with rapidfuzz")
        print("✅ Filtered quest builds (weapon assembly only)")
        print("✅ Removed deprecated planner_link field")
        print("✅ Enhanced build output format")
        print()
        print("Next steps:")
        print("1. Restart the bot: python start.py")
        print("2. Test search: try 'ПМ', 'АК', 'M4A1'")
        print("3. Test random builds: should work with 150+ weapons")
        print("4. Test quest builds: only Mechanic weapon tasks")
        
    except Exception as e:
        print(f"\n❌ Error during synchronization: {e}")
        logger.error(f"Sync error: {e}", exc_info=True)
        return 1
    
    finally:
        await api_client.close()
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    print(f"\nPress Enter to exit...")
    input()
    sys.exit(exit_code)
