"""Tests for scripts/check_categories.py."""

import importlib.util
import json
import logging
from pathlib import Path
from types import ModuleType
from typing import Self
from unittest.mock import AsyncMock, MagicMock

import pytest


def load_script_module() -> ModuleType:
    """Load the check_categories script as a module for testing."""
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "check_categories.py"
    )
    spec = importlib.util.spec_from_file_location(
        "check_categories_module", script_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_check_canonical_repository_names_reports_renamed_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Canonical-name validation should flag renamed repositories clearly."""
    module = load_script_module()
    repository = "owner/repo-old"
    canonical_repository = "owner/repo_new"

    plugins_file = tmp_path / "plugins.json"
    plugins_file.write_text(json.dumps([repository]), encoding="utf-8")

    categories_file = tmp_path / "categories.json"
    categories_file.write_text(
        json.dumps({"Utilities": [repository]}), encoding="utf-8"
    )

    mock_repos = MagicMock()
    mock_repos.get = AsyncMock(
        return_value=MagicMock(data=MagicMock(full_name=canonical_repository))
    )

    class MockGitHubAPI:
        def __init__(self, token: str) -> None:
            self.token = token
            self.repos = mock_repos

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(module, "GitHubAPI", MockGitHubAPI)

    with caplog.at_level(logging.ERROR):
        errors = await module.check_canonical_repository_names(
            str(categories_file), str(plugins_file)
        )

    assert errors == 1
    assert "Repository name mismatch detected!" in caplog.text
    assert "plugins.json and categories.json" in caplog.text
    assert canonical_repository in caplog.text
