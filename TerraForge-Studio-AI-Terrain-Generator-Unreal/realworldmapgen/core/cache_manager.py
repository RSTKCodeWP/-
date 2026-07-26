"""
Result caching system for terrain generations
Caches based on bbox + settings hash
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class TerrainCacheManager:
    """Manages caching of terrain generation results"""

    def __init__(self, cache_dir: Path, max_cache_size_gb: float = 10.0, max_age_days: int = 30):
        """
        Initialize cache manager

        Args:
            cache_dir: Directory to store cached results
            max_cache_size_gb: Maximum cache size in GB
            max_age_days: Maximum age of cached items in days
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_cache_size = max_cache_size_gb * 1024 * 1024 * 1024  # Convert to bytes
        self.max_age = timedelta(days=max_age_days)
        self.metadata_file = cache_dir / "cache_metadata.json"
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Any]:
        """Load cache metadata"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load cache metadata: {e}")
        return {"entries": {}, "total_size": 0}

    def _save_metadata(self):
        """Save cache metadata"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache metadata: {e}")

    def generate_cache_key(self, bbox: Dict, config: Dict) -> str:
        """
        Generate a unique cache key from bbox and configuration

        Args:
            bbox: Bounding box dictionary
            config: Generation configuration dictionary

        Returns:
            SHA256 hash as cache key
        """
        # Create a stable representation of the inputs
        cache_input = {
            # The terrain name is part of the key because output files are named
            # after it. Reusing another terrain's files under a new name would
            # produce artifacts whose filenames and embedded metadata disagree
            # with the request.
            "name": config.get("name"),
            "bbox": {
                "north": round(bbox.get("north", 0), 6),
                "south": round(bbox.get("south", 0), 6),
                "east": round(bbox.get("east", 0), 6),
                "west": round(bbox.get("west", 0), 6),
            },
            "config": {
                "resolution": config.get("resolution"),
                "export_formats": sorted(config.get("export_formats", [])),
                "elevation_source": config.get("elevation_source"),
                "enable_roads": config.get("enable_roads"),
                "enable_buildings": config.get("enable_buildings"),
                "enable_weightmaps": config.get("enable_weightmaps"),
                "enable_vegetation": config.get("enable_vegetation", True),
                "enable_water_bodies": config.get("enable_water_bodies", True),
            }
        }

        # Create hash
        cache_str = json.dumps(cache_input, sort_keys=True)
        cache_hash = hashlib.sha256(cache_str.encode()).hexdigest()

        return cache_hash

    def get_cached_result(self, cache_key: str) -> Optional[Path]:
        """
        Get cached result if available and not expired

        Args:
            cache_key: Cache key to look up

        Returns:
            Path to cached result directory or None
        """
        if cache_key not in self.metadata["entries"]:
            return None

        entry = self.metadata["entries"][cache_key]
        cache_path = Path(entry["path"])

        # Check if cache exists
        if not cache_path.exists():
            logger.warning(f"Cache entry exists in metadata but not on disk: {cache_key}")
            del self.metadata["entries"][cache_key]
            self._save_metadata()
            return None

        # Check if cache is expired
        created_time = datetime.fromisoformat(entry["created"])
        if datetime.now() - created_time > self.max_age:
            logger.info(f"Cache entry expired: {cache_key}")
            self.invalidate_cache(cache_key)
            return None

        # Update last access time
        entry["last_accessed"] = datetime.now().isoformat()
        entry["access_count"] = entry.get("access_count", 0) + 1
        self._save_metadata()

        logger.info(f"Cache hit for key: {cache_key}")
        return cache_path

    def store_result(self, cache_key: str, result_path: Path) -> bool:
        """
        Store a generation result in cache

        Args:
            cache_key: Cache key
            result_path: Path to result directory

        Returns:
            True if stored successfully
        """
        try:
            # Calculate result size
            result_size = sum(f.stat().st_size for f in result_path.rglob('*') if f.is_file())

            # Check if we need to make space
            current_size = self.metadata.get("total_size", 0)
            if current_size + result_size > self.max_cache_size:
                self._evict_old_entries(result_size)

            # Create cache entry
            cache_path = self.cache_dir / cache_key

            # Copy result to cache (in production, you might want to use symlinks or move)
            import shutil
            if cache_path.exists():
                shutil.rmtree(cache_path)
            shutil.copytree(result_path, cache_path)

            # Update metadata
            self.metadata["entries"][cache_key] = {
                "path": str(cache_path),
                "size": result_size,
                "created": datetime.now().isoformat(),
                "last_accessed": datetime.now().isoformat(),
                "access_count": 0,
            }
            self.metadata["total_size"] = current_size + result_size
            self._save_metadata()

            logger.info(f"Stored result in cache: {cache_key} ({result_size / 1024 / 1024:.2f} MB)")
            return True

        except Exception as e:
            logger.error(f"Failed to store result in cache: {e}")
            return False

    def restore_result(self, cache_key: str, destination: Path) -> bool:
        """
        Copy a cached result into ``destination``.

        Returns True when the cached files were restored, False when the entry
        is missing, expired, or could not be copied.
        """
        cache_path = self.get_cached_result(cache_key)
        if cache_path is None:
            return False

        import shutil

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(cache_path, destination)
            logger.info("Restored cached result %s to %s", cache_key[:16], destination)
            return True
        except OSError as e:
            logger.error(f"Failed to restore cached result: {e}")
            return False

    def invalidate_cache(self, cache_key: str):
        """Remove a cache entry"""
        if cache_key not in self.metadata["entries"]:
            return

        entry = self.metadata["entries"][cache_key]
        cache_path = Path(entry["path"])

        # Delete cached files
        if cache_path.exists():
            import shutil
            shutil.rmtree(cache_path)

        # Update metadata
        self.metadata["total_size"] = max(0, self.metadata.get("total_size", 0) - entry["size"])
        del self.metadata["entries"][cache_key]
        self._save_metadata()

        logger.info(f"Invalidated cache entry: {cache_key}")

    def clear_cache(self):
        """Clear all cache entries"""
        for cache_key in list(self.metadata["entries"].keys()):
            self.invalidate_cache(cache_key)

        self.metadata = {"entries": {}, "total_size": 0}
        self._save_metadata()

        logger.info("Cleared all cache entries")

    def _evict_old_entries(self, needed_space: int):
        """
        Evict old cache entries to make space using LRU policy

        Args:
            needed_space: Space needed in bytes
        """
        # Sort entries by last access time (LRU)
        entries = sorted(
            self.metadata["entries"].items(),
            key=lambda x: x[1]["last_accessed"]
        )

        freed_space = 0
        for cache_key, entry in entries:
            if freed_space >= needed_space:
                break

            self.invalidate_cache(cache_key)
            freed_space += entry["size"]

        logger.info(f"Evicted cache entries to free {freed_space / 1024 / 1024:.2f} MB")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "total_entries": len(self.metadata["entries"]),
            "total_size_mb": self.metadata.get("total_size", 0) / 1024 / 1024,
            "max_size_mb": self.max_cache_size / 1024 / 1024,
            "max_age_days": self.max_age.days,
            "oldest_entry": min(
                (entry["created"] for entry in self.metadata["entries"].values()),
                default=None
            ),
            "most_accessed": max(
                self.metadata["entries"].items(),
                key=lambda x: x[1].get("access_count", 0),
                default=(None, {})
            )[0],
        }


@lru_cache(maxsize=100)
def get_cache_manager(
    cache_dir: str = "./cache",
    max_cache_size_gb: float = 10.0,
    max_age_days: int = 30,
) -> TerrainCacheManager:
    """
    Get or create the cache manager for a directory.

    The size and age limits are parameters rather than hardcoded defaults so
    CACHE_MAX_SIZE_GB and CACHE_EXPIRY_DAYS from the configuration take effect.
    """
    return TerrainCacheManager(Path(cache_dir), max_cache_size_gb, max_age_days)


def get_configured_cache_manager() -> TerrainCacheManager:
    """
    The cache manager for the configured directory and limits.

    Every caller must go through this: get_cache_manager is memoised on its
    arguments, so calling it with different ones (or with none, defaulting to
    ./cache regardless of CACHE_DIR) yields a second instance whose in-memory
    metadata silently diverges from the first.
    """
    from ..config import settings

    return get_cache_manager(
        str(settings.cache_dir),
        settings.cache_max_size_gb,
        settings.cache_expiry_days,
    )

