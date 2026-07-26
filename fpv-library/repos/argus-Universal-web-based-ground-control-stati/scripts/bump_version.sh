#!/bin/bash
# Bump version across all files that contain the version string.
# Usage: bash scripts/bump_version.sh 3.5.0
set -e

NEW_VER="$1"
if [ -z "$NEW_VER" ]; then
    echo "Usage: bash scripts/bump_version.sh <new_version>"
    echo "Example: bash scripts/bump_version.sh 3.5.0"
    exit 1
fi

if ! echo "$NEW_VER" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    echo "ERROR: version must be semver (e.g. 3.5.0)"
    exit 1
fi

cd "$(dirname "$0")/.."

# Read current version from pyproject.toml (single source of truth)
OLD_VER=$(python3 -c "
import re
text = open('pyproject.toml').read()
m = re.search(r'^version = \"([^\"]+)\"', text, re.MULTILINE)
print(m.group(1) if m else '')
")

if [ -z "$OLD_VER" ]; then
    echo "ERROR: cannot read current version from pyproject.toml"
    exit 1
fi

if [ "$OLD_VER" = "$NEW_VER" ]; then
    echo "Already at version $NEW_VER"
    exit 0
fi

echo "Bumping $OLD_VER → $NEW_VER"

# 1. pyproject.toml (single source of truth — config.py derives from it)
sed -i "s/^version = \"$OLD_VER\"/version = \"$NEW_VER\"/" pyproject.toml

# 2. package.json
sed -i "s/\"version\": \"$OLD_VER\"/\"version\": \"$NEW_VER\"/" package.json

# 3. public/sw.js cache name
OLD_CACHE=$(echo "$OLD_VER" | sed 's/\.[0-9]*$//')
NEW_CACHE=$(echo "$NEW_VER" | sed 's/\.[0-9]*$//')
if [ "$OLD_CACHE" != "$NEW_CACHE" ]; then
    sed -i "s/argus-gcs-v$OLD_CACHE/argus-gcs-v$NEW_CACHE/" public/sw.js
    echo "  sw.js cache: v$OLD_CACHE → v$NEW_CACHE"
fi

# 4. src-tauri/Cargo.toml
sed -i "s/^version = \"$OLD_VER\"/version = \"$NEW_VER\"/" src-tauri/Cargo.toml

# 5. src-tauri/tauri.conf.json
sed -i "s/\"version\": \"$OLD_VER\"/\"version\": \"$NEW_VER\"/" src-tauri/tauri.conf.json

echo "Done. Files updated:"
echo "  pyproject.toml (source of truth)"
echo "  package.json"
echo "  src-tauri/Cargo.toml"
echo "  src-tauri/tauri.conf.json"
grep -n "$NEW_VER" pyproject.toml package.json src-tauri/Cargo.toml | sed 's/^/  /'
