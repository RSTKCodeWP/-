"""Admin service for statistics and broadcasting."""
import aiosqlite
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class AdminService:
    """Service for admin operations and statistics."""
    
    def __init__(self, db):
        self.db = db
    
    async def get_statistics(self) -> Dict:
        """Get bot statistics."""
        async with aiosqlite.connect(self.db.db_path) as conn:
            # Total users
            async with conn.execute("SELECT COUNT(*) FROM users") as cursor:
                total_users = (await cursor.fetchone())[0]
            
            # Active users (last 24 hours)
            yesterday = int((datetime.now() - timedelta(days=1)).timestamp())
            async with conn.execute(
                "SELECT COUNT(*) FROM users WHERE last_activity > ?", 
                (yesterday,)
            ) as cursor:
                active_users_24h = (await cursor.fetchone())[0] if cursor else 0
            
            # Active users (last 7 days)
            week_ago = int((datetime.now() - timedelta(days=7)).timestamp())
            async with conn.execute(
                "SELECT COUNT(*) FROM users WHERE last_activity > ?", 
                (week_ago,)
            ) as cursor:
                active_users_7d = (await cursor.fetchone())[0] if cursor else 0
            
            # Total builds
            async with conn.execute("SELECT COUNT(*) FROM builds") as cursor:
                total_builds = (await cursor.fetchone())[0]
            
            # Community builds count
            async with conn.execute(
                "SELECT COUNT(*) FROM builds WHERE category = 'community'"
            ) as cursor:
                community_builds = (await cursor.fetchone())[0]
            
            # Total weapons
            async with conn.execute("SELECT COUNT(*) FROM weapons") as cursor:
                total_weapons = (await cursor.fetchone())[0]
            
            # Total modules
            async with conn.execute("SELECT COUNT(*) FROM modules") as cursor:
                total_modules = (await cursor.fetchone())[0]
            
            # User builds count
            async with conn.execute("SELECT COUNT(*) FROM user_builds") as cursor:
                user_builds = (await cursor.fetchone())[0] if cursor else 0
            
            # Language distribution
            async with conn.execute(
                "SELECT language, COUNT(*) FROM users GROUP BY language"
            ) as cursor:
                lang_distribution = dict(await cursor.fetchall())
            
            return {
                "total_users": total_users,
                "active_users_24h": active_users_24h,
                "active_users_7d": active_users_7d,
                "total_builds": total_builds,
                "community_builds": community_builds,
                "user_builds": user_builds,
                "total_weapons": total_weapons,
                "total_modules": total_modules,
                "language_distribution": lang_distribution
            }
    
    async def get_all_user_ids(self) -> List[int]:
        """Get list of all user IDs for broadcasting."""
        async with aiosqlite.connect(self.db.db_path) as conn:
            async with conn.execute("SELECT user_id FROM users") as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    
    async def get_active_user_ids(self, days: int = 7) -> List[int]:
        """Get list of active user IDs (last N days)."""
        timestamp = int((datetime.now() - timedelta(days=days)).timestamp())
        async with aiosqlite.connect(self.db.db_path) as conn:
            async with conn.execute(
                "SELECT user_id FROM users WHERE last_activity > ?",
                (timestamp,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    
    async def update_user_activity(self, user_id: int):
        """Update user's last activity timestamp."""
        timestamp = int(datetime.now().timestamp())
        async with aiosqlite.connect(self.db.db_path) as conn:
            await conn.execute(
                "UPDATE users SET last_activity = ? WHERE user_id = ?",
                (timestamp, user_id)
            )
            await conn.commit()
