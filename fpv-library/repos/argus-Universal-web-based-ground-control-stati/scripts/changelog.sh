#!/bin/bash
# Generate release notes from git log between two tags.
#
# Usage:
#   bash scripts/changelog.sh              # latest tag..HEAD
#   bash scripts/changelog.sh v3.4.0       # v3.4.0..HEAD
#   bash scripts/changelog.sh v3.4.0 v3.5.0  # v3.4.0..v3.5.0
set -e

cd "$(dirname "$0")/.."

if [ -n "$2" ]; then
    RANGE="$1..$2"
elif [ -n "$1" ]; then
    RANGE="$1..HEAD"
else
    PREV=$(git tag --sort=-v:refname | head -1)
    if [ -z "$PREV" ]; then
        RANGE="HEAD"
    else
        RANGE="${PREV}..HEAD"
    fi
fi

echo "## Changes (${RANGE})"
echo ""

FEATS=$(git log "$RANGE" --pretty=format:"%s" | grep -E "^feat:" | sed 's/^feat: /- /' || true)
if [ -n "$FEATS" ]; then
    echo "### New Features"
    echo "$FEATS"
    echo ""
fi

FIXES=$(git log "$RANGE" --pretty=format:"%s" | grep -E "^fix:" | sed 's/^fix: /- /' || true)
if [ -n "$FIXES" ]; then
    echo "### Bug Fixes"
    echo "$FIXES"
    echo ""
fi

REFACTORS=$(git log "$RANGE" --pretty=format:"%s" | grep -E "^refactor:" | sed 's/^refactor: /- /' || true)
if [ -n "$REFACTORS" ]; then
    echo "### Refactors"
    echo "$REFACTORS"
    echo ""
fi

OTHER=$(git log "$RANGE" --pretty=format:"%s" | grep -vE "^(feat|fix|refactor|release|Merge):" | sed 's/^/- /' || true)
if [ -n "$OTHER" ]; then
    echo "### Other"
    echo "$OTHER"
    echo ""
fi
