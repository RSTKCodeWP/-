"""
Game Engine for PvP games with consent.

Implements challenge system with expiration, balance management,
and game mechanics for Russian Roulette and Coin Flip.

Requirements: 8.1, 8.2, 8.3, 8.4, 9.1-9.4, 10.1-10.5
"""

import logging
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, List, Callable


def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)

logger = logging.getLogger(__name__)


class ChallengeStatus(str, Enum):
    """Status of a game challenge."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    DECLINED = "declined"


class GameType(str, Enum):
    """Types of games available."""
    PVP = "pvp"
    ROULETTE = "roulette"
    COINFLIP = "coinflip"


@dataclass
class Challenge:
    """Represents a game challenge between two users."""
    id: str
    chat_id: int
    challenger_id: int
    target_id: int
    game_type: str
    bet_amount: int
    status: str
    created_at: datetime
    expires_at: datetime


@dataclass
class UserBalanceData:
    """User balance information."""
    user_id: int
    chat_id: int
    balance: int
    total_won: int
    total_lost: int


@dataclass
class ChallengeResult:
    """Result of a challenge operation."""
    success: bool
    message: str
    challenge: Optional[Challenge] = None
    error_code: Optional[str] = None


@dataclass
class GameResult:
    """Result of a game."""
    success: bool
    message: str
    winner_id: Optional[int] = None
    loser_id: Optional[int] = None
    amount_transferred: int = 0


@dataclass
class RouletteResult:
    """Result of a Russian Roulette game."""
    success: bool
    message: str
    shot: bool  # True if the player got "shot"
    points_change: int  # Positive for survival, negative for shot
    new_balance: int
    bet_amount: int = 0  # Amount bet (0 for standard mode)
    error_code: Optional[str] = None


@dataclass
class CoinFlipResult:
    """Result of a Coin Flip game."""
    success: bool
    message: str
    choice: str  # User's choice: "heads" or "tails"
    result: str  # Actual result: "heads" or "tails"
    won: bool  # True if user won
    bet_amount: int  # Amount bet
    balance_change: int  # Positive for win, negative for loss
    new_balance: int
    error_code: Optional[str] = None


class GameEngine:
    """
    Engine for PvP games with consent system.
    
    Manages challenges, balances, and game mechanics.
    
    Requirements:
    - 8.1: Challenge with Accept button
    - 8.2: Start game and deduct resources on accept
    - 8.3: Cancel without deduction on timeout
    - 8.4: Prevent multiple pending challenges
    - 9.1-9.4: Russian Roulette game
    - 10.1-10.5: Coin Flip game
    """
    
    # Default challenge timeout in minutes
    DEFAULT_TIMEOUT_MINUTES: int = 5
    
    # Default starting balance for new users
    DEFAULT_STARTING_BALANCE: int = 100
    
    # Russian Roulette settings
    ROULETTE_CHAMBERS: int = 6  # 1/6 probability for shot
    ROULETTE_SHOT_PENALTY: int = 50  # Points lost on shot
    ROULETTE_SURVIVAL_REWARD: int = 10  # Points gained on survival
    
    # Oleg-style messages for roulette
    ROULETTE_SHOT_MESSAGES: List[str] = [
        "💥 БАХ! Пуля нашла твою голову. -{points} очков. Не повезло, бро.",
        "💀 Щёлк... БАМ! Ты труп. -{points} очков. Классика жанра.",
        "🔫 Барабан крутится... ВЫСТРЕЛ! -{points} очков. Олег скорбит.",
        "💥 Ну что, герой? Пуля в черепушке. -{points} очков. F.",
        "☠️ Рулетка не прощает. Выстрел в висок. -{points} очков.",
    ]
    
    ROULETTE_SURVIVAL_MESSAGES: List[str] = [
        "😮‍💨 Щёлк... пусто! Ты выжил, везунчик. +{points} очков.",
        "🍀 Барабан крутится... тишина. Живой! +{points} очков.",
        "😎 Холодный пот, но ты цел. +{points} очков. Красавчик.",
        "🎰 Фортуна на твоей стороне. Пустой патронник. +{points} очков.",
        "✨ Сегодня не твой день умирать. +{points} очков.",
    ]
    
    # Coin Flip messages
    COINFLIP_WIN_MESSAGES: List[str] = [
        "🪙 {result}! Угадал, красавчик. +{amount} очков.",
        "💰 Монетка говорит {result}. Ты в плюсе на {amount}!",
        "🎯 Бинго! {result}. Забирай свои {amount} очков.",
        "✨ Фортуна улыбается. {result} — твоя победа. +{amount}.",
        "🍀 {result}! Везунчик. +{amount} в карман.",
    ]
    
    COINFLIP_LOSE_MESSAGES: List[str] = [
        "🪙 {result}! Мимо. -{amount} очков.",
        "💸 Монетка говорит {result}. Ты проиграл {amount}.",
        "😬 Не угадал. {result}. -{amount} очков.",
        "🎲 {result}. Не твой день. -{amount}.",
        "💀 {result}! Деньги уходят. -{amount} очков.",
    ]
    
    def __init__(self, random_func: Optional[Callable[[], float]] = None):
        """
        Initialize the game engine.
        
        Args:
            random_func: Optional custom random function for testing.
                         Should return float in [0, 1). Defaults to random.random.
        """
        # In-memory storage for challenges (for testing without DB)
        # In production, these would be DB operations
        self._challenges: dict[str, Challenge] = {}
        self._balances: dict[tuple[int, int], UserBalanceData] = {}
        # Random function for games (injectable for testing)
        self._random = random_func or random.random
    
    def _generate_challenge_id(self) -> str:
        """Generate a unique challenge ID."""
        return str(uuid.uuid4())
    
    def get_balance(self, user_id: int, chat_id: int) -> UserBalanceData:
        """
        Get user balance, creating default if not exists.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            
        Returns:
            UserBalanceData with current balance
        """
        key = (user_id, chat_id)
        if key not in self._balances:
            self._balances[key] = UserBalanceData(
                user_id=user_id,
                chat_id=chat_id,
                balance=self.DEFAULT_STARTING_BALANCE,
                total_won=0,
                total_lost=0
            )
        return self._balances[key]

    def set_balance(self, user_id: int, chat_id: int, balance: int) -> None:
        """
        Set user balance directly.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            balance: New balance value
        """
        data = self.get_balance(user_id, chat_id)
        data.balance = balance
    
    def has_pending_challenge(self, user_id: int, chat_id: int) -> bool:
        """
        Check if user has a pending challenge.
        
        Requirements 8.4: Prevent multiple pending challenges.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            
        Returns:
            True if user has pending challenge as challenger
        """
        for challenge in self._challenges.values():
            if (challenge.challenger_id == user_id and 
                challenge.chat_id == chat_id and
                challenge.status == ChallengeStatus.PENDING):
                return True
        return False
    
    def get_pending_challenge(self, challenge_id: str) -> Optional[Challenge]:
        """
        Get a pending challenge by ID.
        
        Args:
            challenge_id: Challenge UUID
            
        Returns:
            Challenge if found and pending, None otherwise
        """
        challenge = self._challenges.get(challenge_id)
        if challenge and challenge.status == ChallengeStatus.PENDING:
            return challenge
        return None
    
    def create_challenge(
        self,
        chat_id: int,
        challenger_id: int,
        target_id: int,
        game_type: str = GameType.PVP,
        bet_amount: int = 0,
        timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES
    ) -> ChallengeResult:
        """
        Create a new game challenge.
        
        Requirements:
        - 8.1: Send challenge with Accept button
        - 8.4: Prevent multiple pending challenges
        
        Args:
            chat_id: Telegram chat ID
            challenger_id: Challenger's user ID
            target_id: Target's user ID
            game_type: Type of game
            bet_amount: Amount to bet (0 for no bet)
            timeout_minutes: Minutes until challenge expires
            
        Returns:
            ChallengeResult with success status and challenge data
        """
        # Validate: can't challenge yourself
        if challenger_id == target_id:
            return ChallengeResult(
                success=False,
                message="Сам с собой играть — признак одиночества.",
                error_code="SELF_CHALLENGE"
            )
        
        # Requirements 8.4: Check for pending challenges
        if self.has_pending_challenge(challenger_id, chat_id):
            return ChallengeResult(
                success=False,
                message="У тебя уже есть активный вызов. Дождись ответа или отмени.",
                error_code="PENDING_EXISTS"
            )
        
        # Validate bet amount
        if bet_amount < 0:
            return ChallengeResult(
                success=False,
                message="Ставка должна быть положительной, гений.",
                error_code="INVALID_BET"
            )
        
        # Check challenger balance if betting
        if bet_amount > 0:
            challenger_balance = self.get_balance(challenger_id, chat_id)
            if challenger_balance.balance < bet_amount:
                return ChallengeResult(
                    success=False,
                    message="Денег нет, но ты держись.",
                    error_code="INSUFFICIENT_BALANCE"
                )
        
        # Create challenge
        now = utc_now()
        challenge = Challenge(
            id=self._generate_challenge_id(),
            chat_id=chat_id,
            challenger_id=challenger_id,
            target_id=target_id,
            game_type=game_type,
            bet_amount=bet_amount,
            status=ChallengeStatus.PENDING,
            created_at=now,
            expires_at=now + timedelta(minutes=timeout_minutes)
        )
        
        self._challenges[challenge.id] = challenge
        
        logger.info(
            f"Challenge created: {challenge.id} - "
            f"{challenger_id} vs {target_id} for {bet_amount}"
        )
        
        return ChallengeResult(
            success=True,
            message="Вызов отправлен! Ждём ответа...",
            challenge=challenge
        )

    def accept_challenge(self, challenge_id: str, acceptor_id: int) -> ChallengeResult:
        """
        Accept a game challenge.
        
        Requirements:
        - 8.2: Start game and deduct resources from both players
        
        Args:
            challenge_id: Challenge UUID
            acceptor_id: User ID of the person accepting
            
        Returns:
            ChallengeResult with success status
        """
        challenge = self._challenges.get(challenge_id)
        
        if not challenge:
            return ChallengeResult(
                success=False,
                message="Вызов не найден.",
                error_code="NOT_FOUND"
            )
        
        if challenge.status != ChallengeStatus.PENDING:
            return ChallengeResult(
                success=False,
                message="Этот вызов уже не активен.",
                error_code="NOT_PENDING"
            )
        
        # Check if acceptor is the target
        if acceptor_id != challenge.target_id:
            return ChallengeResult(
                success=False,
                message="Этот вызов не для тебя.",
                error_code="WRONG_TARGET"
            )
        
        # Check if challenge expired
        if utc_now() > challenge.expires_at:
            challenge.status = ChallengeStatus.EXPIRED
            return ChallengeResult(
                success=False,
                message="Вызов протух. Трус не принял бой вовремя.",
                error_code="EXPIRED"
            )
        
        # Requirements 8.2: Deduct resources from both players
        if challenge.bet_amount > 0:
            challenger_balance = self.get_balance(challenge.challenger_id, challenge.chat_id)
            target_balance = self.get_balance(challenge.target_id, challenge.chat_id)
            
            # Verify both have sufficient balance
            if challenger_balance.balance < challenge.bet_amount:
                challenge.status = ChallengeStatus.CANCELLED
                return ChallengeResult(
                    success=False,
                    message="У челленджера кончились деньги. Вызов отменён.",
                    error_code="CHALLENGER_BROKE"
                )
            
            if target_balance.balance < challenge.bet_amount:
                return ChallengeResult(
                    success=False,
                    message="Денег нет, но ты держись.",
                    error_code="INSUFFICIENT_BALANCE"
                )
            
            # Deduct from both
            challenger_balance.balance -= challenge.bet_amount
            challenger_balance.total_lost += challenge.bet_amount
            
            target_balance.balance -= challenge.bet_amount
            target_balance.total_lost += challenge.bet_amount
        
        # Mark as accepted
        challenge.status = ChallengeStatus.ACCEPTED
        
        logger.info(
            f"Challenge accepted: {challenge_id} - "
            f"bet {challenge.bet_amount} deducted from both players"
        )
        
        return ChallengeResult(
            success=True,
            message="Вызов принят! Да начнётся битва!",
            challenge=challenge
        )
    
    def decline_challenge(self, challenge_id: str, decliner_id: int) -> ChallengeResult:
        """
        Decline a game challenge.
        
        Args:
            challenge_id: Challenge UUID
            decliner_id: User ID of the person declining
            
        Returns:
            ChallengeResult with success status
        """
        challenge = self._challenges.get(challenge_id)
        
        if not challenge:
            return ChallengeResult(
                success=False,
                message="Вызов не найден.",
                error_code="NOT_FOUND"
            )
        
        if challenge.status != ChallengeStatus.PENDING:
            return ChallengeResult(
                success=False,
                message="Этот вызов уже не активен.",
                error_code="NOT_PENDING"
            )
        
        # Check if decliner is the target
        if decliner_id != challenge.target_id:
            return ChallengeResult(
                success=False,
                message="Этот вызов не для тебя.",
                error_code="WRONG_TARGET"
            )
        
        # Mark as declined - no resources deducted
        challenge.status = ChallengeStatus.DECLINED
        
        logger.info(f"Challenge declined: {challenge_id}")
        
        return ChallengeResult(
            success=True,
            message="Вызов отклонён. Трус!",
            challenge=challenge
        )

    def cancel_expired_challenges(self) -> List[Challenge]:
        """
        Cancel all expired challenges.
        
        Requirements:
        - 8.3: Cancel without deducting resources on timeout
        
        Returns:
            List of cancelled challenges
        """
        now = utc_now()
        cancelled = []
        
        for challenge in self._challenges.values():
            if (challenge.status == ChallengeStatus.PENDING and 
                now > challenge.expires_at):
                challenge.status = ChallengeStatus.EXPIRED
                cancelled.append(challenge)
                logger.info(f"Challenge expired: {challenge.id}")
        
        return cancelled
    
    def cancel_challenge(self, challenge_id: str, canceller_id: int) -> ChallengeResult:
        """
        Cancel a pending challenge (by challenger only).
        
        Args:
            challenge_id: Challenge UUID
            canceller_id: User ID of the person cancelling
            
        Returns:
            ChallengeResult with success status
        """
        challenge = self._challenges.get(challenge_id)
        
        if not challenge:
            return ChallengeResult(
                success=False,
                message="Вызов не найден.",
                error_code="NOT_FOUND"
            )
        
        if challenge.status != ChallengeStatus.PENDING:
            return ChallengeResult(
                success=False,
                message="Этот вызов уже не активен.",
                error_code="NOT_PENDING"
            )
        
        # Only challenger can cancel
        if canceller_id != challenge.challenger_id:
            return ChallengeResult(
                success=False,
                message="Только создатель вызова может его отменить.",
                error_code="NOT_CHALLENGER"
            )
        
        # Cancel without deducting resources
        challenge.status = ChallengeStatus.CANCELLED
        
        logger.info(f"Challenge cancelled by challenger: {challenge_id}")
        
        return ChallengeResult(
            success=True,
            message="Вызов отменён.",
            challenge=challenge
        )
    
    def get_user_pending_challenges(self, user_id: int, chat_id: int) -> List[Challenge]:
        """
        Get all pending challenges involving a user.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            
        Returns:
            List of pending challenges where user is challenger or target
        """
        result = []
        for challenge in self._challenges.values():
            if (challenge.chat_id == chat_id and
                challenge.status == ChallengeStatus.PENDING and
                (challenge.challenger_id == user_id or challenge.target_id == user_id)):
                result.append(challenge)
        return result
    
    def play_roulette(self, user_id: int, chat_id: int, bet_amount: int = 0) -> RouletteResult:
        """
        Play Russian Roulette.
        
        Requirements:
        - 5.1: Animation phases (handled by handler)
        - 5.2: "БАХ! 💀" on shot
        - 5.3: "Щелк... 😅" on survival
        - 5.4: Coin betting option
        - 5.5: Deduct bet on loss, award winnings on survival
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            bet_amount: Amount to bet (0 for standard mode with fixed points)
            
        Returns:
            RouletteResult with outcome and new balance
        """
        # Get current balance
        balance_data = self.get_balance(user_id, chat_id)
        
        # Validate bet amount if betting mode
        if bet_amount < 0:
            return RouletteResult(
                success=False,
                message="Ставка должна быть положительной, гений.",
                shot=False,
                points_change=0,
                new_balance=balance_data.balance,
                bet_amount=bet_amount,
                error_code="INVALID_BET"
            )
        
        # Check sufficient balance for betting mode
        if bet_amount > 0 and balance_data.balance < bet_amount:
            return RouletteResult(
                success=False,
                message="Денег нет, но ты держись.",
                shot=False,
                points_change=0,
                new_balance=balance_data.balance,
                bet_amount=bet_amount,
                error_code="INSUFFICIENT_BALANCE"
            )
        
        # Spin the chamber - 1/6 chance of shot
        chamber = int(self._random() * self.ROULETTE_CHAMBERS)
        shot = (chamber == 0)  # Chamber 0 = bullet
        
        if bet_amount > 0:
            # Betting mode: bet on survival
            if shot:
                # Shot - lose bet
                points_change = -bet_amount
                message_template = random.choice(self.ROULETTE_SHOT_MESSAGES)
                message = message_template.format(points=bet_amount)
                balance_data.balance += points_change
                balance_data.total_lost += bet_amount
            else:
                # Survived - win bet (1:1 payout, so net gain = bet_amount)
                points_change = bet_amount
                message_template = random.choice(self.ROULETTE_SURVIVAL_MESSAGES)
                message = message_template.format(points=bet_amount)
                balance_data.balance += points_change
                balance_data.total_won += bet_amount
        else:
            # Standard mode: fixed points
            if shot:
                # Shot - deduct points
                points_change = -self.ROULETTE_SHOT_PENALTY
                message_template = random.choice(self.ROULETTE_SHOT_MESSAGES)
                message = message_template.format(points=self.ROULETTE_SHOT_PENALTY)
                balance_data.balance += points_change
                balance_data.total_lost += self.ROULETTE_SHOT_PENALTY
            else:
                # Survived - award points
                points_change = self.ROULETTE_SURVIVAL_REWARD
                message_template = random.choice(self.ROULETTE_SURVIVAL_MESSAGES)
                message = message_template.format(points=self.ROULETTE_SURVIVAL_REWARD)
                balance_data.balance += points_change
                balance_data.total_won += self.ROULETTE_SURVIVAL_REWARD
        
        logger.info(
            f"Roulette: user {user_id} in chat {chat_id} - "
            f"{'SHOT' if shot else 'SURVIVED'}, bet={bet_amount}, balance change: {points_change}"
        )
        
        return RouletteResult(
            success=True,
            message=message,
            shot=shot,
            points_change=points_change,
            new_balance=balance_data.balance,
            bet_amount=bet_amount
        )
    
    def flip_coin(
        self,
        user_id: int,
        chat_id: int,
        bet_amount: int,
        choice: str
    ) -> CoinFlipResult:
        """
        Play Coin Flip game.
        
        Requirements:
        - 10.1: Accept bet amount and choice (heads/tails)
        - 10.2: 50/50 probability
        - 10.3: Double bet on win
        - 10.4: Deduct bet on loss
        - 10.5: Reject if insufficient balance
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            bet_amount: Amount to bet
            choice: User's choice ("heads" or "tails")
            
        Returns:
            CoinFlipResult with outcome and new balance
        """
        # Normalize choice
        choice = choice.lower().strip()
        if choice not in ("heads", "tails"):
            return CoinFlipResult(
                success=False,
                message="Выбери heads или tails, гений.",
                choice=choice,
                result="",
                won=False,
                bet_amount=bet_amount,
                balance_change=0,
                new_balance=0,
                error_code="INVALID_CHOICE"
            )
        
        # Validate bet amount
        if bet_amount <= 0:
            return CoinFlipResult(
                success=False,
                message="Ставка должна быть положительной, гений.",
                choice=choice,
                result="",
                won=False,
                bet_amount=bet_amount,
                balance_change=0,
                new_balance=0,
                error_code="INVALID_BET"
            )
        
        # Get current balance
        balance_data = self.get_balance(user_id, chat_id)
        
        # Requirements 10.5: Check sufficient balance
        if balance_data.balance < bet_amount:
            return CoinFlipResult(
                success=False,
                message="Денег нет, но ты держись.",
                choice=choice,
                result="",
                won=False,
                bet_amount=bet_amount,
                balance_change=0,
                new_balance=balance_data.balance,
                error_code="INSUFFICIENT_BALANCE"
            )
        
        # Requirements 10.2: 50/50 probability
        coin_result = "heads" if self._random() < 0.5 else "tails"
        won = (choice == coin_result)
        
        if won:
            # Requirements 10.3: Double bet on win (net gain = bet_amount)
            balance_change = bet_amount
            balance_data.balance += balance_change
            balance_data.total_won += balance_change
            message_template = random.choice(self.COINFLIP_WIN_MESSAGES)
            message = message_template.format(
                result=coin_result.capitalize(),
                amount=bet_amount
            )
        else:
            # Requirements 10.4: Deduct bet on loss
            balance_change = -bet_amount
            balance_data.balance += balance_change
            balance_data.total_lost += bet_amount
            message_template = random.choice(self.COINFLIP_LOSE_MESSAGES)
            message = message_template.format(
                result=coin_result.capitalize(),
                amount=bet_amount
            )
        
        logger.info(
            f"CoinFlip: user {user_id} in chat {chat_id} - "
            f"choice={choice}, result={coin_result}, won={won}, "
            f"bet={bet_amount}, balance_change={balance_change}"
        )
        
        return CoinFlipResult(
            success=True,
            message=message,
            choice=choice,
            result=coin_result,
            won=won,
            bet_amount=bet_amount,
            balance_change=balance_change,
            new_balance=balance_data.balance
        )
    
    def clear_challenges(self) -> None:
        """Clear all challenges (for testing)."""
        self._challenges.clear()
    
    def clear_balances(self) -> None:
        """Clear all balances (for testing)."""
        self._balances.clear()
    
    def reset(self) -> None:
        """Reset all state (for testing)."""
        self.clear_challenges()
        self.clear_balances()


# Global game engine instance
game_engine = GameEngine()
