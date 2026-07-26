"""Economy Service - Central economy management for all games.

Manages user balances, transactions, items, and shop functionality.
Version 7.5 - Now uses unified wallet_service for balance operations.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.database.models import User, Wallet
from app.utils import utc_now

logger = logging.getLogger(__name__)


class ItemType(str, Enum):
    """Types of items available in the shop."""
    LOOTBOX_COMMON = "lootbox_common"
    LOOTBOX_RARE = "lootbox_rare"
    LOOTBOX_EPIC = "lootbox_epic"
    LOOTBOX_LEGENDARY = "lootbox_legendary"
    LOOTBOX_MEGA = "lootbox_mega"
    LOOTBOX_MYSTERY = "lootbox_mystery"
    FISHING_ROD_BASIC = "fishing_rod_basic"
    FISHING_ROD_PRO = "fishing_rod_pro"
    FISHING_ROD_GOLDEN = "fishing_rod_golden"
    LUCKY_CHARM = "lucky_charm"  # +5% к выигрышу
    DOUBLE_XP = "double_xp"  # x2 опыт на 1 час
    SHIELD = "shield"  # Защита от PvP на 1 час
    ENERGY_DRINK = "energy_drink"  # Сброс кулдауна /grow
    VIP_STATUS = "vip_status"  # VIP на 24 часа
    ROOSTER_COMMON = "rooster_common"
    ROOSTER_RARE = "rooster_rare"
    ROOSTER_EPIC = "rooster_epic"
    # Мази для роста пиписьки
    PP_CREAM_SMALL = "pp_cream_small"  # +1-3 см
    PP_CREAM_MEDIUM = "pp_cream_medium"  # +2-5 см
    PP_CREAM_LARGE = "pp_cream_large"  # +5-10 см
    PP_CREAM_TITAN = "pp_cream_titan"  # +10-20 см (редкий)
    # PP Protection
    PP_CAGE = "pp_cage"  # Защита PP, блокирует рост
    # New boosters
    DAMAGE_BOOST = "damage_boost"  # +20% урона в боях
    HEAL_POTION = "heal_potion"  # Восстанавливает HP петуху
    CRITICAL_BOOST = "critical_boost"  # +15% шанс крита
    COIN_MAGNET = "coin_magnet"  # +25% монет из игр
    FISHING_BAIT = "fishing_bait"  # +30% редкой рыбы
    GROW_ACCELERATOR = "grow_accelerator"  # -6 часов кулдауна /grow


class Rarity(str, Enum):
    """Item rarity levels."""
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"


@dataclass
class ShopItem:
    """Represents an item in the shop."""
    item_type: ItemType
    name: str
    description: str
    price: int
    emoji: str
    rarity: Rarity = Rarity.COMMON
    duration_hours: int = 0  # 0 = permanent/consumable


# Shop catalog (prices increased by 1.5x for balance, creams by 2x)
SHOP_ITEMS: Dict[ItemType, ShopItem] = {
    ItemType.LOOTBOX_COMMON: ShopItem(
        ItemType.LOOTBOX_COMMON, "Обычный лутбокс", "Шанс на редкие предметы", 
        75, "📦", Rarity.COMMON
    ),
    ItemType.LOOTBOX_RARE: ShopItem(
        ItemType.LOOTBOX_RARE, "Редкий лутбокс", "Повышенный шанс на эпики",
        225, "📦", Rarity.RARE
    ),
    ItemType.LOOTBOX_EPIC: ShopItem(
        ItemType.LOOTBOX_EPIC, "Эпический лутбокс", "Гарантированный эпик+",
        600, "📦", Rarity.EPIC
    ),
    ItemType.LOOTBOX_LEGENDARY: ShopItem(
        ItemType.LOOTBOX_LEGENDARY, "Легендарный лутбокс", "Шанс на легендарку!",
        1500, "📦", Rarity.LEGENDARY
    ),
    ItemType.LOOTBOX_MEGA: ShopItem(
        ItemType.LOOTBOX_MEGA, "Мега лутбокс", "Гарантированная легендарка + бонусы!",
        2500, "🎁", Rarity.LEGENDARY
    ),
    ItemType.LOOTBOX_MYSTERY: ShopItem(
        ItemType.LOOTBOX_MYSTERY, "Мистический лутбокс", "Неизвестное содержимое...",
        500, "🔮", Rarity.RARE
    ),
    # Note: lootbox_mega and lootbox_mystery are also stored as strings in some places
    "lootbox_mega": ShopItem(
        "lootbox_mega", "Мега лутбокс", "Гарантированная легендарка + бонусы!",
        2500, "🎁", Rarity.LEGENDARY
    ),
    "lootbox_mystery": ShopItem(
        "lootbox_mystery", "Мистический лутбокс", "Неизвестное содержимое...",
        500, "🔮", Rarity.RARE
    ),
    ItemType.FISHING_ROD_BASIC: ShopItem(
        ItemType.FISHING_ROD_BASIC, "Удочка новичка", "Базовая удочка для рыбалки",
        150, "🎣", Rarity.COMMON
    ),
    ItemType.FISHING_ROD_PRO: ShopItem(
        ItemType.FISHING_ROD_PRO, "Про удочка", "+20% к редкой рыбе",
        750, "🎣", Rarity.RARE
    ),
    ItemType.FISHING_ROD_GOLDEN: ShopItem(
        ItemType.FISHING_ROD_GOLDEN, "Золотая удочка", "+50% к редкой рыбе",
        3000, "🎣", Rarity.EPIC
    ),
    # New advanced rods (not in ItemType enum, stored as strings)
    "diamond_rod": ShopItem(
        "diamond_rod", "Алмазная удочка", "+75% к редкой рыбе",
        25000, "💎", Rarity.LEGENDARY
    ),
    "cosmic_rod": ShopItem(
        "cosmic_rod", "Космическая удочка", "+100% к редкой рыбе",
        50000, "🌌", Rarity.LEGENDARY
    ),
    ItemType.LUCKY_CHARM: ShopItem(
        ItemType.LUCKY_CHARM, "Талисман удачи", "+5% к выигрышам на 1 час",
        300, "🍀", Rarity.UNCOMMON, duration_hours=1
    ),
    ItemType.DOUBLE_XP: ShopItem(
        ItemType.DOUBLE_XP, "Энергетик x2", "Двойной опыт на 1 час",
        450, "⚡", Rarity.RARE, duration_hours=1
    ),
    ItemType.SHIELD: ShopItem(
        ItemType.SHIELD, "Щит", "Защита от PvP на 1 час",
        375, "🛡️", Rarity.UNCOMMON, duration_hours=1
    ),
    ItemType.ENERGY_DRINK: ShopItem(
        ItemType.ENERGY_DRINK, "Энергетик", "Сброс кулдауна рыбалки",
        225, "🥤", Rarity.UNCOMMON
    ),
    ItemType.VIP_STATUS: ShopItem(
        ItemType.VIP_STATUS, "VIP статус", "VIP бонусы на 24 часа",
        750, "👑", Rarity.EPIC, duration_hours=24
    ),
    
    # New boosters
    ItemType.DAMAGE_BOOST: ShopItem(
        ItemType.DAMAGE_BOOST, "Стероиды", "+20% урона в боях (30 мин)",
        250, "💪", Rarity.UNCOMMON, duration_hours=0.5
    ),
    ItemType.HEAL_POTION: ShopItem(
        ItemType.HEAL_POTION, "Зелье лечения", "Восстанавливает 50 HP петуху",
        150, "🧪", Rarity.COMMON
    ),
    ItemType.CRITICAL_BOOST: ShopItem(
        ItemType.CRITICAL_BOOST, "Адреналин", "+15% шанс крита в бою",
        200, "⚡", Rarity.UNCOMMON
    ),
    ItemType.COIN_MAGNET: ShopItem(
        ItemType.COIN_MAGNET, "Магнит монет", "+25% монет из игр (1ч)",
        350, "🧲", Rarity.RARE, duration_hours=1
    ),
    ItemType.FISHING_BAIT: ShopItem(
        ItemType.FISHING_BAIT, "Премиум наживка", "+30% редкой рыбы (5 раз)",
        180, "🪱", Rarity.UNCOMMON
    ),
    ItemType.GROW_ACCELERATOR: ShopItem(
        ItemType.GROW_ACCELERATOR, "Ускоритель роста", "-6 часов кулдауна /grow",
        400, "🚀", Rarity.RARE
    ),
    
    # Roosters
    ItemType.ROOSTER_COMMON: ShopItem(
        ItemType.ROOSTER_COMMON, "Обычный петух", "Базовый боец",
        300, "🐔", Rarity.COMMON
    ),
    ItemType.ROOSTER_RARE: ShopItem(
        ItemType.ROOSTER_RARE, "Редкий петух", "Сильный боец",
        900, "🐓", Rarity.RARE
    ),
    ItemType.ROOSTER_EPIC: ShopItem(
        ItemType.ROOSTER_EPIC, "Эпический петух", "Элитный боец",
        2250, "🦃", Rarity.EPIC
    ),
    # Мази для роста пиписьки (prices x2 for balance)
    ItemType.PP_CREAM_SMALL: ShopItem(
        ItemType.PP_CREAM_SMALL, "Мазь 'Подрастай'", "+1-3 см к размеру",
        200, "🧴", Rarity.COMMON
    ),
    ItemType.PP_CREAM_MEDIUM: ShopItem(
        ItemType.PP_CREAM_MEDIUM, "Крем 'Титан'", "+2-5 см к размеру",
        600, "🧴", Rarity.UNCOMMON
    ),
    ItemType.PP_CREAM_LARGE: ShopItem(
        ItemType.PP_CREAM_LARGE, "Гель 'Мегамен'", "+5-10 см к размеру",
        1600, "🧴", Rarity.RARE
    ),
    ItemType.PP_CREAM_TITAN: ShopItem(
        ItemType.PP_CREAM_TITAN, "Эликсир 'Годзилла'", "+10-20 см к размеру",
        4000, "🧪", Rarity.EPIC
    ),
    # PP Protection
    ItemType.PP_CAGE: ShopItem(
        ItemType.PP_CAGE, "Пенис-клетка", "Защита PP от негативных эффектов, блокирует рост (24ч)",
        1500, "🔒", Rarity.RARE, duration_hours=24
    ),
}


@dataclass
class TransactionResult:
    """Result of a transaction."""
    success: bool
    message: str
    new_balance: int = 0
    error_code: Optional[str] = None


@dataclass
class InventoryItem:
    """Item in user's inventory."""
    item_type: str
    quantity: int
    expires_at: Optional[datetime] = None


class EconomyService:
    """Central economy management service.
    
    Now uses unified Wallet for all balance operations.
    The chat_id parameter is kept for backward compatibility but ignored.
    """
    
    DEFAULT_BALANCE = 100
    DAILY_BONUS = 50
    DAILY_BONUS_STREAK_MULTIPLIER = 1.1  # +10% за каждый день стрика
    MAX_STREAK_BONUS = 2.0  # Максимум x2
    
    async def get_balance(self, user_id: int, chat_id: int = 0) -> int:
        """Get user's balance from unified Wallet."""
        # Import here to avoid circular imports
        from app.services import wallet_service
        return await wallet_service.get_balance(user_id)
    
    async def add_balance(
        self, user_id: int, amount: int, chat_id: int = 0, reason: str = ""
    ) -> TransactionResult:
        """Add coins to user's balance using unified Wallet."""
        if amount <= 0:
            return TransactionResult(False, "Сумма должна быть положительной", error_code="INVALID_AMOUNT")
        
        from app.services import wallet_service
        result = await wallet_service.add_balance(user_id, amount, reason)
        return TransactionResult(result.success, result.message, result.balance, result.error_code)
    
    async def deduct_balance(
        self, user_id: int, amount: int, chat_id: int = 0, reason: str = ""
    ) -> TransactionResult:
        """Deduct coins from user's balance using unified Wallet."""
        if amount <= 0:
            return TransactionResult(False, "Сумма должна быть положительной", error_code="INVALID_AMOUNT")
        
        from app.services import wallet_service
        result = await wallet_service.deduct_balance(user_id, amount, reason)
        return TransactionResult(result.success, result.message, result.balance, result.error_code)
    
    async def transfer(
        self, from_user_id: int, to_user_id: int, amount: int, chat_id: int = 0
    ) -> TransactionResult:
        """Transfer coins between users using unified Wallet."""
        if from_user_id == to_user_id:
            return TransactionResult(False, "Нельзя перевести самому себе", error_code="SELF_TRANSFER")
        
        if amount <= 0:
            return TransactionResult(False, "Сумма должна быть положительной", error_code="INVALID_AMOUNT")
        
        from app.services import wallet_service
        result = await wallet_service.transfer(from_user_id, to_user_id, amount)
        return TransactionResult(result.success, result.message, result.balance, result.error_code)
    
    def get_shop_items(self) -> List[ShopItem]:
        """Get all available shop items."""
        return list(SHOP_ITEMS.values())
    
    def get_shop_item(self, item_type: ItemType) -> Optional[ShopItem]:
        """Get specific shop item."""
        return SHOP_ITEMS.get(item_type)
    
    async def purchase_item(
        self, user_id: int, item_type: ItemType, chat_id: int = 0
    ) -> TransactionResult:
        """Purchase an item from the shop."""
        item = self.get_shop_item(item_type)
        if not item:
            return TransactionResult(False, "Предмет не найден", error_code="ITEM_NOT_FOUND")
        
        # Deduct balance
        result = await self.deduct_balance(user_id, item.price, chat_id, f"purchase {item.name}")
        if not result.success:
            return result
        
        # Add item to inventory (would need inventory table)
        # For now, just return success
        logger.info(f"User {user_id} purchased {item.name} for {item.price}")
        return TransactionResult(
            True, 
            f"Куплено: {item.emoji} {item.name} за {item.price} монет",
            result.new_balance
        )


# Global instance
economy_service = EconomyService()
