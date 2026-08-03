#!/bin/bash

# Update camera type and filesystem expansion
/usr/bin/firmware.sh
/usr/bin/expand.sh > /home/pi/boot.txt 2>&1

# Variables
DEV=/dev/mmcblk0p3
FLAG_FILE="/data/.expanded"
COMMENTS=""

# Safely unmount /data if mounted
sudo umount /data 2>/dev/null || true

# Perform filesystem check
FLOG=$(sudo fsck -fvy "$DEV" 2>&1)
FSCK_RESULT=$?
COMMENTS+="Checking $DEV returned ($FSCK_RESULT)\n"

if [ $FSCK_RESULT -eq 0 ] || [ $FSCK_RESULT -eq 1 ]; then
    COMMENTS+="Filesystem is healthy or errors corrected.\n"
else
    COMMENTS+="Filesystem check failed (code $FSCK_RESULT). Reviewing log...\n"
    if echo "$FLOG" | grep -qiE "UNRECOVERABLE|CORRUPTED|PANIC"; then
        COMMENTS+="Critical error detected. Reformatting $DEV.\n"
        sudo mkfs.ext4 -F "$DEV"
        COMMENTS+="Reformat complete.\n"
    else
        COMMENTS+="Non-critical error. Manual check recommended.\n"
    fi
fi

# Explicitly mount /data partition after fsck
if ! mountpoint -q /data; then
    if sudo mount -o commit=5,noatime,nodiratime,data=journal "$DEV" /data; then
        COMMENTS+="Mounted $DEV successfully.\n"
    else
        COMMENTS+="Error: Unable to mount $DEV after check.\n"
    fi
fi

# Proceed carefully even if mounting /data failed
if mountpoint -q /data; then
    # Ensure /data/records directory exists and has correct permissions
    sudo mkdir -p /data/records
    sudo chmod 777 /data/records

    # Ensure bind mount directory exists
    mkdir -p /home/pub/records

    # Ensure bind mount is active, add comments accordingly
    if ! mountpoint -q /home/pub/records; then
        if sudo mount --bind /data/records /home/pub/records; then
            COMMENTS+="Bind mount /home/pub/records successful.\n"
        else
            COMMENTS+="Warning: Bind mount failed.\n"
        fi
    fi

    # Safe to touch FLAG_FILE after mounting
    sudo touch "$FLAG_FILE"

    # Set permissions on directories only (no recursion on files)
    sudo find /home/pub/records -type d -exec chmod 777 {} \; &
else
    COMMENTS+="Mounting /data failed; skipping directory setup.\n"
fi

# Application start parameters
USER=pilot
PILOTHOME=start
BINARY=lserv

# Ensure log directory exists even if /data is not mounted (fallback scenario)
LOG_FILE=/data/records/logs-server.txt
if [ ! -d "$(dirname "$LOG_FILE")" ]; then
    sudo mkdir -p "$(dirname "$LOG_FILE")"
    sudo chmod 777 "$(dirname "$LOG_FILE")"
fi

# Output accumulated COMMENTS
echo -e "$COMMENTS" > "$LOG_FILE"

# Run application and append output to the log, regardless of previous errors
cd "/home/$USER/$PILOTHOME"
/home/$USER/$PILOTHOME/$BINARY >> "$LOG_FILE" 2>&1
