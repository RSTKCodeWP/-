# 🏗️ Архитектура EFT Helper Bot

## Обзор

EFT Helper использует **многослойную архитектуру (Layered Architecture)** для разделения ответственности и упрощения поддержки.

## 📐 Структура слоёв

```
┌─────────────────────────────────────┐
│      Presentation Layer             │
│      (handlers/)                    │
│  - Обработка команд пользователя   │
│  - Формирование ответов             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│      Business Logic Layer           │
│      (services/)                    │
│  - Бизнес-правила                   │
│  - Валидация                        │
│  - Координация                      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│      Data Access Layer              │
│  ┌──────────────┐ ┌──────────────┐ │
│  │  database/   │ │ api_clients/ │ │
│  │  (SQLite)    │ │ (tarkov.dev) │ │
│  └──────────────┘ └──────────────┘ │
└─────────────────────────────────────┘
```

## 🎯 Принципы

### 1. **Separation of Concerns (Разделение ответственности)**

Каждый слой отвечает только за свою функцию:

- **Handlers**: Взаимодействие с пользователем
- **Services**: Бизнес-логика
- **Database/API**: Хранение и получение данных

### 2. **Dependency Injection**

Зависимости передаются через middleware:

```python
# В main.py
@dp.update.outer_middleware()
async def inject_services(handler, event, data):
    data["weapon_service"] = self.weapon_service
    data["build_service"] = self.build_service
    # ...
```

### 3. **Single Responsibility Principle**

Каждый класс/модуль имеет одну ответственность:

- `TarkovAPIClient` - только работа с API
- `WeaponService` - только логика оружия
- `UserService` - только логика пользователей

### 4. **Don't Repeat Yourself (DRY)**

Вся повторяющаяся логика вынесена в сервисы:

```python
# Вместо дублирования в каждом handler:
user = await db.get_or_create_user(user_id)

# Используем service:
user = await user_service.get_or_create_user(user_id)
```

## 📦 Компоненты

### `main.py` - Точка входа

```python
class BotApplication:
    def __init__(self):
        self.db = Database()
        self.api_client = TarkovAPIClient()
        self.weapon_service = WeaponService(self.db, self.api_client)
        # ...
```

### `api_clients/` - Внешние API

**Правило**: ВСЕ запросы к внешним API идут ТОЛЬКО через клиенты.

```python
class TarkovAPIClient:
    async def get_all_weapons()
    async def get_all_traders()
    async def get_all_mods()
    # Встроенное кэширование
```

### `services/` - Бизнес-логика

**Правило**: Вся логика обработки данных в сервисах, НЕ в handlers.

```python
class WeaponService:
    async def search_weapons(query, language)
    async def get_weapons_by_category(category)
    async def get_weapons_by_tier(tier)

class BuildService:
    async def get_random_build()
    async def get_builds_for_weapon(weapon_id)
    async def get_builds_by_loyalty(trader_levels)

class UserService:
    async def get_or_create_user(user_id)
    async def update_language(user_id, language)
    async def update_trader_levels(user_id, levels)

class SyncService:
    async def sync_all()
    async def sync_weapons()
    async def sync_traders()
    async def sync_modules()
```

### `handlers/` - Обработчики команд

**Правило**: Только координация, никакой бизнес-логики.

```python
@router.message(Command("start"))
async def cmd_start(message, user_service):
    user = await user_service.get_or_create_user(message.from_user.id)
    await message.answer(get_text("welcome", user.language))
```

### `database/` - Работа с БД

```python
class Database:
    # CRUD операции для всех моделей
    async def get_weapon_by_id(weapon_id)
    async def search_weapons(query)
    # ...
```

## 🔄 Поток данных

### Пример: Поиск оружия

```
Пользователь → /search
    ↓
Handler (search.py)
    ↓
user_service.get_or_create_user()
    ↓
weapon_service.search_weapons(query)
    ↓
database.search_weapons()
    ↓
Результат → Handler → Пользователь
```

### Пример: Синхронизация с API

```
Команда → sync_data.py
    ↓
SyncService.sync_all()
    ↓
api_client.get_all_weapons()
    ↓
database.save_weapons()
    ↓
Результат сохранён
```

## 🎨 Паттерны

### Repository Pattern (через Database)

```python
# Database класс действует как Repository
db = Database()
weapons = await db.get_all_weapons()
```

### Service Layer Pattern

```python
# Сервисы инкапсулируют бизнес-логику
weapon_service = WeaponService(db, api_client)
weapons = await weapon_service.get_weapons_by_category(category)
```

### Dependency Injection

```python
# Зависимости инжектятся через middleware
async def handler(message, weapon_service, user_service):
    # Сервисы уже доступны
```

### Singleton (API Client)

```python
# Один экземпляр TarkovAPIClient на всё приложение
api_client = TarkovAPIClient()
```

## 🚫 Антипаттерны (чего избегать)

### ❌ Бизнес-логика в handlers

```python
# ПЛОХО
async def handler(message, db):
    weapons = await db.get_all_weapons()
    filtered = [w for w in weapons if w.tier == "S"]  # Логика в handler!
    sorted_weapons = sorted(filtered, key=lambda x: x.price)  # Ещё логика!
```

```python
# ХОРОШО
async def handler(message, weapon_service):
    weapons = await weapon_service.get_top_tier_weapons()  # Логика в service
```

### ❌ Прямые API вызовы из handlers

```python
# ПЛОХО
async def handler(message):
    async with aiohttp.ClientSession() as session:
        await session.get("https://api.tarkov.dev/...")  # Прямой вызов!
```

```python
# ХОРОШО
async def handler(message, api_client):
    data = await api_client.get_all_weapons()  # Через клиент
```

### ❌ Дублирование кода

```python
# ПЛОХО - дублируется в каждом handler
user = await db.get_or_create_user(user_id)
```

```python
# ХОРОШО - через service
user = await user_service.get_or_create_user(user_id)
```

## 🧪 Тестирование

Слоистая архитектура упрощает тестирование:

```python
# Тест service (mock database и API)
async def test_weapon_service():
    mock_db = MockDatabase()
    mock_api = MockAPIClient()
    service = WeaponService(mock_db, mock_api)
    
    result = await service.search_weapons("AK-74")
    assert len(result) > 0
```

## 📈 Масштабируемость

### Добавление нового функционала:

1. **Новый API источник**: создать клиент в `api_clients/`
2. **Новая бизнес-логика**: создать service в `services/`
3. **Новая команда**: создать handler в `handlers/`

### Пример: добавление рынка

```python
# 1. api_clients/flea_market_client.py
class FleaMarketClient:
    async def get_prices()

# 2. services/market_service.py
class MarketService:
    async def find_best_deals()

# 3. handlers/market.py
@router.message(Command("market"))
async def show_market(message, market_service):
    deals = await market_service.find_best_deals()
```

## 🔍 Отладка

Логирование на каждом уровне:

```python
# Handler
logger.info(f"User {user_id} requested weapon search")

# Service
logger.debug(f"Searching weapons with query: {query}")

# API Client
logger.info(f"Fetched {len(weapons)} weapons from API")
```

## 📚 Дополнительно

- **SOLID принципы**: архитектура следует SOLID
- **Clean Architecture**: вдохновлена Clean Architecture
- **Domain-Driven Design**: сервисы представляют domain логику
