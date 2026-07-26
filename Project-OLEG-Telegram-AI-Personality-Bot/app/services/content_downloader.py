"""Модуль для автоматического скачивания контента по ссылкам."""

import asyncio
import logging
import os
import tempfile
import re
from typing import Optional, Tuple, NamedTuple
from urllib.parse import urlparse
from asyncio import Queue

import yt_dlp  # Используем yt-dlp для скачивания
from aiogram import Router, F
from aiogram.types import Message

logger = logging.getLogger(__name__)

router = Router()

# Паттерны для распознавания ссылок
LINK_PATTERNS = {
    'youtube': [
        r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})',
    ],
    'tiktok': [
        r'(?:https?:\/\/)?(?:www\.)?tiktok\.com\/@[\w.]+\/video\/(\d+)',
        r'(?:https?:\/\/)?vm\.tiktok\.com\/[a-zA-Z0-9]+\/?',
    ],
    'vkontakte_video': [
        r'(?:https?:\/\/)?(?:www\.)?vk\.com\/video([a-zA-Z0-9_-]+)',
        r'(?:https?:\/\/)?(?:www\.)?vk\.com\/clip([a-zA-Z0-9_-]+)',
    ],
    'vkontakte_music': [
        r'(?:https?:\/\/)?(?:www\.)?vk\.com\/audio([a-zA-Z0-9_-]+)',
        r'(?:https?:\/\/)?(?:www\.)?vk\.com\/music\/album\/([a-zA-Z0-9_-]+)',
    ],
    'soundcloud': [
        r'(?:https?:\/\/)?(?:www\.)?soundcloud\.com\/[\w\/-]+',
    ],
    'yandex_music': [
        r'(?:https?:\/\/)?(?:www\.)?music\.yandex\.ru\/album\/\d+\/track\/\d+',
        r'(?:https?:\/\/)?(?:www\.)?music\.yandex\.ru\/users\/[\w\/-]+',
    ],
    'spotify': [
        r'(?:https?:\/\/)?open\.spotify\.com\/track\/[a-zA-Z0-9]+',
        r'(?:https?:\/\/)?open\.spotify\.com\/playlist\/[a-zA-Z0-9]+',
    ],
    'instagram': [
        r'(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:p|reel)\/([a-zA-Z0-9_-]+)',
    ],
}

# Ограничение размера файла для Telegram (50 МБ для видео, 50 МБ для аудио)
TELEGRAM_FILE_SIZE_LIMIT = 50 * 1024 * 1024  # 50 МБ

class DownloadTask(NamedTuple):
    """Задача для загрузки контента."""
    url: str
    target_chat_id: int
    message: Message


class ContentDownloader:
    """Класс для скачивания контента из различных источников."""

    def __init__(self):
        self.download_queue = Queue()  # Очередь задач на загрузку
        self.active_downloads = set()  # Набор активных задач скачивания
        self.max_concurrent_downloads = 2  # Максимум одновременных скачиваний
        self.download_workers = []  # Список воркеров для обработки очереди

    async def start_workers(self):
        """Запускает воркеров для обработки очереди."""
        for i in range(self.max_concurrent_downloads):
            worker = asyncio.create_task(self._download_worker(i))
            self.download_workers.append(worker)
        logger.info(f"Запущено {self.max_concurrent_downloads} воркеров для загрузки контента")

    async def stop_workers(self):
        """Останавливает все воркеры."""
        # Добавляем специальные задачи для остановки
        for _ in range(self.max_concurrent_downloads):
            await self.download_queue.put(None)

        # Ждем завершения всех воркеров
        for worker in self.download_workers:
            await worker
        self.download_workers.clear()
        logger.info("Все воркеры для загрузки контента остановлены")

    async def _download_worker(self, worker_id: int):
        """Рабочий процесс, который обрабатывает очередь загрузок."""
        logger.info(f"Воркер {worker_id} запущен")
        try:
            while True:
                # Получаем задачу из очереди
                task = await self.download_queue.get()

                # Если задача None, это сигнал остановки
                if task is None:
                    logger.info(f"Воркер {worker_id} получил сигнал остановки")
                    break

                try:
                    # Добавляем задачу в активные
                    self.active_downloads.add(task.url)
                    logger.info(f"Воркер {worker_id} начал обработку задачи: {task.url}")

                    # Выполняем загрузку
                    await self._download_and_send(task.url, task.target_chat_id, task.message)
                except Exception as e:
                    logger.error(f"Ошибка в воркере {worker_id} при обработке {task.url}: {e}")
                    try:
                        await task.message.reply(f"Ошибка при загрузке: {str(e)}")
                    except:
                        pass  # Игнорируем ошибки при отправке сообщения об ошибке
                finally:
                    # Удаляем задачу из активных
                    self.active_downloads.discard(task.url)
                    self.download_queue.task_done()
                    logger.info(f"Воркер {worker_id} завершил обработку задачи: {task.url}")
        except asyncio.CancelledError:
            logger.info(f"Воркер {worker_id} был отменён")
        finally:
            logger.info(f"Воркер {worker_id} остановлен")
        
    def detect_content_type(self, url: str) -> Optional[str]:
        """
        Определяет источник контента по URL.
        
        Args:
            url: URL для анализа
            
        Returns:
            Название источника или None
        """
        for source_name, patterns in LINK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return source_name
        return None
    
    def is_audio_source(self, source: str) -> bool:
        """Проверяет, является ли источник аудио-контентом."""
        audio_sources = ['soundcloud', 'yandex_music', 'spotify', 'vkontakte_music']
        return source in audio_sources
    
    async def download_content(self, url: str, target_chat_id: int, message: Message) -> bool:
        """
        Добавляет задачу на скачивание контента в очередь.

        Args:
            url: URL контента для скачивания
            target_chat_id: ID чата для отправки
            message: Оригинальное сообщение

        Returns:
            True если задача добавлена в очередь
        """
        # Проверяем, не в процессе ли уже загрузки этот URL
        if url in self.active_downloads:
            await message.reply("Этот контент уже скачивается, подожди.")
            return False

        # Добавляем задачу в очередь
        task = DownloadTask(url, target_chat_id, message)
        await self.download_queue.put(task)
        await message.reply("Контент добавлен в очередь на скачивание...")

        logger.info(f"Задача на скачивание добавлена в очередь: {url}")
        return True
    
    async def _download_and_send(self, url: str, target_chat_id: int, message: Message) -> bool:
        """Внутренняя функция для скачивания и отправки контента."""
        source = self.detect_content_type(url)
        if not source:
            return False
        
        is_audio = self.is_audio_source(source)

        try:
            # Временный файл для скачивания
            ext = '.mp3' if is_audio else '.mp4'
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                file_path = tmp_file.name

            # Настройки для yt-dlp
            ydl_opts = {
                'outtmpl': file_path.rsplit('.', 1)[0] + '.%(ext)s',  # Позволяем yt-dlp выбрать расширение
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
            }

            # Добавляем настройки в зависимости от типа контента
            if is_audio:
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })
            else:
                ydl_opts.update({
                    'format': 'best[height<=720][ext=mp4]/best[height<=720]/best',
                })

            # Скачивание
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

                # Ищем скачанный файл
                base_path = file_path.rsplit('.', 1)[0]
                actual_file = None
                for ext in ['.mp3', '.mp4', '.webm', '.m4a', '.ogg', '.opus']:
                    candidate = base_path + ext
                    if os.path.exists(candidate):
                        actual_file = candidate
                        break
                
                if not actual_file:
                    logger.error(f"Файл не найден после скачивания: {base_path}.*")
                    await message.reply("Не удалось скачать контент. Попробуй позже.")
                    return False
                
                file_path = actual_file
                file_size = os.path.getsize(file_path)

                # Проверяем размер файла
                if file_size > TELEGRAM_FILE_SIZE_LIMIT:
                    os.unlink(file_path)
                    content_name = "Аудио" if is_audio else "Видео"
                    await message.reply(
                        f"{content_name} слишком жирное ({file_size / (1024*1024):.1f} МБ). "
                        f"Максимум для Telegram: {TELEGRAM_FILE_SIZE_LIMIT / (1024*1024):.1f} МБ. "
                        f"Скачивай сам, ленивая жопа."
                    )
                    return False

                # Отправляем контент в зависимости от типа
                if is_audio:
                    await self._send_audio(message.bot, target_chat_id, file_path, info)
                else:
                    await self._send_video(message.bot, target_chat_id, file_path, info)

                # Удаляем временный файл после отправки
                if os.path.exists(file_path):
                    os.unlink(file_path)

                logger.info(f"Контент {url} успешно скачан и отправлен в чат {target_chat_id}")
                return True

        except Exception as e:
            # Убедимся, что файл удалён в случае ошибки
            try:
                if 'file_path' in locals() and os.path.exists(file_path):
                    os.unlink(file_path)
            except:
                pass
            
            # Отправляем сообщение об ошибке в стиле Олега
            error_messages = [
                "Что-то сломалось при скачивании. Попробуй позже, чемпион.",
                "Не смог скачать. Либо ссылка кривая, либо сервис лёг.",
                "Ошибка загрузки. Видимо, интернет решил отдохнуть.",
                "Не вышло скачать. Попробуй другую ссылку или подожди.",
            ]
            import random
            try:
                await message.reply(random.choice(error_messages))
            except:
                pass
            
            logger.error(f"Ошибка при скачивании {url}: {e}")
    
    def _get_file_extension(self, content_type: str) -> str:
        """Возвращает расширение файла для типа контента."""
        extensions = {
            'audio': '.mp3',
            'video': '.mp4'
        }
        return extensions.get(content_type, '.mp4')
    
    def _get_postprocessor(self, content_type: str) -> dict:
        """Возвращает постпроцессор для типа контента."""
        if content_type == 'audio':
            return {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }
        return None
    
    async def _send_video(self, bot, chat_id: int, file_path: str, info: dict):
        """Отправляет видео файл в чат."""
        # Подготовка описания
        title = info.get('title', 'Без названия')
        uploader = info.get('uploader', 'Неизвестный')
        
        caption = f"🎬 {title}\n👤 {uploader}"
        if len(caption) > 1024:  # Ограничение длины caption в Telegram
            caption = caption[:1021] + "..."
        
        await bot.send_video(
            chat_id=chat_id,
            video=open(file_path, 'rb'),
            caption=caption,
            supports_streaming=True
        )
    
    async def _send_audio(self, bot, chat_id: int, file_path: str, info: dict):
        """Отправляет аудио файл в чат."""
        # Подготовка метаданных
        title = info.get('title', 'Без названия')
        artist = info.get('uploader', info.get('artist', 'Неизвестный'))
        
        await bot.send_audio(
            chat_id=chat_id,
            audio=open(file_path, 'rb'),
            caption=f"🎵 {title}",
            title=title,
            performer=artist
        )


# Глобальный экземпляр downloader
downloader = ContentDownloader()


@router.message(F.text)  # Обрабатываем все текстовые сообщения
async def handle_links(msg: Message):
    """
    Обрабатывает сообщения с ссылками и добавляет задачи в очередь.
    """
    from app.handlers.owner_panel import is_feature_enabled
    
    # Проверяем, включена ли функция (runtime toggle)
    if not is_feature_enabled("content_download"):
        return
    
    text = msg.text or msg.caption or ""
    if not text:
        return

    # Ищем все ссылки в сообщении
    urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)

    for url in urls:
        # Проверяем, поддерживается ли контент
        content_type = downloader.detect_content_type(url)
        if content_type:
            logger.info(f"Найдена поддерживаемая ссылка: {url} (тип: {content_type})")

            # Проверяем, не является ли это пересланным сообщением от бота (чтобы не зациклиться)
            if msg.forward_from and msg.forward_from.id == msg.bot.id:
                continue  # Пропускаем пересланные сообщения от самого бота

            # Добавляем задачу в очередь
            await downloader.download_content(url, msg.chat.id, msg)
            break  # Обрабатываем только первую подходящую ссылку, чтобы не спамить
