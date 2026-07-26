"""Auction Service - Bidding system for items.

v9.5 - Users can create auctions and bid on items.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.database.models import Auction, AuctionBid
from app.services.inventory import inventory_service, ITEM_CATALOG
from app.services import wallet_service
from app.utils import utc_now
from app.services.ollama_client import generate_text_reply
from aiogram import Bot
import random

logger = logging.getLogger(__name__)

# Constants
EVENT_CHANNEL_ID = -1002739723  # Steam Deck OC
EVENT_TOPIC_ID = 739723  # Games topic

SYSTEM_AUCTION_ITEMS = [
    {"type": "fishing_rod_golden", "name": "Золотая удочка", "emoji": "🎣", "base_price": 1000},
    {"type": "fishing_rod_legendary", "name": "Легендарная удочка", "emoji": "👑", "base_price": 5000},
    {"type": "rooster_rare", "name": "Боевой петух (Редкий)", "emoji": "🐓", "base_price": 800},
    {"type": "rooster_epic", "name": "Боевой петух (Эпик)", "emoji": "🦃", "base_price": 2000},
    {"type": "shield", "name": "Щит от кражи", "emoji": "🛡️", "base_price": 300},
    {"type": "lucky_charm", "name": "Талисман удачи", "emoji": "🍀", "base_price": 250},
    {"type": "energy_drink", "name": "Ящик энергетиков", "emoji": "⚡", "base_price": 400, "quantity": 5},
    {"type": "vip_status", "name": "VIP статус (7 дней)", "emoji": "💎", "base_price": 3000},
]


@dataclass
class AuctionResult:
    """Result of auction operation."""
    success: bool
    message: str
    auction_id: Optional[int] = None


class AuctionService:
    """Service for managing auctions."""
    
    MIN_BID_INCREMENT_PERCENT = 10  # Minimum 10% increase per bid
    MIN_DURATION_HOURS = 1
    MAX_DURATION_HOURS = 72
    
    async def create_system_auction(self, bot: Bot) -> None:
        """Create a random system auction (Black Market)."""
        logger.info("Generating system auction...")
        
        # 1. Select Random Item
        item_def = random.choice(SYSTEM_AUCTION_ITEMS)
        quantity = item_def.get("quantity", 1)
        start_price = int(item_def["base_price"] * random.uniform(0.8, 1.2)) # +/- 20% price variation
        duration = random.randint(4, 12) # 4 to 12 hours
        
        # 2. Generate Description via AI
        prompt = (
            f"Придумай короткое, смешное описание для лота на черном рынке: {item_def['emoji']} {item_def['name']} (x{quantity}). "
            f"Продавец - таинственный барыга Олег. Стиль: киберпанк/базар. "
            f"Не используй кавычки."
        )
        try:
            description = await generate_text_reply(
                user_text=prompt,
                username="system",
                chat_context=None,
                conversation_history=None
            )
        except Exception:
            description = "Товар высшего качества, мамой клянусь!"

        # 3. Create Auction Record
        async_session = get_session()
        async with async_session() as session:
            # Note: We skip inventory check for system (ID 0)
            item_data = {
                "item_type": item_def["type"],
                "quantity": quantity,
                "item_name": item_def["name"],
                "item_data": json.dumps({"is_system": True})
            }
            
            ends_at = utc_now() + timedelta(hours=duration)
            auction = Auction(
                seller_user_id=0, # System ID
                chat_id=EVENT_CHANNEL_ID,
                item_data=json.dumps(item_data),
                start_price=start_price,
                current_price=start_price,
                ends_at=ends_at,
                status="active"
            )
            session.add(auction)
            await session.commit()
            
            auction_id = auction.id
            
        # 4. Announce
        text = (
            f"🏴‍☠️ <b>ЧЁРНЫЙ РЫНОК ОТКРЫТ!</b>\n\n"
            f"{description}\n\n"
            f"📦 Лот: <b>{item_def['emoji']} {item_def['name']}</b> x{quantity}\n"
            f"💰 Начальная цена: <b>{start_price} монет</b>\n"
            f"⏳ До конца: {duration} ч.\n\n"
            f"👉 <i>Сделайте ставку командой:</i>\n"
            f"<code>/bid {auction_id} {start_price + 100}</code>"
        )
        
        try:
            await bot.send_message(
                chat_id=EVENT_CHANNEL_ID,
                message_thread_id=EVENT_TOPIC_ID,
                text=text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to announce system auction: {e}")

    async def create_auction(
        self,
        seller_user_id: int,
        chat_id: int,
        item_type: str,
        quantity: int,
        start_price: int,
        duration_hours: int
    ) -> AuctionResult:
        """
        Create a new auction.
        
        Args:
            seller_user_id: User creating the auction
            chat_id: Chat ID
            item_type: Type of item to auction
            quantity: Quantity to auction
            start_price: Starting bid price
            duration_hours: Auction duration in hours (1-72)
            
        Returns:
            AuctionResult with success status
        """
        if start_price <= 0:
            return AuctionResult(False, "❌ Стартовая цена должна быть больше 0!")
        
        if quantity <= 0:
            return AuctionResult(False, "❌ Количество должно быть больше 0!")
        
        if duration_hours < self.MIN_DURATION_HOURS or duration_hours > self.MAX_DURATION_HOURS:
            return AuctionResult(
                False, 
                f"❌ Длительность должна быть от {self.MIN_DURATION_HOURS} до {self.MAX_DURATION_HOURS} часов!"
            )
        
        if item_type not in ITEM_CATALOG:
            return AuctionResult(False, "❌ Неизвестный предмет!")
        
        async_session = get_session()
        async with async_session() as session:
            async with session.begin():
                # Check if user has the item
                user_item = await inventory_service.get_item(seller_user_id, chat_id, item_type)
                if not user_item or user_item.quantity < quantity:
                    item_info = ITEM_CATALOG[item_type]
                    return AuctionResult(False, f"❌ У тебя недостаточно {item_info.emoji} {item_info.name}!")
                
                # Lock item (remove from inventory)
                result = await inventory_service.remove_item(seller_user_id, chat_id, item_type, quantity)
                if not result.success:
                    return AuctionResult(False, result.message)
                
                # Create auction
                item_data = {
                    "item_type": item_type,
                    "quantity": quantity,
                    "item_name": user_item.item_name,
                    "item_data": user_item.item_data
                }
                
                ends_at = utc_now() + timedelta(hours=duration_hours)
                auction = Auction(
                    seller_user_id=seller_user_id,
                    chat_id=chat_id,
                    item_data=json.dumps(item_data),
                    start_price=start_price,
                    current_price=start_price,
                    ends_at=ends_at,
                    status="active"
                )
                session.add(auction)
                await session.flush()
                
                auction_id = auction.id
        
        item_info = ITEM_CATALOG[item_type]
        return AuctionResult(
            True,
            f"✅ Аукцион создан: {item_info.emoji} {item_info.name} x{quantity}, старт {start_price} 🪙, длится {duration_hours}ч",
            auction_id
        )
    
    async def place_bid(self, auction_id: int, bidder_user_id: int, amount: int) -> AuctionResult:
        """Place a bid on an auction."""
        async_session = get_session()
        async with async_session() as session:
            async with session.begin():
                # Get auction
                result = await session.execute(
                    select(Auction).where(Auction.id == auction_id)
                )
                auction = result.scalars().first()
                
                if not auction:
                    return AuctionResult(False, "❌ Аукцион не найден!")
                
                if auction.status != "active":
                    return AuctionResult(False, "❌ Аукцион уже завершен!")
                
                if utc_now() > auction.ends_at:
                    return AuctionResult(False, "❌ Аукцион уже закончился!")
                
                if auction.seller_user_id == bidder_user_id:
                    return AuctionResult(False, "❌ Нельзя ставить на свой аукцион!")
                
                # Calculate minimum bid
                min_bid = int(auction.current_price * (1 + self.MIN_BID_INCREMENT_PERCENT / 100))
                if amount < min_bid:
                    return AuctionResult(
                        False, 
                        f"❌ Минимальная ставка: {min_bid} 🪙 (текущая: {auction.current_price} 🪙)"
                    )
                
                # Check bidder has enough coins
                balance = await wallet_service.get_balance(bidder_user_id)
                if balance < amount:
                    return AuctionResult(False, f"❌ Недостаточно монет! (есть {balance}, нужно {amount})")
                
                # Create bid
                bid = AuctionBid(
                    auction_id=auction_id,
                    bidder_user_id=bidder_user_id,
                    amount=amount
                )
                session.add(bid)
                
                # Update auction current price
                auction.current_price = amount
                
                await session.commit()
        
        return AuctionResult(True, f"✅ Ставка {amount} 🪙 принята!", auction_id)
    
    async def cancel_auction(self, auction_id: int, user_id: int) -> AuctionResult:
        """Cancel own auction (only if no bids)."""
        async_session = get_session()
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Auction).where(Auction.id == auction_id)
                )
                auction = result.scalars().first()
                
                if not auction:
                    return AuctionResult(False, "❌ Аукцион не найден!")
                
                if auction.seller_user_id != user_id:
                    return AuctionResult(False, "❌ Это не твой аукцион!")
                
                if auction.status != "active":
                    return AuctionResult(False, "❌ Аукцион уже завершен!")
                
                # Check if there are any bids
                bid_result = await session.execute(
                    select(AuctionBid).where(AuctionBid.auction_id == auction_id).limit(1)
                )
                if bid_result.scalars().first():
                    return AuctionResult(False, "❌ Нельзя отменить аукцион с активными ставками!")
                
                # Return item to seller
                item_data = json.loads(auction.item_data)
                await inventory_service.add_item(
                    auction.seller_user_id,
                    auction.chat_id,
                    item_data["item_type"],
                    item_data["quantity"]
                )
                
                auction.status = "cancelled"
                auction.completed_at = utc_now()
                await session.commit()
        
        return AuctionResult(True, "🚫 Аукцион отменен!", auction_id)
    
    async def get_active_auctions(self, chat_id: int, limit: int = 20, offset: int = 0) -> List[Auction]:
        """Get active auctions for a chat."""
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(Auction).where(
                    and_(
                        Auction.chat_id == chat_id,
                        Auction.status == "active",
                        Auction.ends_at > utc_now()
                    )
                ).order_by(Auction.ends_at.asc()).limit(limit).offset(offset)
            )
            return list(result.scalars().all())
    
    async def get_user_auctions(self, user_id: int, chat_id: int) -> List[Auction]:
        """Get user's active auctions."""
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(Auction).where(
                    and_(
                        Auction.seller_user_id == user_id,
                        Auction.chat_id == chat_id,
                        Auction.status == "active"
                    )
                ).order_by(Auction.ends_at.asc())
            )
            return list(result.scalars().all())
    
    async def get_auction_bids(self, auction_id: int) -> List[AuctionBid]:
        """Get all bids for an auction."""
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(AuctionBid).where(
                    AuctionBid.auction_id == auction_id
                ).order_by(AuctionBid.amount.desc())
            )
            return list(result.scalars().all())
    
    async def complete_expired_auctions(self) -> int:
        """Complete expired auctions and transfer items. Returns count of completed auctions."""
        async_session = get_session()
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Auction).where(
                        and_(
                            Auction.status == "active",
                            Auction.ends_at < utc_now()
                        )
                    )
                )
                expired_auctions = result.scalars().all()
                
                count = 0
                for auction in expired_auctions:
                    # Get highest bid
                    bid_result = await session.execute(
                        select(AuctionBid).where(
                            AuctionBid.auction_id == auction.id
                        ).order_by(AuctionBid.amount.desc()).limit(1)
                    )
                    highest_bid = bid_result.scalars().first()
                    
                    if highest_bid:
                        # Transfer item to winner
                        item_data = json.loads(auction.item_data)
                        await inventory_service.add_item(
                            highest_bid.bidder_user_id,
                            auction.chat_id,
                            item_data["item_type"],
                            item_data["quantity"]
                        )
                        
                        # Transfer coins to seller
                        await wallet_service.transfer(
                            highest_bid.bidder_user_id,
                            auction.seller_user_id,
                            highest_bid.amount
                        )
                        
                        auction.winner_user_id = highest_bid.bidder_user_id
                    else:
                        # No bids, return item to seller
                        item_data = json.loads(auction.item_data)
                        await inventory_service.add_item(
                            auction.seller_user_id,
                            auction.chat_id,
                            item_data["item_type"],
                            item_data["quantity"]
                        )
                    
                    auction.status = "completed"
                    auction.completed_at = utc_now()
                    count += 1
                
                await session.commit()
                return count


# Global instance
auction_service = AuctionService()
