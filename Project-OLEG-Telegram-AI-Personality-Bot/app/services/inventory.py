"""Inventory Service - Manages user items from lootboxes and shop.

v7.5.1 - Full inventory system with item effects.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.database.models import UserInventory

logger = logging.getLogger(__name__)


class ItemType(str, Enum):
    """Item types available in the game."""
    # Fishing rods
    BASIC_ROD = "basic_rod"
    SILVER_ROD = "silver_rod"
    GOLDEN_ROD = "golden_rod"
    LEGENDARY_ROD = "legendary_rod"
    
    # Shop fishing rods (from economy.py)
    FISHING_ROD_BASIC = "fishing_rod_basic"
    FISHING_ROD_PRO = "fishing_rod_pro"
    FISHING_ROD_GOLDEN = "fishing_rod_golden"
    
    # Consumables
    LUCKY_CHARM = "lucky_charm"
    ENERGY_DRINK = "energy_drink"
    DOUBLE_XP = "double_xp"
    
    # New boosters
    DAMAGE_BOOST = "damage_boost"
    HEAL_POTION = "heal_potion"
    CRITICAL_BOOST = "critical_boost"
    COIN_MAGNET = "coin_magnet"
    FISHING_BAIT = "fishing_bait"
    GROW_ACCELERATOR = "grow_accelerator"
    
    # Protection
    SHIELD = "shield"
    
    # Status
    VIP_STATUS = "vip_status"
    
    # Lootboxes
    LOOTBOX_COMMON = "lootbox_common"
    LOOTBOX_RARE = "lootbox_rare"
    LOOTBOX_EPIC = "lootbox_epic"
    LOOTBOX_LEGENDARY = "lootbox_legendary"
    LOOTBOX_MEGA = "lootbox_mega"
    LOOTBOX_MYSTERY = "lootbox_mystery"
    
    # Roosters
    ROOSTER_COMMON = "rooster_common"
    ROOSTER_RARE = "rooster_rare"
    ROOSTER_EPIC = "rooster_epic"
    
    # PP Creams (мази для роста)
    PP_CREAM_SMALL = "pp_cream_small"
    PP_CREAM_MEDIUM = "pp_cream_medium"
    PP_CREAM_LARGE = "pp_cream_large"
    PP_CREAM_TITAN = "pp_cream_titan"
    PP_CREAM_OMEGA = "pp_cream_omega"  # Мега-мазь с бустом к /grow
    
    # PP Protection
    PP_CAGE = "pp_cage"


@dataclass
class ItemInfo:
    """Information about an item type."""
    item_type: str
    name: str
    emoji: str
    description: str
    price: int  # Shop price (0 = not buyable)
    effect: Dict[str, Any]  # Item effects
    stackable: bool = True
    max_stack: int = 99


# Item catalog with all available items
ITEM_CATALOG: Dict[str, ItemInfo] = {
    # Fishing Rods (equippable, not stackable)
    ItemType.BASIC_ROD: ItemInfo(
        item_type=ItemType.BASIC_ROD,
        name="Базовая удочка",
        emoji="🎣",
        description="Стандартная удочка для начинающих рыбаков.",
        price=0,  # Free starter
        effect={"rod_bonus": 0.0},
        stackable=False,
    ),
    ItemType.SILVER_ROD: ItemInfo(
        item_type=ItemType.SILVER_ROD,
        name="Серебряная удочка",
        emoji="🥈",
        description="Улучшенная удочка. +10% к редким рыбам.",
        price=500,
        effect={"rod_bonus": 0.1},
        stackable=False,
    ),
    ItemType.GOLDEN_ROD: ItemInfo(
        item_type=ItemType.GOLDEN_ROD,
        name="Золотая удочка",
        emoji="🥇",
        description="Премиум удочка. +25% к редким рыбам.",
        price=2000,
        effect={"rod_bonus": 0.25},
        stackable=False,
    ),
    ItemType.LEGENDARY_ROD: ItemInfo(
        item_type=ItemType.LEGENDARY_ROD,
        name="Легендарная удочка",
        emoji="👑",
        description="Легендарная удочка мастера. +50% к редким рыбам!",
        price=10000,
        effect={"rod_bonus": 0.5},
        stackable=False,
    ),
    
    # New advanced rods
    "diamond_rod": ItemInfo(
        item_type="diamond_rod",
        name="Алмазная удочка",
        emoji="💎",
        description="Удочка из чистого алмаза. +75% к редким рыбам!",
        price=25000,
        effect={"rod_bonus": 0.75},
        stackable=False,
    ),
    "cosmic_rod": ItemInfo(
        item_type="cosmic_rod",
        name="Космическая удочка",
        emoji="🌌",
        description="Удочка из космического материала. +100% к редким рыбам!",
        price=50000,
        effect={"rod_bonus": 1.0},
        stackable=False,
    ),
    
    # Consumables
    ItemType.LUCKY_CHARM: ItemInfo(
        item_type=ItemType.LUCKY_CHARM,
        name="Талисман удачи",
        emoji="🍀",
        description="Увеличивает шанс выигрыша на 10% в следующей игре.",
        price=100,
        effect={"luck_bonus": 0.1, "uses": 1},
        stackable=True,
    ),
    ItemType.ENERGY_DRINK: ItemInfo(
        item_type=ItemType.ENERGY_DRINK,
        name="Энергетик",
        emoji="🥤",
        description="Сбрасывает кулдаун рыбалки (/fish).",
        price=50,
        effect={"reset_fishing_cooldown": True, "uses": 1},
        stackable=True,
    ),
    
    # Protection
    ItemType.SHIELD: ItemInfo(
        item_type=ItemType.SHIELD,
        name="Щит",
        emoji="🛡️",
        description="Защищает от потери монет в следующей проигрышной игре.",
        price=200,
        effect={"loss_protection": True, "uses": 1},
        stackable=True,
    ),
    
    # Status
    ItemType.VIP_STATUS: ItemInfo(
        item_type=ItemType.VIP_STATUS,
        name="VIP статус",
        emoji="👑",
        description="VIP статус на 24 часа. +20% к выигрышам.",
        price=1000,
        effect={"win_bonus": 0.2, "duration_hours": 24},
        stackable=True,
    ),
    
    # Shop fishing rods
    ItemType.FISHING_ROD_BASIC: ItemInfo(
        item_type=ItemType.FISHING_ROD_BASIC,
        name="Удочка новичка",
        emoji="🎣",
        description="Базовая удочка для рыбалки.",
        price=100,
        effect={"rod_bonus": 0.0},
        stackable=False,
    ),
    ItemType.FISHING_ROD_PRO: ItemInfo(
        item_type=ItemType.FISHING_ROD_PRO,
        name="Про удочка",
        emoji="🎣",
        description="+20% к редкой рыбе.",
        price=500,
        effect={"rod_bonus": 0.2},
        stackable=False,
    ),
    ItemType.FISHING_ROD_GOLDEN: ItemInfo(
        item_type=ItemType.FISHING_ROD_GOLDEN,
        name="Золотая удочка",
        emoji="🎣",
        description="+50% к редкой рыбе.",
        price=2000,
        effect={"rod_bonus": 0.5},
        stackable=False,
    ),
    
    # Double XP
    ItemType.DOUBLE_XP: ItemInfo(
        item_type=ItemType.DOUBLE_XP,
        name="Энергетик x2",
        emoji="⚡",
        description="Двойной опыт на 1 час.",
        price=300,
        effect={"xp_bonus": 2.0, "duration_hours": 1},
        stackable=True,
    ),
    
    # New boosters
    ItemType.DAMAGE_BOOST: ItemInfo(
        item_type=ItemType.DAMAGE_BOOST,
        name="Стероиды",
        emoji="💪",
        description="+20% урона в боях на 30 минут.",
        price=250,
        effect={"damage_bonus": 0.2, "duration_minutes": 30},
        stackable=True,
    ),
    ItemType.HEAL_POTION: ItemInfo(
        item_type=ItemType.HEAL_POTION,
        name="Зелье лечения",
        emoji="🧪",
        description="Восстанавливает 50 HP петуху.",
        price=150,
        effect={"heal_amount": 50},
        stackable=True,
    ),
    ItemType.CRITICAL_BOOST: ItemInfo(
        item_type=ItemType.CRITICAL_BOOST,
        name="Адреналин",
        emoji="⚡",
        description="+15% шанс крита в следующем бою.",
        price=200,
        effect={"crit_chance": 0.15, "uses": 1},
        stackable=True,
    ),
    ItemType.COIN_MAGNET: ItemInfo(
        item_type=ItemType.COIN_MAGNET,
        name="Магнит монет",
        emoji="🧲",
        description="+25% монет из игр на 1 час.",
        price=350,
        effect={"coin_bonus": 0.25, "duration_hours": 1},
        stackable=True,
    ),
    ItemType.FISHING_BAIT: ItemInfo(
        item_type=ItemType.FISHING_BAIT,
        name="Премиум наживка",
        emoji="🪱",
        description="+30% шанс редкой рыбы на 5 использований.",
        price=180,
        effect={"fishing_bonus": 0.3, "uses": 5},
        stackable=True,
    ),
    ItemType.GROW_ACCELERATOR: ItemInfo(
        item_type=ItemType.GROW_ACCELERATOR,
        name="Ускоритель роста",
        emoji="🚀",
        description="Уменьшает кулдаун /grow на 6 часов.",
        price=400,
        effect={"cooldown_reduction_hours": 6},
        stackable=True,
    ),
    
    # Lootboxes
    ItemType.LOOTBOX_COMMON: ItemInfo(
        item_type=ItemType.LOOTBOX_COMMON,
        name="Обычный лутбокс",
        emoji="📦",
        description="Шанс на редкие предметы.",
        price=50,
        effect={"lootbox_tier": "common"},
        stackable=True,
    ),
    ItemType.LOOTBOX_RARE: ItemInfo(
        item_type=ItemType.LOOTBOX_RARE,
        name="Редкий лутбокс",
        emoji="📦",
        description="Повышенный шанс на эпики.",
        price=150,
        effect={"lootbox_tier": "rare"},
        stackable=True,
    ),
    ItemType.LOOTBOX_EPIC: ItemInfo(
        item_type=ItemType.LOOTBOX_EPIC,
        name="Эпический лутбокс",
        emoji="📦",
        description="Гарантированный эпик+.",
        price=400,
        effect={"lootbox_tier": "epic"},
        stackable=True,
    ),
    ItemType.LOOTBOX_LEGENDARY: ItemInfo(
        item_type=ItemType.LOOTBOX_LEGENDARY,
        name="Легендарный лутбокс",
        emoji="📦",
        description="Шанс на легендарку!",
        price=1000,
        effect={"lootbox_tier": "legendary"},
        stackable=True,
    ),
    ItemType.LOOTBOX_MEGA: ItemInfo(
        item_type=ItemType.LOOTBOX_MEGA,
        name="Мега лутбокс",
        emoji="🎁",
        description="Гарантированная легендарка + бонусы!",
        price=2500,
        effect={"lootbox_tier": "mega"},
        stackable=True,
    ),
    ItemType.LOOTBOX_MYSTERY: ItemInfo(
        item_type=ItemType.LOOTBOX_MYSTERY,
        name="Мистический лутбокс",
        emoji="🔮",
        description="Неизвестное содержимое... Может быть всё что угодно!",
        price=500,
        effect={"lootbox_tier": "mystery"},
        stackable=True,
    ),
    
    # Roosters
    ItemType.ROOSTER_COMMON: ItemInfo(
        item_type=ItemType.ROOSTER_COMMON,
        name="Обычный петух",
        emoji="🐔",
        description="Базовый боец.",
        price=200,
        effect={"rooster_tier": "common"},
        stackable=True,
    ),
    ItemType.ROOSTER_RARE: ItemInfo(
        item_type=ItemType.ROOSTER_RARE,
        name="Редкий петух",
        emoji="🐓",
        description="Сильный боец.",
        price=600,
        effect={"rooster_tier": "rare"},
        stackable=True,
    ),
    ItemType.ROOSTER_EPIC: ItemInfo(
        item_type=ItemType.ROOSTER_EPIC,
        name="Эпический петух",
        emoji="🦃",
        description="Элитный боец.",
        price=1500,
        effect={"rooster_tier": "epic"},
        stackable=True,
    ),
    
    # PP Creams (мази для роста пиписьки)
    ItemType.PP_CREAM_SMALL: ItemInfo(
        item_type=ItemType.PP_CREAM_SMALL,
        name="Мазь 'Подрастай'",
        emoji="🧴",
        description="+1-3% размера (мин 1 см, макс 30 см).",
        price=100,
        effect={"pp_boost_min": 1, "pp_boost_max": 3, "min_cm": 1, "max_cm": 30},
        stackable=True,
    ),
    ItemType.PP_CREAM_MEDIUM: ItemInfo(
        item_type=ItemType.PP_CREAM_MEDIUM,
        name="Крем 'Титан'",
        emoji="🧴",
        description="+2-5% размера (мин 2 см, макс 50 см).",
        price=300,
        effect={"pp_boost_min": 2, "pp_boost_max": 5, "min_cm": 2, "max_cm": 50},
        stackable=True,
    ),
    ItemType.PP_CREAM_LARGE: ItemInfo(
        item_type=ItemType.PP_CREAM_LARGE,
        name="Гель 'Мегамен'",
        emoji="🧴",
        description="+5-10% размера (мин 5 см, макс 100 см).",
        price=800,
        effect={"pp_boost_min": 5, "pp_boost_max": 10, "min_cm": 5, "max_cm": 100},
        stackable=True,
    ),
    ItemType.PP_CREAM_TITAN: ItemInfo(
        item_type=ItemType.PP_CREAM_TITAN,
        name="Эликсир 'Годзилла'",
        emoji="🧪",
        description="+10-20% размера (мин 10 см, макс 200 см)!",
        price=2000,
        effect={"pp_boost_min": 10, "pp_boost_max": 20, "min_cm": 10, "max_cm": 200},
        stackable=True,
    ),
    ItemType.PP_CREAM_OMEGA: ItemInfo(
        item_type=ItemType.PP_CREAM_OMEGA,
        name="Сыворотка 'Омега'",
        emoji="💉",
        description="+25-50% размера (мин 25 см, макс 500 см) + буст x2 к /grow!",
        price=5000,
        effect={"pp_boost_min": 25, "pp_boost_max": 50, "min_cm": 25, "max_cm": 500, "grow_boost": 2.0, "grow_boost_duration": 1},
        stackable=True,
    ),
    
    # PP Protection
    ItemType.PP_CAGE: ItemInfo(
        item_type=ItemType.PP_CAGE,
        name="Пенис-клетка",
        emoji="🔒",
        description="Защищает PP от негативных эффектов, но блокирует рост. Действует 24 часа.",
        price=1000,
        effect={"protection": True, "blocks_growth": True, "duration_hours": 24},
        stackable=False,
    ),
}


@dataclass
class InventoryResult:
    """Result of inventory operation."""
    success: bool
    message: str
    item: Optional[ItemInfo] = None
    quantity: int = 0


class InventoryService:
    """Service for managing user inventory."""
    
    async def get_inventory(self, user_id: int, chat_id: int) -> List[UserInventory]:
        """Get all items in user's inventory."""
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(UserInventory).where(
                    UserInventory.user_id == user_id,
                    UserInventory.chat_id == chat_id
                )
            )
            return list(result.scalars().all())
    
    async def get_item(self, user_id: int, chat_id: int, item_type: str) -> Optional[UserInventory]:
        """Get specific item from inventory."""
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(UserInventory).where(
                    UserInventory.user_id == user_id,
                    UserInventory.chat_id == chat_id,
                    UserInventory.item_type == item_type
                )
            )
            return result.scalars().first()
    
    async def add_item(
        self, user_id: int, chat_id: int, item_type: str, quantity: int = 1
    ) -> InventoryResult:
        """Add item to user's inventory."""
        if item_type not in ITEM_CATALOG:
            return InventoryResult(False, f"Неизвестный предмет: {item_type}")
        
        item_info = ITEM_CATALOG[item_type]
        
        async_session = get_session()
        async with async_session() as session:
            # Check if item already exists
            result = await session.execute(
                select(UserInventory).where(
                    UserInventory.user_id == user_id,
                    UserInventory.chat_id == chat_id,
                    UserInventory.item_type == item_type
                )
            )
            existing = result.scalars().first()
            
            if existing:
                if item_info.stackable:
                    existing.quantity = min(existing.quantity + quantity, item_info.max_stack)
                    await session.commit()
                    return InventoryResult(
                        True, 
                        f"Добавлено {item_info.emoji} {item_info.name} x{quantity}",
                        item_info,
                        existing.quantity
                    )
                else:
                    return InventoryResult(
                        False, 
                        f"У тебя уже есть {item_info.emoji} {item_info.name}",
                        item_info,
                        1
                    )
            else:
                new_item = UserInventory(
                    user_id=user_id,
                    chat_id=chat_id,
                    item_type=item_type,
                    item_name=item_info.name,
                    quantity=quantity,
                    equipped=False
                )
                session.add(new_item)
                await session.commit()
                return InventoryResult(
                    True,
                    f"Получен {item_info.emoji} {item_info.name}!",
                    item_info,
                    quantity
                )
    
    async def remove_item(
        self, user_id: int, chat_id: int, item_type: str, quantity: int = 1
    ) -> InventoryResult:
        """Remove item from inventory."""
        if item_type not in ITEM_CATALOG:
            return InventoryResult(False, f"Неизвестный предмет: {item_type}")
        
        item_info = ITEM_CATALOG[item_type]
        
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(UserInventory).where(
                    UserInventory.user_id == user_id,
                    UserInventory.chat_id == chat_id,
                    UserInventory.item_type == item_type
                )
            )
            existing = result.scalars().first()
            
            if not existing or existing.quantity < quantity:
                return InventoryResult(
                    False,
                    f"Недостаточно {item_info.emoji} {item_info.name}",
                    item_info,
                    existing.quantity if existing else 0
                )
            
            existing.quantity -= quantity
            if existing.quantity <= 0:
                await session.delete(existing)
            
            await session.commit()
            return InventoryResult(
                True,
                f"Использован {item_info.emoji} {item_info.name}",
                item_info,
                max(0, existing.quantity - quantity)
            )
    
    async def equip_item(
        self, user_id: int, chat_id: int, item_type: str
    ) -> InventoryResult:
        """Equip an item (for rods, etc.)."""
        if item_type not in ITEM_CATALOG:
            return InventoryResult(False, f"Неизвестный предмет: {item_type}")
        
        item_info = ITEM_CATALOG[item_type]
        
        async_session = get_session()
        async with async_session() as session:
            # Check if user has the item
            result = await session.execute(
                select(UserInventory).where(
                    UserInventory.user_id == user_id,
                    UserInventory.chat_id == chat_id,
                    UserInventory.item_type == item_type
                )
            )
            item = result.scalars().first()
            
            if not item:
                return InventoryResult(False, f"У тебя нет {item_info.emoji} {item_info.name}")
            
            # Unequip all items of same category (e.g., all rods)
            if item_type.endswith("_rod"):
                rod_types = [ItemType.BASIC_ROD, ItemType.SILVER_ROD, 
                            ItemType.GOLDEN_ROD, ItemType.LEGENDARY_ROD]
                for rod in rod_types:
                    res = await session.execute(
                        select(UserInventory).where(
                            UserInventory.user_id == user_id,
                            UserInventory.chat_id == chat_id,
                            UserInventory.item_type == rod
                        )
                    )
                    rod_item = res.scalars().first()
                    if rod_item:
                        rod_item.equipped = False
            
            item.equipped = True
            await session.commit()
            
            return InventoryResult(
                True,
                f"Экипирован {item_info.emoji} {item_info.name}!",
                item_info,
                item.quantity
            )
    
    async def get_equipped_rod(self, user_id: int, chat_id: int) -> ItemInfo:
        """Get currently equipped fishing rod."""
        async_session = get_session()
        async with async_session() as session:
            rod_types = [ItemType.LEGENDARY_ROD, ItemType.GOLDEN_ROD, 
                        ItemType.SILVER_ROD, ItemType.BASIC_ROD]
            
            for rod_type in rod_types:
                result = await session.execute(
                    select(UserInventory).where(
                        UserInventory.user_id == user_id,
                        UserInventory.chat_id == chat_id,
                        UserInventory.item_type == rod_type,
                        UserInventory.equipped == True
                    )
                )
                rod = result.scalars().first()
                if rod:
                    return ITEM_CATALOG[rod_type]
        
        # Default to basic rod
        return ITEM_CATALOG[ItemType.BASIC_ROD]
    
    async def has_item(self, user_id: int, chat_id: int, item_type) -> bool:
        """Check if user has an item.
        
        Args:
            user_id: User ID
            chat_id: Chat ID
            item_type: Item type (can be string or ItemType enum)
        """
        # Convert enum to string if needed
        if hasattr(item_type, 'value'):
            item_type = item_type.value
        
        item = await self.get_item(user_id, chat_id, item_type)
        return item is not None and item.quantity > 0
    
    async def has_active_item(self, user_id: int, chat_id: int, item_type: str) -> bool:
        """
        Check if user has an active (equipped and not expired) item.
        
        For time-limited items like PP_CAGE, checks if the item is equipped
        and hasn't expired based on item_data.expires_at.
        
        Args:
            user_id: Telegram user ID
            chat_id: Chat ID
            item_type: Item type to check
            
        Returns:
            True if item is active, False otherwise
        """
        import json
        from datetime import datetime, timezone
        
        item = await self.get_item(user_id, chat_id, item_type)
        if not item or item.quantity <= 0 or not item.equipped:
            return False
        
        # Check expiration for time-limited items
        if item.item_data:
            try:
                data = json.loads(item.item_data)
                expires_at_str = data.get("expires_at")
                if expires_at_str:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    now = datetime.now(timezone.utc)
                    if now > expires_at:
                        return False
            except (json.JSONDecodeError, ValueError):
                pass
        
        return True
    
    async def activate_item(
        self, user_id: int, chat_id: int, item_type: str
    ) -> InventoryResult:
        """
        Activate a time-limited item like PP_CAGE.
        
        Sets the item as equipped and stores expiration time in item_data.
        
        Args:
            user_id: Telegram user ID
            chat_id: Chat ID
            item_type: Item type to activate
            
        Returns:
            InventoryResult with success status
        """
        import json
        from datetime import datetime, timezone, timedelta
        
        if item_type not in ITEM_CATALOG:
            return InventoryResult(False, f"Неизвестный предмет: {item_type}")
        
        item_info = ITEM_CATALOG[item_type]
        
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(UserInventory).where(
                    UserInventory.user_id == user_id,
                    UserInventory.chat_id == chat_id,
                    UserInventory.item_type == item_type
                )
            )
            item = result.scalars().first()
            
            if not item or item.quantity <= 0:
                return InventoryResult(False, f"У тебя нет {item_info.emoji} {item_info.name}")
            
            # Check if already active
            if item.equipped and item.item_data:
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
                            return InventoryResult(
                                False, 
                                f"{item_info.emoji} {item_info.name} уже активна! Осталось: {hours}ч {minutes}м",
                                item_info,
                                item.quantity
                            )
                except (json.JSONDecodeError, ValueError):
                    pass
            
            # Calculate expiration time
            duration_hours = item_info.effect.get("duration_hours", 24)
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(hours=duration_hours)
            
            # Initialize cage HP if it's a PP_CAGE
            item_data = {
                "activated_at": now.isoformat(),
                "expires_at": expires_at.isoformat()
            }
            if item_type == ItemType.PP_CAGE:
                item_data["cage_hp"] = 5  # Initial HP for cage
            
            # Update item
            item.equipped = True
            item.item_data = json.dumps(item_data)
            
            await session.commit()
            
            return InventoryResult(
                True,
                f"🔒 {item_info.name} активирована на {duration_hours} часов!",
                item_info,
                item.quantity
            )
    
    async def deactivate_item(
        self, user_id: int, chat_id: int, item_type: str
    ) -> InventoryResult:
        """
        Deactivate (remove) a time-limited item like PP_CAGE.
        
        Removes the item from inventory entirely.
        
        Args:
            user_id: Telegram user ID
            chat_id: Chat ID
            item_type: Item type to deactivate
            
        Returns:
            InventoryResult with success status
        """
        if item_type not in ITEM_CATALOG:
            return InventoryResult(False, f"Неизвестный предмет: {item_type}")
        
        item_info = ITEM_CATALOG[item_type]
        
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(UserInventory).where(
                    UserInventory.user_id == user_id,
                    UserInventory.chat_id == chat_id,
                    UserInventory.item_type == item_type
                )
            )
            item = result.scalars().first()
            
            if not item or item.quantity <= 0:
                return InventoryResult(False, f"У тебя нет {item_info.emoji} {item_info.name}")
            
            if not item.equipped:
                return InventoryResult(False, f"{item_info.emoji} {item_info.name} не активна")
            
            # Remove the item
            await session.delete(item)
            await session.commit()
            
            return InventoryResult(
                True,
                f"🔓 {item_info.name} снята!",
                item_info,
                0
            )
    
    def get_item_info(self, item_type: str) -> Optional[ItemInfo]:
        """Get item info from catalog."""
        return ITEM_CATALOG.get(item_type)
    
    def get_shop_items(self) -> List[ItemInfo]:
        """Get all items available in shop."""
        return [item for item in ITEM_CATALOG.values() if item.price > 0]


# Global instance
inventory_service = InventoryService()
