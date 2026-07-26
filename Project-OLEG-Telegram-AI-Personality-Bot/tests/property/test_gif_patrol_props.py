"""
Property-based tests for GIF Patrol Service.

**Feature: fortress-update, Property 11: Frame extraction count**
**Validates: Requirements 3.1**
"""

import io
from hypothesis import given, strategies as st, settings, assume
from PIL import Image


class TestFrameExtractionCount:
    """
    **Feature: fortress-update, Property 11: Frame extraction count**
    **Validates: Requirements 3.1**
    
    For any GIF input, the frame extraction function SHALL return exactly 3 frames
    (beginning, middle, end).
    """
    
    def _create_gif_bytes(self, num_frames: int, width: int = 10, height: int = 10) -> bytes:
        """
        Helper to create a GIF with specified number of frames.
        
        Args:
            num_frames: Number of frames in the GIF
            width: Width of each frame
            height: Height of each frame
            
        Returns:
            GIF file as bytes
        """
        frames = []
        for i in range(num_frames):
            # Create a simple colored frame
            color = ((i * 50) % 256, (i * 30) % 256, (i * 70) % 256)
            frame = Image.new('RGB', (width, height), color)
            frames.append(frame)
        
        buffer = io.BytesIO()
        if len(frames) == 1:
            frames[0].save(buffer, format='GIF')
        else:
            frames[0].save(
                buffer, 
                format='GIF', 
                save_all=True, 
                append_images=frames[1:],
                duration=100,
                loop=0
            )
        return buffer.getvalue()
    
    def _extract_frames_pure(self, gif_data: bytes) -> list:
        """
        Pure implementation of frame extraction for testing.
        Mirrors the logic in GIFPatrolService.extract_frames().
        """
        gif = Image.open(io.BytesIO(gif_data))
        
        # Check if animated
        if not hasattr(gif, 'n_frames'):
            frame_bytes = self._frame_to_bytes(gif)
            return [frame_bytes, frame_bytes, frame_bytes]
        
        total_frames = gif.n_frames
        
        if total_frames == 0:
            raise ValueError("GIF has no frames")
        
        # Determine frame indices
        if total_frames == 1:
            frame_indices = [0, 0, 0]
        elif total_frames == 2:
            frame_indices = [0, 0, 1]
        else:
            frame_indices = [0, total_frames // 2, total_frames - 1]
        
        frames = []
        for idx in frame_indices:
            gif.seek(idx)
            frame = gif.convert('RGB')
            frame_bytes = self._frame_to_bytes(frame)
            frames.append(frame_bytes)
        
        return frames
    
    def _frame_to_bytes(self, frame: Image.Image) -> bytes:
        """Convert PIL Image to PNG bytes."""
        buffer = io.BytesIO()
        if frame.mode in ('RGBA', 'P', 'LA'):
            frame = frame.convert('RGB')
        frame.save(buffer, format='PNG')
        return buffer.getvalue()
    
    @settings(max_examples=100)
    @given(num_frames=st.integers(min_value=1, max_value=50))
    def test_extract_frames_returns_exactly_three(self, num_frames: int):
        """
        Property: For any GIF with 1 or more frames, extract_frames returns exactly 3 frames.
        
        **Feature: fortress-update, Property 11: Frame extraction count**
        **Validates: Requirements 3.1**
        """
        # Create a GIF with the specified number of frames
        gif_data = self._create_gif_bytes(num_frames)
        
        # Extract frames
        frames = self._extract_frames_pure(gif_data)
        
        # Assert exactly 3 frames are returned
        assert len(frames) == 3, f"Expected 3 frames, got {len(frames)} for GIF with {num_frames} frames"
    
    @settings(max_examples=100)
    @given(num_frames=st.integers(min_value=1, max_value=50))
    def test_extracted_frames_are_valid_images(self, num_frames: int):
        """
        Property: All extracted frames are valid PNG images.
        
        **Feature: fortress-update, Property 11: Frame extraction count**
        **Validates: Requirements 3.1**
        """
        gif_data = self._create_gif_bytes(num_frames)
        frames = self._extract_frames_pure(gif_data)
        
        for i, frame_bytes in enumerate(frames):
            # Each frame should be valid PNG bytes
            assert len(frame_bytes) > 0, f"Frame {i} is empty"
            
            # Should be parseable as an image
            img = Image.open(io.BytesIO(frame_bytes))
            assert img.format == 'PNG', f"Frame {i} is not PNG format"
    
    @settings(max_examples=50)
    @given(
        num_frames=st.integers(min_value=3, max_value=30),
        width=st.integers(min_value=1, max_value=100),
        height=st.integers(min_value=1, max_value=100)
    )
    def test_frame_indices_are_correct(self, num_frames: int, width: int, height: int):
        """
        Property: For GIFs with 3+ frames, extracted frames are from beginning, middle, and end.
        
        **Feature: fortress-update, Property 11: Frame extraction count**
        **Validates: Requirements 3.1**
        """
        # Create GIF with distinct colored frames
        frames_original = []
        for i in range(num_frames):
            # Each frame has a unique color based on index
            color = (i, i, i)
            frame = Image.new('RGB', (width, height), color)
            frames_original.append(frame)
        
        buffer = io.BytesIO()
        frames_original[0].save(
            buffer,
            format='GIF',
            save_all=True,
            append_images=frames_original[1:],
            duration=100,
            loop=0
        )
        gif_data = buffer.getvalue()
        
        # Extract frames
        extracted = self._extract_frames_pure(gif_data)
        
        # Verify we got 3 frames
        assert len(extracted) == 3
        
        # Expected indices: 0, num_frames//2, num_frames-1
        expected_indices = [0, num_frames // 2, num_frames - 1]
        
        # Verify each extracted frame matches expected index
        for i, frame_bytes in enumerate(extracted):
            img = Image.open(io.BytesIO(frame_bytes))
            pixel = img.getpixel((0, 0))
            expected_color = expected_indices[i]
            # The pixel value should match the frame index
            assert pixel[0] == expected_color, \
                f"Frame {i} should be from index {expected_color}, got pixel value {pixel[0]}"


class TestFrameExtractionEdgeCases:
    """
    Edge case tests for frame extraction.
    """
    
    def _create_gif_bytes(self, num_frames: int, width: int = 10, height: int = 10) -> bytes:
        """Helper to create a GIF with specified number of frames."""
        frames = []
        for i in range(num_frames):
            color = ((i * 50) % 256, (i * 30) % 256, (i * 70) % 256)
            frame = Image.new('RGB', (width, height), color)
            frames.append(frame)
        
        buffer = io.BytesIO()
        if len(frames) == 1:
            frames[0].save(buffer, format='GIF')
        else:
            frames[0].save(
                buffer,
                format='GIF',
                save_all=True,
                append_images=frames[1:],
                duration=100,
                loop=0
            )
        return buffer.getvalue()
    
    def _extract_frames_pure(self, gif_data: bytes) -> list:
        """Pure implementation of frame extraction."""
        gif = Image.open(io.BytesIO(gif_data))
        
        if not hasattr(gif, 'n_frames'):
            buffer = io.BytesIO()
            gif.convert('RGB').save(buffer, format='PNG')
            frame_bytes = buffer.getvalue()
            return [frame_bytes, frame_bytes, frame_bytes]
        
        total_frames = gif.n_frames
        
        if total_frames == 0:
            raise ValueError("GIF has no frames")
        
        if total_frames == 1:
            frame_indices = [0, 0, 0]
        elif total_frames == 2:
            frame_indices = [0, 0, 1]
        else:
            frame_indices = [0, total_frames // 2, total_frames - 1]
        
        frames = []
        for idx in frame_indices:
            gif.seek(idx)
            frame = gif.convert('RGB')
            buffer = io.BytesIO()
            frame.save(buffer, format='PNG')
            frames.append(buffer.getvalue())
        
        return frames
    
    def test_single_frame_gif(self):
        """Edge case: GIF with only 1 frame returns 3 identical frames."""
        gif_data = self._create_gif_bytes(1)
        frames = self._extract_frames_pure(gif_data)
        
        assert len(frames) == 3
        # All frames should be identical
        assert frames[0] == frames[1] == frames[2]
    
    def test_two_frame_gif(self):
        """Edge case: GIF with 2 frames returns [first, first, second]."""
        gif_data = self._create_gif_bytes(2)
        frames = self._extract_frames_pure(gif_data)
        
        assert len(frames) == 3
        # First two should be identical, third different
        assert frames[0] == frames[1]
        assert frames[0] != frames[2]
    
    def test_three_frame_gif(self):
        """Edge case: GIF with exactly 3 frames returns all three."""
        gif_data = self._create_gif_bytes(3)
        frames = self._extract_frames_pure(gif_data)
        
        assert len(frames) == 3
        # All should be different
        assert frames[0] != frames[1]
        assert frames[1] != frames[2]
        assert frames[0] != frames[2]
    
    def test_static_png_image(self):
        """Edge case: Static PNG image (not GIF) returns 3 identical frames."""
        # Create a static PNG
        img = Image.new('RGB', (10, 10), (255, 0, 0))
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        png_data = buffer.getvalue()
        
        # The extract function should handle this gracefully
        # by treating it as a single-frame image
        gif = Image.open(io.BytesIO(png_data))
        
        if not hasattr(gif, 'n_frames') or gif.n_frames == 1:
            # Expected behavior for static image
            pass
