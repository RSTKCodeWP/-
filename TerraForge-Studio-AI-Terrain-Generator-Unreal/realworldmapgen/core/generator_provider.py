"""
Shared access to the process-wide :class:`TerraForgeGenerator`.

Route modules used to each construct their own generator, which meant tasks
started through one router were invisible to another (``/api/batch`` jobs never
showed up under ``/api/tasks``). Everything now goes through this single
lazily-created instance.
"""

from __future__ import annotations

import threading
from typing import Optional

from .terrain_generator import TerraForgeGenerator

_generator: Optional[TerraForgeGenerator] = None
_lock = threading.Lock()


def get_generator() -> TerraForgeGenerator:
    """Return the shared generator, constructing it on first use."""
    global _generator
    if _generator is None:
        with _lock:
            if _generator is None:
                _generator = TerraForgeGenerator()
    return _generator


def reset_generator() -> None:
    """Drop the cached instance so the next call rebuilds it (used by tests)."""
    global _generator
    with _lock:
        _generator = None
