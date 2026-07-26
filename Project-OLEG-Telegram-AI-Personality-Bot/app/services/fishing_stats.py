"""Fishing Statistics Service - Tracks fishing progress and records.

v7.5.1 - Full fishing statistics system.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.database.models import FishingStats

logger = logging.getLogger(__name__)


@dataclass
class FishingStatsData:
    """Fishing statistics data."""
    total_casts: int = 0
    total_earnings: int = 0
    trash_caught: int = 0
    common_caught: int = 0
    uncommon_caught: int = 0
    rare_caught: int = 0
    epic_caught: int = 0
    legendary_caught: int = 0
    biggest_catch_value: int = 0
    biggest_catch_name: Optional[str] = None
    equipped_rod: str = "basic_rod"
    
    @property
    def total_fish(self) -> int:
        """Total fish caught (excluding trash)."""
        return (self.common_caught + self.uncommon_caught + 
                self.rare_caught + self.epic_caught + self.legendary_caught)
    
    @property
    def total_catches(self) -> int:
        """Total catches including trash."""
        return self.total_fish + self.trash_caught
    
    def get_rarity_count(self, rarity: str) -> int:
        """Get count for specific rarity."""
        rarity_map = {
            "trash": self.trash_caught,
            "common": self.common_caught,
            "uncommon": self.uncommon_caught,
            "rare": self.rare_caught,
            "epic": self.epic_caught,
            "legendary": self.legendary_caught,
        }
        return rarity_map.get(rarity.lower(), 0)


class FishingStatsService:
    """Service for managing fishing statistics."""
    
    async def get_stats(self, user_id: int, chat_id: int) -> FishingStatsData:
        """Get fishing stats for user."""
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(FishingStats).where(
                    FishingStats.user_id == user_id,
                    FishingStats.chat_id == chat_id
                )
            )
            stats = result.scalars().first()
            
            if not stats:
                return FishingStatsData()
            
            return FishingStatsData(
                total_casts=stats.total_casts,
                total_earnings=stats.total_earnings,
                trash_caught=stats.trash_caught,
                common_caught=stats.common_caught,
                uncommon_caught=stats.uncommon_caught,
                rare_caught=stats.rare_caught,
                epic_caught=stats.epic_caught,
                legendary_caught=stats.legendary_caught,
                biggest_catch_value=stats.biggest_catch_value,
                biggest_catch_name=stats.biggest_catch_name,
                equipped_rod=stats.equipped_rod,
            )
    
    async def record_catch(
        self, 
        user_id: int, 
        chat_id: int, 
        rarity: str, 
        fish_name: str,
        value: int
    ) -> FishingStatsData:
        """Record a fishing catch."""
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(FishingStats).where(
                    FishingStats.user_id == user_id,
                    FishingStats.chat_id == chat_id
                )
            )
            stats = result.scalars().first()
            
            if not stats:
                stats = FishingStats(
                    user_id=user_id,
                    chat_id=chat_id,
                    total_casts=0,
                    total_earnings=0,
                    trash_caught=0,
                    common_caught=0,
                    uncommon_caught=0,
                    rare_caught=0,
                    epic_caught=0,
                    legendary_caught=0,
                    biggest_catch_value=0,
                )
                session.add(stats)
            
            # Update cast count (handle None values from old records)
            stats.total_casts = (stats.total_casts or 0) + 1
            stats.total_earnings = (stats.total_earnings or 0) + value
            
            # Update rarity count
            rarity_lower = rarity.lower()
            if rarity_lower == "trash":
                stats.trash_caught = (stats.trash_caught or 0) + 1
            elif rarity_lower == "common":
                stats.common_caught = (stats.common_caught or 0) + 1
            elif rarity_lower == "uncommon":
                stats.uncommon_caught = (stats.uncommon_caught or 0) + 1
            elif rarity_lower == "rare":
                stats.rare_caught = (stats.rare_caught or 0) + 1
            elif rarity_lower == "epic":
                stats.epic_caught = (stats.epic_caught or 0) + 1
            elif rarity_lower == "legendary":
                stats.legendary_caught = (stats.legendary_caught or 0) + 1
            
            # Update biggest catch
            current_biggest = stats.biggest_catch_value or 0
            if value > current_biggest:
                stats.biggest_catch_value = value
                stats.biggest_catch_name = fish_name
            
            await session.commit()
            
            return FishingStatsData(
                total_casts=stats.total_casts,
                total_earnings=stats.total_earnings,
                trash_caught=stats.trash_caught,
                common_caught=stats.common_caught,
                uncommon_caught=stats.uncommon_caught,
                rare_caught=stats.rare_caught,
                epic_caught=stats.epic_caught,
                legendary_caught=stats.legendary_caught,
                biggest_catch_value=stats.biggest_catch_value,
                biggest_catch_name=stats.biggest_catch_name,
                equipped_rod=stats.equipped_rod,
            )
    
    async def update_equipped_rod(
        self, user_id: int, chat_id: int, rod_type: str
    ) -> None:
        """Update equipped rod in stats."""
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(FishingStats).where(
                    FishingStats.user_id == user_id,
                    FishingStats.chat_id == chat_id
                )
            )
            stats = result.scalars().first()
            
            if not stats:
                stats = FishingStats(
                    user_id=user_id,
                    chat_id=chat_id,
                    equipped_rod=rod_type
                )
                session.add(stats)
            else:
                stats.equipped_rod = rod_type
            
            await session.commit()
    
    def format_stats(self, stats: FishingStatsData) -> str:
        """Format stats for display."""
        rod_names = {
            "basic_rod": "🎣 Базовая",
            "silver_rod": "🥈 Серебряная",
            "golden_rod": "🥇 Золотая",
            "legendary_rod": "👑 Легендарная",
        }
        rod_name = rod_names.get(stats.equipped_rod, "🎣 Базовая")
        
        lines = [
            "📊 <b>СТАТИСТИКА РЫБАЛКИ</b>\n",
            f"🎣 Удочка: {rod_name}",
            f"🔄 Всего забросов: {stats.total_casts}",
            f"💰 Заработано: {stats.total_earnings} монет\n",
            "<b>Улов по редкости:</b>",
            f"  👟 Мусор: {stats.trash_caught}",
            f"  🐟 Обычная: {stats.common_caught}",
            f"  🐟 Необычная: {stats.uncommon_caught}",
            f"  ⭐ Редкая: {stats.rare_caught}",
            f"  💜 Эпическая: {stats.epic_caught}",
            f"  🌟 Легендарная: {stats.legendary_caught}",
        ]
        
        if stats.biggest_catch_name:
            lines.append(f"\n🏆 Лучший улов: {stats.biggest_catch_name} ({stats.biggest_catch_value} монет)")
        
        return "\n".join(lines)


# Global instance
fishing_stats_service = FishingStatsService()
