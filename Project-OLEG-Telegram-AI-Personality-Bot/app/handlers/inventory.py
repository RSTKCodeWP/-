"""Unified Inventory Handler - Central inventory management with inline buttons.

Version 7.6 - Unified inventory system for all items.
"""

import logging
import random
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select

from app.services.inventory import inventory_service, ITEM_CATALOG, ItemType, ItemInfo
from app.database.session import get_session
from app.database.models import GameStat

logger = logging.getLogger(__name__)
router = Router()


# ============================================================================
# Effect Result Data Classes
# ============================================================================

@dataclass
class EffectResult:
    """Result of applying an item effect."""
    success: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    # For PP cream: {"increase": 5, "new_size": 105}
    # For booster: {"effect": "luck_bonus", "duration": "1 game"}
    # For cage: {"active": True, "expires_in": "23h 59m"}


@dataclass
class LootboxOpenResult:
    """Result of opening a lootbox."""
    success: bool
    message: str
    items_received: list = field(default_factory=list)  # [(item_type, quantity), ...]
    coins_received: int = 0
    details: Dict[str, Any] = field(default_factory=dict)

# Callback prefix for inventory actions
INV_PREFIX = "inv:"

# Inventory categories for display
INVENTORY_CATEGORIES = {
    "rods": ("🎣 Удочки", [
        ItemType.BASIC_ROD, ItemType.SILVER_ROD, ItemType.GOLDEN_ROD, ItemType.LEGENDARY_ROD,
        ItemType.FISHING_ROD_BASIC, ItemType.FISHING_ROD_PRO, ItemType.FISHING_ROD_GOLDEN,
        "diamond_rod", "cosmic_rod"
    ]),
    "pp_items": ("🍆 Усиления", [
        ItemType.PP_CREAM_SMALL, ItemType.PP_CREAM_MEDIUM, 
        ItemType.PP_CREAM_LARGE, ItemType.PP_CREAM_TITAN, 
        ItemType.PP_CREAM_OMEGA, ItemType.PP_CAGE
    ]),
    "boosters": ("⚡ Бустеры", [
        ItemType.ENERGY_DRINK, ItemType.LUCKY_CHARM, ItemType.SHIELD, 
        ItemType.VIP_STATUS, ItemType.DOUBLE_XP, ItemType.DAMAGE_BOOST,
        ItemType.HEAL_POTION, ItemType.CRITICAL_BOOST, ItemType.COIN_MAGNET,
        ItemType.FISHING_BAIT, ItemType.GROW_ACCELERATOR
    ]),
    "lootboxes": ("📦 Лутбоксы", [
        ItemType.LOOTBOX_COMMON, ItemType.LOOTBOX_RARE, 
        ItemType.LOOTBOX_EPIC, ItemType.LOOTBOX_LEGENDARY,
        ItemType.LOOTBOX_MEGA, ItemType.LOOTBOX_MYSTERY
    ]),
    "roosters": ("🐔 Петухи", [
        ItemType.ROOSTER_COMMON, ItemType.ROOSTER_RARE, ItemType.ROOSTER_EPIC
    ]),
}


def get_item_category(item_type: str) -> str:
    """Get category for an item type."""
    for cat_id, (_, items) in INVENTORY_CATEGORIES.items():
        if item_type in [i.value if hasattr(i, 'value') else i for i in items]:
            return cat_id
    return "other"


def is_rod(item_type: str) -> bool:
    """Check if item is a fishing rod."""
    return item_type.endswith("_rod")


def is_lootbox(item_type: str) -> bool:
    """Check if item is a lootbox."""
    return item_type.startswith("lootbox_")


def is_pp_cream(item_type: str) -> bool:
    """Check if item is a PP cream."""
    return item_type.startswith("pp_cream_")


def is_pp_cage(item_type: str) -> bool:
    """Check if item is a PP cage."""
    return item_type == ItemType.PP_CAGE


def is_rooster(item_type: str) -> bool:
    """Check if item is a rooster."""
    return item_type.startswith("rooster_")


def is_booster(item_type: str) -> bool:
    """Check if item is a booster (energy drink, lucky charm, shield, heal potion, etc)."""
    return item_type in [
        ItemType.ENERGY_DRINK, ItemType.LUCKY_CHARM, ItemType.SHIELD,
        ItemType.VIP_STATUS, ItemType.DOUBLE_XP, ItemType.DAMAGE_BOOST,
        ItemType.HEAL_POTION, ItemType.CRITICAL_BOOST, ItemType.COIN_MAGNET,
        ItemType.FISHING_BAIT, ItemType.GROW_ACCELERATOR
    ]


# ============================================================================
# Booster Usage Functions
# ============================================================================

# Booster effect TTL in seconds (1 hour for most boosters)
BOOSTER_EFFECT_TTL = 3600


async def apply_booster(user_id: int, chat_id: int, item_type: str) -> EffectResult:
    """
    Apply booster effect based on item type.
    
    - Energy Drink: Resets fishing cooldown immediately
    - Lucky Charm: Sets +10% luck bonus for next game (stored in Redis)
    - Shield: Sets loss protection for next game (stored in Redis)
    
    Args:
        user_id: Telegram user ID
        chat_id: Chat ID
        item_type: Type of booster item
        
    Returns:
        EffectResult with success status and details
        
    Requirements: 4.1, 4.2, 4.3
    """
    from app.services.mini_games import fishing_game
    
    # Validate item type is a booster
    if not is_booster(item_type):
        return EffectResult(
            success=False,
            message="❌ Это не бустер!"
        )
    
    # Get item info from catalog
    item_info = ITEM_CATALOG.get(item_type)
    if not item_info:
        return EffectResult(
            success=False,
            message="❌ Неизвестный предмет"
        )
    
    # Check if user has the item
    if not await inventory_service.has_item(user_id, chat_id, item_type):
        return EffectResult(
            success=False,
            message=f"❌ У тебя нет {item_info.emoji} {item_info.name}!"
        )
    
    # Apply effect based on item type
    effect_result = None
    
    if item_type == ItemType.ENERGY_DRINK:
        from datetime import datetime, timezone, timedelta
        from app.database.models import GameStat
        from app.database.session import get_session
        from sqlalchemy import select
        
        # Check cooldown (10 minutes between energy drink uses)
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(GameStat).where(GameStat.tg_user_id == user_id)
            )
            game_stat = result.scalars().first()
            
            if game_stat and game_stat.last_energy_drink_use:
                now = datetime.now(timezone.utc)
                if game_stat.last_energy_drink_use.tzinfo is None:
                    last_use = game_stat.last_energy_drink_use.replace(tzinfo=timezone.utc)
                else:
                    last_use = game_stat.last_energy_drink_use
                
                cooldown_seconds = 600  # 10 minutes
                elapsed = (now - last_use).total_seconds()
                
                if elapsed < cooldown_seconds:
                    remaining = int(cooldown_seconds - elapsed)
                    minutes = remaining // 60
                    seconds = remaining % 60
                    return EffectResult(
                        success=False,
                        message=f"⏳ Подожди {minutes}м {seconds}с перед следующим энергетиком!",
                        details={"cooldown_remaining": remaining}
                    )
            
            # Update cooldown
            if game_stat:
                game_stat.last_energy_drink_use = datetime.now(timezone.utc)
                await session.commit()
        
        # Requirement 4.1: Reset fishing cooldown
        fishing_game.reset_cooldown(user_id)
        effect_result = EffectResult(
            success=True,
            message=f"🥤 Использован {item_info.emoji} {item_info.name}!\n\n"
                    f"⚡ Кулдаун рыбалки сброшен!\n"
                    f"Используй /fish",
            details={
                "effect": "reset_fishing_cooldown",
                "duration": "immediate"
            }
        )
    
    elif item_type == ItemType.LUCKY_CHARM:
        # Requirement 4.2: Set luck bonus for next game
        luck_bonus = item_info.effect.get("luck_bonus", 0.1)
        
        # Store luck bonus in Redis or memory
        await _set_booster_effect(user_id, chat_id, "luck_bonus", luck_bonus)
        
        effect_result = EffectResult(
            success=True,
            message=f"🍀 Использован {item_info.emoji} {item_info.name}!\n\n"
                    f"✨ +{int(luck_bonus * 100)}% к выигрышу в следующей игре!",
            details={
                "effect": "luck_bonus",
                "value": luck_bonus,
                "duration": "1 game"
            }
        )
    
    elif item_type == ItemType.SHIELD:
        # Requirement 4.3: Set loss protection for next game
        await _set_booster_effect(user_id, chat_id, "loss_protection", True)
        
        effect_result = EffectResult(
            success=True,
            message=f"🛡️ Использован {item_info.emoji} {item_info.name}!\n\n"
                    f"🛡️ Защита от проигрыша активирована!\n"
                    f"Следующий проигрыш не отнимет монеты.",
            details={
                "effect": "loss_protection",
                "value": True,
                "duration": "1 game"
            }
        )
    
    elif item_type == ItemType.VIP_STATUS:
        # VIP status: +20% to winnings for 24 hours
        duration_hours = item_info.effect.get("duration_hours", 24)
        win_bonus = item_info.effect.get("win_bonus", 0.2)
        
        await _set_booster_effect(
            user_id, chat_id, "vip_status", 
            {"win_bonus": win_bonus, "duration_hours": duration_hours},
            ttl=duration_hours * 3600
        )
        
        effect_result = EffectResult(
            success=True,
            message=f"👑 Использован {item_info.emoji} {item_info.name}!\n\n"
                    f"✨ +{int(win_bonus * 100)}% к выигрышам на {duration_hours} часов!",
            details={
                "effect": "vip_status",
                "win_bonus": win_bonus,
                "duration": f"{duration_hours} hours"
            }
        )
    
    elif item_type == ItemType.DOUBLE_XP:
        # Double XP for 1 hour
        duration_hours = item_info.effect.get("duration_hours", 1)
        xp_bonus = item_info.effect.get("xp_bonus", 2.0)
        
        await _set_booster_effect(
            user_id, chat_id, "double_xp",
            {"xp_bonus": xp_bonus, "duration_hours": duration_hours},
            ttl=duration_hours * 3600
        )
        
        effect_result = EffectResult(
            success=True,
            message=f"⚡ Использован {item_info.emoji} {item_info.name}!\n\n"
                    f"✨ x{xp_bonus} опыта на {duration_hours} час!",
            details={
                "effect": "double_xp",
                "xp_bonus": xp_bonus,
                "duration": f"{duration_hours} hours"
            }
        )
    
    elif item_type == ItemType.HEAL_POTION:
        # Heal rooster - show selection menu
        from app.services.rooster_hp import heal_rooster, get_rooster_hp
        from app.services.inventory import ItemType as InvItemType
        
        # Check which roosters user has
        roosters = []
        for rooster_type in [InvItemType.ROOSTER_COMMON, InvItemType.ROOSTER_RARE, InvItemType.ROOSTER_EPIC]:
            if await inventory_service.has_item(user_id, chat_id, rooster_type):
                current_hp, max_hp = await get_rooster_hp(user_id, chat_id, rooster_type)
                if current_hp < max_hp:
                    roosters.append((rooster_type, current_hp, max_hp))
        
        if not roosters:
            return EffectResult(
                success=False,
                message="❌ У тебя нет раненых петухов!"
            )
        
        # Heal first rooster (or implement selection menu)
        rooster_type, current_hp, max_hp = roosters[0]
        heal_amount = item_info.effect.get("heal_amount", 50)
        new_hp, max_hp = await heal_rooster(user_id, chat_id, rooster_type, heal_amount)
        
        rooster_info = ITEM_CATALOG.get(rooster_type)
        effect_result = EffectResult(
            success=True,
            message=f"🧪 Использовано {item_info.emoji} {item_info.name}!\n\n"
                    f"❤️ {rooster_info.emoji} {rooster_info.name} восстановил {heal_amount} HP!\n"
                    f"HP: {current_hp} → {new_hp}/{max_hp}",
            details={
                "effect": "heal_rooster",
                "rooster_type": rooster_type,
                "heal_amount": heal_amount,
                "new_hp": new_hp
            }
        )
    
    elif item_type in [ItemType.DAMAGE_BOOST, ItemType.CRITICAL_BOOST, ItemType.COIN_MAGNET, 
                       ItemType.FISHING_BAIT, ItemType.GROW_ACCELERATOR]:
        # Generic booster activation
        effect_name = item_type.replace("_", " ").title()
        duration = item_info.effect.get("duration_hours", item_info.effect.get("duration_minutes", 0) / 60)
        
        if duration > 0:
            ttl = int(duration * 3600)
            await _set_booster_effect(user_id, chat_id, item_type, item_info.effect, ttl=ttl)
            duration_text = f"{int(duration)}ч" if duration >= 1 else f"{int(duration * 60)}мин"
        else:
            await _set_booster_effect(user_id, chat_id, item_type, item_info.effect)
            duration_text = "1 использование"
        
        effect_result = EffectResult(
            success=True,
            message=f"✨ Использован {item_info.emoji} {item_info.name}!\n\n"
                    f"⚡ Эффект активирован на {duration_text}!",
            details={
                "effect": item_type,
                "duration": duration_text
            }
        )
    
    else:
        return EffectResult(
            success=False,
            message=f"❌ Неизвестный тип бустера: {item_type}"
        )
    
    # Remove item from inventory after successful use
    if effect_result and effect_result.success:
        remove_result = await inventory_service.remove_item(user_id, chat_id, item_type, 1)
        if not remove_result.success:
            return EffectResult(
                success=False,
                message=f"❌ Ошибка при использовании: {remove_result.message}"
            )
        
        logger.info(f"User {user_id} used booster {item_type} in chat {chat_id}")
    
    return effect_result


async def _set_booster_effect(
    user_id: int, 
    chat_id: int, 
    effect_type: str, 
    value: any,
    ttl: int = BOOSTER_EFFECT_TTL
) -> bool:
    """
    Store booster effect in Redis or memory.
    
    Args:
        user_id: Telegram user ID
        chat_id: Chat ID
        effect_type: Type of effect (luck_bonus, loss_protection, etc.)
        value: Effect value
        ttl: Time to live in seconds
        
    Returns:
        True if stored successfully
    """
    import json
    
    # Try to use Redis if available
    try:
        from app.services.redis_client import redis_client
        if redis_client and redis_client.is_available:
            key = f"booster:{effect_type}:{user_id}:{chat_id}"
            data = json.dumps({"value": value, "user_id": user_id, "chat_id": chat_id})
            await redis_client.set(key, data, ex=ttl)
            logger.debug(f"Stored booster effect {effect_type} for user {user_id} in Redis")
            return True
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Failed to store booster effect in Redis: {e}")
    
    # Fallback: store in memory (will be lost on restart)
    # This is acceptable for short-lived booster effects
    if not hasattr(_set_booster_effect, '_memory_store'):
        _set_booster_effect._memory_store = {}
    
    key = f"booster:{effect_type}:{user_id}:{chat_id}"
    _set_booster_effect._memory_store[key] = {"value": value, "user_id": user_id, "chat_id": chat_id}
    logger.debug(f"Stored booster effect {effect_type} for user {user_id} in memory")
    return True


async def get_booster_effect(user_id: int, chat_id: int, effect_type: str) -> any:
    """
    Get active booster effect for user.
    
    Args:
        user_id: Telegram user ID
        chat_id: Chat ID
        effect_type: Type of effect to check
        
    Returns:
        Effect value if active, None otherwise
    """
    import json
    
    key = f"booster:{effect_type}:{user_id}:{chat_id}"
    
    # Try Redis first
    try:
        from app.services.redis_client import redis_client
        if redis_client and redis_client.is_available:
            data = await redis_client.get(key)
            if data:
                parsed = json.loads(data)
                return parsed.get("value")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Failed to get booster effect from Redis: {e}")
    
    # Fallback to memory
    if hasattr(_set_booster_effect, '_memory_store'):
        stored = _set_booster_effect._memory_store.get(key)
        if stored:
            return stored.get("value")
    
    return None


async def consume_booster_effect(user_id: int, chat_id: int, effect_type: str) -> any:
    """
    Get and consume (remove) a booster effect.
    
    Used for one-time effects like luck_bonus and loss_protection.
    
    Args:
        user_id: Telegram user ID
        chat_id: Chat ID
        effect_type: Type of effect to consume
        
    Returns:
        Effect value if was active, None otherwise
    """
    import json
    
    key = f"booster:{effect_type}:{user_id}:{chat_id}"
    value = None
    
    # Try Redis first
    try:
        from app.services.redis_client import redis_client
        if redis_client and redis_client.is_available:
            data = await redis_client.get(key)
            if data:
                parsed = json.loads(data)
                value = parsed.get("value")
                await redis_client.delete(key)
                logger.debug(f"Consumed booster effect {effect_type} for user {user_id} from Redis")
                return value
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Failed to consume booster effect from Redis: {e}")
    
    # Fallback to memory
    if hasattr(_set_booster_effect, '_memory_store'):
        stored = _set_booster_effect._memory_store.pop(key, None)
        if stored:
            value = stored.get("value")
            logger.debug(f"Consumed booster effect {effect_type} for user {user_id} from memory")
    
    return value


# ============================================================================
# Rod Equipping Functions
# ============================================================================

async def equip_rod(user_id: int, chat_id: int, item_type: str) -> EffectResult:
    """
    Equip a fishing rod.
    
    Uses existing inventory_service.equip_item() to handle the equipping logic,
    which automatically unequips any currently equipped rod.
    Also updates fishing_stats_service to track the equipped rod.
    
    Args:
        user_id: Telegram user ID
        chat_id: Chat ID
        item_type: Type of rod to equip
        
    Returns:
        EffectResult with success status and details
        
    Requirements: 5.1
    """
    from app.services.fishing_stats import fishing_stats_service
    
    # Validate item type is a rod
    if not is_rod(item_type):
        return EffectResult(
            success=False,
            message="❌ Это не удочка!"
        )
    
    # Get item info from catalog
    item_info = ITEM_CATALOG.get(item_type)
    if not item_info:
        return EffectResult(
            success=False,
            message="❌ Неизвестный предмет"
        )
    
    # Check if user has the rod
    if not await inventory_service.has_item(user_id, chat_id, item_type):
        return EffectResult(
            success=False,
            message=f"❌ У тебя нет {item_info.emoji} {item_info.name}!"
        )
    
    # Equip the rod using inventory service
    # This automatically unequips any currently equipped rod
    result = await inventory_service.equip_item(user_id, chat_id, item_type)
    
    if not result.success:
        return EffectResult(
            success=False,
            message=result.message
        )
    
    # Update fishing stats service with the new equipped rod
    await fishing_stats_service.update_equipped_rod(user_id, chat_id, item_type)
    
    # Get rod bonus for display
    rod_bonus = item_info.effect.get("rod_bonus", 0)
    bonus_text = f"+{int(rod_bonus * 100)}% к редким рыбам" if rod_bonus > 0 else ""
    
    logger.info(f"User {user_id} equipped rod {item_type} in chat {chat_id}")
    
    return EffectResult(
        success=True,
        message=f"🎣 Экипирована {item_info.emoji} {item_info.name}!\n\n"
                f"{bonus_text}" if bonus_text else f"🎣 Экипирована {item_info.emoji} {item_info.name}!",
        details={
            "item_type": item_type,
            "rod_bonus": rod_bonus,
            "item_name": item_info.name
        }
    )


# ============================================================================
# Lootbox Opening Functions
# ============================================================================

async def open_lootbox(user_id: int, chat_id: int, item_type: str) -> LootboxOpenResult:
    """
    Open a lootbox and add generated items to inventory.
    
    Uses existing lootbox_engine from mini_games to generate rewards.
    Adds generated items to inventory and awards coins.
    
    Args:
        user_id: Telegram user ID
        chat_id: Chat ID
        item_type: Type of lootbox to open (lootbox_common, lootbox_rare, etc.)
        
    Returns:
        LootboxOpenResult with success status, items received, and coins
        
    Requirements: 6.1, 6.2, 6.3
    """
    from app.services.mini_games import lootbox_engine
    from app.services import wallet_service
    
    # Validate item type is a lootbox
    if not is_lootbox(item_type):
        return LootboxOpenResult(
            success=False,
            message="❌ Это не лутбокс!"
        )
    
    # Get item info from catalog
    item_info = ITEM_CATALOG.get(item_type)
    if not item_info:
        return LootboxOpenResult(
            success=False,
            message="❌ Неизвестный предмет"
        )
    
    # Check if user has the lootbox
    if not await inventory_service.has_item(user_id, chat_id, item_type):
        return LootboxOpenResult(
            success=False,
            message=f"❌ У тебя нет {item_info.emoji} {item_info.name}!"
        )
    
    # Remove lootbox from inventory first
    remove_result = await inventory_service.remove_item(user_id, chat_id, item_type, 1)
    if not remove_result.success:
        return LootboxOpenResult(
            success=False,
            message=f"❌ Ошибка при открытии: {remove_result.message}"
        )
    
    # Extract lootbox tier from item_type (e.g., "lootbox_common" -> "common")
    lootbox_tier = item_type.replace("lootbox_", "")
    
    # Open lootbox using the engine
    result = lootbox_engine.open(lootbox_tier)
    
    if not result.success:
        # Restore lootbox if opening failed
        await inventory_service.add_item(user_id, chat_id, item_type)
        return LootboxOpenResult(
            success=False,
            message=f"❌ Ошибка при открытии: {result.message}"
        )
    
    # Add coins from lootbox
    coins_received = result.total_coins
    if coins_received > 0:
        await wallet_service.add(user_id, coins_received, reason="lootbox reward")
    
    # Add items to inventory
    items_received = []
    items_added_text = []
    
    for item_type_received in result.items:
        if item_type_received:
            add_result = await inventory_service.add_item(user_id, chat_id, item_type_received)
            if add_result.success and add_result.item:
                items_received.append((item_type_received, 1))
                items_added_text.append(f"  {add_result.item.emoji} {add_result.item.name}")
    
    # Build result message with emojis
    message_parts = [f"📦 Открываем {item_info.emoji} {item_info.name}...\n"]
    message_parts.append(result.message)
    
    if items_added_text:
        message_parts.append(f"\n\n🎁 Добавлено в инвентарь:")
        message_parts.extend([f"\n{item}" for item in items_added_text])
    
    logger.info(f"User {user_id} opened lootbox {item_type} in chat {chat_id}: "
                f"{coins_received} coins, {len(items_received)} items")
    
    return LootboxOpenResult(
        success=True,
        message="\n".join(message_parts),
        items_received=items_received,
        coins_received=coins_received,
        details={
            "lootbox_type": item_type,
            "lootbox_tier": lootbox_tier,
            "rewards": [{"name": r.name, "emoji": r.emoji, "coins": r.coins, "item_type": r.item_type} 
                       for r in result.rewards]
        }
    )


# ============================================================================
# PP Cream Usage Functions
# ============================================================================

async def toggle_cage(user_id: int, chat_id: int, activate: bool) -> EffectResult:
    """
    Toggle PP Cage activation state.
    
    Uses existing inventory_service.activate_item() and deactivate_item().
    Shows remaining time for active cage.
    
    Args:
        user_id: Telegram user ID
        chat_id: Chat ID
        activate: True to activate, False to deactivate
        
    Returns:
        EffectResult with success status and details
        
    Requirements: 3.1, 3.2, 3.3
    """
    import json
    from datetime import datetime, timezone
    
    item_type = ItemType.PP_CAGE
    item_info = ITEM_CATALOG.get(item_type)
    
    if not item_info:
        return EffectResult(
            success=False,
            message="❌ Неизвестный предмет"
        )
    
    # Check if user has the cage
    has_cage = await inventory_service.has_item(user_id, chat_id, item_type)
    is_active = await inventory_service.has_active_item(user_id, chat_id, item_type)
    
    if activate:
        # Activate cage - Requirement 3.1, 3.2
        if not has_cage:
            return EffectResult(
                success=False,
                message=f"❌ У тебя нет {item_info.emoji} {item_info.name}!\n"
                        f"Купи в /shop в разделе 'Защита достоинства'",
                details={"error": "no_item"}
            )
        
        if is_active:
            # Get remaining time
            item = await inventory_service.get_item(user_id, chat_id, item_type)
            remaining_text = ""
            if item and item.item_data:
                try:
                    data = json.loads(item.item_data)
                    expires_at_str = data.get("expires_at")
                    if expires_at_str:
                        expires_at = datetime.fromisoformat(expires_at_str)
                        if expires_at.tzinfo is None:
                            expires_at = expires_at.replace(tzinfo=timezone.utc)
                        now = datetime.now(timezone.utc)
                        if now < expires_at:
                            remaining = expires_at - now
                            hours = int(remaining.total_seconds() // 3600)
                            minutes = int((remaining.total_seconds() % 3600) // 60)
                            remaining_text = f"Осталось: {hours}ч {minutes}м"
                except (json.JSONDecodeError, ValueError):
                    pass
            
            return EffectResult(
                success=False,
                message=f"⚠️ {item_info.emoji} {item_info.name} уже активна!\n{remaining_text}",
                details={"error": "already_active", "remaining": remaining_text}
            )
        
        # Activate the cage
        result = await inventory_service.activate_item(user_id, chat_id, item_type)
        
        if result.success:
            # Get expiration info for response
            item = await inventory_service.get_item(user_id, chat_id, item_type)
            expires_in = "24ч"
            if item and item.item_data:
                try:
                    data = json.loads(item.item_data)
                    expires_at_str = data.get("expires_at")
                    if expires_at_str:
                        expires_at = datetime.fromisoformat(expires_at_str)
                        if expires_at.tzinfo is None:
                            expires_at = expires_at.replace(tzinfo=timezone.utc)
                        now = datetime.now(timezone.utc)
                        remaining = expires_at - now
                        hours = int(remaining.total_seconds() // 3600)
                        minutes = int((remaining.total_seconds() % 3600) // 60)
                        expires_in = f"{hours}ч {minutes}м"
                except (json.JSONDecodeError, ValueError):
                    pass
            
            return EffectResult(
                success=True,
                message=f"🔒 {item_info.emoji} {item_info.name} активирована!\n\n"
                        f"⏰ Действует: {expires_in}\n\n"
                        f"⚠️ Пока клетка активна:\n"
                        f"  • Член защищён от потерь в PvP\n"
                        f"  • Мази заблокированы\n\n"
                        f"Сними через инвентарь когда захочешь",
                details={"active": True, "expires_in": expires_in}
            )
        else:
            return EffectResult(
                success=False,
                message=result.message,
                details={"error": "activation_failed"}
            )
    
    else:
        # Deactivate cage - Requirement 3.3
        if not is_active:
            return EffectResult(
                success=False,
                message=f"❌ {item_info.emoji} {item_info.name} не активна!",
                details={"error": "not_active"}
            )
        
        result = await inventory_service.deactivate_item(user_id, chat_id, item_type)
        
        if result.success:
            return EffectResult(
                success=True,
                message=f"🔓 {item_info.emoji} {item_info.name} снята!\n\n"
                        f"✅ Теперь можно использовать мази\n"
                        f"⚠️ Член больше не защищён от потерь",
                details={"active": False}
            )
        else:
            return EffectResult(
                success=False,
                message=result.message,
                details={"error": "deactivation_failed"}
            )


async def apply_pp_cream(user_id: int, chat_id: int, item_type: str) -> EffectResult:
    """
    Apply PP cream effect to increase user's PP size.
    
    Gets cream effect range from ITEM_CATALOG, generates random increase within range,
    updates GameStat.size_cm, and removes item from inventory.
    
    Args:
        user_id: Telegram user ID
        chat_id: Chat ID
        item_type: Type of PP cream item
        
    Returns:
        EffectResult with success status and details
        
    Requirements: 2.1, 2.2, 2.3
    """
    from datetime import datetime, timezone, timedelta
    
    # Validate item type is a PP cream
    if not is_pp_cream(item_type):
        return EffectResult(
            success=False,
            message="❌ Это не мазь для члена!"
        )
    
    # Get item info from catalog
    item_info = ITEM_CATALOG.get(item_type)
    if not item_info:
        return EffectResult(
            success=False,
            message="❌ Неизвестный предмет"
        )
    
    # Check if user has the item
    if not await inventory_service.has_item(user_id, chat_id, item_type):
        return EffectResult(
            success=False,
            message=f"❌ У тебя нет {item_info.emoji} {item_info.name}!"
        )
    
    # Check for active PP Cage (blocks cream usage) - Requirement 2.3
    if await inventory_service.has_active_item(user_id, chat_id, ItemType.PP_CAGE):
        return EffectResult(
            success=False,
            message="🔒 Клетка не даёт использовать мази! Сними через инвентарь.",
            details={"blocked_by": "pp_cage"}
        )
    
    # Check cooldown (5 minutes between cream uses)
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(GameStat).where(GameStat.tg_user_id == user_id)
        )
        game_stat = result.scalars().first()
        
        if not game_stat:
            return EffectResult(
                success=False,
                message="❌ Сначала используй /grow чтобы создать профиль!"
            )
        
        # Check last cream use
        if game_stat.last_cream_use:
            now = datetime.now(timezone.utc)
            if game_stat.last_cream_use.tzinfo is None:
                last_use = game_stat.last_cream_use.replace(tzinfo=timezone.utc)
            else:
                last_use = game_stat.last_cream_use
            
            cooldown_seconds = 300  # 5 minutes
            elapsed = (now - last_use).total_seconds()
            
            if elapsed < cooldown_seconds:
                remaining = int(cooldown_seconds - elapsed)
                minutes = remaining // 60
                seconds = remaining % 60
                return EffectResult(
                    success=False,
                    message=f"⏳ Подожди {minutes}м {seconds}с перед следующим использованием мази!",
                    details={"cooldown_remaining": remaining}
                )
        
        # Get effect range from item catalog
        pp_boost_min = item_info.effect.get("pp_boost_min", 1)
        pp_boost_max = item_info.effect.get("pp_boost_max", 3)
        min_cm = item_info.effect.get("min_cm", 1)
        max_cm = item_info.effect.get("max_cm", 30)
        
        # Calculate percentage-based increase
        current_size = max(1, game_stat.size_cm)
        percent = random.uniform(pp_boost_min, pp_boost_max)
        increase = int(current_size * percent / 100)
        
        # Apply min/max bounds
        increase = max(min_cm, min(max_cm, increase))
        
        old_size = game_stat.size_cm
        game_stat.size_cm = old_size + increase
        game_stat.last_cream_use = datetime.now(timezone.utc)
        new_size = game_stat.size_cm
        
        await session.commit()
    
    # Remove item from inventory
    remove_result = await inventory_service.remove_item(user_id, chat_id, item_type, 1)
    if not remove_result.success:
        # Rollback size change if item removal failed
        async with async_session() as session:
            result = await session.execute(
                select(GameStat).where(GameStat.tg_user_id == user_id)
            )
            game_stat = result.scalars().first()
            if game_stat:
                game_stat.size_cm = old_size
                game_stat.last_cream_use = None
                await session.commit()
        
        return EffectResult(
            success=False,
            message=f"❌ Ошибка при использовании: {remove_result.message}"
        )
    
    # Check for grow_boost effect (Omega cream special)
    grow_boost = item_info.effect.get("grow_boost")
    boost_message = ""
    if grow_boost:
        await _set_booster_effect(user_id, chat_id, "grow_boost", grow_boost, ttl=86400)  # 24h
        boost_message = f"\n\n⚡ <b>БОНУС:</b> x{grow_boost} к следующему /grow!"
    
    # Success! Return result with details - Requirement 2.2
    return EffectResult(
        success=True,
        message=f"🧴 Ты использовал {item_info.emoji} {item_info.name}!\n\n"
                f"📈 Твой писюн вырос на +{increase} см!\n"
                f"📏 Новый размер: {new_size} см{boost_message}",
        details={
            "increase": increase,
            "old_size": old_size,
            "new_size": new_size,
            "item_type": item_type,
            "pp_boost_min": pp_boost_min,
            "pp_boost_max": pp_boost_max,
            "grow_boost": grow_boost
        }
    )


async def build_inventory_text(user_id: int, chat_id: int) -> str:
    """Build inventory display text grouped by categories."""
    items = await inventory_service.get_inventory(user_id, chat_id)
    
    if not items:
        return (
            "🎒 <b>ИНВЕНТАРЬ</b>\n\n"
            "📭 Пусто! Загляни в /shop чтобы купить предметы."
        )
    
    # Filter out zero-quantity items
    items = [item for item in items if item.quantity > 0]
    
    if not items:
        return (
            "🎒 <b>ИНВЕНТАРЬ</b>\n\n"
            "📭 Пусто! Загляни в /shop чтобы купить предметы."
        )
    
    # Group items by category
    categorized = {cat_id: [] for cat_id in INVENTORY_CATEGORIES}
    categorized["other"] = []
    
    for item in items:
        cat = get_item_category(item.item_type)
        categorized[cat].append(item)
    
    # Build text
    text_parts = ["🎒 <b>ИНВЕНТАРЬ</b>\n"]
    
    for cat_id, (cat_name, _) in INVENTORY_CATEGORIES.items():
        cat_items = categorized.get(cat_id, [])
        if not cat_items:
            continue
        
        text_parts.append(f"\n{cat_name}:")
        for item in cat_items:
            item_info = ITEM_CATALOG.get(item.item_type)
            if not item_info:
                continue
            
            emoji = item_info.emoji
            name = item_info.name
            qty = item.quantity
            
            # Show equipped status and bonus for rods
            equipped_mark = ""
            if is_rod(item.item_type):
                bonus = item_info.effect.get("rod_bonus", 0)
                bonus_str = f" (+{int(bonus * 100)}%)" if bonus > 0 else ""
                if item.equipped:
                    equipped_mark = f" ✅{bonus_str}"
                else:
                    equipped_mark = bonus_str
            
            # Show active status for PP cage
            if is_pp_cage(item.item_type) and item.equipped:
                equipped_mark = " 🔒 активна"
            
            # Format quantity
            qty_str = f" x{qty}" if qty > 1 else ""
            
            text_parts.append(f"  {emoji} {name}{qty_str}{equipped_mark}")
    
    # Other items
    other_items = categorized.get("other", [])
    if other_items:
        text_parts.append("\n📦 Прочее:")
        for item in other_items:
            item_info = ITEM_CATALOG.get(item.item_type)
            if item_info:
                qty_str = f" x{item.quantity}" if item.quantity > 1 else ""
                text_parts.append(f"  {item_info.emoji} {item_info.name}{qty_str}")
    
    text_parts.append("\n\n<i>Нажми на предмет для действия</i>")
    
    return "\n".join(text_parts)


async def build_inventory_keyboard(user_id: int, chat_id: int) -> InlineKeyboardMarkup:
    """Build inline keyboard with action buttons for inventory items."""
    items = await inventory_service.get_inventory(user_id, chat_id)
    
    # Filter out zero-quantity items
    items = [item for item in items if item.quantity > 0]
    
    buttons = []
    
    for item in items:
        item_info = ITEM_CATALOG.get(item.item_type)
        if not item_info:
            continue
        
        item_type = item.item_type
        
        # Determine action based on item type
        if is_rod(item_type):
            # Equip button for rods
            if item.equipped:
                btn_text = f"✅ {item_info.emoji} {item_info.name}"
                action = "equipped"  # Already equipped, no action
                callback_data = None
            else:
                btn_text = f"🎣 Экипировать {item_info.name}"
                callback_data = f"{INV_PREFIX}{user_id}:equip:{item_type}"
        elif is_lootbox(item_type):
            # Open button for lootboxes
            btn_text = f"📦 Открыть {item_info.name}"
            callback_data = f"{INV_PREFIX}{user_id}:open:{item_type}"
        elif is_pp_cage(item_type):
            # Activate/Deactivate for PP cage
            if item.equipped:
                btn_text = f"🔓 Снять {item_info.name}"
                callback_data = f"{INV_PREFIX}{user_id}:cage:off"
            else:
                btn_text = f"🔒 Надеть {item_info.name}"
                callback_data = f"{INV_PREFIX}{user_id}:cage:on"
        elif is_rooster(item_type):
            # Roosters don't have inventory actions - used in /cockfight
            # Show HP status
            from app.services.rooster_hp import get_rooster_hp
            current_hp, max_hp = await get_rooster_hp(user_id, chat_id, item_type)
            btn_text = f"{item_info.emoji} {item_info.name} (x{item.quantity}) ❤️ {current_hp}/{max_hp}"
            callback_data = f"{INV_PREFIX}{user_id}:rooster:{item_type}"  # Dummy callback for display
        else:
            # Use button for consumables (creams, boosters)
            btn_text = f"✨ Использовать {item_info.name}"
            callback_data = f"{INV_PREFIX}{user_id}:use:{item_type}"
        
        # Add button (skip only equipped rods)
        if callback_data is None:
            continue
        
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=callback_data)])
    
    # Add refresh and close buttons
    buttons.append([
        InlineKeyboardButton(text="🔄 Обновить", callback_data=f"{INV_PREFIX}{user_id}:refresh"),
        InlineKeyboardButton(text="❌ Закрыть", callback_data=f"{INV_PREFIX}{user_id}:close"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("inventory", "inv", "i"))
async def cmd_inventory(message: Message):
    """Open the unified inventory."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    text = await build_inventory_text(user_id, chat_id)
    keyboard = await build_inventory_keyboard(user_id, chat_id)
    
    await message.reply(text, reply_markup=keyboard, parse_mode="HTML")
    logger.info(f"User {user_id} opened inventory in chat {chat_id}")


@router.callback_query(F.data.startswith(INV_PREFIX))
async def callback_inventory(callback: CallbackQuery):
    """Handle inventory callback actions."""
    # Parse callback data: inv:{user_id}:{action}:{item_type}
    # Example: inv:123456:use:pp_cream_small or inv:123456:refresh
    data = callback.data[len(INV_PREFIX):]  # Remove "inv:" prefix
    parts = data.split(":", 2)  # Split into max 3 parts: user_id, action, item_type
    
    if len(parts) < 2:
        return await callback.answer("Ошибка")
    
    owner_id = parts[0]
    action = parts[1]
    item_type = parts[2] if len(parts) > 2 else None
    
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    logger.debug(f"Inventory callback: owner={owner_id}, action={action}, item={item_type}, user={user_id}")
    
    # Check ownership
    if int(owner_id) != user_id:
        return await callback.answer("Это не твой инвентарь!", show_alert=True)
    
    # Handle actions
    if action == "refresh":
        text = await build_inventory_text(user_id, chat_id)
        keyboard = await build_inventory_keyboard(user_id, chat_id)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer("🔄 Обновлено")
    
    elif action == "close":
        await callback.message.delete()
        await callback.answer()
    
    elif action == "equip" and item_type:
        # Handle rod equipping (task 5) - Requirements 5.1
        result = await equip_rod(user_id, chat_id, item_type)
        if result.success:
            # Refresh inventory display
            text = await build_inventory_text(user_id, chat_id)
            keyboard = await build_inventory_keyboard(user_id, chat_id)
            await callback.message.edit_text(
                f"{result.message}\n\n{text}",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await callback.answer("✅ Удочка экипирована!")
        else:
            await callback.answer(result.message, show_alert=True)
    
    elif action == "open" and item_type:
        # Handle lootbox opening (task 6) - Requirements 6.1, 6.2, 6.3
        result = await open_lootbox(user_id, chat_id, item_type)
        if result.success:
            # Refresh inventory display
            text = await build_inventory_text(user_id, chat_id)
            keyboard = await build_inventory_keyboard(user_id, chat_id)
            await callback.message.edit_text(
                f"{result.message}\n\n{text}",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await callback.answer("📦 Лутбокс открыт!")
        else:
            await callback.answer(result.message, show_alert=True)
    
    elif action == "cage":
        # Handle PP cage toggle (task 3)
        activate = item_type == "on"
        
        result = await toggle_cage(user_id, chat_id, activate)
        if result.success:
            # Refresh inventory display
            text = await build_inventory_text(user_id, chat_id)
            keyboard = await build_inventory_keyboard(user_id, chat_id)
            await callback.message.edit_text(
                f"{result.message}\n\n{text}",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await callback.answer("✅ Готово!")
        else:
            await callback.answer(result.message, show_alert=True)
    
    elif action == "use" and item_type:
        # Handle item usage (tasks 2, 4)
        
        # Handle PP cream usage (task 2)
        if is_pp_cream(item_type):
            result = await apply_pp_cream(user_id, chat_id, item_type)
            if result.success:
                # Refresh inventory display
                text = await build_inventory_text(user_id, chat_id)
                keyboard = await build_inventory_keyboard(user_id, chat_id)
                await callback.message.edit_text(
                    f"{result.message}\n\n{text}",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                await callback.answer("✅ Мазь применена!")
            else:
                await callback.answer(result.message, show_alert=True)
        
        # Handle booster usage (task 4) - Requirements 4.1, 4.2, 4.3
        elif is_booster(item_type):
            result = await apply_booster(user_id, chat_id, item_type)
            if result.success:
                # Refresh inventory display
                text = await build_inventory_text(user_id, chat_id)
                keyboard = await build_inventory_keyboard(user_id, chat_id)
                await callback.message.edit_text(
                    f"{result.message}\n\n{text}",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                await callback.answer("✅ Бустер активирован!")
            else:
                await callback.answer(result.message, show_alert=True)
        
        else:
            # Unknown consumable type
            await callback.answer(f"❌ Неизвестный тип предмета: {item_type}")
    
    elif action == "rooster" and item_type:
        # Roosters are display-only, show info
        item_info = ITEM_CATALOG.get(item_type)
        if item_info:
            from app.services.rooster_hp import get_rooster_hp
            current_hp, max_hp = await get_rooster_hp(user_id, chat_id, item_type)
            await callback.answer(
                f"{item_info.emoji} {item_info.name}\n❤️ HP: {current_hp}/{max_hp}\n\nИспользуй /cockfight для боя!",
                show_alert=True
            )
        else:
            await callback.answer("Информация о петухе")
    
    else:
        logger.warning(f"Unknown inventory action: {action}, item_type: {item_type}")
        await callback.answer("Неизвестное действие")
