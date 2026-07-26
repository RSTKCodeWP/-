"""Market Service - Direct item sales marketplace.

v9.5 - Users can list items for sale at fixed prices.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.database.models import MarketListing
from app.services.inventory import inventory_service, ITEM_CATALOG
from app.services import wallet_service
from app.utils import utc_now

logger = logging.getLogger(__name__)


@dataclass
class MarketResult:
    """Result of market operation."""
    success: bool
    message: str
    listing_id: Optional[int] = None


class MarketService:
    """Service for managing marketplace listings."""
    
    async def create_listing(
        self,
        seller_user_id: int,
        chat_id: int,
        item_type: str,
        quantity: int,
        price: int
    ) -> MarketResult:
        """
        Create a new market listing.
        
        Args:
            seller_user_id: User creating the listing
            chat_id: Chat ID
            item_type: Type of item to sell
            quantity: Quantity to sell
            price: Sale price in coins
            
        Returns:
            MarketResult with success status
        """
        if price <= 0:
            return MarketResult(False, "❌ Цена должна быть больше 0!")
        
        if quantity <= 0:
            return MarketResult(False, "❌ Количество должно быть больше 0!")
        
        if item_type not in ITEM_CATALOG:
            return MarketResult(False, "❌ Неизвестный предмет!")
        
        async_session = get_session()
        async with async_session() as session:
            async with session.begin():
                # Check if user has the item
                user_item = await inventory_service.get_item(seller_user_id, chat_id, item_type)
                if not user_item or user_item.quantity < quantity:
                    item_info = ITEM_CATALOG[item_type]
                    return MarketResult(False, f"❌ У тебя недостаточно {item_info.emoji} {item_info.name}!")
                
                # Lock item (remove from inventory)
                result = await inventory_service.remove_item(seller_user_id, chat_id, item_type, quantity)
                if not result.success:
                    return MarketResult(False, result.message)
                
                # Create listing
                item_data = {
                    "item_type": item_type,
                    "quantity": quantity,
                    "item_name": user_item.item_name,
                    "item_data": user_item.item_data
                }
                
                listing = MarketListing(
                    seller_user_id=seller_user_id,
                    chat_id=chat_id,
                    item_data=json.dumps(item_data),
                    price=price,
                    status="active"
                )
                session.add(listing)
                await session.flush()
                
                listing_id = listing.id
        
        item_info = ITEM_CATALOG[item_type]
        return MarketResult(
            True, 
            f"✅ Выставлено на продажу: {item_info.emoji} {item_info.name} x{quantity} за {price} 🪙",
            listing_id
        )
    
    async def buy_listing(self, listing_id: int, buyer_user_id: int) -> MarketResult:
        """Purchase a market listing."""
        async_session = get_session()
        async with async_session() as session:
            async with session.begin():
                # Get listing
                result = await session.execute(
                    select(MarketListing).where(MarketListing.id == listing_id)
                )
                listing = result.scalars().first()
                
                if not listing:
                    return MarketResult(False, "❌ Объявление не найдено!")
                
                if listing.status != "active":
                    return MarketResult(False, "❌ Объявление уже неактивно!")
                
                if listing.seller_user_id == buyer_user_id:
                    return MarketResult(False, "❌ Нельзя купить свое объявление!")
                
                # Check buyer has enough coins
                balance = await wallet_service.get_balance(buyer_user_id)
                if balance < listing.price:
                    return MarketResult(False, f"❌ Недостаточно монет! (есть {balance}, нужно {listing.price})")
                
                # Execute purchase
                item_data = json.loads(listing.item_data)
                
                # 1. Transfer coins from buyer to seller
                transfer_result = await wallet_service.transfer(buyer_user_id, listing.seller_user_id, listing.price)
                if not transfer_result.success:
                    return MarketResult(False, transfer_result.message)
                
                # 2. Transfer item to buyer
                await inventory_service.add_item(
                    buyer_user_id, 
                    listing.chat_id, 
                    item_data["item_type"], 
                    item_data["quantity"]
                )
                
                # Mark listing as sold
                listing.status = "sold"
                listing.sold_at = utc_now()
                listing.buyer_user_id = buyer_user_id
                await session.commit()
        
        item_info = ITEM_CATALOG[item_data["item_type"]]
        return MarketResult(
            True, 
            f"✅ Куплено: {item_info.emoji} {item_info.name} x{item_data['quantity']} за {listing.price} 🪙!",
            listing_id
        )
    
    async def cancel_listing(self, listing_id: int, user_id: int) -> MarketResult:
        """Cancel own market listing."""
        async_session = get_session()
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(MarketListing).where(MarketListing.id == listing_id)
                )
                listing = result.scalars().first()
                
                if not listing:
                    return MarketResult(False, "❌ Объявление не найдено!")
                
                if listing.seller_user_id != user_id:
                    return MarketResult(False, "❌ Это не твое объявление!")
                
                if listing.status != "active":
                    return MarketResult(False, "❌ Объявление уже неактивно!")
                
                # Return item to seller
                item_data = json.loads(listing.item_data)
                await inventory_service.add_item(
                    listing.seller_user_id,
                    listing.chat_id,
                    item_data["item_type"],
                    item_data["quantity"]
                )
                
                listing.status = "cancelled"
                await session.commit()
        
        return MarketResult(True, "🚫 Объявление отменено!", listing_id)
    
    async def get_active_listings(self, chat_id: int, limit: int = 20, offset: int = 0) -> List[MarketListing]:
        """Get active market listings for a chat."""
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(MarketListing).where(
                    and_(
                        MarketListing.chat_id == chat_id,
                        MarketListing.status == "active"
                    )
                ).order_by(MarketListing.created_at.desc()).limit(limit).offset(offset)
            )
            return list(result.scalars().all())
    
    async def get_user_listings(self, user_id: int, chat_id: int) -> List[MarketListing]:
        """Get user's active listings."""
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(MarketListing).where(
                    and_(
                        MarketListing.seller_user_id == user_id,
                        MarketListing.chat_id == chat_id,
                        MarketListing.status == "active"
                    )
                ).order_by(MarketListing.created_at.desc())
            )
            return list(result.scalars().all())


# Global instance
market_service = MarketService()
