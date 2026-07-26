"""
League Manager for competitive ranking system.

Implements league assignment based on ELO rating with automatic updates.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class League(Enum):
    """
    Player leagues based on ELO rating.
    
    Each league has a display name, emoji, and ELO range.
    """
    SCRAP = ("scrap", "🔩 Scrap", 0, 500)
    SILICON = ("silicon", "💾 Silicon", 500, 1000)
    QUANTUM = ("quantum", "⚛️ Quantum", 1000, 2000)
    ELITE = ("elite", "👑 Elite", 2000, float('inf'))
    
    def __init__(self, code: str, display_name: str, min_elo: int, max_elo: float):
        self._code = code
        self._display_name = display_name
        self._min_elo = min_elo
        self._max_elo = max_elo
    
    @property
    def code(self) -> str:
        """Database code for the league."""
        return self._code
    
    @property
    def display_name(self) -> str:
        """Human-readable name with emoji."""
        return self._display_name
    
    @property
    def min_elo(self) -> int:
        """Minimum ELO for this league (inclusive)."""
        return self._min_elo
    
    @property
    def max_elo(self) -> float:
        """Maximum ELO for this league (exclusive)."""
        return self._max_elo
    
    def contains_elo(self, elo: int) -> bool:
        """Check if an ELO value falls within this league's range."""
        return self._min_elo <= elo < self._max_elo


@dataclass
class LeagueChange:
    """Result of a league update check."""
    old_league: League
    new_league: League
    changed: bool
    
    @property
    def promoted(self) -> bool:
        """True if player moved to a higher league."""
        return self.changed and self.new_league.min_elo > self.old_league.min_elo
    
    @property
    def demoted(self) -> bool:
        """True if player moved to a lower league."""
        return self.changed and self.new_league.min_elo < self.old_league.min_elo


class LeagueManager:
    """
    Manages player league assignments based on ELO rating.
    
    League boundaries:
    - Scrap: 0-500 ELO
    - Silicon: 500-1000 ELO
    - Quantum: 1000-2000 ELO
    - Elite: 2000+ ELO
    """
    
    # Ordered from lowest to highest for iteration
    LEAGUES_ORDERED = [League.SCRAP, League.SILICON, League.QUANTUM, League.ELITE]
    
    def get_league(self, elo: int) -> League:
        """
        Determine the league for a given ELO rating.
        
        Args:
            elo: Current ELO rating (must be >= 0)
            
        Returns:
            The appropriate League for the ELO value
        """
        # Ensure non-negative ELO
        elo = max(0, elo)
        
        for league in self.LEAGUES_ORDERED:
            if league.contains_elo(elo):
                return league
        
        # Fallback to Elite for any ELO >= 2000
        return League.ELITE
    
    def check_league_change(self, old_elo: int, new_elo: int) -> LeagueChange:
        """
        Check if an ELO change results in a league change.
        
        Args:
            old_elo: Previous ELO rating
            new_elo: New ELO rating
            
        Returns:
            LeagueChange with old/new leagues and whether a change occurred
        """
        old_league = self.get_league(old_elo)
        new_league = self.get_league(new_elo)
        
        return LeagueChange(
            old_league=old_league,
            new_league=new_league,
            changed=old_league != new_league
        )
    
    def get_league_by_code(self, code: str) -> Optional[League]:
        """
        Get a League by its database code.
        
        Args:
            code: League code (e.g., 'scrap', 'silicon')
            
        Returns:
            The matching League or None if not found
        """
        code_lower = code.lower()
        for league in League:
            if league.code == code_lower:
                return league
        return None
    
    def get_progress_to_next(self, elo: int) -> Optional[float]:
        """
        Calculate progress percentage to the next league.
        
        Args:
            elo: Current ELO rating
            
        Returns:
            Progress as 0.0-1.0, or None if already at Elite
        """
        current_league = self.get_league(elo)
        
        if current_league == League.ELITE:
            return None
        
        range_size = current_league.max_elo - current_league.min_elo
        progress_in_league = elo - current_league.min_elo
        
        return min(1.0, max(0.0, progress_in_league / range_size))
    
    def elo_to_next_league(self, elo: int) -> Optional[int]:
        """
        Calculate ELO points needed to reach the next league.
        
        Args:
            elo: Current ELO rating
            
        Returns:
            Points needed, or None if already at Elite
        """
        current_league = self.get_league(elo)
        
        if current_league == League.ELITE:
            return None
        
        return int(current_league.max_elo) - elo


async def update_player_league(user_id: int, new_elo: int) -> LeagueChange:
    """
    Update a player's league based on their new ELO rating.
    
    This function checks if the ELO change results in a league change
    and updates the database accordingly.
    
    Args:
        user_id: The Telegram user ID
        new_elo: The new ELO rating after a match
        
    Returns:
        LeagueChange indicating if and how the league changed
    """
    from app.database.session import async_session
    from app.database.models import UserElo, GameStat
    from sqlalchemy import select, update
    
    manager = LeagueManager()
    new_league = manager.get_league(new_elo)
    
    async with async_session() as session:
        # Get current league from UserElo table
        result = await session.execute(
            select(UserElo).where(UserElo.user_id == user_id)
        )
        user_elo = result.scalar_one_or_none()
        
        if user_elo:
            old_league = manager.get_league_by_code(user_elo.league) or League.SCRAP
            
            # Update ELO and league
            await session.execute(
                update(UserElo)
                .where(UserElo.user_id == user_id)
                .values(elo=new_elo, league=new_league.code)
            )
        else:
            # Create new UserElo record
            old_league = League.SCRAP
            user_elo = UserElo(
                user_id=user_id,
                elo=new_elo,
                league=new_league.code
            )
            session.add(user_elo)
        
        # Also update GameStat if it exists
        await session.execute(
            update(GameStat)
            .where(GameStat.tg_user_id == user_id)
            .values(elo_rating=new_elo, league=new_league.code)
        )
        
        await session.commit()
    
    return LeagueChange(
        old_league=old_league,
        new_league=new_league,
        changed=old_league != new_league
    )


# Singleton instance for convenience
league_manager = LeagueManager()


@dataclass
class LeagueStatus:
    """Status of a player's league standing."""
    user_id: int
    elo: int
    league: League
    progress_to_next: float
    elo_to_next: Optional[int]
    is_top_10: bool = False


class LeagueService:
    """
    Service for managing player leagues and ELO ratings.
    
    Provides high-level operations for:
    - Getting player league status
    - Updating ELO after matches
    - Checking league changes
    """
    
    def __init__(self):
        self.manager = LeagueManager()
    
    async def get_status(self, user_id: int, session) -> LeagueStatus:
        """
        Get the current league status for a player.
        
        Args:
            user_id: The Telegram user ID
            session: Database session
            
        Returns:
            LeagueStatus with current ELO, league, and progress
        """
        from app.database.models import UserElo, GameStat
        from sqlalchemy import select, func
        
        # Try to get from UserElo first
        result = await session.execute(
            select(UserElo).where(UserElo.user_id == user_id)
        )
        user_elo = result.scalar_one_or_none()
        
        if user_elo:
            elo = user_elo.elo
        else:
            # Fall back to GameStat
            result = await session.execute(
                select(GameStat).where(GameStat.tg_user_id == user_id)
            )
            game_stat = result.scalar_one_or_none()
            elo = game_stat.elo_rating if game_stat else 1000
        
        league = self.manager.get_league(elo)
        progress = self.manager.get_progress_to_next(elo)
        elo_to_next = self.manager.elo_to_next_league(elo)
        
        # Check if player is in top 10
        top_10_result = await session.execute(
            select(UserElo.user_id)
            .order_by(UserElo.elo.desc())
            .limit(10)
        )
        top_10_ids = [row[0] for row in top_10_result.fetchall()]
        is_top_10 = user_id in top_10_ids
        
        return LeagueStatus(
            user_id=user_id,
            elo=elo,
            league=league,
            progress_to_next=progress if progress is not None else 1.0,
            elo_to_next=elo_to_next,
            is_top_10=is_top_10
        )
    
    async def update_elo(
        self,
        winner_id: int,
        loser_id: int,
        session
    ) -> tuple[LeagueStatus, LeagueStatus]:
        """
        Update ELO ratings after a match.
        
        Args:
            winner_id: The winner's Telegram user ID
            loser_id: The loser's Telegram user ID
            session: Database session
            
        Returns:
            Tuple of (winner_status, loser_status) with updated ELO
        """
        from app.database.models import UserElo, GameStat
        from app.services.elo import elo_calculator
        from sqlalchemy import select
        
        # Get current ELO for both players
        winner_result = await session.execute(
            select(UserElo).where(UserElo.user_id == winner_id)
        )
        winner_elo_record = winner_result.scalar_one_or_none()
        
        loser_result = await session.execute(
            select(UserElo).where(UserElo.user_id == loser_id)
        )
        loser_elo_record = loser_result.scalar_one_or_none()
        
        # Get current ELO values (default 1000)
        winner_current_elo = winner_elo_record.elo if winner_elo_record else 1000
        loser_current_elo = loser_elo_record.elo if loser_elo_record else 1000
        
        # Calculate ELO changes
        elo_change = elo_calculator.calculate(winner_current_elo, loser_current_elo)
        
        # Update or create winner's ELO record
        winner_new_league = self.manager.get_league(elo_change.winner_new_elo)
        if winner_elo_record:
            winner_elo_record.elo = elo_change.winner_new_elo
            winner_elo_record.league = winner_new_league.code
            winner_elo_record.season_wins += 1
        else:
            winner_elo_record = UserElo(
                user_id=winner_id,
                elo=elo_change.winner_new_elo,
                league=winner_new_league.code,
                season_wins=1
            )
            session.add(winner_elo_record)
        
        # Update or create loser's ELO record
        loser_new_league = self.manager.get_league(elo_change.loser_new_elo)
        if loser_elo_record:
            loser_elo_record.elo = elo_change.loser_new_elo
            loser_elo_record.league = loser_new_league.code
        else:
            loser_elo_record = UserElo(
                user_id=loser_id,
                elo=elo_change.loser_new_elo,
                league=loser_new_league.code,
                season_wins=0
            )
            session.add(loser_elo_record)
        
        await session.flush()
        
        # Get updated statuses
        winner_status = LeagueStatus(
            user_id=winner_id,
            elo=elo_change.winner_new_elo,
            league=winner_new_league,
            progress_to_next=self.manager.get_progress_to_next(elo_change.winner_new_elo) or 1.0,
            elo_to_next=self.manager.elo_to_next_league(elo_change.winner_new_elo),
            is_top_10=False  # Will be recalculated if needed
        )
        
        loser_status = LeagueStatus(
            user_id=loser_id,
            elo=elo_change.loser_new_elo,
            league=loser_new_league,
            progress_to_next=self.manager.get_progress_to_next(elo_change.loser_new_elo) or 1.0,
            elo_to_next=self.manager.elo_to_next_league(elo_change.loser_new_elo),
            is_top_10=False
        )
        
        return winner_status, loser_status
    
    async def get_elo(self, user_id: int, session) -> int:
        """
        Get the current ELO for a player.
        
        Args:
            user_id: The Telegram user ID
            session: Database session
            
        Returns:
            Current ELO rating (default 1000)
        """
        from app.database.models import UserElo
        from sqlalchemy import select
        
        result = await session.execute(
            select(UserElo).where(UserElo.user_id == user_id)
        )
        user_elo = result.scalar_one_or_none()
        
        return user_elo.elo if user_elo else 1000


# Singleton instance for league service
league_service = LeagueService()
