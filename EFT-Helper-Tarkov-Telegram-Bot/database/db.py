"""Database management for the EFT Helper bot."""
import aiosqlite
import json
import logging
from typing import List, Optional
from .models import (
    Weapon, Module, Build, Quest, Trader, User, UserBuild,
    BuildCategory, WeaponCategory, TierRating
)

logger = logging.getLogger(__name__)


class Database:
    """Database manager for SQLite operations."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def init_db(self):
        """Initialize database tables."""
        async with aiosqlite.connect(self.db_path) as db:
            # Weapons table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS weapons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name_ru TEXT NOT NULL,
                    name_en TEXT NOT NULL,
                    category TEXT NOT NULL,
                    tier_rating TEXT,
                    base_price INTEGER DEFAULT 0,
                    flea_price INTEGER,
                    caliber TEXT,
                    ergonomics INTEGER,
                    recoil_vertical INTEGER,
                    recoil_horizontal INTEGER,
                    fire_rate INTEGER,
                    effective_range INTEGER
                )
            """)
            
            # Modules table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS modules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name_ru TEXT NOT NULL,
                    name_en TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    trader TEXT NOT NULL,
                    loyalty_level INTEGER NOT NULL,
                    slot_type TEXT NOT NULL,
                    flea_price INTEGER
                )
            """)
            
            # Builds table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS builds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    weapon_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    name_ru TEXT,
                    name_en TEXT,
                    quest_name_ru TEXT,
                    quest_name_en TEXT,
                    total_cost INTEGER DEFAULT 0,
                    min_loyalty_level INTEGER DEFAULT 1,
                    modules TEXT,
                    FOREIGN KEY (weapon_id) REFERENCES weapons (id)
                )
            """)
            
            # Quests table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS quests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name_ru TEXT NOT NULL,
                    name_en TEXT NOT NULL,
                    description_ru TEXT NOT NULL,
                    description_en TEXT NOT NULL,
                    required_builds TEXT
                )
            """)
            
            # Traders table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS traders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    emoji TEXT NOT NULL
                )
            """)
            
            # Users table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    language TEXT DEFAULT 'ru',
                    favorite_builds TEXT,
                    trader_levels TEXT,
                    last_activity INTEGER DEFAULT 0
                )
            """)
            
            # User builds table (for v3.0 dynamic build system)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_builds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    weapon_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    modules TEXT NOT NULL,
                    total_cost INTEGER NOT NULL,
                    tier_rating TEXT NOT NULL,
                    ergonomics INTEGER,
                    recoil_vertical INTEGER,
                    recoil_horizontal INTEGER,
                    is_public BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    likes INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (weapon_id) REFERENCES weapons (id)
                )
            """)
            
            await db.commit()
    
    # User operations
    async def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT user_id, language, favorite_builds, trader_levels FROM users WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    favorites = json.loads(row[2]) if row[2] else []
                    trader_levels = json.loads(row[3]) if row[3] else None
                    return User(user_id=row[0], language=row[1], favorite_builds=favorites, trader_levels=trader_levels)
                return None
    
    async def create_user(self, user_id: int, language: str = "ru") -> User:
        """Create a new user."""
        from utils.constants import DEFAULT_TRADER_LEVELS
        
        default_trader_levels = json.dumps(DEFAULT_TRADER_LEVELS)
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT INTO users (user_id, language, favorite_builds, trader_levels) VALUES (?, ?, ?, ?)",
                    (user_id, language, "[]", default_trader_levels)
                )
                await db.commit()
                logger.info(f"Created new user: {user_id}")
            except Exception as e:
                logger.error(f"Error creating user {user_id}: {e}")
                raise
        return User(user_id=user_id, language=language, favorite_builds=[])
    
    async def update_user_language(self, user_id: int, language: str):
        """Update user's language preference."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET language = ? WHERE user_id = ?",
                (language, user_id)
            )
            await db.commit()
    
    async def update_trader_levels(self, user_id: int, trader_levels: dict):
        """Update user's trader loyalty levels."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET trader_levels = ? WHERE user_id = ?",
                (json.dumps(trader_levels), user_id)
            )
            await db.commit()
    
    async def get_or_create_user(self, user_id: int) -> User:
        """Get existing user or create new one."""
        user = await self.get_user(user_id)
        if not user:
            user = await self.create_user(user_id)
        return user
    
    # Weapon operations
    async def get_weapon_by_id(self, weapon_id: int) -> Optional[Weapon]:
        """Get weapon by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """SELECT id, name_ru, name_en, category, tier_rating, base_price, flea_price,
                   caliber, ergonomics, recoil_vertical, recoil_horizontal, fire_rate, effective_range, tarkov_id 
                   FROM weapons WHERE id = ?""",
                (weapon_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return Weapon(
                        id=row[0],
                        name_ru=row[1],
                        name_en=row[2],
                        category=WeaponCategory(row[3]),
                        tier_rating=TierRating(row[4]) if row[4] else None,
                        base_price=row[5],
                        flea_price=row[6],
                        tarkov_id=row[13],
                        caliber=row[7],
                        ergonomics=row[8],
                        recoil_vertical=row[9],
                        recoil_horizontal=row[10],
                        fire_rate=row[11],
                        effective_range=row[12]
                    )
                return None
    
    async def search_weapons(self, query: str, language: str = "ru") -> List[Weapon]:
        """Search weapons by name with fuzzy matching."""
        from rapidfuzz import fuzz, process
        
        # Безопасная проверка языка для предотвращения SQL injection
        if language not in ("ru", "en"):
            language = "ru"
        
        async with aiosqlite.connect(self.db_path) as db:
            # First try exact/partial matches
            async with db.execute(
                """SELECT id, name_ru, name_en, category, tier_rating, base_price, flea_price,
                   caliber, ergonomics, recoil_vertical, recoil_horizontal, fire_rate, effective_range,
                   velocity, default_width, default_height
                   FROM weapons 
                   WHERE name_ru LIKE ? OR name_en LIKE ? 
                   LIMIT 15""",
                (f"%{query}%", f"%{query}%")
            ) as cursor:
                exact_rows = await cursor.fetchall()
            
            # If we have good exact matches, return them
            if len(exact_rows) >= 5:
                return [self._row_to_weapon(row) for row in exact_rows[:10]]
            
            # Otherwise, get all weapons for fuzzy matching
            async with db.execute(
                """SELECT id, name_ru, name_en, category, tier_rating, base_price, flea_price,
                   caliber, ergonomics, recoil_vertical, recoil_horizontal, fire_rate, effective_range,
                   velocity, default_width, default_height
                   FROM weapons"""
            ) as cursor:
                all_rows = await cursor.fetchall()
            
            # Prepare data for fuzzy matching
            weapons_data = []
            for row in all_rows:
                weapon = self._row_to_weapon(row)
                search_name = weapon.name_ru if language == "ru" else weapon.name_en
                weapons_data.append((weapon, search_name))
            
            # Perform fuzzy matching
            weapon_names = [data[1] for data in weapons_data]
            matches = process.extract(query, weapon_names, scorer=fuzz.partial_ratio, limit=10)
            
            # Filter matches with score > 60 and combine with exact matches
            fuzzy_results = []
            seen_ids = set()
            
            # Add exact matches first
            for row in exact_rows:
                weapon = self._row_to_weapon(row)
                fuzzy_results.append(weapon)
                seen_ids.add(weapon.id)
            
            # Add fuzzy matches
            for match_name, score, _ in matches:
                if score > 60:  # Minimum similarity threshold
                    for weapon, name in weapons_data:
                        if name == match_name and weapon.id not in seen_ids:
                            fuzzy_results.append(weapon)
                            seen_ids.add(weapon.id)
                            break
            
            return fuzzy_results[:10]
    
    def _row_to_weapon(self, row) -> Weapon:
        """Convert database row to Weapon object."""
        return Weapon(
            id=row[0],
            name_ru=row[1],
            name_en=row[2],
            category=WeaponCategory(row[3]),
            tier_rating=TierRating(row[4]) if row[4] else None,
            base_price=row[5],
            flea_price=row[6],
            caliber=row[7],
            ergonomics=row[8],
            recoil_vertical=row[9],
            recoil_horizontal=row[10],
            fire_rate=row[11],
            effective_range=row[12]
        )
    
    async def get_all_weapons(self) -> List[Weapon]:
        """Get all weapons."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """SELECT id, name_ru, name_en, category, tier_rating, base_price, flea_price,
                   caliber, ergonomics, recoil_vertical, recoil_horizontal, fire_rate, effective_range 
                   FROM weapons"""
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    Weapon(
                        id=row[0],
                        name_ru=row[1],
                        name_en=row[2],
                        category=WeaponCategory(row[3]),
                        tier_rating=TierRating(row[4]) if row[4] else None,
                        base_price=row[5],
                        flea_price=row[6],
                        caliber=row[7],
                        ergonomics=row[8],
                        recoil_vertical=row[9],
                        recoil_horizontal=row[10],
                        fire_rate=row[11],
                        effective_range=row[12]
                    )
                    for row in rows
                ]
    
    # Build operations
    async def get_builds_by_weapon(self, weapon_id: int, category: Optional[BuildCategory] = None) -> List[Build]:
        """Get builds for a specific weapon."""
        async with aiosqlite.connect(self.db_path) as db:
            if category:
                query = "SELECT * FROM builds WHERE weapon_id = ? AND category = ?"
                params = (weapon_id, category.value)
            else:
                query = "SELECT * FROM builds WHERE weapon_id = ?"
                params = (weapon_id,)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_build(row) for row in rows]
    
    async def get_build_by_id(self, build_id: int) -> Optional[Build]:
        """Get build by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM builds WHERE id = ?", (build_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_build(row)
                return None
    
    async def get_random_build(self) -> Optional[Build]:
        """Get a random build from the database."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM builds ORDER BY RANDOM() LIMIT 1") as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_build(row)
                return None
    
    async def get_meta_builds(self) -> List[Build]:
        """Get all meta builds."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM builds WHERE category = ?",
                (BuildCategory.META.value,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_build(row) for row in rows]
    
    async def get_quest_builds(self) -> List[Build]:
        """Get all quest builds."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM builds WHERE category = ?",
                (BuildCategory.QUEST.value,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_build(row) for row in rows]
    
    async def get_builds_by_loyalty(self, trader: str, loyalty_level: int) -> List[Build]:
        """Get builds available at specific trader loyalty level."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM builds WHERE min_loyalty_level <= ?",
                (loyalty_level,)
            ) as cursor:
                rows = await cursor.fetchall()
                builds = [self._row_to_build(row) for row in rows]
                
                # Filter builds that have modules available from the trader
                filtered_builds = []
                for build in builds:
                    modules = await self.get_modules_by_ids(build.modules)
                    if all(m.trader == trader and m.loyalty_level <= loyalty_level for m in modules):
                        filtered_builds.append(build)
                
                return filtered_builds
    
    def _row_to_build(self, row) -> Build:
        """Convert database row to Build object."""
        modules = json.loads(row[9]) if row[9] else []
        return Build(
            id=row[0],
            weapon_id=row[1],
            category=BuildCategory(row[2]),
            name_ru=row[3],
            name_en=row[4],
            quest_name_ru=row[5],
            quest_name_en=row[6],
            total_cost=row[7],
            min_loyalty_level=row[8],
            modules=modules
        )
    
    # Module operations
    async def get_module_by_id(self, module_id: int) -> Optional[Module]:
        """Get module by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT id, name_ru, name_en, price, trader, loyalty_level, slot_type, flea_price FROM modules WHERE id = ?",
                (module_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return Module(
                        id=row[0],
                        name_ru=row[1],
                        name_en=row[2],
                        price=row[3],
                        trader=row[4],
                        loyalty_level=row[5],
                        slot_type=row[6],
                        flea_price=row[7]
                    )
                return None
    
    async def get_modules_by_ids(self, module_ids: List[int]) -> List[Module]:
        """Get multiple modules by their IDs."""
        if not module_ids:
            return []
        
        async with aiosqlite.connect(self.db_path) as db:
            placeholders = ",".join("?" * len(module_ids))
            async with db.execute(
                f"SELECT id, name_ru, name_en, price, trader, loyalty_level, slot_type, flea_price, tarkov_id, slot_name FROM modules WHERE id IN ({placeholders})",
                module_ids
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    Module(
                        id=row[0],
                        name_ru=row[1],
                        name_en=row[2],
                        price=row[3],
                        tarkov_id=row[8],
                        slot_name=row[9],
                        trader=row[4],
                        loyalty_level=row[5],
                        slot_type=row[6],
                        flea_price=row[7]
                    )
                    for row in rows
                ]
    
    # Trader operations
    async def get_all_traders(self) -> List[Trader]:
        """Get all traders."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM traders") as cursor:
                rows = await cursor.fetchall()
                return [Trader(id=row[0], name=row[1], emoji=row[2]) for row in rows]
    
    # Quest operations
    async def get_all_quests(self) -> List[Quest]:
        """Get all quests."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM quests") as cursor:
                rows = await cursor.fetchall()
                return [
                    Quest(
                        id=row[0],
                        name_ru=row[1],
                        name_en=row[2],
                        description_ru=row[3],
                        description_en=row[4],
                        required_builds=json.loads(row[5]) if row[5] else []
                    )
                    for row in rows
                ]
    
    # User builds operations (v3.0)
    async def create_user_build(self, user_build: UserBuild) -> int:
        """Create a new user build and return its ID."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO user_builds 
                   (user_id, weapon_id, name, modules, total_cost, tier_rating, 
                    ergonomics, recoil_vertical, recoil_horizontal, is_public)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_build.user_id, user_build.weapon_id, user_build.name,
                 json.dumps(user_build.modules), user_build.total_cost,
                 user_build.tier_rating.value, user_build.ergonomics,
                 user_build.recoil_vertical, user_build.recoil_horizontal,
                 user_build.is_public)
            )
            await db.commit()
            return cursor.lastrowid
    
    async def get_user_build_by_id(self, build_id: int) -> Optional[UserBuild]:
        """Get user build by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """SELECT id, user_id, weapon_id, name, modules, total_cost, tier_rating,
                   ergonomics, recoil_vertical, recoil_horizontal, is_public, 
                   created_at, likes FROM user_builds WHERE id = ?""",
                (build_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_user_build(row)
                return None
    
    async def get_user_builds(self, user_id: int, limit: int = 50) -> List[UserBuild]:
        """Get all builds created by a specific user."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """SELECT id, user_id, weapon_id, name, modules, total_cost, tier_rating,
                   ergonomics, recoil_vertical, recoil_horizontal, is_public, 
                   created_at, likes FROM user_builds 
                   WHERE user_id = ? ORDER BY created_at DESC LIMIT ?""",
                (user_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_user_build(row) for row in rows]
    
    async def get_public_builds(self, limit: int = 50, offset: int = 0) -> List[UserBuild]:
        """Get public builds from the community."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """SELECT id, user_id, weapon_id, name, modules, total_cost, tier_rating,
                   ergonomics, recoil_vertical, recoil_horizontal, is_public, 
                   created_at, likes FROM user_builds 
                   WHERE is_public = 1 ORDER BY likes DESC, created_at DESC LIMIT ? OFFSET ?""",
                (limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_user_build(row) for row in rows]
    
    async def update_user_build_visibility(self, build_id: int, is_public: bool):
        """Update build visibility."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE user_builds SET is_public = ? WHERE id = ?",
                (is_public, build_id)
            )
            await db.commit()
    
    async def delete_user_build(self, build_id: int, user_id: int):
        """Delete a user build (only by owner)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM user_builds WHERE id = ? AND user_id = ?",
                (build_id, user_id)
            )
            await db.commit()
    
    async def increment_build_likes(self, build_id: int):
        """Increment likes for a build."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE user_builds SET likes = likes + 1 WHERE id = ?",
                (build_id,)
            )
            await db.commit()
    
    def _row_to_user_build(self, row) -> UserBuild:
        """Convert database row to UserBuild object."""
        return UserBuild(
            id=row[0],
            user_id=row[1],
            weapon_id=row[2],
            name=row[3],
            modules=json.loads(row[4]) if row[4] else [],
            total_cost=row[5],
            tier_rating=TierRating(row[6]),
            ergonomics=row[7],
            recoil_vertical=row[8],
            recoil_horizontal=row[9],
            is_public=bool(row[10]),
            created_at=row[11],
            likes=row[12]
        )
