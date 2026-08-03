#!/usr/bin/env bash
# Optional: read wifi.txt from USB (line1=SSID, line2=password)
set -euo pipefail
MOUNT="/mnt/aerostab_wifi"
for dev in /dev/sda1 /dev/sdb1; do
  [[ -b "$dev" ]] || continue
  mkdir -p "$MOUNT"
  mount -o ro "$dev" "$MOUNT" 2>/dev/null || continue
  if [[ -f "$MOUNT/wifi.txt" ]]; then
    SSID=$(sed -n '1p' "$MOUNT/wifi.txt")
    PASS=$(sed -n '2p' "$MOUNT/wifi.txt")
    nmcli dev wifi connect "$SSID" password "$PASS" 2>/dev/null || \
      wpa_passphrase "$SSID" "$PASS" >> /etc/wpa_supplicant/wpa_supplicant.conf
    echo "WiFi provisioned for $SSID"
  fi
  umount "$MOUNT" || true
done
