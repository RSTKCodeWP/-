#!/bin/bash
set -e

export PATH=/usr/sbin:/usr/bin:/sbin:/bin

DISK="/dev/mmcblk0"
DATA_PARTITION="${DISK}p3"
FLAG_FILE="/data/.expanded"

# Wait until /data is mounted or mount it temporarily to check flag
mkdir -p /data
mountpoint -q /data || mount $DATA_PARTITION /data

# Check if partition already expanded
if [ -f "$FLAG_FILE" ]; then
    echo "Partition already expanded. Skipping."
    exit 0
fi

echo "Unmounting /data partition..."
umount /data || true

echo "Calculating new partition boundaries..."
LAST_END=$(fdisk -l $DISK | grep "${DISK}p2" | awk '{print $3}')
NEW_START=$(( ( (LAST_END / 2048) + 1 ) * 2048 ))  # aligned to 1MiB
DISK_END=$(($(cat /sys/block/mmcblk0/size) - 1))

echo "Expanding partition..."
fdisk $DISK <<EOF
d
3
n
p
3
$NEW_START
$DISK_END
w
EOF

sleep 3
partprobe $DISK
sleep 3

echo "Checking filesystem before resizing..."
e2fsck -f -y $DATA_PARTITION || true

echo "Resizing filesystem to match new partition size..."
resize2fs $DATA_PARTITION

echo "Remounting expanded partition..."
mount $DATA_PARTITION /data
chmod 777 /data

# Create flag file indicating successful expansion
touch $FLAG_FILE

echo "Partition expansion completed successfully."
lsblk

# Optionally reboot
reboot now
