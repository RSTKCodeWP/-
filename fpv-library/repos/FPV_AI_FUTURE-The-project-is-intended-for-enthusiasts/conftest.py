"""pytest configuration: ensure fpv_ai's bare imports resolve correctly.

fpv/fpv_ai/ uses bare ``fpv_ai.*`` imports (without the ``fpv.`` prefix).
Adding ``fpv/`` to sys.path makes these resolvable.
"""
import sys
import os

# Ensure fpv/ is on sys.path so that ``import fpv_ai`` works inside fpv_ai/
_fpv_dir = os.path.join(os.path.dirname(__file__), "fpv")
if _fpv_dir not in sys.path:
    sys.path.insert(0, _fpv_dir)
