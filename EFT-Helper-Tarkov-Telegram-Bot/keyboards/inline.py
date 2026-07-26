"""Inline keyboards for the EFT Helper bot."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from localization import get_text
from typing import List
from database import Weapon, Build, Trader
from utils.constants import TRADER_EMOJIS


def get_language_selection_keyboard() -> InlineKeyboardMarkup:
    """Get language selection inline keyboard for first-time users."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🇷🇺 Русский",
                    callback_data="lang:ru"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🇬🇧 English",
                    callback_data="lang:en"
                )
            ]
        ]
    )
    return keyboard


def get_weapon_selection_keyboard(weapons: List[Weapon], language: str = "ru") -> InlineKeyboardMarkup:
    """Get weapon selection inline keyboard."""
    buttons = []
    for weapon in weapons:
        weapon_name = weapon.name_ru if language == "ru" else weapon.name_en
        buttons.append([
            InlineKeyboardButton(
                text=weapon_name,
                callback_data=f"weapon:{weapon.id}"
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_build_type_keyboard(weapon_id: int, language: str = "ru") -> InlineKeyboardMarkup:
    """Get build type selection keyboard."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔧 " + ("Сборка из Preset" if language == "ru" else "Preset Build"),
                    callback_data=f"build:preset:{weapon_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("random_build_btn", language),
                    callback_data=f"build:random:{weapon_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("meta_build_btn", language),
                    callback_data=f"build:meta:{weapon_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("constructor_btn", language),
                    callback_data=f"build:constructor:{weapon_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("budget_build_btn", language),
                    callback_data=f"build:budget:{weapon_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("loyalty_build_btn", language),
                    callback_data=f"build:loyalty:{weapon_id}"
                )
            ]
        ]
    )
    return keyboard


def get_traders_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    """Get traders selection keyboard."""
    traders = [
        ("Prapor", "prapor"),
        ("Therapist", "therapist"),
        ("Fence", "fence"),
        ("Skier", "skier"),
        ("Peacekeeper", "peacekeeper"),
        ("Mechanic", "mechanic"),
        ("Ragman", "ragman"),
        ("Jaeger", "jaeger")
    ]
    
    buttons = []
    for trader_name, trader_key in traders:
        emoji = TRADER_EMOJIS.get(trader_key, "💼")
        buttons.append([
            InlineKeyboardButton(
                text=f"{emoji} {get_text(trader_key, language)}",
                callback_data=f"trader:{trader_key}"
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_loyalty_levels_keyboard(trader: str, language: str = "ru") -> InlineKeyboardMarkup:
    """Get loyalty levels keyboard for a trader."""
    buttons = []
    for level in range(1, 5):
        buttons.append([
            InlineKeyboardButton(
                text=get_text("loyalty_level", language, level=level),
                callback_data=f"loyalty:{trader}:{level}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(
            text=get_text("back", language),
            callback_data="back:traders"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_builds_list_keyboard(builds: List[Build], language: str = "ru") -> InlineKeyboardMarkup:
    """Get builds list keyboard."""
    buttons = []
    for build in builds:
        build_name = build.name_ru if language == "ru" else build.name_en
        if build.quest_name_ru or build.quest_name_en:
            quest_name = build.quest_name_ru if language == "ru" else build.quest_name_en
            display_name = f"📜 {quest_name}"
        else:
            display_name = build_name if build_name else f"Build #{build.id}"
        
        buttons.append([
            InlineKeyboardButton(
                text=display_name,
                callback_data=f"show_build:{build.id}"
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_tier_selection_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    """Get tier selection keyboard."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("tier_s", language),
                    callback_data="tier:S"
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("tier_a", language),
                    callback_data="tier:A"
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("tier_b", language),
                    callback_data="tier:B"
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("tier_c", language),
                    callback_data="tier:C"
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("tier_d", language),
                    callback_data="tier:D"
                )
            ]
        ]
    )
    return keyboard
