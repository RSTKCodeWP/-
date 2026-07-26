"""
Property-based tests for ELO Calculator.

Tests correctness properties defined in the design document.
Requirements: 10.1, 10.2, 10.3, 10.4
"""

import os
import importlib.util
from hypothesis import given, strategies as st, settings, assume

# Import elo module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'elo.py')
_spec = importlib.util.spec_from_file_location("elo", _module_path)
_elo_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_elo_module)

EloCalculator = _elo_module.EloCalculator
EloChange = _elo_module.EloChange


# Strategies for generating test data
elo_strategy = st.integers(min_value=0, max_value=5000)


class TestEloRatingDifferenceImpact:
    """
    **Feature: grand-casino-dictator, Property 15: ELO Rating Difference Impact**
    **Validates: Requirements 10.1, 10.2, 10.3**
    
    *For any* match result, the ELO change magnitude is inversely proportional 
    to the expected outcome based on rating difference.
    """
    
    @settings(max_examples=100)
    @given(
        winner_elo=elo_strategy,
        loser_elo=elo_strategy
    )
    def test_elo_change_based_on_rating_difference(
        self,
        winner_elo: int,
        loser_elo: int
    ):
        """
        Property 15: ELO changes are calculated based on rating difference.
        
        For any match:
        - Winner gains points (positive delta)
        - Loser loses points (negative delta)
        - Changes are based on expected outcome
        """
        calculator = EloCalculator()
        result = calculator.calculate(winner_elo, loser_elo)
        
        # Winner should gain points
        assert result.winner_delta >= 0, \
            f"Winner should gain points, got delta {result.winner_delta}"
        
        # Loser should lose points
        assert result.loser_delta <= 0, \
            f"Loser should lose points, got delta {result.loser_delta}"
        
        # New ratings should be calculated correctly
        assert result.winner_new_elo == max(0, winner_elo + result.winner_delta), \
            "Winner new ELO should be old + delta (min 0)"
        assert result.loser_new_elo == max(0, loser_elo + result.loser_delta), \
            "Loser new ELO should be old + delta (min 0)"
    
    @settings(max_examples=100)
    @given(
        base_elo=st.integers(min_value=500, max_value=2000),
        small_diff=st.integers(min_value=0, max_value=100),
        large_diff=st.integers(min_value=200, max_value=1000)
    )
    def test_beating_higher_rated_gives_more_points(
        self,
        base_elo: int,
        small_diff: int,
        large_diff: int
    ):
        """
        Property 15: Beating a higher-rated opponent gives more points.
        
        Requirements 10.2: When a player defeats a higher-rated opponent,
        the system SHALL award more ELO points than defeating a lower-rated opponent.
        """
        assume(large_diff > small_diff)
        
        calculator = EloCalculator()
        
        # Underdog beats favorite (winner has lower ELO)
        underdog_elo = base_elo
        weak_favorite_elo = base_elo + small_diff
        strong_favorite_elo = base_elo + large_diff
        
        # Underdog beats weak favorite
        result_weak = calculator.calculate(underdog_elo, weak_favorite_elo)
        
        # Underdog beats strong favorite
        result_strong = calculator.calculate(underdog_elo, strong_favorite_elo)
        
        # Beating stronger opponent should give more points
        assert result_strong.winner_delta >= result_weak.winner_delta, \
            f"Beating stronger opponent ({strong_favorite_elo}) should give >= points " \
            f"than beating weaker ({weak_favorite_elo}): {result_strong.winner_delta} vs {result_weak.winner_delta}"
    
    @settings(max_examples=100)
    @given(
        base_elo=st.integers(min_value=500, max_value=2000),
        small_diff=st.integers(min_value=0, max_value=100),
        large_diff=st.integers(min_value=200, max_value=1000)
    )
    def test_losing_to_lower_rated_costs_more_points(
        self,
        base_elo: int,
        small_diff: int,
        large_diff: int
    ):
        """
        Property 15: Losing to a lower-rated opponent costs more points.
        
        Requirements 10.3: When a player loses to a lower-rated opponent,
        the system SHALL deduct more ELO points than losing to a higher-rated opponent.
        """
        assume(large_diff > small_diff)
        
        calculator = EloCalculator()
        
        # Favorite loses to underdog (loser has higher ELO)
        favorite_elo = base_elo + large_diff
        weak_underdog_elo = base_elo + small_diff  # Closer to favorite
        strong_underdog_elo = base_elo  # Further from favorite
        
        # Favorite loses to weak underdog (smaller upset)
        result_weak = calculator.calculate(weak_underdog_elo, favorite_elo)
        
        # Favorite loses to strong underdog (bigger upset)
        result_strong = calculator.calculate(strong_underdog_elo, favorite_elo)
        
        # Losing to much lower rated should cost more (more negative delta)
        assert result_strong.loser_delta <= result_weak.loser_delta, \
            f"Losing to lower-rated ({strong_underdog_elo}) should cost >= points " \
            f"than losing to closer-rated ({weak_underdog_elo}): " \
            f"{result_strong.loser_delta} vs {result_weak.loser_delta}"
    
    @settings(max_examples=100)
    @given(elo=elo_strategy)
    def test_expected_score_bounds(self, elo: int):
        """
        Property 15 extended: Expected score is always between 0 and 1.
        """
        calculator = EloCalculator()
        
        # Test against various opponents
        for opponent_elo in [0, 500, 1000, 2000, 5000]:
            expected = calculator.expected_score(elo, opponent_elo)
            
            assert 0 <= expected <= 1, \
                f"Expected score should be in [0,1], got {expected} " \
                f"for {elo} vs {opponent_elo}"
    
    @settings(max_examples=100)
    @given(
        player_elo=elo_strategy,
        opponent_elo=elo_strategy
    )
    def test_expected_scores_sum_to_one(
        self,
        player_elo: int,
        opponent_elo: int
    ):
        """
        Property 15 extended: Expected scores of both players sum to 1.
        
        This is a fundamental property of the ELO system.
        """
        calculator = EloCalculator()
        
        player_expected = calculator.expected_score(player_elo, opponent_elo)
        opponent_expected = calculator.expected_score(opponent_elo, player_elo)
        
        assert abs(player_expected + opponent_expected - 1.0) < 0.0001, \
            f"Expected scores should sum to 1: {player_expected} + {opponent_expected}"
    
    @settings(max_examples=100)
    @given(elo=elo_strategy)
    def test_equal_rating_gives_equal_expected(self, elo: int):
        """
        Property 15 extended: Equal ratings give 50% expected score.
        """
        calculator = EloCalculator()
        
        expected = calculator.expected_score(elo, elo)
        
        assert abs(expected - 0.5) < 0.0001, \
            f"Equal ratings should give 0.5 expected, got {expected}"
    
    @settings(max_examples=100)
    @given(elo=elo_strategy)
    def test_equal_rating_match_gives_symmetric_changes(self, elo: int):
        """
        Property 15 extended: Equal rating match gives symmetric ELO changes.
        
        When players have equal ratings, winner gains what loser loses.
        """
        calculator = EloCalculator()
        
        result = calculator.calculate(elo, elo)
        
        # Changes should be symmetric (or very close due to rounding)
        assert abs(result.winner_delta + result.loser_delta) <= 1, \
            f"Equal rating changes should be symmetric: " \
            f"+{result.winner_delta} vs {result.loser_delta}"
    
    @settings(max_examples=100)
    @given(
        winner_elo=elo_strategy,
        loser_elo=elo_strategy
    )
    def test_elo_never_goes_negative(
        self,
        winner_elo: int,
        loser_elo: int
    ):
        """
        Property 15 extended: ELO rating never goes below 0.
        """
        calculator = EloCalculator()
        
        result = calculator.calculate(winner_elo, loser_elo)
        
        assert result.winner_new_elo >= 0, \
            f"Winner ELO should never be negative: {result.winner_new_elo}"
        assert result.loser_new_elo >= 0, \
            f"Loser ELO should never be negative: {result.loser_new_elo}"
    
    @settings(max_examples=100)
    @given(
        winner_elo=elo_strategy,
        loser_elo=elo_strategy
    )
    def test_k_factor_bounds_maximum_change(
        self,
        winner_elo: int,
        loser_elo: int
    ):
        """
        Property 15 extended: K-factor bounds maximum ELO change.
        
        With K=32, maximum change is 32 points (when expected score is 0 or 1).
        """
        calculator = EloCalculator()
        
        result = calculator.calculate(winner_elo, loser_elo)
        
        assert result.winner_delta <= calculator.K_FACTOR, \
            f"Winner delta {result.winner_delta} should not exceed K={calculator.K_FACTOR}"
        assert abs(result.loser_delta) <= calculator.K_FACTOR, \
            f"Loser delta {result.loser_delta} should not exceed K={calculator.K_FACTOR}"
