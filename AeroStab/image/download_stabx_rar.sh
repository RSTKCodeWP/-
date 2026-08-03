#!/usr/bin/env bash
# Download StabX SD image into repo path (Git LFS target).
# Usage: bash image/download_stabx_rar.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/image/ZERO-16G-2025-11-01-JR.rar"
# Working mirror (2025-11): 1pH3lMNsUBvFGEy4zrGUoNi9G_U657jYb
# Legacy (quota exceeded): 1rfe0nEfN9Ea5nj6zEI2QjtayYVCbb8Ta
FILEID="${STABX_DRIVE_FILE_ID:-1pH3lMNsUBvFGEy4zrGUoNi9G_U657jYb}"
URL="https://drive.google.com/file/d/${FILEID}/view?usp=drivesdk"

mkdir -p "$ROOT/image"

if [[ -f "$OUT" ]]; then
  sz=$(stat -c%s "$OUT" 2>/dev/null || stat -f%z "$OUT")
  if [[ "$sz" -gt 100000000 ]]; then
    echo "Already have $(du -h "$OUT" | cut -f1) at $OUT"
    exit 0
  fi
  echo "Removing invalid stub ($(du -h "$OUT" | cut -f1))"
  rm -f "$OUT"
fi

echo "Downloading StabX image (~1.7 GB)..."
echo "URL: $URL"

if python3 -m gdown "$URL" -O "$OUT" 2>/dev/null; then
  :
else
  # curl fallback with confirm token
  curl -sL -c /tmp/gdcookies.txt "https://drive.google.com/uc?export=download&id=${FILEID}" -o /tmp/gd.html
  UUID=$(grep -oP 'name="uuid" value="\K[^"]+' /tmp/gd.html || true)
  if [[ -n "$UUID" ]]; then
    curl -L -b /tmp/gdcookies.txt \
      "https://drive.usercontent.google.com/download?id=${FILEID}&export=download&confirm=t&uuid=${UUID}" \
      -o "$OUT"
  else
    echo "Download failed (Google Drive quota?)."
    echo "Manual: save file to $OUT then run:"
    echo "  bash scripts/analyze_stabx_image.sh $OUT"
    exit 1
  fi
fi

file "$OUT"
sz=$(stat -c%s "$OUT" 2>/dev/null || stat -f%z "$OUT")
if [[ "$sz" -lt 100000000 ]]; then
  echo "ERROR: got HTML stub, not RAR. Quota exceeded."
  head -c 200 "$OUT"; echo; rm -f "$OUT"; exit 1
fi
echo "OK: $OUT ($(du -h "$OUT" | cut -f1))"
