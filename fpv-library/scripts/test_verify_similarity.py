#!/usr/bin/env python3
"""Unit tests for mirror verification and similarity queries."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from fpv_lib.similarity import owners_from_catalog, similarity_queries  # noqa: E402
from fpv_lib.verify import verify_mirror  # noqa: E402


class SimilarityTests(unittest.TestCase):
    def test_owners_from_catalog(self) -> None:
        catalog = {
            "repos": [
                {"source": "OpenIPC/fpv", "verdict": "keep"},
                {"source": "OpenHD/OpenHD", "verdict": "watch"},
                {"source": "noise/foo", "verdict": "skip"},
            ]
        }
        self.assertEqual(owners_from_catalog(catalog), ["OpenHD", "OpenIPC"])

    def test_similarity_queries_from_topics(self) -> None:
        catalog = {
            "repos": [
                {"verdict": "keep", "topics": ["fpv", "mavlink"], "source": "a/x"},
                {"verdict": "keep", "topics": ["fpv", "osd"], "source": "b/y"},
                {"verdict": "keep", "topics": ["mavlink"], "source": "c/z"},
            ]
        }
        queries = similarity_queries(catalog, max_queries=10)
        self.assertTrue(any("topic:fpv" in q for q in queries))


class VerifyTests(unittest.TestCase):
    @patch("fpv_lib.verify._git")
    def test_verify_ok(self, mock_git: MagicMock) -> None:
        sha = "a" * 40
        dest = MagicMock()
        dest.is_dir.return_value = True

        def side_effect(args, *, cwd):
            result = MagicMock()
            result.returncode = 0
            if args[:2] == ["rev-parse", "HEAD"]:
                result.stdout = sha
            elif args[:2] == ["rev-parse", "origin/main"]:
                result.stdout = sha
            elif args[:2] == ["diff", "--stat"]:
                result.stdout = ""
            elif args[:2] == ["status", "--porcelain"]:
                result.stdout = ""
            elif args[:2] == ["submodule", "status"]:
                result.stdout = ""
            else:
                result.stdout = ""
            return result

        mock_git.side_effect = side_effect
        ok, detail = verify_mirror(dest, expected_sha=sha, branch="main")
        self.assertTrue(ok)
        self.assertEqual(detail, "verified")

    @patch("fpv_lib.verify._git")
    def test_verify_head_mismatch(self, mock_git: MagicMock) -> None:
        dest = MagicMock()
        dest.is_dir.return_value = True
        result = MagicMock()
        result.returncode = 0
        result.stdout = "b" * 40
        mock_git.return_value = result
        ok, detail = verify_mirror(dest, expected_sha="a" * 40, branch="main")
        self.assertFalse(ok)
        self.assertIn("!=", detail)


if __name__ == "__main__":
    unittest.main()
