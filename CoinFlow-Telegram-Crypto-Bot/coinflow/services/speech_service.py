"""Speech recognition service for voice message processing."""

import os
import tempfile
import asyncio
from typing import Optional
from pathlib import Path
from ..utils.logger import setup_logger

logger = setup_logger('speech_service')


class SpeechRecognitionService:
    """Service for converting voice messages to text."""
    
    def __init__(self, use_whisper: bool = True, model_size: str = "base"):
        """
        Initialize speech recognition service.
        
        Args:
            use_whisper: Use Whisper model if True, otherwise use SpeechRecognition
            model_size: Whisper model size (tiny, base, small, medium, large)
        """
        self.use_whisper = use_whisper
        self.whisper_model = None
        
        if use_whisper:
            try:
                # Try faster-whisper first (more efficient)
                from faster_whisper import WhisperModel
                # Use CPU with int8 for better performance on systems without GPU
                self.whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
                self.use_faster_whisper = True
                logger.info(f"Faster-Whisper model '{model_size}' loaded successfully")
            except ImportError:
                try:
                    # Fallback to standard whisper
                    import whisper
                    self.whisper_model = whisper.load_model(model_size)
                    self.use_faster_whisper = False
                    logger.info(f"Standard Whisper model '{model_size}' loaded successfully")
                except ImportError:
                    logger.warning("Whisper not available, falling back to SpeechRecognition")
                    self.use_whisper = False
        
        if not self.use_whisper:
            try:
                import speech_recognition as sr
                self.recognizer = sr.Recognizer()
                logger.info("SpeechRecognition initialized")
            except ImportError:
                logger.error("No speech recognition library available")
                self.recognizer = None
    
    async def transcribe_voice(self, voice_file_path: str, language: str = 'en') -> Optional[str]:
        """
        Transcribe voice message to text.
        
        Args:
            voice_file_path: Path to voice file (OGG)
            language: Language code (en/ru)
        
        Returns:
            Transcribed text or None if failed
        """
        try:
            if self.use_whisper and self.whisper_model:
                return await self._transcribe_with_whisper(voice_file_path, language)
            elif self.recognizer:
                return await self._transcribe_with_sr(voice_file_path, language)
            else:
                logger.error("No speech recognition available")
                return None
        except Exception as e:
            logger.error(f"Error transcribing voice: {e}")
            return None
    
    async def _transcribe_with_whisper(self, voice_file_path: str, language: str) -> Optional[str]:
        """Transcribe using Whisper model (Faster-Whisper or standard)."""
        try:
            # Convert OGG to WAV if needed
            wav_path = await self._convert_to_wav(voice_file_path)
            
            # Transcribe with Whisper
            loop = asyncio.get_event_loop()
            
            if hasattr(self, 'use_faster_whisper') and self.use_faster_whisper:
                # Faster-Whisper API
                def transcribe_faster():
                    segments, info = self.whisper_model.transcribe(wav_path, language=language)
                    text = " ".join([segment.text for segment in segments])
                    return text.strip()
                
                text = await loop.run_in_executor(None, transcribe_faster)
            else:
                # Standard Whisper API
                result = await loop.run_in_executor(
                    None,
                    lambda: self.whisper_model.transcribe(wav_path, language=language)
                )
                text = result.get('text', '').strip()
            
            # Clean up temp file
            if wav_path != voice_file_path:
                os.remove(wav_path)
            
            logger.info(f"Whisper transcription: {text[:50]}...")
            return text if text else None
            
        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return None
    
    async def _transcribe_with_sr(self, voice_file_path: str, language: str) -> Optional[str]:
        """Transcribe using SpeechRecognition library."""
        try:
            import speech_recognition as sr
            
            # Convert to WAV
            wav_path = await self._convert_to_wav(voice_file_path)
            
            # Transcribe
            loop = asyncio.get_event_loop()
            
            def recognize():
                with sr.AudioFile(wav_path) as source:
                    audio = self.recognizer.record(source)
                    lang_code = 'ru-RU' if language == 'ru' else 'en-US'
                    return self.recognizer.recognize_google(audio, language=lang_code)
            
            text = await loop.run_in_executor(None, recognize)
            
            # Clean up
            if wav_path != voice_file_path:
                os.remove(wav_path)
            
            logger.info(f"SR transcription: {text[:50]}...")
            return text.strip() if text else None
            
        except sr.UnknownValueError:
            logger.warning("Speech not understood")
            return None
        except sr.RequestError as e:
            logger.error(f"SR API error: {e}")
            return None
        except Exception as e:
            logger.error(f"SR transcription error: {e}")
            return None
    
    async def _convert_to_wav(self, ogg_path: str) -> str:
        """
        Convert OGG to WAV format.
        
        Args:
            ogg_path: Path to OGG file
        
        Returns:
            Path to WAV file
        """
        try:
            from pydub import AudioSegment
            
            # Create temp WAV file
            temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            temp_wav.close()
            
            # Convert
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: AudioSegment.from_ogg(ogg_path).export(temp_wav.name, format='wav')
            )
            
            return temp_wav.name
            
        except ImportError:
            logger.warning("pydub not available, assuming file is already WAV compatible")
            return ogg_path
        except Exception as e:
            logger.error(f"Audio conversion error: {e}")
            return ogg_path
    
    async def download_voice_file(self, telegram_file, destination: str) -> bool:
        """
        Download voice file from Telegram.
        
        Args:
            telegram_file: Telegram File object
            destination: Destination path
        
        Returns:
            True if successful
        """
        try:
            await telegram_file.download_to_drive(destination)
            return os.path.exists(destination)
        except Exception as e:
            logger.error(f"Error downloading voice file: {e}")
            return False
