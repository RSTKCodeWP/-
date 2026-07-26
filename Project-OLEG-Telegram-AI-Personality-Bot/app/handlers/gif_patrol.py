"""
GIF Patrol Handler - обработчик GIF-анимаций для модерации.

Перехватывает GIF/анимации и анализирует их на запрещённый контент
через GIFPatrolService.

NOTE: GIF patrol is currently work in progress. 
Analysis is disabled by default and can be enabled per-chat in admin panel.

**Feature: fortress-update**
**Validates: Requirements 3.3, 3.4, 3.5**
"""

import logging
import random
import re
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

from app.services.gif_patrol import gif_patrol_service, GIFAnalysisResult
from app.services.alive_ui import alive_ui_service
from app.services.ollama_client import is_ollama_available
from app.utils import safe_reply

logger = logging.getLogger(__name__)

router = Router()

# Максимальный размер файла для анализа (20MB)
MAX_FILE_SIZE = 20 * 1024 * 1024

# Таймаут для анализа GIF (секунды)
ANALYSIS_TIMEOUT = 5.0

# Триггеры для упоминания Олега
OLEG_TRIGGERS = ["олег", "олега", "олегу", "олегом", "олеге", "oleg"]

# Вероятность авто-ответа на GIF (аналогично фото)
AUTO_GIF_REPLY_PROBABILITY = 0.035  # 3.5%


async def extract_animation_bytes(message: Message, bot: Bot) -> Optional[bytes]:
    """
    Извлекает байты анимации из сообщения.
    
    Args:
        message: Сообщение с анимацией
        bot: Экземпляр бота
        
    Returns:
        Байты анимации или None
    """
    try:
        animation = message.animation
        if not animation:
            return None
        
        # Проверяем размер файла
        if animation.file_size and animation.file_size > MAX_FILE_SIZE:
            logger.warning(f"Animation too large: {animation.file_size} bytes")
            return None
        
        # Получаем file_info для загрузки
        file_info = await bot.get_file(animation.file_id)
        
        # Загружаем файл
        file_bytes_io = await bot.download_file(file_info.file_path)
        return file_bytes_io.read()
        
    except Exception as e:
        logger.error(f"Error extracting animation: {e}")
        return None


async def handle_unsafe_content(
    message: Message, 
    result: GIFAnalysisResult,
    bot: Bot
) -> None:
    """
    Обрабатывает обнаружение небезопасного контента.
    
    Args:
        message: Сообщение с GIF
        result: Результат анализа
        bot: Экземпляр бота
    """
    try:
        # Удаляем сообщение
        await message.delete()
        
        # Формируем причину
        categories = ", ".join(result.detected_categories)
        
        # Баним пользователя
        try:
            await bot.ban_chat_member(
                chat_id=message.chat.id,
                user_id=message.from_user.id
            )
            logger.info(
                f"Banned user {message.from_user.id} in chat {message.chat.id} "
                f"for inappropriate GIF content: {categories}"
            )
        except TelegramBadRequest as e:
            # Возможно, нет прав на бан
            logger.warning(f"Could not ban user: {e}")
        
        # Отправляем уведомление в чат
        notification = (
            f"🚫 GIF-патруль обнаружил запрещённый контент ({categories}) "
            f"от пользователя {message.from_user.full_name}. "
            f"Сообщение удалено, пользователь заблокирован."
        )
        
        thread_id = getattr(message, 'message_thread_id', None)
        try:
            # Для форумов используем прямой API
            if thread_id is not None:
                import httpx
                bot_token = bot.token
                api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    "chat_id": message.chat.id,
                    "text": notification,
                    "message_thread_id": thread_id
                }
                async with httpx.AsyncClient() as client:
                    await client.post(api_url, json=payload)
            else:
                await bot.send_message(chat_id=message.chat.id, text=notification)
        except TelegramBadRequest:
            pass  # Игнорируем ошибки отправки уведомления
            
    except Exception as e:
        logger.error(f"Error handling unsafe content: {e}")


async def queue_for_later_analysis(
    message: Message,
    file_id: str
) -> None:
    """
    Ставит GIF в очередь для отложенного анализа.
    
    Используется когда Vision модель недоступна.
    
    Args:
        message: Сообщение с GIF
        file_id: Telegram file_id
    """
    try:
        task_id = await gif_patrol_service.queue_analysis(
            message_id=message.message_id,
            chat_id=message.chat.id,
            file_id=file_id
        )
        logger.info(f"Queued GIF for later analysis: {task_id}")
    except Exception as e:
        logger.error(f"Error queuing GIF for analysis: {e}")


def _contains_bot_mention(text: str, bot) -> bool:
    """
    Проверяет, содержит ли текст упоминание бота.
    
    Args:
        text: Текст для проверки (caption)
        bot: Объект бота для получения username
        
    Returns:
        True если текст содержит упоминание бота
    """
    if not text:
        return False
    
    text_lower = text.lower()
    
    # Проверяем @username бота
    if bot and bot._me and bot._me.username:
        bot_username = bot._me.username.lower()
        if f"@{bot_username}" in text_lower:
            return True
    
    # Проверяем слово "олег" и его формы как отдельное слово
    for trigger in OLEG_TRIGGERS:
        if re.search(rf'\b{trigger}\b', text_lower):
            return True
    
    return False


async def should_process_gif(msg: Message) -> tuple[bool, bool]:
    """
    Проверяет, нужно ли обрабатывать GIF.
    
    Бот обрабатывает GIF если:
    - Это личное сообщение (всегда обрабатываем)
    - В caption есть упоминание бота (@username или "олег")
    - Это ответ на сообщение бота
    - Авто-ответ сработал по вероятности (3.5%)
    
    Args:
        msg: Сообщение с GIF
        
    Returns:
        Tuple (should_process, is_auto_reply)
    """
    # Проверяем доступность Ollama перед обработкой
    if not await is_ollama_available():
        logger.debug(f"GIF processing: skipping - Ollama not available")
        return False, False
    
    # В личных сообщениях всегда обрабатываем
    if msg.chat.type == "private":
        logger.debug(f"GIF processing: private chat, processing message {msg.message_id}")
        return True, False
    
    # Проверяем caption на упоминание бота
    caption = msg.caption or ""
    if _contains_bot_mention(caption, msg.bot):
        logger.debug(f"GIF processing: bot mentioned in caption for message {msg.message_id}")
        return True, False
    
    # Проверяем, является ли это ответом на сообщение бота
    if msg.reply_to_message and msg.reply_to_message.from_user:
        if msg.reply_to_message.from_user.id == msg.bot.id:
            logger.debug(f"GIF processing: reply to bot message for message {msg.message_id}")
            return True, False
    
    # Авто-ответ на GIF с вероятностью 3.5%
    if random.random() < AUTO_GIF_REPLY_PROBABILITY:
        logger.debug(f"GIF processing: auto-reply triggered for message {msg.message_id}")
        return True, True
    
    logger.debug(f"GIF processing: skipping message {msg.message_id} - no explicit mention")
    return False, False


async def is_gif_patrol_enabled(chat_id: int) -> bool:
    """
    Проверяет, включен ли GIF patrol для чата.
    
    GIF patrol отключен по умолчанию (work in progress).
    
    Args:
        chat_id: ID чата
        
    Returns:
        True если GIF patrol включен
    """
    # GIF patrol отключен после удаления системы модерации
    return False


@router.message(F.animation)
async def handle_animation_message(message: Message, bot: Bot):
    """
    Обработчик сообщений с GIF/анимациями.
    
    GIF patrol (модерация) отключен по умолчанию - work in progress.
    Распознавание GIF работает как для фото - рандомно или по запросу.
    
    **Validates: Requirements 3.3, 3.4, 3.5**
    """
    # Проверяем включена ли функция (только для групп)
    from app.services.bot_config import is_feature_enabled
    if message.chat.type != "private" and not await is_feature_enabled(message.chat.id, "vision"):
        return
    
    # Пропускаем сообщения без отправителя (системные)
    if not message.from_user:
        return
    
    # Пропускаем сообщения от ботов
    if message.from_user.is_bot:
        return
    
    animation = message.animation
    if not animation:
        return
    
    # Проверяем, включен ли GIF patrol для этого чата
    gif_patrol_active = await is_gif_patrol_enabled(message.chat.id)
    
    if gif_patrol_active:
        # GIF patrol включен - сканируем каждую гифку на запрещённый контент
        logger.info(
            f"GIF patrol active: processing animation from user {message.from_user.id} "
            f"in chat {message.chat.id}"
        )
        await _process_gif_patrol(message, bot, animation)
    else:
        # GIF patrol отключен - работаем как с фото (рандомно или по запросу)
        should_process, is_auto_reply = await should_process_gif(message)
        if not should_process:
            return
        
        logger.info(
            f"Processing GIF from user {message.from_user.id} "
            f"in chat {message.chat.id} (auto_reply={is_auto_reply})"
        )
        await _process_gif_vision(message, bot, animation, is_auto_reply)


async def _process_gif_patrol(message: Message, bot: Bot, animation) -> None:
    """
    Обрабатывает GIF через patrol (модерация на запрещённый контент).
    """
    # Извлекаем байты анимации
    animation_bytes = await extract_animation_bytes(message, bot)
    
    if not animation_bytes:
        # Не удалось загрузить - ставим в очередь на потом
        await queue_for_later_analysis(message, animation.file_id)
        return
    
    # Start Alive UI status for GIF analysis
    status = None
    thread_id = getattr(message, 'message_thread_id', None)
    try:
        status = await alive_ui_service.start_status(
            message.chat.id, "gif", bot, message_thread_id=thread_id
        )
        
        # Анализируем GIF
        result = await gif_patrol_service.analyze_gif(animation_bytes)
        
        # Clean up status message
        if status:
            await alive_ui_service.finish_status(status, bot)
            status = None
        
        # Проверяем на ошибку анализа (Vision недоступен)
        if result.error:
            logger.warning(f"GIF analysis error: {result.error}")
            await queue_for_later_analysis(message, animation.file_id)
            return
        
        # Если контент небезопасен - принимаем меры
        if not result.is_safe:
            logger.warning(
                f"Unsafe GIF detected from user {message.from_user.id}: "
                f"{result.detected_categories}"
            )
            await handle_unsafe_content(message, result, bot)
        else:
            logger.debug(
                f"GIF from user {message.from_user.id} passed analysis"
            )
            
    except Exception as e:
        logger.error(f"Error analyzing GIF: {e}")
        
        if status:
            await alive_ui_service.show_error(status, "Ошибка анализа GIF", bot)
        
        await queue_for_later_analysis(message, animation.file_id)


async def _process_gif_vision(message: Message, bot: Bot, animation, is_auto_reply: bool) -> None:
    """
    Обрабатывает GIF через vision pipeline.
    
    Анализирует 3 кадра (начало, середина, конец) для полного понимания анимации.
    """
    import random
    from app.services.vision_pipeline import vision_pipeline
    
    # Извлекаем байты анимации
    animation_bytes = await extract_animation_bytes(message, bot)
    
    if not animation_bytes:
        if not is_auto_reply:
            await safe_reply(message, "Не удалось загрузить гифку 😕")
        return
    
    # Извлекаем 3 кадра (начало, середина, конец)
    frames = []
    try:
        frames = gif_patrol_service.extract_frames(animation_bytes)
    except Exception as e:
        logger.warning(f"Error extracting GIF frames: {e}")
    
    if not frames:
        logger.warning("Failed to extract frames from animation, cannot analyze")
        if not is_auto_reply:
            await safe_reply(message, "Не смог разобрать эту гифку — формат не поддерживается 😕")
        return
    
    # Используем caption как user_query
    user_query = None
    caption = message.caption or ""
    if not is_auto_reply and caption.strip():
        user_query = caption.strip()
    
    try:
        # Для авто-ответов не показываем индикатор процесса
        if not is_auto_reply:
            await safe_reply(message, "👀 Разглядываю гифку (3 кадра)...")
        
        # Анализируем все 3 кадра и собираем описания
        frame_descriptions = []
        frame_labels = ["начало", "середина", "конец"]
        
        for idx, frame_bytes in enumerate(frames):
            try:
                # Получаем описание кадра напрямую от Vision модели
                description = await vision_pipeline._get_image_description(frame_bytes)
                if description:
                    frame_descriptions.append(f"[{frame_labels[idx]}]: {description}")
            except Exception as e:
                logger.warning(f"Error analyzing frame {idx}: {e}")
        
        if not frame_descriptions:
            if not is_auto_reply:
                await safe_reply(message, "Хм, модель молчит. Попробуй другую гифку.")
            return
        
        # Объединяем описания всех кадров
        combined_description = "\n".join(frame_descriptions)
        
        # Генерируем комментарий Олега на основе всех кадров
        analysis_result = await vision_pipeline._generate_oleg_comment(
            f"Это GIF-анимация из {len(frames)} кадров:\n{combined_description}",
            user_query
        )
        
        if not analysis_result or not analysis_result.strip():
            if not is_auto_reply:
                fail_messages = [
                    "Чё-то я залип и ничего не понял. Скинь другую гифку.",
                    "Глаза замылились, не разберу что тут происходит. Давай следующую.",
                    "Я чё-то втыкаю в эту анимацию и мыслей ноль. Попробуй другую.",
                    "Эта гифка сломала мне мозг. Есть чё попроще?",
                    "Не, я пас. Хрень какая-то, не могу разобрать."
                ]
                await safe_reply(message, random.choice(fail_messages))
            return
        
        # Обрезаем результат если слишком длинный
        max_length = 4000
        if len(analysis_result) > max_length:
            analysis_result = analysis_result[:max_length] + "...\n\n[обрезано]"
        
        # Для авто-ответов добавляем префикс
        if is_auto_reply:
            prefixes = ["👀 ", "🤔 ", "Хм, ", "О, гифка! ", ""]
            analysis_result = random.choice(prefixes) + analysis_result
        
        # Используем safe_reply для корректной работы в старых топиках форума
        await safe_reply(message, analysis_result)
        
        if is_auto_reply:
            logger.info(f"Auto-reply to GIF in chat {message.chat.id}")
            
    except TelegramBadRequest as e:
        if "thread not found" in str(e).lower() or "message to reply not found" in str(e).lower():
            logger.warning(f"Не удалось ответить на GIF - топик/сообщение удалено: {e}")
        else:
            logger.error(f"Telegram ошибка при обработке GIF: {e}")
    except Exception as e:
        logger.error(f"Ошибка при обработке GIF: {e}")
        if not is_auto_reply:
            await safe_reply(message, "Не смог разглядеть гифку 😕")
