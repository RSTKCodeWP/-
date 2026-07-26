"""Export service for converting builds to tarkov.dev format."""
import json
import logging
from typing import Dict, List, Optional
from io import BytesIO

logger = logging.getLogger(__name__)


class ExportService:
    """Service for exporting builds to various formats."""
    
    @staticmethod
    def build_to_tarkov_json(
        build_id: int,
        build_name: str,
        weapon_tarkov_id: str,
        modules: List[Dict[str, str]]
    ) -> str:
        """
        Generate JSON string in tarkov.dev format.
        
        Args:
            build_id: Build ID from database
            build_name: Name of the build
            weapon_tarkov_id: Tarkov.dev ID of the base weapon
            modules: List of dicts with 'tarkov_id' and 'slot_name'
            
        Returns:
            JSON string compatible with tarkov.dev/builds
        """
        # Filter modules that have both required fields
        valid_items = [
            {"id": m["tarkov_id"], "slot": m["slot_name"]}
            for m in modules
            if m.get("tarkov_id") and m.get("slot_name")
        ]
        
        export_data = {
            "id": f"user_build_{build_id}",
            "name": build_name or "Custom Build",
            "baseItemId": weapon_tarkov_id,
            "items": valid_items
        }
        
        return json.dumps(export_data, ensure_ascii=False, indent=2)
    
    @staticmethod
    def build_to_bytes(
        build_id: int,
        build_name: str,
        weapon_tarkov_id: str,
        modules: List[Dict[str, str]]
    ) -> BytesIO:
        """
        Generate BytesIO object with JSON for Telegram file upload.
        
        Args:
            build_id: Build ID
            build_name: Build name
            weapon_tarkov_id: Tarkov.dev weapon ID
            modules: List of module dicts
            
        Returns:
            BytesIO object containing JSON data
        """
        json_str = ExportService.build_to_tarkov_json(
            build_id, build_name, weapon_tarkov_id, modules
        )
        return BytesIO(json_str.encode('utf-8'))
    
    @staticmethod
    def generate_filename(weapon_name: str, build_name: Optional[str] = None) -> str:
        """
        Generate safe filename for export.
        
        Args:
            weapon_name: Name of the weapon
            build_name: Optional build name
            
        Returns:
            Safe filename string
        """
        # Clean weapon name
        safe_weapon = weapon_name.replace(" ", "_").replace("/", "-")
        
        if build_name:
            safe_build = build_name.replace(" ", "_").replace("/", "-")
            return f"eft_build_{safe_weapon}_{safe_build}.json"
        
        return f"eft_build_{safe_weapon}.json"
    
    @staticmethod
    def validate_export_data(
        weapon_tarkov_id: Optional[str],
        modules: List[Dict[str, str]]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate that export data is complete.
        
        Args:
            weapon_tarkov_id: Tarkov.dev weapon ID
            modules: List of module dicts
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not weapon_tarkov_id:
            return False, "weapon_missing_tarkov_id"
        
        if not modules:
            return False, "no_modules"
        
        # Check if at least one module has valid tarkov_id
        valid_modules = [
            m for m in modules 
            if m.get("tarkov_id") and m.get("slot_name")
        ]
        
        if not valid_modules:
            return False, "modules_missing_tarkov_ids"
        
        return True, None
