#!/usr/bin/env bash
# AeroStab — first-boot installer for Raspberry Pi Zero 2W (Bookworm)
set -euo pipefail

INSTALL_DIR="/opt/aerostab"
CONFIG_DIR="/etc/aerostab"
LOG_DIR="/var/log/aerostab"
USER_NAME="${SUDO_USER:-pi}"

echo "=== AeroStab installer ==="

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo $0"
  exit 1
fi

apt-get update
apt-get install -y \
  python3 python3-pip python3-venv python3-dev \
  libcap-dev libatlas-base-dev \
  libcamera-apps libcamera-dev \
  git

# Enable camera + UART for flight controller
CONFIG_TXT="/boot/firmware/config.txt"
if [[ -f "$CONFIG_TXT" ]]; then
  grep -q '^camera_auto_detect=1' "$CONFIG_TXT" || echo 'camera_auto_detect=1' >> "$CONFIG_TXT"
  grep -q '^dtoverlay=ov5647' "$CONFIG_TXT" || echo 'dtoverlay=ov5647' >> "$CONFIG_TXT"
  # UART on GPIO 14/15, disable BT to free serial0
  grep -q '^dtoverlay=disable-bt' "$CONFIG_TXT" || echo 'dtoverlay=disable-bt' >> "$CONFIG_TXT"
  grep -q '^enable_uart=1' "$CONFIG_TXT" || echo 'enable_uart=1' >> "$CONFIG_TXT"
fi

CMDLINE="/boot/firmware/cmdline.txt"
if [[ -f "$CMDLINE" ]] && ! grep -q 'console=serial0' "$CMDLINE"; then
  sed -i 's/$/ console=serial0,115200/' "$CMDLINE" || true
fi

mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$LOG_DIR"
chown -R "$USER_NAME:$USER_NAME" "$LOG_DIR"

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
rsync -a --exclude '.venv' --exclude '__pycache__' "$SCRIPT_DIR/" "$INSTALL_DIR/"

python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip wheel
"$INSTALL_DIR/.venv/bin/pip" install -e "$INSTALL_DIR[pi]"

if [[ ! -f "$CONFIG_DIR/config.yaml" ]]; then
  cp "$INSTALL_DIR/config/default.yaml" "$CONFIG_DIR/config.yaml"
fi

install -m 644 "$INSTALL_DIR/deploy/aerostab.service" /etc/systemd/system/aerostab.service
systemctl daemon-reload
systemctl enable aerostab.service

# Wi-Fi helper (optional): put wifi.txt on USB stick with SSID on line 1, password line 2
install -m 755 "$INSTALL_DIR/deploy/wifi_provision.sh" /usr/local/bin/aerostab-wifi

echo ""
echo "=== Done ==="
echo "1. Wire FC: Pi TX(GPIO14)->FC RX, Pi RX(GPIO15)->FC TX, GND, 5V"
echo "2. Frank-S01 camera on CSI (ribbon: contacts toward board)"
echo "3. Edit $CONFIG_DIR/config.yaml (FOV 72.4 / 120 / 160 for your lens)"
echo "4. Flash ArduPilot params: deploy/ardupilot_aerostab.param"
echo "5. Reboot: sudo reboot"
echo "6. Web UI: http://aerostab.local:8080 or http://<pi-ip>:8080"
echo "7. Simulate on desk: sudo -u $USER_NAME $INSTALL_DIR/.venv/bin/python -m aerostab --simulate"
