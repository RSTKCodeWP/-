"""
Duel game engine with RPG-style combat.

Implements Rock-Paper-Scissors mechanics wrapped as zone-based combat.
Requirements: 4.3, 6.1, 6.2, 6.3, 6.4
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple, Optional, Callable
import random


class Zone(Enum):
    """Combat zones for attack and defense."""
    HEAD = "head"
    BODY = "body"
    LEGS = "legs"


class DuelStatus(Enum):
    """Status of a duel game."""
    WAITING = "waiting"  # Waiting for opponent to accept
    PLAYING = "playing"  # Duel in progress
    PLAYER1_WIN = "player1_win"
    PLAYER2_WIN = "player2_win"


# Oleg's user ID for PvE mode
OLEG_USER_ID = 0


@dataclass
class DuelState:
    """State of a duel game."""
    player1_id: int
    player2_id: int  # 0 for Oleg (PvE)
    player1_hp: int
    player2_hp: int
    current_turn: int  # player_id whose turn it is
    bet: int
    status: DuelStatus = DuelStatus.PLAYING
    
    @property
    def is_pve(self) -> bool:
        """Check if this is a PvE duel against Oleg."""
        return self.player2_id == OLEG_USER_ID
    
    @property
    def is_finished(self) -> bool:
        """Check if the duel has ended."""
        return self.status in (DuelStatus.PLAYER1_WIN, DuelStatus.PLAYER2_WIN)
    
    @property
    def winner_id(self) -> Optional[int]:
        """Get the winner's ID, or None if game not finished."""
        if self.status == DuelStatus.PLAYER1_WIN:
            return self.player1_id
        elif self.status == DuelStatus.PLAYER2_WIN:
            return self.player2_id
        return None


class DuelEngine:
    """
    RPG-style duel engine with zone-based combat.
    
    Combat uses Rock-Paper-Scissors mechanics:
    - Players choose attack zone and defense zone
    - Attack hits if attacker's zone differs from defender's defended zone
    - Each hit deals DAMAGE points
    - Game ends when either player's HP reaches 0
    """
    
    MAX_HP = 100
    DAMAGE = 25
    
    def __init__(self, random_func: Optional[Callable[[], float]] = None):
        """
        Initialize the duel engine.
        
        Args:
            random_func: Optional random function for testing determinism.
        """
        self._random = random_func or random.random
    
    def create_duel(
        self, 
        challenger_id: int, 
        target_id: int, 
        bet: int
    ) -> DuelState:
        """
        Create a new duel.
        
        Args:
            challenger_id: The challenger's user ID.
            target_id: The target's user ID (0 for Oleg/PvE).
            bet: The bet amount.
            
        Returns:
            A new DuelState with both players at full HP.
        """
        return DuelState(
            player1_id=challenger_id,
            player2_id=target_id,
            player1_hp=self.MAX_HP,
            player2_hp=self.MAX_HP,
            current_turn=challenger_id,
            bet=bet,
            status=DuelStatus.PLAYING
        )
    
    def make_move(
        self,
        state: DuelState,
        player_id: int,
        attack: Zone,
        defend: Zone,
        opponent_attack: Zone,
        opponent_defend: Zone
    ) -> DuelState:
        """
        Execute a round of combat.
        
        Both players simultaneously choose attack and defense zones.
        Attack hits if attacker's zone differs from defender's defended zone.
        
        Args:
            state: Current duel state.
            player_id: The player making the move.
            attack: Player's attack zone.
            defend: Player's defense zone.
            opponent_attack: Opponent's attack zone.
            opponent_defend: Opponent's defense zone.
            
        Returns:
            Updated duel state after the round.
        """
        if state.is_finished:
            return state
        
        # Determine which player is which
        if player_id == state.player1_id:
            p1_attack, p1_defend = attack, defend
            p2_attack, p2_defend = opponent_attack, opponent_defend
        else:
            p1_attack, p1_defend = opponent_attack, opponent_defend
            p2_attack, p2_defend = attack, defend
        
        # Calculate damage
        # Player 1 attacks Player 2: hits if attack zone != defend zone
        p1_hits = p1_attack != p2_defend
        # Player 2 attacks Player 1: hits if attack zone != defend zone
        p2_hits = p2_attack != p1_defend
        
        # Apply damage
        new_p1_hp = state.player1_hp
        new_p2_hp = state.player2_hp
        
        if p2_hits:
            new_p1_hp = max(0, state.player1_hp - self.DAMAGE)
        if p1_hits:
            new_p2_hp = max(0, state.player2_hp - self.DAMAGE)
        
        # Determine game status
        new_status = state.status
        if new_p1_hp <= 0 and new_p2_hp <= 0:
            # Both knocked out - attacker (player1) wins on tie
            new_status = DuelStatus.PLAYER1_WIN
        elif new_p1_hp <= 0:
            new_status = DuelStatus.PLAYER2_WIN
        elif new_p2_hp <= 0:
            new_status = DuelStatus.PLAYER1_WIN
        
        return DuelState(
            player1_id=state.player1_id,
            player2_id=state.player2_id,
            player1_hp=new_p1_hp,
            player2_hp=new_p2_hp,
            current_turn=state.current_turn,
            bet=state.bet,
            status=new_status
        )
    
    def oleg_move(self) -> Tuple[Zone, Zone]:
        """
        Generate Oleg's move for PvE mode.
        
        Randomly selects attack and defense zones.
        
        Returns:
            Tuple of (attack_zone, defense_zone).
        """
        zones = list(Zone)
        
        # Random attack zone
        attack_idx = int(self._random() * len(zones))
        attack = zones[attack_idx]
        
        # Random defense zone
        defend_idx = int(self._random() * len(zones))
        defend = zones[defend_idx]
        
        return attack, defend
    
    def check_termination(self, state: DuelState) -> DuelState:
        """
        Check if the duel should end based on HP.
        
        Args:
            state: Current duel state.
            
        Returns:
            Updated state with correct status if game should end.
        """
        if state.is_finished:
            return state
        
        new_status = state.status
        
        if state.player1_hp <= 0 and state.player2_hp <= 0:
            # Both at 0 - player1 (challenger) wins on tie
            new_status = DuelStatus.PLAYER1_WIN
        elif state.player1_hp <= 0:
            new_status = DuelStatus.PLAYER2_WIN
        elif state.player2_hp <= 0:
            new_status = DuelStatus.PLAYER1_WIN
        
        if new_status != state.status:
            return DuelState(
                player1_id=state.player1_id,
                player2_id=state.player2_id,
                player1_hp=state.player1_hp,
                player2_hp=state.player2_hp,
                current_turn=state.current_turn,
                bet=state.bet,
                status=new_status
            )
        
        return state
    
    def render_hp_bar(self, hp: int, max_hp: int = None) -> str:
        """
        Render a visual HP bar.
        
        Args:
            hp: Current HP value.
            max_hp: Maximum HP (defaults to MAX_HP).
            
        Returns:
            String representation like "[████░░░] 60%"
        """
        if max_hp is None:
            max_hp = self.MAX_HP
        
        # Clamp HP to valid range
        hp = max(0, min(hp, max_hp))
        
        # Calculate percentage
        percentage = int((hp / max_hp) * 100) if max_hp > 0 else 0
        
        # Calculate filled blocks (7 blocks total for visual)
        total_blocks = 7
        filled_blocks = int((hp / max_hp) * total_blocks) if max_hp > 0 else 0
        empty_blocks = total_blocks - filled_blocks
        
        # Build the bar
        bar = "█" * filled_blocks + "░" * empty_blocks
        
        return f"[{bar}] {percentage}%"
