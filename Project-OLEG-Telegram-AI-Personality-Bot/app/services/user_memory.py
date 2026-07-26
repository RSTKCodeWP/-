"""
Сервис памяти о пользователях для Олега.

Хранит профили пользователей: сетап, предпочтения, историю вопросов.
Используется для персонализации ответов.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import json
from dataclasses import dataclass, field, asdict

import logging

logger = logging.getLogger(__name__)
from app.services.vector_db import vector_db


@dataclass
class UserProfile:
    """Профиль пользователя для памяти Олега."""
    user_id: int
    username: Optional[str] = None
    
    # Железо
    cpu: Optional[str] = None
    gpu: Optional[str] = None
    ram: Optional[str] = None
    storage: Optional[str] = None
    motherboard: Optional[str] = None
    psu: Optional[str] = None
    case: Optional[str] = None
    cooling: Optional[str] = None
    monitor: Optional[str] = None
    peripherals: List[str] = field(default_factory=list)
    
    # Устройства
    laptop: Optional[str] = None
    steam_deck: bool = False
    steam_deck_mods: List[str] = field(default_factory=list)
    phone: Optional[str] = None
    console: Optional[str] = None  # Если есть (для подколов)
    
    # Софт и ОС
    os: Optional[str] = None
    distro: Optional[str] = None  # Для Linux
    de: Optional[str] = None  # Desktop Environment
    
    # Предпочтения
    brand_preference: Optional[str] = None  # amd, intel, nvidia
    games: List[str] = field(default_factory=list)
    expertise: List[str] = field(default_factory=list)  # В чём шарит
    
    # Личное
    name: Optional[str] = None  # Имя если представился
    city: Optional[str] = None  # Город
    country: Optional[str] = None  # Страна
    job: Optional[str] = None  # Работа/профессия
    hobbies: List[str] = field(default_factory=list)  # Хобби
    music: List[str] = field(default_factory=list)  # Музыка
    movies: List[str] = field(default_factory=list)  # Фильмы/сериалы
    pets: List[str] = field(default_factory=list)  # Питомцы
    languages: List[str] = field(default_factory=list)  # Языки программирования или обычные
    age: Optional[int] = None  # Возраст если сказал
    birthday: Optional[str] = None  # День рождения в формате DD.MM (без года)
    birthday_chat_id: Optional[int] = None  # Чат для поздравлений (если указан)
    
    # Проблемы и история
    current_problems: List[str] = field(default_factory=list)
    resolved_problems: List[str] = field(default_factory=list)
    
    # Метаданные
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    message_count: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "UserProfile":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def to_context_string(self) -> str:
        """Генерирует строку контекста для промпта."""
        parts = []
        
        if self.username:
            parts.append(f"@{self.username}")
        
        # Сетап
        setup_parts = []
        if self.cpu:
            setup_parts.append(f"CPU: {self.cpu}")
        if self.gpu:
            setup_parts.append(f"GPU: {self.gpu}")
        if self.ram:
            setup_parts.append(f"RAM: {self.ram}")
        if self.os:
            os_str = self.os
            if self.distro:
                os_str = f"{self.distro}"
            setup_parts.append(f"OS: {os_str}")
        
        if setup_parts:
            parts.append(f"Сетап: {', '.join(setup_parts)}")
        
        if self.steam_deck:
            deck_str = "Steam Deck"
            if self.steam_deck_mods:
                deck_str += f" ({', '.join(self.steam_deck_mods[:3])})"
            parts.append(deck_str)
        
        if self.laptop:
            parts.append(f"Ноут: {self.laptop}")
        
        if self.brand_preference:
            parts.append(f"Фанат {self.brand_preference.upper()}")
        
        if self.expertise:
            parts.append(f"Шарит в: {', '.join(self.expertise[:3])}")
        
        if self.current_problems:
            parts.append(f"Проблемы: {self.current_problems[-1]}")
        
        if self.console:
            parts.append(f"Консольщик ({self.console})")
        
        return " | ".join(parts) if parts else ""


class UserMemoryService:
    """Сервис для работы с памятью о пользователях."""
    
    def __init__(self):
        self._cache: Dict[str, UserProfile] = {}  # chat_id:user_id -> profile
        self._cache_ttl = 3600  # 1 час
        self._cache_timestamps: Dict[str, datetime] = {}
    
    def _get_cache_key(self, chat_id: int, user_id: int) -> str:
        return f"{chat_id}:{user_id}"
    
    def _get_collection_name(self, chat_id: int) -> str:
        return f"chat_{chat_id}_user_profiles"
    
    async def get_profile(self, chat_id: int, user_id: int) -> Optional[UserProfile]:
        """Получить профиль пользователя."""
        cache_key = self._get_cache_key(chat_id, user_id)
        
        # Проверяем кэш
        if cache_key in self._cache:
            cache_time = self._cache_timestamps.get(cache_key)
            if cache_time and datetime.now() - cache_time < timedelta(seconds=self._cache_ttl):
                return self._cache[cache_key]
        
        # Загружаем из ChromaDB
        try:
            collection_name = self._get_collection_name(chat_id)
            
            # Используем тот же формат where что и при сохранении
            results = vector_db.search_facts(
                collection_name=collection_name,
                query=f"user profile {user_id}",
                n_results=5,
                where={"type": "profile"}
            )
            
            # Фильтруем по user_id вручную (ChromaDB может иметь проблемы с int в where)
            for result in results:
                meta = result.get('metadata', {})
                stored_user_id = meta.get('user_id')
                
                # Сравниваем как int (user_id может быть сохранён как строка)
                if stored_user_id is not None:
                    try:
                        if int(stored_user_id) == int(user_id):
                            profile_data = json.loads(result.get('text', '{}'))
                            profile = UserProfile.from_dict(profile_data)
                            
                            # Кэшируем
                            self._cache[cache_key] = profile
                            self._cache_timestamps[cache_key] = datetime.now()
                            
                            return profile
                    except (ValueError, TypeError):
                        continue
                        
        except Exception as e:
            logger.debug(f"Profile not found for user {user_id} in chat {chat_id}: {e}")
        
        return None
    
    async def save_profile(self, chat_id: int, user_id: int, profile: UserProfile):
        """Сохранить профиль пользователя."""
        try:
            collection_name = self._get_collection_name(chat_id)
            profile_json = json.dumps(profile.to_dict(), ensure_ascii=False)
            
            # Удаляем старый профиль если есть
            try:
                vector_db.delete_facts(
                    collection_name=collection_name,
                    where={"user_id": user_id, "type": "profile"}
                )
            except:
                pass
            
            # Сохраняем новый
            vector_db.add_fact(
                collection_name=collection_name,
                fact_text=profile_json,
                metadata={
                    "user_id": user_id,
                    "type": "profile",
                    "username": profile.username or "",
                    "updated_at": datetime.now().isoformat()
                }
            )
            
            # Обновляем кэш
            cache_key = self._get_cache_key(chat_id, user_id)
            self._cache[cache_key] = profile
            self._cache_timestamps[cache_key] = datetime.now()
            
            logger.debug(f"Profile saved for user {user_id} in chat {chat_id}")
        except Exception as e:
            logger.error(f"Error saving profile: {e}")
    
    # Факты которые принадлежат Олегу (боту), а не пользователям
    # Эти факты НЕ должны сохраняться в профили пользователей
    OLEG_SETUP_KEYWORDS = [
        'ptm7950', 'термопаста ptm', 'ptm 7950',  # Термопаста Олега
        'steam deck', 'steamdeck', 'стим дек',  # Steam Deck Олега (если юзер сам не говорит)
        'hyprland',  # DE Олега
        'arch linux', 'арч линукс',  # Дистрибутив Олега
        'minifuse', 'minilab',  # Аудио железо из примеров
        'shp9500',  # Наушники из примеров
    ]
    
    def _is_oleg_setup_fact(self, text: str) -> bool:
        """Проверяет, является ли факт частью сетапа Олега (бота), а не пользователя."""
        text_lower = text.lower()
        
        # Проверяем ключевые слова сетапа Олега
        for keyword in self.OLEG_SETUP_KEYWORDS:
            if keyword in text_lower:
                # Исключение: если юзер явно говорит "у меня", "мой", "купил"
                user_ownership_markers = ['у меня', 'мой ', 'моя ', 'моё ', 'мои ', 'купил', 'заказал', 'поставил себе', 'установил себе']
                has_ownership = any(marker in text_lower for marker in user_ownership_markers)
                
                if not has_ownership:
                    logger.debug(f"Filtered out Oleg's setup fact: {text[:50]}...")
                    return True
        
        return False

    async def update_profile_from_facts(
        self, 
        chat_id: int, 
        user_id: int, 
        username: Optional[str],
        facts: List[Dict]
    ) -> UserProfile:
        """Обновить профиль на основе извлечённых фактов."""
        # Получаем существующий профиль или создаём новый
        profile = await self.get_profile(chat_id, user_id)
        if not profile:
            profile = UserProfile(user_id=user_id, username=username)
            profile.first_seen = datetime.now().isoformat()
        
        profile.last_seen = datetime.now().isoformat()
        profile.message_count += 1
        
        if username:
            profile.username = username
        
        # Обновляем на основе фактов
        for fact in facts:
            # Фильтруем факты которые принадлежат Олегу, а не пользователю
            fact_text = fact.get('text', '')
            if self._is_oleg_setup_fact(fact_text):
                continue
            text = fact.get('text', '').lower()
            original_text = fact.get('text', '')  # Оригинал для имён
            category = fact.get('metadata', {}).get('category', '')
            
            # Парсим железо
            if category == 'hardware' or 'rtx' in text or 'gtx' in text or 'rx ' in text or 'radeon' in text:
                self._parse_hardware(profile, text)
            
            # Парсим софт/ОС
            if category == 'software' or 'linux' in text or 'windows' in text or 'arch' in text:
                self._parse_software(profile, text)
            
            # Парсим личную информацию
            self._parse_personal(profile, text, original_text)
            
            # Парсим проблемы
            if category == 'problem':
                if len(profile.current_problems) < 5:
                    profile.current_problems.append(fact.get('text', '')[:100])
            
            # Парсим экспертизу
            if category == 'expertise':
                expertise = self._extract_expertise(text)
                if expertise and expertise not in profile.expertise:
                    profile.expertise.append(expertise)
            
            # Steam Deck
            if 'steam deck' in text or 'дек' in text:
                profile.steam_deck = True
                mods = self._extract_deck_mods(text)
                for mod in mods:
                    if mod not in profile.steam_deck_mods:
                        profile.steam_deck_mods.append(mod)
        
        # Сохраняем обновлённый профиль
        await self.save_profile(chat_id, user_id, profile)
        
        return profile
    
    def _parse_hardware(self, profile: UserProfile, text: str):
        """Парсит информацию о железе из текста."""
        import re
        
        # GPU
        gpu_patterns = [
            r'(rtx\s*\d{4}\s*(?:ti|super)?)',
            r'(gtx\s*\d{4}\s*(?:ti)?)',
            r'(rx\s*\d{4}\s*(?:xt)?)',
            r'(radeon\s*(?:rx\s*)?\d{4})',
            r'(arc\s*[ab]\d{3})',
        ]
        for pattern in gpu_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                profile.gpu = match.group(1).upper()
                break
        
        # CPU
        cpu_patterns = [
            r'(ryzen\s*\d\s*\d{4}x?3?d?)',
            r'(i[3579]-\d{4,5}[a-z]*)',
            r'(core\s*ultra\s*\d\s*\d{3}[a-z]*)',
        ]
        for pattern in cpu_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                profile.cpu = match.group(1)
                break
        
        # RAM
        ram_match = re.search(r'(\d{2,3})\s*(?:gb|гб|гигов?)\s*(?:ram|озу|памят)?', text, re.IGNORECASE)
        if ram_match:
            profile.ram = f"{ram_match.group(1)}GB"
        
        # Brand preference
        if 'amd' in text and ('фанат' in text or 'люблю' in text or 'топ' in text):
            profile.brand_preference = 'amd'
        elif 'intel' in text and ('фанат' in text or 'люблю' in text or 'топ' in text):
            profile.brand_preference = 'intel'
        elif 'nvidia' in text and ('фанат' in text or 'люблю' in text or 'топ' in text):
            profile.brand_preference = 'nvidia'
    
    def _parse_software(self, profile: UserProfile, text: str):
        """Парсит информацию о софте/ОС."""
        # Linux distros
        distros = ['arch', 'ubuntu', 'fedora', 'debian', 'manjaro', 'mint', 'nixos', 'gentoo', 'cachyos', 'bazzite', 'nobara']
        for distro in distros:
            if distro in text.lower():
                profile.os = 'linux'
                profile.distro = distro.capitalize()
                break
        
        if 'windows' in text.lower():
            if 'ненавижу' not in text and 'говно' not in text:
                profile.os = 'windows'
        
        # DE
        des = ['kde', 'gnome', 'hyprland', 'sway', 'i3', 'xfce']
        for de in des:
            if de in text.lower():
                profile.de = de.upper()
                break
    
    def _extract_expertise(self, text: str) -> Optional[str]:
        """Извлекает область экспертизы."""
        expertise_keywords = {
            'разгон': 'разгон',
            'overclock': 'разгон',
            'андервольт': 'андервольт',
            'undervolt': 'андервольт',
            'пайка': 'board level repair',
            'ремонт': 'ремонт',
            'linux': 'Linux',
            'сервер': 'серверы',
            'сеть': 'сети',
            'программирован': 'программирование',
        }
        
        for keyword, expertise in expertise_keywords.items():
            if keyword in text.lower():
                return expertise
        return None
    
    def _extract_deck_mods(self, text: str) -> List[str]:
        """Извлекает моды Steam Deck."""
        mods = []
        mod_keywords = {
            'ptm7950': 'PTM7950',
            'термопрокладк': 'термопрокладки',
            'андервольт': 'андервольт',
            'разгон памят': 'разгон RAM',
            '6400': 'RAM 6400',
            'ssd': 'SSD апгрейд',
        }
        
        for keyword, mod in mod_keywords.items():
            if keyword in text.lower():
                mods.append(mod)
        
        return mods
    
    def _parse_personal(self, profile: UserProfile, text: str, original_text: str):
        """Парсит личную информацию из текста."""
        import re
        
        # Имя (меня зовут X, я X)
        name_patterns = [
            r'меня зовут\s+([а-яё]+)',
            r'я\s+([а-яё]{3,})\s*[,.]',
            r'зови меня\s+([а-яё]+)',
        ]
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).capitalize()
                if len(name) >= 3 and name.lower() not in ['это', 'тут', 'там', 'вот', 'что', 'как']:
                    profile.name = name
                    break
        
        # Город
        cities = {
            'москв': 'Москва', 'питер': 'Питер', 'спб': 'СПб', 'петербург': 'СПб',
            'новосиб': 'Новосибирск', 'екатеринбург': 'Екатеринбург', 'казан': 'Казань',
            'нижн': 'Нижний Новгород', 'самар': 'Самара', 'омск': 'Омск',
            'челябинск': 'Челябинск', 'ростов': 'Ростов', 'уфа': 'Уфа',
            'красноярск': 'Красноярск', 'воронеж': 'Воронеж', 'пермь': 'Пермь',
            'волгоград': 'Волгоград', 'краснодар': 'Краснодар', 'киев': 'Киев',
            'минск': 'Минск', 'алмат': 'Алматы', 'ташкент': 'Ташкент',
        }
        for key, city in cities.items():
            if key in text and ('живу' in text or 'из' in text or 'город' in text):
                profile.city = city
                break
        
        # Работа/профессия
        jobs = {
            'программист': 'программист', 'разработчик': 'разработчик', 'девелопер': 'разработчик',
            'сисадмин': 'сисадмин', 'админ': 'админ', 'devops': 'DevOps',
            'тестировщик': 'тестировщик', 'qa': 'QA', 'дизайнер': 'дизайнер',
            'студент': 'студент', 'школьник': 'школьник', 'фрилансер': 'фрилансер',
            'инженер': 'инженер', 'аналитик': 'аналитик', 'менеджер': 'менеджер',
            'эникей': 'эникейщик', 'техподдержк': 'техподдержка',
        }
        for key, job in jobs.items():
            if key in text and ('работаю' in text or 'я ' in text):
                profile.job = job
                break
        
        # Хобби
        hobbies_map = {
            'фотограф': 'фотография', 'фото': 'фотография',
            'музык': 'музыка', 'гитар': 'гитара', 'пиан': 'пианино',
            'рисова': 'рисование', 'рисую': 'рисование',
            'спорт': 'спорт', 'качалк': 'качалка', 'бег': 'бег',
            'велосипед': 'велосипед', 'плава': 'плавание',
            'кино': 'кино', 'фильм': 'кино', 'сериал': 'сериалы',
            'аниме': 'аниме', 'манг': 'манга',
            'книг': 'книги', 'читаю': 'книги',
            'готов': 'готовка', 'кулинар': 'готовка',
            '3d': '3D моделирование', 'блендер': '3D моделирование',
            'стрим': 'стримы', 'ютуб': 'YouTube',
        }
        for key, hobby in hobbies_map.items():
            if key in text and hobby not in profile.hobbies:
                if len(profile.hobbies) < 5:
                    profile.hobbies.append(hobby)
        
        # Музыка
        music_genres = ['рок', 'метал', 'электроник', 'рэп', 'хип-хоп', 'поп', 'джаз', 
                       'классик', 'панк', 'инди', 'техно', 'хаус', 'dnb', 'драм']
        for genre in music_genres:
            if genre in text and ('слушаю' in text or 'люблю' in text or 'музык' in text):
                if genre not in profile.music and len(profile.music) < 5:
                    profile.music.append(genre)
        
        # Питомцы
        pets_map = {
            'кот': 'кот', 'кошк': 'кошка', 'котик': 'кот', 'котэ': 'кот',
            'собак': 'собака', 'пёс': 'собака', 'пес': 'собака',
            'попугай': 'попугай', 'хомяк': 'хомяк', 'крыс': 'крыса',
        }
        for key, pet in pets_map.items():
            if key in text and ('есть' in text or 'мой' in text or 'моя' in text or 'у меня' in text):
                if pet not in profile.pets and len(profile.pets) < 3:
                    profile.pets.append(pet)
        
        # Языки программирования
        prog_langs = ['python', 'javascript', 'typescript', 'java', 'c++', 'c#', 'rust', 
                     'go', 'kotlin', 'swift', 'php', 'ruby', 'lua']
        for lang in prog_langs:
            if lang in text and ('пишу' in text or 'знаю' in text or 'учу' in text or 'на ' in text):
                if lang not in profile.languages and len(profile.languages) < 5:
                    profile.languages.append(lang)
        
        # Возраст
        age_match = re.search(r'мне\s+(\d{1,2})\s*(?:лет|год)', text)
        if age_match:
            age = int(age_match.group(1))
            if 10 <= age <= 80:
                profile.age = age
        
        # Игры
        games_list = ['cs2', 'cs:go', 'dota', 'дота', 'valorant', 'apex', 'pubg', 
                     'fortnite', 'minecraft', 'майнкрафт', 'gta', 'гта', 'elden ring',
                     'baldur', 'cyberpunk', 'киберпанк', 'witcher', 'ведьмак',
                     'dark souls', 'дарк соулс', 'tarkov', 'тарков', 'rust', 'раст',
                     'wow', 'варкрафт', 'diablo', 'path of exile', 'poe']
        for game in games_list:
            if game in text and game not in profile.games:
                if len(profile.games) < 5:
                    profile.games.append(game)
    
    async def get_context_for_user(self, chat_id: int, user_id: int) -> str:
        """Получить контекст о пользователе для промпта."""
        profile = await self.get_profile(chat_id, user_id)
        if profile:
            return profile.to_context_string()
        return ""
    
    async def get_all_profiles_context(self, chat_id: int, user_ids: List[int]) -> Dict[int, str]:
        """Получить контекст для нескольких пользователей."""
        result = {}
        for user_id in user_ids:
            context = await self.get_context_for_user(chat_id, user_id)
            if context:
                result[user_id] = context
        return result
    
    async def get_birthdays_today(self, today_str: str) -> List[Dict]:
        """
        Получить всех пользователей с днём рождения сегодня.
        
        Args:
            today_str: Дата в формате DD.MM
            
        Returns:
            Список словарей с user_id, username, chat_id, birthday_chat_id
        """
        birthdays = []
        
        try:
            # Получаем все коллекции профилей
            collections = vector_db.client.list_collections()
            
            for coll in collections:
                if "_user_profiles" not in coll.name:
                    continue
                
                # Извлекаем chat_id из имени коллекции
                try:
                    chat_id = int(coll.name.replace("chat_", "").replace("_user_profiles", ""))
                except ValueError:
                    continue
                
                # Получаем все профили из коллекции
                try:
                    collection = vector_db.client.get_collection(coll.name)
                    results = collection.get(
                        where={"type": "profile"},
                        include=["documents", "metadatas"]
                    )
                    
                    if not results or not results.get('documents'):
                        continue
                    
                    for i, doc in enumerate(results['documents']):
                        try:
                            profile_data = json.loads(doc)
                            birthday = profile_data.get('birthday')
                            
                            if birthday == today_str:
                                birthdays.append({
                                    'user_id': profile_data.get('user_id'),
                                    'username': profile_data.get('username'),
                                    'name': profile_data.get('name'),
                                    'chat_id': chat_id,
                                    'birthday_chat_id': profile_data.get('birthday_chat_id')
                                })
                        except (json.JSONDecodeError, KeyError):
                            continue
                            
                except Exception as e:
                    logger.debug(f"Error reading collection {coll.name}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error getting birthdays: {e}")
        
        return birthdays
    
    async def set_birthday(
        self, 
        chat_id: int, 
        user_id: int, 
        username: Optional[str],
        birthday: str,
        birthday_chat_id: Optional[int] = None
    ) -> bool:
        """
        Установить день рождения пользователя.
        
        Args:
            chat_id: ID чата где вызвана команда
            user_id: ID пользователя
            username: Username пользователя
            birthday: Дата в формате DD.MM
            birthday_chat_id: ID чата для поздравлений (опционально)
            
        Returns:
            True если успешно
        """
        try:
            profile = await self.get_profile(chat_id, user_id)
            if not profile:
                profile = UserProfile(user_id=user_id, username=username)
                profile.first_seen = datetime.now().isoformat()
            
            profile.birthday = birthday
            if birthday_chat_id:
                profile.birthday_chat_id = birthday_chat_id
            
            if username:
                profile.username = username
            
            await self.save_profile(chat_id, user_id, profile)
            return True
            
        except Exception as e:
            logger.error(f"Error setting birthday: {e}")
            return False


# Глобальный экземпляр
user_memory = UserMemoryService()
