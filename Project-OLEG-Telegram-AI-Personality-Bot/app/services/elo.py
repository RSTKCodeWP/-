"""
ELO Rating Calculator for competitive games.

Implements standard ELO formula for calculating rating changes after matches.
"""

from dataclasses import dataclass


@dataclass
class EloChange:
    """Result of an ELO calculation after a match."""
    winner_delta: int
    loser_delta: int
    winner_new_elo: int
    loser_new_elo: int


class EloCalculator:
    """
    ELO rating calculator using standard formula.
    
    The ELO system calculates rating changes based on:
    - Current ratings of both players
    - Expected outcome based on rating difference
    - K-factor determining maximum rating change per game
    """
    
    K_FACTOR = 32  # Standard K-factor
    
    def expected_score(self, player_elo: int, opponent_elo: int) -> float:
        """
        Calculate expected score (probability of winning) for a player.
        
        Uses the standard ELO formula:
        E = 1 / (1 + 10^((opponent_elo - player_elo) / 400))
        
        Args:
            player_elo: Current ELO rating of the player
            opponent_elo: Current ELO rating of the opponent
            
        Returns:
            Expected score between 0 and 1
        """
        exponent = (opponent_elo - player_elo) / 400.0
        return 1.0 / (1.0 + 10 ** exponent)
    
    def calculate(self, winner_elo: int, loser_elo: int) -> EloChange:
        """
        Calculate ELO changes after a match.
        
        The winner gains points and the loser loses points.
        The magnitude depends on the rating difference:
        - Beating a higher-rated opponent gives more points
        - Losing to a lower-rated opponent costs more points
        
        Args:
            winner_elo: Current ELO rating of the winner
            loser_elo: Current ELO rating of the loser
            
        Returns:
            EloChange with deltas and new ratings for both players
        """
        # Expected scores
        winner_expected = self.expected_score(winner_elo, loser_elo)
        loser_expected = self.expected_score(loser_elo, winner_elo)
        
        # Actual scores: winner gets 1, loser gets 0
        winner_actual = 1.0
        loser_actual = 0.0
        
        # Calculate rating changes
        winner_delta = round(self.K_FACTOR * (winner_actual - winner_expected))
        loser_delta = round(self.K_FACTOR * (loser_actual - loser_expected))
        
        # Calculate new ratings (minimum 0)
        winner_new_elo = max(0, winner_elo + winner_delta)
        loser_new_elo = max(0, loser_elo + loser_delta)
        
        return EloChange(
            winner_delta=winner_delta,
            loser_delta=loser_delta,
            winner_new_elo=winner_new_elo,
            loser_new_elo=loser_new_elo
        )


# Singleton instance for convenience
elo_calculator = EloCalculator()
