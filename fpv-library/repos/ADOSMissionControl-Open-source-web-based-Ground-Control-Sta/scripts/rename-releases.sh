#!/bin/bash
# Rename release artifacts to user-friendly names
# arm64 → apple-silicon, x64 → intel

set -e

RELEASE_DIR="${1:-release}"

if [ ! -d "$RELEASE_DIR" ]; then
  echo "Release directory not found: $RELEASE_DIR"
  exit 1
fi

cd "$RELEASE_DIR"

renamed=0

for f in *-arm64.dmg; do
  [ -f "$f" ] || continue
  new="${f/-arm64/-apple-silicon}"
  mv "$f" "$new"
  echo "Renamed: $f → $new"
  renamed=$((renamed + 1))
done

for f in *-x64.dmg; do
  [ -f "$f" ] || continue
  new="${f/-x64/-intel}"
  mv "$f" "$new"
  echo "Renamed: $f → $new"
  renamed=$((renamed + 1))
done

if [ $renamed -eq 0 ]; then
  echo "No DMG files found to rename"
else
  echo "Renamed $renamed file(s)"
fi
