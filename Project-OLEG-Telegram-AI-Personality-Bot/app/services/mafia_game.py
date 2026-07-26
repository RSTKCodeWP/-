"""
Mafia Game Service (v9.5.0)

Manages mafia game logic including:
- Lobby creation and player registration
- Role assignment
- Night phase actions (kill, heal, check)
- Day phase voting
- Win condition checking
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    MafiaGame, MafiaPlayer, MafiaNightAction, MafiaVote, MafiaStats, User
)
from app.utils import utc_now

logger = logging.getLogger(__name__)


# Game configuration
LOBBY_TIMEOUT = 180  # 3 minutes
NIGHT_TIMEOUT = 120  # 2 minutes
DAY_DISCUSSION_TIMEOUT = 180  # 3 minutes
DAY_VOTING_TIMEOUT = 120  # 2 minutes

# Role distribution by player count
ROLE_DISTRIBUTION = {
    4: {"mafia": 1, "detective": 1, "doctor": 0, "citizen": 2},
    5: {"mafia": 1, "detective": 1, "doctor": 1, "citizen": 2},
    6: {"mafia": 1, "detective": 1, "doctor": 1, "citizen": 3},
    7: {"mafia": 2, "detective": 1, "doctor": 1, "citizen": 3},
    8: {"mafia": 2, "detective": 1, "doctor": 1, "citizen": 4},
    9: {"mafia": 2, "detective": 1, "doctor": 1, "citizen": 5},
    10: {"mafia": 3, "detective": 1, "doctor": 1, "citizen": 5},
    11: {"mafia": 3, "detective": 1, "doctor": 1, "citizen": 6},
    12: {"mafia": 3, "detective": 1, "doctor": 1, "citizen": 7},
}


class MafiaGameService:
    """Service for managing mafia games."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_lobby(self, chat_id: int, creator_user_id: int) -> Optional[MafiaGame]:
        """
        Create a new mafia game lobby.
        
        Returns None if there's already an active game in this chat.
        Automatically cancels old lobbies that exceeded timeout.
        """
        # Check for existing active game (only non-finished games)
        result = await self.session.execute(
            select(MafiaGame).where(
                and_(
                    MafiaGame.chat_id == chat_id,
                    MafiaGame.status.in_(["lobby", "night", "day_discussion", "day_voting"])
                )
            )
        )
        existing_game = result.scalar_one_or_none()
        
        if existing_game:
            # Check if it's an old lobby that should be cancelled
            if existing_game.status == "lobby":
                time_since_creation = (utc_now() - existing_game.created_at).total_seconds()
                if time_since_creation > LOBBY_TIMEOUT:
                    # Auto-cancel expired lobby
                    logger.info(f"Auto-cancelling expired lobby {existing_game.id} (age: {time_since_creation}s)")
                    existing_game.status = "finished"
                    existing_game.finished_at = utc_now()
                    await self.session.commit()
                    # Continue to create new lobby
                else:
                    logger.warning(f"Cannot create lobby in chat {chat_id}: game {existing_game.id} is {existing_game.status}")
                    return None
            else:
                # Game is in progress
                logger.warning(f"Cannot create lobby in chat {chat_id}: game {existing_game.id} is {existing_game.status}")
                return None
        
        # Create new game
        game = MafiaGame(
            chat_id=chat_id,
            status="lobby",
            phase_number=0,
            created_at=utc_now(),
            phase_started_at=utc_now()
        )
        self.session.add(game)
        await self.session.commit()
        await self.session.refresh(game)
        
        logger.info(f"Created mafia game lobby {game.id} in chat {chat_id}")
        return game
    
    async def join_lobby(self, game_id: int, user_id: int, username: Optional[str]) -> bool:
        """
        Add a player to the lobby.
        
        Returns False if game is not in lobby state or player already joined.
        """
        # Get game
        game = await self.session.get(MafiaGame, game_id)
        if not game or game.status != "lobby":
            return False
        
        # Check if player already joined
        result = await self.session.execute(
            select(MafiaPlayer).where(
                and_(
                    MafiaPlayer.game_id == game_id,
                    MafiaPlayer.user_id == user_id
                )
            )
        )
        existing_player = result.scalar_one_or_none()
        
        if existing_player:
            return False
        
        # Check max players
        result = await self.session.execute(
            select(func.count(MafiaPlayer.id)).where(MafiaPlayer.game_id == game_id)
        )
        player_count = result.scalar()
        
        if player_count >= 12:
            return False
        
        # Add player
        player = MafiaPlayer(
            game_id=game_id,
            user_id=user_id,
            username=username,
            role="",  # Will be assigned when game starts
            is_alive=True
        )
        self.session.add(player)
        await self.session.commit()
        
        logger.info(f"User {user_id} joined mafia game {game_id}")
        return True
    
    async def leave_lobby(self, game_id: int, user_id: int) -> bool:
        """Remove a player from the lobby."""
        game = await self.session.get(MafiaGame, game_id)
        if not game or game.status != "lobby":
            return False
        
        result = await self.session.execute(
            select(MafiaPlayer).where(
                and_(
                    MafiaPlayer.game_id == game_id,
                    MafiaPlayer.user_id == user_id
                )
            )
        )
        player = result.scalar_one_or_none()
        
        if player:
            await self.session.delete(player)
            await self.session.commit()
            logger.info(f"User {user_id} left mafia game {game_id}")
            return True
        
        return False

    
    async def start_game(self, game_id: int) -> Tuple[bool, str]:
        """
        Start the game and assign roles.
        
        Returns (success, error_message).
        """
        game = await self.session.get(MafiaGame, game_id)
        if not game or game.status != "lobby":
            return False, "Игра не найдена или уже началась"
        
        # Get players
        result = await self.session.execute(
            select(MafiaPlayer).where(MafiaPlayer.game_id == game_id)
        )
        players = list(result.scalars().all())
        
        player_count = len(players)
        if player_count < 4:
            return False, f"Недостаточно игроков (минимум 4, сейчас {player_count})"
        
        if player_count > 12:
            return False, f"Слишком много игроков (максимум 12, сейчас {player_count})"
        
        # Assign roles
        roles = self._generate_roles(player_count)
        random.shuffle(players)
        
        for player, role in zip(players, roles):
            player.role = role
        
        # Update game status
        game.status = "night"
        game.phase_number = 1
        game.started_at = utc_now()
        game.phase_started_at = utc_now()
        
        await self.session.commit()
        
        logger.info(f"Started mafia game {game_id} with {player_count} players")
        return True, ""
    
    def _generate_roles(self, player_count: int) -> List[str]:
        """Generate role list based on player count."""
        if player_count not in ROLE_DISTRIBUTION:
            # Fallback for unexpected counts
            player_count = min(ROLE_DISTRIBUTION.keys(), key=lambda x: abs(x - player_count))
        
        distribution = ROLE_DISTRIBUTION[player_count]
        roles = []
        
        for role, count in distribution.items():
            roles.extend([role] * count)
        
        return roles
    
    async def get_active_game(self, chat_id: int) -> Optional[MafiaGame]:
        """Get active game in chat."""
        result = await self.session.execute(
            select(MafiaGame).where(
                and_(
                    MafiaGame.chat_id == chat_id,
                    MafiaGame.status.in_(["lobby", "night", "day_discussion", "day_voting"])
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_game_players(self, game_id: int, alive_only: bool = False) -> List[MafiaPlayer]:
        """Get players in game."""
        query = select(MafiaPlayer).where(MafiaPlayer.game_id == game_id)
        
        if alive_only:
            query = query.where(MafiaPlayer.is_alive == True)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def submit_night_action(
        self, 
        game_id: int, 
        user_id: int, 
        action_type: str, 
        target_user_id: int
    ) -> bool:
        """
        Submit a night action (kill, heal, check).
        
        Returns False if action is invalid.
        """
        game = await self.session.get(MafiaGame, game_id)
        if not game or game.status != "night":
            return False
        
        # Get player
        result = await self.session.execute(
            select(MafiaPlayer).where(
                and_(
                    MafiaPlayer.game_id == game_id,
                    MafiaPlayer.user_id == user_id,
                    MafiaPlayer.is_alive == True
                )
            )
        )
        player = result.scalar_one_or_none()
        
        if not player:
            return False
        
        # Validate action type matches role
        valid_actions = {
            "mafia": "kill",
            "doctor": "heal",
            "detective": "check"
        }
        
        if player.role not in valid_actions or valid_actions[player.role] != action_type:
            return False
        
        # Check if action already exists
        result = await self.session.execute(
            select(MafiaNightAction).where(
                and_(
                    MafiaNightAction.game_id == game_id,
                    MafiaNightAction.phase_number == game.phase_number,
                    MafiaNightAction.user_id == user_id
                )
            )
        )
        existing_action = result.scalar_one_or_none()
        
        if existing_action:
            # Update existing action
            existing_action.target_user_id = target_user_id
        else:
            # Create new action
            action = MafiaNightAction(
                game_id=game_id,
                phase_number=game.phase_number,
                user_id=user_id,
                action_type=action_type,
                target_user_id=target_user_id
            )
            self.session.add(action)
        
        await self.session.commit()
        
        logger.info(f"Night action: {action_type} by {user_id} on {target_user_id} in game {game_id}")
        return True
    
    async def process_night_phase(self, game_id: int) -> Dict:
        """
        Process night actions and determine results.
        
        Returns dict with:
        - killed_user_id: ID of killed player (or None if saved)
        - detective_result: Dict with detective check results
        """
        game = await self.session.get(MafiaGame, game_id)
        if not game or game.status != "night":
            return {}
        
        # Get all night actions
        result = await self.session.execute(
            select(MafiaNightAction).where(
                and_(
                    MafiaNightAction.game_id == game_id,
                    MafiaNightAction.phase_number == game.phase_number
                )
            )
        )
        actions = list(result.scalars().all())
        
        # Process actions
        kill_target = None
        heal_target = None
        detective_checks = {}
        
        for action in actions:
            if action.action_type == "kill":
                kill_target = action.target_user_id
            elif action.action_type == "heal":
                heal_target = action.target_user_id
            elif action.action_type == "check":
                # Get target role
                target_result = await self.session.execute(
                    select(MafiaPlayer).where(
                        and_(
                            MafiaPlayer.game_id == game_id,
                            MafiaPlayer.user_id == action.target_user_id
                        )
                    )
                )
                target_player = target_result.scalar_one_or_none()
                if target_player:
                    is_mafia = target_player.role in ["mafia", "don"]
                    detective_checks[action.user_id] = {
                        "target_id": action.target_user_id,
                        "is_mafia": is_mafia
                    }
        
        # Determine if kill succeeds
        killed_user_id = None
        if kill_target and kill_target != heal_target:
            # Kill succeeds
            result = await self.session.execute(
                select(MafiaPlayer).where(
                    and_(
                        MafiaPlayer.game_id == game_id,
                        MafiaPlayer.user_id == kill_target
                    )
                )
            )
            victim = result.scalar_one_or_none()
            if victim:
                victim.is_alive = False
                victim.death_phase = game.phase_number
                victim.death_reason = "killed"
                killed_user_id = kill_target
        
        # Move to day phase
        game.status = "day_discussion"
        game.phase_started_at = utc_now()
        
        await self.session.commit()
        
        return {
            "killed_user_id": killed_user_id,
            "detective_checks": detective_checks
        }

    
    async def start_voting(self, game_id: int) -> bool:
        """Start day voting phase."""
        game = await self.session.get(MafiaGame, game_id)
        if not game or game.status != "day_discussion":
            return False
        
        game.status = "day_voting"
        game.phase_started_at = utc_now()
        await self.session.commit()
        
        return True
    
    async def submit_vote(self, game_id: int, voter_id: int, target_id: int) -> bool:
        """Submit a vote for lynching."""
        game = await self.session.get(MafiaGame, game_id)
        if not game or game.status != "day_voting":
            return False
        
        # Check voter is alive
        result = await self.session.execute(
            select(MafiaPlayer).where(
                and_(
                    MafiaPlayer.game_id == game_id,
                    MafiaPlayer.user_id == voter_id,
                    MafiaPlayer.is_alive == True
                )
            )
        )
        voter = result.scalar_one_or_none()
        
        if not voter:
            return False
        
        # Check target is alive
        result = await self.session.execute(
            select(MafiaPlayer).where(
                and_(
                    MafiaPlayer.game_id == game_id,
                    MafiaPlayer.user_id == target_id,
                    MafiaPlayer.is_alive == True
                )
            )
        )
        target = result.scalar_one_or_none()
        
        if not target:
            return False
        
        # Check if vote already exists
        result = await self.session.execute(
            select(MafiaVote).where(
                and_(
                    MafiaVote.game_id == game_id,
                    MafiaVote.phase_number == game.phase_number,
                    MafiaVote.voter_id == voter_id
                )
            )
        )
        existing_vote = result.scalar_one_or_none()
        
        if existing_vote:
            # Update vote
            existing_vote.target_id = target_id
        else:
            # Create new vote
            vote = MafiaVote(
                game_id=game_id,
                phase_number=game.phase_number,
                voter_id=voter_id,
                target_id=target_id
            )
            self.session.add(vote)
        
        await self.session.commit()
        
        logger.info(f"Vote: {voter_id} -> {target_id} in game {game_id}")
        return True
    
    async def process_voting(self, game_id: int) -> Dict:
        """
        Process voting and lynch the player with most votes.
        
        Returns dict with:
        - lynched_user_id: ID of lynched player (or None if tie)
        - vote_counts: Dict of {user_id: vote_count}
        """
        game = await self.session.get(MafiaGame, game_id)
        if not game or game.status != "day_voting":
            return {}
        
        # Get all votes
        result = await self.session.execute(
            select(MafiaVote).where(
                and_(
                    MafiaVote.game_id == game_id,
                    MafiaVote.phase_number == game.phase_number
                )
            )
        )
        votes = list(result.scalars().all())
        
        # Count votes
        vote_counts = {}
        for vote in votes:
            vote_counts[vote.target_id] = vote_counts.get(vote.target_id, 0) + 1
        
        # Find player with most votes
        lynched_user_id = None
        if vote_counts:
            max_votes = max(vote_counts.values())
            candidates = [uid for uid, count in vote_counts.items() if count == max_votes]
            
            if len(candidates) == 1:
                # Lynch the player
                lynched_user_id = candidates[0]
                result = await self.session.execute(
                    select(MafiaPlayer).where(
                        and_(
                            MafiaPlayer.game_id == game_id,
                            MafiaPlayer.user_id == lynched_user_id
                        )
                    )
                )
                victim = result.scalar_one_or_none()
                if victim:
                    victim.is_alive = False
                    victim.death_phase = game.phase_number
                    victim.death_reason = "lynched"
        
        # Check win conditions
        winner = await self._check_win_condition(game_id)
        
        if winner:
            game.status = "finished"
            game.winner = winner
            game.finished_at = utc_now()
            await self._update_stats(game_id, winner)
        else:
            # Move to next night
            game.status = "night"
            game.phase_number += 1
            game.phase_started_at = utc_now()
        
        await self.session.commit()
        
        return {
            "lynched_user_id": lynched_user_id,
            "vote_counts": vote_counts,
            "winner": winner
        }
    
    async def _check_win_condition(self, game_id: int) -> Optional[str]:
        """
        Check if game has a winner.
        
        Returns "mafia", "citizens", or None.
        """
        # Get alive players
        result = await self.session.execute(
            select(MafiaPlayer).where(
                and_(
                    MafiaPlayer.game_id == game_id,
                    MafiaPlayer.is_alive == True
                )
            )
        )
        alive_players = list(result.scalars().all())
        
        mafia_count = sum(1 for p in alive_players if p.role in ["mafia", "don"])
        citizen_count = len(alive_players) - mafia_count
        
        if mafia_count == 0:
            return "citizens"
        elif mafia_count >= citizen_count:
            return "mafia"
        
        return None
    
    async def _update_stats(self, game_id: int, winner: str):
        """Update player statistics after game ends."""
        game = await self.session.get(MafiaGame, game_id)
        if not game:
            return
        
        # Get all players
        result = await self.session.execute(
            select(MafiaPlayer).where(MafiaPlayer.game_id == game_id)
        )
        players = list(result.scalars().all())
        
        for player in players:
            # Get or create stats
            result = await self.session.execute(
                select(MafiaStats).where(
                    and_(
                        MafiaStats.user_id == player.user_id,
                        MafiaStats.chat_id == game.chat_id
                    )
                )
            )
            stats = result.scalar_one_or_none()
            
            if not stats:
                stats = MafiaStats(
                    user_id=player.user_id,
                    chat_id=game.chat_id
                )
                self.session.add(stats)
            
            # Update stats
            stats.games_played += 1
            
            if player.is_alive:
                stats.games_survived += 1
            
            # Check if won
            player_won = False
            if player.role in ["mafia", "don"] and winner == "mafia":
                player_won = True
                stats.mafia_wins += 1
                stats.mafia_games += 1
            elif player.role not in ["mafia", "don"] and winner == "citizens":
                player_won = True
                stats.citizen_wins += 1
                stats.citizen_games += 1
            elif player.role in ["mafia", "don"]:
                stats.mafia_games += 1
            else:
                stats.citizen_games += 1
            
            if player_won:
                stats.games_won += 1
            
            # Role-specific stats
            if player.role == "detective":
                stats.detective_games += 1
                # Count successful checks
                result = await self.session.execute(
                    select(MafiaNightAction).where(
                        and_(
                            MafiaNightAction.game_id == game_id,
                            MafiaNightAction.user_id == player.user_id,
                            MafiaNightAction.action_type == "check"
                        )
                    )
                )
                checks = list(result.scalars().all())
                for check in checks:
                    # Check if target was mafia
                    target_result = await self.session.execute(
                        select(MafiaPlayer).where(
                            and_(
                                MafiaPlayer.game_id == game_id,
                                MafiaPlayer.user_id == check.target_user_id
                            )
                        )
                    )
                    target = target_result.scalar_one_or_none()
                    if target and target.role in ["mafia", "don"]:
                        stats.detective_checks += 1
            
            elif player.role == "doctor":
                stats.doctor_games += 1
                # Count successful saves
                result = await self.session.execute(
                    select(MafiaNightAction).where(
                        and_(
                            MafiaNightAction.game_id == game_id,
                            MafiaNightAction.user_id == player.user_id,
                            MafiaNightAction.action_type == "heal"
                        )
                    )
                )
                heals = list(result.scalars().all())
                for heal in heals:
                    # Check if target was attacked same night
                    kill_result = await self.session.execute(
                        select(MafiaNightAction).where(
                            and_(
                                MafiaNightAction.game_id == game_id,
                                MafiaNightAction.phase_number == heal.phase_number,
                                MafiaNightAction.action_type == "kill",
                                MafiaNightAction.target_user_id == heal.target_user_id
                            )
                        )
                    )
                    if kill_result.scalar_one_or_none():
                        stats.doctor_saves += 1
            
            # Voting accuracy
            result = await self.session.execute(
                select(MafiaVote).where(
                    and_(
                        MafiaVote.game_id == game_id,
                        MafiaVote.voter_id == player.user_id
                    )
                )
            )
            votes = list(result.scalars().all())
            for vote in votes:
                stats.total_votes += 1
                # Check if voted for mafia
                target_result = await self.session.execute(
                    select(MafiaPlayer).where(
                        and_(
                            MafiaPlayer.game_id == game_id,
                            MafiaPlayer.user_id == vote.target_id
                        )
                    )
                )
                target = target_result.scalar_one_or_none()
                if target and target.role in ["mafia", "don"]:
                    stats.correct_votes += 1
        
        await self.session.commit()
    
    async def cancel_game(self, game_id: int) -> bool:
        """Cancel an active game."""
        game = await self.session.get(MafiaGame, game_id)
        if not game or game.status == "finished":
            return False
        
        game.status = "finished"
        game.finished_at = utc_now()
        await self.session.commit()
        
        logger.info(f"Cancelled mafia game {game_id}")
        return True
    
    async def get_player_role(self, game_id: int, user_id: int) -> Optional[str]:
        """Get player's role in game."""
        result = await self.session.execute(
            select(MafiaPlayer.role).where(
                and_(
                    MafiaPlayer.game_id == game_id,
                    MafiaPlayer.user_id == user_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_mafia_team(self, game_id: int) -> List[MafiaPlayer]:
        """Get all mafia members in game."""
        result = await self.session.execute(
            select(MafiaPlayer).where(
                and_(
                    MafiaPlayer.game_id == game_id,
                    MafiaPlayer.role.in_(["mafia", "don"])
                )
            )
        )
        return list(result.scalars().all())
