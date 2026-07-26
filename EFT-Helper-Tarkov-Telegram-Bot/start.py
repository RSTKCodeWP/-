"""Скрипт автоматического запуска бота с проверками и инициализацией."""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


async def check_env_file():
    """Проверка наличия BOT_TOKEN в переменных окружения."""
    print("🔍 Проверка конфигурации...")
    
    # Проверяем переменную окружения BOT_TOKEN
    bot_token = os.getenv("BOT_TOKEN", "")
    
    if not bot_token or bot_token == "your_telegram_bot_token_here":
        print("❌ BOT_TOKEN не настроен!")
        print("\n📝 Создайте файл .env в корне проекта:")
        print("   BOT_TOKEN=your_telegram_bot_token_here")
        print("   ADMIN_IDS=123456789")
        print("\n   Получите токен у @BotFather в Telegram")
        print("\n   После настройки перезапустите: docker-compose restart")
        return False
    
    print("✅ BOT_TOKEN найден")
    return True


async def migrate_database():
    """Миграция базы данных для обновления схемы."""
    import aiosqlite
    import json
    from utils.constants import DEFAULT_TRADER_LEVELS, DEFAULT_DB_PATH
    
    db_path = DEFAULT_DB_PATH
    
    async with aiosqlite.connect(db_path) as db:
        # Миграция 1: Добавление trader_levels в users
        async with db.execute("PRAGMA table_info(users)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
        
        if "trader_levels" not in column_names:
            print("   📝 Миграция: добавление trader_levels...")
            
            # Добавляем новую колонку
            await db.execute("ALTER TABLE users ADD COLUMN trader_levels TEXT")
            
            # Устанавливаем значения по умолчанию
            default_trader_levels = json.dumps(DEFAULT_TRADER_LEVELS)
            
            await db.execute(
                "UPDATE users SET trader_levels = ?",
                (default_trader_levels,)
            )
            
            await db.commit()
            print("   ✅ trader_levels добавлен")
        
        # Миграция 2: Добавление характеристик оружия
        async with db.execute("PRAGMA table_info(weapons)") as cursor:
            columns = await cursor.fetchall()
            weapon_columns = [col[1] for col in columns]
        
        weapon_stats_columns = [
            ("caliber", "TEXT"),
            ("ergonomics", "INTEGER"),
            ("recoil_vertical", "INTEGER"),
            ("recoil_horizontal", "INTEGER"),
            ("fire_rate", "INTEGER"),
            ("effective_range", "INTEGER"),
            ("flea_price", "INTEGER")
        ]
        
        migration_needed = False
        for col_name, col_type in weapon_stats_columns:
            if col_name not in weapon_columns:
                if not migration_needed:
                    print("   📝 Миграция: добавление характеристик оружия...")
                    migration_needed = True
                try:
                    await db.execute(f"ALTER TABLE weapons ADD COLUMN {col_name} {col_type}")
                    print(f"   ✅ {col_name} добавлен")
                except Exception as e:
                    print(f"   ⚠️  Ошибка при добавлении {col_name}: {e}")
        
        if migration_needed:
            await db.commit()
            print("   ✅ Характеристики оружия добавлены")
        
        # Миграция 3: Добавление flea_price в modules
        async with db.execute("PRAGMA table_info(modules)") as cursor:
            columns = await cursor.fetchall()
            module_columns = [col[1] for col in columns]
        
        if "flea_price" not in module_columns:
            print("   📝 Миграция: добавление flea_price в modules...")
            try:
                await db.execute("ALTER TABLE modules ADD COLUMN flea_price INTEGER")
                await db.commit()
                print("   ✅ flea_price добавлен в modules")
            except Exception as e:
                print(f"   ⚠️  Ошибка при добавлении flea_price: {e}")


async def init_database():
    """Инициализация базы данных."""
    print("\n🗄️  Инициализация базы данных...")
    
    from database import Database
    
    db = Database("data/eft_helper.db")
    await db.init_db()
    
    print("✅ База данных инициализирована")
    
    # Выполняем миграцию при необходимости
    await migrate_database()
    
    return db


async def check_database_content(db):
    """Проверка наличия данных в базе."""
    print("\n📊 Проверка содержимого базы данных...")
    
    import aiosqlite
    
    async with aiosqlite.connect(db.db_path) as conn:
        # Проверка наличия оружия
        async with conn.execute("SELECT COUNT(*) FROM weapons") as cursor:
            weapons_count = (await cursor.fetchone())[0]
        
        # Проверка наличия модулей
        async with conn.execute("SELECT COUNT(*) FROM modules") as cursor:
            modules_count = (await cursor.fetchone())[0]
        
        # Проверка наличия сборок
        async with conn.execute("SELECT COUNT(*) FROM builds") as cursor:
            builds_count = (await cursor.fetchone())[0]
        
        # Проверка наличия торговцев
        async with conn.execute("SELECT COUNT(*) FROM traders") as cursor:
            traders_count = (await cursor.fetchone())[0]
    
    print(f"   Оружие: {weapons_count}")
    print(f"   Модули: {modules_count}")
    print(f"   Сборки: {builds_count}")
    print(f"   Торговцы: {traders_count}")
    
    return {
        "weapons": weapons_count,
        "modules": modules_count,
        "builds": builds_count,
        "traders": traders_count
    }


async def populate_sample_data():
    """Заполнение базы тестовыми данными."""
    print("\n📦 Заполнение базы тестовыми данными...")
    print("   (Это может занять некоторое время)")
    
    try:
        # Добавляем путь к scripts в sys.path
        scripts_path = os.path.join(os.path.dirname(__file__), 'scripts')
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
        
        # Импортируем и запускаем populate_db
        import populate_db
        await populate_db.main()
        print("✅ Тестовые данные добавлены")
        return True
    except Exception as e:
        print(f"❌ Ошибка при заполнении данных: {e}")
        import traceback
        traceback.print_exc()
        return False


async def load_data_from_api():
    """Загрузка всех данных из API (при первом запуске)."""
    import aiohttp
    
    print("\n📡 Загрузка данных из tarkov.dev API...")
    print("   Это займет около минуты...\n")
    
    API_URL = "https://api.tarkov.dev/graphql"
    
    query = """
    {
        items(limit: 10000) {
            id
            name
            shortName
            avg24hPrice
            types
            properties {
                ... on ItemPropertiesWeapon {
                    caliber
                    ergonomics
                    recoilVertical
                    recoilHorizontal
                    fireRate
                }
            }
            buyFor {
                vendor {
                    ... on TraderOffer {
                        trader {
                            name
                        }
                        minTraderLevel
                    }
                }
                price
            }
        }
    }
    """
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, json={"query": query}, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    print(f"❌ API вернул код {resp.status}")
                    return False
                
                data = await resp.json()
                
                if "errors" in data:
                    print(f"❌ Ошибки API: {data['errors']}")
                    return False
                
                items = data.get("data", {}).get("items", [])
                print(f"✅ Получено предметов: {len(items)}")
                
                if not items:
                    return False
                
                # Separate items
                weapons = []
                mods = []
                
                for item in items:
                    item_types = [t.lower() for t in item.get("types", [])]
                    
                    if "gun" in item_types:
                        weapons.append(item)
                    elif any(mod_type in item_types for mod_type in [
                        "mods", "mod", "suppressor", "sight", "scope", "stock", 
                        "grip", "pistolgrip", "foregrip", "magazine", "handguard", 
                        "mount", "barrel", "gasblock", "charging", "receiver"
                    ]):
                        mods.append(item)
                
                print(f"   Оружие: {len(weapons)}, Модули: {len(mods)}")
                
                # Save to DB
                await save_api_data_to_db(weapons, mods)
                
                return True
                
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        return False


async def save_api_data_to_db(weapons, mods):
    """Save API data to database."""
    import aiosqlite
    
    db_path = "data/eft_helper.db"
    
    async with aiosqlite.connect(db_path) as db:
        # Save weapons
        for weapon in weapons:
            try:
                name_en = weapon.get("shortName") or weapon.get("name", "Unknown")
                props = weapon.get("properties") or {}
                
                await db.execute(
                    """INSERT OR REPLACE INTO weapons 
                    (name_ru, name_en, category, base_price, flea_price, caliber, 
                     ergonomics, recoil_vertical, recoil_horizontal, fire_rate) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (name_en, name_en, "assault_rifle", weapon.get("avg24hPrice", 0),
                     weapon.get("avg24hPrice"), props.get("caliber"),
                     props.get("ergonomics"), props.get("recoilVertical"),
                     props.get("recoilHorizontal"), props.get("fireRate"))
                )
            except:
                pass
        
        # Save mods
        for mod in mods:
            try:
                name_en = mod.get("shortName") or mod.get("name", "Unknown")
                price = mod.get("avg24hPrice", 0) or 0
                
                trader = "Mechanic"
                trader_price = price
                loyalty_level = 2
                
                buy_for = mod.get("buyFor", [])
                if buy_for:
                    for offer in buy_for:
                        vendor = offer.get("vendor")
                        if vendor and vendor.get("__typename") != "FleaMarket":
                            trader_data = vendor.get("trader")
                            if trader_data:
                                trader = trader_data.get("name", "Mechanic")
                                loyalty_level = vendor.get("minTraderLevel", 2)
                                trader_price = offer.get("price", price)
                                break
                
                # Determine slot type
                name_lower = name_en.lower()
                types_lower = [t.lower() for t in mod.get("types", [])]
                
                if "sight" in name_lower or "scope" in name_lower or "sight" in types_lower:
                    slot_type = "sight"
                elif "stock" in name_lower or "stock" in types_lower:
                    slot_type = "stock"
                elif "grip" in name_lower or "grip" in types_lower:
                    slot_type = "grip"
                elif "suppressor" in name_lower or "suppressor" in types_lower:
                    slot_type = "muzzle"
                elif "magazine" in name_lower or "magazine" in types_lower:
                    slot_type = "magazine"
                elif "handguard" in name_lower or "handguard" in types_lower:
                    slot_type = "handguard"
                elif "barrel" in name_lower or "barrel" in types_lower:
                    slot_type = "barrel"
                else:
                    slot_type = "universal"
                
                await db.execute(
                    """INSERT OR REPLACE INTO modules 
                    (name_ru, name_en, price, trader, loyalty_level, slot_type, flea_price) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (name_en, name_en, trader_price, trader, loyalty_level, slot_type, price)
                )
            except:
                pass
        
        await db.commit()
        print(f"   ✅ Сохранено в базу данных")


async def update_builds_with_modules():
    """Update builds with actual module IDs from database."""
    import aiosqlite
    import json
    from database.meta_builds_data import META_BUILDS
    
    db_path = "data/eft_helper.db"
    
    async def find_module_by_name(conn, part_name: str) -> int:
        """Try to find module ID by part name."""
        async with conn.execute(
            "SELECT id FROM modules WHERE name_en LIKE ? OR name_ru LIKE ? LIMIT 1",
            (f"%{part_name}%", f"%{part_name}%")
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
        
        words = part_name.split()
        for word in words:
            if len(word) > 3:
                async with conn.execute(
                    "SELECT id FROM modules WHERE name_en LIKE ? OR name_ru LIKE ? LIMIT 1",
                    (f"%{word}%", f"%{word}%")
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return row[0]
        return None
    
    async with aiosqlite.connect(db_path) as conn:
        for weapon_name, builds in META_BUILDS.items():
            async with conn.execute(
                "SELECT id FROM weapons WHERE name_en LIKE ? OR name_ru LIKE ? LIMIT 1",
                (f"%{weapon_name}%", f"%{weapon_name}%")
            ) as cursor:
                weapon_row = await cursor.fetchone()
            
            if not weapon_row:
                continue
            
            weapon_id = weapon_row[0]
            
            for build_type, build_data in builds.items():
                name_en = build_data.get("name_en", f"{weapon_name} {build_type}")
                parts = build_data.get("parts", [])
                
                async with conn.execute(
                    "SELECT id, modules FROM builds WHERE weapon_id = ? AND name_en = ?",
                    (weapon_id, name_en)
                ) as cursor:
                    build_row = await cursor.fetchone()
                
                if not build_row:
                    continue
                
                build_id = build_row[0]
                current_modules = json.loads(build_row[1]) if build_row[1] else []
                
                if current_modules:
                    continue
                
                module_ids = []
                for part_name in parts:
                    module_id = await find_module_by_name(conn, part_name)
                    if module_id:
                        module_ids.append(module_id)
                
                if module_ids:
                    total_cost = 0
                    max_loyalty = 1
                    
                    for module_id in module_ids:
                        async with conn.execute(
                            "SELECT price, loyalty_level FROM modules WHERE id = ?",
                            (module_id,)
                        ) as cursor:
                            mod_row = await cursor.fetchone()
                            if mod_row:
                                total_cost += mod_row[0]
                                max_loyalty = max(max_loyalty, mod_row[1])
                    
                    await conn.execute(
                        "UPDATE builds SET modules = ?, total_cost = ?, min_loyalty_level = ? WHERE id = ?",
                        (json.dumps(module_ids), total_cost, max_loyalty, build_id)
                    )
        
        await conn.commit()


async def sync_from_api():
    """Синхронизация данных с tarkov.dev API."""
    try:
        print("\n🌐 Синхронизация с tarkov.dev API...")
        return await load_data_from_api()
    except Exception as e:
        print(f"⚠️  Ошибка синхронизации: {e}")
        print("   Продолжаем с локальными данными...")
        return False


async def start_bot():
    """Запуск бота."""
    print("\n🤖 Запуск бота...")
    print("=" * 60)
    
    import logging
    from aiogram import Bot, Dispatcher
    from aiogram.fsm.storage.memory import MemoryStorage
    from database.config import settings
    from handlers import common, search, builds, loyalty, tier_list, settings as settings_handler, dynamic_builds, budget_constructor, quest_builds, meta_builds_handler, admin
    from services.user_service import UserService
    from services.build_service import BuildService
    from services.random_build_service import RandomBuildService
    from services.admin_service import AdminService
    from api_clients import TarkovAPIClient
    from services.weapon_service import WeaponService
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Database already initialized
    from database import Database
    db = Database("data/eft_helper.db")
    
    # Initialize API client once (shared across all requests)
    api_client = TarkovAPIClient()
    
    # v5.1 AI Services
    print("\n🤖 Инициализация AI-ассистента...")
    ai_assistant = None
    ai_generation_service = None
    context_builder = None
    news_service = None
    
    try:
        from services import AIAssistant, AIGenerationService, ContextBuilder, NewsService
        
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
        
        print(f"   Ollama: {ollama_url}")
        print(f"   Model: {ollama_model}")
        logger.info(f"Initializing AI services: Ollama at {ollama_url}, model {ollama_model}")
        
        news_service = NewsService()
        print("   ✅ NewsService")
        context_builder = ContextBuilder(api_client, db)
        print("   ✅ ContextBuilder")
        ai_generation_service = AIGenerationService(api_client, db, ollama_url, ollama_model)
        print("   ✅ AIGenerationService")
        ai_assistant = AIAssistant(api_client, db, ai_generation_service, news_service)
        print("   ✅ AIAssistant")
        
        print("✅ AI-ассистент инициализирован!\n")
        logger.info("✅ AI services initialized successfully")
    except Exception as e:
        print(f"❌ Ошибка инициализации AI: {e}\n")
        logger.error(f"❌ Failed to initialize AI services: {e}", exc_info=True)
        logger.warning("⚠️  Bot will work without AI assistant")
    
    # Initialize bot and dispatcher
    bot = Bot(token=settings.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Register routers
    dp.include_router(common.router)
    dp.include_router(search.router)
    dp.include_router(builds.router)
    dp.include_router(loyalty.router)
    dp.include_router(tier_list.router)
    dp.include_router(settings_handler.router)
    dp.include_router(dynamic_builds.router)
    dp.include_router(budget_constructor.router)
    dp.include_router(quest_builds.router)
    dp.include_router(meta_builds_handler.router)
    dp.include_router(admin.router)  # Admin panel
    
    # Middleware to inject db and services into handlers
    @dp.update.outer_middleware()
    async def db_middleware(handler, event, data):
        # Use the shared API client instead of creating a new one
        data["db"] = db
        data["user_service"] = UserService(db)
        data["build_service"] = BuildService(db, api_client)
        data["random_build_service"] = RandomBuildService(api_client)
        data["admin_service"] = AdminService(db)
        data["api_client"] = api_client
        data["weapon_service"] = WeaponService(db, api_client)
        # v5.1 AI services
        data["ai_assistant"] = ai_assistant
        data["ai_generation_service"] = ai_generation_service
        data["context_builder"] = context_builder
        data["news_service"] = news_service
        return await handler(event, data)
    
    # Global error handler
    @dp.error()
    async def error_handler(event, **kwargs):
        exception = kwargs.get('exception')
        logger.error(f"Error occurred: {exception}", exc_info=True)
        return True
    
    logger.info("Bot starting...")
    
    try:
        # Start polling
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        # Clean up resources
        await bot.session.close()
        await api_client.close()
        logger.info("Bot stopped")


async def main():
    """Основная функция запуска."""
    print("=" * 60)
    print("  EFT Helper - Автоматический запуск")
    print("=" * 60)
    
    # 1. Проверка .env файла
    if not await check_env_file():
        print("\n❌ Запуск прерван. Настройте .env файл и запустите снова.")
        return
    
    # 2. Инициализация базы данных
    db = await init_database()
    
    # 3. Проверка содержимого базы
    db_content = await check_database_content(db)
    
    # 4. Автоматическая загрузка данных если база пустая
    if db_content["modules"] < 100:
        print("\n⚠️  База данных пуста или содержит мало данных!")
        print("\n📦 Автоматическая загрузка данных из API...")
        
        # Сначала загружаем тестовые данные для базовой структуры
        await populate_sample_data()
        
        # Затем загружаем полные данные из API
        success = await load_data_from_api()
        
        if not success:
            print("❌ Не удалось загрузить данные из API")
            print("   Используем базовые тестовые данные")
        else:
            print("✅ Данные загружены успешно!")
            
            # Обновляем сборки с новыми модулями
            print("\n🔧 Обновление сборок с модулями...")
            await update_builds_with_modules()
    
    # Финальная проверка
    db_content = await check_database_content(db)
    
    # 5. Финальная проверка
    print("\n✅ Все проверки пройдены!")
    print("=" * 60)
    
    # 6. Запуск бота
    await start_bot()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Бот остановлен пользователем")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
