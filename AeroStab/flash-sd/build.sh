#!/usr/bin/env bash
# Зібрати все для заливки SD → flash-sd/dist/
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FLASH="$(cd "$(dirname "$0")" && pwd)"
DIST="$FLASH/dist"

echo "=== AeroStab flash-sd build ==="
bash "$ROOT/image/build_sd_bundle.sh"

mkdir -p "$DIST"
cp -f "$ROOT/dist/aerostab-sd-bundle.tar.gz" "$DIST/"
cp -f "$ROOT/deploy/ardupilot_aerostab.param" "$DIST/"
cp -f "$ROOT/deploy/ardupilot_rtl_failsafe.param" "$DIST/"
cp -f "$ROOT/FLIGHT.md" "$DIST/"
cp -f "$FLASH/cloud-init-user-data.example" "$DIST/user-data.example"
cp -f "$FLASH/wifi.txt.example" "$DIST/wifi.txt.example"

(
  cd "$DIST"
  sha256sum aerostab-sd-bundle.tar.gz > CHECKSUMS.sha256
)

echo ""
echo "Готово: $DIST/"
ls -lh "$DIST/"
