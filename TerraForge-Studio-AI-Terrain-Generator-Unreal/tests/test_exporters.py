"""
Tests for terrain exporters and the generator's derived layers.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from realworldmapgen.core.terrain_generator import TerraForgeGenerator
from realworldmapgen.exporters.base import TerrainData
from realworldmapgen.exporters.generic.gltf_exporter import GLTFExporter
from realworldmapgen.exporters.unity.terrain_exporter import UnityTerrainExporter
from realworldmapgen.exporters.unreal5.heightmap_exporter import Unreal5HeightmapExporter


@pytest.fixture
def terrain() -> TerrainData:
    """A small terrain with a deterministic, non-flat heightmap."""
    rows = np.linspace(0, 500, 64, dtype=np.float32)
    heightmap = np.tile(rows, (64, 1))

    return TerrainData(
        heightmap=heightmap,
        resolution=64,
        bbox_north=37.80,
        bbox_south=37.75,
        bbox_east=-122.40,
        bbox_west=-122.45,
        name="test_terrain",
    )


# ---------------------------------------------------------------------------
# TerrainData
# ---------------------------------------------------------------------------
def test_terrain_data_derives_elevation_range(terrain):
    assert terrain.min_elevation == pytest.approx(0.0)
    assert terrain.max_elevation == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# Unreal Engine 5
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ue5_export_resizes_to_a_valid_landscape_size(terrain, tmp_path):
    """UE5 landscapes only accept specific sizes; 64 must be snapped to 1009."""
    files = await Unreal5HeightmapExporter(tmp_path).export(terrain)

    assert terrain.resolution == 1009
    assert files["heightmap"].exists()

    metadata = json.loads(files["metadata"].read_text())
    assert metadata["unreal_engine_5"]["landscape_size"] == 1009


@pytest.mark.asyncio
async def test_ue5_heightmap_is_16bit_grayscale(terrain, tmp_path):
    from PIL import Image

    files = await Unreal5HeightmapExporter(tmp_path).export(terrain)

    with Image.open(files["heightmap"]) as image:
        assert image.mode in {"I;16", "I"}
        assert image.size == (1009, 1009)


def test_ue5_validate_reports_invalid_resolution(terrain, tmp_path):
    valid, error = Unreal5HeightmapExporter(tmp_path).validate(terrain)
    assert valid is False
    assert "1009" in error


# ---------------------------------------------------------------------------
# Unity
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unity_export_writes_raw_heightmap(terrain, tmp_path):
    files = await UnityTerrainExporter(tmp_path).export(terrain)

    heightmap = files["heightmap"]
    assert heightmap.exists()
    # Unity RAW heightmaps are 16-bit, so the file is 2 bytes per sample.
    side = int((heightmap.stat().st_size / 2) ** 0.5)
    assert side * side * 2 == heightmap.stat().st_size


# ---------------------------------------------------------------------------
# GLTF
# ---------------------------------------------------------------------------
def test_gltf_face_generation_is_correct():
    """The vectorized grid triangulation must match the naive loop."""
    rows, cols = 5, 7
    faces = GLTFExporter._build_faces(rows, cols)

    expected = []
    for i in range(rows - 1):
        for j in range(cols - 1):
            v0 = i * cols + j
            v1 = v0 + 1
            v2 = v0 + cols
            v3 = v2 + 1
            expected.append([v0, v1, v2])
            expected.append([v1, v3, v2])

    assert faces.tolist() == expected


def test_gltf_face_indices_stay_within_the_vertex_buffer():
    rows, cols = 33, 21
    faces = GLTFExporter._build_faces(rows, cols)

    assert faces.min() >= 0
    assert faces.max() < rows * cols
    assert len(faces) == (rows - 1) * (cols - 1) * 2


def test_gltf_decimation_caps_mesh_size(tmp_path):
    exporter = GLTFExporter(tmp_path, max_mesh_resolution=128)
    decimated = exporter._decimate(np.zeros((2048, 2048), dtype=np.float32))

    assert decimated.shape == (128, 128)


def test_gltf_decimation_leaves_small_meshes_alone(tmp_path):
    exporter = GLTFExporter(tmp_path, max_mesh_resolution=512)
    heightmap = np.zeros((64, 64), dtype=np.float32)

    assert exporter._decimate(heightmap).shape == (64, 64)


def test_gltf_vertex_colors_span_the_gradient():
    elevations = np.linspace(0, 1000, 256, dtype=np.float64)
    colors = GLTFExporter._generate_vertex_colors(elevations)

    assert colors.shape == (256, 4)
    assert colors.dtype == np.uint8
    assert (colors[:, 3] == 255).all()
    # Low ground is blue-dominant, peaks are white.
    assert colors[0][2] > colors[0][0]
    assert colors[-1].tolist() == [255, 255, 255, 255]


def test_gltf_vertex_colors_handle_flat_terrain():
    colors = GLTFExporter._generate_vertex_colors(np.full(16, 42.0))
    assert colors.shape == (16, 4)
    assert np.isfinite(colors).all()


# ---------------------------------------------------------------------------
# Weightmaps
# ---------------------------------------------------------------------------
def test_weightmaps_sum_to_one_per_pixel():
    elevation = np.random.default_rng(1).normal(500, 120, size=(48, 48)).astype(np.float32)

    weightmaps = TerraForgeGenerator._generate_weightmaps(elevation)

    assert set(weightmaps) == {"rock", "grass", "dirt", "sand"}
    total = sum(weightmaps.values())
    assert total == pytest.approx(np.ones((48, 48)), abs=1e-4)


def test_weightmaps_are_bounded():
    elevation = np.random.default_rng(2).normal(0, 300, size=(32, 32)).astype(np.float32)

    for layer in TerraForgeGenerator._generate_weightmaps(elevation).values():
        assert layer.min() >= 0.0
        assert layer.max() <= 1.0


def test_weightmaps_handle_flat_terrain():
    """A perfectly flat heightmap must not divide by a zero elevation span."""
    weightmaps = TerraForgeGenerator._generate_weightmaps(np.full((16, 16), 100.0, dtype=np.float32))

    for layer in weightmaps.values():
        assert np.isfinite(layer).all()


def test_weightmaps_handle_nan_input():
    elevation = np.full((16, 16), 100.0, dtype=np.float32)
    elevation[4:8, 4:8] = np.nan

    for layer in TerraForgeGenerator._generate_weightmaps(elevation).values():
        assert np.isfinite(layer).all()


# ---------------------------------------------------------------------------
# Synthetic fallback
# ---------------------------------------------------------------------------
def test_synthetic_terrain_is_deterministic():
    first = TerraForgeGenerator._generate_synthetic_terrain(32)
    second = TerraForgeGenerator._generate_synthetic_terrain(32)

    assert first.shape == (32, 32)
    assert np.array_equal(first, second)


# ---------------------------------------------------------------------------
# Export manifest integrity
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unity_splatmap_is_actually_written(terrain, tmp_path):
    """
    Every path an exporter reports must exist.

    _export_splatmap used to compute a filename and return it without writing
    anything, so the export result advertised a file that was never created.
    """
    terrain.weightmaps = {
        "rock": np.full((64, 64), 0.25, dtype=np.float32),
        "grass": np.full((64, 64), 0.25, dtype=np.float32),
        "dirt": np.full((64, 64), 0.25, dtype=np.float32),
        "sand": np.full((64, 64), 0.25, dtype=np.float32),
    }

    files = await UnityTerrainExporter(tmp_path).export(terrain)

    assert "splatmap" in files
    for label, path in files.items():
        assert path.exists(), f"exporter reported {label} at {path}, which does not exist"


@pytest.mark.asyncio
async def test_unity_splatmap_channels_carry_the_layers(terrain, tmp_path):
    """Unity reads an RGBA alphamap; one channel per terrain layer."""
    from PIL import Image

    terrain.weightmaps = {
        "rock": np.full((64, 64), 1.0, dtype=np.float32),
        "grass": np.zeros((64, 64), dtype=np.float32),
        "dirt": np.zeros((64, 64), dtype=np.float32),
        "sand": np.zeros((64, 64), dtype=np.float32),
    }

    files = await UnityTerrainExporter(tmp_path).export(terrain)

    with Image.open(files["splatmap"]) as image:
        assert image.mode == "RGBA"
        pixel = image.getpixel((0, 0))

    # rock is the first channel and is fully weighted here.
    assert pixel[0] == 255
    assert pixel[1:] == (0, 0, 0)


@pytest.mark.asyncio
async def test_unity_export_without_weightmaps_omits_the_splatmap(terrain, tmp_path):
    terrain.weightmaps = None

    files = await UnityTerrainExporter(tmp_path).export(terrain)

    assert "splatmap" not in files
    for path in files.values():
        assert path.exists()


@pytest.mark.asyncio
async def test_ue5_reported_files_all_exist(terrain, tmp_path):
    files = await Unreal5HeightmapExporter(tmp_path).export(terrain)

    for label, path in files.items():
        assert path.exists(), f"exporter reported {label} at {path}, which does not exist"
