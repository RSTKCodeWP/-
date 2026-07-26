"""Text-to-Speech service for voice message generation.

This module provides TTS functionality including:
- Voice message generation with text truncation
- Auto-voice probability check (0.1% chance)
- Fallback to gTTS on Edge TTS unavailability
- Edge TTS for Russian voice synthesis (Microsoft)

**Feature: fortress-update, oleg-commands-fix**
**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**
"""

import io
import logging
import random
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# TTS Configuration
MAX_TEXT_LENGTH = 500
TRUNCATION_SUFFIX = "...и так далее"
AUTO_VOICE_PROBABILITY = 0.001  # 0.1%


@dataclass
class TTSResult:
    """Result of TTS generation."""
    audio_data: bytes
    duration_seconds: float
    format: str  # mp3
    original_text: str
    was_truncated: bool


class TTSService:
    """
    Text-to-Speech service for generating voice messages.
    
    Provides voice generation with Oleg's characteristic voice,
    text truncation for long messages, and auto-voice probability.
    Uses Edge TTS (Microsoft) with gTTS fallback.
    
    **Feature: fortress-update, oleg-commands-fix**
    **Validates: Requirements 5.1, 5.2, 5.3, 5.5**
    """
    
    # Edge TTS configuration
    DEFAULT_VOICE = "ru-RU-DmitryNeural"
    
    # Mapping personas to voices and parameters
    PERSONA_VOICES = {
        "oleg": {"voice": "ru-RU-DmitryNeural", "pitch": "-15Hz", "rate": "+0%"},
        "oleg_legacy": {"voice": "ru-RU-DmitryNeural", "pitch": "+0Hz", "rate": "+0%"},
        "dude": {"voice": "ru-RU-DmitryNeural", "pitch": "-10Hz", "rate": "-20%"},
        "stalin": {"voice": "ru-RU-DmitryNeural", "pitch": "-10Hz", "rate": "-5%"},
        "anime": {"voice": "ru-RU-SvetlanaNeural", "pitch": "+20Hz", "rate": "+10%"},
        "trump": {"voice": "ru-RU-DmitryNeural", "pitch": "+5Hz", "rate": "+5%"},
        "putin": {"voice": "ru-RU-DmitryNeural", "pitch": "-5Hz", "rate": "-5%"},
        "pozdnyakov": {"voice": "ru-RU-DmitryNeural", "pitch": "+0Hz", "rate": "+10%"},
        "zgeek": {"voice": "ru-RU-DmitryNeural", "pitch": "-5Hz", "rate": "+5%"},
    }
    
    def __init__(self, tts_model: Optional[str] = None):
        """Initialize TTS service."""
        self._default_voice = tts_model or self.DEFAULT_VOICE
        self._is_available = True
        self._edge_available = True  # Track Edge TTS availability separately
    
    def truncate_text(self, text: str, max_length: int = MAX_TEXT_LENGTH) -> tuple[str, bool]:
        """Truncate text to maximum length with suffix."""
        if not text:
            return "", False
        
        if len(text) <= max_length:
            return text, False
        
        suffix_length = len(TRUNCATION_SUFFIX)
        truncated = text[:max_length - suffix_length] + TRUNCATION_SUFFIX
        return truncated, True
    
    def should_auto_voice(self) -> bool:
        """Check if response should be auto-voiced (0.1% chance)."""
        return random.random() < AUTO_VOICE_PROBABILITY
    
    async def generate_voice(
        self,
        text: str,
        max_chars: int = MAX_TEXT_LENGTH,
        persona: str = "oleg"
    ) -> Optional[TTSResult]:
        """Generate voice message from text."""
        if not text:
            return None
            
        # Clean text from special symbols (keep alphanumeric and basic punctuation)
        # Allow Cyrillic, Latin, numbers, and basic punctuation
        clean_text = re.sub(r'[^\w\s.,!?;:()\-—"\'«»]', '', text)
        # Remove multiple spaces
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        if not clean_text:
            return None
        
        processed_text, was_truncated = self.truncate_text(clean_text, max_chars)
        
        if was_truncated:
            logger.info(f"Text truncated from {len(clean_text)} to {len(processed_text)} chars")
        
        try:
            audio_data = await self._generate_audio(processed_text, persona)
            
            if audio_data is None:
                return None
            
            return TTSResult(
                audio_data=audio_data,
                duration_seconds=self._estimate_duration(processed_text),
                format="mp3",
                original_text=processed_text,
                was_truncated=was_truncated
            )
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            return None
    
    async def _generate_audio(self, text: str, persona: str = "oleg") -> Optional[bytes]:
        """Generate audio using Edge TTS with gTTS fallback."""
        if not self._is_available:
            logger.warning("TTS service marked as unavailable, skipping generation")
            return None
        
        # Try Edge TTS first
        if self._edge_available:
            logger.debug(f"Attempting Edge TTS generation for persona {persona}...")
            audio = await self._generate_edge_tts(text, persona)
            if audio:
                return audio
            logger.warning("Edge TTS failed, trying gTTS fallback")
            self._edge_available = False
        
        # Fallback to gTTS
        logger.debug("Attempting gTTS generation...")
        return await self._generate_gtts(text)
    
    async def _generate_edge_tts(self, text: str, persona: str = "oleg") -> Optional[bytes]:
        """Generate audio using Edge TTS (Microsoft)."""
        try:
            import edge_tts
            
            # Get voice config for persona
            config = self.PERSONA_VOICES.get(persona, self.PERSONA_VOICES["oleg"])
            voice = config["voice"]
            pitch = config["pitch"]
            rate = config["rate"]
            
            logger.info(f"Edge TTS generation: persona={persona}, voice={voice}, pitch={pitch}, rate={rate}")
            
            communicate = edge_tts.Communicate(text, voice, pitch=pitch, rate=rate)
            
            audio_buffer = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])
            
            audio_data = audio_buffer.getvalue()
            if not audio_data:
                logger.error("Edge TTS returned empty audio")
                return None
            
            logger.info(f"Edge TTS generated: {len(audio_data)} bytes")
            return audio_data
            
        except ImportError:
            logger.error("edge-tts not installed")
            return None
        except Exception as e:
            logger.error(f"Edge TTS failed: {e}")
            return None
    
    async def _generate_gtts(self, text: str) -> Optional[bytes]:
        """Generate audio using gTTS (Google) as fallback."""
        try:
            from gtts import gTTS
            import asyncio
            
            logger.debug(f"gTTS generation for: {text[:50]}...")
            
            def _sync_generate():
                tts = gTTS(text=text, lang='ru')
                audio_buffer = io.BytesIO()
                tts.write_to_fp(audio_buffer)
                return audio_buffer.getvalue()
            
            # Run sync gTTS in thread pool
            loop = asyncio.get_event_loop()
            audio_data = await loop.run_in_executor(None, _sync_generate)
            
            if not audio_data:
                logger.error("gTTS returned empty audio")
                return None
            
            logger.info(f"gTTS generated: {len(audio_data)} bytes")
            return audio_data
            
        except ImportError:
            logger.error("gTTS not installed. Install with: pip install gTTS")
            self._is_available = False
            return None
        except Exception as e:
            logger.error(f"gTTS failed: {e}")
            return None
    
    def _estimate_duration(self, text: str) -> float:
        """Estimate audio duration (10 chars/sec for Russian)."""
        return len(text) / 10
    
    @property
    def is_available(self) -> bool:
        """Check if TTS service is available."""
        return self._is_available
    
    def set_available(self, available: bool) -> None:
        """Set TTS service availability."""
        self._is_available = available
        if available:
            self._edge_available = True  # Reset Edge availability too
            logger.info("TTS service marked as available")
        else:
            logger.warning("TTS service marked as unavailable")
    
    def reset_edge_tts(self) -> None:
        """Reset Edge TTS availability (try Edge again)."""
        self._edge_available = True
        logger.info("Edge TTS reset, will try on next request")
    
    async def queue_tts_task(
        self,
        text: str,
        chat_id: int,
        reply_to: int,
        max_chars: int = MAX_TEXT_LENGTH
    ) -> Optional[str]:
        """Queue TTS generation task for async processing via Arq worker."""
        try:
            from app.worker import enqueue_tts_task
            from app.config import settings
            
            if not settings.worker_enabled or not settings.redis_enabled:
                logger.debug(f"Worker not enabled, TTS task not queued for chat {chat_id}")
                return None
            
            job = await enqueue_tts_task(
                text=text,
                chat_id=chat_id,
                reply_to=reply_to,
                max_chars=max_chars,
            )
            
            if job is not None:
                logger.info(f"TTS task queued for chat {chat_id}: {job.job_id}")
                return job.job_id
            
            return None
            
        except ImportError:
            logger.warning("Arq worker module not available")
            return None
        except Exception as e:
            logger.error(f"Failed to queue TTS task: {e}")
            return None


# Global TTS service instance
tts_service = TTSService()
