"""Database models for the EFT Helper bot."""
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


class BuildCategory(str, Enum):
    """Build category types."""
    RANDOM = "random"
    META = "meta"
    QUEST = "quest"
    LOYALTY = "loyalty"


class WeaponCategory(str, Enum):
    """Weapon category types."""
    ASSAULT_RIFLE = "assault_rifle"
    SMG = "smg"
    SNIPER = "sniper"
    DMR = "dmr"
    SHOTGUN = "shotgun"
    PISTOL = "pistol"
    LMG = "lmg"


class TierRating(str, Enum):
    """Tier list ratings."""
    S_TIER = "S"
    A_TIER = "A"
    B_TIER = "B"
    C_TIER = "C"
    D_TIER = "D"


@dataclass
class Weapon:
    """Weapon data model."""
    id: int
    name_ru: str
    name_en: str
    category: WeaponCategory
    tier_rating: Optional[TierRating] = None
    base_price: int = 0
    flea_price: Optional[int] = None  # Flea market price
    tarkov_id: Optional[str] = None  # Tarkov.dev API ID for export
    # Weapon characteristics
    caliber: Optional[str] = None
    ergonomics: Optional[int] = None
    recoil_vertical: Optional[int] = None
    recoil_horizontal: Optional[int] = None
    fire_rate: Optional[int] = None
    effective_range: Optional[int] = None


@dataclass
class Module:
    """Weapon module/attachment data model."""
    id: int
    name_ru: str
    name_en: str
    price: int
    trader: str
    loyalty_level: int
    slot_type: str  # e.g., "stock", "grip", "sight", "barrel", etc.
    tarkov_id: Optional[str] = None  # Tarkov.dev API ID for export
    slot_name: Optional[str] = None  # Slot name for export (e.g., "mod_pistol_grip")
    flea_price: Optional[int] = None  # Flea market price


@dataclass
class Build:
    """Weapon build data model."""
    id: int
    weapon_id: int
    category: BuildCategory
    name_ru: Optional[str] = None
    name_en: Optional[str] = None
    quest_name_ru: Optional[str] = None
    quest_name_en: Optional[str] = None
    total_cost: int = 0
    min_loyalty_level: int = 1
    modules: List[int] = None  # List of module IDs
    is_quest: bool = False  # Flag for quest builds
    tier_rating: Optional[TierRating] = None  # Build quality tier
    
    def __post_init__(self):
        if self.modules is None:
            self.modules = []


@dataclass
class UserBuild:
    """User-created weapon build data model."""
    id: int
    user_id: int
    weapon_id: int
    name: str
    modules: List[int]  # List of module IDs (stored as JSON)
    total_cost: int
    tier_rating: TierRating
    ergonomics: Optional[int] = None
    recoil_vertical: Optional[int] = None
    recoil_horizontal: Optional[int] = None
    is_public: bool = False
    created_at: Optional[str] = None
    likes: int = 0
    
    def __post_init__(self):
        if self.modules is None:
            self.modules = []


@dataclass
class Quest:
    """Quest data model."""
    id: int
    name_ru: str
    name_en: str
    description_ru: str
    description_en: str
    required_builds: List[int] = None  # List of build IDs
    
    def __post_init__(self):
        if self.required_builds is None:
            self.required_builds = []


@dataclass
class Trader:
    """Trader data model."""
    id: int
    name: str
    emoji: str


@dataclass
class User:
    """User data model."""
    user_id: int
    language: str = "ru"  # Default language
    favorite_builds: List[int] = None  # List of build IDs
    trader_levels: dict = None  # Trader loyalty levels: {"prapor": 1, "therapist": 2, ...}
    
    def __post_init__(self):
        if self.favorite_builds is None:
            self.favorite_builds = []
        if self.trader_levels is None:
            self.trader_levels = {
                "prapor": 1,
                "therapist": 1,
                "fence": 1,
                "skier": 1,
                "peacekeeper": 1,
                "mechanic": 1,
                "ragman": 1,
                "jaeger": 1
            }
