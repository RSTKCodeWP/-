#!/bin/bash
#
# Ruben-FPV Installer
# Run this script to set up either Air Unit or Ground Station
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/rubenCodeforges/ruben-fpv/main/install.sh | sudo bash
#   # or after cloning:
#   sudo ./install.sh
#

set -e

INSTALL_DIR="/opt/ruben-fpv"
REPO_URL="https://github.com/rubenCodeforges/ruben-fpv.git"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}"
echo "╔═══════════════════════════════════════╗"
echo "║       RUBEN-FPV INSTALLER             ║"
echo "║   Low-Latency FPV Video System        ║"
echo "╚═══════════════════════════════════════╝"
echo -e "${NC}"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[-] Please run as root (sudo ./install.sh)${NC}"
    exit 1
fi

# Detect if we're running from repo or standalone
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/air/ruben-tx.py" ]; then
    SOURCE_DIR="$SCRIPT_DIR"
    echo "[*] Installing from local repo: $SOURCE_DIR"
else
    # Clone repo
    echo "[*] Cloning repository..."
    SOURCE_DIR=$(mktemp -d)
    git clone --depth 1 "$REPO_URL" "$SOURCE_DIR"
fi

# Ask for role
echo ""
echo "Select device role:"
echo "  1) Air Unit (transmitter - camera side)"
echo "  2) Ground Station (receiver - display side)"
echo ""
read -p "Enter choice [1/2]: " ROLE_CHOICE

case $ROLE_CHOICE in
    1)
        ROLE="air"
        SERVICE_DESC="Ruben-FPV Air Unit Transmitter"
        ;;
    2)
        ROLE="ground"
        SERVICE_DESC="Ruben-FPV Ground Station Receiver"
        ;;
    *)
        echo -e "${RED}[-] Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}[+] Installing as: ${ROLE^^} UNIT${NC}"
echo ""

# Install dependencies
echo "[*] Installing dependencies..."
apt update
apt install -y ffmpeg python3-scapy wireless-tools iw

# Check for video tools on ground station
if [ "$ROLE" = "ground" ]; then
    if ! command -v mpv &> /dev/null && ! command -v ffplay &> /dev/null; then
        echo "[*] Installing mpv for video display..."
        apt install -y mpv
    fi
fi

# Create install directory
echo "[*] Installing to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"

# Copy files
cp -r "$SOURCE_DIR/common" "$INSTALL_DIR/"
cp -r "$SOURCE_DIR/$ROLE"/* "$INSTALL_DIR/"

# Set permissions
chmod +x "$INSTALL_DIR"/*.sh
chmod +x "$INSTALL_DIR"/*.py 2>/dev/null || true

# Detect WiFi interface
echo ""
echo "[*] Detecting WiFi interfaces..."
INTERFACES=$(iw dev | grep Interface | awk '{print $2}')
echo "    Available: $INTERFACES"

# Try to find external adapter (usually wlan1)
DEFAULT_IFACE="wlan1"
if ! echo "$INTERFACES" | grep -q "wlan1"; then
    DEFAULT_IFACE=$(echo "$INTERFACES" | head -1)
fi

read -p "WiFi interface to use [$DEFAULT_IFACE]: " WIFI_IFACE
WIFI_IFACE=${WIFI_IFACE:-$DEFAULT_IFACE}

# Update config with selected interface
sed -i "s/WIFI_INTERFACE=.*/WIFI_INTERFACE=\"$WIFI_IFACE\"/" "$INSTALL_DIR/config.sh"

# Create systemd service
echo "[*] Creating systemd service..."
cat > /etc/systemd/system/ruben-fpv.service << EOF
[Unit]
Description=$SERVICE_DESC
After=network.target

[Service]
Type=simple
ExecStartPre=$INSTALL_DIR/setup-monitor.sh
ExecStart=$INSTALL_DIR/start.sh
Restart=on-failure
RestartSec=5
User=root
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
LimitNOFILE=65536
Nice=-10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ruben-fpv

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

# Ask about RTL8812AU driver
echo ""
echo -e "${YELLOW}[?] Install RTL8812AU driver for T2U Plus adapter?${NC}"
echo "    (Required for TP-Link Archer T2U Plus)"
echo "    Pre-compiled driver included for kernel 6.12.47+rpt-rpi-v8"
read -p "Install driver? [y/N]: " INSTALL_DRIVER

if [ "$INSTALL_DRIVER" = "y" ] || [ "$INSTALL_DRIVER" = "Y" ]; then
    # Use the bundled driver installer (uses pre-compiled if kernel matches)
    if [ -f "$SOURCE_DIR/drivers/install-rtl8812au.sh" ]; then
        bash "$SOURCE_DIR/drivers/install-rtl8812au.sh"
    else
        # Fallback: compile from source
        echo "[*] Building RTL8812AU driver from source..."
        apt install -y git dkms build-essential

        # Try to find kernel headers
        HEADERS_PKG=$(apt-cache search "linux-headers-$(uname -r)" | head -1 | cut -d' ' -f1)
        [ -n "$HEADERS_PKG" ] && apt install -y "$HEADERS_PKG"

        DRIVER_DIR=$(mktemp -d)
        git clone --depth 1 https://github.com/aircrack-ng/rtl8812au.git "$DRIVER_DIR"
        cd "$DRIVER_DIR"
        make dkms_install || {
            echo -e "${YELLOW}[!] Driver install failed - check kernel headers${NC}"
        }
        cd -
        rm -rf "$DRIVER_DIR"
    fi
fi

# Cleanup temp dir if we cloned
if [ "$SOURCE_DIR" != "$SCRIPT_DIR" ]; then
    rm -rf "$SOURCE_DIR"
fi

# Done
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════╗"
echo "║       INSTALLATION COMPLETE!          ║"
echo "╚═══════════════════════════════════════╝${NC}"
echo ""
echo "Configuration: $INSTALL_DIR/config.sh"
echo ""
echo "Commands:"
echo "  Test manually:    sudo $INSTALL_DIR/start.sh"
echo "  Enable on boot:   sudo systemctl enable ruben-fpv"
echo "  Start service:    sudo systemctl start ruben-fpv"
echo "  View logs:        journalctl -u ruben-fpv -f"
echo ""

if [ "$ROLE" = "air" ]; then
    echo -e "${YELLOW}Note: Connect camera to USB and verify /dev/video0 exists${NC}"
else
    echo -e "${YELLOW}Note: Ensure channel matches air unit (default: 36)${NC}"
fi

echo ""
read -p "Enable auto-start on boot? [y/N]: " ENABLE_SERVICE
if [ "$ENABLE_SERVICE" = "y" ] || [ "$ENABLE_SERVICE" = "Y" ]; then
    systemctl enable ruben-fpv
    echo -e "${GREEN}[+] Service enabled${NC}"
fi

echo ""
echo "Done! Reboot recommended if driver was installed."
