"""
Thumbnail generator for terrain heightmaps
Creates preview images for generation history
"""

import base64
import io
import logging
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class ThumbnailGenerator:
    """Generates thumbnail previews of terrain heightmaps"""

    def __init__(self, thumbnail_size: tuple = (400, 300)):
        """
        Initialize thumbnail generator

        Args:
            thumbnail_size: Size of generated thumbnails (width, height)
        """
        self.thumbnail_size = thumbnail_size

    def _finalize(self, thumbnail: Image.Image, output_path: Optional[Path]) -> str:
        """
        Save the thumbnail when a path is given and always return a data URI.

        Callers embed the returned value directly in an ``<img src>``, so this
        must be base64 whether or not the image was also written to disk.
        """
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            thumbnail.save(output_path, 'PNG', optimize=True)

        buffer = io.BytesIO()
        thumbnail.save(buffer, format='PNG', optimize=True)
        b64_data = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{b64_data}"


    def generate_from_heightmap(
        self,
        heightmap_path: Path,
        output_path: Optional[Path] = None
    ) -> Optional[str]:
        """
        Generate thumbnail from heightmap file

        Args:
            heightmap_path: Path to heightmap image
            output_path: Optional path to save thumbnail (if None, returns base64)

        Returns:
            Base64 encoded thumbnail or None if failed
        """
        try:
            # Load heightmap
            with Image.open(heightmap_path) as img:
                # Convert to grayscale if needed
                if img.mode != 'L':
                    img = img.convert('L')

                # Apply shading for better visualization
                shaded = self._apply_hillshade(np.array(img))

                # Create thumbnail
                thumbnail = Image.fromarray(shaded)
                thumbnail.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)

                return self._finalize(thumbnail, output_path)

        except Exception as e:
            logger.error(f"Failed to generate thumbnail: {e}")
            return None

    def _apply_hillshade(
        self,
        elevation: np.ndarray,
        azimuth: float = 315.0,
        altitude: float = 45.0
    ) -> np.ndarray:
        """
        Apply hillshade effect to elevation data

        Args:
            elevation: 2D array of elevation values
            azimuth: Light source azimuth (degrees)
            altitude: Light source altitude (degrees)

        Returns:
            Shaded elevation array (uint8)
        """
        try:
            # Normalize elevation to 0-1
            elevation = elevation.astype(float)
            elevation = (elevation - elevation.min()) / (elevation.max() - elevation.min() + 1e-10)

            # Calculate gradients
            dy, dx = np.gradient(elevation)

            # Calculate slope and aspect
            slope = np.arctan(np.sqrt(dx**2 + dy**2))
            aspect = np.arctan2(-dx, dy)

            # Convert angles to radians
            azimuth_rad = np.radians(azimuth)
            altitude_rad = np.radians(altitude)

            # Calculate hillshade
            hillshade = np.cos(altitude_rad) * np.cos(slope) + \
                       np.sin(altitude_rad) * np.sin(slope) * \
                       np.cos(azimuth_rad - aspect)

            # Normalize to 0-255
            hillshade = np.clip(hillshade, 0, 1)

            # Apply colormap (terrain-like)
            colored = self._apply_terrain_colormap(elevation, hillshade)

            return colored

        except Exception as e:
            logger.error(f"Hillshade calculation failed: {e}")
            # Fallback to simple grayscale
            return (elevation * 255).astype(np.uint8)

    def _apply_terrain_colormap(
        self,
        elevation: np.ndarray,
        hillshade: np.ndarray
    ) -> np.ndarray:
        """
        Apply terrain-style colormap to elevation data

        Args:
            elevation: Normalized elevation (0-1)
            hillshade: Hillshade values (0-1)

        Returns:
            RGB image array (uint8)
        """
        try:
            # Define color stops (elevation -> RGB)
            color_stops = [
                (0.0, [34, 102, 102]),    # Deep water
                (0.2, [68, 137, 112]),    # Shallow water
                (0.3, [136, 170, 85]),    # Low land
                (0.5, [204, 187, 85]),    # Plains
                (0.7, [153, 119, 85]),    # Hills
                (0.85, [187, 187, 187]),  # Mountains
                (1.0, [255, 255, 255]),   # Peaks
            ]

            # Create RGB image
            rgb = np.zeros((*elevation.shape, 3), dtype=np.uint8)

            # Interpolate colors based on elevation
            for i in range(len(color_stops) - 1):
                elev_start, color_start = color_stops[i]
                elev_end, color_end = color_stops[i + 1]

                mask = (elevation >= elev_start) & (elevation < elev_end)
                t = (elevation[mask] - elev_start) / (elev_end - elev_start + 1e-10)

                for c in range(3):
                    rgb[mask, c] = (
                        color_start[c] * (1 - t) + color_end[c] * t
                    ).astype(np.uint8)

            # Apply hillshading
            for c in range(3):
                rgb[:, :, c] = (rgb[:, :, c] * hillshade).astype(np.uint8)

            return rgb

        except Exception as e:
            logger.error(f"Colormap application failed: {e}")
            # Fallback to grayscale
            gray = (elevation * 255).astype(np.uint8)
            return np.stack([gray, gray, gray], axis=-1)

    def generate_from_array(
        self,
        elevation_data: np.ndarray,
        output_path: Optional[Path] = None
    ) -> Optional[str]:
        """
        Generate thumbnail directly from elevation array

        Args:
            elevation_data: 2D numpy array of elevation values
            output_path: Optional path to save thumbnail

        Returns:
            Base64 encoded thumbnail or path
        """
        try:
            # Apply shading
            shaded = self._apply_hillshade(elevation_data)

            # Create thumbnail
            thumbnail = Image.fromarray(shaded)
            thumbnail.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)

            return self._finalize(thumbnail, output_path)

        except Exception as e:
            logger.error(f"Failed to generate thumbnail from array: {e}")
            return None


def generate_thumbnail(
    source: Path | np.ndarray,
    output: Optional[Path] = None,
    size: tuple = (400, 300)
) -> Optional[str]:
    """
    Convenience function to generate thumbnail

    Args:
        source: Path to heightmap or elevation array
        output: Optional output path; the thumbnail is written there as well
        size: Thumbnail size (width, height)

    Returns:
        A ``data:image/png;base64,...`` URI, or None if generation failed.
    """
    generator = ThumbnailGenerator(thumbnail_size=size)

    if isinstance(source, Path):
        return generator.generate_from_heightmap(source, output)
    elif isinstance(source, np.ndarray):
        return generator.generate_from_array(source, output)
    else:
        raise TypeError("Source must be Path or numpy array")

