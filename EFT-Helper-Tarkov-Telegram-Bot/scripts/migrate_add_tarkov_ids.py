"""Migration script to add tarkov_id and slot_name fields for export functionality."""
import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def migrate_database(db_path: str = "data/eft_helper.db"):
    """Add tarkov_id to weapons and modules, slot_name to modules."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Starting migration: Adding tarkov_id and slot_name fields...")
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(weapons)")
        weapons_columns = [col[1] for col in cursor.fetchall()]
        
        cursor.execute("PRAGMA table_info(modules)")
        modules_columns = [col[1] for col in cursor.fetchall()]
        
        # Add tarkov_id to weapons if not exists
        if "tarkov_id" not in weapons_columns:
            print("  Adding tarkov_id to weapons table...")
            cursor.execute("ALTER TABLE weapons ADD COLUMN tarkov_id TEXT")
            print("  ✅ Added tarkov_id to weapons")
        else:
            print("  ⏭️  tarkov_id already exists in weapons")
        
        # Add tarkov_id to modules if not exists
        if "tarkov_id" not in modules_columns:
            print("  Adding tarkov_id to modules table...")
            cursor.execute("ALTER TABLE modules ADD COLUMN tarkov_id TEXT")
            print("  ✅ Added tarkov_id to modules")
        else:
            print("  ⏭️  tarkov_id already exists in modules")
        
        # Add slot_name to modules if not exists
        if "slot_name" not in modules_columns:
            print("  Adding slot_name to modules table...")
            cursor.execute("ALTER TABLE modules ADD COLUMN slot_name TEXT")
            print("  ✅ Added slot_name to modules")
        else:
            print("  ⏭️  slot_name already exists in modules")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database()
