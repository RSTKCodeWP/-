"""Mini Games Engine - All new games for v7.5.

Includes: Fishing, Crash, Dice, Guess Number, War, Wheel, Lootbox, Cockfight.
"""

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any, Callable

from app.utils import utc_now

logger = logging.getLogger(__name__)


class GameStatus(str, Enum):
    """Game status."""
    WAITING = "waiting"
    PLAYING = "playing"
    FINISHED = "finished"
    CANCELLED = "cancelled"


# ============================================================================
# FISHING GAME
# ============================================================================

class FishRarity(str, Enum):
    TRASH = "trash"
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"


@dataclass
class Fish:
    """Represents a caught fish."""
    name: str
    emoji: str
    rarity: FishRarity
    value: int  # Sell price
    weight: float  # kg


# Fish catalog with probabilities
FISH_CATALOG: Dict[FishRarity, List[Fish]] = {
    FishRarity.TRASH: [
        Fish("Старый ботинок", "👟", FishRarity.TRASH, 0, 0.5),  # No coins for trash
        Fish("Консервная банка", "🥫", FishRarity.TRASH, 0, 0.1),
        Fish("Водоросли", "🌿", FishRarity.TRASH, 0, 0.2),
    ],
    FishRarity.COMMON: [
        Fish("Карась", "🐟", FishRarity.COMMON, 10, 0.8),
        Fish("Окунь", "🐟", FishRarity.COMMON, 12, 1.0),
        Fish("Плотва", "🐟", FishRarity.COMMON, 8, 0.5),
        Fish("Ёрш", "🐟", FishRarity.COMMON, 7, 0.3),
    ],
    FishRarity.UNCOMMON: [
        Fish("Щука", "🐟", FishRarity.UNCOMMON, 25, 3.0),
        Fish("Судак", "🐟", FishRarity.UNCOMMON, 30, 2.5),
        Fish("Лещ", "🐟", FishRarity.UNCOMMON, 20, 2.0),
    ],
    FishRarity.RARE: [
        Fish("Сом", "🐋", FishRarity.RARE, 80, 15.0),
        Fish("Карп", "🐟", FishRarity.RARE, 60, 8.0),
        Fish("Форель", "🐟", FishRarity.RARE, 70, 3.0),
    ],
    FishRarity.EPIC: [
        Fish("Осётр", "🐋", FishRarity.EPIC, 200, 25.0),
        Fish("Белуга", "🐋", FishRarity.EPIC, 250, 40.0),
        Fish("Тунец", "🐟", FishRarity.EPIC, 180, 50.0),
    ],
    FishRarity.LEGENDARY: [
        Fish("Золотая рыбка", "✨", FishRarity.LEGENDARY, 1000, 0.5),
        Fish("Кракен", "🦑", FishRarity.LEGENDARY, 2000, 100.0),
        Fish("Левиафан", "🐉", FishRarity.LEGENDARY, 5000, 500.0),
    ],
}

# Rarity probabilities (base, can be modified by rod) - Rebalanced for fun (v9.6)
FISH_PROBABILITIES = {
    FishRarity.TRASH: 0.10,  # Decreased from 0.20
    FishRarity.COMMON: 0.45,  # Slightly decreased
    FishRarity.UNCOMMON: 0.25,  # Increased
    FishRarity.RARE: 0.12,  # Increased from 0.07
    FishRarity.EPIC: 0.06,  # Increased from 0.025
    FishRarity.LEGENDARY: 0.02,  # Increased from 0.005
}


@dataclass
class FishingResult:
    """Result of a fishing attempt."""
    success: bool
    message: str
    fish: Optional[Fish] = None
    coins_earned: int = 0
    error_code: Optional[str] = None


class FishingGame:
    """Fishing game logic."""
    
    COOLDOWN_SECONDS = 30  # Decreased from 90 to 30 for fun
    
    def __init__(self, random_func: Optional[Callable[[], float]] = None):
        self._random = random_func or random.random
        self._cooldowns: Dict[int, datetime] = {}
    
    def reset_cooldown(self, user_id: int) -> None:
        """Reset fishing cooldown for user (used by energy drink)."""
        if user_id in self._cooldowns:
            del self._cooldowns[user_id]
    
    def _select_rarity(self, rod_bonus: float = 0.0, fishing_bonus: float = 0.0) -> FishRarity:
        """Select fish rarity based on probabilities.
        
        Args:
            rod_bonus: Bonus from equipped rod
            fishing_bonus: Bonus from premium bait
        """
        roll = self._random()
        cumulative = 0.0
        
        # Combine bonuses
        total_bonus = rod_bonus + fishing_bonus
        
        # Adjust probabilities with combined bonus (increases rare+ chances)
        probs = FISH_PROBABILITIES.copy()
        if total_bonus > 0:
            bonus_pool = probs[FishRarity.TRASH] * total_bonus
            probs[FishRarity.TRASH] -= bonus_pool
            probs[FishRarity.RARE] += bonus_pool * 0.5
            probs[FishRarity.EPIC] += bonus_pool * 0.3
            probs[FishRarity.LEGENDARY] += bonus_pool * 0.2
        
        for rarity, prob in probs.items():
            cumulative += prob
            if roll < cumulative:
                return rarity
        return FishRarity.COMMON
    
    def cast(self, user_id: int, rod_bonus: float = 0.0, fishing_bonus: float = 0.0) -> FishingResult:
        """Cast the fishing rod.
        
        Args:
            user_id: User ID
            rod_bonus: Bonus from equipped rod
            fishing_bonus: Bonus from premium bait
        """
        # Check cooldown
        now = utc_now()
        if user_id in self._cooldowns:
            remaining = (self._cooldowns[user_id] - now).total_seconds()
            if remaining > 0:
                return FishingResult(
                    False, f"Подожди {int(remaining)} сек. перед следующим забросом",
                    error_code="COOLDOWN"
                )
        
        # Set cooldown
        self._cooldowns[user_id] = now + timedelta(seconds=self.COOLDOWN_SECONDS)
        
        # Select rarity and fish
        rarity = self._select_rarity(rod_bonus, fishing_bonus)
        fish_list = FISH_CATALOG[rarity]
        fish = random.choice(fish_list)
        
        # Generate message based on rarity
        if rarity == FishRarity.TRASH:
            msg = f"🎣 Вытащил {fish.emoji} {fish.name}... Ну, бывает."
        elif rarity == FishRarity.LEGENDARY:
            msg = f"🎣✨ ЛЕГЕНДАРНЫЙ УЛОВ! {fish.emoji} {fish.name}! (+{fish.value} монет)"
        elif rarity == FishRarity.EPIC:
            msg = f"🎣🔥 ЭПИК! {fish.emoji} {fish.name}! (+{fish.value} монет)"
        elif rarity == FishRarity.RARE:
            msg = f"🎣⭐ Редкая рыба! {fish.emoji} {fish.name} (+{fish.value} монет)"
        else:
            msg = f"🎣 Поймал {fish.emoji} {fish.name} ({fish.weight} кг) — +{fish.value} монет"
        
        return FishingResult(True, msg, fish, fish.value)


# ============================================================================
# CRASH GAME
# ============================================================================

@dataclass
class CrashGame:
    """Crash game state."""
    user_id: int
    bet: int
    multiplier: float = 1.0
    crash_point: float = 0.0
    status: GameStatus = GameStatus.PLAYING
    cashed_out: bool = False
    winnings: int = 0


@dataclass
class CrashResult:
    """Result of crash game action."""
    success: bool
    message: str
    multiplier: float = 1.0
    crashed: bool = False
    winnings: int = 0
    error_code: Optional[str] = None


class CrashEngine:
    """Crash game engine - multiplier grows until crash."""
    
    TICK_INTERVAL = 0.5  # seconds between multiplier updates
    MULTIPLIER_INCREMENT = 0.1
    HOUSE_EDGE = 0.05  # Increased from 3% to 5% for balance
    MAX_BET = 1000  # Maximum bet limit
    
    def __init__(self, random_func: Optional[Callable[[], float]] = None):
        self._random = random_func or random.random
        self._games: Dict[int, CrashGame] = {}
    
    def _generate_crash_point(self) -> float:
        """Generate crash point with house edge."""
        # Using inverse of uniform distribution for exponential-like crash
        r = self._random()
        if r < self.HOUSE_EDGE:
            return 1.0  # Instant crash
        # Crash point formula: higher values are rarer
        crash = 1.0 / (1.0 - r * (1 - self.HOUSE_EDGE))
        return round(min(crash, 100.0), 2)  # Cap at 100x
    
    def start_game(self, user_id: int, bet: int) -> CrashResult:
        """Start a new crash game."""
        if user_id in self._games and self._games[user_id].status == GameStatus.PLAYING:
            return CrashResult(False, "У тебя уже есть активная игра!", error_code="ALREADY_PLAYING")
        
        if bet <= 0:
            return CrashResult(False, "Ставка должна быть положительной", error_code="INVALID_BET")
        
        crash_point = self._generate_crash_point()
        game = CrashGame(user_id=user_id, bet=bet, crash_point=crash_point)
        self._games[user_id] = game
        
        logger.info(f"Crash game started: user={user_id}, bet={bet}, crash_point={crash_point}")
        return CrashResult(True, "🚀 Ракета взлетает! Успей забрать до краша!", multiplier=1.0)
    
    def tick(self, user_id: int) -> CrashResult:
        """Advance the game by one tick."""
        if user_id not in self._games:
            return CrashResult(False, "Игра не найдена", error_code="NO_GAME")
        
        game = self._games[user_id]
        if game.status != GameStatus.PLAYING:
            return CrashResult(False, "Игра уже завершена", error_code="GAME_OVER")
        
        # Increase multiplier
        game.multiplier = round(game.multiplier + self.MULTIPLIER_INCREMENT, 2)
        
        # Check for crash
        if game.multiplier >= game.crash_point:
            game.status = GameStatus.FINISHED
            return CrashResult(
                True, f"💥 КРАШ на x{game.crash_point}! Ты потерял {game.bet} монет.",
                multiplier=game.crash_point, crashed=True, winnings=-game.bet
            )
        
        return CrashResult(True, f"🚀 x{game.multiplier}", multiplier=game.multiplier)
    
    def cash_out(self, user_id: int) -> CrashResult:
        """Cash out at current multiplier."""
        if user_id not in self._games:
            return CrashResult(False, "Игра не найдена", error_code="NO_GAME")
        
        game = self._games[user_id]
        if game.status != GameStatus.PLAYING:
            return CrashResult(False, "Игра уже завершена", error_code="GAME_OVER")
        
        game.cashed_out = True
        game.status = GameStatus.FINISHED
        game.winnings = int(game.bet * game.multiplier)
        profit = game.winnings - game.bet
        
        return CrashResult(
            True, f"💰 Забрал на x{game.multiplier}! Выигрыш: +{profit} монет",
            multiplier=game.multiplier, winnings=profit
        )
    
    def get_game(self, user_id: int) -> Optional[CrashGame]:
        """Get current game state."""
        return self._games.get(user_id)
    
    def end_game(self, user_id: int) -> None:
        """Clean up game."""
        if user_id in self._games:
            del self._games[user_id]


# ============================================================================
# DICE DUEL GAME
# ============================================================================

@dataclass
class DiceResult:
    """Result of dice roll."""
    success: bool
    message: str
    player_roll: int = 0
    opponent_roll: int = 0
    won: bool = False
    winnings: int = 0
    error_code: Optional[str] = None


class DiceGame:
    """Dice duel game - roll against bot or player."""
    
    DICE_EMOJI = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
    
    def __init__(self, random_func: Optional[Callable[[], float]] = None):
        self._random = random_func or random.random
    
    def _roll(self) -> int:
        """Roll a single die (1-6)."""
        return int(self._random() * 6) + 1
    
    def _roll_dice(self, count: int = 2) -> List[int]:
        """Roll multiple dice."""
        return [self._roll() for _ in range(count)]
    
    def _format_roll(self, rolls: List[int]) -> str:
        """Format dice roll with emojis."""
        emojis = [self.DICE_EMOJI[r - 1] for r in rolls]
        return " ".join(emojis) + f" = {sum(rolls)}"
    
    def play_vs_bot(self, user_id: int, bet: int) -> DiceResult:
        """Play dice against the bot.
        
        Returns winnings as net change to balance:
        - Win: +bet (profit)
        - Lose: -bet (loss)
        - Draw: 0 (no change)
        
        Handler should deduct bet first, then apply winnings.
        """
        if bet <= 0:
            return DiceResult(False, "Ставка должна быть положительной", error_code="INVALID_BET")
        
        player_rolls = self._roll_dice(2)
        bot_rolls = self._roll_dice(2)
        player_total = sum(player_rolls)
        bot_total = sum(bot_rolls)
        
        player_str = self._format_roll(player_rolls)
        bot_str = self._format_roll(bot_rolls)
        
        if player_total > bot_total:
            # Win: get bet back + profit (total 2x bet)
            winnings = bet * 2  # Return bet + win bet
            msg = (f"🎲 Твой бросок: {player_str}\n"
                   f"🤖 Бот: {bot_str}\n\n"
                   f"🎉 Победа! +{bet} монет")
            return DiceResult(True, msg, player_total, bot_total, True, winnings)
        elif player_total < bot_total:
            # Lose: lose bet
            msg = (f"🎲 Твой бросок: {player_str}\n"
                   f"🤖 Бот: {bot_str}\n\n"
                   f"😢 Проигрыш. -{bet} монет")
            return DiceResult(True, msg, player_total, bot_total, False, 0)
        else:
            # Draw: get bet back
            msg = (f"🎲 Твой бросок: {player_str}\n"
                   f"🤖 Бот: {bot_str}\n\n"
                   f"🤝 Ничья! Ставка возвращена.")
            return DiceResult(True, msg, player_total, bot_total, False, bet)


# ============================================================================
# GUESS NUMBER GAME
# ============================================================================

@dataclass
class GuessGame:
    """Guess the number game state."""
    user_id: int
    target: int
    min_val: int
    max_val: int
    attempts: int = 0
    max_attempts: int = 7
    bet: int = 0
    status: GameStatus = GameStatus.PLAYING
    hints: List[str] = field(default_factory=list)


@dataclass
class GuessResult:
    """Result of a guess."""
    success: bool
    message: str
    correct: bool = False
    attempts_left: int = 0
    winnings: int = 0
    hint: str = ""
    error_code: Optional[str] = None


class GuessEngine:
    """Guess the number game engine."""
    
    def __init__(self, random_func: Optional[Callable[[], float]] = None):
        self._random = random_func or random.random
        self._games: Dict[int, GuessGame] = {}
    
    def start_game(self, user_id: int, bet: int, max_val: int = 100) -> GuessResult:
        """Start a new guess game."""
        if user_id in self._games and self._games[user_id].status == GameStatus.PLAYING:
            return GuessResult(False, "У тебя уже есть активная игра!", error_code="ALREADY_PLAYING")
        
        target = int(self._random() * max_val) + 1
        game = GuessGame(user_id=user_id, target=target, min_val=1, max_val=max_val, bet=bet)
        self._games[user_id] = game
        
        return GuessResult(
            True, f"🔮 Загадал число от 1 до {max_val}. У тебя {game.max_attempts} попыток!",
            attempts_left=game.max_attempts
        )
    
    def guess(self, user_id: int, number: int) -> GuessResult:
        """Make a guess."""
        if user_id not in self._games:
            return GuessResult(False, "Игра не найдена. Начни с /guess", error_code="NO_GAME")
        
        game = self._games[user_id]
        if game.status != GameStatus.PLAYING:
            return GuessResult(False, "Игра уже завершена", error_code="GAME_OVER")
        
        game.attempts += 1
        attempts_left = game.max_attempts - game.attempts
        
        if number == game.target:
            game.status = GameStatus.FINISHED
            # Reward based on attempts (fewer = more)
            multiplier = (game.max_attempts - game.attempts + 1) / game.max_attempts
            winnings = int(game.bet * (1 + multiplier * 2))
            return GuessResult(
                True, f"🎉 УГАДАЛ! Число было {game.target}. Попыток: {game.attempts}\n+{winnings} монет!",
                correct=True, attempts_left=0, winnings=winnings
            )
        
        if attempts_left <= 0:
            game.status = GameStatus.FINISHED
            return GuessResult(
                True, f"😢 Попытки кончились! Число было {game.target}. -{game.bet} монет",
                correct=False, attempts_left=0, winnings=-game.bet
            )
        
        # Give hint
        if number < game.target:
            hint = f"⬆️ Больше! (от {number + 1} до {game.max_val})"
            game.min_val = max(game.min_val, number + 1)
        else:
            hint = f"⬇️ Меньше! (от {game.min_val} до {number - 1})"
            game.max_val = min(game.max_val, number - 1)
        
        game.hints.append(hint)
        return GuessResult(True, hint, attempts_left=attempts_left, hint=hint)
    
    def get_game(self, user_id: int) -> Optional[GuessGame]:
        return self._games.get(user_id)
    
    def end_game(self, user_id: int) -> None:
        if user_id in self._games:
            del self._games[user_id]


# ============================================================================
# WAR CARD GAME
# ============================================================================

@dataclass
class Card:
    """Playing card."""
    suit: str
    rank: str
    value: int
    
    def __str__(self) -> str:
        suits = {"hearts": "♥️", "diamonds": "♦️", "clubs": "♣️", "spades": "♠️"}
        return f"{self.rank}{suits.get(self.suit, self.suit)}"


@dataclass
class WarResult:
    """Result of war card game."""
    success: bool
    message: str
    player_card: Optional[Card] = None
    opponent_card: Optional[Card] = None
    won: bool = False
    is_war: bool = False
    winnings: int = 0
    error_code: Optional[str] = None


class WarGame:
    """War card game - simple high card wins."""
    
    SUITS = ["hearts", "diamonds", "clubs", "spades"]
    RANKS = [("2", 2), ("3", 3), ("4", 4), ("5", 5), ("6", 6), ("7", 7), ("8", 8),
             ("9", 9), ("10", 10), ("J", 11), ("Q", 12), ("K", 13), ("A", 14)]
    
    def __init__(self, random_func: Optional[Callable[[], float]] = None):
        self._random = random_func or random.random
    
    def _draw_card(self) -> Card:
        """Draw a random card."""
        suit = self.SUITS[int(self._random() * 4)]
        rank, value = self.RANKS[int(self._random() * 13)]
        return Card(suit, rank, value)
    
    def play(self, user_id: int, bet: int) -> WarResult:
        """Play a round of war.
        
        Returns winnings to add after bet is deducted:
        - Win: bet * 2 (get bet back + profit)
        - Lose: 0 (bet already lost)
        - Draw: bet (get bet back)
        """
        if bet <= 0:
            return WarResult(False, "Ставка должна быть положительной", error_code="INVALID_BET")
        
        player_card = self._draw_card()
        bot_card = self._draw_card()
        
        if player_card.value > bot_card.value:
            winnings = bet * 2  # Return bet + win bet
            msg = (f"🃏 Твоя карта: {player_card}\n"
                   f"🤖 Карта бота: {bot_card}\n\n"
                   f"🎉 Победа! +{bet} монет")
            return WarResult(True, msg, player_card, bot_card, True, False, winnings)
        elif player_card.value < bot_card.value:
            msg = (f"🃏 Твоя карта: {player_card}\n"
                   f"🤖 Карта бота: {bot_card}\n\n"
                   f"😢 Проигрыш. -{bet} монет")
            return WarResult(True, msg, player_card, bot_card, False, False, 0)
        else:
            # War! Draw - return bet
            msg = (f"🃏 Твоя карта: {player_card}\n"
                   f"🤖 Карта бота: {bot_card}\n\n"
                   f"⚔️ ВОЙНА! Ничья — ставка возвращена.")
            return WarResult(True, msg, player_card, bot_card, False, True, bet)


# ============================================================================
# WHEEL OF FORTUNE
# ============================================================================

@dataclass
class WheelSegment:
    """Segment on the wheel."""
    emoji: str
    name: str
    multiplier: float  # 0 = lose, 1 = return bet, 2 = double, etc.
    probability: float


WHEEL_SEGMENTS = [
    WheelSegment("💀", "Банкрот", 0.0, 0.10),
    WheelSegment("😢", "Минус половина", 0.5, 0.15),
    WheelSegment("🔄", "Возврат", 1.0, 0.25),
    WheelSegment("💰", "x1.5", 1.5, 0.20),
    WheelSegment("💎", "x2", 2.0, 0.15),
    WheelSegment("🔥", "x3", 3.0, 0.10),
    WheelSegment("🌟", "x5", 5.0, 0.04),
    WheelSegment("👑", "ДЖЕКПОТ x10", 10.0, 0.01),
]


@dataclass
class WheelResult:
    """Result of wheel spin."""
    success: bool
    message: str
    segment: Optional[WheelSegment] = None
    winnings: int = 0
    error_code: Optional[str] = None


class WheelGame:
    """Wheel of Fortune game."""
    
    def __init__(self, random_func: Optional[Callable[[], float]] = None):
        self._random = random_func or random.random
    
    def spin(self, user_id: int, bet: int) -> WheelResult:
        """Spin the wheel.
        
        Returns winnings to add after bet is deducted:
        - Multiplier applied to bet, then returned
        - x0 (bankrupt): 0 (lose all)
        - x0.5: bet/2 (lose half)
        - x1: bet (break even)
        - x2+: bet * multiplier (profit)
        """
        if bet <= 0:
            return WheelResult(False, "Ставка должна быть положительной", error_code="INVALID_BET")
        
        roll = self._random()
        cumulative = 0.0
        selected = WHEEL_SEGMENTS[-1]
        
        for segment in WHEEL_SEGMENTS:
            cumulative += segment.probability
            if roll < cumulative:
                selected = segment
                break
        
        # Winnings = what to add back after bet deducted
        winnings = int(bet * selected.multiplier)
        profit = winnings - bet
        
        if selected.multiplier == 0:
            msg = f"🎡 Колесо крутится...\n\n{selected.emoji} {selected.name}!\n\n💀 Потерял всё: -{bet} монет"
        elif selected.multiplier < 1:
            loss = bet - winnings
            msg = f"🎡 Колесо крутится...\n\n{selected.emoji} {selected.name}!\n\n😢 -{loss} монет"
        elif selected.multiplier == 1:
            msg = f"🎡 Колесо крутится...\n\n{selected.emoji} {selected.name}!\n\n🔄 Ставка возвращена"
        elif selected.multiplier >= 10:
            msg = f"🎡 Колесо крутится...\n\n{selected.emoji} {selected.name}!\n\n🎉🎉🎉 ДЖЕКПОТ! +{profit} монет!"
        else:
            msg = f"🎡 Колесо крутится...\n\n{selected.emoji} {selected.name}!\n\n💰 +{profit} монет"
        
        return WheelResult(True, msg, selected, winnings)


# ============================================================================
# LOOTBOX SYSTEM
# ============================================================================

class LootboxRarity(str, Enum):
    COMMON = "common"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"


@dataclass
class LootboxReward:
    """Reward from lootbox."""
    name: str
    emoji: str
    rarity: LootboxRarity
    coins: int = 0
    item_type: Optional[str] = None


# Lootbox contents by type - expanded with new tiers
LOOTBOX_CONTENTS: Dict[str, Dict[LootboxRarity, List[LootboxReward]]] = {
    "common": {
        LootboxRarity.COMMON: [
            LootboxReward("Горсть монет", "🪙", LootboxRarity.COMMON, coins=20),
            LootboxReward("Мелочь", "💵", LootboxRarity.COMMON, coins=30),
            LootboxReward("Немного монет", "💰", LootboxRarity.COMMON, coins=50),
        ],
        LootboxRarity.RARE: [
            LootboxReward("Кошелёк", "👛", LootboxRarity.RARE, coins=100),
            LootboxReward("Талисман удачи", "🍀", LootboxRarity.RARE, item_type="lucky_charm"),
        ],
        LootboxRarity.EPIC: [
            LootboxReward("Сундук монет", "📦", LootboxRarity.EPIC, coins=250),
        ],
        LootboxRarity.LEGENDARY: [
            LootboxReward("Джекпот!", "💎", LootboxRarity.LEGENDARY, coins=500),
        ],
    },
    "rare": {
        LootboxRarity.COMMON: [
            LootboxReward("Монеты", "💰", LootboxRarity.COMMON, coins=75),
        ],
        LootboxRarity.RARE: [
            LootboxReward("Хороший куш", "💵", LootboxRarity.RARE, coins=150),
            LootboxReward("Энергетик", "🥤", LootboxRarity.RARE, item_type="energy_drink"),
        ],
        LootboxRarity.EPIC: [
            LootboxReward("Большой куш", "💎", LootboxRarity.EPIC, coins=400),
            LootboxReward("Щит", "🛡️", LootboxRarity.EPIC, item_type="shield"),
        ],
        LootboxRarity.LEGENDARY: [
            LootboxReward("Мега джекпот!", "👑", LootboxRarity.LEGENDARY, coins=1000),
        ],
    },
    "epic": {
        LootboxRarity.COMMON: [
            LootboxReward("Монеты", "💰", LootboxRarity.COMMON, coins=150),
        ],
        LootboxRarity.RARE: [
            LootboxReward("Солидный куш", "💵", LootboxRarity.RARE, coins=300),
        ],
        LootboxRarity.EPIC: [
            LootboxReward("Эпик награда", "💎", LootboxRarity.EPIC, coins=600),
            LootboxReward("VIP статус", "👑", LootboxRarity.EPIC, item_type="vip_status"),
        ],
        LootboxRarity.LEGENDARY: [
            LootboxReward("Легендарный куш!", "🌟", LootboxRarity.LEGENDARY, coins=2000),
        ],
    },
    "legendary": {
        LootboxRarity.COMMON: [
            LootboxReward("Монеты", "💰", LootboxRarity.COMMON, coins=300),
        ],
        LootboxRarity.RARE: [
            LootboxReward("Большие монеты", "💵", LootboxRarity.RARE, coins=500),
        ],
        LootboxRarity.EPIC: [
            LootboxReward("Эпик сокровище", "💎", LootboxRarity.EPIC, coins=1000),
        ],
        LootboxRarity.LEGENDARY: [
            LootboxReward("МЕГА ДЖЕКПОТ!", "👑", LootboxRarity.LEGENDARY, coins=5000),
            LootboxReward("Золотая удочка", "🎣", LootboxRarity.LEGENDARY, item_type="fishing_rod_golden"),
        ],
    },
    "mega": {
        LootboxRarity.COMMON: [
            LootboxReward("Куча монет", "💰", LootboxRarity.COMMON, coins=500),
        ],
        LootboxRarity.RARE: [
            LootboxReward("Огромный куш", "💵", LootboxRarity.RARE, coins=1000),
        ],
        LootboxRarity.EPIC: [
            LootboxReward("Эпическое богатство", "💎", LootboxRarity.EPIC, coins=2500),
            LootboxReward("Редкий петух", "🐓", LootboxRarity.EPIC, item_type="rooster_rare"),
        ],
        LootboxRarity.LEGENDARY: [
            LootboxReward("КОСМИЧЕСКИЙ ДЖЕКПОТ!", "🌌", LootboxRarity.LEGENDARY, coins=10000),
            LootboxReward("Алмазная удочка", "💎", LootboxRarity.LEGENDARY, item_type="diamond_rod"),
            LootboxReward("Эпический петух", "🦃", LootboxRarity.LEGENDARY, item_type="rooster_epic"),
        ],
    },
    "mystery": {
        LootboxRarity.COMMON: [
            LootboxReward("Пустота", "❓", LootboxRarity.COMMON, coins=0),
            LootboxReward("Немного монет", "💰", LootboxRarity.COMMON, coins=50),
        ],
        LootboxRarity.RARE: [
            LootboxReward("Сюрприз!", "🎁", LootboxRarity.RARE, coins=200),
            LootboxReward("Случайный бустер", "⚡", LootboxRarity.RARE, item_type="energy_drink"),
        ],
        LootboxRarity.EPIC: [
            LootboxReward("Большой сюрприз!", "🎉", LootboxRarity.EPIC, coins=800),
            LootboxReward("Талисман удачи", "🍀", LootboxRarity.EPIC, item_type="lucky_charm"),
        ],
        LootboxRarity.LEGENDARY: [
            LootboxReward("НЕВЕРОЯТНАЯ УДАЧА!", "✨", LootboxRarity.LEGENDARY, coins=3000),
            LootboxReward("Космическая удочка", "🌌", LootboxRarity.LEGENDARY, item_type="cosmic_rod"),
        ],
    },
}

# Probabilities by lootbox type - expanded
LOOTBOX_PROBABILITIES: Dict[str, Dict[LootboxRarity, float]] = {
    "common": {LootboxRarity.COMMON: 0.70, LootboxRarity.RARE: 0.20, LootboxRarity.EPIC: 0.08, LootboxRarity.LEGENDARY: 0.02},
    "rare": {LootboxRarity.COMMON: 0.50, LootboxRarity.RARE: 0.30, LootboxRarity.EPIC: 0.15, LootboxRarity.LEGENDARY: 0.05},
    "epic": {LootboxRarity.COMMON: 0.30, LootboxRarity.RARE: 0.35, LootboxRarity.EPIC: 0.25, LootboxRarity.LEGENDARY: 0.10},
    "legendary": {LootboxRarity.COMMON: 0.15, LootboxRarity.RARE: 0.30, LootboxRarity.EPIC: 0.35, LootboxRarity.LEGENDARY: 0.20},
    "mega": {LootboxRarity.COMMON: 0.05, LootboxRarity.RARE: 0.20, LootboxRarity.EPIC: 0.40, LootboxRarity.LEGENDARY: 0.35},
    "mystery": {LootboxRarity.COMMON: 0.40, LootboxRarity.RARE: 0.30, LootboxRarity.EPIC: 0.20, LootboxRarity.LEGENDARY: 0.10},
}


@dataclass
class LootboxResult:
    """Result of opening a lootbox."""
    success: bool
    message: str
    rewards: List[LootboxReward] = field(default_factory=list)
    total_coins: int = 0
    items: List[str] = field(default_factory=list)
    error_code: Optional[str] = None


class LootboxEngine:
    """Lootbox opening engine."""
    
    def __init__(self, random_func: Optional[Callable[[], float]] = None):
        self._random = random_func or random.random
    
    def open(self, lootbox_type: str = "common") -> LootboxResult:
        """Open a lootbox."""
        if lootbox_type not in LOOTBOX_CONTENTS:
            return LootboxResult(False, "Неизвестный тип лутбокса", error_code="INVALID_TYPE")
        
        contents = LOOTBOX_CONTENTS[lootbox_type]
        probs = LOOTBOX_PROBABILITIES[lootbox_type]
        
        # Select rarity
        roll = self._random()
        cumulative = 0.0
        selected_rarity = LootboxRarity.COMMON
        
        for rarity, prob in probs.items():
            cumulative += prob
            if roll < cumulative:
                selected_rarity = rarity
                break
        
        # Select reward
        rewards_list = contents.get(selected_rarity, contents[LootboxRarity.COMMON])
        reward = random.choice(rewards_list)
        
        total_coins = reward.coins
        items = [reward.item_type] if reward.item_type else []
        
        # Build message
        rarity_names = {
            LootboxRarity.COMMON: "Обычный",
            LootboxRarity.RARE: "⭐ Редкий",
            LootboxRarity.EPIC: "💜 Эпический",
            LootboxRarity.LEGENDARY: "🌟 ЛЕГЕНДАРНЫЙ",
        }
        
        msg = f"📦 Открываем лутбокс...\n\n"
        msg += f"{rarity_names[selected_rarity]} дроп!\n"
        msg += f"{reward.emoji} {reward.name}\n"
        
        if reward.coins:
            msg += f"\n💰 +{reward.coins} монет"
        if reward.item_type:
            msg += f"\n🎁 Получен предмет!"
        
        return LootboxResult(True, msg, [reward], total_coins, items)


# ============================================================================
# COCKFIGHT GAME
# ============================================================================

class RoosterTier(str, Enum):
    COMMON = "common"
    RARE = "rare"
    EPIC = "epic"


@dataclass
class Rooster:
    """A fighting rooster."""
    name: str
    emoji: str
    tier: RoosterTier
    base_power: int
    special_move: str
    
    def get_power(self) -> int:
        """Get power with random variance."""
        variance = random.randint(-10, 10)
        return max(1, self.base_power + variance)


# Rooster catalog - expanded with more variety
ROOSTERS: Dict[RoosterTier, List[Rooster]] = {
    RoosterTier.COMMON: [
        Rooster("Петька", "🐔", RoosterTier.COMMON, 50, "Клевок"),
        Rooster("Кукарек", "🐔", RoosterTier.COMMON, 45, "Крыло"),
        Rooster("Рыжик", "🐔", RoosterTier.COMMON, 55, "Шпора"),
        Rooster("Цыпа", "🐔", RoosterTier.COMMON, 48, "Быстрый удар"),
        Rooster("Пёстрый", "🐔", RoosterTier.COMMON, 52, "Двойной клюв"),
        Rooster("Боря", "🐔", RoosterTier.COMMON, 47, "Прыжок"),
    ],
    RoosterTier.RARE: [
        Rooster("Громобой", "🐓", RoosterTier.RARE, 70, "Удар грома"),
        Rooster("Огненный", "🐓", RoosterTier.RARE, 75, "Огненный клюв"),
        Rooster("Стальной", "🐓", RoosterTier.RARE, 80, "Стальные когти"),
        Rooster("Вихрь", "🐓", RoosterTier.RARE, 72, "Ураганный удар"),
        Rooster("Молния", "🐓", RoosterTier.RARE, 78, "Электрошок"),
        Rooster("Титан", "🐓", RoosterTier.RARE, 76, "Сокрушающий удар"),
    ],
    RoosterTier.EPIC: [
        Rooster("Феникс", "🦃", RoosterTier.EPIC, 100, "Возрождение"),
        Rooster("Дракон", "🦃", RoosterTier.EPIC, 110, "Драконий рёв"),
        Rooster("Легенда", "🦃", RoosterTier.EPIC, 95, "Легендарный удар"),
        Rooster("Кракен", "🦃", RoosterTier.EPIC, 105, "Щупальца хаоса"),
        Rooster("Годзилла", "🦃", RoosterTier.EPIC, 115, "Атомное дыхание"),
        Rooster("Валькирия", "🦃", RoosterTier.EPIC, 98, "Небесный меч"),
    ],
}


@dataclass
class CockfightResult:
    """Result of a cockfight."""
    success: bool
    message: str
    player_rooster: Optional[Rooster] = None
    opponent_rooster: Optional[Rooster] = None
    player_power: int = 0
    opponent_power: int = 0
    won: bool = False
    winnings: int = 0
    error_code: Optional[str] = None


class CockfightGame:
    """Cockfight betting game."""
    
    def __init__(self, random_func: Optional[Callable[[], float]] = None):
        self._random = random_func or random.random
    
    def _select_opponent_rooster(self, player_tier: RoosterTier) -> Rooster:
        """Select opponent rooster (same or adjacent tier)."""
        tiers = list(RoosterTier)
        player_idx = tiers.index(player_tier)
        
        # 60% same tier, 40% adjacent
        if self._random() < 0.6 or player_idx == 0:
            tier = player_tier
        else:
            tier = tiers[max(0, player_idx - 1)]
        
        return random.choice(ROOSTERS[tier])
    
    def fight(self, user_id: int, bet: int, rooster_tier: RoosterTier = RoosterTier.COMMON, luck_bonus: float = 0.0, damage_bonus: float = 0.0, crit_bonus: float = 0.0) -> CockfightResult:
        """Start a cockfight with dynamic events.
        
        Args:
            user_id: User ID
            bet: Bet amount
            rooster_tier: Rooster tier
            luck_bonus: Luck bonus from lucky charm (affects close fights)
            damage_bonus: Damage bonus from steroids (increases base power)
            crit_bonus: Critical hit chance bonus from adrenaline
        """
        if bet <= 0:
            return CockfightResult(False, "Ставка должна быть положительной", error_code="INVALID_BET")
        
        # Select roosters
        player_rooster = random.choice(ROOSTERS[rooster_tier])
        opponent_rooster = self._select_opponent_rooster(rooster_tier)
        
        # Calculate base power with damage bonus
        player_power = player_rooster.get_power()
        if damage_bonus > 0:
            player_power = int(player_power * (1 + damage_bonus))
        opponent_power = opponent_rooster.get_power()
        
        # Build fight narrative with events
        msg = f"🐔 <b>ПЕТУШИНЫЕ БОИ</b> 🐔\n\n"
        msg += f"Твой боец: {player_rooster.emoji} {player_rooster.name}\n"
        msg += f"Противник: {opponent_rooster.emoji} {opponent_rooster.name}\n\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"⚔️ БОЙ!\n\n"
        
        events = []
        
        # Player attack with events
        player_crit = self._random() < (0.15 + luck_bonus + crit_bonus)  # 15% base + luck + crit bonus
        player_miss = self._random() < 0.10  # 10% miss chance
        
        if player_miss:
            events.append(f"💨 {player_rooster.name} промахнулся!")
            player_power = int(player_power * 0.5)
        elif player_crit:
            events.append(f"💥 КРИТИЧЕСКИЙ УДАР! {player_rooster.name} использует {player_rooster.special_move}!")
            player_power = int(player_power * 1.5)
        else:
            events.append(f"{player_rooster.name} использует {player_rooster.special_move}!")
        
        events.append(f"💪 Урон: {player_power}")
        
        # Opponent attack with events
        opponent_crit = self._random() < 0.15
        opponent_miss = self._random() < 0.10
        opponent_counter = self._random() < 0.12  # 12% counter chance
        
        if opponent_miss:
            events.append(f"\n💨 {opponent_rooster.name} промахнулся!")
            opponent_power = int(opponent_power * 0.5)
        elif opponent_counter:
            events.append(f"\n🛡️ КОНТРАТАКА! {opponent_rooster.name} блокирует и наносит {opponent_rooster.special_move}!")
            opponent_power = int(opponent_power * 1.3)
        elif opponent_crit:
            events.append(f"\n💥 КРИТИЧЕСКИЙ УДАР! {opponent_rooster.name} использует {opponent_rooster.special_move}!")
            opponent_power = int(opponent_power * 1.5)
        else:
            events.append(f"\n{opponent_rooster.name} отвечает {opponent_rooster.special_move}!")
        
        events.append(f"💪 Урон: {opponent_power}")
        
        msg += "\n".join(events) + "\n\n"
        
        # Determine winner with luck bonus affecting close fights
        power_diff = abs(player_power - opponent_power)
        booster_msgs = []
        if power_diff <= 5 and luck_bonus > 0:
            # Close fight - luck bonus tips the scale
            player_power += int(player_power * luck_bonus)
            booster_msgs.append(f"🍀 Удача на твоей стороне! (+{int(luck_bonus * 100)}%)")
        if damage_bonus > 0:
            booster_msgs.append(f"💪 Стероиды активны! (+{int(damage_bonus * 100)}% урона)")
        if crit_bonus > 0:
            booster_msgs.append(f"⚡ Адреналин активен! (+{int(crit_bonus * 100)}% крита)")
        
        if booster_msgs:
            msg += "\n".join(booster_msgs) + "\n\n"
        
        if player_power > opponent_power:
            # Reduced multipliers: x1.3 -> x1.2, x1.6 -> x1.4, x2.0 -> x1.7
            multiplier = 1.2 if rooster_tier == RoosterTier.COMMON else 1.4 if rooster_tier == RoosterTier.RARE else 1.7
            winnings = int(bet * multiplier)
            msg += f"🎉 <b>ПОБЕДА!</b> {player_rooster.name} побеждает!\n+{winnings} монет"
            return CockfightResult(True, msg, player_rooster, opponent_rooster, player_power, opponent_power, True, winnings)
        elif player_power < opponent_power:
            msg += f"😢 <b>ПОРАЖЕНИЕ!</b> {opponent_rooster.name} оказался сильнее.\n-{bet} монет"
            return CockfightResult(True, msg, player_rooster, opponent_rooster, player_power, opponent_power, False, -bet)
        else:
            msg += f"🤝 <b>НИЧЬЯ!</b> Оба петуха устали. Ставка возвращена."
            return CockfightResult(True, msg, player_rooster, opponent_rooster, player_power, opponent_power, False, 0)


# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

fishing_game = FishingGame()
crash_engine = CrashEngine()
dice_game = DiceGame()
guess_engine = GuessEngine()
war_game = WarGame()
wheel_game = WheelGame()
lootbox_engine = LootboxEngine()
cockfight_game = CockfightGame()
