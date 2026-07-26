#!/bin/bash
# Ruben-FPV Ground Station Configuration

# Source common config
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
source "$SCRIPT_DIR/../common/config.sh"

# Display settings
DISPLAY_OUTPUT="${DISPLAY_OUTPUT:-:0}"  # X display or framebuffer

# Decoder settings (for ffplay/mpv)
DECODE_BUFFER="${DECODE_BUFFER:-100}"   # Buffer size in ms (lower = less latency)
