"""Check builds in database."""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database


async def check_builds():
    """Check builds data in database."""
    from database.config import settings
    db = Database(settings.DATABASE_PATH)
    
    print("=" * 60)
    print("CHECKING BUILDS IN DATABASE")
    print("=" * 60)
    
    # Check what tables exist
    import aiosqlite
    async with aiosqlite.connect(db.db_path) as conn:
        # List all tables
        async with conn.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
            tables = await cursor.fetchall()
            print("\nTables in database:")
            for table in tables:
                print(f"  - {table[0]}")
        
        # Check if builds table exists
        if not any('build' in t[0].lower() for t in tables):
            print("\n❌ No builds table found in database!")
            print("\nNote: Loyalty builds require pre-created builds in the database.")
            print("Dynamic builds generate on-the-fly using the API.")
            return
        
        # Total builds
        async with conn.execute("SELECT COUNT(*) FROM builds") as cursor:
            row = await cursor.fetchone()
            total_builds = row[0]
            print(f"\nTotal builds in DB: {total_builds}")
        
        # Builds by category
        async with conn.execute("SELECT category, COUNT(*) FROM builds GROUP BY category") as cursor:
            rows = await cursor.fetchall()
            print("\nBuilds by category:")
            for category, count in rows:
                print(f"  {category}: {count}")
        
        # Check weapon IDs
        async with conn.execute("SELECT DISTINCT weapon_id FROM builds") as cursor:
            rows = await cursor.fetchall()
            weapon_ids = [r[0] for r in rows]
            print(f"\nUnique weapon IDs in builds: {len(weapon_ids)}")
            print(f"Sample weapon IDs: {weapon_ids[:10]}")
        
        # Check if those weapon IDs exist in weapons table
        if weapon_ids:
            placeholders = ','.join('?' * len(weapon_ids[:10]))
            async with conn.execute(
                f"SELECT id FROM weapons WHERE id IN ({placeholders})",
                weapon_ids[:10]
            ) as cursor:
                existing_weapons = await cursor.fetchall()
                print(f"\nWeapons found in DB for those IDs: {len(existing_weapons)}/{min(10, len(weapon_ids))}")
        
        # Sample builds
        async with conn.execute("SELECT * FROM builds LIMIT 5") as cursor:
            rows = await cursor.fetchall()
            print("\nSample builds:")
            for row in rows:
                print(f"  Build ID={row[0]}, weapon_id={row[1]}, category={row[2]}, total_cost={row[6]}")


if __name__ == "__main__":
    asyncio.run(check_builds())
