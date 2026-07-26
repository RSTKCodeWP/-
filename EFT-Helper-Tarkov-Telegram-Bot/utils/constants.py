"""Constants and configurations for EFT Helper bot."""

# Trader emojis
TRADER_EMOJIS = {
    "Prapor": "🔫",
    "prapor": "🔫",
    "Therapist": "💊",
    "therapist": "💊",
    "Fence": "🗑️",
    "fence": "🗑️",
    "Skier": "💼",
    "skier": "💼",
    "Peacekeeper": "🤝",
    "peacekeeper": "🤝",
    "Mechanic": "🔧",
    "mechanic": "🔧",
    "Ragman": "👕",
    "ragman": "👕",
    "Jaeger": "🌲",
    "jaeger": "🌲",
}

# Default trader loyalty levels
DEFAULT_TRADER_LEVELS = {
    "prapor": 1,
    "therapist": 1,
    "fence": 1,
    "skier": 1,
    "peacekeeper": 1,
    "mechanic": 1,
    "ragman": 1,
    "jaeger": 1,
}

# Category emojis
CATEGORY_EMOJIS = {
    "assault_rifle": "🔫",
    "smg": "🔫",
    "sniper": "🔫",
    "dmr": "🔫",
    "shotgun": "🔫",
    "pistol": "🔫",
    "lmg": "🔫",
}

# Tier emojis
TIER_EMOJIS = {
    "S": "🏆",
    "A": "🥇",
    "B": "🥈",
    "C": "🥉",
    "D": "📊",
}

# API cache duration in hours
API_CACHE_DURATION_HOURS = 24

# Rate limiting settings
RATE_LIMIT_MESSAGES_PER_MINUTE = 20
RATE_LIMIT_COMMANDS_PER_MINUTE = 10

# Database settings
DEFAULT_DB_PATH = "data/eft_helper.db"

# API URLs
TARKOV_DEV_API_URL = "https://api.tarkov.dev/graphql"
TARKOV_MARKET_API_URL = "https://api.tarkov-market.com/api/v1"
