#!/bin/bash
#
# RTL8812AU/RTL8821AU Driver Installer
# Installs pre-compiled module if kernel matches, otherwise builds from source
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DRIVER_DIR="$SCRIPT_DIR/rtl8812au"
KERNEL_VERSION=$(uname -r)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}[*] RTL8812AU/RTL8821AU Driver Installer${NC}"
echo "    Kernel: $KERNEL_VERSION"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[-] Please run as root${NC}"
    exit 1
fi

# Check if already loaded
if lsmod | grep -q 88XXau; then
    echo -e "${GREEN}[+] Driver already loaded${NC}"
    exit 0
fi

# Try pre-compiled module first
PRECOMPILED="$DRIVER_DIR/88XXau.ko.xz"
PRECOMPILED_KERNEL="6.12.47+rpt-rpi-v8"  # Kernel this was compiled for

if [ "$KERNEL_VERSION" = "$PRECOMPILED_KERNEL" ] && [ -f "$PRECOMPILED" ]; then
    echo -e "${GREEN}[+] Using pre-compiled driver${NC}"

    # Create directory and copy
    mkdir -p "/lib/modules/$KERNEL_VERSION/updates/dkms"
    cp "$PRECOMPILED" "/lib/modules/$KERNEL_VERSION/updates/dkms/"

    # Update module dependencies
    depmod -a

    # Load module
    modprobe 88XXau

    echo -e "${GREEN}[+] Driver installed and loaded${NC}"
    exit 0
fi

# Kernel doesn't match - need to compile
echo -e "${YELLOW}[!] Kernel mismatch - need to compile from source${NC}"
echo "    Pre-compiled: $PRECOMPILED_KERNEL"
echo "    Current:      $KERNEL_VERSION"
echo ""

# Install build dependencies
echo "[*] Installing build dependencies..."
apt update
apt install -y dkms build-essential git

# Find kernel headers
HEADERS_PKG=$(apt-cache search "linux-headers-${KERNEL_VERSION}" | head -1 | cut -d' ' -f1)
if [ -n "$HEADERS_PKG" ]; then
    apt install -y "$HEADERS_PKG"
else
    echo -e "${YELLOW}[!] Kernel headers not found in repo${NC}"
    echo "    Trying generic package..."
    apt install -y linux-headers-rpi-v8 || true
fi

# Clone and build
echo "[*] Cloning driver source..."
TEMP_DIR=$(mktemp -d)
git clone --depth 1 https://github.com/aircrack-ng/rtl8812au.git "$TEMP_DIR/rtl8812au"

echo "[*] Building driver (this takes a while on Pi)..."
cd "$TEMP_DIR/rtl8812au"
make dkms_install

# Cleanup
rm -rf "$TEMP_DIR"

# Load module
modprobe 88XXau

echo -e "${GREEN}[+] Driver compiled, installed, and loaded${NC}"
