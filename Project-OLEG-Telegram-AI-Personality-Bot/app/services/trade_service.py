"""Trade Service - P2P trading between users.

v9.5 - Allows users to exchange items and coins.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.database.models import Trade, UserInventory
from app.services.inventory import inventory_service, ITEM_CATALOG
from app.services import wallet_service
from app.utils import utc_now

logger = logging.getLogger(__name__)


@dataclass
class TradeResult:
    """Result of trade operation."""
    success: bool
    message: str
    trade_id: Optional[int] = None


class TradeService:
    """Service for managing P2P trades."""
    
    TRADE_EXPIRY_MINUTES = 5
    
    async def create_trade(
        self,
        from_user_id: int,
        to_user_id: int,
        chat_id: int,
        offer_items: List[Dict[str, Any]],
        offer_coins: int,
        request_items: List[Dict[str, Any]],
        request_coins: int
    ) -> TradeResult:
        """
        Create a new trade offer.
        
        Args:
            from_user_id: User creating the trade
            to_user_id: User receiving the trade offer
            chat_id: Chat ID
            offer_items: Items offered [{"item_type": "...", "quantity": 1}]
            offer_coins: Coins offered
            request_items: Items requested
            request_coins: Coins requested
            
        Returns:
            TradeResult with success status
        """
        if from_user_id == to_user_id:
            return TradeResult(False, "❌ Нельзя обмениваться с самим собой!")
        
        if not offer_items and offer_coins == 0:
            return TradeResult(False, "❌ Ты должен что-то предложить!")
        
        if not request_items and request_coins == 0:
            return TradeResult(False, "❌ Ты должен что-то запросить!")
        
        async_session = get_session()
        async with async_session() as session:
            async with session.begin():
                # Validate and lock offered items
                locked_items = []
                for item_spec in offer_items:
                    item_type = item_spec["item_type"]
                    quantity = item_spec.get("quantity", 1)
                    
                    # Check if user has the item
                    user_item = await inventory_service.get_item(from_user_id, chat_id, item_type)
                    if not user_item or user_item.quantity < quantity:
                        return TradeResult(False, f"❌ У тебя недостаточно {ITEM_CATALOG[item_type].name}!")
                    
                    # Lock item (remove from inventory)
                    result = await inventory_service.remove_item(from_user_id, chat_id, item_type, quantity)
                    if not result.success:
                        return TradeResult(False, result.message)
                    
                    locked_items.append({
                        "item_type": item_type,
                        "quantity": quantity,
                        "item_name": user_item.item_name,
                        "item_data": user_item.item_data
                    })
                
                # Validate offered coins
                if offer_coins > 0:
                    balance = await wallet_service.get_balance(from_user_id)
                    if balance < offer_coins:
                        # Rollback locked items
                        for item in locked_items:
                            await inventory_service.add_item(
                                from_user_id, chat_id, item["item_type"], item["quantity"]
                            )
                        return TradeResult(False, f"❌ У тебя недостаточно монет! (есть {balance}, нужно {offer_coins})")
                
                # Create trade
                expires_at = utc_now() + timedelta(minutes=self.TRADE_EXPIRY_MINUTES)
                trade = Trade(
                    from_user_id=from_user_id,
                    to_user_id=to_user_id,
                    chat_id=chat_id,
                    offer_items=json.dumps(locked_items) if locked_items else None,
                    offer_coins=offer_coins,
                    request_items=json.dumps(request_items) if request_items else None,
                    request_coins=request_coins,
                    status="pending",
                    expires_at=expires_at
                )
                session.add(trade)
                await session.flush()
                
                trade_id = trade.id
        
        return TradeResult(True, "✅ Предложение обмена отправлено!", trade_id)
    
    async def accept_trade(self, trade_id: int, user_id: int) -> TradeResult:
        """Accept a trade offer."""
        async_session = get_session()
        async with async_session() as session:
            async with session.begin():
                # Get trade
                result = await session.execute(
                    select(Trade).where(Trade.id == trade_id)
                )
                trade = result.scalars().first()
                
                if not trade:
                    return TradeResult(False, "❌ Обмен не найден!")
                
                if trade.to_user_id != user_id:
                    return TradeResult(False, "❌ Это не твой обмен!")
                
                if trade.status != "pending":
                    return TradeResult(False, f"❌ Обмен уже {trade.status}!")
                
                if utc_now() > trade.expires_at:
                    trade.status = "expired"
                    await session.commit()
                    return TradeResult(False, "❌ Время обмена истекло!")
                
                # Validate receiver has requested items
                request_items = json.loads(trade.request_items) if trade.request_items else []
                for item_spec in request_items:
                    item_type = item_spec["item_type"]
                    quantity = item_spec.get("quantity", 1)
                    
                    user_item = await inventory_service.get_item(user_id, trade.chat_id, item_type)
                    if not user_item or user_item.quantity < quantity:
                        return TradeResult(False, f"❌ У тебя недостаточно {ITEM_CATALOG[item_type].name}!")
                
                # Validate receiver has requested coins
                if trade.request_coins > 0:
                    balance = await wallet_service.get_balance(user_id)
                    if balance < trade.request_coins:
                        return TradeResult(False, f"❌ У тебя недостаточно монет! (есть {balance}, нужно {trade.request_coins})")
                
                # Execute trade
                # 1. Transfer offered items to receiver
                offer_items = json.loads(trade.offer_items) if trade.offer_items else []
                for item in offer_items:
                    await inventory_service.add_item(
                        user_id, trade.chat_id, item["item_type"], item["quantity"]
                    )
                
                # 2. Transfer offered coins to receiver
                if trade.offer_coins > 0:
                    await wallet_service.transfer(trade.from_user_id, user_id, trade.offer_coins)
                
                # 3. Transfer requested items to initiator
                for item_spec in request_items:
                    await inventory_service.remove_item(
                        user_id, trade.chat_id, item_spec["item_type"], item_spec.get("quantity", 1)
                    )
                    await inventory_service.add_item(
                        trade.from_user_id, trade.chat_id, item_spec["item_type"], item_spec.get("quantity", 1)
                    )
                
                # 4. Transfer requested coins to initiator
                if trade.request_coins > 0:
                    await wallet_service.transfer(user_id, trade.from_user_id, trade.request_coins)
                
                # Mark trade as accepted
                trade.status = "accepted"
                trade.completed_at = utc_now()
                await session.commit()
        
        return TradeResult(True, "✅ Обмен завершен!", trade_id)
    
    async def reject_trade(self, trade_id: int, user_id: int) -> TradeResult:
        """Reject a trade offer."""
        async_session = get_session()
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Trade).where(Trade.id == trade_id)
                )
                trade = result.scalars().first()
                
                if not trade:
                    return TradeResult(False, "❌ Обмен не найден!")
                
                if trade.to_user_id != user_id:
                    return TradeResult(False, "❌ Это не твой обмен!")
                
                if trade.status != "pending":
                    return TradeResult(False, f"❌ Обмен уже {trade.status}!")
                
                # Return items to initiator
                offer_items = json.loads(trade.offer_items) if trade.offer_items else []
                for item in offer_items:
                    await inventory_service.add_item(
                        trade.from_user_id, trade.chat_id, item["item_type"], item["quantity"]
                    )
                
                trade.status = "rejected"
                trade.completed_at = utc_now()
                await session.commit()
        
        return TradeResult(True, "❌ Обмен отклонен!", trade_id)
    
    async def cancel_trade(self, trade_id: int, user_id: int) -> TradeResult:
        """Cancel own trade offer."""
        async_session = get_session()
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Trade).where(Trade.id == trade_id)
                )
                trade = result.scalars().first()
                
                if not trade:
                    return TradeResult(False, "❌ Обмен не найден!")
                
                if trade.from_user_id != user_id:
                    return TradeResult(False, "❌ Это не твой обмен!")
                
                if trade.status != "pending":
                    return TradeResult(False, f"❌ Обмен уже {trade.status}!")
                
                # Return items to initiator
                offer_items = json.loads(trade.offer_items) if trade.offer_items else []
                for item in offer_items:
                    await inventory_service.add_item(
                        trade.from_user_id, trade.chat_id, item["item_type"], item["quantity"]
                    )
                
                trade.status = "cancelled"
                trade.completed_at = utc_now()
                await session.commit()
        
        return TradeResult(True, "🚫 Обмен отменен!", trade_id)
    
    async def get_pending_trades(self, user_id: int, chat_id: int) -> List[Trade]:
        """Get all pending trades for a user."""
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(Trade).where(
                    and_(
                        Trade.chat_id == chat_id,
                        Trade.status == "pending",
                        (Trade.from_user_id == user_id) | (Trade.to_user_id == user_id)
                    )
                ).order_by(Trade.created_at.desc())
            )
            return list(result.scalars().all())
    
    async def expire_old_trades(self) -> int:
        """Expire old trades and return items. Returns count of expired trades."""
        async_session = get_session()
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Trade).where(
                        and_(
                            Trade.status == "pending",
                            Trade.expires_at < utc_now()
                        )
                    )
                )
                expired_trades = result.scalars().all()
                
                count = 0
                for trade in expired_trades:
                    # Return items to initiator
                    offer_items = json.loads(trade.offer_items) if trade.offer_items else []
                    for item in offer_items:
                        await inventory_service.add_item(
                            trade.from_user_id, trade.chat_id, item["item_type"], item["quantity"]
                        )
                    
                    trade.status = "expired"
                    trade.completed_at = utc_now()
                    count += 1
                
                await session.commit()
                return count


# Global instance
trade_service = TradeService()
