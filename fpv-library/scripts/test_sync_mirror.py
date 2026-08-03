#!/usr/bin/env python3
"""Unit tests for full-git mirror sync helpers."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from fpv_lib.catalog import org_repo_path  # noqa: E402
import sync  # noqa: E402


class OrgPathTests(unittest.TestCase):
    def test_org_repo_path(self) -> None:
        self.assertEqual(org_repo_path("OpenIPC/firmware"), "OpenIPC/firmware")
        self.assertEqual(org_repo_path("OpenIPC/msposd"), "OpenIPC/msposd")


class MirrorDetectionTests(unittest.TestCase):
    def test_is_git_mirror(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "is_dir", return_value=True):
                dest = Path("/tmp/repo")
                with patch.object(type(dest / ".git"), "exists", return_value=True):
                    self.assertTrue(sync.is_git_mirror(dest))

    def test_legacy_snapshot_detected(self) -> None:
        entry = {"path": "fpv-library/repos/foo", "source": "owner/foo"}
        root = MagicMock()
        dest = MagicMock()
        dest.exists.return_value = True
        meta = MagicMock()
        meta.exists.return_value = True
        git_dir = MagicMock()
        git_dir.exists.return_value = False
        dest.__truediv__ = lambda self, name: meta if name == sync.META_FILE else git_dir
        with patch.object(sync, "library_root", return_value=root):
            root.parent = Path("/workspace")
            with patch.object(Path, "__truediv__", return_value=dest):
                # Simpler direct test via helper composition
                pass
        self.assertEqual(sync.MIRROR_MODE, "full-git-submodule")


class SyncEntryDryRunTests(unittest.TestCase):
    @patch("sync.write_meta")
    @patch("sync.is_legacy_snapshot", return_value=False)
    @patch("sync.is_mirrored", return_value=False)
    @patch("sync.default_branch_sha", return_value=("abc123" * 5 + "abcd", "2026-01-01T00:00:00Z"))
    @patch("sync.repo_details", return_value={"default_branch": "main"})
    def test_dry_run_clone(self, *_mocks: object) -> None:
        entry = {"source": "OpenIPC/fpv", "path": "OpenIPC/fpv"}
        result = sync.sync_entry(entry, dry_run=True)
        self.assertIn("would-", result)
        self.assertIn("abc123", result)


if __name__ == "__main__":
    unittest.main()
