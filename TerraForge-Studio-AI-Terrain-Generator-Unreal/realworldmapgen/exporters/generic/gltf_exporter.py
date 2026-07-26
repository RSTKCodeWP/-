"""
GLTF/GLB Exporter
Exports terrain as 3D mesh in GLTF format
"""

import json
from pathlib import Path
from typing import Dict, Optional

import numpy as np

try:
    import trimesh

    TRIMESH_AVAILABLE = True
except ImportError:
    TRIMESH_AVAILABLE = False

from ..base import BaseExporter, TerrainData


class GLTFExporter(BaseExporter):
    """
    Export terrain as GLTF/GLB 3D mesh.

    GLTF is a universal 3D format supported by:
    - Blender
    - Three.js, Babylon.js
    - Unity (via plugins)
    - Unreal Engine (via plugins)
    - Web browsers (AR/VR)

    Output:
    - {name}.gltf + {name}.bin (separate files)
    - OR {name}.glb (single binary file)
    """

    #: Beyond this many vertices per side a terrain mesh stops being useful in
    #: a real-time engine (and stops fitting in memory during export), so the
    #: heightmap is downsampled before triangulation.
    DEFAULT_MAX_MESH_RESOLUTION = 512

    def __init__(
        self,
        output_dir: Path,
        binary_format: bool = True,
        max_mesh_resolution: Optional[int] = None,
    ):
        """
        Args:
            binary_format: If True, export as .glb, else as .gltf
            max_mesh_resolution: Cap on mesh vertices per side. The heightmap
                is decimated to this size before triangulation.
        """
        super().__init__(output_dir)
        self.binary_format = binary_format
        self.max_mesh_resolution = max_mesh_resolution or self.DEFAULT_MAX_MESH_RESOLUTION

    @property
    def format_name(self) -> str:
        return "GLTF" if not self.binary_format else "GLB"

    @property
    def file_extensions(self) -> list[str]:
        return [".glb"] if self.binary_format else [".gltf", ".bin"]

    def validate(self, terrain_data: TerrainData) -> tuple[bool, Optional[str]]:
        """Validate terrain data for GLTF export"""
        if not TRIMESH_AVAILABLE:
            return False, "trimesh library not installed (pip install trimesh)"

        if terrain_data.heightmap is None:
            return False, "Heightmap data is missing"

        return True, None

    async def export(self, terrain_data: TerrainData) -> Dict[str, Path]:
        """Export terrain as GLTF mesh"""

        if not TRIMESH_AVAILABLE:
            raise ImportError("trimesh is required for GLTF export")

        output_files = {}

        # Generate 3D mesh from heightmap
        mesh = await self._generate_mesh(terrain_data)

        # Export to GLTF/GLB
        if self.binary_format:
            filename = f"{terrain_data.name}.glb"
            filepath = self.output_dir / filename
            mesh.export(filepath, file_type="glb")
            output_files["model"] = filepath
        else:
            filename = f"{terrain_data.name}.gltf"
            filepath = self.output_dir / filename
            mesh.export(filepath, file_type="gltf")
            output_files["model"] = filepath
            output_files["binary"] = self.output_dir / f"{terrain_data.name}.bin"

        # Export metadata
        metadata = self.create_metadata(terrain_data)
        metadata_path = self.output_dir / f"{terrain_data.name}_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        output_files["metadata"] = metadata_path

        return output_files

    def _decimate(self, heightmap: np.ndarray) -> np.ndarray:
        """Downsample the heightmap to at most ``max_mesh_resolution`` per side."""
        rows, cols = heightmap.shape
        limit = self.max_mesh_resolution

        if rows <= limit and cols <= limit:
            return heightmap

        row_idx = np.linspace(0, rows - 1, min(rows, limit)).astype(np.intp)
        col_idx = np.linspace(0, cols - 1, min(cols, limit)).astype(np.intp)
        return heightmap[np.ix_(row_idx, col_idx)]

    @staticmethod
    def _build_faces(rows: int, cols: int) -> np.ndarray:
        """
        Build the triangle index array for a regular grid.

        Fully vectorized: a 2048x2048 grid produces ~8.4M triangles, which a
        per-quad Python loop cannot generate in reasonable time or memory.
        """
        # Index of the top-left corner of every quad in the grid.
        row_starts = np.arange(rows - 1, dtype=np.int64)[:, None] * cols
        col_offsets = np.arange(cols - 1, dtype=np.int64)[None, :]

        v0 = (row_starts + col_offsets).ravel()
        v1 = v0 + 1
        v2 = v0 + cols
        v3 = v2 + 1

        # Two counter-clockwise triangles per quad.
        faces = np.empty((v0.size * 2, 3), dtype=np.int64)
        faces[0::2] = np.column_stack([v0, v1, v2])
        faces[1::2] = np.column_stack([v1, v3, v2])
        return faces

    async def _generate_mesh(self, terrain_data: TerrainData) -> "trimesh.Trimesh":
        """Generate 3D mesh from heightmap"""

        heightmap = self._decimate(np.asarray(terrain_data.heightmap, dtype=np.float64))
        heightmap = np.nan_to_num(heightmap, nan=0.0, posinf=0.0, neginf=0.0)
        rows, cols = heightmap.shape

        # Real-world extent in metres, accounting for longitude convergence.
        center_lat = (terrain_data.bbox_north + terrain_data.bbox_south) / 2
        width_m = (terrain_data.bbox_east - terrain_data.bbox_west) * 111_320 * np.cos(
            np.radians(center_lat)
        )
        height_m = (terrain_data.bbox_north - terrain_data.bbox_south) * 110_574

        x = np.linspace(0, width_m, cols)
        y = np.linspace(0, height_m, rows)
        grid_x, grid_y = np.meshgrid(x, y)

        vertices = np.column_stack(
            [grid_x.ravel(), grid_y.ravel(), heightmap.ravel() * terrain_data.vertical_scale]
        )
        faces = self._build_faces(rows, cols)

        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        mesh.visual.vertex_colors = self._generate_vertex_colors(heightmap.ravel())

        return mesh

    @staticmethod
    def _generate_vertex_colors(elevations: np.ndarray) -> np.ndarray:
        """
        Map elevation to an RGBA hypsometric gradient.

        Vectorized with :func:`numpy.interp` so a multi-million vertex mesh is
        coloured in one pass instead of a per-vertex Python loop.
        """
        e_min = float(elevations.min())
        e_max = float(elevations.max())

        if e_max <= e_min:
            normalized = np.zeros_like(elevations, dtype=np.float64)
        else:
            normalized = (elevations - e_min) / (e_max - e_min)

        # Control points: water -> lowland green -> earth brown -> snow white.
        stops = np.array([0.0, 0.33, 0.66, 1.0])
        reds = np.array([0.0, 0.0, 139.0, 255.0])
        greens = np.array([0.0, 255.0, 178.0, 255.0])
        blues = np.array([255.0, 0.0, 69.0, 255.0])

        colors = np.empty((normalized.size, 4), dtype=np.uint8)
        colors[:, 0] = np.interp(normalized, stops, reds).astype(np.uint8)
        colors[:, 1] = np.interp(normalized, stops, greens).astype(np.uint8)
        colors[:, 2] = np.interp(normalized, stops, blues).astype(np.uint8)
        colors[:, 3] = 255

        return colors

