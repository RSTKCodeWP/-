"""Tests for the RotorHazard Community Plugins code."""

import json
from pathlib import Path


def load_fixture(filename: str) -> str:
    """Load a fixture."""
    path = Path(__file__).parent / "fixtures" / filename
    return json.loads(path.read_text())
