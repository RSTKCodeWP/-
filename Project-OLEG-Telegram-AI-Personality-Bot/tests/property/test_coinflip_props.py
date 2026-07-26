"""
Property-based tests for Coinflip game.

Tests correctness properties defined in the design document.
**Feature: grand-casino-dictator, Property 7: Coinflip Balance Change**
**Feature: grand-casino-dictator, Property 8: Coinflip Insufficient Balance Rejection**
**Validates: Requirements 8.2, 8.3, 8.4**
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
CoinFlipResult = _game_engine_module.CoinFlipResult


# Strategies for generating test data
user_id_strategy = st.integers(min_value=1, max_value=10**12)
chat_id_strategy = st.integers(min_value=-10**12, max_value=10**12)
bet_amount_strategy = st.integers(min_value=1, max_value=1000)
balance_strategy = st.integers(min_value=0, max_value=100000)
choice_strategy = st.sampled_from(["heads", "tails"])


class TestCoinflipBalanceChange:
    """
    **Feature: grand-casino-dictator, Property 7: Coinflip Balance Change**
    **Validates: Requirements 8.2, 8.3**
    
    *For any* coinflip game result, the player's balance change equals exactly 
    +bet_amount on win or -bet_amount on loss.
    """
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        initial_balance=st.integers(min_value=100, max_value=10000),
        bet_amount=bet_amount_strategy,
        choice=choice_strategy
    )
    def test_win_doubles_bet(
        self,
        user_id: int,
        chat_id: int,
        initial_balance: int,
        bet_amount: int,
        choice: str
    ):
        """
        Property 7: When player wins, balance increases by exactly bet_amount.
        
        Requirements 8.2: WHEN the coinflip result matches the user's choice 
        THEN the system SHALL double the bet amount.
        
        For any coinflip game where player wins:
        - Balance change equals +bet_amount
        - Final balance equals initial_balance + bet_amount
        """
        assume(initial_balance >= bet_amount)
        
        # Create engine with deterministic random that matches player's choice
        # random < 0.5 = heads, random >= 0.5 = tails
        if choice == "heads":
            random_value = 0.0  # Will result in heads
        else:
            random_value = 0.5  # Will result in tails
        
        engine = GameEngine(random_func=lambda: random_value)
        
        # Set initial balance
        engine.set_balance(user_id, chat_id, initial_balance)
        
        # Play coinflip (will always win)
        result = engine.flip_coin(user_id, chat_id, bet_amount, choice)
        
        # Verify win occurred
        assert result.success, f"Coinflip should succeed: {result.message}"
        assert result.won, f"Should have won with choice={choice}, result={result.result}"
        assert result.choice == choice
        assert result.result == choice
        
        # Verify balance increased by bet amount (Requirements 8.2)
        expected_balance = initial_balance + bet_amount
        assert result.new_balance == expected_balance, \
            f"Balance should be {expected_balance}, got {result.new_balance}"
        
        # Verify balance_change equals +bet_amount
        assert result.balance_change == bet_amount, \
            f"Balance change should be {bet_amount}, got {result.balance_change}"
        
        # Verify balance in engine matches
        balance_data = engine.get_balance(user_id, chat_id)
        assert balance_data.balance == expected_balance
        assert balance_data.total_won >= bet_amount

    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        initial_balance=st.integers(min_value=100, max_value=10000),
        bet_amount=bet_amount_strategy,
        choice=choice_strategy
    )
    def test_loss_deducts_bet(
        self,
        user_id: int,
        chat_id: int,
        initial_balance: int,
        bet_amount: int,
        choice: str
    ):
        """
        Property 7: When player loses, balance decreases by exactly bet_amount.
        
        Requirements 8.3: WHEN the coinflip result does not match 
        THEN the system SHALL deduct the bet amount from user's balance.
        
        For any coinflip game where player loses:
        - Balance change equals -bet_amount
        - Final balance equals initial_balance - bet_amount
        """
        assume(initial_balance >= bet_amount)
        
        # Create engine with deterministic random that does NOT match player's choice
        # random < 0.5 = heads, random >= 0.5 = tails
        if choice == "heads":
            random_value = 0.5  # Will result in tails (player chose heads, loses)
        else:
            random_value = 0.0  # Will result in heads (player chose tails, loses)
        
        engine = GameEngine(random_func=lambda: random_value)
        
        # Set initial balance
        engine.set_balance(user_id, chat_id, initial_balance)
        
        # Play coinflip (will always lose)
        result = engine.flip_coin(user_id, chat_id, bet_amount, choice)
        
        # Verify loss occurred
        assert result.success, f"Coinflip should succeed: {result.message}"
        assert not result.won, f"Should have lost with choice={choice}, result={result.result}"
        assert result.choice == choice
        assert result.result != choice
        
        # Verify balance decreased by bet amount (Requirements 8.3)
        expected_balance = initial_balance - bet_amount
        assert result.new_balance == expected_balance, \
            f"Balance should be {expected_balance}, got {result.new_balance}"
        
        # Verify balance_change equals -bet_amount
        assert result.balance_change == -bet_amount, \
            f"Balance change should be -{bet_amount}, got {result.balance_change}"
        
        # Verify balance in engine matches
        balance_data = engine.get_balance(user_id, chat_id)
        assert balance_data.balance == expected_balance
        assert balance_data.total_lost >= bet_amount

    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        initial_balance=st.integers(min_value=100, max_value=10000),
        bet_amount=bet_amount_strategy,
        choice=choice_strategy,
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_balance_change_matches_outcome(
        self,
        user_id: int,
        chat_id: int,
        initial_balance: int,
        bet_amount: int,
        choice: str,
        seed: int
    ):
        """
        Property 7: Balance change always matches the game outcome.
        
        For any coinflip game:
        - If won: balance_change == +bet_amount
        - If lost: balance_change == -bet_amount
        - Final balance == initial_balance + balance_change
        """
        import random as rand_module
        
        assume(initial_balance >= bet_amount)
        
        # Create engine with seeded random
        rng = rand_module.Random(seed)
        engine = GameEngine(random_func=rng.random)
        
        # Set initial balance
        engine.set_balance(user_id, chat_id, initial_balance)
        
        # Play coinflip
        result = engine.flip_coin(user_id, chat_id, bet_amount, choice)
        
        assert result.success
        
        # Verify balance change matches outcome
        if result.won:
            expected_change = bet_amount
        else:
            expected_change = -bet_amount
        
        assert result.balance_change == expected_change, \
            f"Balance change should be {expected_change}, got {result.balance_change}"
        
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
        chat_id=chat_id_strategy,
        initial_balance=st.integers(min_value=1, max_value=1000),
        choice=choice_strategy
    )
    def test_exact_balance_bet_allowed(
        self,
        user_id: int,
        chat_id: int,
        initial_balance: int,
        choice: str
    ):
        """
        Property 7 edge case: Betting exact balance should be allowed.
        """
        engine = GameEngine()
        
        # Set initial balance
        engine.set_balance(user_id, chat_id, initial_balance)
        
        # Bet exact balance
        result = engine.flip_coin(user_id, chat_id, initial_balance, choice)
        
        # Should succeed
        assert result.success, f"Betting exact balance should succeed: {result.message}"
        
        # Balance should change appropriately
        if result.won:
            assert result.new_balance == initial_balance * 2, \
                f"Balance should double on win, got {result.new_balance}"
        else:
            assert result.new_balance == 0, \
                "Balance should be 0 after losing exact balance"



class TestCoinflipInsufficientBalanceRejection:
    """
    **Feature: grand-casino-dictator, Property 8: Coinflip Insufficient Balance Rejection**
    **Validates: Requirements 8.4**
    
    *For any* coinflip bet where bet_amount exceeds player's current balance, 
    the game is rejected and balance remains unchanged.
    """
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        initial_balance=st.integers(min_value=0, max_value=100),
        bet_excess=st.integers(min_value=1, max_value=1000),
        choice=choice_strategy
    )
    def test_insufficient_balance_rejects_bet(
        self,
        user_id: int,
        chat_id: int,
        initial_balance: int,
        bet_excess: int,
        choice: str
    ):
        """
        Property 8: Bets exceeding balance are rejected, balance unchanged.
        
        Requirements 8.4: IF a user has insufficient balance for the bet 
        THEN the system SHALL reject the bet and display an error message.
        
        For any bet amount > balance:
        - Coinflip should fail with INSUFFICIENT_BALANCE error
        - Balance should remain unchanged
        """
        bet_amount = initial_balance + bet_excess  # Always exceeds balance
        
        engine = GameEngine()
        
        # Set initial balance
        engine.set_balance(user_id, chat_id, initial_balance)
        
        # Try to play coinflip with insufficient balance
        result = engine.flip_coin(user_id, chat_id, bet_amount, choice)
        
        # Verify rejection
        assert not result.success, "Coinflip should fail with insufficient balance"
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
        choice=choice_strategy
    )
    def test_zero_balance_rejects_any_bet(
        self,
        user_id: int,
        chat_id: int,
        choice: str
    ):
        """
        Property 8 edge case: Zero balance rejects any positive bet.
        """
        engine = GameEngine()
        
        # Set zero balance
        engine.set_balance(user_id, chat_id, 0)
        
        # Try to bet any amount
        result = engine.flip_coin(user_id, chat_id, 1, choice)
        
        # Verify rejection
        assert not result.success, "Coinflip should fail with zero balance"
        assert result.error_code == "INSUFFICIENT_BALANCE"
        
        # Verify balance unchanged
        balance_data = engine.get_balance(user_id, chat_id)
        assert balance_data.balance == 0

    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        choice=choice_strategy
    )
    def test_negative_bet_rejected(
        self,
        user_id: int,
        chat_id: int,
        choice: str
    ):
        """
        Property 8 edge case: Negative bets are rejected.
        """
        engine = GameEngine()
        engine.set_balance(user_id, chat_id, 1000)
        
        # Try negative bet
        result = engine.flip_coin(user_id, chat_id, -100, choice)
        
        assert not result.success, "Negative bet should be rejected"
        assert result.error_code == "INVALID_BET", \
            f"Error code should be INVALID_BET, got {result.error_code}"
        
        # Balance unchanged
        balance_data = engine.get_balance(user_id, chat_id)
        assert balance_data.balance == 1000

    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        choice=choice_strategy
    )
    def test_zero_bet_rejected(
        self,
        user_id: int,
        chat_id: int,
        choice: str
    ):
        """
        Property 8 edge case: Zero bets are rejected.
        """
        engine = GameEngine()
        engine.set_balance(user_id, chat_id, 1000)
        
        # Try zero bet
        result = engine.flip_coin(user_id, chat_id, 0, choice)
        
        assert not result.success, "Zero bet should be rejected"
        assert result.error_code == "INVALID_BET", \
            f"Error code should be INVALID_BET, got {result.error_code}"
        
        # Balance unchanged
        balance_data = engine.get_balance(user_id, chat_id)
        assert balance_data.balance == 1000

    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy
    )
    def test_invalid_choice_rejected(
        self,
        user_id: int,
        chat_id: int
    ):
        """
        Property 8 edge case: Invalid choices are rejected.
        """
        engine = GameEngine()
        engine.set_balance(user_id, chat_id, 1000)
        
        # Try invalid choice
        result = engine.flip_coin(user_id, chat_id, 100, "invalid")
        
        assert not result.success, "Invalid choice should be rejected"
        assert result.error_code == "INVALID_CHOICE", \
            f"Error code should be INVALID_CHOICE, got {result.error_code}"
        
        # Balance unchanged
        balance_data = engine.get_balance(user_id, chat_id)
        assert balance_data.balance == 1000
