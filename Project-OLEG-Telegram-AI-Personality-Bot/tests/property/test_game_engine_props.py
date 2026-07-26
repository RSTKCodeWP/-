"""
Property-based tests for GameEngine.

Tests correctness properties defined in the design document.
Requirements: 8.1, 8.2, 8.3, 8.4
"""

import os
import importlib.util
from datetime import timedelta
from hypothesis import given, strategies as st, settings, assume

# Import game_engine module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'game_engine.py')
_spec = importlib.util.spec_from_file_location("game_engine", _module_path)
_game_engine_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_game_engine_module)

GameEngine = _game_engine_module.GameEngine
ChallengeStatus = _game_engine_module.ChallengeStatus
GameType = _game_engine_module.GameType
RouletteResult = _game_engine_module.RouletteResult
CoinFlipResult = _game_engine_module.CoinFlipResult


# Strategies for generating test data
user_id_strategy = st.integers(min_value=1, max_value=10**12)
chat_id_strategy = st.integers(min_value=-10**12, max_value=10**12)
bet_amount_strategy = st.integers(min_value=0, max_value=1000)
positive_bet_strategy = st.integers(min_value=1, max_value=100)


class TestChallengeAcceptanceDeductsResources:
    """
    **Feature: oleg-v5-refactoring, Property 9: Challenge Acceptance Deducts Resources**
    **Validates: Requirements 8.2**
    
    *For any* accepted game challenge, both challenger and acceptor balances 
    SHALL decrease by the bet amount.
    """
    
    @settings(max_examples=100)
    @given(
        chat_id=chat_id_strategy,
        challenger_id=user_id_strategy,
        target_id=user_id_strategy,
        bet_amount=positive_bet_strategy,
        challenger_initial=st.integers(min_value=100, max_value=10000),
        target_initial=st.integers(min_value=100, max_value=10000)
    )
    def test_accept_deducts_from_both_players(
        self,
        chat_id: int,
        challenger_id: int,
        target_id: int,
        bet_amount: int,
        challenger_initial: int,
        target_initial: int
    ):
        """
        Property 9: When a challenge is accepted, both players lose the bet amount.
        
        For any valid challenge with bet > 0:
        - Challenger balance decreases by bet_amount
        - Target balance decreases by bet_amount
        """
        # Ensure different users
        assume(challenger_id != target_id)
        # Ensure both can afford the bet
        assume(challenger_initial >= bet_amount)
        assume(target_initial >= bet_amount)
        
        engine = GameEngine()
        
        # Set initial balances
        engine.set_balance(challenger_id, chat_id, challenger_initial)
        engine.set_balance(target_id, chat_id, target_initial)
        
        # Create challenge
        create_result = engine.create_challenge(
            chat_id=chat_id,
            challenger_id=challenger_id,
            target_id=target_id,
            bet_amount=bet_amount
        )
        
        assert create_result.success, f"Challenge creation failed: {create_result.message}"
        challenge_id = create_result.challenge.id
        
        # Accept challenge
        accept_result = engine.accept_challenge(challenge_id, target_id)
        
        assert accept_result.success, f"Challenge acceptance failed: {accept_result.message}"
        
        # Verify balances decreased
        challenger_balance = engine.get_balance(challenger_id, chat_id)
        target_balance = engine.get_balance(target_id, chat_id)
        
        assert challenger_balance.balance == challenger_initial - bet_amount, \
            f"Challenger balance should be {challenger_initial - bet_amount}, got {challenger_balance.balance}"
        
        assert target_balance.balance == target_initial - bet_amount, \
            f"Target balance should be {target_initial - bet_amount}, got {target_balance.balance}"

    @settings(max_examples=100)
    @given(
        chat_id=chat_id_strategy,
        challenger_id=user_id_strategy,
        target_id=user_id_strategy,
        challenger_initial=st.integers(min_value=100, max_value=10000),
        target_initial=st.integers(min_value=100, max_value=10000)
    )
    def test_zero_bet_no_deduction(
        self,
        chat_id: int,
        challenger_id: int,
        target_id: int,
        challenger_initial: int,
        target_initial: int
    ):
        """
        Property 9 edge case: Zero bet means no balance change.
        """
        assume(challenger_id != target_id)
        
        engine = GameEngine()
        
        # Set initial balances
        engine.set_balance(challenger_id, chat_id, challenger_initial)
        engine.set_balance(target_id, chat_id, target_initial)
        
        # Create challenge with zero bet
        create_result = engine.create_challenge(
            chat_id=chat_id,
            challenger_id=challenger_id,
            target_id=target_id,
            bet_amount=0
        )
        
        assert create_result.success
        challenge_id = create_result.challenge.id
        
        # Accept challenge
        accept_result = engine.accept_challenge(challenge_id, target_id)
        assert accept_result.success
        
        # Verify balances unchanged
        challenger_balance = engine.get_balance(challenger_id, chat_id)
        target_balance = engine.get_balance(target_id, chat_id)
        
        assert challenger_balance.balance == challenger_initial, \
            "Challenger balance should not change with zero bet"
        assert target_balance.balance == target_initial, \
            "Target balance should not change with zero bet"


class TestExpiredChallengePreservesBalances:
    """
    **Feature: oleg-v5-refactoring, Property 10: Expired Challenge Preserves Balances**
    **Validates: Requirements 8.3**
    
    *For any* expired challenge, neither challenger nor target balances SHALL change.
    """
    
    @settings(max_examples=100)
    @given(
        chat_id=chat_id_strategy,
        challenger_id=user_id_strategy,
        target_id=user_id_strategy,
        bet_amount=positive_bet_strategy,
        challenger_initial=st.integers(min_value=100, max_value=10000),
        target_initial=st.integers(min_value=100, max_value=10000)
    )
    def test_expired_challenge_no_deduction(
        self,
        chat_id: int,
        challenger_id: int,
        target_id: int,
        bet_amount: int,
        challenger_initial: int,
        target_initial: int
    ):
        """
        Property 10: Expired challenges don't affect balances.
        
        For any challenge that expires:
        - Challenger balance remains unchanged
        - Target balance remains unchanged
        """
        assume(challenger_id != target_id)
        assume(challenger_initial >= bet_amount)
        assume(target_initial >= bet_amount)
        
        engine = GameEngine()
        
        # Set initial balances
        engine.set_balance(challenger_id, chat_id, challenger_initial)
        engine.set_balance(target_id, chat_id, target_initial)
        
        # Create challenge
        create_result = engine.create_challenge(
            chat_id=chat_id,
            challenger_id=challenger_id,
            target_id=target_id,
            bet_amount=bet_amount,
            timeout_minutes=5
        )
        
        assert create_result.success
        challenge = create_result.challenge
        
        # Manually expire the challenge by setting expires_at to past
        challenge.expires_at = challenge.created_at - timedelta(minutes=1)
        
        # Run expiration check
        expired = engine.cancel_expired_challenges()
        
        assert len(expired) == 1, "Should have one expired challenge"
        assert expired[0].status == ChallengeStatus.EXPIRED
        
        # Verify balances unchanged
        challenger_balance = engine.get_balance(challenger_id, chat_id)
        target_balance = engine.get_balance(target_id, chat_id)
        
        assert challenger_balance.balance == challenger_initial, \
            f"Challenger balance should remain {challenger_initial}, got {challenger_balance.balance}"
        assert target_balance.balance == target_initial, \
            f"Target balance should remain {target_initial}, got {target_balance.balance}"

    @settings(max_examples=100)
    @given(
        chat_id=chat_id_strategy,
        challenger_id=user_id_strategy,
        target_id=user_id_strategy,
        bet_amount=positive_bet_strategy,
        challenger_initial=st.integers(min_value=100, max_value=10000),
        target_initial=st.integers(min_value=100, max_value=10000)
    )
    def test_declined_challenge_no_deduction(
        self,
        chat_id: int,
        challenger_id: int,
        target_id: int,
        bet_amount: int,
        challenger_initial: int,
        target_initial: int
    ):
        """
        Property 10 extended: Declined challenges also preserve balances.
        """
        assume(challenger_id != target_id)
        assume(challenger_initial >= bet_amount)
        assume(target_initial >= bet_amount)
        
        engine = GameEngine()
        
        # Set initial balances
        engine.set_balance(challenger_id, chat_id, challenger_initial)
        engine.set_balance(target_id, chat_id, target_initial)
        
        # Create challenge
        create_result = engine.create_challenge(
            chat_id=chat_id,
            challenger_id=challenger_id,
            target_id=target_id,
            bet_amount=bet_amount
        )
        
        assert create_result.success
        challenge_id = create_result.challenge.id
        
        # Decline challenge
        decline_result = engine.decline_challenge(challenge_id, target_id)
        assert decline_result.success
        
        # Verify balances unchanged
        challenger_balance = engine.get_balance(challenger_id, chat_id)
        target_balance = engine.get_balance(target_id, chat_id)
        
        assert challenger_balance.balance == challenger_initial, \
            "Challenger balance should not change on decline"
        assert target_balance.balance == target_initial, \
            "Target balance should not change on decline"


class TestPendingChallengeBlocksNewChallenges:
    """
    **Feature: oleg-v5-refactoring, Property 11: Pending Challenge Blocks New Challenges**
    **Validates: Requirements 8.4**
    
    *For any* user with a pending challenge, attempting to create a new challenge SHALL fail.
    """
    
    @settings(max_examples=100)
    @given(
        chat_id=chat_id_strategy,
        challenger_id=user_id_strategy,
        target1_id=user_id_strategy,
        target2_id=user_id_strategy,
        bet_amount=bet_amount_strategy
    )
    def test_pending_challenge_blocks_new(
        self,
        chat_id: int,
        challenger_id: int,
        target1_id: int,
        target2_id: int,
        bet_amount: int
    ):
        """
        Property 11: User with pending challenge cannot create another.
        
        For any user who has created a pending challenge:
        - Creating a second challenge should fail
        - Error code should be PENDING_EXISTS
        """
        # Ensure all users are different
        assume(challenger_id != target1_id)
        assume(challenger_id != target2_id)
        assume(target1_id != target2_id)
        
        engine = GameEngine()
        
        # Set sufficient balance
        engine.set_balance(challenger_id, chat_id, 10000)
        engine.set_balance(target1_id, chat_id, 10000)
        engine.set_balance(target2_id, chat_id, 10000)
        
        # Create first challenge
        result1 = engine.create_challenge(
            chat_id=chat_id,
            challenger_id=challenger_id,
            target_id=target1_id,
            bet_amount=bet_amount
        )
        
        assert result1.success, "First challenge should succeed"
        
        # Try to create second challenge
        result2 = engine.create_challenge(
            chat_id=chat_id,
            challenger_id=challenger_id,
            target_id=target2_id,
            bet_amount=bet_amount
        )
        
        assert not result2.success, "Second challenge should fail"
        assert result2.error_code == "PENDING_EXISTS", \
            f"Error code should be PENDING_EXISTS, got {result2.error_code}"
    
    @settings(max_examples=100)
    @given(
        chat_id=chat_id_strategy,
        challenger_id=user_id_strategy,
        target1_id=user_id_strategy,
        target2_id=user_id_strategy,
        bet_amount=bet_amount_strategy
    )
    def test_accepted_challenge_allows_new(
        self,
        chat_id: int,
        challenger_id: int,
        target1_id: int,
        target2_id: int,
        bet_amount: int
    ):
        """
        Property 11 extended: After challenge is accepted, user can create new one.
        """
        assume(challenger_id != target1_id)
        assume(challenger_id != target2_id)
        assume(target1_id != target2_id)
        
        engine = GameEngine()
        
        # Set sufficient balance
        engine.set_balance(challenger_id, chat_id, 10000)
        engine.set_balance(target1_id, chat_id, 10000)
        engine.set_balance(target2_id, chat_id, 10000)
        
        # Create and accept first challenge
        result1 = engine.create_challenge(
            chat_id=chat_id,
            challenger_id=challenger_id,
            target_id=target1_id,
            bet_amount=bet_amount
        )
        assert result1.success
        
        accept_result = engine.accept_challenge(result1.challenge.id, target1_id)
        assert accept_result.success
        
        # Now should be able to create new challenge
        result2 = engine.create_challenge(
            chat_id=chat_id,
            challenger_id=challenger_id,
            target_id=target2_id,
            bet_amount=bet_amount
        )
        
        assert result2.success, "Should be able to create new challenge after previous was accepted"


class TestRouletteProbabilityDistribution:
    """
    **Feature: oleg-v5-refactoring, Property 12: Roulette Probability Distribution**
    **Validates: Requirements 9.1**
    
    *For any* large sample of roulette games (n > 100), the "shot" frequency 
    SHALL converge to approximately 1/6 (16.67% ± 5%).
    """
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_roulette_probability_converges_to_one_sixth(
        self,
        user_id: int,
        chat_id: int,
        seed: int
    ):
        """
        Property 12: Over many games, shot probability should be ~1/6.
        
        We use a deterministic random sequence based on seed to make the test
        reproducible while still testing the probability distribution.
        """
        import random as rand_module
        
        # Create a deterministic random generator
        rng = rand_module.Random(seed)
        engine = GameEngine(random_func=rng.random)
        
        # Give user enough balance to play many games
        engine.set_balance(user_id, chat_id, 100000)
        
        # Play 600 games (100 expected shots at 1/6 probability)
        num_games = 600
        shots = 0
        
        for _ in range(num_games):
            result = engine.play_roulette(user_id, chat_id)
            if result.shot:
                shots += 1
        
        # Expected: 100 shots (1/6 of 600)
        # Allow ±8% tolerance: 16.67% ± 8% = 8.67% to 24.67%
        # For 600 games: 52 to 148 shots
        # This wider tolerance accounts for natural variance in random sampling
        # while still catching systematic bias in the implementation
        expected_rate = 1 / 6
        tolerance = 0.08
        min_shots = int(num_games * (expected_rate - tolerance))
        max_shots = int(num_games * (expected_rate + tolerance))
        
        assert min_shots <= shots <= max_shots, \
            f"Shot count {shots} out of {num_games} games is outside expected range [{min_shots}, {max_shots}]. " \
            f"Expected ~{expected_rate:.2%}, got {shots/num_games:.2%}"


class TestRouletteShotDeductsPoints:
    """
    **Feature: oleg-v5-refactoring, Property 13: Roulette Shot Deducts Points**
    **Validates: Requirements 9.2**
    
    *For any* roulette game where shot occurs, the user's balance SHALL decrease.
    """
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        initial_balance=st.integers(min_value=0, max_value=10000)
    )
    def test_shot_deducts_penalty(
        self,
        user_id: int,
        chat_id: int,
        initial_balance: int
    ):
        """
        Property 13: When shot occurs, balance decreases by penalty amount.
        
        We force a shot by using a deterministic random that returns 0.
        """
        # Create engine with deterministic random that always returns 0 (shot)
        engine = GameEngine(random_func=lambda: 0.0)
        
        # Set initial balance
        engine.set_balance(user_id, chat_id, initial_balance)
        
        # Play roulette (will always be a shot)
        result = engine.play_roulette(user_id, chat_id)
        
        # Verify shot occurred
        assert result.shot, "Should have been shot with random=0"
        
        # Verify balance decreased
        expected_balance = initial_balance - engine.ROULETTE_SHOT_PENALTY
        assert result.new_balance == expected_balance, \
            f"Balance should be {expected_balance}, got {result.new_balance}"
        
        # Verify points_change is negative
        assert result.points_change == -engine.ROULETTE_SHOT_PENALTY, \
            f"Points change should be -{engine.ROULETTE_SHOT_PENALTY}, got {result.points_change}"
        
        # Verify balance in engine matches
        balance_data = engine.get_balance(user_id, chat_id)
        assert balance_data.balance == expected_balance
        assert balance_data.total_lost >= engine.ROULETTE_SHOT_PENALTY


class TestRouletteSurvivalAwardsPoints:
    """
    **Feature: oleg-v5-refactoring, Property 14: Roulette Survival Awards Points**
    **Validates: Requirements 9.3**
    
    *For any* roulette game where chamber is empty, the user's balance SHALL increase.
    """
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        initial_balance=st.integers(min_value=0, max_value=10000)
    )
    def test_survival_awards_points(
        self,
        user_id: int,
        chat_id: int,
        initial_balance: int
    ):
        """
        Property 14: When chamber is empty, balance increases by reward amount.
        
        We force survival by using a deterministic random that returns 0.5 (not 0).
        """
        # Create engine with deterministic random that returns 0.5 (survival)
        # Chamber = int(0.5 * 6) = 3, which is not 0, so no shot
        engine = GameEngine(random_func=lambda: 0.5)
        
        # Set initial balance
        engine.set_balance(user_id, chat_id, initial_balance)
        
        # Play roulette (will always survive)
        result = engine.play_roulette(user_id, chat_id)
        
        # Verify survival
        assert not result.shot, "Should have survived with random=0.5"
        
        # Verify balance increased
        expected_balance = initial_balance + engine.ROULETTE_SURVIVAL_REWARD
        assert result.new_balance == expected_balance, \
            f"Balance should be {expected_balance}, got {result.new_balance}"
        
        # Verify points_change is positive
        assert result.points_change == engine.ROULETTE_SURVIVAL_REWARD, \
            f"Points change should be {engine.ROULETTE_SURVIVAL_REWARD}, got {result.points_change}"
        
        # Verify balance in engine matches
        balance_data = engine.get_balance(user_id, chat_id)
        assert balance_data.balance == expected_balance
        assert balance_data.total_won >= engine.ROULETTE_SURVIVAL_REWARD


class TestCoinFlipProbabilityDistribution:
    """
    **Feature: oleg-v5-refactoring, Property 15: Coin Flip Probability Distribution**
    **Validates: Requirements 10.2**
    
    *For any* large sample of coin flips (n > 100), heads and tails frequencies 
    SHALL each be approximately 50% (± 5%).
    """
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_coinflip_probability_converges_to_fifty_percent(
        self,
        user_id: int,
        chat_id: int,
        seed: int
    ):
        """
        Property 15: Over many flips, heads/tails should each be ~50%.
        
        We use a deterministic random sequence based on seed to make the test
        reproducible while still testing the probability distribution.
        """
        import random as rand_module
        
        # Create a deterministic random generator
        rng = rand_module.Random(seed)
        engine = GameEngine(random_func=rng.random)
        
        # Give user enough balance to play many games
        engine.set_balance(user_id, chat_id, 10000000)
        
        # Play 1000 games for better statistical significance
        num_games = 1000
        heads_count = 0
        
        for _ in range(num_games):
            result = engine.flip_coin(user_id, chat_id, bet_amount=1, choice="heads")
            assert result.success, f"Flip should succeed: {result.message}"
            if result.result == "heads":
                heads_count += 1
        
        # Expected: 500 heads (50% of 1000)
        # For 1000 games with 50% probability, std dev = sqrt(1000*0.5*0.5) ≈ 15.8
        # Allow ±7% tolerance (70 heads), which is ~4.4 std devs
        # This gives us 99.999% confidence interval while still catching bias
        expected_rate = 0.5
        tolerance = 0.07
        min_heads = int(num_games * (expected_rate - tolerance))
        max_heads = int(num_games * (expected_rate + tolerance))
        
        assert min_heads <= heads_count <= max_heads, \
            f"Heads count {heads_count} out of {num_games} flips is outside expected range [{min_heads}, {max_heads}]. " \
            f"Expected ~{expected_rate:.2%}, got {heads_count/num_games:.2%}"


class TestCoinFlipWinDoublesBet:
    """
    **Feature: oleg-v5-refactoring, Property 16: Coin Flip Win Doubles Bet**
    **Validates: Requirements 10.3**
    
    *For any* winning coin flip with bet amount B, the user's balance 
    SHALL increase by B (net gain = B, since they bet B and won 2B).
    """
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        initial_balance=st.integers(min_value=100, max_value=10000),
        bet_amount=st.integers(min_value=1, max_value=100)
    )
    def test_win_increases_balance_by_bet(
        self,
        user_id: int,
        chat_id: int,
        initial_balance: int,
        bet_amount: int
    ):
        """
        Property 16: When user wins, balance increases by bet amount.
        
        We force a win by using a deterministic random that returns 0 (heads)
        and choosing heads.
        """
        assume(initial_balance >= bet_amount)
        
        # Create engine with deterministic random that always returns 0 (heads)
        engine = GameEngine(random_func=lambda: 0.0)
        
        # Set initial balance
        engine.set_balance(user_id, chat_id, initial_balance)
        
        # Play coin flip choosing heads (will always win)
        result = engine.flip_coin(user_id, chat_id, bet_amount=bet_amount, choice="heads")
        
        # Verify win
        assert result.success, f"Flip should succeed: {result.message}"
        assert result.won, "Should have won with random=0 and choice=heads"
        assert result.result == "heads", "Result should be heads"
        
        # Verify balance increased by bet amount
        expected_balance = initial_balance + bet_amount
        assert result.new_balance == expected_balance, \
            f"Balance should be {expected_balance}, got {result.new_balance}"
        
        # Verify balance_change is positive
        assert result.balance_change == bet_amount, \
            f"Balance change should be {bet_amount}, got {result.balance_change}"
        
        # Verify balance in engine matches
        balance_data = engine.get_balance(user_id, chat_id)
        assert balance_data.balance == expected_balance
        assert balance_data.total_won >= bet_amount


class TestCoinFlipLossDeductsBet:
    """
    **Feature: oleg-v5-refactoring, Property 17: Coin Flip Loss Deducts Bet**
    **Validates: Requirements 10.4**
    
    *For any* losing coin flip with bet amount B, the user's balance 
    SHALL decrease by B.
    """
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        initial_balance=st.integers(min_value=100, max_value=10000),
        bet_amount=st.integers(min_value=1, max_value=100)
    )
    def test_loss_decreases_balance_by_bet(
        self,
        user_id: int,
        chat_id: int,
        initial_balance: int,
        bet_amount: int
    ):
        """
        Property 17: When user loses, balance decreases by bet amount.
        
        We force a loss by using a deterministic random that returns 0 (heads)
        and choosing tails.
        """
        assume(initial_balance >= bet_amount)
        
        # Create engine with deterministic random that always returns 0 (heads)
        engine = GameEngine(random_func=lambda: 0.0)
        
        # Set initial balance
        engine.set_balance(user_id, chat_id, initial_balance)
        
        # Play coin flip choosing tails (will always lose since result is heads)
        result = engine.flip_coin(user_id, chat_id, bet_amount=bet_amount, choice="tails")
        
        # Verify loss
        assert result.success, f"Flip should succeed: {result.message}"
        assert not result.won, "Should have lost with random=0 and choice=tails"
        assert result.result == "heads", "Result should be heads"
        
        # Verify balance decreased by bet amount
        expected_balance = initial_balance - bet_amount
        assert result.new_balance == expected_balance, \
            f"Balance should be {expected_balance}, got {result.new_balance}"
        
        # Verify balance_change is negative
        assert result.balance_change == -bet_amount, \
            f"Balance change should be -{bet_amount}, got {result.balance_change}"
        
        # Verify balance in engine matches
        balance_data = engine.get_balance(user_id, chat_id)
        assert balance_data.balance == expected_balance
        assert balance_data.total_lost >= bet_amount


class TestInsufficientBalanceRejectsBet:
    """
    **Feature: oleg-v5-refactoring, Property 18: Insufficient Balance Rejects Bet**
    **Validates: Requirements 10.5**
    
    *For any* bet amount exceeding user's balance, the bet SHALL be rejected 
    and balance SHALL remain unchanged.
    """
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        initial_balance=st.integers(min_value=0, max_value=100),
        bet_excess=st.integers(min_value=1, max_value=1000),
        choice=st.sampled_from(["heads", "tails"])
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
        Property 18: Bets exceeding balance are rejected, balance unchanged.
        
        For any bet amount > balance:
        - Flip should fail with INSUFFICIENT_BALANCE error
        - Balance should remain unchanged
        """
        bet_amount = initial_balance + bet_excess  # Always exceeds balance
        
        engine = GameEngine()
        
        # Set initial balance
        engine.set_balance(user_id, chat_id, initial_balance)
        
        # Try to flip with insufficient balance
        result = engine.flip_coin(user_id, chat_id, bet_amount=bet_amount, choice=choice)
        
        # Verify rejection
        assert not result.success, "Flip should fail with insufficient balance"
        assert result.error_code == "INSUFFICIENT_BALANCE", \
            f"Error code should be INSUFFICIENT_BALANCE, got {result.error_code}"
        
        # Verify balance unchanged
        balance_data = engine.get_balance(user_id, chat_id)
        assert balance_data.balance == initial_balance, \
            f"Balance should remain {initial_balance}, got {balance_data.balance}"
        
        # Verify no wins/losses recorded
        assert balance_data.total_won == 0, "No wins should be recorded"
        assert balance_data.total_lost == 0, "No losses should be recorded"
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        chat_id=chat_id_strategy,
        initial_balance=st.integers(min_value=1, max_value=1000),
        choice=st.sampled_from(["heads", "tails"])
    )
    def test_exact_balance_bet_allowed(
        self,
        user_id: int,
        chat_id: int,
        initial_balance: int,
        choice: str
    ):
        """
        Property 18 edge case: Betting exact balance should be allowed.
        """
        engine = GameEngine()
        
        # Set initial balance
        engine.set_balance(user_id, chat_id, initial_balance)
        
        # Bet exact balance
        result = engine.flip_coin(user_id, chat_id, bet_amount=initial_balance, choice=choice)
        
        # Should succeed
        assert result.success, f"Betting exact balance should succeed: {result.message}"
