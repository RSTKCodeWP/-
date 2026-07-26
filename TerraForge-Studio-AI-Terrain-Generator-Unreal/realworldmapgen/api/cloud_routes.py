"""
Cloud storage API routes
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cloud", tags=["cloud"])


class UploadRequest(BaseModel):
    local_path: str
    remote_path: str
    provider: Optional[str] = None
    metadata: Optional[dict] = None


@router.get("/providers")
async def list_providers():
    """List configured cloud storage providers"""
    try:
        from ..core.cloud_storage import get_cloud_storage

        cloud = get_cloud_storage()
        providers = cloud.list_providers()

        return {
            "providers": providers,
            "count": len(providers)
        }
    except Exception as e:
        logger.error(f"Failed to list providers: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/upload")
async def upload_file(request: UploadRequest):
    """Upload file to cloud storage"""
    try:
        from ..core.cloud_storage import get_cloud_storage

        cloud = get_cloud_storage()
        local_path = Path(request.local_path)

        if not local_path.exists():
            raise HTTPException(status_code=404, detail="Local file not found")

        url = await cloud.upload(
            local_path,
            request.remote_path,
            request.provider,
            request.metadata
        )

        if not url:
            raise HTTPException(status_code=500, detail="Upload failed")

        return {
            "success": True,
            "url": url,
            "remote_path": request.remote_path
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/upload-generation/{task_id}")
async def upload_generation(task_id: str, provider: Optional[str] = None):
    """Upload a completed generation to cloud storage"""
    try:
        from ..config import settings
        from ..core.cloud_storage import get_cloud_storage

        cloud = get_cloud_storage()

        # Find generation output directory
        output_dir = settings.output_dir / task_id

        if not output_dir.exists():
            raise HTTPException(status_code=404, detail="Generation not found")

        # Upload directory
        remote_prefix = f"generations/{task_id}"
        urls = await cloud.upload_directory(output_dir, remote_prefix, provider)

        return {
            "success": True,
            "uploaded_count": len(urls),
            "urls": urls
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload generation: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/list/{provider}")
async def list_files(provider: str, prefix: str = ""):
    """List files in cloud storage"""
    try:
        from ..core.cloud_storage import get_cloud_storage

        cloud = get_cloud_storage()
        storage = cloud.get_provider(provider)

        if not storage:
            raise HTTPException(status_code=404, detail="Provider not found")

        files = await storage.list_files(prefix)

        return {
            "files": files,
            "count": len(files)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{provider}/{path:path}")
async def delete_file(provider: str, path: str):
    """Delete file from cloud storage"""
    try:
        from ..core.cloud_storage import get_cloud_storage

        cloud = get_cloud_storage()
        storage = cloud.get_provider(provider)

        if not storage:
            raise HTTPException(status_code=404, detail="Provider not found")

        success = await storage.delete_file(path)

        if not success:
            raise HTTPException(status_code=500, detail="Delete failed")

        return {
            "success": True,
            "message": f"File deleted: {path}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete file: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{provider}/url/{path:path}")
async def get_signed_url(provider: str, path: str, expires_in: int = 3600):
    """Get signed URL for file access"""
    try:
        from ..core.cloud_storage import get_cloud_storage

        cloud = get_cloud_storage()
        storage = cloud.get_provider(provider)

        if not storage:
            raise HTTPException(status_code=404, detail="Provider not found")

        url = await storage.get_url(path, expires_in)

        return {
            "url": url,
            "expires_in": expires_in
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get signed URL: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

