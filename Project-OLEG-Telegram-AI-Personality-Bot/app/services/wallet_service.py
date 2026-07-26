"""
Unified Wallet Service - Single source of truth for user balances.

Replaces the fragmented economy system:
- Wallet (global balance)
- UserBalance (per-chat balance) 
- game_engine._balances (in-memory)

All games now use this service for balance operations.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.database.models import User, Wallet

logger = logging.getLogger(__name__)


# Default starting balance for new users
DEFAULT_BALANCE = 100


@dataclass
class BalanceResult:
    """Result of a balance operation."""
    success: bool
    message: str
    balance: int = 0
    error_code: Optional[str] = None


async def get_or_create_user(tg_user_id: int, username: Optional[str] = None) -> User:
    """
    Get or create a User record by Telegram user ID.
    
    Args:
        tg_user_id: Telegram user ID
        username: Optional username
        
    Returns:
        User object
    """
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.tg_user_id == tg_user_id)
        )
        user = result.scalars().first()
        
        if not user:
            user = User(tg_user_id=tg_user_id, username=username)
            session.add(user)
            await session.flush()
            
            # Create wallet for new user
            wallet = Wallet(user_id=user.id, balance=DEFAULT_BALANCE)
            session.add(wallet)
            await session.commit()
            await session.refresh(user)
            
        return user


async def get_balance(tg_user_id: int) -> int:
    """
    Get user's balance from Wallet.
    
    Args:
        tg_user_id: Telegram user ID
        
    Returns:
        Current balance (creates wallet with default balance if not exists)
    """
    async_session = get_session()
    async with async_session() as session:
        # Get user
        result = await session.execute(
            select(User).where(User.tg_user_id == tg_user_id)
        )
        user = result.scalars().first()
        
        if not user:
            # Create user and wallet
            user = User(tg_user_id=tg_user_id)
            session.add(user)
            await session.flush()
            
            wallet = Wallet(user_id=user.id, balance=DEFAULT_BALANCE)
            session.add(wallet)
            await session.commit()
            return DEFAULT_BALANCE
        
        # Get wallet
        result = await session.execute(
            select(Wallet).where(Wallet.user_id == user.id)
        )
        wallet = result.scalars().first()
        
        if not wallet:
            wallet = Wallet(user_id=user.id, balance=DEFAULT_BALANCE)
            session.add(wallet)
            await session.commit()
            return DEFAULT_BALANCE
        
        return wallet.balance


async def add_balance(tg_user_id: int, amount: int, reason: str = "") -> BalanceResult:
    """
    Add coins to user's balance.
    
    Args:
        tg_user_id: Telegram user ID
        amount: Amount to add (must be positive)
        reason: Optional reason for logging
        
    Returns:
        BalanceResult with new balance
    """
    if amount <= 0:
        return BalanceResult(
            success=False,
            message="Сумма должна быть положительной",
            error_code="INVALID_AMOUNT"
        )
    
    async_session = get_session()
    async with async_session() as session:
        # Get or create user
        result = await session.execute(
            select(User).where(User.tg_user_id == tg_user_id)
        )
        user = result.scalars().first()
        
        if not user:
            user = User(tg_user_id=tg_user_id)
            session.add(user)
            await session.flush()
        
        # Get or create wallet
        result = await session.execute(
            select(Wallet).where(Wallet.user_id == user.id)
        )
        wallet = result.scalars().first()
        
        if not wallet:
            wallet = Wallet(user_id=user.id, balance=DEFAULT_BALANCE)
            session.add(wallet)
        
        wallet.balance += amount
        await session.commit()
        
        logger.info(f"Added {amount} to user {tg_user_id}: {reason} (new balance: {wallet.balance})")
        
        return BalanceResult(
            success=True,
            message=f"+{amount} монет",
            balance=wallet.balance
        )


async def deduct_balance(tg_user_id: int, amount: int, reason: str = "") -> BalanceResult:
    """
    Deduct coins from user's balance.
    
    Args:
        tg_user_id: Telegram user ID
        amount: Amount to deduct (must be positive)
        reason: Optional reason for logging
        
    Returns:
        BalanceResult with new balance or error
    """
    if amount <= 0:
        return BalanceResult(
            success=False,
            message="Сумма должна быть положительной",
            error_code="INVALID_AMOUNT"
        )
    
    current = await get_balance(tg_user_id)
    
    if current < amount:
        return BalanceResult(
            success=False,
            message=f"Недостаточно монет. У тебя {current}, нужно {amount}",
            balance=current,
            error_code="INSUFFICIENT_FUNDS"
        )
    
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.tg_user_id == tg_user_id)
        )
        user = result.scalars().first()
        
        if not user:
            return BalanceResult(
                success=False,
                message="Пользователь не найден",
                error_code="USER_NOT_FOUND"
            )
        
        result = await session.execute(
            select(Wallet).where(Wallet.user_id == user.id)
        )
        wallet = result.scalars().first()
        
        if not wallet:
            return BalanceResult(
                success=False,
                message="Кошелёк не найден",
                error_code="WALLET_NOT_FOUND"
            )
        
        wallet.balance -= amount
        await session.commit()
        
        logger.info(f"Deducted {amount} from user {tg_user_id}: {reason} (new balance: {wallet.balance})")
        
        return BalanceResult(
            success=True,
            message=f"-{amount} монет",
            balance=wallet.balance
        )


async def set_balance(tg_user_id: int, amount: int, reason: str = "") -> BalanceResult:
    """
    Set user's balance to a specific amount.
    
    Args:
        tg_user_id: Telegram user ID
        amount: New balance (can be 0 or positive)
        reason: Optional reason for logging
        
    Returns:
        BalanceResult with new balance
    """
    if amount < 0:
        return BalanceResult(
            success=False,
            message="Баланс не может быть отрицательным",
            error_code="INVALID_AMOUNT"
        )
    
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.tg_user_id == tg_user_id)
        )
        user = result.scalars().first()
        
        if not user:
            user = User(tg_user_id=tg_user_id)
            session.add(user)
            await session.flush()
        
        result = await session.execute(
            select(Wallet).where(Wallet.user_id == user.id)
        )
        wallet = result.scalars().first()
        
        if not wallet:
            wallet = Wallet(user_id=user.id, balance=amount)
            session.add(wallet)
        else:
            wallet.balance = amount
        
        await session.commit()
        
        logger.info(f"Set balance for user {tg_user_id} to {amount}: {reason}")
        
        return BalanceResult(
            success=True,
            message=f"Баланс: {amount}",
            balance=amount
        )


async def transfer(from_user_id: int, to_user_id: int, amount: int) -> BalanceResult:
    """
    Transfer coins between users.
    
    Args:
        from_user_id: Sender's Telegram user ID
        to_user_id: Receiver's Telegram user ID
        amount: Amount to transfer
        
    Returns:
        BalanceResult with sender's new balance
    """
    if from_user_id == to_user_id:
        return BalanceResult(
            success=False,
            message="Нельзя перевести самому себе",
            error_code="SELF_TRANSFER"
        )
    
    if amount <= 0:
        return BalanceResult(
            success=False,
            message="Сумма должна быть положительной",
            error_code="INVALID_AMOUNT"
        )
    
    # Deduct from sender
    deduct_result = await deduct_balance(from_user_id, amount, f"transfer to {to_user_id}")
    if not deduct_result.success:
        return deduct_result
    
    # Add to receiver
    add_result = await add_balance(to_user_id, amount, f"transfer from {from_user_id}")
    if not add_result.success:
        # Rollback
        await add_balance(from_user_id, amount, "transfer rollback")
        return BalanceResult(
            success=False,
            message="Ошибка перевода",
            error_code="TRANSFER_ERROR"
        )
    
    return BalanceResult(
        success=True,
        message=f"Переведено {amount} монет",
        balance=deduct_result.balance
    )


# Convenience aliases for backward compatibility
wallet_service_get_balance = get_balance
wallet_service_add = add_balance
wallet_service_deduct = deduct_balance
