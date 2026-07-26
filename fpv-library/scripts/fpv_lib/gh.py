#!/usr/bin/env python3
"""GitHub API helpers via gh CLI."""

from __future__ import annotations

import json
import subprocess
from typing import Any


class GhError(RuntimeError):
    pass


def gh_api(path: str, *, paginate: bool = False) -> Any:
    cmd = ["gh", "api", path]
    if paginate:
        cmd.insert(2, "--paginate")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise GhError(result.stderr.strip() or result.stdout.strip())
    if paginate:
        items: list[Any] = []
        for line in result.stdout.splitlines():
            if line.strip():
                items.extend(json.loads(line))
        return items
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)


def search_repos(query: str, *, page: int = 1, per_page: int = 30) -> list[dict[str, Any]]:
    q = query.replace(" ", "+")
    data = gh_api(
        f"/search/repositories?q={q}&sort=updated&order=desc&per_page={per_page}&page={page}"
    )
    return data.get("items", [])


def list_owner_repos(owner: str, *, per_page: int = 100) -> list[dict[str, Any]]:
    return gh_api(f"/users/{owner}/repos?per_page={per_page}&sort=updated", paginate=True)


def repo_details(source: str) -> dict[str, Any]:
    return gh_api(f"/repos/{source}")


def default_branch_sha(source: str) -> tuple[str, str]:
    repo = repo_details(source)
    branch = repo.get("default_branch", "main")
    ref = gh_api(f"/repos/{source}/git/ref/heads/{branch}")
    sha = ref["object"]["sha"]
    return sha, repo.get("pushed_at") or repo.get("updated_at") or ""
