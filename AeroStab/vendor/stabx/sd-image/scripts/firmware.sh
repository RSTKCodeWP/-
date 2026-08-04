#!/bin/bash

DATA_DIR="/home/pilot/start/data"
CAMERA_FILE="$DATA_DIR/camera.txt"
PLATFORM="zero"
FIRMWARE_DIR="$DATA_DIR/settings/firmware/$PLATFORM"
DEST_CONFIG="/boot/firmware/config.txt"

# Check if camera.txt exists
if [[ -f "$CAMERA_FILE" ]]; then
    camera=$(tr '[:upper:]' '[:lower:]' < "$CAMERA_FILE")
    echo "Read camera: '$camera'"
else
    echo "camera.txt not found. Exiting."
    exit 1
fi

# Loop through folders in the firmware directory
matched=0
for folder in "$FIRMWARE_DIR"/*/; do
    folder_name=$(basename "$folder" | tr '[:upper:]' '[:lower:]')
    echo "Checking folder: '$folder_name' against camera: '$camera'"
    if [[ "$camera" == "$folder_name"* ]]; then
        echo "Match found: '$folder_name'"
        SOURCE_CONFIG="$folder/config.txt"
        if [[ -f "$SOURCE_CONFIG" ]]; then
            echo "Found source config: '$SOURCE_CONFIG'"
            if ! cmp -s "$SOURCE_CONFIG" "$DEST_CONFIG"; then
                echo "Configuration differs. Copying '$SOURCE_CONFIG' to '$DEST_CONFIG'"
                if sudo cp "$SOURCE_CONFIG" "$DEST_CONFIG"; then
                    echo "Copy successful. System will reboot."
                    matched=1
                else
                    echo "Copy failed. Not rebooting."
                    matched=0
                fi
            else
                echo "Configuration already up-to-date."
            fi
        else
            echo "No config.txt found in '$folder_name'."
        fi
        break
    fi
done

# Reboot if config was updated
if [[ "$matched" -eq 1 ]]; then
    echo "Rebooting system now."
    sudo reboot now
else
    echo "No matching folder found or no update needed."
fi
