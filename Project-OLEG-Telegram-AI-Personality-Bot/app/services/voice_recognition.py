"""Сервис распознавания голосовых сообщений (STT) на базе faster-whisper."""

import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

# Флаг доступности faster-whisper
_whisper_available = False
_whisper_model = None

try:
    from faster_whisper import WhisperModel
    _whisper_available = True
    logger.info("faster-whisper успешно импортирован")
except ImportError:
    logger.warning("faster-whisper не установлен. Распознавание голосовых недоступно. Установи: pip install faster-whisper")


async def init_whisper():
    """Инициализирует модель Whisper."""
    global _whisper_model
    
    if not _whisper_available:
        logger.warning("faster-whisper недоступен, пропускаем инициализацию")
        return False
    
    try:
        from app.config import settings
        model_name = settings.whisper_model
        
        # Устанавливаем зеркало HuggingFace если указано (для РФ)
        hf_mirror = getattr(settings, 'huggingface_mirror', None) or os.environ.get('HF_ENDPOINT')
        if hf_mirror:
            os.environ['HF_ENDPOINT'] = hf_mirror
            logger.info(f"Используется зеркало HuggingFace: {hf_mirror}")
        
        logger.info(f"Загрузка модели faster-whisper: {model_name}...")
        # CPU mode, int8 для скорости
        _whisper_model = WhisperModel(model_name, device="cpu", compute_type="int8")
        logger.info(f"Модель faster-whisper '{model_name}' загружена")
        return True
    except Exception as e:
        logger.error(f"Ошибка при загрузке модели faster-whisper: {e}")
        logger.error("Если HuggingFace недоступен, установи HF_ENDPOINT=https://hf-mirror.com в .env")
        return False


def is_available() -> bool:
    """Проверяет, доступно ли распознавание голоса."""
    return _whisper_available and _whisper_model is not None


async def transcribe_voice(file_path: str) -> Optional[str]:
    """
    Распознаёт речь из аудиофайла.
    
    Args:
        file_path: Путь к аудиофайлу (ogg, mp3, wav и т.д.)
        
    Returns:
        Распознанный текст или None при ошибке
    """
    if not is_available():
        logger.warning("faster-whisper недоступен для распознавания")
        return None
    
    if not os.path.exists(file_path):
        logger.error(f"Файл не найден: {file_path}")
        return None
    
    try:
        logger.info(f"Начинаю распознавание: {file_path}")
        
        # faster-whisper API
        segments, info = _whisper_model.transcribe(
            file_path,
            language="ru",
            beam_size=5
        )
        
        # Собираем текст из сегментов
        text = " ".join(segment.text for segment in segments).strip()
        
        if text:
            logger.info(f"Распознано: {text[:100]}...")
        else:
            logger.warning("Пустой результат распознавания")
            
        return text if text else None
        
    except Exception as e:
        logger.error(f"Ошибка при распознавании голоса: {e}")
        return None



async def transcribe_voice_message(bot, file_id: str) -> Optional[str]:
    """
    Скачивает и распознаёт голосовое сообщение из Telegram.
    
    Args:
        bot: Экземпляр бота
        file_id: ID файла в Telegram
        
    Returns:
        Распознанный текст или None
    """
    if not is_available():
        return None
    
    temp_file = None
    temp_path = None
    try:
        # Получаем информацию о файле
        file_info = await bot.get_file(file_id)
        
        # Создаём временный файл
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg")
        temp_path = temp_file.name
        temp_file.close()
        
        # Скачиваем файл
        await bot.download_file(file_info.file_path, destination=temp_path)
        logger.info(f"Голосовое скачано: {temp_path}")
        
        # Распознаём
        text = await transcribe_voice(temp_path)
        
        return text
        
    except Exception as e:
        logger.error(f"Ошибка при обработке голосового сообщения: {e}")
        return None
        
    finally:
        # Удаляем временный файл
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                logger.debug(f"Временный файл удалён: {temp_path}")
            except Exception as e:
                logger.warning(f"Не удалось удалить временный файл: {e}")


async def transcribe_video_note(bot, file_id: str) -> Optional[str]:
    """
    Скачивает видеосообщение (кружочек), извлекает аудио и распознаёт речь.
    
    Args:
        bot: Экземпляр бота
        file_id: ID файла в Telegram
        
    Returns:
        Распознанный текст или None
    """
    import subprocess
    
    if not is_available():
        return None
    
    temp_video = None
    temp_audio = None
    video_path = None
    audio_path = None
    try:
        # Получаем информацию о файле
        file_info = await bot.get_file(file_id)
        
        # Создаём временный файл для видео
        temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        video_path = temp_video.name
        temp_video.close()
        
        # Скачиваем видео
        await bot.download_file(file_info.file_path, destination=video_path)
        logger.info(f"Видеосообщение скачано: {video_path}")
        
        # Создаём временный файл для аудио
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        audio_path = temp_audio.name
        temp_audio.close()
        
        # Извлекаем аудио с помощью ffmpeg
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn",  # Без видео
            "-acodec", "pcm_s16le",  # WAV формат
            "-ar", "16000",  # 16kHz для Whisper
            "-ac", "1",  # Моно
            audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg ошибка: {result.stderr}")
            return None
        
        logger.info(f"Аудио извлечено: {audio_path}")
        
        # Распознаём
        text = await transcribe_voice(audio_path)
        
        return text
        
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg таймаут при извлечении аудио")
        return None
    except FileNotFoundError:
        logger.error("FFmpeg не найден. Установи ffmpeg для распознавания видеосообщений.")
        return None
    except Exception as e:
        logger.error(f"Ошибка при обработке видеосообщения: {e}")
        return None
        
    finally:
        # Удаляем временные файлы
        for path in [video_path, audio_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                    logger.debug(f"Временный файл удалён: {path}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить временный файл: {e}")
