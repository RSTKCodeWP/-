#!/bin/bash
# Setup WiFi adapter in monitor mode for packet capture

set -e

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
source "$SCRIPT_DIR/config.sh"

echo "[*] Setting up monitor mode on $WIFI_INTERFACE..."

# Kill processes that might interfere
echo "[*] Stopping interfering services..."
systemctl stop wpa_supplicant 2>/dev/null || true
systemctl stop NetworkManager 2>/dev/null || true
killall wpa_supplicant 2>/dev/null || true

# Bring interface down
echo "[*] Bringing interface down..."
ip link set "$WIFI_INTERFACE" down

# Set monitor mode
echo "[*] Setting monitor mode..."
iw "$WIFI_INTERFACE" set monitor control

# Bring interface up
echo "[*] Bringing interface up..."
ip link set "$WIFI_INTERFACE" up

# Set channel (must match air unit!)
echo "[*] Setting channel $WIFI_CHANNEL..."
iw "$WIFI_INTERFACE" set channel "$WIFI_CHANNEL"

# Verify
MODE=$(iwconfig "$WIFI_INTERFACE" 2>/dev/null | grep -o "Mode:[^ ]*" | cut -d: -f2)
if [ "$MODE" = "Monitor" ]; then
    echo "[+] Success! $WIFI_INTERFACE is in Monitor mode on channel $WIFI_CHANNEL"
else
    echo "[-] Failed to set monitor mode. Current mode: $MODE"
    exit 1
fi
