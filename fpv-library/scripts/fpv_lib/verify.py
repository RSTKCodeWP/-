#!/usr/bin/env python3
"""Verify local git mirrors match upstream exactly."""

from __future__ import annotations

import subprocess
from pathlib import Path

META_FILE = ".fpv-library.json"


class VerifyError(RuntimeError):
    pass


def _git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def verify_mirror(
    dest: Path,
    *,
    expected_sha: str,
    branch: str,
) -> tuple[bool, str]:
    """Return (ok, detail). Checks HEAD, tree diff, and working tree cleanliness."""
    if not dest.is_dir():
        return False, "destination missing"

    head = _git(["rev-parse", "HEAD"], cwd=dest)
    if head.returncode != 0:
        return False, "not a git repository"
    local_sha = head.stdout.strip()
    if local_sha != expected_sha:
        return False, f"HEAD {local_sha[:12]} != upstream {expected_sha[:12]}"

    remote_ref = _git(["rev-parse", f"origin/{branch}"], cwd=dest)
    if remote_ref.returncode == 0 and remote_ref.stdout.strip() != expected_sha:
        return False, f"origin/{branch} {remote_ref.stdout.strip()[:12]} != upstream {expected_sha[:12]}"

    diff = _git(["diff", "--stat", f"origin/{branch}"], cwd=dest)
    if diff.returncode == 0 and diff.stdout.strip():
        return False, f"tree differs from origin/{branch}: {diff.stdout.strip()[:240]}"

    status = _git(["status", "--porcelain"], cwd=dest)
    if status.returncode == 0:
        dirty = [
            line
            for line in status.stdout.splitlines()
            if META_FILE not in line and line.strip()
        ]
        if dirty:
            return False, f"dirty working tree: {dirty[0][:120]}"

    sub = _git(["submodule", "status", "--recursive"], cwd=dest)
    if sub.returncode == 0:
        for line in sub.stdout.splitlines():
            if line.startswith("-") or line.startswith("+"):
                return False, f"submodule not synced: {line[:120]}"

    return True, "verified"
