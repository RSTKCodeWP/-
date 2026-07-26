"""Helper functions for localization."""
from localization import get_text


def localize_trader_name(trader_name: str, language: str = "ru") -> str:
    """
    Localize trader name from API response.
    
    Args:
        trader_name: Trader name from API (e.g., "Mechanic", "Prapor")
        language: Target language ("ru" or "en")
    
    Returns:
        Localized trader name
    """
    if not trader_name:
        return "Unknown" if language == "en" else "Неизвестно"
    
    # Normalize trader name
    trader_key = trader_name.lower().strip()
    
    # Map common trader names
    trader_mapping = {
        "prapor": "prapor",
        "therapist": "therapist",
        "fence": "fence",
        "skier": "skier",
        "peacekeeper": "peacekeeper",
        "mechanic": "mechanic",
        "ragman": "ragman",
        "jaeger": "jaeger",
        "lightkeeper": "lightkeeper",
        # Russian variants
        "прапор": "prapor",
        "терапевт": "therapist",
        "барахольщик": "fence",
        "лыжник": "skier",
        "миротворец": "peacekeeper",
        "механик": "mechanic",
        "барыга": "ragman",
        "егерь": "jaeger",
        "смотритель": "lightkeeper",
    }
    
    localization_key = trader_mapping.get(trader_key, trader_key)
    return get_text(localization_key, language)


def localize_item_name(item_data: dict, language: str = "ru") -> str:
    """
    Get localized item name from API response.
    API already returns localized names based on lang parameter.
    
    Args:
        item_data: Item data from API
        language: Target language ("ru" or "en")
    
    Returns:
        Localized item name
    """
    # API returns localized name in the 'name' field when lang parameter is set
    return item_data.get("name", item_data.get("shortName", "Unknown"))


def localize_quest_name(quest_data: dict, language: str = "ru") -> str:
    """
    Get localized quest name from API response.
    API already returns localized names based on lang parameter.
    
    Args:
        quest_data: Quest data from API
        language: Target language ("ru" or "en")
    
    Returns:
        Localized quest name
    """
    # API returns localized name in the 'name' field when lang parameter is set
    return quest_data.get("name", "Unknown Quest")
