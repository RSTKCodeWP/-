#!/usr/bin/env bash
# Boot-time camera overlay selection (StabX firmware.sh pattern).
# Reads /etc/aerostab/camera.txt → applies matching profile to config.txt.
set -euo pipefail

CAMERA_FILE="${AEROSTAB_CAMERA_FILE:-/etc/aerostab/camera.txt}"
PLATFORM="${AEROSTAB_PLATFORM:-zero}"
PROFILES_ROOT="${AEROSTAB_FIRMWARE_DIR:-/etc/aerostab/firmware/$PLATFORM}"
CONFIG_TXT="/boot/firmware/config.txt"
[[ -f "$CONFIG_TXT" ]] || CONFIG_TXT="/boot/config.txt"

[[ -f "$CAMERA_FILE" ]] || exit 0
camera=$(tr '[:upper:]' '[:lower:]' < "$CAMERA_FILE" | tr -d '\r\n ')
[[ -n "$camera" ]] || exit 0

matched=0
for folder in "$PROFILES_ROOT"/*/; do
  [[ -d "$folder" ]] || continue
  folder_name=$(basename "$folder" | tr '[:upper:]' '[:lower:]')
  if [[ "$camera" == "$folder_name"* ]]; then
    SOURCE_CONFIG="$folder/config.txt"
    if [[ -f "$SOURCE_CONFIG" ]]; then
      if ! cmp -s "$SOURCE_CONFIG" "$CONFIG_TXT" 2>/dev/null; then
        echo "AeroStab: applying camera profile $folder_name → $CONFIG_TXT"
        cp "$SOURCE_CONFIG" "$CONFIG_TXT"
        matched=1
      fi
    fi
    break
  fi
done

if [[ "$matched" -eq 1 ]]; then
  echo "AeroStab: camera config updated — reboot required"
  touch /run/aerostab-camera-reboot-needed 2>/dev/null || true
fi
