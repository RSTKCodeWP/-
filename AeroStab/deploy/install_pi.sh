#!/usr/bin/env bash
# AeroStab production installer — Raspberry Pi OS Bookworm 64-bit
# flash → install → reboot → http://aerostab.local:8080 → FLIGHT OK → PosHold arm
set -euo pipefail

INSTALL_DIR="/opt/aerostab"
CONFIG_DIR="/etc/aerostab"
LOG_DIR="/var/log/aerostab"
USER_NAME="${SUDO_USER:-pi}"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== AeroStab installer ==="
[[ "$(id -u)" -eq 0 ]] || { echo "sudo $0"; exit 1; }

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  python3 python3-pip python3-venv python3-dev \
  libcap-dev libatlas-base-dev \
  libcamera-apps libcamera-dev \
  avahi-daemon rsync

usermod -aG dialout,video,spi,i2c "$USER_NAME" 2>/dev/null || true
hostnamectl set-hostname aerostab 2>/dev/null || true
grep -q 'aerostab' /etc/hosts 2>/dev/null || echo '127.0.1.1 aerostab' >> /etc/hosts

mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$LOG_DIR"
rsync -a --exclude '.venv' --exclude '__pycache__' --exclude 'logs' --exclude '.pytest_cache' \
  "$SCRIPT_DIR/" "$INSTALL_DIR/"

python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip wheel
"$INSTALL_DIR/.venv/bin/pip" install -e "$INSTALL_DIR[pi]"

[[ -f "$CONFIG_DIR/config.yaml" ]] || cp "$INSTALL_DIR/config/default.yaml" "$CONFIG_DIR/config.yaml"

python3 - <<'PY'
import json
from pathlib import Path
p = Path("/etc/aerostab/mask.json")
if not p.exists() or not p.read_text().strip():
    cols, rows = 16, 12
    p.write_text(json.dumps({"cols": cols, "rows": rows, "cells": [False] * (cols * rows)}))
PY

# OV5647 + UART for Matek FC
CONFIG_TXT="/boot/firmware/config.txt"
[[ -f "$CONFIG_TXT" ]] || CONFIG_TXT="/boot/config.txt"
mkdir -p "$CONFIG_DIR/firmware/zero/ov5647"
install -m 644 "$INSTALL_DIR/deploy/settings/firmware/zero/ov5647/config.txt" \
  "$CONFIG_DIR/firmware/zero/ov5647/config.txt"
[[ -f "$CONFIG_DIR/camera.txt" ]] || echo 'ov5647' > "$CONFIG_DIR/camera.txt"
install -m 755 "$INSTALL_DIR/deploy/firmware.sh" /usr/local/bin/aerostab-firmware
/usr/local/bin/aerostab-firmware || true

if [[ -f /boot/firmware/cmdline.txt ]]; then
  sed -i 's/console=serial0,[0-9]* //g' /boot/firmware/cmdline.txt || true
fi
for unit in serial-getty@ttyAMA0.service getty@ttyAMA0.service; do
  systemctl disable "$unit" 2>/dev/null || true
  systemctl stop "$unit" 2>/dev/null || true
done

chown -R "$USER_NAME:$USER_NAME" "$INSTALL_DIR" "$CONFIG_DIR" "$LOG_DIR"
install -m 644 "$INSTALL_DIR/FLIGHT.md" "$CONFIG_DIR/FLIGHT.md" 2>/dev/null || true
sed "s/^User=pi/User=$USER_NAME/; s/^Group=pi/Group=$USER_NAME/" \
  "$INSTALL_DIR/deploy/aerostab.service" > /etc/systemd/system/aerostab.service
install -m 755 "$INSTALL_DIR/deploy/wifi_provision.sh" /usr/local/bin/aerostab-wifi

mkdir -p /etc/avahi/services
cat > /etc/avahi/services/aerostab.service <<'EOF'
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name replace-wildcards="yes">AeroStab</name>
  <service>
    <type>_http._tcp</type>
    <port>8080</port>
  </service>
</service-group>
EOF
systemctl restart avahi-daemon || true

systemctl daemon-reload
systemctl enable aerostab.service

# WiFi provisioning (StabX-style wifi.txt + USB)
install -m 644 "$INSTALL_DIR/deploy/aerostab-wifi.service" /etc/systemd/system/
install -m 644 "$INSTALL_DIR/deploy/aerostab-usb-wifi.service" /etc/systemd/system/
systemctl enable aerostab-wifi.service 2>/dev/null || true
systemctl enable aerostab-usb-wifi.service 2>/dev/null || true

# Optional /data partition (StabX-style flight records on p3)
if [[ -b /dev/mmcblk0p3 ]] && blkid /dev/mmcblk0p3 2>/dev/null | grep -q 'TYPE="ext4"'; then
  mkdir -p /data/records
  if ! grep -q '/data ' /etc/fstab 2>/dev/null; then
    echo '/dev/mmcblk0p3 /data ext4 defaults,noatime 0 2' >> /etc/fstab
  fi
  mount /data 2>/dev/null || true
  mkdir -p "$LOG_DIR/records"
  echo "Flight records: /data/records (ext4 p3 mounted)"
fi

echo ""
echo "=== AeroStab installed ==="
echo "1. sudo reboot"
echo "2. http://aerostab.local:8080"
echo "3. Mission Planner: deploy/ardupilot_aerostab.param"
echo "4. Pi TX→FC RX, RX→TX, GND, 5V @ 230400"
echo "5. Arm PosHold з пульта лише при FLIGHT OK"
echo "6. WiFi (опційно): sudo aerostab-wifi \"SSID\" \"pass\""
