import asyncio
import logging
import sys
import aiohttp

# uvloop — быстрый event loop для Linux/macOS (даёт ~20-30% прирост I/O)
if sys.platform != "win32":
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        pass

# orjson — быстрая JSON сериализация (в 3-10x быстрее стандартного json)
try:
    import orjson
    
    def _orjson_dumps(data) -> str:
        return orjson.dumps(data).decode("utf-8")
    
    ORJSON_AVAILABLE = True
except ImportError:
    ORJSON_AVAILABLE = False

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession

from app.config import settings
from app.logger import setup_logging
from app.database.session import init_db
from app.database.models import Chat
from app.handlers import qna, games, achievements, auctions, quests, guilds, team_wars, duos, statistics, vision, random_responses, help
from app.handlers.trading import router as trading_router
from app.handlers.game_hub import router as game_hub_router
from app.handlers.gif_patrol import router as gif_patrol_router
from app.handlers.tournaments import router as tournaments_router
from app.handlers.health import router as health_router
from app.handlers.chat_join import router as chat_join_router
from app.handlers.voice import router as voice_router
from app.handlers.summarizer import router as summarizer_router
from app.handlers.topic_listener import router as topic_listener_router
from app.handlers.challenges import router as challenges_router
from app.handlers.tips import router as tips_router
from app.handlers.blackjack import router as blackjack_router
from app.handlers.broadcast import router as broadcast_router
from app.handlers.owner_panel import router as owner_panel_router
from app.handlers.admin_dashboard import router as admin_dashboard_router
from app.handlers.mini_games import router as mini_games_router
from app.handlers.shop import router as shop_router
from app.handlers.inventory import router as inventory_router
from app.services.content_downloader import router as content_downloader_router
from app.handlers.reactions import router as oleg_reactions_router
from app.handlers.marriages import router as marriages_router
from app.handlers.mafia import router as mafia_router
from app.middleware.logging import MessageLoggerMiddleware
from app.middleware.anti_click import AntiClickMiddleware
from app.middleware.feature_toggle import FeatureToggleMiddleware
from app.middleware.sdoc_filter import SDOCFilterMiddleware
from app.jobs.scheduler import setup_scheduler

# Логгер будет инициализирован в main()
logger = logging.getLogger(__name__)


async def set_bot_status(bot: Bot, online: bool = True):
    """Обновить статус бота в описании."""
    try:
        status = "🟢" if online else "🔴"
        base_desc = "Твой личный кибер-кентуха. Поясняю за железо, разгоняю скуку и баню душнил."
        # Короткое описание (показывается в профиле бота, макс 120 символов)
        await bot.set_my_short_description(
            short_description=f"{status} {base_desc}"
        )
        logger.info(f"Статус бота обновлён: {'Онлайн' if online else 'Офлайн'}")
    except Exception as e:
        logger.warning(f"Не удалось обновить статус бота: {e}")


async def on_startup(bot: Bot, dp: Dispatcher):
    """Действия при запуске бота."""
    # Ставим статус "Онлайн"
    await set_bot_status(bot, online=True)
    
    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("База данных инициализирована")
    
    # Инициализация достижений и квестов
    logger.info("Инициализация достижений и квестов...")
    from app.services.achievements import init_achievements
    from app.services.quests import init_quests
    await init_achievements()
    await init_quests()
    logger.info("Достижения и квесты инициализированы")
    
    # Register command scopes for different chat types
    logger.info("Регистрация команд для разных типов чатов...")
    from app.services.command_scope import setup_commands
    if await setup_commands(bot):
        logger.info("Команды зарегистрированы для групп и ЛС")
    else:
        logger.warning("Не удалось зарегистрировать команды, используются значения по умолчанию")
    
    # Initialize Redis
    if settings.redis_enabled:
        logger.info("Подключение к Redis...")
        from app.services.redis_client import redis_client
        await redis_client.connect()
        
        # Configure rate limiter to use Redis
        from app.middleware.rate_limit import rate_limiter
        rate_limiter.set_redis_client(redis_client)
        logger.info("Redis подключен и настроен для rate limiting")
        
        # Configure StateManager to use Redis for game sessions (Requirements 2.x)
        from app.services.state_manager import state_manager
        state_manager.set_redis_client(redis_client)
        logger.info("StateManager настроен для использования Redis")

    logger.info("Настройка планировщика задач...")
    await setup_scheduler(bot)
    logger.info("Планировщик запущен")



    # Инициализация антиспама
    if settings.antispam_enabled:
        logger.info("Инициализация антиспама...")
        from app.services.token_limiter import token_limiter
        if settings.owner_id:
            token_limiter.add_to_whitelist(settings.owner_id)
        token_limiter.burst_limit = settings.antispam_burst
        token_limiter.hourly_limit = settings.antispam_hourly
        logger.info(f"Антиспам: {settings.antispam_burst}/мин, {settings.antispam_hourly}/час")

    logger.info("Запуск фоновой задачи для случайных сообщений...")
    from app.handlers.random_responses import schedule_random_messages
    # Создаем задачу для периодических случайных сообщений
    random_task = asyncio.create_task(schedule_random_messages(bot))
    # Храним задачу в dispatcher, чтобы можно было корректно завершить при выключении
    if not hasattr(dp, 'tasks'):
        dp.tasks = []
    dp.tasks.append(random_task)
    logger.info("Фоновая задача для случайных сообщений запущена")

    # Воркеры запускаются всегда, проверка включения происходит в хендлере
    logger.info("Запуск воркеров загрузки контента...")
    from app.services.content_downloader import downloader
    await downloader.start_workers()
    logger.info(f"Воркеры загрузки контента запущены (функция {'включена' if settings.content_download_enabled else 'выключена по умолчанию'})")

    # Инициализация Whisper для распознавания голосовых
    if settings.voice_recognition_enabled:
        logger.info("Инициализация Whisper для распознавания голосовых...")
        from app.services.voice_recognition import init_whisper
        if await init_whisper():
            logger.info("Whisper инициализирован")
        else:
            logger.warning("Whisper не удалось инициализировать, распознавание голосовых недоступно")

    # Edge TTS не требует предзагрузки (работает через API)
    logger.info("TTS: используется Edge TTS (Microsoft API)")

    # Initialize Arq worker pool for heavy tasks
    if settings.worker_enabled and settings.redis_enabled:
        logger.info("Инициализация Arq worker pool...")
        try:
            from app.worker import get_arq_pool
            pool = await get_arq_pool()
            if pool:
                logger.info("Arq worker pool инициализирован")
            else:
                logger.warning("Не удалось инициализировать Arq worker pool")
        except Exception as e:
            logger.warning(f"Ошибка инициализации Arq worker pool: {e}")

    # Initialize default knowledge in RAG
    logger.info("Проверка дефолтных знаний в RAG...")
    try:
        from app.services.vector_db import vector_db
        import json
        from pathlib import Path
        
        if vector_db.client:
            collection_name = settings.chromadb_collection_name
            stats = vector_db.get_default_knowledge_stats(collection_name)
            
            # Читаем версию из JSON файла
            json_version = None
            knowledge_paths = [
                Path(__file__).parent / "data" / "default_knowledge.json",
                Path("app/data/default_knowledge.json"),
            ]
            for path in knowledge_paths:
                if path.exists():
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            json_data = json.load(f)
                            json_version = json_data.get("version", "unknown")
                            break
                    except Exception:
                        pass
            
            current_version = stats.get("version", "unknown")
            needs_reload = (
                stats.get("total", 0) == 0 or  # Нет фактов
                (json_version and json_version != current_version)  # Версия изменилась
            )
            
            if needs_reload:
                if stats.get("total", 0) > 0:
                    logger.info(f"Версия базы знаний изменилась: {current_version} -> {json_version}, перезагружаем...")
                    # Очищаем старые знания перед загрузкой новых
                    vector_db.clear_default_knowledge(collection_name)
                else:
                    logger.info("Дефолтные знания не найдены, загружаем...")
                
                result = vector_db.load_default_knowledge(collection_name)
                if result.get("error"):
                    logger.warning(f"Ошибка загрузки дефолтных знаний: {result['error']}")
                else:
                    logger.info(f"Загружено {result['loaded']} фактов из {result['categories']} категорий (v{result.get('version', '?')})")
            else:
                logger.info(f"Дефолтные знания уже загружены: {stats['total']} фактов (v{stats.get('version', '?')})")
        else:
            logger.warning("ChromaDB не инициализирована, пропускаем загрузку дефолтных знаний")
    except Exception as e:
        logger.warning(f"Ошибка инициализации дефолтных знаний: {e}")

    # SDOC Integration - синхронизация админов и топиков
    if settings.sdoc_exclusive_mode:
        logger.info("SDOC Mode: Олег работает только в Steam Deck OC")
        logger.info(f"SDOC Owner: {settings.sdoc_owner_id}")
        
        # Синхронизация админов будет выполнена при первом сообщении из группы
        # (когда узнаем chat_id)
        from app.services.sdoc_service import sdoc_service
        if settings.sdoc_chat_id:
            sdoc_service.chat_id = settings.sdoc_chat_id
            logger.info(f"SDOC Chat ID: {settings.sdoc_chat_id}")
            
            # Регистрируем группу SDOC в базе данных
            try:
                chat_info = await bot.get_chat(settings.sdoc_chat_id)
                async with async_session() as session:
                    from sqlalchemy import select
                    result = await session.execute(
                        select(Chat).where(Chat.id == settings.sdoc_chat_id)
                    )
                    existing_chat = result.scalar_one_or_none()
                    
                    if not existing_chat:
                        new_chat = Chat(
                            id=settings.sdoc_chat_id,
                            title=chat_info.title or "Steam Deck OC",
                            is_forum=getattr(chat_info, 'is_forum', False),
                            owner_user_id=settings.sdoc_owner_id
                        )
                        session.add(new_chat)
                        await session.commit()
                        logger.info(f"Группа SDOC зарегистрирована: {chat_info.title}")
                    else:
                        # Обновляем title если изменился
                        if existing_chat.title != chat_info.title:
                            existing_chat.title = chat_info.title
                            await session.commit()
                        logger.info(f"Группа SDOC уже в базе: {existing_chat.title}")
            except Exception as e:
                logger.warning(f"Не удалось зарегистрировать SDOC в базе: {e}")
            
            # Синхронизируем админов
            try:
                count = await sdoc_service.sync_admins(bot, settings.sdoc_chat_id)
                logger.info(f"Синхронизировано {count} админов SDOC")
                
                # Инициализируем топики
                from app.services.sdoc_service import init_sdoc_topics
                await init_sdoc_topics(settings.sdoc_chat_id)
            except Exception as e:
                logger.warning(f"Не удалось синхронизировать SDOC: {e}")
        else:
            logger.info("SDOC Chat ID не указан, будет определён автоматически")

    # Start metrics server
    if settings.metrics_enabled:
        logger.info("Запуск сервера метрик...")
        from app.services.metrics_server import metrics_server
        await metrics_server.start()
        logger.info(f"Сервер метрик запущен на порту {settings.metrics_port}")


def build_dp() -> Dispatcher:
    """Построить диспетчер с обработчиками."""
    dp = Dispatcher(storage=MemoryStorage())
    
    # Retry middleware — автоматический повтор при сетевых ошибках (должен быть первым)
    from app.middleware.retry import RetryMiddleware
    dp.message.outer_middleware(RetryMiddleware(max_retries=3, base_delay=1.0))
    dp.callback_query.outer_middleware(RetryMiddleware(max_retries=3, base_delay=1.0))
    
    # SDOC Filter — первый middleware, отсекает чужие группы
    if settings.sdoc_exclusive_mode:
        dp.message.outer_middleware(SDOCFilterMiddleware())
    
    dp.message.middleware(MessageLoggerMiddleware())
    dp.message.middleware(FeatureToggleMiddleware())  # Проверка включенных функций
    
    # Rate limiting (should be one of the first middlewares)
    from app.middleware.rate_limit import RateLimitMiddleware
    dp.message.outer_middleware(RateLimitMiddleware())
    
    # Anti-click protection for game buttons (Requirements 3.x)
    dp.callback_query.middleware(AntiClickMiddleware())

    # Routers
    dp.include_routers(
        health_router,  # Health check должен быть первым для быстрого ответа
        help.router,  # Help должен быть вторым для приоритета
        owner_panel_router,  # Панель владельца бота /owner (до qna!)
        admin_dashboard_router,  # Admin dashboard /admin (до qna!)
        broadcast_router,  # Broadcast wizard for admin announcements (Requirements 13.x)
        game_hub_router,  # Game Hub UI (Requirements 1.x) - before games for /games priority
        challenges_router,  # PvP challenges with consent (Requirements 8.x)
        blackjack_router,  # Blackjack game (Requirements 9.x)
        mini_games_router,  # New mini games v7.5 (fish, crash, dice, guess, war, wheel, loot, cockfight)
        shop_router,  # Shop system v7.5
        inventory_router,  # Unified inventory system v7.6 (Requirements 1.x)
        tournaments_router,  # Tournament standings (Requirements 10.5)
        games.router,
        voice_router,  # Роутер для голосовых сообщений (до qna, чтобы перехватить voice)
        summarizer_router,  # Роутер для пересказа контента (/tldr, /summary)
        tips_router,  # Советы для админов
        marriages_router,  # Роутер для системы браков (до qna!)
        mafia_router,  # Mafia game v9.5.0 (cooperative social deduction)
        qna.router,
        achievements.router,  # Достижения
        trading_router,  # Trading system v9.5 (trades, market, auctions)
        auctions.router,
        quests.router,  # Ежедневные квесты
        guilds.router,  # Гильдии
        team_wars.router,
        duos.router,  # Дуэты
        statistics.router,
        gif_patrol_router,  # GIF Patrol - анализ GIF на запрещённый контент (до vision)
        vision.router,  # Роутер для обработки изображений
        random_responses.router,  # Роутер для рандомных ответов
        oleg_reactions_router,  # Роутер для реакций на сообщения Олега (Requirements 8.x)
        content_downloader_router,  # Роутер для скачивания контента
        chat_join_router,  # Роутер для обработки событий добавления в чат
        topic_listener_router,  # Роутер для глобального слушателя топиков (RAG) - должен быть последним
    )
    return dp


async def main():
    """Главная функция бота."""
    logger.info("=" * 60)
    logger.info("ЗАПУСК БОТА ОЛЕГ")
    logger.info("=" * 60)
    logger.info(f"Модель: {settings.ollama_model}")
    logger.info(f"Redis: {'включен' if settings.redis_enabled else 'выключен'}")
    logger.info(f"Уровень логов: {settings.log_level}")
    
    # Логируем оптимизации
    if sys.platform != "win32":
        try:
            import uvloop
            logger.info("uvloop: включен")
        except ImportError:
            logger.info("uvloop: не установлен")
    else:
        logger.info("uvloop: недоступен на Windows")

    if not settings.bot_token:
        logger.error("TELEGRAM_BOT_TOKEN не установлен!")
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    # Создаём бота с orjson для быстрой сериализации (через monkey-patch)
    if ORJSON_AVAILABLE:
        import json
        # Патчим стандартный json модуль для использования orjson
        _original_dumps = json.dumps
        def _patched_dumps(*args, **kwargs):
            # Убираем несовместимые kwargs
            kwargs.pop('ensure_ascii', None)
            kwargs.pop('separators', None)
            kwargs.pop('indent', None)
            try:
                return orjson.dumps(args[0]).decode('utf-8') if args else '{}'
            except (TypeError, orjson.JSONEncodeError):
                return _original_dumps(*args, **kwargs)
        json.dumps = _patched_dumps
        logger.info("orjson: включен (monkey-patch json.dumps)")

    # Настраиваем сессию с HTTP прокси для обхода блокировок
    session = None
    if settings.mtproto_enabled:
        logger.info("Настраиваем HTTP прокси для обхода блокировок...")

        # Основной и fallback прокси
        proxy_list = [
            "http://127.0.0.1:8082",       # Основной (финский SOCKS5)
            "http://127.0.0.1:8083",       # Fallback 1
            "http://host.docker.internal:8082",  # Fallback 2
        ]

        for proxy_url in proxy_list:
            try:
                logger.info(f"Тестируем прокси {proxy_url}...")

                connector = aiohttp.TCPConnector()
                aio_session = aiohttp.ClientSession(connector=connector)

                async with aio_session.get(
                    f"https://api.telegram.org/bot{settings.bot_token}/getMe",
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        username = data["result"]["username"]
                        logger.info(f"✅ Прокси работает: {proxy_url} (бот: @{username})")
                        await aio_session.close()

                        # Патчим aiohttp чтобы ВСЕ запросы шли через этот прокси
                        _orig_request = aiohttp.ClientSession._request
                        async def _proxied_request(self, method, url, **kwargs):
                            kwargs['proxy'] = proxy_url
                            return await _orig_request(self, method, url, **kwargs)
                        aiohttp.ClientSession._request = _proxied_request

                        session = AiohttpSession()
                        break
                    else:
                        await aio_session.close()
            except Exception as e:
                logger.debug(f"Прокси {proxy_url} не работает: {type(e).__name__}")

    if session is None:
        logger.warning("⚠️ Ни один прокси не работает, пробуем напрямую...")
        session = AiohttpSession()

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML), session=session)
    
    dp = build_dp()

    await on_startup(bot, dp)

    logger.info("=" * 60)
    logger.info("БОТ ГОТОВ К РАБОТЕ")
    logger.info("=" * 60)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook удален, pending updates очищены")
        
        bot_info = await bot.get_me()
        logger.info(f"Бот: @{bot_info.username} (id: {bot_info.id})")
        logger.info("Начинаем polling...")
        
        # Mark polling as active for health checks
        if settings.metrics_enabled:
            from app.services.metrics_server import set_polling_active
            set_polling_active(True)
        
        await dp.start_polling(bot, skip_updates=True)
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logger.error(f"Критическая ошибка: {type(e).__name__}: {e}")
        raise
    finally:
        # Mark polling as inactive
        if settings.metrics_enabled:
            from app.services.metrics_server import set_polling_active
            set_polling_active(False)
        
        logger.info("=" * 60)
        logger.info("ОСТАНОВКА БОТА")
        logger.info("=" * 60)
        
        # Ставим статус "Офлайн"
        await set_bot_status(bot, online=False)
        
        logger.info("Остановка фоновых задач...")
        # Отменяем все задачи, которые мы сохранили в dp
        if hasattr(dp, 'tasks'):
            for task in dp.tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass  # Ожидаемое поведение при отмене

        logger.info("Фоновые задачи остановлены")

        logger.info("Остановка воркеров загрузки контента...")
        from app.services.content_downloader import downloader
        await downloader.stop_workers()
        logger.info("Воркеры загрузки контента остановлены")
        
        # Stop metrics server
        if settings.metrics_enabled:
            logger.info("Остановка сервера метрик...")
            from app.services.metrics_server import metrics_server
            await metrics_server.stop()
            logger.info("Сервер метрик остановлен")

        # Close Arq worker pool
        if settings.worker_enabled and settings.redis_enabled:
            logger.info("Закрытие Arq worker pool...")
            try:
                from app.worker import close_arq_pool
                await close_arq_pool()
                logger.info("Arq worker pool закрыт")
            except Exception as e:
                logger.warning(f"Ошибка закрытия Arq worker pool: {e}")

        # Close Redis connection
        if settings.redis_enabled:
            logger.info("Закрытие соединения с Redis...")
            from app.services.redis_client import redis_client
            await redis_client.close()
            logger.info("Redis соединение закрыто")

        # Close global httpx client for Ollama
        logger.info("Закрытие httpx клиентов...")
        from app.services.http_clients import close_all_clients
        await close_all_clients()
        logger.info("httpx клиенты закрыты")

        await bot.session.close()
        logger.info("Сессия бота закрыта")


if __name__ == "__main__":
    # Инициализировать логирование только при прямом запуске
    setup_logging()
    asyncio.run(main())
