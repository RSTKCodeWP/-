"""
GIF Patrol Service - анализ GIF-анимаций на запрещённый контент.

Извлекает кадры из GIF и анализирует их через Vision Pipeline
для обнаружения порнографии, скримеров и насилия.

**Feature: fortress-update**
**Validates: Requirements 3.1, 3.2, 3.6**
"""

import asyncio
import io
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from PIL import Image

from app.services.vision_pipeline import vision_pipeline

logger = logging.getLogger(__name__)


class ContentCategory(Enum):
    """Категории запрещённого контента."""
    PORNOGRAPHY = "pornography"
    SCREAMER = "screamer"
    VIOLENCE = "violence"
    SAFE = "safe"


@dataclass
class FrameAnalysis:
    """Результат анализа одного кадра."""
    frame_index: int
    is_safe: bool
    detected_category: Optional[ContentCategory]
    confidence: float
    description: str


@dataclass
class GIFAnalysisResult:
    """Результат анализа GIF."""
    is_safe: bool
    detected_categories: List[str]
    confidence: float
    frame_results: List[FrameAnalysis]
    error: Optional[str] = None


class GIFPatrolService:
    """
    Сервис для анализа GIF-анимаций на запрещённый контент.
    
    Извлекает 3 кадра (начало, середина, конец) и анализирует
    каждый через существующий Vision Pipeline.
    """
    
    # Промпт для анализа кадра на запрещённый контент
    CONTENT_ANALYSIS_PROMPT = """Analyze this image for inappropriate content.
Check for:
1. Pornographic or sexually explicit content
2. Screamer/jumpscare content (scary faces, horror imagery designed to shock)
3. Violent or gory content (blood, injuries, weapons being used)

Respond with ONLY one of these categories:
- SAFE: Normal, appropriate content
- PORNOGRAPHY: Sexual or nude content
- SCREAMER: Horror/jumpscare imagery
- VIOLENCE: Violent or gory content

Your response must be exactly one word from the list above."""

    # Количество кадров для извлечения
    FRAME_COUNT = 3
    
    # Таймаут для анализа одного кадра (секунды)
    FRAME_ANALYSIS_TIMEOUT = 5.0
    
    # Порог уверенности для определения небезопасного контента
    CONFIDENCE_THRESHOLD = 0.7
    
    def __init__(self):
        """Инициализация сервиса."""
        self._vision_pipeline = vision_pipeline
    
    def extract_frames(self, gif_data: bytes) -> List[bytes]:
        """
        Извлекает 3 кадра из GIF или MP4 анимации (начало, середина, конец).
        
        Telegram часто конвертирует GIF в MP4 для экономии трафика,
        поэтому поддерживаем оба формата.
        
        Args:
            gif_data: Байты GIF или MP4 файла
            
        Returns:
            Список из 3 кадров в формате PNG bytes
            
        Raises:
            ValueError: Если данные не являются валидным GIF/MP4
        """
        # Определяем формат по magic bytes
        is_mp4 = gif_data[:4] == b'\x00\x00\x00\x18' or gif_data[4:8] == b'ftyp'
        is_gif = gif_data[:6] in (b'GIF87a', b'GIF89a')
        
        logger.debug(f"Animation format detection: is_gif={is_gif}, is_mp4={is_mp4}, first_bytes={gif_data[:12].hex()}")
        
        # Если это MP4 — сразу идём в imageio
        if is_mp4:
            logger.info("Detected MP4 format, using imageio")
            return self._extract_frames_mp4(gif_data)
        
        # Пробуем открыть как GIF через PIL
        try:
            gif = Image.open(io.BytesIO(gif_data))
            
            # Проверяем, что это анимированный GIF
            if not hasattr(gif, 'n_frames'):
                # Статичное изображение - возвращаем его 3 раза
                frame_bytes = self._frame_to_bytes(gif)
                return [frame_bytes, frame_bytes, frame_bytes]
            
            total_frames = gif.n_frames
            
            if total_frames == 0:
                raise ValueError("GIF has no frames")
            
            # Определяем индексы кадров для извлечения
            if total_frames == 1:
                frame_indices = [0, 0, 0]
            elif total_frames == 2:
                frame_indices = [0, 0, 1]
            else:
                frame_indices = [
                    0,                          # Начало
                    total_frames // 2,          # Середина
                    total_frames - 1            # Конец
                ]
            
            frames = []
            for idx in frame_indices:
                gif.seek(idx)
                frame = gif.convert('RGB')
                frame_bytes = self._frame_to_bytes(frame)
                frames.append(frame_bytes)
            
            logger.info(f"Extracted {len(frames)} frames from GIF with {total_frames} total frames")
            return frames
            
        except Exception as pil_error:
            logger.debug(f"PIL failed to open as GIF: {pil_error}, trying as MP4...")
        
        # Если PIL не смог открыть - пробуем как MP4 через imageio
        return self._extract_frames_mp4(gif_data)
    
    def _extract_frames_mp4(self, mp4_data: bytes) -> List[bytes]:
        """
        Извлекает кадры из MP4 через imageio.
        
        Args:
            mp4_data: Байты MP4 файла
            
        Returns:
            Список из 3 кадров в формате PNG bytes
        """
        try:
            import imageio.v3 as iio
            
            # Читаем все кадры из MP4
            frames_array = iio.imread(io.BytesIO(mp4_data), plugin="pyav")
            total_frames = len(frames_array)
            
            logger.info(f"MP4 has {total_frames} frames")
            
            if total_frames == 0:
                raise ValueError("MP4 has no frames")
            
            # Определяем индексы кадров
            if total_frames == 1:
                frame_indices = [0, 0, 0]
            elif total_frames == 2:
                frame_indices = [0, 0, 1]
            else:
                frame_indices = [
                    0,
                    total_frames // 2,
                    total_frames - 1
                ]
            
            frames = []
            for idx in frame_indices:
                # Конвертируем numpy array в PIL Image
                frame_img = Image.fromarray(frames_array[idx])
                if frame_img.mode != 'RGB':
                    frame_img = frame_img.convert('RGB')
                frame_bytes = self._frame_to_bytes(frame_img)
                frames.append(frame_bytes)
            
            logger.info(f"Extracted {len(frames)} frames from MP4")
            return frames
            
        except ImportError as e:
            logger.error(f"imageio not available for MP4 processing: {e}")
            raise ValueError("Cannot extract frames from MP4: imageio[pyav] not installed")
        except Exception as e:
            logger.error(f"Error extracting frames from MP4: {e}")
            raise ValueError(f"Failed to extract frames from MP4: {e}")
    
    def _frame_to_bytes(self, frame: Image.Image) -> bytes:
        """Конвертирует PIL Image в PNG bytes."""
        buffer = io.BytesIO()
        # Конвертируем в RGB если нужно (для GIF с прозрачностью)
        if frame.mode in ('RGBA', 'P', 'LA'):
            frame = frame.convert('RGB')
        frame.save(buffer, format='PNG')
        return buffer.getvalue()
    
    async def analyze_frame(self, frame_data: bytes, frame_index: int) -> FrameAnalysis:
        """
        Анализирует один кадр на запрещённый контент.
        
        Args:
            frame_data: Байты кадра (PNG)
            frame_index: Индекс кадра (0, 1, 2)
            
        Returns:
            Результат анализа кадра
        """
        try:
            # Используем Vision Pipeline для анализа
            response = await self._vision_pipeline.analyze(
                frame_data, 
                user_query=self.CONTENT_ANALYSIS_PROMPT
            )
            
            # Парсим ответ модели
            category, confidence = self._parse_analysis_response(response)
            
            is_safe = category == ContentCategory.SAFE
            
            return FrameAnalysis(
                frame_index=frame_index,
                is_safe=is_safe,
                detected_category=category if not is_safe else None,
                confidence=confidence,
                description=response
            )
            
        except Exception as e:
            logger.error(f"Error analyzing frame {frame_index}: {e}")
            # При ошибке считаем кадр безопасным (fail-open для доступности)
            return FrameAnalysis(
                frame_index=frame_index,
                is_safe=True,
                detected_category=None,
                confidence=0.0,
                description=f"Analysis error: {e}"
            )
    
    def _parse_analysis_response(self, response: str) -> tuple[ContentCategory, float]:
        """
        Парсит ответ модели и определяет категорию контента.
        
        Args:
            response: Ответ от Vision Pipeline
            
        Returns:
            Tuple (категория, уверенность)
        """
        response_upper = response.upper().strip()
        
        # Ищем ключевые слова в ответе
        if "PORNOGRAPHY" in response_upper or "SEXUAL" in response_upper or "NUDE" in response_upper:
            return ContentCategory.PORNOGRAPHY, 0.9
        elif "SCREAMER" in response_upper or "HORROR" in response_upper or "JUMPSCARE" in response_upper:
            return ContentCategory.SCREAMER, 0.85
        elif "VIOLENCE" in response_upper or "VIOLENT" in response_upper or "GORE" in response_upper or "BLOOD" in response_upper:
            return ContentCategory.VIOLENCE, 0.85
        elif "SAFE" in response_upper or "NORMAL" in response_upper or "APPROPRIATE" in response_upper:
            return ContentCategory.SAFE, 0.9
        else:
            # Не удалось определить - считаем безопасным с низкой уверенностью
            return ContentCategory.SAFE, 0.5
    
    async def analyze_gif(self, gif_data: bytes) -> GIFAnalysisResult:
        """
        Полный анализ GIF на запрещённый контент.
        
        Извлекает 3 кадра и анализирует каждый параллельно.
        GIF считается небезопасным, если хотя бы один кадр небезопасен.
        
        Args:
            gif_data: Байты GIF-файла
            
        Returns:
            Результат анализа GIF
        """
        try:
            # Извлекаем кадры
            frames = self.extract_frames(gif_data)
            
            # Анализируем кадры параллельно с таймаутом
            tasks = [
                asyncio.wait_for(
                    self.analyze_frame(frame, idx),
                    timeout=self.FRAME_ANALYSIS_TIMEOUT
                )
                for idx, frame in enumerate(frames)
            ]
            
            frame_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Обрабатываем результаты
            valid_results = []
            for idx, result in enumerate(frame_results):
                if isinstance(result, Exception):
                    logger.warning(f"Frame {idx} analysis failed: {result}")
                    # Создаём безопасный результат при ошибке
                    valid_results.append(FrameAnalysis(
                        frame_index=idx,
                        is_safe=True,
                        detected_category=None,
                        confidence=0.0,
                        description=f"Analysis timeout/error"
                    ))
                else:
                    valid_results.append(result)
            
            # Определяем общий результат
            detected_categories = []
            max_confidence = 0.0
            is_safe = True
            
            for result in valid_results:
                if not result.is_safe and result.detected_category:
                    is_safe = False
                    category_name = result.detected_category.value
                    if category_name not in detected_categories:
                        detected_categories.append(category_name)
                    max_confidence = max(max_confidence, result.confidence)
            
            return GIFAnalysisResult(
                is_safe=is_safe,
                detected_categories=detected_categories,
                confidence=max_confidence if not is_safe else 1.0,
                frame_results=valid_results
            )
            
        except ValueError as e:
            # Ошибка извлечения кадров
            return GIFAnalysisResult(
                is_safe=True,  # Fail-open
                detected_categories=[],
                confidence=0.0,
                frame_results=[],
                error=str(e)
            )
        except Exception as e:
            logger.error(f"Error analyzing GIF: {e}")
            return GIFAnalysisResult(
                is_safe=True,  # Fail-open
                detected_categories=[],
                confidence=0.0,
                frame_results=[],
                error=str(e)
            )
    
    async def queue_analysis(
        self, 
        gif_data: bytes,
        message_id: int, 
        chat_id: int, 
        user_id: int,
        file_id: str
    ) -> Optional[str]:
        """
        Ставит GIF в очередь на анализ через Arq Worker.
        
        **Validates: Requirements 14.3**
        
        Args:
            gif_data: Байты GIF-файла
            message_id: ID сообщения с GIF
            chat_id: ID чата
            user_id: ID пользователя
            file_id: Telegram file_id GIF
            
        Returns:
            ID задачи в очереди или None
        """
        try:
            from app.worker import enqueue_gif_analysis_task
            from app.config import settings
            
            # Check if worker is enabled
            if not settings.worker_enabled or not settings.redis_enabled:
                logger.debug(f"Worker not enabled, GIF analysis not queued for chat {chat_id}")
                return None
            
            job = await enqueue_gif_analysis_task(
                gif_data=gif_data,
                message_id=message_id,
                chat_id=chat_id,
                user_id=user_id,
                file_id=file_id,
            )
            
            if job is not None:
                logger.info(f"GIF analysis task queued for chat {chat_id}: {job.job_id}")
                return job.job_id
            
            return None
            
        except ImportError:
            logger.warning("Arq worker module not available")
            return None
        except Exception as e:
            logger.error(f"Failed to queue GIF analysis task: {e}")
            return None


# Глобальный экземпляр сервиса
gif_patrol_service = GIFPatrolService()
