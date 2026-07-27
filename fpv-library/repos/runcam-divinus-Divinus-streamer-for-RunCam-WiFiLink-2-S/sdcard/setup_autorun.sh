#!/bin/sh
# setup_autorun.sh — ONE-TIME SSH setup to enable SD card autorun
# Run this ONCE via SSH: sh /mnt/mmcblk0p1/setup_autorun.sh
# After this, all future installs/updates work via SD card only.

SD="/mnt/mmcblk0p1"
RC="/etc/rc.local"

echo "[setup] Remounting rootfs as rw..."
mount -o remount,rw /

echo "[setup] Adding SD autorun trigger to $RC..."
# Remove old entry if exists
sed -i '/mmcblk0p1.*autorun/d' "$RC"

# Inject before final 'exit 0'
sed -i '/^exit 0/i # SD card autorun\nmount /dev/mmcblk0p1 /mnt/mmcblk0p1 2>/dev/null || true\n[ -f /mnt/mmcblk0p1/autorun.sh ] \&\& sh /mnt/mmcblk0p1/autorun.sh \&' "$RC"

echo "[setup] Done! rc.local now:"
cat "$RC"
echo ""
echo "[setup] SD autorun is now PERMANENT."
echo "[setup] From now on: put files on SD → insert → power on → done."
