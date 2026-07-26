#!/bin/bash
# Atomic release: bump → test → commit → tag → push.
# If tests fail, version bump is rolled back — no orphan commits or tags.
#
# Usage: bash scripts/make-release.sh 3.7.0
set -e

NEW_VER="$1"
if [ -z "$NEW_VER" ]; then
    echo "Usage: bash scripts/make-release.sh <version>"
    echo "Example: bash scripts/make-release.sh 3.7.0"
    exit 1
fi

cd "$(dirname "$0")/.."

# Preflight checks
if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: working tree not clean. Commit or stash first."
    exit 1
fi

BRANCH=$(git branch --show-current)
if [ "$BRANCH" != "main" ]; then
    echo "ERROR: releases must be from main (currently on $BRANCH)"
    exit 1
fi

if git rev-parse "v$NEW_VER" >/dev/null 2>&1; then
    echo "ERROR: tag v$NEW_VER already exists"
    exit 1
fi

# Bump version across all files
bash scripts/bump_version.sh "$NEW_VER"

# Run tests BEFORE committing — rollback on failure
echo ""
echo "[release] Running test gate before commit..."
FAIL=0
npx vitest run --bail 1 --reporter=dot || FAIL=1
if [ "$FAIL" -eq 0 ]; then
    python -m pytest tests/test_unit_*.py tests/test_contract_*.py -q --tb=line -x || FAIL=1
fi

if [ "$FAIL" -ne 0 ]; then
    echo ""
    echo "Tests failed — rolling back version bump."
    git checkout -- .
    exit 1
fi

echo ""
echo "[release] Tests passed. Committing..."

# Commit + tag
if [ -n "$(git status --porcelain)" ]; then
    git add pyproject.toml package.json public/sw.js \
           src-tauri/Cargo.toml src-tauri/tauri.conf.json
    git commit -m "release: v$NEW_VER"
fi
git tag -a "v$NEW_VER" -m "Release v$NEW_VER"

# Push commit + tag
git push origin main --tags

echo ""
echo "Released v$NEW_VER"
echo "GitHub Actions will build artifacts and create the Release."
echo "Watch: https://github.com/L-X-Yao/argus/actions"
