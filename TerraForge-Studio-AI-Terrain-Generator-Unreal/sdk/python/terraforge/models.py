"""TerraForge SDK Data Models"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class BoundingBox:
    """Geographic bounding box"""
    north: float
    south: float
    east: float
    west: float
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "north": self.north,
            "south": self.south,
            "east": self.east,
            "west": self.west
        }


@dataclass
class GenerationStatus:
    """Terrain generation status"""
    id: str
    status: str  # pending, processing, completed, failed
    progress: int
    bbox: BoundingBox
    resolution: int
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GenerationStatus':
        bbox = BoundingBox(**data['bbox'])
        return cls(
            id=data['id'],
            status=data['status'],
            progress=data.get('progress', 0),
            bbox=bbox,
            resolution=data['resolution'],
            created_at=data['created_at'],
            completed_at=data.get('completed_at'),
            error=data.get('error'),
            result=data.get('result')
        )


@dataclass
class ExportResult:
    """Export result"""
    id: str
    format: str
    status: str  # pending, processing, completed, failed
    download_url: Optional[str] = None
    file_size: Optional[int] = None
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    error: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExportResult':
        return cls(
            id=data['id'],
            format=data['format'],
            status=data['status'],
            download_url=data.get('download_url'),
            file_size=data.get('file_size'),
            created_at=data.get('created_at'),
            expires_at=data.get('expires_at'),
            error=data.get('error')
        )


class ExportFormat:
    """Available export formats"""
    GODOT = "godot"
    UNITY = "unity"
    UNREAL = "unreal"
    CRYENGINE = "cryengine"
    GLTF = "gltf"
    GEOTIFF = "geotiff"
