"""Contract: version strings must be consistent across all locations.

pyproject.toml is the single source of truth. backend/config.py derives
from it at import time. The remaining files are synced by bump_version.sh.
If any file drifts, this test fails immediately.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _extract_versions() -> dict[str, str]:
    versions: dict[str, str] = {}

    from backend.config import VERSION

    versions["backend/config.py"] = VERSION

    versions["pyproject.toml"] = re.search(
        r'^version = "([^"]+)"',
        _read("pyproject.toml"),
        re.MULTILINE,
    ).group(1)

    versions["package.json"] = json.loads(_read("package.json"))["version"]

    versions["src-tauri/Cargo.toml"] = re.search(
        r'^version = "([^"]+)"',
        _read("src-tauri/Cargo.toml"),
        re.MULTILINE,
    ).group(1)

    versions["src-tauri/tauri.conf.json"] = json.loads(
        _read("src-tauri/tauri.conf.json"),
    )["version"]

    m = re.search(r"argus-gcs-v([\d.]+)", _read("public/sw.js"))
    if m:
        versions["public/sw.js"] = m.group(1)

    return versions


class TestVersionConsistency:
    def test_all_versions_match(self):
        versions = _extract_versions()
        source = versions["pyproject.toml"]
        assert source, "Cannot read version from pyproject.toml"

        sw_ver = versions.pop("public/sw.js", "")
        expected_sw = ".".join(source.split(".")[:2])
        assert sw_ver == expected_sw, f"public/sw.js has v{sw_ver}, expected v{expected_sw} (derived from {source})"

        mismatched = {k: v for k, v in versions.items() if v != source}
        assert not mismatched, (
            f"\nVersion drift detected (source of truth: {source}):\n"
            + "\n".join(f"  {k}: {v}" for k, v in sorted(mismatched.items()))
            + "\n\nRun: bash scripts/bump_version.sh "
            + source
        )
