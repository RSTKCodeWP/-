"""Quest builds data - Gunsmith and other quests."""

QUEST_BUILDS = {
    "gunsmith_part_1": {
        "name_ru": "Оружейник - Часть 1",
        "name_en": "Gunsmith - Part 1",
        "trader": "Mechanic",
        "level_required": 10,
        "description_ru": "Собрать МР-133 с определенными характеристиками",
        "description_en": "Build MP-133 with specific stats",
        "weapon": "MP-133",
        "requirements": {
            "durability": ">=60",
            "ergonomics": ">=20"
        },
        "recommended_parts": [
            "MP-133 plastic forestock",
            "ME Cylinder muzzle adapter 12ga",
            "Tactical foregrip"
        ]
    },
    "gunsmith_part_2": {
        "name_ru": "Оружейник - Часть 2", 
        "name_en": "Gunsmith - Part 2",
        "trader": "Mechanic",
        "level_required": 15,
        "description_ru": "Собрать AKS-74U с определенными характеристиками",
        "description_en": "Build AKS-74U with specific stats",
        "weapon": "AKS-74U",
        "requirements": {
            "recoil_sum": "<=550",
            "ergonomics": ">=58",
            "weight": "<=3.5kg"
        },
        "recommended_parts": [
            "Zenit PT Lock",
            "Zenit PT-3 stock",
            "Zenit B-11 handguard",
            "Zenit RK-3 pistol grip"
        ]
    },
    "gunsmith_part_3": {
        "name_ru": "Оружейник - Часть 3",
        "name_en": "Gunsmith - Part 3", 
        "trader": "Mechanic",
        "level_required": 18,
        "description_ru": "Собрать МР-153 с определенными характеристиками",
        "description_en": "Build MP-153 with specific stats",
        "weapon": "MP-153",
        "requirements": {
            "ergonomics": ">=45",
            "capacity": ">=8"
        },
        "recommended_parts": [
            "GK-02 muzzle brake",
            "Magpul MOE handguard",
            "CSS knuckle duster"
        ]
    },
    "gunsmith_part_4": {
        "name_ru": "Оружейник - Часть 4",
        "name_en": "Gunsmith - Part 4",
        "trader": "Mechanic",
        "level_required": 20,
        "description_ru": "Собрать AK-74M с определенными характеристиками",
        "description_en": "Build AK-74M with specific stats",
        "weapon": "AK-74M",
        "requirements": {
            "recoil_sum": "<=350",
            "ergonomics": ">=55",
            "capacity": ">=30"
        },
        "recommended_parts": [
            "Zenit B-33 dust cover",
            "Zenit PT-3 stock",
            "RK-3 pistol grip",
            "DTK-2 muzzle brake"
        ]
    },
    "gunsmith_part_5": {
        "name_ru": "Оружейник - Часть 5",
        "name_en": "Gunsmith - Part 5",
        "trader": "Mechanic",
        "level_required": 25,
        "description_ru": "Собрать M4A1 с определенными характеристиками",
        "description_en": "Build M4A1 with specific stats",
        "weapon": "M4A1",
        "requirements": {
            "recoil_sum": "<=300",
            "ergonomics": ">=50",
            "sighting_range": ">=800m"
        },
        "recommended_parts": [
            "Daniel Defense RIS II",
            "Magpul MOE stock",
            "REAP-IR thermal scope",
            "Lantac Dragon muzzle brake"
        ]
    },
    "gunsmith_part_6": {
        "name_ru": "Оружейник - Часть 6",
        "name_en": "Gunsmith - Part 6",
        "trader": "Mechanic",
        "level_required": 28,
        "description_ru": "Собрать АКМ с определенными характеристиками",
        "description_en": "Build AKM with specific stats",
        "weapon": "AKM",
        "requirements": {
            "recoil_sum": "<=450",
            "ergonomics": ">=40",
            "accuracy": "<=2.5 MOA"
        },
        "recommended_parts": [
            "Zenit B-10M handguard",
            "Magpul MOE AKM stock",
            "PWS CQB muzzle brake"
        ]
    },
    "punisher_part_5": {
        "name_ru": "Каратель - Часть 5",
        "name_en": "The Punisher - Part 5",
        "trader": "Prapor",
        "level_required": 18,
        "description_ru": "Убить 10 PMC с использованием MP5",
        "description_en": "Kill 10 PMCs using MP5",
        "weapon": "MP5",
        "requirements": {
            "suppressor": "required"
        },
        "recommended_parts": [
            "MP5SD suppressor",
            "B&T MP5 tri-rail handguard",
            "EOTech 553"
        ]
    },
    "shooter_born_in_heaven": {
        "name_ru": "Снайпер родился на небесах",
        "name_en": "Shooter Born in Heaven",
        "trader": "Jaeger",
        "level_required": 20,
        "description_ru": "Убить PMC выстрелами в голову с расстояния >100м",
        "description_en": "Kill PMCs with headshots from >100m",
        "weapon": "Any sniper rifle",
        "requirements": {
            "effective_range": ">=500m",
            "scope_magnification": ">=4x"
        },
        "recommended_weapons": ["Mosin", "SV-98", "M700", "DVL-10"],
        "recommended_parts": [
            "March Tactical 3-24x42",
            "Nightforce ATACR 7-35x56",
            "Scope mount"
        ]
    }
}


def get_quest_by_id(quest_id: str):
    """Get quest build data by ID."""
    return QUEST_BUILDS.get(quest_id)


def get_all_quests():
    """Get all quest builds."""
    return QUEST_BUILDS


def get_quests_by_weapon(weapon_name: str):
    """Get all quests requiring specific weapon."""
    result = []
    for quest_id, quest_data in QUEST_BUILDS.items():
        if quest_data.get("weapon", "").lower() == weapon_name.lower():
            result.append({**quest_data, "id": quest_id})
    return result


def get_quests_by_trader(trader_name: str):
    """Get all quests from specific trader."""
    result = []
    for quest_id, quest_data in QUEST_BUILDS.items():
        if quest_data.get("trader", "").lower() == trader_name.lower():
            result.append({**quest_data, "id": quest_id})
    return result
