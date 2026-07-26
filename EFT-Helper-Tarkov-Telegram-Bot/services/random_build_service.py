"""Service for generating truly random weapon builds with compatibility checks."""
import logging
import random
from typing import List, Dict, Optional, Tuple
from api_clients import TarkovAPIClient

logger = logging.getLogger(__name__)


class RandomBuildService:
    """
    Сервис для генерации случайных сборок оружия с проверкой совместимости.
    
    Генерирует действительно рандомные сборки, где для каждого слота оружия
    выбирается случайный совместимый модуль из списка allowedItems.
    """
    
    def __init__(self, api_client: TarkovAPIClient):
        """
        Инициализация сервиса.
        
        Args:
            api_client: Клиент для работы с Tarkov API
        """
        self.api = api_client
    
    async def generate_random_build(self, weapon_id: str) -> Optional[Dict]:
        """
        Генерирует случайную сборку для указанного оружия.
        
        Args:
            weapon_id: ID оружия из Tarkov API
            
        Returns:
            Словарь с информацией о сборке:
            {
                "weapon": {...},  # Информация об оружии
                "mods": [...]     # Список выбранных модулей
            }
        """
        # Получаем детальную информацию об оружии со слотами
        weapon_data = await self.api.get_weapon_details(weapon_id)
        
        if not weapon_data:
            logger.error(f"Failed to get weapon details for {weapon_id}")
            return None
        
        # Проверяем что у оружия есть слоты
        properties = weapon_data.get("properties")
        if not properties or not isinstance(properties, dict):
            logger.warning(f"Weapon {weapon_id} has no properties")
            return {
                "weapon": weapon_data,
                "mods": []
            }
        
        slots = properties.get("slots", [])
        if not slots:
            logger.info(f"Weapon {weapon_id} has no modification slots")
            return {
                "weapon": weapon_data,
                "mods": []
            }
        
        # Генерируем случайные моды для каждого слота
        selected_mods = []
        
        for slot in slots:
            # Пытаемся выбрать мод для этого слота
            mod = self._select_random_mod_for_slot(slot)
            if mod:
                selected_mods.append({
                    "slot_name": slot.get("name", "Unknown"),
                    "slot_id": slot.get("id", ""),
                    "mod": mod
                })
        
        logger.info(f"Generated random build for {weapon_id} with {len(selected_mods)} mods")
        
        return {
            "weapon": weapon_data,
            "mods": selected_mods
        }
    
    def _select_random_mod_for_slot(self, slot: Dict) -> Optional[Dict]:
        """
        Выбирает случайный совместимый мод для слота.
        
        Args:
            slot: Данные слота с фильтрами совместимости
            
        Returns:
            Информация о выбранном моде или None
        """
        # Проверяем обязательность слота
        is_required = slot.get("required", False)
        
        # Для необязательных слотов с вероятностью 30% пропускаем
        if not is_required and random.random() < 0.3:
            return None
        
        # Получаем фильтры слота
        filters = slot.get("filters")
        if not filters or not isinstance(filters, dict):
            return None
        
        # Получаем разрешенные и исключенные предметы
        allowed_items = filters.get("allowedItems", [])
        excluded_items = filters.get("excludedItems", [])
        
        if not allowed_items:
            return None
        
        # Создаем список ID исключенных предметов
        excluded_items_ids = {item.get("id") for item in excluded_items if isinstance(item, dict)}
        
        # Фильтруем исключенные предметы
        all_allowed_items = []
        for item in allowed_items:
            if isinstance(item, dict) and item.get("id") not in excluded_items_ids:
                all_allowed_items.append(item)
        
        if not all_allowed_items:
            return None
        
        # Выбираем случайный мод из разрешенных
        selected_mod = random.choice(all_allowed_items)
        
        return selected_mod
    
    async def generate_random_build_for_random_weapon(self, lang: str = "en") -> Optional[Dict]:
        """
        Генерирует случайную сборку для случайного оружия.
        
        Args:
            lang: Language code ("ru" or "en")
        
        Returns:
            Словарь с информацией о сборке или None
        """
        # Получаем список всех оружий с локализацией
        try:
            weapons = await self.api.get_all_weapons(lang=lang)
            logger.info(f"API returned {len(weapons) if weapons else 0} weapons for lang={lang}")
        except Exception as e:
            logger.error(f"Failed to fetch weapons from API: {e}", exc_info=True)
            return None
        
        if not weapons:
            logger.error(f"No weapons available for random build generation (API returned empty list for lang={lang})")
            return None
        
        # Фильтруем только реальное оружие (не гранатометы, сигнальные пистолеты и т.д.)
        # Оружие должно быть модифицируемым
        suitable_weapons = []
        for weapon in weapons:
            # Проверяем что это оружие (тип gun)
            types = weapon.get("types", [])
            if "gun" not in types:
                continue
            
            # Добавляем в список подходящих
            suitable_weapons.append(weapon)
        
        if not suitable_weapons:
            logger.error("No suitable weapons found for random build")
            return None
        
        # Выбираем случайное оружие
        selected_weapon = random.choice(suitable_weapons)
        weapon_id = selected_weapon.get("id")
        
        if not weapon_id:
            logger.error("Selected weapon has no ID")
            return None
        
        logger.info(f"Selected random weapon: {selected_weapon.get('name', 'Unknown')} ({weapon_id})")
        
        # Генерируем сборку для выбранного оружия
        build_result = await self.generate_random_build(weapon_id)
        
        return build_result
    
    def format_build_info(
        self, 
        build_data: Dict, 
        language: str = "ru"
    ) -> Tuple[str, int]:
        """
        Форматирует информацию о сборке для отображения пользователю с полными характеристиками.
        
        Args:
            build_data: Данные сборки из generate_random_build
            language: Язык интерфейса
            
        Returns:
            Кортеж (текст сборки, общая стоимость)
        """
        weapon = build_data.get("weapon", {})
        mods = build_data.get("mods", [])
        
        # Формируем заголовок
        weapon_name = weapon.get("name", "Unknown Weapon")
        text = f"🔫 **{weapon_name}**\n"
        text += f"📦 *{weapon.get('shortName', '')}*\n\n"
        
        # Характеристики оружия
        properties = weapon.get("properties", {})
        if properties:
            text += "📊 **Характеристики:**\n" if language == "ru" else "📊 **Stats:**\n"
            
            if "caliber" in properties and properties["caliber"]:
                text += f"  • Калибр: {properties['caliber']}\n" if language == "ru" else f"  • Caliber: {properties['caliber']}\n"
            
            if "ergonomics" in properties and properties["ergonomics"]:
                text += f"  • Эргономика: {properties['ergonomics']}\n" if language == "ru" else f"  • Ergonomics: {properties['ergonomics']}\n"
            
            if "recoilVertical" in properties and properties["recoilVertical"]:
                text += f"  • Отдача (верт): {properties['recoilVertical']}\n" if language == "ru" else f"  • Recoil (vert): {properties['recoilVertical']}\n"
            
            if "recoilHorizontal" in properties and properties["recoilHorizontal"]:
                text += f"  • Отдача (гор): {properties['recoilHorizontal']}\n" if language == "ru" else f"  • Recoil (hor): {properties['recoilHorizontal']}\n"
            
            if "fireRate" in properties and properties["fireRate"]:
                text += f"  • Скорострельность: {properties['fireRate']} в/м\n" if language == "ru" else f"  • Fire Rate: {properties['fireRate']} RPM\n"
            
            if "velocity" in properties and properties["velocity"]:
                text += f"  • Скорость пули: {properties['velocity']} м/с\n" if language == "ru" else f"  • Velocity: {properties['velocity']} m/s\n"
            
            text += "\n"
        
        # Список модулей
        if mods:
            text += "🔧 **Модули:**\n" if language == "ru" else "🔧 **Mods:**\n"
            total_cost = 0
            min_loyalty_level = 1
            required_trader = None
            
            for mod_data in mods:
                slot_name = mod_data.get("slot_name", "Unknown Slot")
                mod = mod_data.get("mod", {})
                mod_name = mod.get("shortName") or mod.get("name", "Unknown")
                mod_price = mod.get("avg24hPrice") or 0
                
                # Ensure price is a number
                if mod_price is None:
                    mod_price = 0
                
                total_cost += mod_price
                
                price_text = f"{mod_price:,} ₽".replace(",", " ") if mod_price else "? ₽"
                text += f"  - **{slot_name}**: {mod_name}\n"
            
            text += "\n"
            
            # Общая стоимость
            weapon_price = weapon.get("avg24hPrice", 0) or 0
            total_with_weapon = total_cost + weapon_price
            
            text += "💰 **Стоимость:**\n" if language == "ru" else "💰 **Cost:**\n"
            text += f"  • Оружие: {weapon_price:,} ₽\n".replace(",", " ") if language == "ru" else f"  • Weapon: {weapon_price:,} ₽\n".replace(",", " ")
            text += f"  • Модули: {total_cost:,} ₽\n".replace(",", " ") if language == "ru" else f"  • Mods: {total_cost:,} ₽\n".replace(",", " ")
            text += f"  • **Итого: {total_with_weapon:,} ₽**\n".replace(",", " ") if language == "ru" else f"  • **Total: {total_with_weapon:,} ₽**\n".replace(",", " ")
            
            # Информация о доступности
            if min_loyalty_level > 1:
                text += f"\n🛒 **Доступно при лояльности**: {required_trader} Lvl {min_loyalty_level}\n" if language == "ru" else f"\n🛒 **Available at loyalty**: {required_trader} Lvl {min_loyalty_level}\n"
            
            return text, total_with_weapon
        else:
            weapon_price = weapon.get("avg24hPrice", 0) or 0
            text += "ℹ️ Модули не установлены (базовая конфигурация)\n" if language == "ru" else "ℹ️ No mods installed (base configuration)\n"
            text += f"💰 **Стоимость**: {weapon_price:,} ₽\n".replace(",", " ") if language == "ru" else f"💰 **Cost**: {weapon_price:,} ₽\n".replace(",", " ")
            return text, weapon_price

