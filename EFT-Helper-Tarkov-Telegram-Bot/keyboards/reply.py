"""Reply keyboards for the EFT Helper bot."""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from localization import get_text


def get_main_menu_keyboard(language: str = "ru") -> ReplyKeyboardMarkup:
    """Get main menu reply keyboard with v5.3 features."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=get_text("search_weapon", language)),
                KeyboardButton(text=get_text("random_build", language))
            ],
            [
                KeyboardButton(text=get_text("all_quest_builds", language)),
                KeyboardButton(text=get_text("loyalty_build_menu", language))
            ],
            [
                KeyboardButton(text=get_text("budget_build_menu", language)),
                KeyboardButton(text=get_text("best_weapons", language))
            ],
            [
                KeyboardButton(text=get_text("settings", language))
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard


def get_settings_keyboard(language: str = "ru") -> ReplyKeyboardMarkup:
    """Get settings keyboard."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=get_text("lang_ru", language)),
                KeyboardButton(text=get_text("lang_en", language))
            ],
            [
                KeyboardButton(text=get_text("back", language))
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard
