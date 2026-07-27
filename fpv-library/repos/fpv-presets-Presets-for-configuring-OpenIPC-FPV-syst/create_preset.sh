#!/bin/bash

# Exit on error
set -e

# Check if a preset name is provided
if [ -z "$1" ]; then
    echo "Usage: $0 \"Preset Name\""
    exit 1
fi

# Convert preset name to lowercase and replace spaces with underscores
PRESET_NAME="$1"
FOLDER_NAME=$(echo "$PRESET_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '_')
PRESET_DIR="./presets/$FOLDER_NAME"

# Create the preset directory
mkdir -p "$PRESET_DIR/sensor"

# Create the preset-config.yaml file
cat <<EOF > "$PRESET_DIR/preset-config.yaml"
name: "$PRESET_NAME"
author: "Your Name"
description: "Description of $PRESET_NAME."
category: "FPV"
sensor: ""  # Set sensor file if needed
status: "Community"
tags: ["$PRESET_NAME"]
files:
  wfb.conf:
    txpower: "1"
    channel: "161"
    driver_txpower_override: "20"
    stbc: "1"
    ldpc: "1"
    mcs_index: "1"
    fec_k: "8"
    fec_n: "12"
  telemetry.conf:
    serial: /dev/ttyS2
    # 2 for msposd
    router: 0 
  majestic.yaml:
    fpv.enabled: "true"
    fpv.noiseLevel: "0"
    system.logLevel: "debug"
    video0.codec: "h265"
    video0.fps: "60"
    video0.bitrate: "4096"
    video0.size: "1920x1080"
    
EOF


# Create an empty sensor file as a placeholder
touch "$PRESET_DIR/sensor/.keep"

# Display success message
echo "✅ Preset '$PRESET_NAME' created successfully in '$PRESET_DIR'"
echo "Edit '$PRESET_DIR/preset-config.yaml' to configure the preset."
