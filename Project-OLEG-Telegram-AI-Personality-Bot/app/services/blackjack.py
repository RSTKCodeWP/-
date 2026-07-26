"""
Blackjack game engine.

Implements the Blackjack card game with standard casino rules.
Requirements: 9.1, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Callable
import random


class GameStatus(Enum):
    """Status of a Blackjack game."""
    PLAYING = "playing"
    PLAYER_BUSTED = "player_busted"
    DEALER_BUSTED = "dealer_busted"
    PLAYER_WIN = "player_win"
    DEALER_WIN = "dealer_win"
    PUSH = "push"
    PLAYER_BLACKJACK = "player_blackjack"


SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]


@dataclass
class Card:
    """A playing card with suit and rank."""
    suit: str  # ♠♥♦♣
    rank: str  # 2-10, J, Q, K, A
    
    @property
    def value(self) -> int:
        """
        Get the value of the card.
        
        Face cards (J, Q, K) = 10
        Number cards = face value
        Ace = 11 (soft value, adjusted in Hand.value)
        """
        if self.rank in ("J", "Q", "K"):
            return 10
        elif self.rank == "A":
            return 11
        else:
            return int(self.rank)
    
    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"
    
    def __repr__(self) -> str:
        return f"Card('{self.suit}', '{self.rank}')"


@dataclass
class Hand:
    """A hand of cards in Blackjack."""
    cards: List[Card] = field(default_factory=list)
    
    @property
    def value(self) -> int:
        """
        Calculate the total value of the hand.
        
        Aces are counted as 11 unless that would bust the hand,
        in which case they count as 1.
        """
        total = sum(card.value for card in self.cards)
        aces = sum(1 for card in self.cards if card.rank == "A")
        
        # Convert aces from 11 to 1 as needed to avoid busting
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1
        
        return total
    
    @property
    def is_soft(self) -> bool:
        """
        Check if the hand is soft (has an ace counted as 11).
        
        A hand is soft if it contains an ace that can be counted as 11
        without busting.
        """
        total = sum(card.value for card in self.cards)
        aces = sum(1 for card in self.cards if card.rank == "A")
        
        # Count how many aces need to be converted to 1
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1
        
        # If there are still aces counted as 11, the hand is soft
        return aces > 0
    
    @property
    def is_blackjack(self) -> bool:
        """
        Check if the hand is a natural Blackjack.
        
        A Blackjack is exactly 21 with the first two cards.
        """
        return len(self.cards) == 2 and self.value == 21
    
    @property
    def is_busted(self) -> bool:
        """Check if the hand has busted (value > 21)."""
        return self.value > 21
    
    def add_card(self, card: Card) -> None:
        """Add a card to the hand."""
        self.cards.append(card)
    
    def __str__(self) -> str:
        cards_str = " ".join(str(card) for card in self.cards)
        return f"{cards_str} ({self.value})"



@dataclass
class BlackjackGame:
    """State of a Blackjack game."""
    player_hand: Hand
    dealer_hand: Hand
    bet: int
    status: GameStatus = GameStatus.PLAYING
    deck: List[Card] = field(default_factory=list)
    
    def __post_init__(self):
        """Ensure hands are Hand objects."""
        if not isinstance(self.player_hand, Hand):
            self.player_hand = Hand(self.player_hand)
        if not isinstance(self.dealer_hand, Hand):
            self.dealer_hand = Hand(self.dealer_hand)


class BlackjackEngine:
    """
    Engine for playing Blackjack.
    
    Implements standard casino Blackjack rules:
    - Dealer stands on 17
    - Blackjack pays 1.5x
    - Double down allowed on any two cards
    """
    
    DEALER_STAND_VALUE = 17
    BLACKJACK_PAYOUT_MULTIPLIER = 1.5
    
    def __init__(self, random_func: Optional[Callable[[], float]] = None):
        """
        Initialize the Blackjack engine.
        
        Args:
            random_func: Optional random function for testing determinism.
        """
        self._random = random_func or random.random
    
    def _create_deck(self) -> List[Card]:
        """Create a standard 52-card deck."""
        return [Card(suit, rank) for suit in SUITS for rank in RANKS]
    
    def _shuffle_deck(self, deck: List[Card]) -> List[Card]:
        """Shuffle the deck using Fisher-Yates algorithm."""
        deck = deck.copy()
        n = len(deck)
        for i in range(n - 1, 0, -1):
            j = int(self._random() * (i + 1))
            deck[i], deck[j] = deck[j], deck[i]
        return deck
    
    def _deal_card(self, game: BlackjackGame) -> Card:
        """Deal a card from the deck."""
        return game.deck.pop()
    
    def create_game(self, user_id: int, bet: int) -> BlackjackGame:
        """
        Create a new Blackjack game and deal initial cards.
        
        Deals 2 cards to player and 2 to dealer.
        
        Args:
            user_id: The user's ID (for tracking).
            bet: The bet amount.
            
        Returns:
            A new BlackjackGame with initial cards dealt.
        """
        deck = self._shuffle_deck(self._create_deck())
        
        player_hand = Hand()
        dealer_hand = Hand()
        
        game = BlackjackGame(
            player_hand=player_hand,
            dealer_hand=dealer_hand,
            bet=bet,
            deck=deck
        )
        
        # Deal cards: player, dealer, player, dealer
        player_hand.add_card(self._deal_card(game))
        dealer_hand.add_card(self._deal_card(game))
        player_hand.add_card(self._deal_card(game))
        dealer_hand.add_card(self._deal_card(game))
        
        # Check for player blackjack
        if player_hand.is_blackjack:
            if dealer_hand.is_blackjack:
                game.status = GameStatus.PUSH
            else:
                game.status = GameStatus.PLAYER_BLACKJACK
        elif dealer_hand.is_blackjack:
            game.status = GameStatus.DEALER_WIN
        
        return game
    
    def hit(self, game: BlackjackGame) -> BlackjackGame:
        """
        Deal one additional card to the player.
        
        Args:
            game: The current game state.
            
        Returns:
            Updated game state.
        """
        if game.status != GameStatus.PLAYING:
            return game
        
        game.player_hand.add_card(self._deal_card(game))
        
        if game.player_hand.is_busted:
            game.status = GameStatus.PLAYER_BUSTED
        
        return game
    
    def stand(self, game: BlackjackGame) -> BlackjackGame:
        """
        Player stands, dealer plays their hand.
        
        Dealer draws until reaching 17 or higher.
        
        Args:
            game: The current game state.
            
        Returns:
            Updated game state with final result.
        """
        if game.status != GameStatus.PLAYING:
            return game
        
        # Dealer draws until 17 or higher
        while game.dealer_hand.value < self.DEALER_STAND_VALUE:
            game.dealer_hand.add_card(self._deal_card(game))
        
        # Determine winner
        if game.dealer_hand.is_busted:
            game.status = GameStatus.DEALER_BUSTED
        elif game.dealer_hand.value > game.player_hand.value:
            game.status = GameStatus.DEALER_WIN
        elif game.player_hand.value > game.dealer_hand.value:
            game.status = GameStatus.PLAYER_WIN
        else:
            game.status = GameStatus.PUSH
        
        return game
    
    def double(self, game: BlackjackGame) -> BlackjackGame:
        """
        Double down: double the bet, take one card, then stand.
        
        Args:
            game: The current game state.
            
        Returns:
            Updated game state.
        """
        if game.status != GameStatus.PLAYING:
            return game
        
        # Double the bet
        game.bet *= 2
        
        # Deal one card
        game.player_hand.add_card(self._deal_card(game))
        
        # Check for bust
        if game.player_hand.is_busted:
            game.status = GameStatus.PLAYER_BUSTED
            return game
        
        # Automatically stand
        return self.stand(game)
    
    def calculate_payout(self, game: BlackjackGame) -> int:
        """
        Calculate the payout for a completed game.
        
        Returns:
            Positive value for player win, negative for loss, 0 for push.
        """
        if game.status == GameStatus.PLAYER_BLACKJACK:
            # Blackjack pays 1.5x
            return int(game.bet * self.BLACKJACK_PAYOUT_MULTIPLIER)
        elif game.status in (GameStatus.PLAYER_WIN, GameStatus.DEALER_BUSTED):
            return game.bet
        elif game.status in (GameStatus.DEALER_WIN, GameStatus.PLAYER_BUSTED):
            return -game.bet
        else:  # PUSH
            return 0
    
    def determine_winner(self, player_value: int, dealer_value: int) -> str:
        """
        Determine the winner based on hand values.
        
        Assumes neither hand is busted.
        
        Args:
            player_value: Player's hand value.
            dealer_value: Dealer's hand value.
            
        Returns:
            "player", "dealer", or "push"
        """
        if player_value > dealer_value:
            return "player"
        elif dealer_value > player_value:
            return "dealer"
        else:
            return "push"
