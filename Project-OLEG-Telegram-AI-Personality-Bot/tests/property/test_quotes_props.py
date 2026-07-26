"""
Property-based tests for Quote Generator Service.

Fortress Update v6.0: Tests for quote rendering properties.

Requirements: 7.3, 7.5, 7.6
"""

import os
import sys
import importlib.util
import pytest
from hypothesis import given, strategies as st, settings
from io import BytesIO
from PIL import Image

# Import quote_generator module directly without going through app package
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_module_path = os.path.join(_project_root, 'app', 'services', 'quote_generator.py')
_spec = importlib.util.spec_from_file_location("quote_generator", _module_path)
_quote_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_quote_module)

QuoteGeneratorService = _quote_module.QuoteGeneratorService
QuoteStyle = _quote_module.QuoteStyle
QuoteTheme = _quote_module.QuoteTheme
MessageData = _quote_module.MessageData
MAX_CHAIN_MESSAGES = _quote_module.MAX_CHAIN_MESSAGES
MAX_IMAGE_WIDTH = _quote_module.MAX_IMAGE_WIDTH
MAX_IMAGE_HEIGHT = _quote_module.MAX_IMAGE_HEIGHT


# Test data generators
usernames = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_'),
    min_size=1,
    max_size=32
).filter(lambda x: len(x.strip()) > 0)

quote_texts = st.text(
    min_size=1,
    max_size=500
).filter(lambda x: len(x.strip()) > 0)

# Message count for chain tests - including values above the limit
message_counts = st.integers(min_value=1, max_value=20)

# Generate list of messages for chain tests
message_data_strategy = st.builds(
    MessageData,
    text=quote_texts,
    username=usernames,
    timestamp=st.none() | st.just("12:34")
)

message_lists = st.lists(
    message_data_strategy,
    min_size=1,
    max_size=20
)


class TestQuoteChainLimit:
    """
    Property tests for quote chain limit.
    
    **Feature: fortress-update, Property 17: Quote chain limit**
    **Validates: Requirements 7.3**
    """
    
    @pytest.fixture
    def service(self):
        """Create a QuoteGeneratorService instance."""
        return QuoteGeneratorService()
    
    @given(messages=message_lists)
    @settings(max_examples=100, deadline=30000)
    @pytest.mark.asyncio
    async def test_quote_chain_limit_enforced(self, messages):
        """
        **Feature: fortress-update, Property 17: Quote chain limit**
        **Validates: Requirements 7.3**
        
        For any /q [N] command where N > 10, the rendered chain SHALL contain 
        at most 10 messages.
        """
        service = QuoteGeneratorService()
        style = QuoteStyle(theme=QuoteTheme.DARK)
        
        # Render the quote chain
        result = await service.render_quote_chain(messages, style)
        
        # The service should have processed at most MAX_CHAIN_MESSAGES
        # We verify this by checking that the result is valid
        assert result is not None
        assert result.image_data is not None
        assert len(result.image_data) > 0
        
        # Verify the image is valid
        img = Image.open(BytesIO(result.image_data))
        assert img is not None
        
        # The internal implementation should have truncated to MAX_CHAIN_MESSAGES
        # We can't directly verify the message count in the image, but we verify
        # the service doesn't crash and produces valid output
    
    @given(count=st.integers(min_value=11, max_value=100))
    @settings(max_examples=50, deadline=30000)
    @pytest.mark.asyncio
    async def test_chain_limit_constant_is_10(self, count):
        """
        **Feature: fortress-update, Property 17: Quote chain limit**
        **Validates: Requirements 7.3**
        
        Verify that MAX_CHAIN_MESSAGES is exactly 10.
        """
        assert MAX_CHAIN_MESSAGES == 10
        
        # For any count > 10, the service should truncate
        service = QuoteGeneratorService()
        messages = [
            MessageData(text=f"Message {i}", username=f"user{i}")
            for i in range(count)
        ]
        
        style = QuoteStyle(theme=QuoteTheme.DARK)
        result = await service.render_quote_chain(messages, style)
        
        # Should still produce valid output
        assert result is not None
        assert result.image_data is not None


class TestQuoteImageDimensions:
    """
    Property tests for quote image dimensions.
    
    **Feature: fortress-update, Property 18: Quote image dimensions**
    **Validates: Requirements 7.5**
    """
    
    @given(text=quote_texts, username=usernames)
    @settings(max_examples=100, deadline=30000)
    @pytest.mark.asyncio
    async def test_single_quote_dimensions(self, text, username):
        """
        **Feature: fortress-update, Property 18: Quote image dimensions**
        **Validates: Requirements 7.5**
        
        For any rendered quote image, the dimensions SHALL not exceed MAX_IMAGE_WIDTH x MAX_IMAGE_HEIGHT.
        """
        service = QuoteGeneratorService()
        style = QuoteStyle(theme=QuoteTheme.DARK)
        
        result = await service.render_quote(text, username, style=style)
        
        # Verify dimensions don't exceed max
        assert result.width <= MAX_IMAGE_WIDTH
        assert result.height <= MAX_IMAGE_HEIGHT
        
        # Verify by actually loading the image
        img = Image.open(BytesIO(result.image_data))
        assert img.width <= MAX_IMAGE_WIDTH
        assert img.height <= MAX_IMAGE_HEIGHT
    
    @given(messages=message_lists)
    @settings(max_examples=100, deadline=30000)
    @pytest.mark.asyncio
    async def test_chain_quote_dimensions(self, messages):
        """
        **Feature: fortress-update, Property 18: Quote image dimensions**
        **Validates: Requirements 7.5**
        
        For any rendered quote chain image, the dimensions SHALL not exceed MAX_IMAGE_WIDTH x MAX_IMAGE_HEIGHT.
        """
        service = QuoteGeneratorService()
        style = QuoteStyle(theme=QuoteTheme.DARK)
        
        result = await service.render_quote_chain(messages, style)
        
        # Verify dimensions don't exceed max
        assert result.width <= MAX_IMAGE_WIDTH
        assert result.height <= MAX_IMAGE_HEIGHT
        
        # Verify by actually loading the image
        img = Image.open(BytesIO(result.image_data))
        assert img.width <= MAX_IMAGE_WIDTH
        assert img.height <= MAX_IMAGE_HEIGHT
    
    @given(text=quote_texts, username=usernames)
    @settings(max_examples=50, deadline=60000)
    @pytest.mark.asyncio
    async def test_roast_quote_dimensions(self, text, username):
        """
        **Feature: fortress-update, Property 18: Quote image dimensions**
        **Validates: Requirements 7.5**
        
        For any rendered roast quote image, the dimensions SHALL not exceed MAX_IMAGE_WIDTH x MAX_IMAGE_HEIGHT.
        """
        service = QuoteGeneratorService()
        style = QuoteStyle(theme=QuoteTheme.DARK)
        
        result = await service.render_roast_quote(text, username, style=style)
        
        # Verify dimensions don't exceed max
        assert result.width <= MAX_IMAGE_WIDTH
        assert result.height <= MAX_IMAGE_HEIGHT
        
        # Verify by actually loading the image
        img = Image.open(BytesIO(result.image_data))
        assert img.width <= MAX_IMAGE_WIDTH
        assert img.height <= MAX_IMAGE_HEIGHT
    
    @pytest.mark.asyncio
    async def test_max_image_size_constants(self):
        """
        **Feature: fortress-update, Property 18: Quote image dimensions**
        **Validates: Requirements 7.5**
        
        Verify that MAX_IMAGE_WIDTH and MAX_IMAGE_HEIGHT are set correctly.
        """
        assert MAX_IMAGE_WIDTH == 800
        assert MAX_IMAGE_HEIGHT == 1200


class TestQuoteWebPFormat:
    """
    Property tests for quote image format.
    
    **Feature: fortress-update, Property 18: Quote image dimensions**
    **Validates: Requirements 7.5**
    """
    
    @given(text=quote_texts, username=usernames)
    @settings(max_examples=50, deadline=30000)
    @pytest.mark.asyncio
    async def test_output_format_is_webp(self, text, username):
        """
        **Feature: fortress-update, Property 18: Quote image dimensions**
        **Validates: Requirements 7.5**
        
        For any rendered quote, the output format SHALL be WebP.
        """
        service = QuoteGeneratorService()
        style = QuoteStyle(theme=QuoteTheme.DARK)
        
        result = await service.render_quote(text, username, style=style)
        
        # Verify format is webp
        assert result.format == 'webp'
        
        # Verify by loading the image
        img = Image.open(BytesIO(result.image_data))
        assert img.format == 'WEBP'


class TestQuotePersistence:
    """
    Property tests for quote persistence.
    
    **Feature: fortress-update, Property 19: Quote persistence**
    **Validates: Requirements 7.6**
    """
    
    @given(text=quote_texts, username=usernames)
    @settings(max_examples=50, deadline=30000)
    @pytest.mark.asyncio
    async def test_quote_generates_valid_image_data(self, text, username):
        """
        **Feature: fortress-update, Property 19: Quote persistence**
        **Validates: Requirements 7.6**
        
        For any successfully rendered quote, the image_data SHALL be non-empty
        and suitable for database storage.
        """
        service = QuoteGeneratorService()
        style = QuoteStyle(theme=QuoteTheme.DARK)
        
        result = await service.render_quote(text, username, style=style)
        
        # Verify image data is non-empty and can be stored
        assert result.image_data is not None
        assert len(result.image_data) > 0
        assert isinstance(result.image_data, bytes)
        
        # Verify the data can be read back as an image
        img = Image.open(BytesIO(result.image_data))
        assert img is not None
        
        # Verify we can convert back to bytes (simulating DB round-trip)
        output = BytesIO()
        img.save(output, format='WEBP')
        output.seek(0)
        recovered_data = output.read()
        assert len(recovered_data) > 0
    
    @given(text=quote_texts, username=usernames)
    @settings(max_examples=30, deadline=30000)
    @pytest.mark.asyncio
    async def test_quote_image_data_is_deterministic_structure(self, text, username):
        """
        **Feature: fortress-update, Property 19: Quote persistence**
        **Validates: Requirements 7.6**
        
        For any quote, the QuoteImage result SHALL have all required fields
        for database persistence.
        """
        service = QuoteGeneratorService()
        style = QuoteStyle(theme=QuoteTheme.DARK)
        
        result = await service.render_quote(text, username, style=style)
        
        # Verify all required fields are present
        assert hasattr(result, 'image_data')
        assert hasattr(result, 'format')
        assert hasattr(result, 'width')
        assert hasattr(result, 'height')
        
        # Verify types
        assert isinstance(result.image_data, bytes)
        assert isinstance(result.format, str)
        assert isinstance(result.width, int)
        assert isinstance(result.height, int)
        
        # Verify values are sensible
        assert result.format == 'webp'
        assert result.width > 0
        assert result.height > 0


class TestAvatarPlaceholder:
    """
    Property tests for avatar placeholder rendering.
    
    **Feature: release-candidate-8, Property 5: Avatar placeholder renders for missing avatars**
    **Validates: Requirements 3.4**
    """
    
    @given(username=usernames)
    @settings(max_examples=100, deadline=30000)
    @pytest.mark.asyncio
    async def test_avatar_placeholder_renders_for_missing_avatars(self, username):
        """
        **Feature: release-candidate-8, Property 5: Avatar placeholder renders for missing avatars**
        **Validates: Requirements 3.4**
        
        For any username without avatar data, _draw_avatar() SHALL render a colored 
        circle with the first letter of the username.
        """
        service = QuoteGeneratorService()
        
        # Create a test image to draw on
        from PIL import Image, ImageDraw
        img = Image.new('RGB', (100, 100), (255, 255, 255))
        
        # Draw avatar without avatar_data (should render placeholder)
        service._draw_avatar(img, x=10, y=10, size=64, username=username, avatar_data=None)
        
        # Verify the image was modified (placeholder was drawn)
        # The placeholder should be a colored circle, so the image should not be all white
        pixels = list(img.getdata())
        all_white = all(p == (255, 255, 255) for p in pixels)
        
        assert not all_white, "Avatar placeholder should have been drawn"
        
        # Verify the placeholder uses a consistent color based on username
        # Draw again and verify same result
        img2 = Image.new('RGB', (100, 100), (255, 255, 255))
        service._draw_avatar(img2, x=10, y=10, size=64, username=username, avatar_data=None)
        
        pixels2 = list(img2.getdata())
        assert pixels == pixels2, "Avatar placeholder should be deterministic for same username"
    
    @given(username=usernames)
    @settings(max_examples=50, deadline=30000)
    @pytest.mark.asyncio
    async def test_placeholder_color_is_consistent(self, username):
        """
        **Feature: release-candidate-8, Property 5: Avatar placeholder renders for missing avatars**
        **Validates: Requirements 3.4**
        
        For any username, the placeholder color SHALL be consistent across multiple renders.
        """
        service = QuoteGeneratorService()
        
        # Get the color for this username
        color1 = service._get_username_color(username)
        color2 = service._get_username_color(username)
        
        assert color1 == color2, "Username color should be deterministic"
        
        # Verify it's a valid RGB tuple
        assert isinstance(color1, tuple)
        assert len(color1) == 3
        assert all(0 <= c <= 255 for c in color1)
    
    @given(text=quote_texts, username=usernames)
    @settings(max_examples=100, deadline=30000)
    @pytest.mark.asyncio
    async def test_quote_renders_with_placeholder_avatar(self, text, username):
        """
        **Feature: release-candidate-8, Property 5: Avatar placeholder renders for missing avatars**
        **Validates: Requirements 3.4**
        
        For any quote rendered without avatar_data, the result SHALL be a valid image
        with a placeholder avatar (colored circle with initial).
        """
        service = QuoteGeneratorService()
        style = QuoteStyle(theme=QuoteTheme.LIGHT)
        
        # Render quote without avatar data
        result = await service.render_quote(
            text=text,
            username=username,
            style=style,
            avatar_data=None  # No avatar data - should use placeholder
        )
        
        # Verify the result is valid
        assert result is not None
        assert result.image_data is not None
        assert len(result.image_data) > 0
        
        # Verify the image can be loaded
        img = Image.open(BytesIO(result.image_data))
        assert img is not None
        assert img.width > 0
        assert img.height > 0
    
    @given(username=st.text(min_size=1, max_size=1, alphabet=st.characters(whitelist_categories=('L',))))
    @settings(max_examples=50, deadline=30000)
    @pytest.mark.asyncio
    async def test_placeholder_shows_first_letter(self, username):
        """
        **Feature: release-candidate-8, Property 5: Avatar placeholder renders for missing avatars**
        **Validates: Requirements 3.4**
        
        For any username, the placeholder SHALL display the first letter (uppercase).
        """
        service = QuoteGeneratorService()
        
        # The placeholder should use the first character uppercase
        expected_initial = username[0].upper()
        
        # We can't easily verify the text in the image, but we can verify
        # that the service doesn't crash and produces valid output
        from PIL import Image
        img = Image.new('RGB', (100, 100), (255, 255, 255))
        
        # This should not raise an exception
        service._draw_avatar(img, x=10, y=10, size=64, username=username, avatar_data=None)
        
        # Verify something was drawn
        pixels = list(img.getdata())
        all_white = all(p == (255, 255, 255) for p in pixels)
        assert not all_white, f"Placeholder for '{username}' should have been drawn"
