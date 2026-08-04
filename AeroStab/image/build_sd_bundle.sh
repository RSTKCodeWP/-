#!/usr/bin/env bash
# Build SD-card bundle for Pi Zero 2W first-boot auto-install.
# Output: dist/aerostab-sd-bundle.tar.gz
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/dist"
STAGE="$OUT/sd-bundle-stage"
BUNDLE_NAME="aerostab-sd-bundle"

rm -rf "$STAGE"
mkdir -p "$STAGE/aerostab" "$OUT"

echo "=== Staging AeroStab for SD bundle ==="
if command -v rsync >/dev/null 2>&1; then
  rsync -a \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '.pytest_cache' \
    --exclude 'logs' \
    --exclude 'dist' \
    --exclude '.git' \
    --exclude 'image/ZERO-16G-*.rar' \
    --exclude 'image/extracted' \
    --exclude 'image/stabx-drive' \
    --exclude 'flash-sd/dist' \
    "$ROOT/" "$STAGE/aerostab/project/"
else
  mkdir -p "$STAGE/aerostab/project"
  tar -C "$ROOT" \
    --exclude='.venv' --exclude='__pycache__' --exclude='.pytest_cache' \
    --exclude='logs' --exclude='dist' --exclude='.git' \
    --exclude='image/ZERO-16G-*.rar' --exclude='image/extracted' \
    --exclude='image/stabx-drive' --exclude='flash-sd/dist' \
    -cf - . | tar -C "$STAGE/aerostab/project" -xf -
fi

cp "$ROOT/image/firstboot/install-on-first-boot.sh" "$STAGE/aerostab/install-on-first-boot.sh"
cp "$ROOT/image/firstboot/aerostab-firstboot.service" "$STAGE/aerostab/aerostab-firstboot.service"
cp "$ROOT/image/firstboot/README-FIRSTBOOT.txt" "$STAGE/aerostab/README-FIRSTBOOT.txt"
cp "$ROOT/flash-sd/README.md" "$STAGE/aerostab/FLASH-INSTRUCTIONS.md"
cp "$ROOT/flash-sd/STABX-CHECKLIST.md" "$STAGE/aerostab/STABX-CHECKLIST.md"
cp "$ROOT/deploy/ardupilot_aerostab.param" "$STAGE/aerostab/ardupilot_aerostab.param"
cp "$ROOT/FLIGHT.md" "$STAGE/aerostab/FLIGHT.md"

# Marker: Pi OS firstrun hook reads this on boot partition
cat > "$STAGE/aerostab/ENABLE_FIRSTBOOT" <<'EOF'
AeroStab first-boot installer enabled.
On first Linux boot, copy aerostab-firstboot.service and run install-on-first-boot.sh.
EOF

tar -czf "$OUT/${BUNDLE_NAME}.tar.gz" -C "$STAGE" aerostab

echo ""
echo "=== Bundle ready ==="
echo "  $OUT/${BUNDLE_NAME}.tar.gz"
echo ""
echo "Flash Pi OS Lite 64-bit, then:"
echo "  bash flash-sd/prepare-sd.sh /media/\$USER/bootfs --auto-install"
echo "  # or: sudo tar -xzf ${BUNDLE_NAME}.tar.gz -C /media/\$USER/bootfs/"
echo "See flash-sd/README.md for full instructions."
echo ""
ls -lh "$OUT/${BUNDLE_NAME}.tar.gz"
