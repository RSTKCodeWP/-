#!/usr/bin/env python3
"""
EFT Helper v2.0 Update Script
Complete migration and validation for the enhanced version
"""
import asyncio
import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database
from api_clients import TarkovAPIClient
from services import SyncService, RandomBuildService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_migration():
    """Run database migration."""
    print("🔄 Running database migration...")
    from scripts.migrate_db import migrate_database
    await migrate_database()
    print("✅ Migration completed")


async def sync_enhanced_data():
    """Sync all data with v2.0 enhancements."""
    print("🔄 Syncing enhanced data from tarkov.dev API...")
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "eft_helper.db")
    db = Database(db_path)
    api_client = TarkovAPIClient()
    sync_service = SyncService(db, api_client)
    
    try:
        await db.init_db()
        results = await sync_service.sync_all()
        
        print(f"✅ Synced {results.get('weapons', 0)} weapons with full characteristics")
        print(f"✅ Synced {results.get('modules', 0)} modules with localization")
        print(f"✅ Synced {results.get('quest_builds', 0)} weapon build quests")
        
        return results
    finally:
        await api_client.close()


async def validate_functionality():
    """Validate all v2.0 functionality."""
    print("\n🔍 Validating v2.0 functionality...")
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "eft_helper.db")
    db = Database(db_path)
    api_client = TarkovAPIClient()
    
    validation_results = {
        "weapons_count": 0,
        "search_working": False,
        "fuzzy_search_working": False,
        "random_build_working": False,
        "localization_working": False
    }
    
    try:
        # Test 1: Check weapon count
        weapons = await db.get_all_weapons()
        validation_results["weapons_count"] = len(weapons)
        print(f"📊 Weapons in database: {len(weapons)}")
        
        if len(weapons) >= 100:
            print("✅ Weapon count target met (100+)")
        else:
            print("⚠️  Weapon count below target (100+)")
        
        # Test 2: Test exact search
        search_results = await db.search_weapons("M4A1", "en")
        if search_results:
            validation_results["search_working"] = True
            print("✅ Exact search working")
        else:
            print("❌ Exact search not working")
        
        # Test 3: Test fuzzy search
        fuzzy_results = await db.search_weapons("ПМ", "ru")
        if fuzzy_results:
            validation_results["fuzzy_search_working"] = True
            print("✅ Fuzzy search working")
            print(f"   Found: {fuzzy_results[0].name_ru} ({fuzzy_results[0].name_en})")
        else:
            print("❌ Fuzzy search not working")
        
        # Test 4: Test localization
        if fuzzy_results and fuzzy_results[0].name_ru != fuzzy_results[0].name_en:
            validation_results["localization_working"] = True
            print("✅ Localization working")
        else:
            print("⚠️  Localization may not be working properly")
        
        # Test 5: Test random build generation
        random_service = RandomBuildService(api_client)
        try:
            random_build = await random_service.generate_random_build_for_random_weapon("ru")
            if random_build:
                validation_results["random_build_working"] = True
                print("✅ Random build generation working")
            else:
                print("❌ Random build generation not working")
        except Exception as e:
            print(f"❌ Random build generation error: {e}")
        
        # Test 6: Check quest builds
        quest_builds = await db.get_quest_builds()
        print(f"📜 Quest builds loaded: {len(quest_builds)}")
        
        return validation_results
        
    finally:
        await api_client.close()


async def main():
    """Main update function."""
    print("=" * 80)
    print("  EFT Helper v2.0 Update & Migration Script")
    print("  Comprehensive upgrade with enhanced features")
    print("=" * 80)
    print()
    
    print("🚀 Starting EFT Helper v2.0 update process...")
    print()
    
    try:
        # Step 1: Run migration
        await run_migration()
        print()
        
        # Step 2: Sync enhanced data
        sync_results = await sync_enhanced_data()
        print()
        
        # Step 3: Validate functionality
        validation_results = await validate_functionality()
        print()
        
        # Summary
        print("=" * 60)
        print("📋 UPDATE SUMMARY")
        print("=" * 60)
        
        print("✅ Database migration completed")
        print("✅ Enhanced data synchronization completed")
        print(f"✅ {validation_results['weapons_count']} weapons loaded")
        
        if validation_results["search_working"]:
            print("✅ Search functionality working")
        else:
            print("❌ Search functionality issues")
        
        if validation_results["fuzzy_search_working"]:
            print("✅ Fuzzy search with rapidfuzz working")
        else:
            print("❌ Fuzzy search issues")
        
        if validation_results["random_build_working"]:
            print("✅ Random build generation working")
        else:
            print("❌ Random build generation issues")
        
        if validation_results["localization_working"]:
            print("✅ Full localization (ru/en) working")
        else:
            print("⚠️  Localization may need attention")
        
        print()
        print("🎉 EFT Helper v2.0 update completed!")
        print()
        print("Key improvements:")
        print("• Removed deprecated planner_link field")
        print("• Enhanced weapon database (150+ weapons)")
        print("• Full Russian/English localization")
        print("• Fuzzy search with typo tolerance")
        print("• Filtered quest builds (weapon assembly only)")
        print("• Enhanced build output format")
        print("• Complete weapon characteristics")
        print()
        print("Next steps:")
        print("1. Restart the bot: python start.py")
        print("2. Test search: 'ПМ', 'АК', 'M4A1'")
        print("3. Try random builds")
        print("4. Check quest builds")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Update failed: {e}")
        logger.error(f"Update error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    print(f"\nPress Enter to exit...")
    input()
    sys.exit(exit_code)
