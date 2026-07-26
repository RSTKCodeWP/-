"""TerraForge Studio API Client"""

import time
from typing import Optional, Dict, Any
import requests
from .models import BoundingBox, GenerationStatus, ExportResult


class TerraForge:
    """TerraForge Studio API Client"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.terraforge.studio/v1",
        timeout: int = 30
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })
    
    def generate_terrain(
        self,
        bbox: BoundingBox,
        resolution: int = 30,
        source: str = "srtm",
        wait: bool = False,
        poll_interval: int = 2
    ) -> GenerationStatus:
        """Generate terrain from bounding box"""
        response = self.session.post(
            f"{self.base_url}/terrain/generate",
            json={
                "bbox": bbox.to_dict(),
                "resolution": resolution,
                "source": source
            },
            timeout=self.timeout
        )
        response.raise_for_status()
        
        result = GenerationStatus.from_dict(response.json())
        
        if wait:
            return self.wait_for_generation(result.id, poll_interval)
        
        return result
    
    def get_generation_status(self, generation_id: str) -> GenerationStatus:
        """Get generation status"""
        response = self.session.get(
            f"{self.base_url}/terrain/generate/{generation_id}",
            timeout=self.timeout
        )
        response.raise_for_status()
        return GenerationStatus.from_dict(response.json())
    
    def wait_for_generation(
        self,
        generation_id: str,
        poll_interval: int = 2,
        max_wait: int = 300
    ) -> GenerationStatus:
        """Wait for generation to complete"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status = self.get_generation_status(generation_id)
            
            if status.status in ['completed', 'failed']:
                return status
            
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Generation {generation_id} did not complete within {max_wait}s")
    
    def export_terrain(
        self,
        generation_id: str,
        format: str,
        options: Optional[Dict[str, Any]] = None,
        wait: bool = False,
        poll_interval: int = 2
    ) -> ExportResult:
        """Export terrain to game engine format"""
        payload = {
            "generation_id": generation_id,
            "format": format
        }
        if options:
            payload["options"] = options
        
        response = self.session.post(
            f"{self.base_url}/export",
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        result = ExportResult.from_dict(response.json())
        
        if wait:
            return self.wait_for_export(result.id, poll_interval)
        
        return result
    
    def get_export_status(self, export_id: str) -> ExportResult:
        """Get export status"""
        response = self.session.get(
            f"{self.base_url}/export/{export_id}",
            timeout=self.timeout
        )
        response.raise_for_status()
        return ExportResult.from_dict(response.json())
    
    def wait_for_export(
        self,
        export_id: str,
        poll_interval: int = 2,
        max_wait: int = 300
    ) -> ExportResult:
        """Wait for export to complete"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status = self.get_export_status(export_id)
            
            if status.status in ['completed', 'failed']:
                return status
            
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Export {export_id} did not complete within {max_wait}s")
    
    def get_history(self, limit: int = 10, offset: int = 0) -> Dict[str, Any]:
        """Get generation history"""
        response = self.session.get(
            f"{self.base_url}/history",
            params={"limit": limit, "offset": offset},
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
