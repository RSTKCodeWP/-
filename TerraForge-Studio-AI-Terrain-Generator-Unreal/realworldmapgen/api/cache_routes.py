"""
Cache management API routes
"""

import logging

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cache", tags=["cache"])


@router.get("/stats")
async def get_cache_stats():
    """Get cache statistics"""
    try:
        from ..core.cache_manager import get_configured_cache_manager

        cache = get_configured_cache_manager()
        stats = cache.get_cache_stats()

        return stats
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/entries")
async def get_cache_entries():
    """Get all cache entries with metadata"""
    try:
        from ..core.cache_manager import get_configured_cache_manager

        cache = get_configured_cache_manager()
        entries = []

        for key, entry in cache.metadata.get("entries", {}).items():
            entries.append({
                "key": key,
                "size_mb": entry["size"] / (1024 * 1024),
                "created": entry["created"],
                "last_accessed": entry["last_accessed"],
                "access_count": entry.get("access_count", 0),
            })

        # Sort by last accessed (most recent first)
        entries.sort(key=lambda x: x["last_accessed"], reverse=True)

        return {
            "entries": entries,
            "count": len(entries)
        }
    except Exception as e:
        logger.error(f"Failed to get cache entries: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/clear")
async def clear_cache():
    """Clear entire cache"""
    try:
        from ..core.cache_manager import get_configured_cache_manager

        cache = get_configured_cache_manager()
        cache.clear_cache()

        logger.info("Cache cleared via API")

        return {
            "success": True,
            "message": "Cache cleared successfully"
        }
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{cache_key}")
async def delete_cache_entry(cache_key: str):
    """Delete specific cache entry"""
    try:
        from ..core.cache_manager import get_configured_cache_manager

        cache = get_configured_cache_manager()

        if cache_key not in cache.metadata.get("entries", {}):
            raise HTTPException(status_code=404, detail="Cache entry not found")

        cache.invalidate_cache(cache_key)

        logger.info(f"Cache entry deleted via API: {cache_key[:16]}...")

        return {
            "success": True,
            "message": f"Cache entry {cache_key[:16]}... deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete cache entry: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/entry/{cache_key}")
async def get_cache_entry(cache_key: str):
    """Get specific cache entry details"""
    try:
        from ..core.cache_manager import get_configured_cache_manager

        cache = get_configured_cache_manager()

        if cache_key not in cache.metadata.get("entries", {}):
            raise HTTPException(status_code=404, detail="Cache entry not found")

        entry = cache.metadata["entries"][cache_key]

        return {
            "key": cache_key,
            "path": entry["path"],
            "size_mb": entry["size"] / (1024 * 1024),
            "created": entry["created"],
            "last_accessed": entry["last_accessed"],
            "access_count": entry.get("access_count", 0),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get cache entry: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/optimize")
async def optimize_cache():
    """Optimize cache by removing least recently used entries if over limit"""
    try:
        from ..core.cache_manager import get_configured_cache_manager

        cache = get_configured_cache_manager()

        # Get current size
        current_size = cache.metadata.get("total_size", 0)

        if current_size > cache.max_cache_size:
            # Evict entries to get under limit
            cache._evict_old_entries(current_size - cache.max_cache_size)

            return {
                "success": True,
                "message": "Cache optimized",
                "freed_mb": (current_size - cache.metadata.get("total_size", 0)) / (1024 * 1024)
            }
        else:
            return {
                "success": True,
                "message": "Cache is already optimized",
                "freed_mb": 0
            }
    except Exception as e:
        logger.error(f"Failed to optimize cache: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

