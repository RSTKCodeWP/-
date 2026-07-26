"""
GeoTIFF Exporter
Exports georeferenced elevation data as GeoTIFF
"""

import json
from pathlib import Path
from typing import Dict, Optional

try:
    import rasterio
    from rasterio.crs import CRS
    from rasterio.transform import from_bounds

    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False

from ..base import BaseExporter, TerrainData


class GeoTIFFExporter(BaseExporter):
    """
    Export terrain as GeoTIFF raster.

    GeoTIFF is a standard format for geospatial raster data:
    - QGIS, ArcGIS, GDAL compatible
    - Preserves coordinate reference system (CRS)
    - Professional GIS applications

    Output:
    - {name}_elevation.tif - Georeferenced elevation raster
    - {name}_metadata.json - Export metadata
    """

    @property
    def format_name(self) -> str:
        return "GeoTIFF"

    @property
    def file_extensions(self) -> list[str]:
        return [".tif", ".json"]

    def validate(self, terrain_data: TerrainData) -> tuple[bool, Optional[str]]:
        """Validate terrain data for GeoTIFF export"""
        if not RASTERIO_AVAILABLE:
            return False, "rasterio library not installed (pip install rasterio)"

        if terrain_data.heightmap is None:
            return False, "Heightmap data is missing"

        return True, None

    async def export(self, terrain_data: TerrainData) -> Dict[str, Path]:
        """Export terrain as GeoTIFF"""

        if not RASTERIO_AVAILABLE:
            raise ImportError("rasterio is required for GeoTIFF export")

        output_files = {}

        # Export elevation GeoTIFF
        geotiff_path = await self._export_geotiff(terrain_data)
        output_files["geotiff"] = geotiff_path

        # Export metadata
        metadata = self.create_metadata(terrain_data)
        metadata["geotiff"] = {
            "crs": terrain_data.crs,
            "bounds": {
                "left": terrain_data.bbox_west,
                "bottom": terrain_data.bbox_south,
                "right": terrain_data.bbox_east,
                "top": terrain_data.bbox_north,
            },
            "pixel_size": {
                "x": (terrain_data.bbox_east - terrain_data.bbox_west)
                / terrain_data.resolution,
                "y": (terrain_data.bbox_north - terrain_data.bbox_south)
                / terrain_data.resolution,
            },
        }

        metadata_path = self.output_dir / f"{terrain_data.name}_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        output_files["metadata"] = metadata_path

        return output_files

    async def _export_geotiff(self, terrain_data: TerrainData) -> Path:
        """Export elevation data as GeoTIFF"""

        heightmap = terrain_data.heightmap

        # Create affine transform (maps pixel coordinates to geographic coordinates)
        transform = from_bounds(
            terrain_data.bbox_west,
            terrain_data.bbox_south,
            terrain_data.bbox_east,
            terrain_data.bbox_north,
            heightmap.shape[1],  # width
            heightmap.shape[0],  # height
        )

        # Parse CRS
        crs = CRS.from_string(terrain_data.crs)

        # Export as GeoTIFF
        filename = f"{terrain_data.name}_elevation.tif"
        filepath = self.output_dir / filename

        with rasterio.open(
            filepath,
            "w",
            driver="GTiff",
            height=heightmap.shape[0],
            width=heightmap.shape[1],
            count=1,  # Number of bands
            dtype=heightmap.dtype,
            crs=crs,
            transform=transform,
            compress="lzw",  # Compression for smaller file size
        ) as dst:
            dst.write(heightmap, 1)  # Write to band 1

            # Add metadata tags
            dst.update_tags(
                AREA_OR_POINT="Point",
                SOURCE="TerraForge Studio",
                TERRAIN_NAME=terrain_data.name,
                MIN_ELEVATION=str(terrain_data.min_elevation),
                MAX_ELEVATION=str(terrain_data.max_elevation),
            )

        return filepath

