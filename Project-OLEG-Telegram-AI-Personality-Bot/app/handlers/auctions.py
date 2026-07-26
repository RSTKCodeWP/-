import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database.session import get_session
from app.database.models import User, Wallet, GameStat, Auction, AuctionBid
from app.handlers.games import ensure_user # Reusing ensure_user from games handler
from app.utils import utc_now

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("create_auction"))
async def cmd_create_auction(msg: Message):
    """
    Handles the /create_auction command to create an auction.
    Usage: /create_auction <item_type> <quantity> <start_price> <duration_hours>
    Example: /create_auction size_cm 10 50 24 (auctions 10 cm, starting at 50 coins, for 24 hours)
    """
    async_session = get_session()
    seller_user = await ensure_user(msg.from_user)

    parts = (msg.text or "").split()
    if len(parts) != 5:
        return await msg.reply("Использование: /create_auction <тип_предмета> <количество> <начальная_цена> <длительность_часы>")

    item_type = parts[1]
    try:
        quantity = int(parts[2])
        start_price = int(parts[3])
        duration_hours = int(parts[4])
    except ValueError:
        return await msg.reply("Количество, начальная цена и длительность должны быть числами.")

    if quantity <= 0 or start_price <= 0 or duration_hours <= 0:
        return await msg.reply("Все значения должны быть положительными числами.")

    ends_at = utc_now() + timedelta(hours=duration_hours)

    async with async_session() as session:
        # Check if seller has the item
        if item_type == "size_cm":
            game_stat_res = await session.execute(select(GameStat).filter_by(user_id=seller_user.id))
            game_stat = game_stat_res.scalars().first()
            if not game_stat or game_stat.size_cm < quantity:
                return await msg.reply(f"У вас недостаточно {item_type} для аукциона.")
        elif item_type == "balance":
            wallet_res = await session.execute(select(Wallet).filter_by(user_id=seller_user.id))
            wallet = wallet_res.scalars().first()
            if not wallet or wallet.balance < quantity:
                return await msg.reply(f"У вас недостаточно {item_type} для аукциона.")
        else:
            return await msg.reply(f"Неизвестный тип предмета: {item_type}.")
        
        # Create auction offer
        auction = Auction(
            seller_user_id=seller_user.id,
            item_type=item_type,
            item_quantity=quantity,
            start_price=start_price,
            ends_at=ends_at,
            status="active"
        )
        session.add(auction)
        await session.commit()
        await msg.reply(
            f"Аукцион создан: {quantity} {item_type} за {start_price} монет. "
            f"Завершится через {duration_hours} часов. (ID: {auction.id})"
        )


@router.message(Command("list_auctions"))
async def cmd_list_auctions(msg: Message):
    """
    Handles the /list_auctions command to list all active auctions.
    """
    async_session = get_session()
    async with async_session() as session:
        active_auctions_res = await session.execute(
            select(Auction)
            .filter(Auction.status == "active", Auction.ends_at > utc_now())
            .options(joinedload(Auction.seller), joinedload(Auction.current_highest_bid).joinedload(AuctionBid.bidder))
            .limit(10)
        )
        active_auctions = active_auctions_res.scalars().all()

        if not active_auctions:
            return await msg.reply("Активных аукционов нет.")

        auction_list = ["Активные аукционы:"]
        for auction in active_auctions:
            seller_name = auction.seller.username or str(auction.seller.tg_user_id)
            current_bid_info = ""
            if auction.current_highest_bid:
                bidder_name = auction.current_highest_bid.bidder.username or str(auction.current_highest_bid.bidder.tg_user_id)
                current_bid_info = f", Текущая ставка: {auction.current_highest_bid.amount} от {bidder_name}"
            
            auction_list.append(
                f"ID: {auction.id} | Продавец: {seller_name} | "
                f"Предмет: {auction.item_quantity} {auction.item_type} | "
                f"Нач. цена: {auction.start_price}{current_bid_info} | "
                f"Завершение: {auction.ends_at.strftime('%Y-%m-%d %H:%M')}"
            )
        await msg.reply("\n".join(auction_list))


@router.message(Command("bid"))
async def cmd_bid(msg: Message):
    """
    Handles the /bid command to place a bid on an auction.
    Usage: /bid <auction_id> <amount>
    """
    async_session = get_session()
    bidder_user = await ensure_user(msg.from_user)

    parts = (msg.text or "").split()
    if len(parts) != 3:
        return await msg.reply("Использование: /bid <ID_аукциона> <сумма>")
    
    try:
        auction_id = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        return await msg.reply("ID аукциона и сумма ставки должны быть числами.")

    if amount <= 0:
        return await msg.reply("Сумма ставки должна быть положительной.")

    async with async_session() as session:
        auction_res = await session.execute(
            select(Auction)
            .filter_by(id=auction_id, status="active")
            .options(joinedload(Auction.current_highest_bid))
        )
        auction = auction_res.scalars().first()

        if not auction:
            return await msg.reply("Аукцион не найден или уже неактивен.")
        
        if auction.seller_user_id == bidder_user.id:
            return await msg.reply("Нельзя делать ставки на свой собственный аукцион.")
        
        if auction.ends_at < utc_now():
            return await msg.reply("Аукцион уже завершен.")

        current_highest_bid_amount = auction.current_highest_bid.amount if auction.current_highest_bid else auction.start_price
        if amount <= current_highest_bid_amount:
            return await msg.reply(f"Ваша ставка ({amount}) должна быть выше текущей ({current_highest_bid_amount}).")

        # Check bidder's wallet
        bidder_wallet_res = await session.execute(select(Wallet).filter_by(user_id=bidder_user.id))
        bidder_wallet = bidder_wallet_res.scalars().first()
        if not bidder_wallet or bidder_wallet.balance < amount:
            return await msg.reply(f"У вас недостаточно средств ({bidder_wallet.balance}) для такой ставки ({amount}).")
        
        # If there was a previous highest bidder, refund their money
        if auction.current_highest_bid:
            previous_bidder_id = auction.current_highest_bid.bidder_user_id
            previous_bid_amount = auction.current_highest_bid.amount
            previous_bidder_wallet_res = await session.execute(select(Wallet).filter_by(user_id=previous_bidder_id))
            previous_bidder_wallet = previous_bidder_wallet_res.scalars().first()
            if previous_bidder_wallet:
                previous_bidder_wallet.balance += previous_bid_amount
                # Log this action or notify the user

        # Create new bid
        new_bid = AuctionBid(
            auction_id=auction.id,
            bidder_user_id=bidder_user.id,
            amount=amount
        )
        session.add(new_bid)
        await session.flush() # Flush to get the ID of the new bid
        
        auction.current_highest_bid_id = new_bid.id
        auction.current_highest_bid = new_bid # Update relationship object as well

        bidder_wallet.balance -= amount # Deduct bid amount from bidder

        await session.commit()
        await msg.reply(f"Ваша ставка {amount} на аукцион ID:{auction.id} принята. Вы стали ведущим.")

