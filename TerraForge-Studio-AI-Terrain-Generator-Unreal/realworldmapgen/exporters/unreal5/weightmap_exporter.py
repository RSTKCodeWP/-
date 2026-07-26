"""
Unreal Engine 5 Weightmap Exporter
Exports material layer weightmaps for UE5 Landscape
"""

import json
from pathlib import Path
from typing import Dict, Optional

import numpy as np
from PIL import Image

from ..base import BaseExporter, TerrainData


class Unreal5WeightmapExporter(BaseExporter):
    """
    Export material layer weightmaps for UE5 Landscape.

    Weightmaps define material blending:
    - R channel: Rock/Stone
    - G channel: Grass/Vegetation
    - B channel: Dirt/Soil
    - A channel: Sand/Beach

    UE5 uses these to blend landscape materials based on slope, height, etc.
    """

    @property
    def format_name(self) -> str:
        return "Unreal Engine 5 Weightmaps"

    @property
    def file_extensions(self) -> list[str]:
        return [".png"]

    def validate(self, terrain_data: TerrainData) -> tuple[bool, Optional[str]]:
        """Validate terrain data for weightmap export"""
        if terrain_data.heightmap is None:
            return False, "Heightmap data is missing"
        return True, None

    async def export(self, terrain_data: TerrainData) -> Dict[str, Path]:
        """Export weightmaps for UE5"""

        output_files = {}

        # Generate weightmaps if not provided
        if terrain_data.weightmaps is None:
            weightmaps = await self._generate_weightmaps(terrain_data)
        else:
            weightmaps = terrain_data.weightmaps

        # Export each channel as separate PNG (or combined RGBA)
        weightmap_rgba = np.zeros(
            (*terrain_data.heightmap.shape, 4), dtype=np.uint8
        )

        channel_names = {"R": "rock", "G": "grass", "B": "dirt", "A": "sand"}

        for idx, (_channel, name) in enumerate(channel_names.items()):
            if name in weightmaps:
                weightmap_rgba[:, :, idx] = (weightmaps[name] * 255).astype(
                    np.uint8
                )

        # Save combined RGBA weightmap
        filename = f"{terrain_data.name}_weightmap.png"
        filepath = self.output_dir / filename

        image = Image.fromarray(weightmap_rgba)
        image.save(filepath)

        output_files["weightmap"] = filepath

        # Export metadata
        metadata = {
            "channels": {
                "R": "rock",
                "G": "grass",
                "B": "dirt",
                "A": "sand",
            },
            "usage": "Import as Landscape Layer Weightmap in UE5",
        }

        metadata_path = self.output_dir / f"{terrain_data.name}_weightmap_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        output_files["metadata"] = metadata_path

        return output_files

    async def _generate_weightmaps(
        self, terrain_data: TerrainData
    ) -> Dict[str, np.ndarray]:
        """
        Auto-generate weightmaps based on slope and height.

        Rules:
        - Rock: Steep slopes (>30°)
        - Grass: Gentle slopes (<20°), mid-elevation
        - Dirt: Medium slopes, transition areas
        - Sand: Low elevation, flat areas
        """

        heightmap = terrain_data.heightmap

        # Calculate slope
        dy, dx = np.gradient(heightmap)
        slope = np.degrees(np.arctan(np.sqrt(dx**2 + dy**2)))

        # Normalize height to 0-1
        height_norm = (heightmap - heightmap.min()) / (
            heightmap.max() - heightmap.min()
        )

        # Initialize weightmaps
        rock = np.zeros_like(heightmap, dtype=np.float32)
        grass = np.zeros_like(heightmap, dtype=np.float32)
        dirt = np.zeros_like(heightmap, dtype=np.float32)
        sand = np.zeros_like(heightmap, dtype=np.float32)

        # Rock: steep slopes
        rock = np.clip((slope - 30) / 30, 0, 1)

        # Sand: low elevation + flat
        sand = (1 - height_norm) * (1 - np.clip(slope / 15, 0, 1))

        # Grass: mid elevation + gentle slope
        grass = (
            (1 - np.abs(height_norm - 0.5) * 2) * (1 - np.clip(slope / 20, 0, 1))
        )

        # Dirt: everything else (transition)
        dirt = np.clip(1 - (rock + grass + sand), 0, 1)

        # Normalize so sum = 1 at each pixel
        total = rock + grass + dirt + sand
        total = np.maximum(total, 0.001)  # Avoid division by zero

        rock /= total
        grass /= total
        dirt /= total
        sand /= total

        return {"rock": rock, "grass": grass, "dirt": dirt, "sand": sand}

