#!/bin/bash
USER=pilot

AUTORUN="/home/$USER/start" 
LOGFILE="/home/pub/records/usb_script.log"
LOCKFILE="/tmp/usbautorun.lock"


sudo chmod -R 777 /home/$USER/start/

# Check if the lock file exists
if [ -e "$LOCKFILE" ]; then
    echo "Script is already running, exiting." >> "$LOGFILE"
    exit 0
fi

# Create the lock file
touch "$LOCKFILE"

# Ensure the lock file is removed when the script exits
trap "rm -f $LOCKFILE" EXIT

rm -f "$LOGFILE"
echo "$(date '+%M:%S.%3N') USB script started" >> "$LOGFILE"

# Wait for the USB drive to be mounted
MAX_WAIT=50  # Maximum wait time in seconds
COUNTER=0
MOUNT_DIR=""
MOUNT_PREFIX="/media" 

sudo mount -o remount,size=5M /dev/shm
sudo rm -rf /dev/shm/*

echo "$(date '+%M:%S.%3N') Waiting for USB drive to mount..." >> "$LOGFILE"

while [ $COUNTER -lt $MAX_WAIT ]; do
    # Find the mount directory
    MOUNT_DIR=$(lsblk -o NAME,MOUNTPOINT | grep "$MOUNT_PREFIX" | awk '{print $2}')
    
    echo "$MOUNT_DIR" >> "$LOGFILE"
    
    if [ -n "$MOUNT_DIR" ]; then
        echo "$(date '+%M:%S.%3N') USB drive mounted at $MOUNT_DIR" >> "$LOGFILE"
        break
    fi
    echo "$(date '+%M:%S.%3N') ...waiting for mount..." >> "$LOGFILE"
    sleep 1
    COUNTER=$((COUNTER + 1))
done

if [ -z "$MOUNT_DIR" ]; then
    echo "$(date '+%M:%S.%3N') USB drive is not mounted" >> "$LOGFILE"
    exit 0
fi

# Define the paths for the executable and settings
SEEK="$MOUNT_DIR/wifi.txt"

# If the executable found, run the executable
if [ -f "$SEEK" ]; then
    cp -v $MOUNT_DIR/wifi.txt /home/$USER/start/data/wifi.txt >> "$MOUNT_DIR/updated.txt" 2>&1
    /usr/bin/bash -c '/usr/bin/wifi.sh > '$MOUNT_DIR/wifi_log.txt' 2>&1'
else
    echo "$(date '+%M:%S.%3N') wifi.txt not found" >> "$LOGFILE"
fi


# echo "$(date): Found sync.txt. Starting sync..." >> "$LOGFILE"
# rsync -av --include '*/' "$AUTORUN/data/records"/ "$MOUNT_DIR/records"/ >> "$LOGFILE"
