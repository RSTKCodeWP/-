"""Voice recognition service for CoinFlow bot."""

import os
import io
import shutil
from typing import Optional, Dict
from ..utils.logger import setup_logger

logger = setup_logger('voice_service')

# Try to import speech recognition libraries
try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False
    logger.warning("speech_recognition not available. Install with: pip install SpeechRecognition")

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logger.warning("pydub not available. Install with: pip install pydub")

# Check if ffmpeg is available
FFMPEG_AVAILABLE = shutil.which('ffmpeg') is not None
if not FFMPEG_AVAILABLE:
    logger.warning("ffmpeg not found in PATH. Voice recognition requires ffmpeg for audio conversion.")


class VoiceService:
    """Service for voice message recognition."""
    
    def __init__(self):
        """Initialize voice service."""
        self.available = SR_AVAILABLE and PYDUB_AVAILABLE and FFMPEG_AVAILABLE
        self.ffmpeg_available = FFMPEG_AVAILABLE
        
        if SR_AVAILABLE and PYDUB_AVAILABLE:
            if FFMPEG_AVAILABLE:
                self.recognizer = sr.Recognizer()
                logger.info("Voice service initialized successfully")
            else:
                logger.warning("Voice service initialized but ffmpeg not available")
        else:
            logger.warning("Voice service initialized but libraries not available")
    
    def is_available(self) -> bool:
        """Check if voice recognition is available."""
        return self.available
    
    async def convert_ogg_to_wav(self, ogg_data: bytes) -> Optional[bytes]:
        """
        Convert OGG audio to WAV format.
        
        Args:
            ogg_data: OGG audio data
        
        Returns:
            WAV audio data or None
        """
        if not PYDUB_AVAILABLE:
            logger.error("pydub not available")
            return None
        
        if not FFMPEG_AVAILABLE:
            logger.error("ffmpeg not found in PATH")
            return None
        
        try:
            # Load OGG from bytes
            audio = AudioSegment.from_ogg(io.BytesIO(ogg_data))
            
            # Convert to WAV
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format='wav')
            wav_buffer.seek(0)
            
            return wav_buffer.read()
        except FileNotFoundError as e:
            logger.error(f"ffmpeg executable not found: {e}")
            return None
        except Exception as e:
            logger.error(f"Error converting OGG to WAV: {e}")
            return None
    
    async def recognize_speech(self, audio_data: bytes, language: str = 'en') -> Dict:
        """
        Recognize speech from audio data.
        
        Args:
            audio_data: Audio data (WAV format)
            language: Language code (en, ru, etc.)
        
        Returns:
            Dictionary with recognition results
        """
        if not self.available:
            return {'error': 'Voice recognition not available'}
        
        try:
            # Create audio data object
            audio_io = io.BytesIO(audio_data)
            
            with sr.AudioFile(audio_io) as source:
                audio = self.recognizer.record(source)
            
            # Try Google Speech Recognition (free)
            try:
                text = self.recognizer.recognize_google(audio, language=language)
                logger.info(f"Speech recognized: {text}")
                
                return {
                    'success': True,
                    'text': text,
                    'language': language,
                    'engine': 'google'
                }
            except sr.UnknownValueError:
                logger.warning("Speech not understood")
                return {
                    'success': False,
                    'error': 'speech_not_understood',
                    'message': 'Could not understand the audio'
                }
            except sr.RequestError as e:
                logger.error(f"Google Speech Recognition error: {e}")
                return {
                    'success': False,
                    'error': 'api_error',
                    'message': str(e)
                }
        
        except Exception as e:
            logger.error(f"Error recognizing speech: {e}")
            return {
                'success': False,
                'error': 'exception',
                'message': str(e)
            }
    
    async def process_voice_message(self, ogg_data: bytes, language: str = 'en') -> Dict:
        """
        Process voice message (convert and recognize).
        
        Args:
            ogg_data: OGG audio data from Telegram
            language: User's language preference
        
        Returns:
            Recognition result with error codes for localization
        """
        # Check dependencies
        if not SR_AVAILABLE:
            return {
                'success': False,
                'error': 'speechrecognition_missing',
                'message': 'SpeechRecognition library not installed'
            }
        
        if not PYDUB_AVAILABLE:
            return {
                'success': False,
                'error': 'pydub_missing',
                'message': 'pydub library not installed'
            }
        
        if not FFMPEG_AVAILABLE:
            return {
                'success': False,
                'error': 'ffmpeg_missing',
                'message': 'ffmpeg not found in system PATH'
            }
        
        try:
            # Convert OGG to WAV
            wav_data = await self.convert_ogg_to_wav(ogg_data)
            
            if not wav_data:
                return {
                    'success': False,
                    'error': 'conversion_failed',
                    'message': 'Failed to convert audio format'
                }
            
            # Recognize speech
            lang_code = 'ru-RU' if language == 'ru' else 'en-US'
            result = await self.recognize_speech(wav_data, lang_code)
            
            return result
        
        except Exception as e:
            logger.error(f"Error processing voice message: {e}")
            return {
                'success': False,
                'error': 'exception',
                'message': str(e)
            }
    
    def parse_conversion_command(self, text: str) -> Optional[Dict]:
        """
        Parse conversion command from recognized text.
        
        Examples:
            "convert 100 dollars to euros"
            "100 USD to EUR"
            "сколько стоит 50 рублей в долларах"
        
        Args:
            text: Recognized text
        
        Returns:
            Parsed command or None
        """
        import re
        
        text = text.lower()
        
        # Pattern 1: "100 USD to EUR"
        pattern1 = r'(\d+(?:\.\d+)?)\s*([a-z]+)\s+(?:to|в|in)\s+([a-z]+)'
        match = re.search(pattern1, text, re.IGNORECASE)
        
        if match:
            return {
                'amount': float(match.group(1)),
                'from_currency': match.group(2).upper(),
                'to_currency': match.group(3).upper()
            }
        
        # Pattern 2: "convert 100 dollars to euros"
        pattern2 = r'(?:convert|конверт|сколько)\s+(\d+(?:\.\d+)?)\s+([a-z]+)'
        match = re.search(pattern2, text, re.IGNORECASE)
        
        if match:
            amount = float(match.group(1))
            currency = match.group(2).upper()
            
            # Try to find target currency
            to_pattern = r'(?:to|в|in)\s+([a-z]+)'
            to_match = re.search(to_pattern, text, re.IGNORECASE)
            
            if to_match:
                return {
                    'amount': amount,
                    'from_currency': currency,
                    'to_currency': to_match.group(1).upper()
                }
        
        # Pattern 3: Simple "100 bitcoin"
        pattern3 = r'(\d+(?:\.\d+)?)\s+(bitcoin|btc|ethereum|eth|dollars?|euros?|rubles?|рубл)'
        match = re.search(pattern3, text, re.IGNORECASE)
        
        if match:
            amount = float(match.group(1))
            currency_text = match.group(2).lower()
            
            # Map common names to codes
            currency_map = {
                'bitcoin': 'BTC',
                'btc': 'BTC',
                'ethereum': 'ETH',
                'eth': 'ETH',
                'dollar': 'USD',
                'dollars': 'USD',
                'euro': 'EUR',
                'euros': 'EUR',
                'ruble': 'RUB',
                'rubles': 'RUB',
                'рубл': 'RUB'
            }
            
            from_currency = currency_map.get(currency_text, currency_text.upper())
            
            # Default to USD if not specified
            return {
                'amount': amount,
                'from_currency': from_currency,
                'to_currency': 'USD'
            }
        
        return None
