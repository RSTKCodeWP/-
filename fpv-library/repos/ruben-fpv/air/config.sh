#!/bin/bash
# Ruben-FPV Air Unit Configuration

# Source common config
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
source "$SCRIPT_DIR/../common/config.sh"

# Video device (check with: v4l2-ctl --list-devices)
VIDEO_DEVICE="${VIDEO_DEVICE:-/dev/video0}"

# Video encoding settings
VIDEO_WIDTH="${VIDEO_WIDTH:-1280}"
VIDEO_HEIGHT="${VIDEO_HEIGHT:-720}"
VIDEO_FPS="${VIDEO_FPS:-30}"
VIDEO_BITRATE="${VIDEO_BITRATE:-4M}"

# Keyframe interval (lower = faster recovery after packet loss, higher = better compression)
VIDEO_GOP="${VIDEO_GOP:-10}"
