"""
Property-based tests for Blackjack engine.

Tests correctness properties defined in the design document.
Requirements: 9.3, 9.4, 9.5, 9.6, 9.7, 9.8
"""

import os
import importlib.util
from hypothesis import given, strategies as st, settings, assume

# Import blackjack module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'blackjack.py')
_spec = importlib.util.spec_from_file_location("blackjack", _module_path)
_blackjack_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_blackjack_module)

Card = _blackjack_module.Card
Hand = _blackjack_module.Hand
BlackjackGame = _blackjack_module.BlackjackGame
BlackjackEngine = _blackjack_module.BlackjackEngine
GameStatus = _blackjack_module.GameStatus
SUITS = _blackjack_module.SUITS
RANKS = _blackjack_module.RANKS


# Strategies for generating test data
suit_strategy = st.sampled_from(SUITS)
rank_strategy = st.sampled_from(RANKS)
card_strategy = st.builds(Card, suit=suit_strategy, rank=rank_strategy)
cards_strategy = st.lists(card_strategy, min_size=1, max_size=10)
bet_strategy = st.integers(min_value=1, max_value=10000)
user_id_strategy = st.integers(min_value=1, max_value=10**12)


class TestBlackjackBustDetection:
    """
    **Feature: grand-casino-dictator, Property 12: Blackjack Bust Detection**
    **Validates: Requirements 9.6**
    
    *For any* Blackjack hand with value exceeding 21, the hand is correctly 
    identified as busted.
    """
    
    @settings(max_examples=100)
    @given(cards=cards_strategy)
    def test_hand_busted_when_value_exceeds_21(self, cards: list):
        """
        Property 12: Hand is busted if and only if value > 21.
        
        For any hand:
        - is_busted is True iff value > 21
        - is_busted is False iff value <= 21
        """
        hand = Hand(cards=cards)
        value = hand.value
        
        if value > 21:
            assert hand.is_busted, \
                f"Hand with value {value} should be busted, cards: {[str(c) for c in cards]}"
        else:
            assert not hand.is_busted, \
                f"Hand with value {value} should not be busted, cards: {[str(c) for c in cards]}"
    
    @settings(max_examples=100)
    @given(
        num_high_cards=st.integers(min_value=3, max_value=5),
        suits=st.lists(suit_strategy, min_size=5, max_size=5)
    )
    def test_multiple_high_cards_always_bust(self, num_high_cards: int, suits: list):
        """
        Property 12 edge case: Multiple high cards (10, J, Q, K) always bust.
        
        Three or more cards with value 10 will always exceed 21.
        """
        high_ranks = ["10", "J", "Q", "K"]
        cards = [Card(suits[i % len(suits)], high_ranks[i % len(high_ranks)]) 
                 for i in range(num_high_cards)]
        
        hand = Hand(cards=cards)
        
        # 3+ cards of value 10 = 30+ which is always > 21
        assert hand.is_busted, \
            f"Hand with {num_high_cards} high cards (value {hand.value}) should be busted"
    
    @settings(max_examples=100)
    @given(suit=suit_strategy)
    def test_single_card_never_busts(self, suit: str):
        """
        Property 12 edge case: A single card can never bust.
        
        Maximum single card value is 11 (Ace), which is <= 21.
        """
        for rank in RANKS:
            hand = Hand(cards=[Card(suit, rank)])
            assert not hand.is_busted, \
                f"Single card {rank}{suit} should never bust"



class TestBlackjackNaturalDetection:
    """
    **Feature: grand-casino-dictator, Property 14: Blackjack Natural Detection**
    **Validates: Requirements 9.8**
    
    *For any* initial two-card hand totaling exactly 21, the hand is correctly 
    identified as Blackjack.
    """
    
    @settings(max_examples=100)
    @given(
        ace_suit=suit_strategy,
        ten_suit=suit_strategy,
        ten_rank=st.sampled_from(["10", "J", "Q", "K"])
    )
    def test_ace_plus_ten_is_blackjack(self, ace_suit: str, ten_suit: str, ten_rank: str):
        """
        Property 14: Ace + 10-value card = Blackjack.
        
        Any combination of Ace with 10, J, Q, or K should be detected as Blackjack.
        """
        hand = Hand(cards=[Card(ace_suit, "A"), Card(ten_suit, ten_rank)])
        
        assert hand.value == 21, \
            f"Ace + {ten_rank} should equal 21, got {hand.value}"
        assert hand.is_blackjack, \
            f"Ace + {ten_rank} should be Blackjack"
    
    @settings(max_examples=100)
    @given(
        ten_suit=suit_strategy,
        ace_suit=suit_strategy,
        ten_rank=st.sampled_from(["10", "J", "Q", "K"])
    )
    def test_ten_plus_ace_is_blackjack(self, ten_suit: str, ace_suit: str, ten_rank: str):
        """
        Property 14: Order doesn't matter - 10-value + Ace = Blackjack.
        """
        hand = Hand(cards=[Card(ten_suit, ten_rank), Card(ace_suit, "A")])
        
        assert hand.value == 21, \
            f"{ten_rank} + Ace should equal 21, got {hand.value}"
        assert hand.is_blackjack, \
            f"{ten_rank} + Ace should be Blackjack"
    
    @settings(max_examples=100)
    @given(cards=st.lists(card_strategy, min_size=3, max_size=7))
    def test_three_or_more_cards_not_blackjack(self, cards: list):
        """
        Property 14: Blackjack requires exactly 2 cards.
        
        Even if 3+ cards total 21, it's not a Blackjack.
        """
        hand = Hand(cards=cards)
        
        # Blackjack requires exactly 2 cards
        assert not hand.is_blackjack, \
            f"Hand with {len(cards)} cards should not be Blackjack even if value is {hand.value}"
    
    @settings(max_examples=100)
    @given(
        card1=card_strategy,
        card2=card_strategy
    )
    def test_two_cards_blackjack_iff_value_21(self, card1: Card, card2: Card):
        """
        Property 14: Two-card hand is Blackjack iff value equals 21.
        """
        hand = Hand(cards=[card1, card2])
        
        if hand.value == 21:
            assert hand.is_blackjack, \
                f"Two cards totaling 21 should be Blackjack: {card1}, {card2}"
        else:
            assert not hand.is_blackjack, \
                f"Two cards totaling {hand.value} should not be Blackjack: {card1}, {card2}"


class TestBlackjackHitCardCount:
    """
    **Feature: grand-casino-dictator, Property 9: Blackjack Hit Card Count**
    **Validates: Requirements 9.3**
    
    *For any* Blackjack game in playing state, calling hit() increases the 
    player's hand size by exactly one card.
    """
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        bet=bet_strategy,
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_hit_adds_exactly_one_card(self, user_id: int, bet: int, seed: int):
        """
        Property 9: Hit adds exactly one card to player's hand.
        
        For any game in PLAYING state:
        - After hit(), player hand size increases by 1
        - Deck size decreases by 1
        """
        import random as rand_module
        rng = rand_module.Random(seed)
        engine = BlackjackEngine(random_func=rng.random)
        
        game = engine.create_game(user_id=user_id, bet=bet)
        
        # Skip if game already ended (blackjack or dealer blackjack)
        assume(game.status == GameStatus.PLAYING)
        
        initial_hand_size = len(game.player_hand.cards)
        initial_deck_size = len(game.deck)
        
        game = engine.hit(game)
        
        assert len(game.player_hand.cards) == initial_hand_size + 1, \
            f"Hit should add exactly one card. Before: {initial_hand_size}, After: {len(game.player_hand.cards)}"
        
        assert len(game.deck) == initial_deck_size - 1, \
            f"Deck should decrease by one. Before: {initial_deck_size}, After: {len(game.deck)}"
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        bet=bet_strategy,
        num_hits=st.integers(min_value=1, max_value=5),
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_multiple_hits_add_correct_cards(self, user_id: int, bet: int, num_hits: int, seed: int):
        """
        Property 9 extended: Multiple hits add correct number of cards.
        
        For any sequence of hits while game is PLAYING:
        - Each hit adds exactly one card
        - Total cards added equals number of hits
        """
        import random as rand_module
        rng = rand_module.Random(seed)
        engine = BlackjackEngine(random_func=rng.random)
        
        game = engine.create_game(user_id=user_id, bet=bet)
        assume(game.status == GameStatus.PLAYING)
        
        initial_hand_size = len(game.player_hand.cards)
        hits_performed = 0
        
        for _ in range(num_hits):
            if game.status != GameStatus.PLAYING:
                break
            game = engine.hit(game)
            hits_performed += 1
        
        expected_size = initial_hand_size + hits_performed
        assert len(game.player_hand.cards) == expected_size, \
            f"After {hits_performed} hits, hand should have {expected_size} cards, got {len(game.player_hand.cards)}"
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        bet=bet_strategy,
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_hit_on_non_playing_game_no_change(self, user_id: int, bet: int, seed: int):
        """
        Property 9 edge case: Hit on non-PLAYING game doesn't change hand.
        """
        import random as rand_module
        rng = rand_module.Random(seed)
        engine = BlackjackEngine(random_func=rng.random)
        
        game = engine.create_game(user_id=user_id, bet=bet)
        
        # Force game to end by hitting until bust or standing
        while game.status == GameStatus.PLAYING:
            game = engine.hit(game)
        
        # Now game is not PLAYING
        hand_size_before = len(game.player_hand.cards)
        game = engine.hit(game)
        
        assert len(game.player_hand.cards) == hand_size_before, \
            "Hit on non-PLAYING game should not change hand size"


class TestBlackjackStandDealerDraw:
    """
    **Feature: grand-casino-dictator, Property 10: Blackjack Stand Dealer Draw**
    **Validates: Requirements 9.4**
    
    *For any* Blackjack game where player stands, the dealer draws cards 
    until hand value is 17 or higher.
    """
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        bet=bet_strategy,
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_dealer_draws_to_17_or_higher(self, user_id: int, bet: int, seed: int):
        """
        Property 10: After stand, dealer has 17+ or is busted.
        
        For any game where player stands:
        - Dealer's final hand value is >= 17 OR dealer is busted
        """
        import random as rand_module
        rng = rand_module.Random(seed)
        engine = BlackjackEngine(random_func=rng.random)
        
        game = engine.create_game(user_id=user_id, bet=bet)
        assume(game.status == GameStatus.PLAYING)
        
        game = engine.stand(game)
        
        # Dealer should have 17+ or be busted
        if game.dealer_hand.is_busted:
            assert game.status == GameStatus.DEALER_BUSTED, \
                "Busted dealer should result in DEALER_BUSTED status"
        else:
            assert game.dealer_hand.value >= 17, \
                f"Dealer should have 17+, got {game.dealer_hand.value}"
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        bet=bet_strategy,
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_dealer_stops_at_17_or_higher(self, user_id: int, bet: int, seed: int):
        """
        Property 10 extended: Dealer stops drawing once reaching 17+.
        
        If dealer's initial hand is already 17+, no additional cards are drawn.
        """
        import random as rand_module
        rng = rand_module.Random(seed)
        engine = BlackjackEngine(random_func=rng.random)
        
        game = engine.create_game(user_id=user_id, bet=bet)
        assume(game.status == GameStatus.PLAYING)
        
        initial_dealer_cards = len(game.dealer_hand.cards)
        initial_dealer_value = game.dealer_hand.value
        
        game = engine.stand(game)
        
        # If dealer started with 17+, should not have drawn more cards
        if initial_dealer_value >= 17:
            assert len(game.dealer_hand.cards) == initial_dealer_cards, \
                f"Dealer with {initial_dealer_value} should not draw more cards"
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        bet=bet_strategy,
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_stand_ends_game(self, user_id: int, bet: int, seed: int):
        """
        Property 10 extended: Stand always ends the game.
        
        After stand, game status is never PLAYING.
        """
        import random as rand_module
        rng = rand_module.Random(seed)
        engine = BlackjackEngine(random_func=rng.random)
        
        game = engine.create_game(user_id=user_id, bet=bet)
        assume(game.status == GameStatus.PLAYING)
        
        game = engine.stand(game)
        
        assert game.status != GameStatus.PLAYING, \
            "After stand, game should not be in PLAYING state"
        
        valid_end_states = {
            GameStatus.PLAYER_WIN,
            GameStatus.DEALER_WIN,
            GameStatus.DEALER_BUSTED,
            GameStatus.PUSH
        }
        assert game.status in valid_end_states, \
            f"Game should end in valid state, got {game.status}"


class TestBlackjackDoubleMechanics:
    """
    **Feature: grand-casino-dictator, Property 11: Blackjack Double Mechanics**
    **Validates: Requirements 9.5**
    
    *For any* Blackjack game where player doubles, the bet is doubled, 
    exactly one card is dealt, and the game proceeds to dealer's turn.
    """
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        bet=bet_strategy,
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_double_doubles_bet(self, user_id: int, bet: int, seed: int):
        """
        Property 11: Double doubles the bet amount.
        """
        import random as rand_module
        rng = rand_module.Random(seed)
        engine = BlackjackEngine(random_func=rng.random)
        
        game = engine.create_game(user_id=user_id, bet=bet)
        assume(game.status == GameStatus.PLAYING)
        
        original_bet = game.bet
        game = engine.double(game)
        
        assert game.bet == original_bet * 2, \
            f"Bet should double from {original_bet} to {original_bet * 2}, got {game.bet}"
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        bet=bet_strategy,
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_double_adds_exactly_one_card(self, user_id: int, bet: int, seed: int):
        """
        Property 11: Double deals exactly one card to player.
        """
        import random as rand_module
        rng = rand_module.Random(seed)
        engine = BlackjackEngine(random_func=rng.random)
        
        game = engine.create_game(user_id=user_id, bet=bet)
        assume(game.status == GameStatus.PLAYING)
        
        initial_cards = len(game.player_hand.cards)
        game = engine.double(game)
        
        assert len(game.player_hand.cards) == initial_cards + 1, \
            f"Double should add exactly one card. Before: {initial_cards}, After: {len(game.player_hand.cards)}"
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        bet=bet_strategy,
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_double_ends_game(self, user_id: int, bet: int, seed: int):
        """
        Property 11: Double automatically stands and ends the game.
        """
        import random as rand_module
        rng = rand_module.Random(seed)
        engine = BlackjackEngine(random_func=rng.random)
        
        game = engine.create_game(user_id=user_id, bet=bet)
        assume(game.status == GameStatus.PLAYING)
        
        game = engine.double(game)
        
        assert game.status != GameStatus.PLAYING, \
            "After double, game should not be in PLAYING state"
        
        valid_end_states = {
            GameStatus.PLAYER_WIN,
            GameStatus.DEALER_WIN,
            GameStatus.PLAYER_BUSTED,
            GameStatus.DEALER_BUSTED,
            GameStatus.PUSH
        }
        assert game.status in valid_end_states, \
            f"Game should end in valid state, got {game.status}"
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        bet=bet_strategy,
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_double_on_non_playing_no_change(self, user_id: int, bet: int, seed: int):
        """
        Property 11 edge case: Double on non-PLAYING game doesn't change anything.
        """
        import random as rand_module
        rng = rand_module.Random(seed)
        engine = BlackjackEngine(random_func=rng.random)
        
        game = engine.create_game(user_id=user_id, bet=bet)
        
        # Force game to end
        while game.status == GameStatus.PLAYING:
            game = engine.hit(game)
        
        bet_before = game.bet
        cards_before = len(game.player_hand.cards)
        status_before = game.status
        
        game = engine.double(game)
        
        assert game.bet == bet_before, "Bet should not change on non-PLAYING game"
        assert len(game.player_hand.cards) == cards_before, "Cards should not change"
        assert game.status == status_before, "Status should not change"


class TestBlackjackWinnerDetermination:
    """
    **Feature: grand-casino-dictator, Property 13: Blackjack Winner Determination**
    **Validates: Requirements 9.7**
    
    *For any* two Blackjack hands that are not busted, the hand closer to 21 
    wins; if equal, it's a push.
    """
    
    @settings(max_examples=100)
    @given(
        player_value=st.integers(min_value=2, max_value=21),
        dealer_value=st.integers(min_value=2, max_value=21)
    )
    def test_higher_value_wins(self, player_value: int, dealer_value: int):
        """
        Property 13: Higher hand value wins (when neither busted).
        
        For any two valid hand values (2-21):
        - Higher value wins
        - Equal values result in push
        """
        engine = BlackjackEngine()
        result = engine.determine_winner(player_value, dealer_value)
        
        if player_value > dealer_value:
            assert result == "player", \
                f"Player with {player_value} should beat dealer with {dealer_value}"
        elif dealer_value > player_value:
            assert result == "dealer", \
                f"Dealer with {dealer_value} should beat player with {player_value}"
        else:
            assert result == "push", \
                f"Equal values ({player_value}) should result in push"
    
    @settings(max_examples=100)
    @given(value=st.integers(min_value=2, max_value=21))
    def test_equal_values_push(self, value: int):
        """
        Property 13: Equal hand values always result in push.
        """
        engine = BlackjackEngine()
        result = engine.determine_winner(value, value)
        
        assert result == "push", \
            f"Equal values ({value}) should always result in push"
    
    @settings(max_examples=100)
    @given(
        user_id=user_id_strategy,
        bet=bet_strategy,
        seed=st.integers(min_value=0, max_value=2**32 - 1)
    )
    def test_game_winner_matches_hand_comparison(self, user_id: int, bet: int, seed: int):
        """
        Property 13: Game outcome matches hand value comparison.
        
        For any completed game (via stand):
        - If player value > dealer value (neither busted): player wins
        - If dealer value > player value (neither busted): dealer wins
        - If equal (neither busted): push
        """
        import random as rand_module
        rng = rand_module.Random(seed)
        engine = BlackjackEngine(random_func=rng.random)
        
        game = engine.create_game(user_id=user_id, bet=bet)
        assume(game.status == GameStatus.PLAYING)
        
        game = engine.stand(game)
        
        player_value = game.player_hand.value
        dealer_value = game.dealer_hand.value
        player_busted = game.player_hand.is_busted
        dealer_busted = game.dealer_hand.is_busted
        
        # Check game status matches expected outcome
        if player_busted:
            assert game.status == GameStatus.PLAYER_BUSTED, \
                "Busted player should result in PLAYER_BUSTED"
        elif dealer_busted:
            assert game.status == GameStatus.DEALER_BUSTED, \
                "Busted dealer should result in DEALER_BUSTED"
        elif player_value > dealer_value:
            assert game.status == GameStatus.PLAYER_WIN, \
                f"Player {player_value} > Dealer {dealer_value} should be PLAYER_WIN"
        elif dealer_value > player_value:
            assert game.status == GameStatus.DEALER_WIN, \
                f"Dealer {dealer_value} > Player {player_value} should be DEALER_WIN"
        else:
            assert game.status == GameStatus.PUSH, \
                f"Equal values ({player_value}) should be PUSH"
    
    @settings(max_examples=100)
    @given(
        bet=bet_strategy,
        player_value=st.integers(min_value=2, max_value=21),
        dealer_value=st.integers(min_value=2, max_value=21)
    )
    def test_payout_matches_winner(self, bet: int, player_value: int, dealer_value: int):
        """
        Property 13 extended: Payout correctly reflects winner.
        
        - Player win: positive payout (bet amount)
        - Dealer win: negative payout (-bet amount)
        - Push: zero payout
        """
        engine = BlackjackEngine()
        
        # Create a mock game with specific values
        game = engine.create_game(user_id=1, bet=bet)
        
        # Manually set the game status based on values
        if player_value > dealer_value:
            game.status = GameStatus.PLAYER_WIN
            expected_payout = bet
        elif dealer_value > player_value:
            game.status = GameStatus.DEALER_WIN
            expected_payout = -bet
        else:
            game.status = GameStatus.PUSH
            expected_payout = 0
        
        payout = engine.calculate_payout(game)
        
        assert payout == expected_payout, \
            f"Payout should be {expected_payout}, got {payout}"

