"""
Zip packaging for generated terrain directories.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def _newest_mtime(directory: Path) -> float:
    """Modification time of the most recently touched file in a tree."""
    return max(
        (child.stat().st_mtime for child in directory.rglob("*") if child.is_file()),
        default=0.0,
    )


def create_map_archive(map_dir: Path, destination_dir: Path, name: str | None = None) -> Path:
    """
    Zip a generated map directory.

    An existing archive is reused when it is at least as new as every file in
    ``map_dir``, so repeated downloads of an unchanged map do not re-compress
    hundreds of megabytes.

    Args:
        map_dir: Directory holding the generated terrain.
        destination_dir: Where the ``.zip`` is written.
        name: Archive base name; defaults to the map directory's name.

    Returns:
        Path to the zip archive.

    Raises:
        FileNotFoundError: If ``map_dir`` does not exist.
    """
    map_dir = Path(map_dir)
    if not map_dir.is_dir():
        raise FileNotFoundError(f"Map directory does not exist: {map_dir}")

    destination_dir = Path(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)

    archive_path = destination_dir / f"{name or map_dir.name}.zip"

    if archive_path.exists() and archive_path.stat().st_mtime >= _newest_mtime(map_dir):
        logger.debug("Reusing up-to-date archive %s", archive_path)
        return archive_path

    logger.info("Creating archive %s from %s", archive_path, map_dir)
    shutil.make_archive(str(archive_path.with_suffix("")), "zip", root_dir=map_dir)
    return archive_path
