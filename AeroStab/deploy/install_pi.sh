#!/usr/bin/env bash
# AeroStab production installer — Raspberry Pi OS Bookworm 64-bit
# Goal: flash → install → reboot → http://aerostab.local:8080 → PosHold hover
set -euo pipefail

INSTALL_DIR="/opt/aerostab"
CONFIG_DIR="/etc/aerostab"
LOG_DIR="/var/log/aerostab"
USER_NAME="${SUDO_USER:-pi}"

echo "=== AeroStab v0.5 installer ==="
[[ "$(id -u)" -eq 0 ]] || { echo "sudo $0"; exit 1; }

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  python3 python3-pip python3-venv python3-dev \
  libcap-dev libatlas-base-dev \
  libcamera-apps libcamera-dev \
  avahi-daemon rsync

# Groups for UART / camera / SPI
usermod -aG dialout,video,spi,i2c "$USER_NAME" 2>/dev/null || true

# Hostname for aerostab.local
hostnamectl set-hostname aerostab 2>/dev/null || true
if [[ -f /etc/hosts ]]; then
  grep -q 'aerostab' /etc/hosts || echo '127.0.1.1 aerostab' >> /etc/hosts
fi

# Frank-S01 / OV5647 CSI + UART for FC — profile via firmware.sh
CONFIG_TXT="/boot/firmware/config.txt"
[[ -f "$CONFIG_TXT" ]] || CONFIG_TXT="/boot/config.txt"

mkdir -p "$CONFIG_DIR/firmware/zero/ov5647" "$CONFIG_DIR/firmware/zero/imx219"
install -m 644 "$INSTALL_DIR/deploy/settings/firmware/zero/ov5647/config.txt" \
  "$CONFIG_DIR/firmware/zero/ov5647/config.txt"
install -m 644 "$INSTALL_DIR/deploy/settings/firmware/zero/imx219/config.txt" \
  "$CONFIG_DIR/firmware/zero/imx219/config.txt"
[[ -f "$CONFIG_DIR/camera.txt" ]] || echo 'ov5647' > "$CONFIG_DIR/camera.txt"

install -m 755 "$INSTALL_DIR/deploy/firmware.sh" /usr/local/bin/aerostab-firmware
/usr/local/bin/aerostab-firmware || true

if [[ -f "$CONFIG_TXT" ]]; then
  grep -q '^gpu_mem=' "$CONFIG_TXT" || echo 'gpu_mem=128' >> "$CONFIG_TXT"
fi

# Disable serial console on UART (Bookworm) — StabX stops getty@ttyAMA0
if [[ -f /boot/firmware/cmdline.txt ]]; then
  sed -i 's/console=serial0,[0-9]* //g' /boot/firmware/cmdline.txt || true
fi
for unit in serial-getty@ttyAMA0.service getty@ttyAMA0.service; do
  systemctl disable "$unit" 2>/dev/null || true
  systemctl stop "$unit" 2>/dev/null || true
done

# Optional /data records partition (StabX p3) — bind-mount if present
if grep -q '/data ' /proc/mounts 2>/dev/null; then
  mkdir -p /data/records /var/log/aerostab
  chmod 777 /data/records 2>/dev/null || true
  if ! mountpoint -q /var/log/aerostab 2>/dev/null; then
    mkdir -p /data/records/aerostab
    mount --bind /data/records/aerostab /var/log/aerostab 2>/dev/null || true
  fi
fi

mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$LOG_DIR"

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
rsync -a --exclude '.venv' --exclude '__pycache__' --exclude 'logs' --exclude '.pytest_cache' \
  "$SCRIPT_DIR/" "$INSTALL_DIR/"

python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip wheel
"$INSTALL_DIR/.venv/bin/pip" install -e "$INSTALL_DIR[pi]"
"$INSTALL_DIR/.venv/bin/pip" install -e "$INSTALL_DIR[pi,sensors]" || true

[[ -f "$CONFIG_DIR/config.yaml" ]] || cp "$INSTALL_DIR/config/default.yaml" "$CONFIG_DIR/config.yaml"

# Valid empty mask (never touch empty file — crashes JSON loader)
python3 - <<'PY'
import json
from pathlib import Path
p = Path("/etc/aerostab/mask.json")
if not p.exists() or not p.read_text().strip():
    cols, rows = 16, 12
    p.write_text(json.dumps({"cols": cols, "rows": rows, "cells": [False]*(cols*rows)}))
PY

chown -R "$USER_NAME:$USER_NAME" "$INSTALL_DIR" "$CONFIG_DIR" "$LOG_DIR"
install -m 644 "$INSTALL_DIR/FLIGHT.md" "$CONFIG_DIR/FLIGHT.md" 2>/dev/null || true

install -m 644 "$INSTALL_DIR/deploy/aerostab.service" /etc/systemd/system/aerostab.service
install -m 755 "$INSTALL_DIR/deploy/wifi_provision.sh" /usr/local/bin/aerostab-wifi
install -m 644 "$INSTALL_DIR/deploy/aerostab-wifi.service" /etc/systemd/system/aerostab-wifi.service
install -m 644 "$INSTALL_DIR/deploy/aerostab-usb-wifi.service" /etc/systemd/system/aerostab-usb-wifi.service

# Fallback WiFi profile (field setup hotspot alternative to StabX uapilot)
if command -v nmcli >/dev/null 2>&1; then
  install -m 600 "$INSTALL_DIR/deploy/aerostab.nmconnection" \
    /etc/NetworkManager/system-connections/aerostab-fallback.nmconnection 2>/dev/null || true
fi

# mDNS
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
systemctl enable aerostab.service aerostab-wifi.service aerostab-usb-wifi.service

echo ""
echo "=== AeroStab installed ==="
echo "1. Reboot: sudo reboot"
echo "2. Open:   http://aerostab.local:8080"
echo "3. Complete first-flight wizard (green = ready)"
echo "4. Load:   deploy/ardupilot_aerostab.param in Mission Planner"
echo "5. WiFi: put wifi.txt on USB (SSID line1, password line2) or:"
echo "     sudo aerostab-wifi \"SSID\" \"password\""
echo "6. Camera profile: echo imx219 > /etc/aerostab/camera.txt && sudo aerostab-firmware && reboot"
echo "7. Wire:   Pi TX→FC RX, Pi RX→FC TX, GND, 5V"
echo "8. Arm PosHold only when UI shows FLIGHT OK (or use ARM FC button)"
echo ""
echo "Params note: SERIAL2 = TELEM2 @ 230400 — change SERIALx if needed"
