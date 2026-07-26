"""
Unity Terrain Exporter
Exports terrain heightmaps and data for Unity Engine
"""

import json
from pathlib import Path
from typing import Dict, Optional

import numpy as np
from PIL import Image

from ..base import BaseExporter, TerrainData


class UnityTerrainExporter(BaseExporter):
    """
    Export terrain for Unity Engine.

    Unity Terrain Requirements:
    - Resolution: 2^N + 1 (e.g., 513, 1025, 2049, 4097)
    - Format: RAW 16-bit little-endian
    - Height range: 0-65535 maps to terrain height

    Output files:
    - {name}_heightmap.raw - 16-bit RAW heightmap
    - {name}_splatmap.png - RGBA splatmap (R=rock, G=grass, B=dirt, A=sand)
    - {name}_metadata.json - Import settings
    - {name}_import_script.cs - C# Editor script
    """

    VALID_SIZES = [513, 1025, 2049, 4097]

    @property
    def format_name(self) -> str:
        return "Unity Terrain"

    @property
    def file_extensions(self) -> list[str]:
        return [".raw", ".png", ".json", ".cs"]

    def validate(self, terrain_data: TerrainData) -> tuple[bool, Optional[str]]:
        """Validate terrain data for Unity export"""

        if terrain_data.resolution not in self.VALID_SIZES:
            closest = min(
                self.VALID_SIZES, key=lambda x: abs(x - terrain_data.resolution)
            )
            return (
                False,
                f"Resolution {terrain_data.resolution} not valid for Unity. "
                f"Valid: {self.VALID_SIZES}. Closest: {closest}",
            )

        if terrain_data.heightmap is None:
            return False, "Heightmap data is missing"

        return True, None

    async def export(self, terrain_data: TerrainData) -> Dict[str, Path]:
        """Export terrain to Unity format"""

        # Auto-resize if needed
        is_valid, error = self.validate(terrain_data)
        if not is_valid:
            target_size = min(
                self.VALID_SIZES, key=lambda x: abs(x - terrain_data.resolution)
            )
            terrain_data.heightmap = self._resize_heightmap(
                terrain_data.heightmap, target_size
            )
            terrain_data.resolution = target_size

        output_files = {}

        # 1. Export heightmap
        heightmap_path = await self._export_heightmap(terrain_data)
        output_files["heightmap"] = heightmap_path

        # 2. Export splatmap (if weightmaps available)
        if terrain_data.weightmaps:
            splatmap_path = await self._export_splatmap(terrain_data)
            output_files["splatmap"] = splatmap_path

        # 3. Export metadata
        metadata_path = await self._export_metadata(terrain_data)
        output_files["metadata"] = metadata_path

        # 4. Generate C# import script
        script_path = await self._generate_import_script(terrain_data)
        output_files["import_script"] = script_path

        return output_files

    async def _export_heightmap(self, terrain_data: TerrainData) -> Path:
        """Export 16-bit RAW heightmap"""

        heightmap = terrain_data.heightmap

        # Normalize to 0-65535
        normalized = self._normalize_heightmap(heightmap, 0, 65535)
        heightmap_uint16 = normalized.astype(np.uint16)

        # Unity expects little-endian RAW
        filename = f"{terrain_data.name}_heightmap.raw"
        filepath = self.output_dir / filename

        heightmap_uint16.tofile(filepath)

        return filepath

    #: Splatmap channel order. Unity reads an RGBA alphamap where each channel
    #: is the weight of the terrain layer at the same index.
    SPLATMAP_LAYERS = ("rock", "grass", "dirt", "sand")

    async def _export_splatmap(self, terrain_data: TerrainData) -> Path:
        """
        Export the terrain splatmap (Unity alphamap) as an RGBA PNG.

        One channel per terrain layer, matching :attr:`SPLATMAP_LAYERS`. The
        generator produces weights that already sum to 1 per pixel, which is
        what Unity expects from an alphamap.

        This previously returned a path without writing anything, so the export
        result advertised a file that did not exist.
        """
        weightmaps = terrain_data.weightmaps or {}
        height, width = terrain_data.heightmap.shape

        splatmap = np.zeros((height, width, 4), dtype=np.uint8)
        for index, layer in enumerate(self.SPLATMAP_LAYERS):
            if layer not in weightmaps:
                continue

            weights = np.clip(np.nan_to_num(weightmaps[layer]), 0.0, 1.0)
            # export() may have resized the heightmap to a valid Unity terrain
            # size; the weightmaps still carry the requested resolution, so
            # they are brought to the same grid before being packed.
            if weights.shape != (height, width):
                weights = np.clip(self._resize_heightmap(weights, height), 0.0, 1.0)

            splatmap[:, :, index] = (weights * 255).astype(np.uint8)

        filename = f"{terrain_data.name}_splatmap.png"
        filepath = self.output_dir / filename

        Image.fromarray(splatmap, mode="RGBA").save(filepath)

        return filepath

    async def _export_metadata(self, terrain_data: TerrainData) -> Path:
        """Export metadata JSON"""

        metadata = self.create_metadata(terrain_data)

        # Calculate terrain dimensions
        bbox_width_deg = terrain_data.bbox_east - terrain_data.bbox_west
        bbox_height_deg = terrain_data.bbox_north - terrain_data.bbox_south

        # Approximate meters (1 degree ≈ 111km at equator)
        center_lat = (terrain_data.bbox_north + terrain_data.bbox_south) / 2
        width_m = bbox_width_deg * 111000 * np.cos(np.radians(center_lat))
        height_m = bbox_height_deg * 111000

        metadata["unity"] = {
            "terrain_resolution": terrain_data.resolution,
            "heightmap_resolution": terrain_data.resolution,
            "terrain_width": width_m,
            "terrain_length": height_m,
            "terrain_height": terrain_data.max_elevation
            - terrain_data.min_elevation,
            "import_settings": {
                "depth": "16bit",
                "resolution": f"{terrain_data.resolution}x{terrain_data.resolution}",
                "byte_order": "Little-Endian",
            },
        }

        filename = f"{terrain_data.name}_metadata.json"
        filepath = self.output_dir / filename

        with open(filepath, "w") as f:
            json.dump(metadata, f, indent=2)

        return filepath

    async def _generate_import_script(self, terrain_data: TerrainData) -> Path:
        """Generate C# Editor script for Unity"""

        width_m = 2048  # Default
        height_m = (
            terrain_data.max_elevation - terrain_data.min_elevation
        ) or 600

        script = f'''using UnityEngine;
using UnityEditor;
using System.IO;

public class TerraForgeImporter : EditorWindow
{{
    [MenuItem("Tools/TerraForge/Import Terrain")]
    static void ImportTerrain()
    {{
        string heightmapPath = EditorUtility.OpenFilePanel(
            "Select Heightmap RAW", "", "raw");

        if (string.IsNullOrEmpty(heightmapPath)) return;

        // Create terrain
        TerrainData terrainData = new TerrainData();
        terrainData.heightmapResolution = {terrain_data.resolution};
        terrainData.size = new Vector3({width_m}f, {height_m}f, {width_m}f);

        // Read RAW file
        byte[] heightmapBytes = File.ReadAllBytes(heightmapPath);
        float[,] heights = new float[{terrain_data.resolution}, {terrain_data.resolution}];

        for (int y = 0; y < {terrain_data.resolution}; y++)
        {{
            for (int x = 0; x < {terrain_data.resolution}; x++)
            {{
                int index = (y * {terrain_data.resolution} + x) * 2;
                ushort value = (ushort)(heightmapBytes[index] | (heightmapBytes[index + 1] << 8));
                heights[y, x] = value / 65535f;
            }}
        }}

        terrainData.SetHeights(0, 0, heights);

        // Create terrain GameObject
        GameObject terrainObj = Terrain.CreateTerrainGameObject(terrainData);
        terrainObj.name = "{terrain_data.name}";

        Debug.Log("Terrain imported successfully!");
    }}
}}
'''

        filename = f"{terrain_data.name}_import_script.cs"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(script)

        return filepath

