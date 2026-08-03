#!/usr/bin/env bash
# Підготувати вже записану SD (boot-розділ змонтований) — розпакувати bundle + опційно cloud-init.
# Usage:
#   sudo bash flash-sd/prepare-sd.sh /media/$USER/bootfs
#   sudo bash flash-sd/prepare-sd.sh /media/$USER/bootfs --auto-install
set -euo pipefail

BOOT="${1:-}"
AUTO="${2:-}"

if [[ -z "$BOOT" || ! -d "$BOOT" ]]; then
  echo "Usage: sudo $0 /path/to/bootfs [--auto-install]"
  echo "  --auto-install  копіює user-data для автоматичного першого встановлення (потрібен Wi-Fi в Imager)"
  exit 1
fi

FLASH="$(cd "$(dirname "$0")" && pwd)"
DIST="$FLASH/dist"
BUNDLE="$DIST/aerostab-sd-bundle.tar.gz"

[[ -f "$BUNDLE" ]] || { echo "Спочатку: bash flash-sd/build.sh"; exit 1; }

echo "=== Розпакування bundle на $BOOT ==="
tar -xzf "$BUNDLE" -C "$BOOT/"

if [[ "$AUTO" == "--auto-install" ]]; then
  if [[ -f "$DIST/user-data.example" ]]; then
    cp "$DIST/user-data.example" "$BOOT/user-data"
    echo "Скопійовано user-data (cloud-init auto-install)"
  fi
fi

echo ""
echo "На boot-розділі:"
ls -la "$BOOT/aerostab/" 2>/dev/null || ls -la "$BOOT/firmware/aerostab/" 2>/dev/null || true
echo ""
echo "Вийміть SD, вставте в Pi Zero 2W, увімкніть."
echo "Якщо без --auto-install: ssh pi@aerostab.local"
echo "  sudo bash /boot/firmware/aerostab/install-on-first-boot.sh"
