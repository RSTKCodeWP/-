"""
Unreal Engine 5 Heightmap Exporter
Exports terrain heightmaps in UE5 Landscape format
"""

import json
from pathlib import Path
from typing import Dict, Optional

import numpy as np
from PIL import Image

from ..base import BaseExporter, TerrainData


class Unreal5HeightmapExporter(BaseExporter):
    """
    Export heightmaps for Unreal Engine 5 Landscape.

    UE5 Landscape Requirements:
    - Resolution: (2^N + 1) x (2^N + 1)
      Valid sizes: 1009, 2017, 4033, 8129
    - Format: 16-bit grayscale PNG or RAW
    - Height range: 0-65535 maps to -256m to +256m by default
      (configurable with Z Scale in UE5)

    Output files:
    - {name}_heightmap.png - 16-bit heightmap
    - {name}_metadata.json - Import settings
    - {name}_import_script.py - UE5 Python import script
    """

    # Valid Landscape sizes for UE5
    VALID_SIZES = [1009, 2017, 4033, 8129]

    def __init__(self, output_dir: Path, export_format: str = "16bit_png"):
        """
        Initialize UE5 heightmap exporter.

        Args:
            output_dir: Output directory path
            export_format: '16bit_png' or 'raw'
        """
        super().__init__(output_dir)
        self.export_format = export_format

    @property
    def format_name(self) -> str:
        return "Unreal Engine 5 Heightmap"

    @property
    def file_extensions(self) -> list[str]:
        if self.export_format == "raw":
            return [".raw", ".json", ".py"]
        return [".png", ".json", ".py"]

    def validate(self, terrain_data: TerrainData) -> tuple[bool, Optional[str]]:
        """Validate terrain data for UE5 export"""

        # Check if resolution is valid for UE5 Landscape
        if terrain_data.resolution not in self.VALID_SIZES:
            closest = min(self.VALID_SIZES, key=lambda x: abs(x - terrain_data.resolution))
            return (
                False,
                f"Resolution {terrain_data.resolution} is not valid for UE5 Landscape. "
                f"Valid sizes: {self.VALID_SIZES}. Closest valid size: {closest}",
            )

        # Check heightmap data
        if terrain_data.heightmap is None:
            return False, "Heightmap data is missing"

        return True, None

    async def export(self, terrain_data: TerrainData) -> Dict[str, Path]:
        """Export terrain to UE5 format"""

        # Validate first
        is_valid, error = self.validate(terrain_data)
        if not is_valid:
            # Auto-resize to nearest valid size
            target_size = min(
                self.VALID_SIZES, key=lambda x: abs(x - terrain_data.resolution)
            )
            print(
                f"Auto-resizing from {terrain_data.resolution} to {target_size} for UE5"
            )
            terrain_data.heightmap = self._resize_heightmap(
                terrain_data.heightmap, target_size
            )
            terrain_data.resolution = target_size

        output_files = {}

        # 1. Export heightmap
        heightmap_path = await self._export_heightmap(terrain_data)
        output_files["heightmap"] = heightmap_path

        # 2. Export metadata
        metadata_path = await self._export_metadata(terrain_data)
        output_files["metadata"] = metadata_path

        # 3. Generate import script
        script_path = await self._generate_import_script(terrain_data)
        output_files["import_script"] = script_path

        # 4. Generate README
        readme_path = await self._generate_readme(terrain_data)
        output_files["readme"] = readme_path

        return output_files

    async def _export_heightmap(self, terrain_data: TerrainData) -> Path:
        """Export 16-bit heightmap"""

        heightmap = terrain_data.heightmap

        # UE5 expects 0-65535 to map to height range
        # Default: -256m to +256m
        # We'll normalize to actual terrain range and provide scale in metadata

        # Normalize to 0-65535
        normalized = self._normalize_heightmap(heightmap, 0, 65535)

        # Convert to uint16
        heightmap_uint16 = normalized.astype(np.uint16)

        if self.export_format == "raw":
            # Export as RAW file (little-endian 16-bit)
            filename = f"{terrain_data.name}_heightmap.raw"
            filepath = self.output_dir / filename
            heightmap_uint16.tofile(filepath)
        else:
            # Export as 16-bit PNG
            filename = f"{terrain_data.name}_heightmap.png"
            filepath = self.output_dir / filename

            # Use PIL to save 16-bit grayscale PNG
            # A uint16 array already maps to PIL's "I;16" mode; passing mode
            # explicitly is deprecated and removed in Pillow 13.
            image = Image.fromarray(heightmap_uint16)
            image.save(filepath)

        return filepath

    async def _export_metadata(self, terrain_data: TerrainData) -> Path:
        """Export metadata JSON"""

        metadata = self.create_metadata(terrain_data)

        # Add UE5-specific metadata
        elevation_range = terrain_data.max_elevation - terrain_data.min_elevation

        metadata["unreal_engine_5"] = {
            "landscape_size": terrain_data.resolution,
            "section_size": "127x127",  # Recommended
            "sections_per_component": 1,
            "number_of_components": self._calculate_components(
                terrain_data.resolution
            ),
            "scale": {
                "x": 100.0,  # Default UE5 scale (1 unit = 100cm)
                "y": 100.0,
                "z": elevation_range / 512.0
                * 100.0,  # Scale Z to fit elevation range
            },
            "import_settings": {
                "material": "Auto",
                "layer_info": "None",
                "import_type": "Landscape",
            },
        }

        filename = f"{terrain_data.name}_metadata.json"
        filepath = self.output_dir / filename

        with open(filepath, "w") as f:
            json.dump(metadata, f, indent=2)

        return filepath

    async def _generate_import_script(self, terrain_data: TerrainData) -> Path:
        """Generate Python script for automatic import in UE5"""

        script_content = f'''"""
Unreal Engine 5 Landscape Import Script
Auto-generated by TerraForge Studio

Usage:
1. Copy this script to your UE5 project's Content/Python/ folder
2. In UE5, go to: Tools → Execute Python Script
3. Select this script

Or run from UE5 Python console:
>>> exec(open("path/to/this/script.py").read())
"""

import unreal

def import_landscape():
    """Import landscape from heightmap"""

    # Heightmap file path
    heightmap_path = r"{self.output_dir / (terrain_data.name + '_heightmap.png')}"

    # Landscape settings
    landscape_size = {terrain_data.resolution}
    section_size = 127
    sections_per_component = 1

    # Calculate scale
    elevation_range = {terrain_data.max_elevation - terrain_data.min_elevation}
    z_scale = elevation_range / 512.0 * 100.0

    print(f"Importing landscape: {{landscape_size}}x{{landscape_size}}")
    print(f"Z Scale: {{z_scale}}")

    # Import settings
    landscape_import_data = unreal.LandscapeImportLayerInfo()

    # TODO: Implement actual import using UE5 Python API
    # This requires UE5.1+ with Python Editor Scripting enabled

    print("Heightmap ready for manual import:")
    print(f"  File: {{heightmap_path}}")
    print(f"  Size: {{landscape_size}} x {{landscape_size}}")
    print(f"  Section Size: {{section_size}}")
    print(f"  Z Scale: {{z_scale}}")

    print("\\nManual Import Steps:")
    print("1. Landscape Mode → Manage → Import from File")
    print("2. Select heightmap file")
    print("3. Set Section Size: 127x127")
    print("4. Set Sections Per Component: 1")
    print(f"5. Set Scale: X=100, Y=100, Z={{z_scale}}")

if __name__ == "__main__":
    import_landscape()
'''

        filename = f"{terrain_data.name}_import_script.py"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(script_content)

        return filepath

    async def _generate_readme(self, terrain_data: TerrainData) -> Path:
        """Generate README with import instructions"""

        readme_content = f"""# {terrain_data.name} - Unreal Engine 5 Import Guide

## Quick Import

### Method 1: Manual Import (Recommended)

1. Open your UE5 project
2. Enable **Landscape Mode** (Shift + 2)
3. Click **Manage** tab → **Import from File**
4. Select heightmap: `{terrain_data.name}_heightmap.png`
5. Configure settings:
   - **Section Size**: 127 x 127 quads
   - **Sections Per Component**: 1
   - **Number of Components**: {self._calculate_components(terrain_data.resolution)}
   - **Scale**:
     - X: 100.0
     - Y: 100.0
     - Z: {(terrain_data.max_elevation - terrain_data.min_elevation) / 512.0 * 100.0:.2f}
6. Click **Import**

### Method 2: Python Script (UE5.1+)

1. Copy `{terrain_data.name}_import_script.py` to your project
2. In UE5: Tools → Execute Python Script
3. Select the import script

## Terrain Information

- **Resolution**: {terrain_data.resolution} x {terrain_data.resolution}
- **Elevation Range**: {terrain_data.min_elevation:.1f}m to {terrain_data.max_elevation:.1f}m
- **Geographic Bounds**:
  - North: {terrain_data.bbox_north}
  - South: {terrain_data.bbox_south}
  - East: {terrain_data.bbox_east}
  - West: {terrain_data.bbox_west}

## Next Steps

1. **Create Landscape Material**:
   - Use weightmaps for material blending (if exported)
   - Add texture layers (grass, rock, dirt, etc.)

2. **Optimize Performance**:
   - Enable Nanite for high-poly meshes
   - Use LODs for distant terrain
   - Enable Landscape Streaming

3. **Add Details**:
   - Import vegetation (foliage tool)
   - Import buildings (static meshes)
   - Import roads (splines or decals)

## Files Included

- `{terrain_data.name}_heightmap.png` - 16-bit heightmap
- `{terrain_data.name}_metadata.json` - Metadata and settings
- `{terrain_data.name}_import_script.py` - Auto-import script
- This README file

## Support

For issues or questions:
- GitHub: https://github.com/bobberdolle1/TerraForge-Studio
- Documentation: See docs/UNREAL_IMPORT.md

Generated by TerraForge Studio
"""

        filename = f"{terrain_data.name}_README.txt"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(readme_content)

        return filepath

    def _calculate_components(self, landscape_size: int) -> str:
        """Calculate recommended number of components"""

        # UE5 formula: (Landscape Size - 1) / (Section Size * Sections Per Component) + 1
        section_size = 127
        sections_per_component = 1

        components_per_side = (landscape_size - 1) // (
            section_size * sections_per_component
        ) + 1

        return f"{components_per_side} x {components_per_side}"

