"""
Main entry point for EFT Helper Telegram Bot.
Единственная точка входа для бота - следуйте техническому заданию.
"""
import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from database import Database
from api_clients import TarkovAPIClient
from services import WeaponService, BuildService, UserService, SyncService, AdminService
from services.random_build_service import RandomBuildService
from services import CompatibilityChecker, TierEvaluator, BuildGenerator
from services import ContextBuilder, AIGenerationService, AIAssistant
from handlers import common, search, builds, loyalty, tier_list, settings, budget
from handlers import community_builds, dynamic_builds, admin, quest_builds

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class BotApplication:
    """Main bot application class."""
    
    def __init__(self):
        # Configuration
        self.bot_token = os.getenv("BOT_TOKEN")
        if not self.bot_token or self.bot_token == "your_telegram_bot_token_here":
            raise ValueError("BOT_TOKEN not configured in .env file")
        
        # Database
        self.db = Database("data/eft_helper.db")
        
        # API Client (centralized)
        self.api_client = TarkovAPIClient()
        
        # Services (business logic layer)
        self.weapon_service = WeaponService(self.db, self.api_client)
        self.build_service = BuildService(self.db, self.api_client)
        self.user_service = UserService(self.db)
        self.sync_service = SyncService(self.db, self.api_client)
        self.random_build_service = RandomBuildService(self.api_client)
        self.admin_service = AdminService(self.db)
        
        # v3.0 Services
        self.compatibility_checker = CompatibilityChecker(self.api_client)
        self.tier_evaluator = TierEvaluator()
        self.build_generator = BuildGenerator(self.api_client, self.compatibility_checker, self.tier_evaluator)
        
        # News Service
        from services import NewsService
        self.news_service = NewsService()
        
        # v5.1 AI Services
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
        self.context_builder = ContextBuilder(self.api_client, self.db)
        self.ai_generation_service = AIGenerationService(self.api_client, self.db, ollama_url, ollama_model)
        self.ai_assistant = AIAssistant(self.api_client, self.db, self.ai_generation_service, self.news_service)
        
        # Bot and Dispatcher
        self.bot = Bot(token=self.bot_token)
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)
    
    async def setup(self):
        """Initialize database and prepare bot."""
        logger.info("Initializing database...")
        await self.db.init_db()
        logger.info("Database initialized successfully")
        
        # Автоматическое обновление цен при запуске
        await self.update_prices_on_startup()
    
    def register_handlers(self):
        """Register all bot handlers."""
        self.dp.include_router(common.router)
        self.dp.include_router(search.router)
        self.dp.include_router(builds.router)
        self.dp.include_router(quest_builds.router)  # Quest builds with AI
        self.dp.include_router(budget.router)  # v5.3 Budget builds
        self.dp.include_router(community_builds.router)  # v3.0
        self.dp.include_router(dynamic_builds.router)    # v3.0
        self.dp.include_router(loyalty.router)
        self.dp.include_router(tier_list.router)
        self.dp.include_router(settings.router)
        self.dp.include_router(admin.router)  # Admin panel
        
        logger.info("Handlers registered")
    
    def register_middleware(self):
        """Register middleware to inject dependencies."""
        @self.dp.update.outer_middleware()
        async def inject_services(handler, event, data):
            """Inject services into handlers."""
            data["db"] = self.db
            data["weapon_service"] = self.weapon_service
            data["build_service"] = self.build_service
            data["user_service"] = self.user_service
            data["api_client"] = self.api_client
            data["random_build_service"] = self.random_build_service
            data["admin_service"] = self.admin_service
            # v3.0 services
            data["compatibility_checker"] = self.compatibility_checker
            data["tier_evaluator"] = self.tier_evaluator
            data["build_generator"] = self.build_generator
            # v5.1 AI services
            data["ai_assistant"] = self.ai_assistant
            data["ai_generation_service"] = self.ai_generation_service
            data["context_builder"] = self.context_builder
            # News service
            data["news_service"] = self.news_service
            return await handler(event, data)
        
        @self.dp.error()
        async def error_handler(event, exception):
            """Global error handler."""
            logger.error(f"Error occurred: {exception}", exc_info=True)
            return True
        
        logger.info("Middleware registered")
    
    async def update_prices_on_startup(self):
        """Обновление цен с API при запуске бота."""
        try:
            logger.info("🔄 Проверка актуальности данных...")
            
            # Проверяем, есть ли данные в базе
            import aiosqlite
            async with aiosqlite.connect(self.db.db_path) as conn:
                async with conn.execute("SELECT COUNT(*) FROM weapons") as cursor:
                    weapons_count = (await cursor.fetchone())[0]
            
            if weapons_count > 0:
                logger.info("💰 Обновление цен с tarkov.dev API...")
                await self.sync_service.sync_weapons()
                await self.sync_service.sync_modules()
                logger.info("✅ Цены успешно обновлены")
            else:
                logger.info("⚠️  База данных пуста. Запустите синхронизацию вручную.")
        except Exception as e:
            logger.warning(f"⚠️  Не удалось обновить цены: {e}")
            logger.info("Бот продолжит работу с текущими данными")
    
    async def price_update_task(self):
        """Фоновая задача для периодического обновления цен."""
        while True:
            try:
                # Ждем 12 часов
                await asyncio.sleep(12 * 60 * 60)
                
                logger.info("🔄 Плановое обновление цен...")
                await self.sync_service.sync_weapons()
                await self.sync_service.sync_modules()
                logger.info("✅ Цены обновлены")
            except asyncio.CancelledError:
                logger.info("Задача обновления цен остановлена")
                break
            except Exception as e:
                logger.error(f"Ошибка при обновлении цен: {e}")
                # Продолжаем работу даже при ошибке
        
        logger.info("Middleware registered")
    
    async def start(self):
        """Start the bot."""
        await self.setup()
        self.register_handlers()
        self.register_middleware()
        
        logger.info("=" * 60)
        logger.info("  EFT Helper Bot Started")
        logger.info("  Автообновление цен: каждые 12 часов")
        
        # Check AI assistant availability
        ai_available = await self.ai_generation_service.check_ollama_available()
        if ai_available:
            logger.info("  ✅ AI Assistant (Nikita Buyanov) - ONLINE")
        else:
            logger.warning("  ⚠️  AI Assistant - OFFLINE (fallback mode)")
        
        logger.info("=" * 60)
        
        # Запускаем фоновую задачу обновления цен
        price_task = asyncio.create_task(self.price_update_task())
        
        try:
            await self.dp.start_polling(
                self.bot,
                allowed_updates=self.dp.resolve_used_update_types()
            )
        finally:
            # Останавливаем фоновую задачу
            price_task.cancel()
            try:
                await price_task
            except asyncio.CancelledError:
                pass
            await self.cleanup()
    
    async def cleanup(self):
        """Cleanup resources."""
        logger.info("Shutting down bot...")
        await self.bot.session.close()
        await self.api_client.close()
        logger.info("Bot stopped")


async def main():
    """Main function."""
    try:
        app = BotApplication()
        await app.start()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Critical error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    
    # Run bot
    asyncio.run(main())
