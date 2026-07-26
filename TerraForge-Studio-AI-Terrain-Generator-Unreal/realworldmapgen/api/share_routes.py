"""
Share Links API Routes
Enables sharing of terrain generation configurations
"""

import json
import logging
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/share", tags=["share"])

# In-memory storage (in production, use database)
share_links_storage: Dict[str, Dict[str, Any]] = {}
STORAGE_FILE = Path("./cache/share_links.json")


class ShareConfigModel(BaseModel):
    bbox: Dict[str, float]
    name: str
    resolution: int
    exportFormats: list[str]
    elevationSource: str
    enableRoads: bool
    enableBuildings: bool
    enableWeightmaps: bool
    presetId: Optional[str] = None


class ShareOptionsModel(BaseModel):
    expiresIn: Optional[int] = None  # milliseconds
    maxAccess: Optional[int] = None
    requireAuth: bool = False
    allowEdit: bool = False


class CreateShareRequest(BaseModel):
    config: ShareConfigModel
    options: ShareOptionsModel = ShareOptionsModel()
    metadata: Optional[Dict[str, Any]] = None


def load_storage():
    """Load share links from file"""
    global share_links_storage
    if STORAGE_FILE.exists():
        try:
            with open(STORAGE_FILE, 'r') as f:
                share_links_storage = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load share links: {e}")


def save_storage():
    """Save share links to file"""
    try:
        STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STORAGE_FILE, 'w') as f:
            json.dump(share_links_storage, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save share links: {e}")


def generate_short_id(length: int = 8) -> str:
    """Generate a short, URL-safe ID"""
    return secrets.token_urlsafe(length)[:length]


# Load storage on startup
load_storage()


@router.post("/create")
async def create_share_link(request: CreateShareRequest):
    """Create a new share link"""
    try:
        # Generate unique short ID
        short_id = generate_short_id()
        while short_id in share_links_storage:
            short_id = generate_short_id()

        # Calculate expiry
        expires_at = None
        if request.options.expiresIn and request.options.expiresIn > 0:
            expires_at = (datetime.now() + timedelta(milliseconds=request.options.expiresIn)).isoformat()

        # Create share link object
        share_link = {
            "id": short_id,
            "shortId": short_id,
            "createdAt": datetime.now().isoformat(),
            "expiresAt": expires_at,
            "accessCount": 0,
            "maxAccess": request.options.maxAccess,
            "isActive": True,
            "config": request.config.model_dump(),
            "metadata": request.metadata or {},
            "options": request.options.model_dump(),
        }

        # Store
        share_links_storage[short_id] = share_link
        save_storage()

        logger.info(f"Created share link: {short_id}")

        return {
            "shareLink": share_link,
            "url": f"/share/{short_id}",
            "shortUrl": short_id,
        }
    except Exception as e:
        logger.error(f"Failed to create share link: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{short_id}")
async def get_share_link(short_id: str):
    """Get share link by ID"""
    if short_id not in share_links_storage:
        raise HTTPException(status_code=404, detail="Share link not found")

    share_link = share_links_storage[short_id]

    # Check if active
    if not share_link.get("isActive", True):
        raise HTTPException(status_code=410, detail="Share link has been deactivated")

    # Check expiry
    if share_link.get("expiresAt"):
        expiry = datetime.fromisoformat(share_link["expiresAt"])
        if datetime.now() > expiry:
            share_link["isActive"] = False
            save_storage()
            raise HTTPException(status_code=410, detail="Share link has expired")

    # Check max access
    if share_link.get("maxAccess"):
        if share_link["accessCount"] >= share_link["maxAccess"]:
            share_link["isActive"] = False
            save_storage()
            raise HTTPException(status_code=410, detail="Share link access limit reached")

    # Increment access count
    share_link["accessCount"] += 1
    save_storage()

    return share_link


@router.get("/list")
async def list_share_links():
    """List all share links (in production, filter by user)"""
    return {
        "links": list(share_links_storage.values()),
        "count": len(share_links_storage)
    }


@router.post("/{short_id}/deactivate")
async def deactivate_share_link(short_id: str):
    """Deactivate a share link"""
    if short_id not in share_links_storage:
        raise HTTPException(status_code=404, detail="Share link not found")

    share_links_storage[short_id]["isActive"] = False
    save_storage()

    logger.info(f"Deactivated share link: {short_id}")

    return {"success": True, "message": "Share link deactivated"}


@router.delete("/{short_id}")
async def delete_share_link(short_id: str):
    """Delete a share link"""
    if short_id not in share_links_storage:
        raise HTTPException(status_code=404, detail="Share link not found")

    del share_links_storage[short_id]
    save_storage()

    logger.info(f"Deleted share link: {short_id}")

    return {"success": True, "message": "Share link deleted"}


@router.get("/{short_id}/stats")
async def get_share_link_stats(short_id: str):
    """Get statistics for a share link"""
    if short_id not in share_links_storage:
        raise HTTPException(status_code=404, detail="Share link not found")

    link = share_links_storage[short_id]

    return {
        "shortId": short_id,
        "accessCount": link.get("accessCount", 0),
        "maxAccess": link.get("maxAccess"),
        "isActive": link.get("isActive", True),
        "createdAt": link.get("createdAt"),
        "expiresAt": link.get("expiresAt"),
    }

