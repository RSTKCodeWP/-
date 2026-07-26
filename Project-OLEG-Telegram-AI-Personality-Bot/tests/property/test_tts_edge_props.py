"""
Property-based tests for EdgeTTSService file lifecycle.

**Feature: grand-casino-dictator, Property 20: TTS File Lifecycle**
**Validates: Requirements 15.3**

For any TTS generation request, a temporary file is created, used for sending,
and then deleted regardless of success or failure.
"""

import os
import sys
import asyncio
import importlib.util
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, strategies as st, settings, assume

# Import TTS Edge module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'tts_edge.py')
_spec = importlib.util.spec_from_file_location("tts_edge", _module_path)
_tts_edge_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tts_edge_module)

EdgeTTSService = _tts_edge_module.EdgeTTSService
TTSFileResult = _tts_edge_module.TTSFileResult


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for generating valid text for TTS
valid_text = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'S', 'Z')),
    min_size=1,
    max_size=500
).filter(lambda x: x.strip())

# Strategy for voice selection
voice_strategy = st.sampled_from(["male", "female", None])


# ============================================================================
# Property 20: TTS File Lifecycle
# ============================================================================

class TestTTSFileLifecycle:
    """
    **Feature: grand-casino-dictator, Property 20: TTS File Lifecycle**
    **Validates: Requirements 15.3**
    
    For any TTS generation request, a temporary file is created, used for sending,
    and then deleted regardless of success or failure.
    """
    
    def test_temp_path_generation_unique(self):
        """
        Property: Each temp path generated is unique.
        """
        service = EdgeTTSService()
        
        paths = [service._generate_temp_path() for _ in range(100)]
        
        # All paths should be unique
        assert len(paths) == len(set(paths)), "Generated paths are not unique"
    
    def test_temp_path_has_correct_format(self):
        """
        Property: Temp paths have correct prefix and suffix.
        """
        service = EdgeTTSService()
        
        for _ in range(10):
            path = service._generate_temp_path()
            filename = os.path.basename(path)
            
            assert filename.startswith(service.FILE_PREFIX), f"Path {path} missing prefix"
            assert filename.endswith(service.FILE_SUFFIX), f"Path {path} missing suffix"
    
    def test_delete_nonexistent_file_succeeds(self):
        """
        Property: Deleting a non-existent file returns True (idempotent).
        """
        service = EdgeTTSService()
        
        fake_path = "/tmp/nonexistent_file_12345.mp3"
        result = service.delete_temp_file(fake_path)
        
        assert result is True, "Deleting non-existent file should succeed"
    
    def test_delete_existing_file_removes_it(self):
        """
        Property: Deleting an existing file removes it from filesystem.
        """
        import tempfile
        
        service = EdgeTTSService()
        
        # Create a real temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            f.write(b"test audio data")
            temp_path = f.name
        
        assert os.path.exists(temp_path), "Temp file should exist before delete"
        
        result = service.delete_temp_file(temp_path)
        
        assert result is True, "Delete should return True"
        assert not os.path.exists(temp_path), "File should be deleted"
    
    @settings(max_examples=50)
    @given(text=valid_text)
    def test_property_20_synthesize_to_file_creates_result(self, text: str):
        """
        **Feature: grand-casino-dictator, Property 20: TTS File Lifecycle**
        **Validates: Requirements 15.3**
        
        For any valid text, synthesize_to_file returns a TTSFileResult
        with a valid file path.
        """
        assume(text.strip())
        
        service = EdgeTTSService()
        
        # Mock edge_tts to avoid actual API calls
        mock_communicate = MagicMock()
        mock_communicate.save = AsyncMock()
        
        with patch.dict('sys.modules', {'edge_tts': MagicMock()}):
            # Run async test
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(service.synthesize_to_file(text))
                
                # Result should always have a file path
                assert result.file_path is not None
                assert result.file_path.endswith(".mp3")
                assert service.FILE_PREFIX in result.file_path
                
                # Cleanup if file was created
                if os.path.exists(result.file_path):
                    os.remove(result.file_path)
            finally:
                loop.close()
    
    def test_empty_text_returns_error(self):
        """
        Property: Empty text returns result with error, no file created.
        """
        service = EdgeTTSService()
        
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(service.synthesize_to_file(""))
            
            assert result.created is False
            assert result.error is not None
            assert "Empty" in result.error or "empty" in result.error
        finally:
            loop.close()
    
    def test_whitespace_only_text_returns_error(self):
        """
        Property: Whitespace-only text returns result with error.
        """
        service = EdgeTTSService()
        
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(service.synthesize_to_file("   \n\t  "))
            
            assert result.created is False
            assert result.error is not None
        finally:
            loop.close()
    
    @settings(max_examples=20)
    @given(voice=voice_strategy)
    def test_voice_selection_valid(self, voice):
        """
        Property: Voice selection always results in valid voice name.
        """
        service = EdgeTTSService()
        
        if voice:
            service.set_voice(voice)
        
        # Voice name should always be one of the valid Russian voices
        assert service.voice_name in EdgeTTSService.RUSSIAN_VOICES.values()
    
    def test_russian_voices_available(self):
        """
        Property: Both Russian voices (Dmitry and Svetlana) are available.
        """
        assert "male" in EdgeTTSService.RUSSIAN_VOICES
        assert "female" in EdgeTTSService.RUSSIAN_VOICES
        assert EdgeTTSService.RUSSIAN_VOICES["male"] == "ru-RU-DmitryNeural"
        assert EdgeTTSService.RUSSIAN_VOICES["female"] == "ru-RU-SvetlanaNeural"


class TestTTSFileLifecycleIntegration:
    """
    Integration tests for the complete file lifecycle.
    
    **Feature: grand-casino-dictator, Property 20: TTS File Lifecycle**
    **Validates: Requirements 15.3**
    """
    
    def test_send_voice_lifecycle_file_deleted_on_success(self):
        """
        Property: After successful send_voice, temp file is deleted.
        
        Tests the complete lifecycle: Create → Send → Delete
        """
        import tempfile
        
        service = EdgeTTSService()
        
        # Create mock bot
        mock_bot = MagicMock()
        mock_bot.send_voice = AsyncMock()
        
        # Create a real temp file to simulate successful synthesis
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            f.write(b"fake audio data")
            temp_path = f.name
        
        # Patch the service to use our temp file
        original_generate = service._generate_temp_path
        service._generate_temp_path = lambda: temp_path
        
        # Create mock edge_tts module
        mock_edge_tts = MagicMock()
        mock_communicate_instance = MagicMock()
        
        async def mock_save(path):
            # File already exists from our setup
            pass
        
        mock_communicate_instance.save = mock_save
        mock_edge_tts.Communicate = MagicMock(return_value=mock_communicate_instance)
        
        with patch.dict('sys.modules', {'edge_tts': mock_edge_tts}):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    service.send_voice(mock_bot, 12345, "Test text")
                )
                
                # File should be deleted after send
                assert result.deleted is True
                assert not os.path.exists(temp_path), "Temp file should be deleted after send"
            finally:
                loop.close()
                service._generate_temp_path = original_generate
                # Cleanup just in case
                if os.path.exists(temp_path):
                    os.remove(temp_path)
    
    def test_send_voice_lifecycle_file_deleted_on_send_failure(self):
        """
        Property: Even if send fails, temp file is still deleted.
        """
        import tempfile
        
        service = EdgeTTSService()
        
        # Create mock bot that fails to send
        mock_bot = MagicMock()
        mock_bot.send_voice = AsyncMock(side_effect=Exception("Send failed"))
        
        # Create a real temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            f.write(b"fake audio data")
            temp_path = f.name
        
        # Patch the service
        original_generate = service._generate_temp_path
        service._generate_temp_path = lambda: temp_path
        
        # Create mock edge_tts module
        mock_edge_tts = MagicMock()
        mock_communicate_instance = MagicMock()
        
        async def mock_save(path):
            pass
        
        mock_communicate_instance.save = mock_save
        mock_edge_tts.Communicate = MagicMock(return_value=mock_communicate_instance)
        
        with patch.dict('sys.modules', {'edge_tts': mock_edge_tts}):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    service.send_voice(mock_bot, 12345, "Test text")
                )
                
                # Send should have failed
                assert result.sent is False
                assert result.error is not None
                
                # But file should STILL be deleted
                assert result.deleted is True
                assert not os.path.exists(temp_path), "Temp file should be deleted even on send failure"
            finally:
                loop.close()
                service._generate_temp_path = original_generate
                if os.path.exists(temp_path):
                    os.remove(temp_path)
    
    def test_send_voice_lifecycle_file_deleted_on_synthesis_failure(self):
        """
        Property: Even if synthesis fails, cleanup is attempted.
        """
        service = EdgeTTSService()
        
        mock_bot = MagicMock()
        
        # Mock edge_tts to fail by raising ImportError
        with patch.dict('sys.modules', {'edge_tts': None}):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    service.send_voice(mock_bot, 12345, "Test text")
                )
                
                # Synthesis should have failed
                assert result.created is False
                
                # Cleanup should still be attempted
                assert result.deleted is True
            finally:
                loop.close()


class TestTTSServiceConfiguration:
    """
    Tests for EdgeTTSService configuration.
    
    **Validates: Requirements 15.1, 15.2**
    """
    
    def test_default_voice_is_male(self):
        """
        Property: Default voice is male (Dmitry).
        """
        service = EdgeTTSService()
        
        assert service.voice_name == "ru-RU-DmitryNeural"
    
    def test_can_set_female_voice(self):
        """
        Property: Can switch to female voice (Svetlana).
        """
        service = EdgeTTSService(voice="female")
        
        assert service.voice_name == "ru-RU-SvetlanaNeural"
    
    def test_invalid_voice_keeps_default(self):
        """
        Property: Invalid voice name keeps current voice.
        """
        service = EdgeTTSService()
        original_voice = service.voice_name
        
        service.set_voice("invalid_voice")
        
        assert service.voice_name == original_voice
    
    def test_service_initially_available(self):
        """
        Property: Service is initially marked as available.
        """
        service = EdgeTTSService()
        
        assert service.is_available is True
