#!/usr/bin/env python3
"""Sync Caddx Ground Configuration releases from GitHub and optionally download assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

LIB_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = LIB_ROOT / "manifests/Caddx_Ground_Configuration_Release.json"
DEFAULT_STATUS = LIB_ROOT / "manifests/Caddx_Ground_Configuration_Release.status.json"
DEFAULT_OUT = LIB_ROOT / "ground-config"
API_URL = "https://api.github.com/repos/CaddxFPV-Tech/Caddx_Ground_Configuration_Release/releases"
SOURCE = "CaddxFPV-Tech/Caddx_Ground_Configuration_Release"
SKIP_ASSETS = frozenset()


def asset_id(name: str) -> str:
    lower = name.lower()
    if lower.endswith("-setup.exe"):
        return "setup"
    if lower.endswith("-portable.zip"):
        return "portable"
    if lower.endswith("-full.nupkg"):
        return "full"
    if lower.endswith("-delta.nupkg"):
        return "delta"
    if lower == "releases.win.json":
        return "releases_win_json"
    if lower == "releases":
        return "releases"
    stem = re.sub(r"[^a-z0-9]+", "_", Path(name).stem.lower()).strip("_")
    return stem or "asset"


def asset_kind(asset_id_value: str, name: str) -> str:
    mapping = {
        "setup": "installer",
        "portable": "portable",
        "full": "nupkg",
        "delta": "nupkg-delta",
        "releases_win_json": "metadata",
        "releases": "metadata",
    }
    return mapping.get(asset_id_value, "other")


def parse_digest(digest: str | None) -> str:
    if not digest:
        return ""
    return digest.removeprefix("sha256:").lower()


def fetch_releases() -> list[dict]:
    req = urllib.request.Request(
        API_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "fpv-library-sync"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build_manifest_payload(releases_api: list[dict]) -> dict:
    releases: list[dict] = []
    for rel in releases_api:
        if rel.get("draft") or rel.get("prerelease"):
            continue
        tag = rel["tag_name"]
        assets = []
        for item in rel.get("assets", []):
            name = item["name"]
            if name in SKIP_ASSETS:
                continue
            aid = asset_id(name)
            assets.append(
                {
                    "id": aid,
                    "name": name,
                    "kind": asset_kind(aid, name),
                    "platform": "win",
                    "url": item["browser_download_url"],
                    "size": item["size"],
                    "sha256": parse_digest(item.get("digest")),
                }
            )
        releases.append(
            {
                "tag": tag,
                "version": tag.lstrip("vV"),
                "releaseDate": (rel.get("published_at") or "")[:10],
                "changelogUrl": rel.get("html_url", ""),
                "notes": (rel.get("body") or "").strip(),
                "assets": assets,
            }
        )
    return {
        "schemaVersion": 1,
        "source": SOURCE,
        "releases": releases,
    }


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def latest_tag(manifest: dict) -> str:
    releases = manifest.get("releases") or []
    return releases[0]["tag"] if releases else ""


def manifest_changed(old: dict | None, new: dict) -> bool:
    if old is None:
        return True
    return json.dumps(old, sort_keys=True) != json.dumps(new, sort_keys=True)


def write_status(path: Path, manifest: dict, changed: bool, downloaded: bool) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    old = load_json(path) or {}
    status = {
        "source": SOURCE,
        "lastChecked": now,
        "latestTag": latest_tag(manifest),
        "releaseCount": len(manifest.get("releases", [])),
        "releasesUrl": "https://github.com/CaddxFPV-Tech/Caddx_Ground_Configuration_Release/releases",
        "manifestPath": str(DEFAULT_MANIFEST.relative_to(LIB_ROOT.parent)),
        "downloadDir": str(DEFAULT_OUT.relative_to(LIB_ROOT.parent)),
        "manifestUpdated": changed,
        "downloaded": downloaded,
        "history": old.get("history", []),
    }
    if changed:
        entry = {
            "at": now,
            "latestTag": status["latestTag"],
            "releaseCount": status["releaseCount"],
        }
        history = [entry] + [h for h in status["history"] if h.get("latestTag") != entry["latestTag"]]
        status["history"] = history[:20]
    else:
        status["history"] = old.get("history", [])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def download_assets(manifest: dict, out_dir: Path, tags: list[str] | None) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    errors = 0
    selected = manifest["releases"]
    if tags:
        selected = [r for r in selected if r["tag"] in tags]
    for release in selected:
        release_dir = out_dir / release["tag"]
        release_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n== {release['tag']} ({release['releaseDate']}) ==")
        for asset in release["assets"]:
            dest = release_dir / asset["name"]
            if dest.exists() and dest.stat().st_size == asset["size"]:
                sha = hashlib.sha256(dest.read_bytes()).hexdigest()
                if not asset.get("sha256") or sha == asset["sha256"]:
                    print(f"skip (ok) {dest.name}")
                    continue
            print(f"download {asset['name']} ...")
            try:
                urllib.request.urlretrieve(asset["url"], dest)
            except urllib.error.URLError as exc:
                print(f"ERROR {asset['name']}: {exc}", file=sys.stderr)
                errors += 1
                continue
            sha = hashlib.sha256(dest.read_bytes()).hexdigest()
            expected = asset.get("sha256", "")
            if expected and sha != expected:
                print(f"ERROR SHA256 mismatch for {asset['name']}", file=sys.stderr)
                errors += 1
                continue
            print(f"OK {dest} ({dest.stat().st_size} bytes)")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync and download Caddx Ground Configuration releases")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check-only", action="store_true", help="refresh manifest/status only")
    parser.add_argument("--download", action="store_true", help="download assets after sync")
    parser.add_argument(
        "--tag",
        action="append",
        dest="tags",
        help="limit download to tag (repeatable); default all releases when downloading",
    )
    args = parser.parse_args()

    print(f"Fetching {API_URL} ...")
    try:
        api_releases = fetch_releases()
    except urllib.error.URLError as exc:
        print(f"GitHub API error: {exc}", file=sys.stderr)
        return 1

    new_manifest = build_manifest_payload(api_releases)
    old_manifest = load_json(args.manifest)
    changed = manifest_changed(old_manifest, new_manifest)

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(new_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if changed:
        print(f"manifest updated -> {args.manifest}")
        print(f"latest: {latest_tag(new_manifest)} ({len(new_manifest['releases'])} releases)")
    else:
        print(f"manifest unchanged (latest {latest_tag(new_manifest)})")

    downloaded = False
    errors = 0
    if args.download and not args.check_only:
        errors = download_assets(new_manifest, args.out, args.tags)
        downloaded = True
        if errors:
            print(f"\n{errors} download error(s)", file=sys.stderr)

    write_status(args.status, new_manifest, changed, downloaded)
    print(f"status -> {args.status}")

    if changed and args.check_only:
        print("NEW RELEASE DATA — commit manifest/status update")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
