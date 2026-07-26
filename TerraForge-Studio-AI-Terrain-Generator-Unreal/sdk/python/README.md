# TerraForge Studio Python SDK

Official Python SDK for TerraForge Studio API.

## Installation

```bash
pip install terraforge
```

## Quick Start

```python
from terraforge import TerraForge, BoundingBox, ExportFormat

# Initialize client
client = TerraForge(api_key="tfg_live_abc123...")

# Define area (Paris, France)
bbox = BoundingBox(
    north=48.8566,
    south=48.8466,
    east=2.3522,
    west=2.3422
)

# Generate terrain
generation = client.generate_terrain(
    bbox=bbox,
    resolution=30,
    wait=True  # Wait for completion
)

print(f"Status: {generation.status}")
print(f"Heightmap: {generation.result['heightmap_url']}")

# Export to Godot
export = client.export_terrain(
    generation_id=generation.id,
    format=ExportFormat.GODOT,
    options={
        "meshSubdivision": 128,
        "heightScale": 1.0
    },
    wait=True
)

print(f"Download: {export.download_url}")
```

## Features

- ✅ Terrain generation from bounding box
- ✅ Multiple export formats (Godot, Unity, UE5)
- ✅ Async/await support
- ✅ Progress tracking
- ✅ History management
- ✅ Type hints
- ✅ Error handling

## API Reference

### TerraForge

Main client class.

#### Constructor
```python
TerraForge(
    api_key: str,
    base_url: str = "https://api.terraforge.studio/v1",
    timeout: int = 30
)
```

#### Methods

##### generate_terrain()
```python
client.generate_terrain(
    bbox: BoundingBox,
    resolution: int = 30,
    source: str = "srtm",
    wait: bool = False,
    poll_interval: int = 2
) -> GenerationStatus
```

##### export_terrain()
```python
client.export_terrain(
    generation_id: str,
    format: str,
    options: Optional[Dict] = None,
    wait: bool = False
) -> ExportResult
```

##### get_history()
```python
client.get_history(
    limit: int = 10,
    offset: int = 0
) -> Dict
```

## Export Formats

```python
from terraforge import ExportFormat

ExportFormat.GODOT      # Godot Engine
ExportFormat.UNITY      # Unity
ExportFormat.UNREAL     # Unreal Engine 5
ExportFormat.GLTF       # glTF 2.0
ExportFormat.GEOTIFF    # GeoTIFF
```

## Examples

### Basic Generation
```python
bbox = BoundingBox(48.8566, 48.8466, 2.3522, 2.3422)
result = client.generate_terrain(bbox, resolution=30, wait=True)
```

### Check Status
```python
status = client.get_generation_status("gen_abc123")
print(f"Progress: {status.progress}%")
```

### Export to Unity
```python
export = client.export_terrain(
    generation_id="gen_abc123",
    format=ExportFormat.UNITY,
    options={
        "heightmapResolution": 513,
        "heightScale": 600,
        "bitDepth": 16
    }
)
```

### View History
```python
history = client.get_history(limit=10)
for item in history['items']:
    print(f"{item['id']}: {item['status']}")
```

## License

MIT License

## Support

- Documentation: https://docs.terraforge.studio
- API Reference: https://api.terraforge.studio/docs
- GitHub: https://github.com/terraforge/python-sdk
