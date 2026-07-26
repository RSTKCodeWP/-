"""
Property-based tests for Russian Roulette with coin betting.

Tests correctness properties defined in the design document.
**Feature: grand-casino-dictator, Property 4: Roulette Coin Balance Consistency**
**Validates: Requirements 5.5**
"""

import os
import importlib.util
from hypothesis import given, strategies as st, settings, assume

# Import game_engine module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'game_engine.py')
_spec = importlib.util.spec_from_file_location("game_engine", _module_path)
_game_engine_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_game_engine_module)

GameEngine = _game_engine_module.GameEngine
RouletteResult = _game_engine_module.RouletteResult


# Strategies for generating test data
user_id_strategy = st.integers(min_value=1, max_value=10**12)
chat_id_strategy = st.integers(min_value=-10**12, max_value=10**12)
bet_amount_strategy = st.integers(min_value=1, max_value=1000)
balance_strategy = st.integers(min_value=0, max_value=100000)


class TestRouletteCoinBalanceConsistency:
    """
    **Feature: grand-casino-dictator, Property 4: Roulette Coin Balance Consistency**
    **Validates: Requirements 5.5**
    
    *For any* roulette game with coin betting, the player's balance change equals 
    -bet on shot or +winnings on survival, and the final balance is never negative 
    below a defined floor.
    """
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        initial_balance=st.integers(min_value=100, max_value=10000),
        bet_amount=bet_amount_strategy
    )
    def test_shot_deducts_bet_amount(
        self,
        user_id: int,
        chat_id: int,
        initial_balance: int,
        bet_amount: int
    ):
        """
        Property 4: When shot occurs in betting mode, balance decreases by bet amount.
        
        For any roulette game with bet > 0 where shot occurs:
        - Balance change equals -bet_amount
        - Final balance equals initial_balance - bet_amount
        """
        assume(initial_balance >= bet_amount)
        
        # Create engine with deterministic random that always returns 0 (shot)
        engine = GameEngine(random_func=lambda: 0.0)
        
        # Set initial balance
        engine.set_balance(user_id, chat_id, initial_balance)
        
        # Play roulette with bet (will always be a shot)
        result = engine.play_roulette(user_id, chat_id, bet_amount=bet_amount)
        
        # Verify shot occurred
        assert result.success, f"Roulette should succeed: {result.message}"
        assert result.shot, "Should have been shot with random=0"
        
        # Verify balance decreased by bet amount
        expected_balance = initial_balance - bet_amount
        assert result.new_balance == expected_balance, \
            f"Balance should be {expected_balance}, got {result.new_balance}"
        
        # Verify points_change equals -bet_amount
        assert result.points_change == -bet_amount, \
            f"Points change should be -{bet_amount}, got {result.points_change}"
        
        # Verify balance in engine matches
        balance_data = engine.get_balance(user_id, chat_id)
        assert balance_data.balance == expected_balance
        assert balance_data.total_lost >= bet_amount

    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        initial_balance=st.integers(min_value=100, max_value=10000),
        bet_amount=bet_amount_strategy
    )
    def test_survival_awards_bet_amount(
        self,
        user_id: int,
        chat_id: int,
        initial_balance: int,
        bet_amount: int
    ):
        """
        Property 4: When survival occurs in betting mode, balance increases by bet amount.
        
        For any roulette game with bet > 0 where survival occurs:
        - Balance change equals +bet_amount
        - Final balance equals initial_balance + bet_amount
        """
        assume(initial_balance >= bet_amount)
        
        # Create engine with deterministic random that returns 0.5 (survival)
        # Chamber = int(0.5 * 6) = 3, which is not 0, so no shot
        engine = GameEngine(random_func=lambda: 0.5)
        
        # Set initial balance
        engine.set_balance(user_id, chat_id, initial_balance)
        
        # Play roulette with bet (will always survive)
        result = engine.play_roulette(user_id, chat_id, bet_amount=bet_amount)
        
        # Verify survival
        assert result.success, f"Roulette should succeed: {result.message}"
        assert not result.shot, "Should have survived with random=0.5"
        
        # Verify balance increased by bet amount
        expected_balance = initial_balance + bet_amount
        assert result.new_balance == expected_balance, \
            f"Balance should be {expected_balance}, got {result.new_balance}"
        
        # Verify points_change equals +bet_amount
        assert result.points_change == bet_amount, \
            f"Points change should be {bet_amount}, got {result.points_change}"
        
        # Verify balance in engine matches
        balance_data = engine.get_balance(user_id, chat_id)
        assert balance_data.balance == expected_balance
        assert balance_data.total_won >= bet_amount

    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        initial_balance=st.integers(min_value=0, max_value=100),
        bet_excess=st.integers(min_value=1, max_value=1000)
    )
    def test_insufficient_balance_rejects_bet(
        self,
        user_id: int,
        chat_id: int,
        initial_balance: int,
        bet_excess: int
    ):
        """
        Property 4: Bets exceeding balance are rejected, balance unchanged.
        
        For any bet amount > balance:
        - Roulette should fail with INSUFFICIENT_BALANCE error
        - Balance should remain unchanged
        """
        bet_amount = initial_balance + bet_excess  # Always exceeds balance
        
        engine = GameEngine()
        
        # Set initial balance
        engine.set_balance(user_id, chat_id, initial_balance)
        
        # Try to play roulette with insufficient balance
        result = engine.play_roulette(user_id, chat_id, bet_amount=bet_amount)
        
        # Verify rejection
        assert not result.success, "Roulette should fail with insufficient balance"
        assert result.error_code == "INSUFFICIENT_BALANCE", \
            f"Error code should be INSUFFICIENT_BALANCE, got {result.error_code}"
        
        # Verify balance unchanged
        balance_data = engine.get_balance(user_id, chat_id)
        assert balance_data.balance == initial_balance, \
            f"Balance should remain {initial_balance}, got {balance_data.balance}"

    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        initial_balance=st.integers(min_value=1, max_value=1000)
    )
    def test_exact_balance_bet_allowed(
        self,
        user_id: int,
        chat_id: int,
        initial_balance: int
    ):
        """
        Property 4 edge case: Betting exact balance should be allowed.
        """
        engine = GameEngine()
        
        # Set initial balance
        engine.set_balance(user_id, chat_id, initial_balance)
        
        # Bet exact balance
        result = engine.play_roulette(user_id, chat_id, bet_amount=initial_balance)
        
        # Should succeed
        assert result.success, f"Betting exact balance should succeed: {result.message}"
        
        # Balance should change appropriately
        if result.shot:
            assert result.new_balance == 0, "Balance should be 0 after losing exact balance"
        else:
            assert result.new_balance == initial_balance * 2, \
                f"Balance should double on survival, got {result.new_balance}"

    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        initial_balance=st.integers(min_value=100, max_value=10000)
    )
    def test_zero_bet_uses_standard_mode(
        self,
        user_id: int,
        chat_id: int,
        initial_balance: int
    ):
        """
        Property 4 edge case: Zero bet uses standard mode with fixed points.
        """
        # Create engine with deterministic random for shot
        engine_shot = GameEngine(random_func=lambda: 0.0)
        engine_shot.set_balance(user_id, chat_id, initial_balance)
        
        # Play with zero bet (standard mode)
        result_shot = engine_shot.play_roulette(user_id, chat_id, bet_amount=0)
        
        assert result_shot.success
        assert result_shot.shot
        # Standard mode uses fixed penalty
        assert result_shot.points_change == -engine_shot.ROULETTE_SHOT_PENALTY
        
        # Create engine with deterministic random for survival
        engine_survive = GameEngine(random_func=lambda: 0.5)
        engine_survive.set_balance(user_id, chat_id, initial_balance)
        
        # Play with zero bet (standard mode)
        result_survive = engine_survive.play_roulette(user_id, chat_id, bet_amount=0)
        
        assert result_survive.success
        assert not result_survive.shot
        # Standard mode uses fixed reward
        assert result_survive.points_change == engine_survive.ROULETTE_SURVIVAL_REWARD

    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        initial_balance=st.integers(min_value=100, max_value=10000),
        bet_amount=bet_amount_strategy,
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_balance_change_matches_outcome(
        self,
        user_id: int,
        chat_id: int,
        initial_balance: int,
        bet_amount: int,
        seed: int
    ):
        """
        Property 4: Balance change always matches the game outcome.
        
        For any roulette game with bet > 0:
        - If shot: balance_change == -bet_amount
        - If survival: balance_change == +bet_amount
        - Final balance == initial_balance + balance_change
        """
        import random as rand_module
        
        assume(initial_balance >= bet_amount)
        
        # Create engine with seeded random
        rng = rand_module.Random(seed)
        engine = GameEngine(random_func=rng.random)
        
        # Set initial balance
        engine.set_balance(user_id, chat_id, initial_balance)
        
        # Play roulette
        result = engine.play_roulette(user_id, chat_id, bet_amount=bet_amount)
        
        assert result.success
        
        # Verify balance change matches outcome
        if result.shot:
            expected_change = -bet_amount
        else:
            expected_change = bet_amount
        
        assert result.points_change == expected_change, \
            f"Points change should be {expected_change}, got {result.points_change}"
        
        # Verify final balance
        expected_balance = initial_balance + expected_change
        assert result.new_balance == expected_balance, \
            f"Balance should be {expected_balance}, got {result.new_balance}"
        
        # Verify engine state matches
        balance_data = engine.get_balance(user_id, chat_id)
        assert balance_data.balance == expected_balance

    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy
    )
    def test_negative_bet_rejected(
        self,
        user_id: int,
        chat_id: int
    ):
        """
        Property 4 edge case: Negative bets are rejected.
        """
        engine = GameEngine()
        engine.set_balance(user_id, chat_id, 1000)
        
        # Try negative bet
        result = engine.play_roulette(user_id, chat_id, bet_amount=-100)
        
        assert not result.success, "Negative bet should be rejected"
        assert result.error_code == "INVALID_BET", \
            f"Error code should be INVALID_BET, got {result.error_code}"
        
        # Balance unchanged
        balance_data = engine.get_balance(user_id, chat_id)
        assert balance_data.balance == 1000
