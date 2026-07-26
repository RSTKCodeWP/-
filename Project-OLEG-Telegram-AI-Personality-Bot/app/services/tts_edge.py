"""Edge-TTS Service for voice message generation.

This module provides TTS functionality using Microsoft Edge TTS API:
- Russian voices: Dmitry (male) and Svetlana (female)
- Temp file lifecycle management: Create → Send → Delete
- Error handling with user notification

**Feature: grand-casino-dictator, Property 20: TTS File Lifecycle**
**Validates: Requirements 15.1, 15.2, 15.3, 15.4**
"""

import logging
import os
import tempfile
import uuid
from dataclasses import dataclass
from typing import Optional

from aiogram import Bot
from aiogram.types import FSInputFile

logger = logging.getLogger(__name__)


class TTSSynthesisError(Exception):
    """Error during TTS synthesis.
    
    **Validates: Requirements 15.4**
    """
    pass


class VoiceNotFoundError(Exception):
    """Requested voice not found.
    
    **Validates: Requirements 15.4**
    """
    pass


@dataclass
class TTSFileResult:
    """Result of TTS file generation with lifecycle tracking."""
    file_path: str
    audio_bytes: Optional[bytes]
    text: str
    voice: str
    created: bool
    sent: bool
    deleted: bool
    error: Optional[str]


class EdgeTTSService:
    """
    TTS service using Microsoft Edge API.
    
    Provides voice generation with proper temp file lifecycle:
    1. Create temp file with audio
    2. Send as voice message
    3. Delete temp file (always, regardless of success/failure)
    
    **Feature: grand-casino-dictator**
    **Validates: Requirements 15.1, 15.2, 15.3, 15.4**
    """
    
    RUSSIAN_VOICES = {
        "male": "ru-RU-DmitryNeural",
        "female": "ru-RU-SvetlanaNeural"
    }
    
    DEFAULT_VOICE = "male"
    TEMP_DIR = tempfile.gettempdir()
    FILE_PREFIX = "oleg_tts_"
    FILE_SUFFIX = ".mp3"
    
    def __init__(self, voice: str = DEFAULT_VOICE):
        """
        Initialize Edge TTS service.
        
        Args:
            voice: Voice type - "male" (Dmitry) or "female" (Svetlana)
        """
        self._voice_type = voice
        self._voice_name = self.RUSSIAN_VOICES.get(voice, self.RUSSIAN_VOICES["male"])
        self._is_available = True
    
    @property
    def voice_name(self) -> str:
        """Get current voice name."""
        return self._voice_name
    
    @property
    def is_available(self) -> bool:
        """Check if service is available."""
        return self._is_available
    
    def set_voice(self, voice: str) -> None:
        """
        Set voice type.
        
        Args:
            voice: "male" for Dmitry or "female" for Svetlana
        """
        if voice in self.RUSSIAN_VOICES:
            self._voice_type = voice
            self._voice_name = self.RUSSIAN_VOICES[voice]
            logger.info(f"Voice set to {self._voice_name}")
        else:
            logger.warning(f"Unknown voice '{voice}', keeping {self._voice_name}")
    
    def _generate_temp_path(self) -> str:
        """Generate unique temp file path."""
        unique_id = uuid.uuid4().hex[:8]
        filename = f"{self.FILE_PREFIX}{unique_id}{self.FILE_SUFFIX}"
        return os.path.join(self.TEMP_DIR, filename)
    
    async def synthesize(self, text: str, voice: Optional[str] = None) -> Optional[bytes]:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to convert to speech
            voice: Optional voice override ("male" or "female")
            
        Returns:
            Audio bytes in MP3 format, or None on failure
            
        **Validates: Requirements 15.1, 15.2**
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for TTS")
            return None
        
        voice_name = self.RUSSIAN_VOICES.get(voice, self._voice_name) if voice else self._voice_name
        
        try:
            import edge_tts
            
            logger.debug(f"Synthesizing with {voice_name}: {text[:50]}...")
            communicate = edge_tts.Communicate(text, voice_name)
            
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
            
            if not audio_chunks:
                logger.error("Edge TTS returned no audio data")
                return None
            
            audio_data = b"".join(audio_chunks)
            logger.info(f"Synthesized {len(audio_data)} bytes with {voice_name}")
            return audio_data
            
        except ImportError:
            logger.error("edge-tts library not installed. Install with: pip install edge-tts")
            self._is_available = False
            return None
        except Exception as e:
            logger.error(f"Edge TTS synthesis failed: {e}")
            return None

    async def synthesize_to_file(self, text: str, voice: Optional[str] = None) -> TTSFileResult:
        """
        Synthesize speech and save to temp file.
        
        This method handles the first part of the file lifecycle:
        Create temp file with audio data.
        
        Args:
            text: Text to convert to speech
            voice: Optional voice override
            
        Returns:
            TTSFileResult with file path and status
            
        **Validates: Requirements 15.3**
        """
        file_path = self._generate_temp_path()
        voice_name = self.RUSSIAN_VOICES.get(voice, self._voice_name) if voice else self._voice_name
        
        result = TTSFileResult(
            file_path=file_path,
            audio_bytes=None,
            text=text,
            voice=voice_name,
            created=False,
            sent=False,
            deleted=False,
            error=None
        )
        
        if not text or not text.strip():
            result.error = "Empty text provided"
            return result
        
        try:
            import edge_tts
            
            logger.debug(f"Synthesizing to file {file_path}")
            communicate = edge_tts.Communicate(text, voice_name)
            await communicate.save(file_path)
            
            # Verify file was created
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                result.created = True
                # Also read bytes for potential in-memory use
                with open(file_path, "rb") as f:
                    result.audio_bytes = f.read()
                logger.info(f"Created TTS file: {file_path} ({os.path.getsize(file_path)} bytes)")
            else:
                result.error = "File creation failed or empty"
                logger.error(result.error)
                
        except ImportError:
            result.error = "edge-tts library not installed"
            logger.error(result.error)
            self._is_available = False
        except Exception as e:
            result.error = str(e)
            logger.error(f"Edge TTS file synthesis failed: {e}")
        
        return result
    
    def delete_temp_file(self, file_path: str) -> bool:
        """
        Delete temp file.
        
        This method handles the final part of the file lifecycle:
        Delete temp file after use.
        
        Args:
            file_path: Path to temp file to delete
            
        Returns:
            True if deleted successfully, False otherwise
            
        **Validates: Requirements 15.3**
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Deleted temp file: {file_path}")
                return True
            else:
                logger.debug(f"Temp file already deleted: {file_path}")
                return True  # Consider already-deleted as success
        except Exception as e:
            logger.error(f"Failed to delete temp file {file_path}: {e}")
            return False
    
    async def send_voice(
        self,
        bot: Bot,
        chat_id: int,
        text: str,
        voice: Optional[str] = None,
        reply_to_message_id: Optional[int] = None
    ) -> TTSFileResult:
        """
        Generate and send voice message with full lifecycle management.
        
        Implements the complete temp file lifecycle:
        1. Create temp file with synthesized audio
        2. Send as voice message to chat
        3. Delete temp file (always, regardless of success/failure)
        
        Args:
            bot: Aiogram Bot instance
            chat_id: Target chat ID
            text: Text to convert to speech
            voice: Optional voice override ("male" or "female")
            reply_to_message_id: Optional message to reply to
            
        Returns:
            TTSFileResult with complete lifecycle status
            
        **Validates: Requirements 15.1, 15.2, 15.3, 15.4**
        """
        # Step 1: Create temp file
        result = await self.synthesize_to_file(text, voice)
        
        if not result.created:
            # Cleanup attempt even if creation failed (file might be partial)
            result.deleted = self.delete_temp_file(result.file_path)
            return result
        
        # Step 2: Send voice message
        try:
            voice_file = FSInputFile(result.file_path)
            await bot.send_voice(
                chat_id=chat_id,
                voice=voice_file,
                reply_to_message_id=reply_to_message_id
            )
            result.sent = True
            logger.info(f"Sent voice message to chat {chat_id}")
            
        except Exception as e:
            result.error = f"Failed to send voice: {e}"
            logger.error(result.error)
        
        # Step 3: Delete temp file (ALWAYS, regardless of send success)
        finally:
            result.deleted = self.delete_temp_file(result.file_path)
        
        return result
    
    async def send_voice_with_notification(
        self,
        bot: Bot,
        chat_id: int,
        text: str,
        voice: Optional[str] = None,
        reply_to_message_id: Optional[int] = None
    ) -> TTSFileResult:
        """
        Generate and send voice message with error notification to user.
        
        Same as send_voice but notifies user on failure.
        Falls back to Silero TTS if Edge TTS fails (works in Russia).
        
        Args:
            bot: Aiogram Bot instance
            chat_id: Target chat ID
            text: Text to convert to speech
            voice: Optional voice override
            reply_to_message_id: Optional message to reply to
            
        Returns:
            TTSFileResult with complete lifecycle status
            
        **Validates: Requirements 15.4**
        """
        result = await self.send_voice(bot, chat_id, text, voice, reply_to_message_id)
        
        if result.error:
            # Try gTTS fallback (Google Translate TTS)
            logger.info("Edge TTS failed, trying gTTS fallback...")
            gtts_result = await self._gtts_fallback(bot, chat_id, text, reply_to_message_id)
            if gtts_result and gtts_result.sent:
                return gtts_result
            
            # Try pyttsx3 fallback (offline TTS)
            logger.info("gTTS failed, trying pyttsx3 offline fallback...")
            pyttsx3_result = await self._pyttsx3_fallback(bot, chat_id, text, reply_to_message_id)
            if pyttsx3_result and pyttsx3_result.sent:
                return pyttsx3_result
            
            # All failed - notify user
            try:
                error_msg = "🔊 <b>Голосовой движок временно недоступен</b>\n\n"
                error_msg += f"<i>{text[:200]}{'...' if len(text) > 200 else ''}</i>"
                await bot.send_message(
                    chat_id=chat_id,
                    text=error_msg,
                    parse_mode="HTML",
                    reply_to_message_id=reply_to_message_id
                )
                logger.info(f"Sent TTS error notification to chat {chat_id}")
            except Exception as e:
                logger.error(f"Failed to send error notification: {e}")
        
        return result
    
    async def _gtts_fallback(
        self,
        bot: Bot,
        chat_id: int,
        text: str,
        reply_to_message_id: Optional[int] = None
    ) -> Optional[TTSFileResult]:
        """Fallback to gTTS (Google Translate TTS)."""
        file_path = self._generate_temp_path()
        
        result = TTSFileResult(
            file_path=file_path,
            audio_bytes=None,
            text=text,
            voice="gtts",
            created=False,
            sent=False,
            deleted=False,
            error=None
        )
        
        try:
            from gtts import gTTS
            import asyncio
            
            # gTTS is synchronous, run in executor
            def generate_gtts():
                tts = gTTS(text=text, lang='ru')
                tts.save(file_path)
            
            await asyncio.get_event_loop().run_in_executor(None, generate_gtts)
            
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                result.created = True
                logger.info(f"gTTS created file: {file_path}")
                
                # Send voice
                voice_file = FSInputFile(file_path)
                await bot.send_voice(
                    chat_id=chat_id,
                    voice=voice_file,
                    reply_to_message_id=reply_to_message_id
                )
                result.sent = True
                logger.info(f"gTTS fallback succeeded for chat {chat_id}")
            else:
                result.error = "gTTS file creation failed"
                
        except ImportError:
            logger.warning("gTTS not installed")
            result.error = "gTTS not installed"
        except Exception as e:
            logger.error(f"gTTS fallback failed: {e}")
            result.error = str(e)
        finally:
            # Cleanup
            result.deleted = self.delete_temp_file(file_path)
        
        return result
    
    async def _pyttsx3_fallback(
        self,
        bot: Bot,
        chat_id: int,
        text: str,
        reply_to_message_id: Optional[int] = None
    ) -> Optional[TTSFileResult]:
        """Fallback to pyttsx3 (offline TTS with espeak)."""
        # pyttsx3 saves as wav, need to convert
        wav_path = self._generate_temp_path().replace('.mp3', '.wav')
        mp3_path = self._generate_temp_path()
        
        result = TTSFileResult(
            file_path=mp3_path,
            audio_bytes=None,
            text=text,
            voice="pyttsx3",
            created=False,
            sent=False,
            deleted=False,
            error=None
        )
        
        try:
            import pyttsx3
            import asyncio
            import subprocess
            
            def generate_pyttsx3():
                engine = pyttsx3.init()
                # Set Russian voice if available
                voices = engine.getProperty('voices')
                for voice in voices:
                    if 'ru' in voice.id.lower() or 'russian' in voice.name.lower():
                        engine.setProperty('voice', voice.id)
                        break
                engine.setProperty('rate', 150)
                engine.save_to_file(text, wav_path)
                engine.runAndWait()
            
            await asyncio.get_event_loop().run_in_executor(None, generate_pyttsx3)
            
            # Convert wav to mp3 using ffmpeg
            if os.path.exists(wav_path):
                proc = await asyncio.create_subprocess_exec(
                    'ffmpeg', '-y', '-i', wav_path, '-acodec', 'libmp3lame', '-q:a', '4', mp3_path,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                await proc.wait()
                
                # Cleanup wav
                try:
                    os.remove(wav_path)
                except:
                    pass
            
            if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
                result.created = True
                logger.info(f"pyttsx3 created file: {mp3_path}")
                
                # Send voice
                voice_file = FSInputFile(mp3_path)
                await bot.send_voice(
                    chat_id=chat_id,
                    voice=voice_file,
                    reply_to_message_id=reply_to_message_id
                )
                result.sent = True
                logger.info(f"pyttsx3 fallback succeeded for chat {chat_id}")
            else:
                result.error = "pyttsx3 file creation failed"
                
        except ImportError:
            logger.warning("pyttsx3 not installed")
            result.error = "pyttsx3 not installed"
        except Exception as e:
            logger.error(f"pyttsx3 fallback failed: {e}")
            result.error = str(e)
        finally:
            # Cleanup
            result.deleted = self.delete_temp_file(mp3_path)
            try:
                if os.path.exists(wav_path):
                    os.remove(wav_path)
            except:
                pass
        
        return result


# Global Edge TTS service instance
edge_tts_service = EdgeTTSService()
