"""Voice transcription service using faster-whisper."""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class VoiceTranscriber:
    """Transcribes voice messages using faster-whisper."""
    
    def __init__(self, model_size: str = "tiny", **kwargs):
        """
        Initialize voice transcriber.
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
        """
        self.model_size = model_size
        self._model = None
    
    def _load_model(self):
        """Load faster-whisper model lazily."""
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
                logger.info(f"Loading faster-whisper model: {self.model_size}")
                self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
                logger.info("faster-whisper model loaded successfully")
            except ImportError:
                logger.error("faster-whisper not installed. Install with: pip install faster-whisper")
                raise
            except Exception as e:
                logger.error(f"Error loading faster-whisper model: {e}")
                raise
    
    async def transcribe(self, audio_file_path: str, language: str = "ru") -> Optional[str]:
        """
        Transcribe audio file to text using faster-whisper.
        
        Args:
            audio_file_path: Path to audio file
            language: Expected language (ru/en)
            
        Returns:
            Transcribed text or None if transcription failed
        """
        try:
            if not os.path.exists(audio_file_path):
                logger.error(f"Audio file not found: {audio_file_path}")
                return None
            
            # Load model if not loaded
            if self._model is None:
                self._load_model()
            
            logger.info(f"Transcribing audio file: {audio_file_path}")
            
            # Map language codes
            whisper_lang = "ru" if language == "ru" else "en"
            
            # Transcribe (run in executor to avoid blocking)
            import asyncio
            segments, info = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._model.transcribe(audio_file_path, language=whisper_lang)
            )
            
            # Collect all segments
            transcribed_text = " ".join([segment.text for segment in segments]).strip()
            
            if transcribed_text:
                logger.info(f"Transcription successful: {transcribed_text[:50]}...")
                return transcribed_text
            else:
                logger.warning("Transcription returned empty text")
                return None
        
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}", exc_info=True)
            return None
    
    async def is_available(self) -> bool:
        """Check if faster-whisper is available."""
        try:
            from faster_whisper import WhisperModel
            return True
        except ImportError:
            return False
