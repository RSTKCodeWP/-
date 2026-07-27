#!/bin/sh
echo "[restore] Stopping divinus..."
killall -9 divinus 2>/dev/null || true

mount -o remount,rw /

echo "[restore] Removing divinus..."
rm -f /usr/bin/divinus /etc/divinus.yaml
rm -f /etc/init.d/S95divinus

echo "[restore] Restoring majestic..."
[ -f /etc/init.d/S95majestic.disabled ] && mv /etc/init.d/S95majestic.disabled /etc/init.d/S95majestic

echo "[restore] Removing SD autorun from rc.local..."
sed -i '/mmcblk0p1.*autorun/d' /etc/rc.local

echo "[restore] Done. Reboot to start majestic."
