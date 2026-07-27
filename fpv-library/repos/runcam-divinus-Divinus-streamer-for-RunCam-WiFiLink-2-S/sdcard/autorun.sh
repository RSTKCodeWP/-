#!/bin/sh
SD="/mnt/mmcblk0p1"
LOG="$SD/install.log"

# Mount SD card if not already mounted
mount /dev/mmcblk0p1 "$SD" 2>/dev/null || true

echo "=== RunCam Divinus Installer $(date) ===" >> "$LOG"

if [ -f /usr/bin/divinus ] && [ -f /etc/divinus.yaml ]; then
    echo "[autorun] Already installed, skip." >> "$LOG"
    exit 0
fi

if [ ! -f "$SD/install_divinus.sh" ]; then
    echo "[autorun] ERROR: install_divinus.sh not found!" >> "$LOG"
    exit 1
fi

chmod +x "$SD/install_divinus.sh"
sh "$SD/install_divinus.sh" 2>&1 | tee -a "$LOG"
sleep 5 && reboot
