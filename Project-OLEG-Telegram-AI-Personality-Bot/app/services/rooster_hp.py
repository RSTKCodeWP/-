"""Rooster HP Management System.

Manages health points for roosters in cockfights.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from sqlalchemy import select

from app.database.session import get_session
from app.database.models import UserInventory

logger = logging.getLogger(__name__)

# Constants
MAX_HP = 100
MIN_HP_FOR_FIGHT = 10  # Decreased from 20
HP_REGEN_PER_HOUR = 20  # Increased from 5 (now regenerates fully in 5 hours)
FIGHT_HP_LOSS_MIN = 5   # Decreased from 10
FIGHT_HP_LOSS_MAX = 15  # Decreased from 30


async def get_rooster_hp(user_id: int, chat_id: int, rooster_type: str) -> Tuple[int, int]:
    """
    Get rooster's current HP and max HP.
    
    Args:
        user_id: Telegram user ID
        chat_id: Chat ID
        rooster_type: Type of rooster (rooster_common, rooster_rare, rooster_epic)
        
    Returns:
        Tuple of (current_hp, max_hp)
    """
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(UserInventory).where(
                UserInventory.user_id == user_id,
                UserInventory.chat_id == chat_id,
                UserInventory.item_type == rooster_type
            )
        )
        rooster = result.scalars().first()
        
        if not rooster:
            return (0, 0)
        
        # Parse metadata
        metadata = {}
        if rooster.item_data:
            try:
                metadata = json.loads(rooster.item_data)
            except json.JSONDecodeError:
                pass
        
        # Initialize HP if not set
        if "hp" not in metadata:
            metadata["hp"] = MAX_HP
            metadata["max_hp"] = MAX_HP
            metadata["last_regen"] = datetime.now(timezone.utc).isoformat()
            rooster.item_data = json.dumps(metadata)
            await session.commit()
            return (MAX_HP, MAX_HP)
        
        # Apply passive regeneration
        current_hp = metadata.get("hp", MAX_HP)
        max_hp = metadata.get("max_hp", MAX_HP)
        last_regen_str = metadata.get("last_regen")
        
        if last_regen_str and current_hp < max_hp:
            try:
                last_regen = datetime.fromisoformat(last_regen_str)
                if last_regen.tzinfo is None:
                    last_regen = last_regen.replace(tzinfo=timezone.utc)
                
                now = datetime.now(timezone.utc)
                hours_passed = (now - last_regen).total_seconds() / 3600
                
                if hours_passed >= 1:
                    regen_amount = int(hours_passed) * HP_REGEN_PER_HOUR
                    current_hp = min(max_hp, current_hp + regen_amount)
                    metadata["hp"] = current_hp
                    metadata["last_regen"] = now.isoformat()
                    rooster.item_data = json.dumps(metadata)
                    await session.commit()
                    logger.info(f"Rooster {rooster_type} regenerated {regen_amount} HP for user {user_id}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse last_regen: {e}")
        
        return (current_hp, max_hp)


async def set_rooster_hp(user_id: int, chat_id: int, rooster_type: str, new_hp: int) -> bool:
    """
    Set rooster's HP.
    
    Args:
        user_id: Telegram user ID
        chat_id: Chat ID
        rooster_type: Type of rooster
        new_hp: New HP value
        
    Returns:
        True if successful, False otherwise
    """
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(UserInventory).where(
                UserInventory.user_id == user_id,
                UserInventory.chat_id == chat_id,
                UserInventory.item_type == rooster_type
            )
        )
        rooster = result.scalars().first()
        
        if not rooster:
            return False
        
        # Parse metadata
        metadata = {}
        if rooster.item_data:
            try:
                metadata = json.loads(rooster.item_data)
            except json.JSONDecodeError:
                pass
        
        # Update HP
        max_hp = metadata.get("max_hp", MAX_HP)
        metadata["hp"] = max(0, min(max_hp, new_hp))
        metadata["max_hp"] = max_hp
        metadata["last_regen"] = datetime.now(timezone.utc).isoformat()
        
        rooster.item_data = json.dumps(metadata)
        await session.commit()
        
        logger.info(f"Set rooster {rooster_type} HP to {new_hp} for user {user_id}")
        return True


async def damage_rooster(user_id: int, chat_id: int, rooster_type: str, damage: int) -> Tuple[int, int]:
    """
    Apply damage to rooster.
    
    Args:
        user_id: Telegram user ID
        chat_id: Chat ID
        rooster_type: Type of rooster
        damage: Damage amount
        
    Returns:
        Tuple of (new_hp, max_hp)
    """
    current_hp, max_hp = await get_rooster_hp(user_id, chat_id, rooster_type)
    new_hp = max(0, current_hp - damage)
    await set_rooster_hp(user_id, chat_id, rooster_type, new_hp)
    return (new_hp, max_hp)


async def heal_rooster(user_id: int, chat_id: int, rooster_type: str, heal_amount: int) -> Tuple[int, int]:
    """
    Heal rooster.
    
    Args:
        user_id: Telegram user ID
        chat_id: Chat ID
        rooster_type: Type of rooster
        heal_amount: Amount to heal
        
    Returns:
        Tuple of (new_hp, max_hp)
    """
    current_hp, max_hp = await get_rooster_hp(user_id, chat_id, rooster_type)
    new_hp = min(max_hp, current_hp + heal_amount)
    await set_rooster_hp(user_id, chat_id, rooster_type, new_hp)
    return (new_hp, max_hp)


async def can_fight(user_id: int, chat_id: int, rooster_type: str) -> Tuple[bool, str]:
    """
    Check if rooster can fight.
    
    Args:
        user_id: Telegram user ID
        chat_id: Chat ID
        rooster_type: Type of rooster
        
    Returns:
        Tuple of (can_fight, reason)
    """
    current_hp, max_hp = await get_rooster_hp(user_id, chat_id, rooster_type)
    
    if current_hp < MIN_HP_FOR_FIGHT:
        return (False, f"❤️ HP петуха слишком низкое: {current_hp}/{max_hp}. Нужно минимум {MIN_HP_FOR_FIGHT} HP. Используй зелье лечения!")
    
    return (True, "")
