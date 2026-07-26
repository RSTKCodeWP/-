"""
Async Game Engine - Uses wallet_service for persistent balance storage.

Replaces the in-memory balance storage in game_engine.py with
database-backed wallet_service for production use.

Requirements: 8.1, 8.2, 8.3, 8.4, 9.1-9.4, 10.1-10.5
"""

import logging
import random
from dataclasses import dataclass
from typing import Optional, List

from app.services import wallet_service

logger = logging.getLogger(__name__)


@dataclass
class RouletteResult:
    """Result of a Russian Roulette game."""
    success: bool
    message: str
    shot: bool
    points_change: int
    new_balance: int
    bet_amount: int = 0
    error_code: Optional[str] = None


@dataclass
class CoinFlipResult:
    """Result of a Coin Flip game."""
    success: bool
    message: str
    choice: str
    result: str
    won: bool
    bet_amount: int
    balance_change: int
    new_balance: int
    error_code: Optional[str] = None


class AsyncGameEngine:
    """
    Async game engine with persistent balance storage.
    
    Uses wallet_service for all balance operations.
    """
    
    # Russian Roulette settings
    ROULETTE_CHAMBERS: int = 6
    ROULETTE_SHOT_PENALTY: int = 50
    ROULETTE_SURVIVAL_REWARD: int = 10
    
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
    
    async def get_balance(self, user_id: int) -> int:
        """Get user balance from wallet_service."""
        return await wallet_service.get_balance(user_id)
    
    async def play_roulette(self, user_id: int, bet_amount: int = 0) -> RouletteResult:
        """
        Play Russian Roulette with persistent balance.
        
        Args:
            user_id: Telegram user ID
            bet_amount: Amount to bet (0 for standard mode)
            
        Returns:
            RouletteResult with outcome
        """
        current_balance = await wallet_service.get_balance(user_id)
        
        # Validate bet
        if bet_amount < 0:
            return RouletteResult(
                success=False,
                message="Ставка должна быть положительной, гений.",
                shot=False,
                points_change=0,
                new_balance=current_balance,
                bet_amount=bet_amount,
                error_code="INVALID_BET"
            )
        
        if bet_amount > 0 and current_balance < bet_amount:
            return RouletteResult(
                success=False,
                message=f"Денег нет, но ты держись. У тебя {current_balance}.",
                shot=False,
                points_change=0,
                new_balance=current_balance,
                bet_amount=bet_amount,
                error_code="INSUFFICIENT_BALANCE"
            )
        
        # Spin the chamber - 1/6 chance of shot
        chamber = random.randint(0, self.ROULETTE_CHAMBERS - 1)
        shot = (chamber == 0)
        
        if bet_amount > 0:
            # Betting mode
            if shot:
                points_change = -bet_amount
                message_template = random.choice(self.ROULETTE_SHOT_MESSAGES)
                message = message_template.format(points=bet_amount)
                result = await wallet_service.deduct_balance(user_id, bet_amount, "roulette loss")
            else:
                points_change = bet_amount
                message_template = random.choice(self.ROULETTE_SURVIVAL_MESSAGES)
                message = message_template.format(points=bet_amount)
                result = await wallet_service.add_balance(user_id, bet_amount, "roulette win")
        else:
            # Standard mode: fixed points
            if shot:
                points_change = -self.ROULETTE_SHOT_PENALTY
                message_template = random.choice(self.ROULETTE_SHOT_MESSAGES)
                message = message_template.format(points=self.ROULETTE_SHOT_PENALTY)
                result = await wallet_service.deduct_balance(
                    user_id, self.ROULETTE_SHOT_PENALTY, "roulette shot"
                )
            else:
                points_change = self.ROULETTE_SURVIVAL_REWARD
                message_template = random.choice(self.ROULETTE_SURVIVAL_MESSAGES)
                message = message_template.format(points=self.ROULETTE_SURVIVAL_REWARD)
                result = await wallet_service.add_balance(
                    user_id, self.ROULETTE_SURVIVAL_REWARD, "roulette survival"
                )
        
        logger.info(
            f"Roulette: user {user_id} - "
            f"{'SHOT' if shot else 'SURVIVED'}, bet={bet_amount}, change={points_change}"
        )
        
        return RouletteResult(
            success=True,
            message=message,
            shot=shot,
            points_change=points_change,
            new_balance=result.balance,
            bet_amount=bet_amount
        )
    
    async def flip_coin(
        self,
        user_id: int,
        bet_amount: int,
        choice: str
    ) -> CoinFlipResult:
        """
        Play Coin Flip with persistent balance.
        
        Args:
            user_id: Telegram user ID
            bet_amount: Amount to bet
            choice: User's choice ("heads" or "tails")
            
        Returns:
            CoinFlipResult with outcome
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
        
        current_balance = await wallet_service.get_balance(user_id)
        
        if current_balance < bet_amount:
            return CoinFlipResult(
                success=False,
                message=f"Денег нет, но ты держись. У тебя {current_balance}.",
                choice=choice,
                result="",
                won=False,
                bet_amount=bet_amount,
                balance_change=0,
                new_balance=current_balance,
                error_code="INSUFFICIENT_BALANCE"
            )
        
        # 50/50 flip
        coin_result = "heads" if random.random() < 0.5 else "tails"
        won = (choice == coin_result)
        
        if won:
            balance_change = bet_amount
            message_template = random.choice(self.COINFLIP_WIN_MESSAGES)
            message = message_template.format(result=coin_result.capitalize(), amount=bet_amount)
            result = await wallet_service.add_balance(user_id, bet_amount, "coinflip win")
        else:
            balance_change = -bet_amount
            message_template = random.choice(self.COINFLIP_LOSE_MESSAGES)
            message = message_template.format(result=coin_result.capitalize(), amount=bet_amount)
            result = await wallet_service.deduct_balance(user_id, bet_amount, "coinflip loss")
        
        logger.info(
            f"CoinFlip: user {user_id} - choice={choice}, result={coin_result}, "
            f"won={won}, bet={bet_amount}"
        )
        
        return CoinFlipResult(
            success=True,
            message=message,
            choice=choice,
            result=coin_result,
            won=won,
            bet_amount=bet_amount,
            balance_change=balance_change,
            new_balance=result.balance
        )


# Global async game engine instance
async_game_engine = AsyncGameEngine()
