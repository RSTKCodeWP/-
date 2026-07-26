"""
Marriage system handler.

Implements /marry, /divorce, /marriages commands for social interactions.
Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6
"""

import logging
from datetime import timedelta, timezone
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select, or_, and_

from app.database.session import get_session
from app.database.models import Marriage, MarriageProposal
from app.utils import utc_now

logger = logging.getLogger(__name__)

router = Router()

# Callback data prefixes
ACCEPT_PROPOSAL_PREFIX = "marry_accept:"
DECLINE_PROPOSAL_PREFIX = "marry_decline:"

# Proposal expiration time (5 minutes)
PROPOSAL_EXPIRATION_MINUTES = 5


def normalize_user_ids(user1_id: int, user2_id: int) -> tuple[int, int]:
    """
    Normalize user IDs so user1_id < user2_id.
    This ensures consistent storage in the Marriage table.
    
    **Validates: Requirements 9.2**
    """
    if user1_id < user2_id:
        return user1_id, user2_id
    return user2_id, user1_id


async def is_user_married(user_id: int, chat_id: int) -> bool:
    """
    Check if a user is currently married in a chat.
    
    **Validates: Requirements 9.4**
    
    Args:
        user_id: Telegram user ID
        chat_id: Chat ID
        
    Returns:
        True if user is married, False otherwise
    """
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(Marriage).where(
                Marriage.chat_id == chat_id,
                Marriage.divorced_at.is_(None),
                or_(
                    Marriage.user1_id == user_id,
                    Marriage.user2_id == user_id
                )
            )
        )
        return result.scalars().first() is not None


async def get_spouse_id(user_id: int, chat_id: int) -> int | None:
    """
    Get the spouse's user ID if the user is married.
    
    Args:
        user_id: Telegram user ID
        chat_id: Chat ID
        
    Returns:
        Spouse's user ID or None if not married
    """
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(Marriage).where(
                Marriage.chat_id == chat_id,
                Marriage.divorced_at.is_(None),
                or_(
                    Marriage.user1_id == user_id,
                    Marriage.user2_id == user_id
                )
            )
        )
        marriage = result.scalars().first()
        if marriage:
            return marriage.user2_id if marriage.user1_id == user_id else marriage.user1_id
        return None


async def has_pending_proposal(from_user_id: int, to_user_id: int, chat_id: int) -> bool:
    """
    Check if there's already a pending proposal between these users.
    
    **Validates: Requirements 9.4**
    
    Args:
        from_user_id: Proposer's user ID
        to_user_id: Target's user ID
        chat_id: Chat ID
        
    Returns:
        True if pending proposal exists, False otherwise
    """
    async_session = get_session()
    async with async_session() as session:
        # Get all pending proposals between these users
        result = await session.execute(
            select(MarriageProposal).where(
                MarriageProposal.chat_id == chat_id,
                MarriageProposal.status == "pending",
                or_(
                    and_(
                        MarriageProposal.from_user_id == from_user_id,
                        MarriageProposal.to_user_id == to_user_id
                    ),
                    and_(
                        MarriageProposal.from_user_id == to_user_id,
                        MarriageProposal.to_user_id == from_user_id
                    )
                )
            )
        )
        
        now = utc_now()
        for proposal in result.scalars():
            # Handle naive datetime from SQLite
            expires_at = proposal.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            if expires_at > now:
                return True  # Found valid non-expired proposal
            else:
                # Mark expired proposal
                proposal.status = "expired"
                await session.commit()
        
        return False


async def create_proposal(from_user_id: int, to_user_id: int, chat_id: int) -> MarriageProposal | None:
    """
    Create a new marriage proposal.
    
    **Validates: Requirements 9.1**
    
    Args:
        from_user_id: Proposer's user ID
        to_user_id: Target's user ID
        chat_id: Chat ID
        
    Returns:
        Created MarriageProposal object or None if pending proposal already exists
    """
    async_session = get_session()
    async with async_session() as session:
        now = utc_now()
        
        # Check for existing pending proposal (not expired)
        existing = await session.execute(
            select(MarriageProposal).where(
                MarriageProposal.from_user_id == from_user_id,
                MarriageProposal.to_user_id == to_user_id,
                MarriageProposal.chat_id == chat_id,
                MarriageProposal.status == "pending"
            )
        )
        existing_proposal = existing.scalars().first()
        if existing_proposal:
            # Check if it's expired
            expires_at = existing_proposal.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            if expires_at > now:
                return None  # Valid pending proposal exists
            else:
                # Mark as expired and continue to create new one
                existing_proposal.status = "expired"
        
        proposal = MarriageProposal(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            chat_id=chat_id,
            created_at=now,
            expires_at=now + timedelta(minutes=PROPOSAL_EXPIRATION_MINUTES),
            status="pending"
        )
        session.add(proposal)
        await session.commit()
        await session.refresh(proposal)
        return proposal


async def accept_proposal(proposal_id: int) -> Marriage | None:
    """
    Accept a marriage proposal and create the marriage.
    
    **Validates: Requirements 9.2**
    
    Args:
        proposal_id: Proposal ID
        
    Returns:
        Created Marriage object or None if failed
    """
    async_session = get_session()
    async with async_session() as session:
        # Get and update proposal
        result = await session.execute(
            select(MarriageProposal).where(MarriageProposal.id == proposal_id)
        )
        proposal = result.scalars().first()
        
        if not proposal or proposal.status != "pending":
            return None
        
        # Check if proposal expired
        expires_at = proposal.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < utc_now():
            proposal.status = "expired"
            await session.commit()
            return None
        
        # Check if either user is already married
        for user_id in [proposal.from_user_id, proposal.to_user_id]:
            check_result = await session.execute(
                select(Marriage).where(
                    Marriage.chat_id == proposal.chat_id,
                    Marriage.divorced_at.is_(None),
                    or_(
                        Marriage.user1_id == user_id,
                        Marriage.user2_id == user_id
                    )
                )
            )
            if check_result.scalars().first():
                proposal.status = "rejected"
                await session.commit()
                return None
        
        # Update proposal status
        proposal.status = "accepted"
        
        # Create marriage with normalized user IDs
        user1_id, user2_id = normalize_user_ids(proposal.from_user_id, proposal.to_user_id)
        marriage = Marriage(
            user1_id=user1_id,
            user2_id=user2_id,
            chat_id=proposal.chat_id,
            married_at=utc_now()
        )
        session.add(marriage)
        await session.commit()
        await session.refresh(marriage)
        
        return marriage


async def reject_proposal(proposal_id: int) -> bool:
    """
    Reject a marriage proposal.
    
    **Validates: Requirements 9.3**
    
    Args:
        proposal_id: Proposal ID
        
    Returns:
        True if rejected successfully, False otherwise
    """
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(MarriageProposal).where(MarriageProposal.id == proposal_id)
        )
        proposal = result.scalars().first()
        
        if not proposal or proposal.status != "pending":
            return False
        
        proposal.status = "rejected"
        await session.commit()
        return True


async def divorce(user_id: int, chat_id: int) -> bool:
    """
    Divorce the user from their spouse.
    
    **Validates: Requirements 9.5**
    
    Args:
        user_id: User requesting divorce
        chat_id: Chat ID
        
    Returns:
        True if divorced successfully, False otherwise
    """
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(Marriage).where(
                Marriage.chat_id == chat_id,
                Marriage.divorced_at.is_(None),
                or_(
                    Marriage.user1_id == user_id,
                    Marriage.user2_id == user_id
                )
            )
        )
        marriage = result.scalars().first()
        
        if not marriage:
            return False
        
        marriage.divorced_at = utc_now()
        await session.commit()
        return True


async def get_chat_marriages(chat_id: int) -> list[Marriage]:
    """
    Get all active marriages in a chat.
    
    Args:
        chat_id: Chat ID
        
    Returns:
        List of active Marriage objects
    """
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(Marriage).where(
                Marriage.chat_id == chat_id,
                Marriage.divorced_at.is_(None)
            ).order_by(Marriage.married_at.desc())
        )
        return list(result.scalars().all())


def create_proposal_keyboard(proposal_id: int) -> InlineKeyboardMarkup:
    """Create inline keyboard for proposal accept/decline."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💍 Принять",
                callback_data=f"{ACCEPT_PROPOSAL_PREFIX}{proposal_id}"
            ),
            InlineKeyboardButton(
                text="💔 Отклонить",
                callback_data=f"{DECLINE_PROPOSAL_PREFIX}{proposal_id}"
            )
        ]
    ])



@router.message(Command("marry"))
async def cmd_marry(msg: Message):
    """
    Command /marry [@user] - Propose marriage to another user.
    
    **Validates: Requirements 9.1, 9.4**
    
    Usage:
    - Reply to a message: /marry
    - Mention user: /marry @username
    """
    logger.info(f"[MARRY] Command received from {msg.from_user.id if msg.from_user else 'unknown'} in chat {msg.chat.id}")
    
    if not msg.from_user:
        logger.warning("[MARRY] No from_user, returning")
        return
    
    proposer_id = msg.from_user.id
    chat_id = msg.chat.id
    proposer_name = msg.from_user.username or msg.from_user.first_name
    
    # Get target user
    target_id = None
    target_name = None
    
    # Check if replying to a message
    if msg.reply_to_message and msg.reply_to_message.from_user:
        reply_user = msg.reply_to_message.from_user
        logger.info(f"[MARRY] Reply to user: {reply_user.id}, is_bot={reply_user.is_bot}")
        # Skip if replying to bot or self
        if not reply_user.is_bot and reply_user.id != proposer_id:
            target_id = reply_user.id
            target_name = reply_user.username or reply_user.first_name
    
    # Check for text_mention entities (when user is mentioned via @)
    if not target_id and msg.entities:
        for entity in msg.entities:
            if entity.type == "text_mention" and entity.user:
                if not entity.user.is_bot and entity.user.id != proposer_id:
                    target_id = entity.user.id
                    target_name = entity.user.username or entity.user.first_name
                    logger.info(f"[MARRY] Found text_mention: {target_id}")
                    break
            elif entity.type == "mention":
                # Extract username from text
                username = msg.text[entity.offset + 1:entity.offset + entity.length]  # skip @
                target_name = username
                logger.info(f"[MARRY] Found mention: @{username}, need to lookup user_id")
                # Try to find user in database by username
                from app.database.models import UserProfile
                async_session = get_session()
                async with async_session() as session:
                    result = await session.execute(
                        select(UserProfile).where(UserProfile.username == username)
                    )
                    user_profile = result.scalars().first()
                    if user_profile:
                        target_id = user_profile.user_id
                        logger.info(f"[MARRY] Found user_id from DB: {target_id}")
                break
    
    logger.info(f"[MARRY] target_id={target_id}, target_name={target_name}")
    
    if not target_id:
        if target_name:
            # Username was mentioned but user not found in DB
            await msg.reply(
                f"❌ Не могу найти @{target_name} в базе.\n\n"
                "Этот человек должен хотя бы раз написать в чат, чтобы я его запомнил.\n"
                "Или ответь на его сообщение командой /marry",
                parse_mode="HTML"
            )
        else:
            await msg.reply(
                "💍 <b>Как сделать предложение:</b>\n\n"
                "• Ответь на сообщение: /marry\n"
                "• Или упомяни: /marry @username\n\n"
                "<i>Человек должен хотя бы раз написать в чат</i>",
                parse_mode="HTML"
            )
        return
    
    # Check if proposer is already married
    # **Validates: Requirements 9.4**
    if await is_user_married(proposer_id, chat_id):
        spouse_id = await get_spouse_id(proposer_id, chat_id)
        await msg.reply(
            "💒 Ты уже в браке! Сначала разведись командой /divorce",
            parse_mode="HTML"
        )
        return
    
    # Check if target is already married
    # **Validates: Requirements 9.4**
    if await is_user_married(target_id, chat_id):
        await msg.reply(
            f"💔 @{target_name} уже в браке!",
            parse_mode="HTML"
        )
        return
    
    # Check for existing pending proposal
    # **Validates: Requirements 9.4**
    if await has_pending_proposal(proposer_id, target_id, chat_id):
        await msg.reply(
            "⏳ Предложение уже отправлено! Ожидай ответа.",
            parse_mode="HTML"
        )
        return
    
    # Create proposal
    proposal = await create_proposal(proposer_id, target_id, chat_id)
    
    # Handle race condition - proposal already exists
    if not proposal:
        await msg.reply(
            "⏳ Предложение уже отправлено! Ожидай ответа.",
            parse_mode="HTML"
        )
        return
    
    # Send proposal message
    await msg.reply(
        f"💍 <b>ПРЕДЛОЖЕНИЕ РУКИ И СЕРДЦА!</b>\n\n"
        f"@{proposer_name} делает предложение @{target_name}!\n\n"
        f"<i>У тебя есть {PROPOSAL_EXPIRATION_MINUTES} минут на ответ</i>",
        reply_markup=create_proposal_keyboard(proposal.id),
        parse_mode="HTML"
    )
    
    logger.info(f"Marriage proposal created: {proposer_id} -> {target_id} in chat {chat_id}")


@router.message(Command("divorce"))
async def cmd_divorce(msg: Message):
    """
    Command /divorce - Divorce from current spouse.
    
    **Validates: Requirements 9.5**
    """
    if not msg.from_user:
        return
    
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    user_name = msg.from_user.username or msg.from_user.first_name
    
    # Check if user is married
    if not await is_user_married(user_id, chat_id):
        await msg.reply(
            "💔 Ты не в браке! Некого разводить.",
            parse_mode="HTML"
        )
        return
    
    # Get spouse info before divorce
    spouse_id = await get_spouse_id(user_id, chat_id)
    
    # Process divorce
    if await divorce(user_id, chat_id):
        await msg.reply(
            f"💔 <b>РАЗВОД!</b>\n\n"
            f"@{user_name} подал(а) на развод.\n"
            f"Брак расторгнут. 😢",
            parse_mode="HTML"
        )
        logger.info(f"Divorce processed: {user_id} in chat {chat_id}")
    else:
        await msg.reply(
            "❌ Не удалось оформить развод. Попробуй позже.",
            parse_mode="HTML"
        )


@router.message(Command("marriages"))
async def cmd_marriages(msg: Message):
    """
    Command /marriages - Show all marriages in the chat.
    """
    if not msg.from_user:
        return
    
    chat_id = msg.chat.id
    
    marriages = await get_chat_marriages(chat_id)
    
    if not marriages:
        await msg.reply(
            "💔 В этом чате пока нет браков.\n\n"
            "Используй /marry чтобы сделать предложение!",
            parse_mode="HTML"
        )
        return
    
    lines = ["💒 <b>Браки в чате:</b>\n"]
    
    for i, marriage in enumerate(marriages, 1):
        days_married = (utc_now() - marriage.married_at).days
        lines.append(
            f"{i}. 💑 <code>{marriage.user1_id}</code> ❤️ <code>{marriage.user2_id}</code>\n"
            f"   📅 Вместе {days_married} дней"
        )
    
    await msg.reply("\n".join(lines), parse_mode="HTML")


@router.callback_query(F.data.startswith(ACCEPT_PROPOSAL_PREFIX))
async def callback_accept_proposal(callback: CallbackQuery):
    """
    Handle Accept button click for marriage proposal.
    
    **Validates: Requirements 9.2**
    """
    if not callback.data or not callback.from_user:
        return
    
    proposal_id = int(callback.data[len(ACCEPT_PROPOSAL_PREFIX):])
    acceptor_id = callback.from_user.id
    acceptor_name = callback.from_user.username or callback.from_user.first_name
    
    # Get proposal to verify acceptor
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(MarriageProposal).where(MarriageProposal.id == proposal_id)
        )
        proposal = result.scalars().first()
    
    if not proposal:
        await callback.answer("❌ Предложение не найдено", show_alert=True)
        return
    
    # Only target can accept
    if acceptor_id != proposal.to_user_id:
        await callback.answer("⚠️ Это предложение не для тебя!", show_alert=True)
        return
    
    # Check if proposal expired
    expires_at = proposal.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < utc_now():
        await callback.answer("⏰ Предложение истекло!", show_alert=True)
        if callback.message:
            await callback.message.edit_text(
                "⏰ <b>Предложение истекло</b>\n\n"
                "Время на ответ вышло.",
                parse_mode="HTML"
            )
        return
    
    # Accept proposal
    marriage = await accept_proposal(proposal_id)
    
    if not marriage:
        await callback.answer("❌ Не удалось принять предложение", show_alert=True)
        return
    
    # Update message
    if callback.message:
        await callback.message.edit_text(
            f"💒 <b>СВАДЬБА!</b>\n\n"
            f"🎉 @{acceptor_name} принял(а) предложение!\n\n"
            f"💍 Поздравляем молодожёнов! 🥂",
            parse_mode="HTML"
        )
    
    await callback.answer("💍 Поздравляем с браком!")
    logger.info(f"Marriage accepted: proposal {proposal_id}")


@router.callback_query(F.data.startswith(DECLINE_PROPOSAL_PREFIX))
async def callback_decline_proposal(callback: CallbackQuery):
    """
    Handle Decline button click for marriage proposal.
    
    **Validates: Requirements 9.3**
    """
    if not callback.data or not callback.from_user:
        return
    
    proposal_id = int(callback.data[len(DECLINE_PROPOSAL_PREFIX):])
    decliner_id = callback.from_user.id
    decliner_name = callback.from_user.username or callback.from_user.first_name
    
    # Get proposal to verify decliner
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(MarriageProposal).where(MarriageProposal.id == proposal_id)
        )
        proposal = result.scalars().first()
    
    if not proposal:
        await callback.answer("❌ Предложение не найдено", show_alert=True)
        return
    
    # Only target or proposer can decline
    if decliner_id not in [proposal.to_user_id, proposal.from_user_id]:
        await callback.answer("⚠️ Это предложение не для тебя!", show_alert=True)
        return
    
    # Reject proposal
    if await reject_proposal(proposal_id):
        if callback.message:
            if decliner_id == proposal.from_user_id:
                # Proposer cancelled
                await callback.message.edit_text(
                    f"💔 <b>Предложение отменено</b>\n\n"
                    f"@{decliner_name} передумал(а).",
                    parse_mode="HTML"
                )
            else:
                # Target rejected
                await callback.message.edit_text(
                    f"💔 <b>Предложение отклонено</b>\n\n"
                    f"@{decliner_name} сказал(а) нет. 😢",
                    parse_mode="HTML"
                )
        await callback.answer("💔 Предложение отклонено")
        logger.info(f"Marriage proposal declined: {proposal_id}")
    else:
        await callback.answer("❌ Не удалось отклонить предложение", show_alert=True)
