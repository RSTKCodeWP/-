#!/usr/bin/env bash
# AeroStab production installer — Raspberry Pi OS Bookworm 64-bit
set -euo pipefail

INSTALL_DIR="/opt/aerostab"
CONFIG_DIR="/etc/aerostab"
LOG_DIR="/var/log/aerostab"
USER_NAME="${SUDO_USER:-pi}"

echo "=== AeroStab v0.2 installer ==="
[[ "$(id -u)" -eq 0 ]] || { echo "sudo $0"; exit 1; }

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  python3 python3-pip python3-venv python3-dev \
  libcap-dev libatlas-base-dev \
  libcamera-apps libcamera-dev \
  avahi-daemon

# Frank-S01 / OV5647 CSI + UART for FC
CONFIG_TXT="/boot/firmware/config.txt"
if [[ -f "$CONFIG_TXT" ]]; then
  grep -q '^camera_auto_detect=1' "$CONFIG_TXT" || echo 'camera_auto_detect=1' >> "$CONFIG_TXT"
  grep -q '^dtoverlay=ov5647' "$CONFIG_TXT" || echo 'dtoverlay=ov5647' >> "$CONFIG_TXT"
  grep -q '^dtoverlay=disable-bt' "$CONFIG_TXT" || echo 'dtoverlay=disable-bt' >> "$CONFIG_TXT"
  grep -q '^enable_uart=1' "$CONFIG_TXT" || echo 'enable_uart=1' >> "$CONFIG_TXT"
  grep -q '^gpu_mem=128' "$CONFIG_TXT" || echo 'gpu_mem=128' >> "$CONFIG_TXT"
fi

mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$LOG_DIR"
chown -R "$USER_NAME:$USER_NAME" "$LOG_DIR"

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
rsync -a --exclude '.venv' --exclude '__pycache__' --exclude 'logs' "$SCRIPT_DIR/" "$INSTALL_DIR/"

python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip wheel
"$INSTALL_DIR/.venv/bin/pip" install -e "$INSTALL_DIR[pi]"

[[ -f "$CONFIG_DIR/config.yaml" ]] || cp "$INSTALL_DIR/config/default.yaml" "$CONFIG_DIR/config.yaml"
touch "$CONFIG_DIR/mask.json"
chown "$USER_NAME:$USER_NAME" "$CONFIG_DIR/mask.json" "$CONFIG_DIR/config.yaml"

install -m 644 "$INSTALL_DIR/deploy/aerostab.service" /etc/systemd/system/aerostab.service
install -m 755 "$INSTALL_DIR/deploy/wifi_provision.sh" /usr/local/bin/aerostab-wifi

# mDNS: aerostab.local
if [[ -f /etc/avahi/services/aerostab.service ]]; then
  true
else
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
fi

systemctl daemon-reload
systemctl enable aerostab.service

echo ""
echo "=== AeroStab installed ==="
echo "Reboot, then open http://aerostab.local:8080"
echo "Wire: Pi TX→FC RX, Pi RX→FC TX, GND, 5V"
echo "Load deploy/ardupilot_aerostab.param in Mission Planner"
echo "Simulate: $INSTALL_DIR/.venv/bin/python -m aerostab --simulate"
