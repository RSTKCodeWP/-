"""Модуль обработки изображений (Vision Module) для бота Олег.

Использует 2-step Vision Pipeline для анализа изображений:
Step 1: Vision model описывает изображение (скрыто от пользователя)
Step 2: Oleg LLM комментирует описание в своём стиле

Поддерживает:
- Одиночные фото
- Media groups (несколько фото за раз) — анализирует все и отвечает одним сообщением
"""

import asyncio
import logging
import random
import re
from typing import Optional, List, Dict
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from app.services.vision_pipeline import vision_pipeline
from app.services.ollama_client import is_ollama_available
from app.utils import safe_reply

logger = logging.getLogger(__name__)


# Триггеры для упоминания Олега
OLEG_TRIGGERS = ["олег", "олега", "олегу", "олегом", "олеге", "oleg"]

# Вероятность авто-ответа на изображения (2-5%)
AUTO_IMAGE_REPLY_PROBABILITY = 0.035  # 3.5% базовая вероятность

# Кэш для media_group — собираем фото из одной группы
# {media_group_id: {"messages": [Message], "processed": bool, "timer_task": Task}}
_media_group_cache: Dict[str, dict] = {}

# Время ожидания остальных фото из группы (секунды)
MEDIA_GROUP_WAIT_TIME = 1.0


def _contains_bot_mention(text: str, bot) -> bool:
    """
    Проверяет, содержит ли текст упоминание бота.
    
    Args:
        text: Текст для проверки (caption или message text)
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


async def should_process_image(msg: Message) -> tuple[bool, bool]:
    """
    Проверяет, нужно ли обрабатывать изображение.
    
    Бот обрабатывает изображение если:
    - В caption есть упоминание бота (@username или "олег")
    - Это ответ на сообщение бота
    - Авто-ответ сработал по вероятности (2-5%) - только для фото, НЕ для стикеров
    
    Args:
        msg: Сообщение с изображением
        
    Returns:
        Tuple (should_process, is_auto_reply)
        
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
    """
    # Проверяем доступность Ollama перед обработкой
    if not await is_ollama_available():
        logger.debug(f"Image processing: skipping - Ollama not available")
        return False, False
    
    # В личных сообщениях всегда обрабатываем изображения
    if msg.chat.type == "private":
        logger.debug(f"Image processing: private chat, processing message {msg.message_id}")
        return True, False
    
    # Проверяем caption на упоминание бота
    caption = msg.caption or ""
    if _contains_bot_mention(caption, msg.bot):
        logger.debug(f"Image processing: bot mentioned in caption for message {msg.message_id}")
        return True, False
    
    # Проверяем, является ли это ответом на сообщение бота
    if msg.reply_to_message and msg.reply_to_message.from_user:
        if msg.reply_to_message.from_user.id == msg.bot.id:
            logger.debug(f"Image processing: reply to bot message for message {msg.message_id}")
            return True, False
    
    # Авто-ответ на изображения с вероятностью 2-5% - только для фото, НЕ для стикеров
    if not msg.sticker and random.random() < AUTO_IMAGE_REPLY_PROBABILITY:
        logger.debug(f"Image processing: auto-reply triggered for message {msg.message_id}")
        return True, True
    
    logger.debug(f"Image processing: skipping message {msg.message_id} - no explicit mention")
    return False, False

router = Router()


# Legacy function kept for backward compatibility - now uses VisionPipeline
async def analyze_image_with_vlm(image_data: bytes, prompt: str) -> str:
    """
    Анализирует изображение с помощью 2-step Vision Pipeline.
    
    DEPRECATED: Используйте vision_pipeline.analyze() напрямую.

    Args:
        image_data: Байты изображения
        prompt: Текст запроса к модели (используется как user_query)

    Returns:
        Результат анализа изображения в стиле Олега
    """
    logger.info(f"analyze_image_with_vlm called (legacy), delegating to VisionPipeline")
    return await vision_pipeline.analyze(image_data, user_query=prompt if prompt else None)


async def extract_image_bytes(message: Message) -> Optional[bytes]:
    """
    Извлекает байты изображения из сообщения.
    
    Поддерживает фото, документы-изображения и стикеры.
    Стикеры конвертируются в PNG для анализа.

    Args:
        message: Сообщение с изображением

    Returns:
        Байты изображения или None
    """
    try:
        # Получаем самое большое фото из списка
        if message.photo:
            # Берем самое большое изображение (последнее в списке)
            photo = message.photo[-1]

            # Получаем file_info для загрузки
            file_info = await message.bot.get_file(photo.file_id)

            # Загружаем изображение
            file_bytes_io = await message.bot.download_file(file_info.file_path)
            image_bytes = file_bytes_io.read()
            return image_bytes
        elif message.document and message.document.mime_type and message.document.mime_type.startswith('image/'):
            # Если это документ изображения
            file_info = await message.bot.get_file(message.document.file_id)
            file_bytes_io = await message.bot.download_file(file_info.file_path)
            image_bytes = file_bytes_io.read()
            return image_bytes
        elif message.sticker:
            # Обрабатываем стикер как изображение
            sticker = message.sticker
            
            # Если это анимированный стикер (.tgs - Lottie JSON) - пропускаем
            # .tgs требует специальной обработки через lottie/rlottie
            if sticker.is_animated:
                logger.debug(f"Skipping animated .tgs sticker (requires lottie rendering)")
                return None
            
            # Если это видео-стикер (.webm) - извлекаем первый кадр
            if sticker.is_video:
                try:
                    # Получаем file_info для загрузки
                    file_info = await message.bot.get_file(sticker.file_id)
                    
                    # Загружаем видео-стикер
                    file_bytes_io = await message.bot.download_file(file_info.file_path)
                    video_bytes = file_bytes_io.read()
                    
                    # Извлекаем первый кадр через imageio
                    try:
                        import imageio.v3 as iio
                        import io
                        
                        # Читаем первый кадр
                        frames = iio.imiter(io.BytesIO(video_bytes), plugin='pyav')
                        first_frame = next(frames)
                        
                        # Конвертируем в PIL Image
                        from PIL import Image
                        img = Image.fromarray(first_frame)
                        
                        # Сохраняем как PNG
                        output = io.BytesIO()
                        img.save(output, format='PNG')
                        logger.info(f"Extracted first frame from video sticker")
                        return output.getvalue()
                        
                    except ImportError:
                        logger.warning("imageio[pyav] not available for video sticker processing")
                        return None
                    except Exception as e:
                        logger.warning(f"Failed to extract frame from video sticker: {e}")
                        return None
                        
                except Exception as e:
                    logger.error(f"Error processing video sticker: {e}")
                    return None
            
            # Обычный статичный стикер (.webp)
            # Получаем file_info для загрузки
            file_info = await message.bot.get_file(sticker.file_id)
            
            # Загружаем стикер (обычно .webp)
            file_bytes_io = await message.bot.download_file(file_info.file_path)
            sticker_bytes = file_bytes_io.read()
            
            # Конвертируем .webp в PNG для лучшей совместимости
            try:
                from PIL import Image
                import io
                
                img = Image.open(io.BytesIO(sticker_bytes))
                # Конвертируем в RGB если нужно
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                
                # Сохраняем как PNG
                output = io.BytesIO()
                img.save(output, format='PNG')
                return output.getvalue()
            except ImportError:
                # Если PIL не установлен, возвращаем как есть
                logger.warning("PIL not available, returning sticker as-is")
                return sticker_bytes
            except Exception as e:
                logger.warning(f"Failed to convert sticker: {e}, returning as-is")
                return sticker_bytes
        else:
            return None
    except Exception as e:
        logger.error(f"Ошибка при извлечении изображения: {e}")
        return None


@router.message(F.photo | F.document | F.sticker)
async def handle_image_message(msg: Message):
    """
    Обработчик сообщений с изображениями и стикерами.
    
    Обрабатывает изображение если:
    - Упоминание в caption (@username или "олег")
    - Ответ на сообщение бота
    - Авто-ответ сработал (2-5% вероятность)
    
    Стикеры обрабатываются как изображения (конвертируются в PNG).
    
    Поддерживает media_group — несколько фото за раз анализируются вместе.
    
    **Validates: Requirements 1.1, 1.4**
    """
    # Проверяем включена ли функция
    from app.services.bot_config import is_feature_enabled
    if msg.chat.type != "private" and not await is_feature_enabled(msg.chat.id, "vision"):
        return
    
    # Проверяем, нужно ли обрабатывать изображение
    should_process, is_auto_reply = await should_process_image(msg)
    if not should_process:
        return
    
    # Проверяем, есть ли текст рядом с изображением (для запроса)
    text = msg.caption if msg.caption else ""

    # Проверяем, не является ли это командой
    if text and text.startswith('/'):
        return

    # Если это media_group — собираем все фото и обрабатываем вместе
    if msg.media_group_id:
        await _handle_media_group(msg, is_auto_reply)
        return

    # Одиночное фото — обрабатываем сразу
    await _process_single_image(msg, is_auto_reply)


async def _handle_media_group(msg: Message, is_auto_reply: bool) -> None:
    """
    Обрабатывает фото из media_group.
    
    Собирает все фото из группы и анализирует их вместе.
    """
    global _media_group_cache
    
    group_id = msg.media_group_id
    
    # Добавляем сообщение в кэш группы
    if group_id not in _media_group_cache:
        _media_group_cache[group_id] = {
            "messages": [],
            "processed": False,
            "is_auto_reply": is_auto_reply,
            "timer_task": None
        }
    
    _media_group_cache[group_id]["messages"].append(msg)
    
    # Отменяем предыдущий таймер если есть
    if _media_group_cache[group_id]["timer_task"]:
        _media_group_cache[group_id]["timer_task"].cancel()
    
    # Запускаем таймер для обработки группы
    async def process_after_delay():
        await asyncio.sleep(MEDIA_GROUP_WAIT_TIME)
        await _process_media_group(group_id)
    
    _media_group_cache[group_id]["timer_task"] = asyncio.create_task(process_after_delay())


async def _process_media_group(group_id: str) -> None:
    """
    Обрабатывает собранную media_group.
    """
    global _media_group_cache
    
    if group_id not in _media_group_cache:
        return
    
    group_data = _media_group_cache[group_id]
    
    # Проверяем, не обработана ли уже
    if group_data["processed"]:
        return
    
    group_data["processed"] = True
    messages = group_data["messages"]
    is_auto_reply = group_data["is_auto_reply"]
    
    # Очищаем кэш
    del _media_group_cache[group_id]
    
    if not messages:
        return
    
    # Берём первое сообщение для ответа
    first_msg = messages[0]
    
    # Собираем caption из первого сообщения с caption
    user_query = None
    for m in messages:
        if m.caption and m.caption.strip():
            if not is_auto_reply:
                user_query = m.caption.strip()
            break
    
    from aiogram.exceptions import TelegramBadRequest
    
    try:
        # Показываем индикатор
        if not is_auto_reply:
            await safe_reply(first_msg, f"👀 Разглядываю {len(messages)} фото...")
        
        # Извлекаем байты всех изображений
        image_descriptions = []
        for idx, m in enumerate(messages, 1):
            image_bytes = await extract_image_bytes(m)
            if image_bytes:
                try:
                    description = await vision_pipeline._get_image_description(image_bytes)
                    if description:
                        image_descriptions.append(f"[Фото {idx}]: {description}")
                except Exception as e:
                    logger.warning(f"Error analyzing image {idx} in media_group: {e}")
        
        if not image_descriptions:
            if not is_auto_reply:
                await safe_reply(first_msg, "Хм, модель молчит. Попробуй другие картинки.")
            return
        
        # Объединяем описания всех фото
        combined_description = "\n\n".join(image_descriptions)
        
        # Генерируем комментарий Олега
        analysis_result = await vision_pipeline._generate_oleg_comment(
            f"Пользователь прислал {len(messages)} фото:\n{combined_description}",
            user_query
        )
        
        if not analysis_result or not analysis_result.strip():
            if not is_auto_reply:
                await safe_reply(first_msg, "Хм, модель молчит. Попробуй другие картинки.")
            return
        
        # Обрезаем если слишком длинный
        max_length = 4000
        if len(analysis_result) > max_length:
            analysis_result = analysis_result[:max_length] + "...\n\n[обрезано]"
        
        # Для авто-ответов добавляем префикс
        if is_auto_reply:
            prefixes = ["👀 ", "🤔 ", "Хм, ", "О, ", ""]
            analysis_result = random.choice(prefixes) + analysis_result
        
        await safe_reply(first_msg, analysis_result)
        
        logger.info(f"Processed media_group with {len(messages)} images in chat {first_msg.chat.id}")
        
    except TelegramBadRequest as e:
        if "thread not found" in str(e).lower() or "message to reply not found" in str(e).lower():
            logger.warning(f"Не удалось ответить на media_group - топик удалён: {e}")
        else:
            logger.error(f"Telegram ошибка при обработке media_group: {e}")
    except Exception as e:
        logger.error(f"Ошибка при обработке media_group: {e}")
        if not is_auto_reply:
            await safe_reply(first_msg, "Глаза мои разлюбили. Не могу разглядеть, что там на скринах.")


async def _process_single_image(msg: Message, is_auto_reply: bool) -> None:
    """
    Обрабатывает одиночное изображение.
    """
    text = msg.caption if msg.caption else ""
    
    # Skip animated stickers silently (they can't be processed)
    if msg.sticker and msg.sticker.is_animated:
        logger.debug(f"Skipping animated sticker in message {msg.message_id}")
        return
    
    # Проверяем, есть ли изображение
    image_bytes = await extract_image_bytes(msg)
    if not image_bytes:
        logger.warning(f"Не удалось извлечь изображение из сообщения {msg.message_id}")
        return

    # Используем текст как user_query для VisionPipeline
    user_query = None
    if not is_auto_reply and text and text.strip():
        user_query = text.strip()

    from aiogram.exceptions import TelegramBadRequest

    try:
        # Для авто-ответов не показываем индикатор процесса
        if not is_auto_reply:
            await safe_reply(msg, "👀 Разглядываю...")

        # Анализируем изображение через 2-step Vision Pipeline
        analysis_result = await vision_pipeline.analyze(image_bytes, user_query=user_query)

        # Проверяем на пустой результат
        if not analysis_result or not analysis_result.strip():
            if not is_auto_reply:
                fail_messages = [
                    "Хм, смотрю на это и мыслей ровно ноль. Попробуй другую картинку.",
                    "Глаза чё-то не видят ни хрена. Скинь чё-нить почётче.",
                    "Я хз чё это. Мазня какая-то. Давай другой скрин.",
                    "Ничего не разобрал. Видимо, зрение подводит. Попробуй ещё раз.",
                    "Пустота в голове. Не могу понять, чё тут нарисовано."
                ]
                await safe_reply(msg, random.choice(fail_messages))
            return
            
        # Обрезаем результат если слишком длинный
        max_length = 4000
        if len(analysis_result) > max_length:
            analysis_result = analysis_result[:max_length] + "...\n\n[слишком много инфы, лень читать]"

        # Для авто-ответов добавляем префикс
        if is_auto_reply:
            prefixes = ["👀 ", "🤔 ", "Хм, ", "О, ", "Ничёсе, ", "Гляди-ка, "]
            analysis_result = random.choice(prefixes) + analysis_result

        # Определяем формат ответа (текст/голос/видео) используя глобальные настройки
        from app.services.ollama_client import get_global_voice_chance, get_global_video_chance
        import random as _random
        
        voice_chance = get_global_voice_chance()
        video_chance = get_global_video_chance()
        
        # Бросаем кубики (приоритет: Видео -> Голос -> Текст)
        roll = _random.random()
        should_video = roll < video_chance
        should_voice = not should_video and (roll < (video_chance + voice_chance))
        
        video_sent = False
        voice_sent = False
        
        # --- ПОПЫТКА ОТПРАВИТЬ ВИДЕО ---
        if should_video:
            try:
                from app.services.tts import tts_service
                template_path = "assets/video_templates/default.mp4"
                
                import os
                if os.path.exists(template_path):
                    voice_result = await tts_service.generate_voice(analysis_result)
                    if voice_result:
                        from app.handlers.qna import _send_video_note_fallback
                        video_sent = await _send_video_note_fallback(msg, voice_result, template_path)
                
                if not video_sent:
                    should_voice = True
            except Exception as e:
                logger.warning(f"Video generation failed for vision: {e}")
                should_voice = True
        
        # --- ПОПЫТКА ОТПРАВИТЬ ГОЛОС ---
        if should_voice and not video_sent:
            try:
                from app.services.tts import tts_service
                from aiogram.types import BufferedInputFile
                
                result = await tts_service.generate_voice(analysis_result)
                if result is not None:
                    voice_file = BufferedInputFile(
                        file=result.audio_data,
                        filename="voice.mp3"
                    )
                    await msg.reply_voice(
                        voice=voice_file,
                        caption=None,
                        duration=int(result.duration_seconds)
                    )
                    voice_sent = True
            except Exception as e:
                logger.warning(f"Voice generation failed for vision: {e}")
        
        # --- ТЕКСТОВЫЙ ОТВЕТ (если голос/видео не сработали) ---
        if not video_sent and not voice_sent:
            await safe_reply(msg, analysis_result)
        
        if is_auto_reply:
            logger.info(f"Auto-reply to image in chat {msg.chat.id}")

    except TelegramBadRequest as e:
        if "thread not found" in str(e).lower() or "message to reply not found" in str(e).lower():
            logger.warning(f"Не удалось ответить - топик/сообщение удалено: {e}")
        else:
            logger.error(f"Telegram ошибка при обработке изображения: {e}")
    except Exception as e:
        logger.error(f"Ошибка при обработке изображения: {e}")
        if not is_auto_reply:
            fail_exceptions = [
                "Глаза мои разлюбили. Не могу разглядеть, что там на скрине.",
                "Чё-то в глаз попало, не вижу ни черта. Попробуй позже.",
                "Зрение подвело. Видимо, пора в отпуск.",
                "Не разберу. Картинка — мыло, или я просто устал."
            ]
            await safe_reply(msg, random.choice(fail_exceptions))


# Команда для проверки работы модуля зрения
@router.message(Command("vision_test"))
async def cmd_vision_test(msg: Message):
    """
    Команда для тестирования модуля зрения.
    """
    await msg.reply(
        "📸 Модуль зрения активирован!\n"
        "Пришли фото со своим вопросом в описании, и я всё рассмотрю и отвечу по существу."
    )