"""Tests for scripts/check_releases.py."""

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace


def load_script_module() -> ModuleType:
    """Load the check_releases script as a module for testing."""
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_releases.py"
    spec = importlib.util.spec_from_file_location("check_releases_module", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def release(tag: str, *, prerelease: bool, day: int) -> SimpleNamespace:
    """Create a minimal GitHub release object."""
    return SimpleNamespace(
        tag_name=tag,
        prerelease=prerelease,
        created_at=datetime(2026, 1, day, tzinfo=UTC),
    )


def test_select_used_ref_prefers_stable_release() -> None:
    """The latest stable release wins over a newer prerelease."""
    module = load_script_module()

    selected_ref = module.select_used_ref(
        [
            release("v2.0.0-beta.1", prerelease=True, day=3),
            release("v1.1.0", prerelease=False, day=2),
            release("v1.0.0", prerelease=False, day=1),
        ]
    )

    assert selected_ref == "v1.1.0"


def test_select_used_ref_falls_back_to_latest_prerelease() -> None:
    """The newest prerelease is used when no stable release exists."""
    module = load_script_module()

    selected_ref = module.select_used_ref(
        [
            release("v1.0.0-beta.1", prerelease=True, day=1),
            release("v1.0.0-beta.2", prerelease=True, day=2),
        ]
    )

    assert selected_ref == "v1.0.0-beta.2"
