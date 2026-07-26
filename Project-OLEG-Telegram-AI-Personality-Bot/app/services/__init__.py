"""Services package - Business logic layer.

Note: wallet_service is imported lazily to avoid circular imports.
Use: from app.services import wallet_service
"""

import importlib
import sys

# Lazy imports to avoid circular dependencies
__all__ = ["wallet_service"]

_lazy_modules = {
    "wallet_service": "app.services.wallet_service",
}


def __getattr__(name):
    """Lazy import for wallet_service."""
    if name in _lazy_modules:
        module_path = _lazy_modules[name]
        # Check if already imported to avoid recursion
        if module_path in sys.modules:
            return sys.modules[module_path]
        # Import the module directly
        module = importlib.import_module(module_path)
        # Cache it in this package's namespace
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
