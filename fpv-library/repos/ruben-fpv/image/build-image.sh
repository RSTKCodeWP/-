#!/bin/bash
#
# Ruben-FPV Image Builder
# Creates a ready-to-flash Raspberry Pi image
#
# Usage: sudo ./build-image.sh [output-name]
#
# Requirements: Linux with losetup, mount, wget, xz
#

set -e

# Configuration
PI_OS_URL="https://downloads.raspberrypi.com/raspios_lite_arm64/images/raspios_lite_arm64-2024-11-19/2024-11-19-raspios-bookworm-arm64-lite.img.xz"
PI_OS_FILENAME="raspios-lite.img.xz"
OUTPUT_NAME="${1:-ruben-fpv.img}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
WORK_DIR="/tmp/ruben-image-build"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}"
echo "╔═══════════════════════════════════════╗"
echo "║     RUBEN-FPV IMAGE BUILDER           ║"
echo "╚═══════════════════════════════════════╝"
echo -e "${NC}"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[-] Please run as root (sudo ./build-image.sh)${NC}"
    exit 1
fi

# Check dependencies
for cmd in losetup mount wget xz; do
    if ! command -v $cmd &> /dev/null; then
        echo -e "${RED}[-] Missing dependency: $cmd${NC}"
        exit 1
    fi
done

# Create work directory
echo "[*] Setting up work directory..."
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# Download Pi OS if not cached
if [ ! -f "/tmp/$PI_OS_FILENAME" ]; then
    echo "[*] Downloading Raspberry Pi OS Lite..."
    wget -O "/tmp/$PI_OS_FILENAME" "$PI_OS_URL"
else
    echo "[*] Using cached Pi OS image"
fi

# Extract image
echo "[*] Extracting image..."
xz -dk -c "/tmp/$PI_OS_FILENAME" > "$OUTPUT_NAME"

# Get image size and expand if needed (add 500MB for our stuff)
echo "[*] Expanding image by 500MB..."
dd if=/dev/zero bs=1M count=500 >> "$OUTPUT_NAME" 2>/dev/null

# Setup loop device
echo "[*] Setting up loop device..."
LOOP=$(losetup -fP --show "$OUTPUT_NAME")
echo "    Loop device: $LOOP"

# Wait for partitions
sleep 2
partprobe "$LOOP" 2>/dev/null || true
sleep 1

# Find partitions
BOOT_PART="${LOOP}p1"
ROOT_PART="${LOOP}p2"

if [ ! -b "$ROOT_PART" ]; then
    echo -e "${RED}[-] Could not find root partition${NC}"
    losetup -d "$LOOP"
    exit 1
fi

# Expand root partition
echo "[*] Expanding root partition..."
parted -s "$LOOP" resizepart 2 100%
e2fsck -f -y "$ROOT_PART" || true
resize2fs "$ROOT_PART"

# Create mount points
BOOT_MNT="$WORK_DIR/boot"
ROOT_MNT="$WORK_DIR/root"
mkdir -p "$BOOT_MNT" "$ROOT_MNT"

# Mount partitions
echo "[*] Mounting partitions..."
mount "$ROOT_PART" "$ROOT_MNT"
mount "$BOOT_PART" "$BOOT_MNT"

# Create directory structure
echo "[*] Installing Ruben-FPV..."
mkdir -p "$ROOT_MNT/opt/ruben-fpv/repo"
mkdir -p "$ROOT_MNT/opt/ruben-fpv/drivers"

# Copy all repo files
cp -r "$REPO_DIR/air" "$ROOT_MNT/opt/ruben-fpv/repo/"
cp -r "$REPO_DIR/ground" "$ROOT_MNT/opt/ruben-fpv/repo/"
cp -r "$REPO_DIR/common" "$ROOT_MNT/opt/ruben-fpv/repo/"
cp -r "$REPO_DIR/drivers"/* "$ROOT_MNT/opt/ruben-fpv/drivers/" 2>/dev/null || true

# Copy firstboot script
cp "$SCRIPT_DIR/firstboot.sh" "$ROOT_MNT/opt/ruben-fpv/"
chmod +x "$ROOT_MNT/opt/ruben-fpv/firstboot.sh"

# Install firstboot service
cp "$SCRIPT_DIR/ruben-firstboot.service" "$ROOT_MNT/etc/systemd/system/"
ln -sf /etc/systemd/system/ruben-firstboot.service "$ROOT_MNT/etc/systemd/system/multi-user.target.wants/ruben-firstboot.service"

# Install main service file (will be enabled by firstboot)
cp "$SCRIPT_DIR/ruben-fpv.service" "$ROOT_MNT/etc/systemd/system/" 2>/dev/null || \
cat > "$ROOT_MNT/etc/systemd/system/ruben-fpv.service" << 'EOF'
[Unit]
Description=Ruben-FPV Service
After=network.target

[Service]
Type=simple
ExecStartPre=/opt/ruben-fpv/setup-monitor.sh
ExecStart=/opt/ruben-fpv/start.sh
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

# Create default config
cat > "$ROOT_MNT/opt/ruben-fpv/config.sh" << 'EOF'
#!/bin/bash
# Ruben-FPV Configuration
WIFI_INTERFACE="wlan1"
WIFI_CHANNEL="36"
VIDEO_PORT="5000"
MTU_SIZE="1400"
VIDEO_DEVICE="/dev/video0"
VIDEO_WIDTH="1280"
VIDEO_HEIGHT="720"
VIDEO_FPS="30"
VIDEO_BITRATE="4M"
VIDEO_GOP="10"
EOF

# Create ruben.txt on boot partition
echo "[*] Creating boot config template..."
cat > "$BOOT_MNT/ruben.txt" << 'EOF'
# Ruben-FPV Configuration
# Edit this file to configure the device role
#
# ROLE options:
#   air    = Air Unit (transmitter, camera, headless)
#   ground = Ground Station (receiver, display, desktop)
#
# After editing, safely eject SD card and boot your Pi

ROLE=air
EOF

# Enable SSH by default
touch "$BOOT_MNT/ssh"

# Set hostname based on role (will be updated by firstboot)
echo "ruben-fpv" > "$ROOT_MNT/etc/hostname"

# Cleanup
echo "[*] Unmounting..."
sync
umount "$BOOT_MNT"
umount "$ROOT_MNT"
losetup -d "$LOOP"

# Move to output location
OUTPUT_PATH="$REPO_DIR/$OUTPUT_NAME"
mv "$WORK_DIR/$OUTPUT_NAME" "$OUTPUT_PATH"

# Cleanup work dir
rm -rf "$WORK_DIR"

# Calculate checksum
echo "[*] Calculating checksum..."
SHA256=$(sha256sum "$OUTPUT_PATH" | cut -d' ' -f1)

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════╗"
echo "║         IMAGE BUILD COMPLETE!         ║"
echo "╚═══════════════════════════════════════╝${NC}"
echo ""
echo "Output: $OUTPUT_PATH"
echo "Size:   $(du -h "$OUTPUT_PATH" | cut -f1)"
echo "SHA256: $SHA256"
echo ""
echo -e "${YELLOW}To use:${NC}"
echo "1. Flash to SD card:"
echo "   sudo dd if=$OUTPUT_PATH of=/dev/sdX bs=4M status=progress"
echo "   # or use Raspberry Pi Imager"
echo ""
echo "2. Edit boot partition ruben.txt:"
echo "   ROLE=air     # for transmitter"
echo "   ROLE=ground  # for receiver"
echo ""
echo "3. Insert SD card and power on Pi"
echo ""
