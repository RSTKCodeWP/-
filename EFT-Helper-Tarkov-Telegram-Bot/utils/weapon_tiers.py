"""Weapon tier ratings for EFT Helper (v5.3)."""

# Weapon tier ratings based on performance, popularity, and meta status
# S-Tier: Top meta weapons with excellent stats
# A-Tier: Very strong weapons, competitive
# B-Tier: Good weapons, viable for most situations
# C-Tier: Average weapons, budget-friendly
# D-Tier: Weak or niche weapons

WEAPON_TIERS = {
    # Assault Rifles - S Tier
    "M4A1": "S",
    "HK 416A5": "S",
    "SCAR-L": "S",
    "MCX SPEAR": "S",
    "AK-74N": "A",
    "AK-74M": "A",
    
    # Assault Rifles - A Tier
    "AKM": "A",
    "AKMN": "A",
    "AK-103": "A",
    "AK-104": "A",
    "M4A1 (ADAR)": "A",
    "MDR 5.56x45": "A",
    "RD-704": "A",
    
    # Assault Rifles - B Tier
    "AK-105": "B",
    "AK-101": "B",
    "AK-102": "B",
    "TX-15": "B",
    "MDR 7.62x51": "B",
    "Mutant": "B",
    
    # Assault Rifles - C Tier
    "OP-SKS": "C",
    "SKS": "C",
    "VPO-136": "C",
    "VPO-209": "C",
    
    # DMR - S Tier
    "SR-25": "S",
    "RSASS": "S",
    "SVD": "S",
    
    # DMR - A Tier
    "M1A": "A",
    "SA-58": "A",
    "RFB": "A",
    
    # DMR - B Tier
    "VSS": "B",
    "AS VAL": "B",
    "SVDS": "B",
    
    # Sniper Rifles - S Tier
    "DVL-10": "S",
    "M700": "S",
    
    # Sniper Rifles - A Tier
    "AXMC": "A",
    "T-5000": "A",
    "Mosin": "B",
    "VPO-215": "C",
    
    # SMGs - S Tier
    "MP5": "S",
    "MP7A2": "S",
    "MPX": "S",
    
    # SMGs - A Tier
    "P90": "A",
    "MP9": "A",
    "UMP 45": "A",
    "Vector 9x19": "A",
    "Vector .45": "A",
    
    # SMGs - B Tier
    "PP-19-01": "B",
    "PP-91": "B",
    "MP5K-N": "B",
    "Saiga-9": "B",
    
    # SMGs - C Tier
    "PP-9": "C",
    "STM-9": "C",
    "Kedr": "C",
    
    # Pistols - A Tier
    "Five-seveN": "A",
    "Glock 18C": "A",
    
    # Pistols - B Tier
    "M1911A1": "B",
    "P226R": "B",
    "PL-15": "B",
    "SR-1MP": "B",
    
    # Pistols - C Tier
    "PM": "C",
    "APB": "C",
    "TT": "C",
    "PB": "C",
    "M9A3": "C",
    
    # Shotguns - A Tier
    "MP-153": "A",
    "MP-155": "A",
    "Saiga-12": "A",
    
    # Shotguns - B Tier
    "M870": "B",
    "KS-23M": "B",
    
    # Shotguns - C Tier
    "TOZ-106": "C",
    "MP-133": "C",
    
    # LMGs - S Tier
    "RPK-16": "S",
    
    # LMGs - A Tier
    "PKM": "A",
    "PKP": "A",
}


def get_weapon_tier(weapon_name: str) -> str:
    """
    Get tier rating for a weapon.
    
    Args:
        weapon_name: Name of the weapon (English or Russian)
        
    Returns:
        Tier rating (S/A/B/C/D), defaults to B if not found
    """
    # Try exact match first
    if weapon_name in WEAPON_TIERS:
        return WEAPON_TIERS[weapon_name]
    
    # Try partial match (case-insensitive)
    weapon_lower = weapon_name.lower()
    for key, tier in WEAPON_TIERS.items():
        if key.lower() in weapon_lower or weapon_lower in key.lower():
            return tier
    
    # Default to B tier
    return "B"


def get_tier_weapons(tier: str) -> list:
    """
    Get all weapons of a specific tier.
    
    Args:
        tier: Tier rating (S/A/B/C/D)
        
    Returns:
        List of weapon names in that tier
    """
    return [weapon for weapon, weapon_tier in WEAPON_TIERS.items() if weapon_tier == tier.upper()]


def get_tier_emoji(tier: str) -> str:
    """Get emoji for tier rating."""
    tier_emojis = {
        "S": "🏆",
        "A": "🥇",
        "B": "🥈",
        "C": "🥉",
        "D": "📊"
    }
    return tier_emojis.get(tier.upper(), "⭐")
