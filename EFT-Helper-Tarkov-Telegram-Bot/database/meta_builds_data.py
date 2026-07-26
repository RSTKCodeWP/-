"""Популярные мета-сборки оружия для EFT 2025."""

# Формат: weapon_name -> список сборок
META_BUILDS = {
    "AK-74M": {
        "meta": {
            "name_ru": "Мета AK-74M",
            "name_en": "Meta AK-74M",
            "description_ru": "Низкая отдача, высокая эргономика",
            "description_en": "Low recoil, high ergonomics",
            "parts": [
                "Zenit B-33 dust cover",
                "Zenit PT-3 stock", 
                "Zenit RK-3 pistol grip",
                "Zenit B-10M handguard",
                "DTK-2 muzzle brake",
                "EOTech 553",
                "Magpul 60-round magazine"
            ],
            "estimated_cost": 250000,
            "min_loyalty": 3
        },
        "budget": {
            "name_ru": "Бюджетная AK-74M",
            "name_en": "Budget AK-74M", 
            "description_ru": "Дешевая сборка для рейдов",
            "description_en": "Cheap build for raids",
            "parts": [
                "GP-25 recoil pad",
                "AK-74 polymer handguard",
                "RK-3 pistol grip",
                "DTK-1 muzzle brake"
            ],
            "estimated_cost": 45000,
            "min_loyalty": 1
        }
    },
    
    "M4A1": {
        "meta": {
            "name_ru": "Мета M4A1",
            "name_en": "Meta M4A1",
            "description_ru": "Лазерный луч с минимальной отдачей",
            "description_en": "Laser beam with minimal recoil",
            "parts": [
                "Daniel Defense RIS II handguard",
                "Magpul MOE stock",
                "Magpul MOE grip",
                "SilencerCo Saker 5.56 suppressor",
                "EOTech EXPS3",
                "Magpul D60 magazine",
                "Lantac Dragon muzzle brake"
            ],
            "estimated_cost": 450000,
            "min_loyalty": 4
        },
        "pvp": {
            "name_ru": "PvP M4A1",
            "name_en": "PvP M4A1",
            "description_ru": "Баланс эргономики и отдачи для PvP",
            "description_en": "Balanced ergo/recoil for PvP",
            "parts": [
                "TROY M7A1 PDW stock",
                "Noveske Gen.3 handguard",
                "Strike Industries AR Pistol Grip",
                "SureFire SOCOM556-RC2 suppressor",
                "Aimpoint T-1"
            ],
            "estimated_cost": 380000,
            "min_loyalty": 3
        }
    },
    
    "HK 416": {
        "meta": {
            "name_ru": "Мета HK 416",
            "name_en": "Meta HK 416",
            "description_ru": "Максимальная эффективность",
            "description_en": "Maximum efficiency",
            "parts": [
                "HK E1 stock",
                "HK Battle Grip",
                "HK MR556A1 handguard",
                "OSS QD 556 suppressor",
                "EOTech Vudu scope"
            ],
            "estimated_cost": 500000,
            "min_loyalty": 4
        }
    },
    
    "AKM": {
        "meta": {
            "name_ru": "Мета АКМ",
            "name_en": "Meta AKM",
            "description_ru": "Мощный 7.62x39 с контролируемой отдачей",
            "description_en": "Powerful 7.62x39 with controlled recoil",
            "parts": [
                "Zenit B-10M handguard",
                "Magpul Zhukov-S stock",
                "Magpul MOE AKM grip",
                "PWS CQB muzzle brake",
                "PK-06 sight"
            ],
            "estimated_cost": 200000,
            "min_loyalty": 2
        }
    },
    
    "MP5": {
        "meta": {
            "name_ru": "Мета MP5",
            "name_en": "Meta MP5",
            "description_ru": "Тихий убийца для CQB",
            "description_en": "Silent killer for CQB",
            "parts": [
                "MP5SD suppressor",
                "B&T MP5 tri-rail handguard",
                "MP5 A3 stock",
                "EOTech 553"
            ],
            "estimated_cost": 180000,
            "min_loyalty": 3
        }
    },
    
    "Mosin": {
        "sniper": {
            "name_ru": "Снайперский Мосин",
            "name_en": "Sniper Mosin",
            "description_ru": "Дальняя дистанция с оптикой",
            "description_en": "Long range with optics",
            "parts": [
                "Mosin stock",
                "Kochetov mount",
                "March Tactical 3-24x42 scope",
                "Mosin thread adapter"
            ],
            "estimated_cost": 120000,
            "min_loyalty": 2
        }
    },
    
    "DVL-10": {
        "meta": {
            "name_ru": "Мета DVL-10",
            "name_en": "Meta DVL-10",
            "description_ru": "Бесшумный снайпер",
            "description_en": "Silent sniper",
            "parts": [
                "DVL-10 stock",
                "GTAC Viper 10x scope",
                "DVL bipod"
            ],
            "estimated_cost": 350000,
            "min_loyalty": 4
        }
    },
    
    "MP-153": {
        "budget": {
            "name_ru": "Бюджетная MP-153",
            "name_en": "Budget MP-153",
            "description_ru": "Дешевая сборка для Фабрики",
            "description_en": "Cheap build for Factory",
            "parts": [
                "GK-02 muzzle brake",
                "Magpul handguard",
                "Red dot sight"
            ],
            "estimated_cost": 55000,
            "min_loyalty": 1
        }
    },
    
    "AS VAL": {
        "meta": {
            "name_ru": "Мета АС ВАЛ",
            "name_en": "Meta AS VAL",
            "description_ru": "Встроенный глушитель, отличная эргономика",
            "description_en": "Integrated suppressor, great ergonomics",
            "parts": [
                "AS VAL polymer stock",
                "Rotor 43 muzzle brake",
                "EOTech EXPS3",
                "30-round magazine"
            ],
            "estimated_cost": 180000,
            "min_loyalty": 3
        }
    },
    
    "VSS Vintorez": {
        "meta": {
            "name_ru": "Мета ВСС Винторез",
            "name_en": "Meta VSS Vintorez",
            "description_ru": "Бесшумный DMR",
            "description_en": "Silent DMR",
            "parts": [
                "VSS polymer stock",
                "Rotor 43 muzzle brake",
                "PSO scope",
                "20-round magazine"
            ],
            "estimated_cost": 150000,
            "min_loyalty": 2
        }
    },
    
    "SR-25": {
        "meta": {
            "name_ru": "Мета SR-25",
            "name_en": "Meta SR-25",
            "description_ru": "Дальнобойный DMR",
            "description_en": "Long-range DMR",
            "parts": [
                "KAC URX 3.1 handguard",
                "Magpul PRS stock",
                "AAC 762-SDN-6 suppressor",
                "Aimpoint Micro T-1",
                "KAC vertical grip"
            ],
            "estimated_cost": 550000,
            "min_loyalty": 4
        }
    }
}


def get_builds_for_weapon(weapon_name: str):
    """Получить все сборки для оружия."""
    return META_BUILDS.get(weapon_name, {})


def get_all_meta_builds():
    """Получить все мета-сборки."""
    result = []
    for weapon, builds in META_BUILDS.items():
        for build_type, build_data in builds.items():
            result.append({
                "weapon": weapon,
                "type": build_type,
                **build_data
            })
    return result


def get_budget_builds():
    """Получить только бюджетные сборки."""
    result = []
    for weapon, builds in META_BUILDS.items():
        if "budget" in builds:
            result.append({
                "weapon": weapon,
                **builds["budget"]
            })
    return result
