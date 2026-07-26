"""
Migration script for EFT Helper v3.0
Creates user_builds table and adds new fields to existing tables.
"""
import asyncio
import aiosqlite
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import Database

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def migrate():
    """Run migration to v3.0."""
    db_path = "data/eft_helper.db"
    
    logger.info("=" * 60)
    logger.info("EFT Helper v3.0 Migration")
    logger.info("=" * 60)
    
    # Create backup
    import shutil
    from datetime import datetime
    backup_path = f"data/eft_helper_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    
    if os.path.exists(db_path):
        logger.info(f"Creating backup: {backup_path}")
        shutil.copy2(db_path, backup_path)
        logger.info("✅ Backup created")
    
    # Initialize database (will create user_builds table if it doesn't exist)
    db = Database(db_path)
    await db.init_db()
    logger.info("✅ Database schema updated")
    
    # Add new fields to builds table if they don't exist
    async with aiosqlite.connect(db_path) as conn:
        # Check if is_quest column exists
        cursor = await conn.execute("PRAGMA table_info(builds)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if "is_quest" not in column_names:
            logger.info("Adding is_quest column to builds table...")
            await conn.execute("ALTER TABLE builds ADD COLUMN is_quest BOOLEAN DEFAULT 0")
            logger.info("✅ Added is_quest column")
        
        if "tier_rating" not in column_names:
            logger.info("Adding tier_rating column to builds table...")
            await conn.execute("ALTER TABLE builds ADD COLUMN tier_rating TEXT")
            logger.info("✅ Added tier_rating column")
        
        await conn.commit()
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("Migration completed successfully!")
    logger.info("=" * 60)
    logger.info("")
    logger.info("v3.0 Features:")
    logger.info("  ✅ Dynamic build generation with budget/loyalty constraints")
    logger.info("  ✅ Module compatibility checking")
    logger.info("  ✅ Build quality tier evaluation (S/A/B/C/D)")
    logger.info("  ✅ User build saving and sharing")
    logger.info("  ✅ Community builds viewing")
    logger.info("")
    logger.info("You can now run the bot with: python start.py")


if __name__ == "__main__":
    asyncio.run(migrate())
