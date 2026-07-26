#!/bin/bash
# Ruben-FPV Air Unit Launcher

set -e

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
source "$SCRIPT_DIR/config.sh"

# Export config for Python script
export WIFI_INTERFACE
export VIDEO_PORT
export MTU_SIZE

echo "=========================================="
echo "       RUBEN-FPV AIR UNIT"
echo "=========================================="
echo ""
echo "Interface: $WIFI_INTERFACE"
echo "Channel:   $WIFI_CHANNEL"
echo "Video:     ${VIDEO_WIDTH}x${VIDEO_HEIGHT}@${VIDEO_FPS}fps"
echo "Bitrate:   $VIDEO_BITRATE"
echo ""

cleanup() {
    echo ""
    echo "[*] Stopping Ruben-FPV Air Unit..."
    [ -n "$VIDEO_PID" ] && kill $VIDEO_PID 2>/dev/null || true
    [ -n "$TX_PID" ] && kill $TX_PID 2>/dev/null || true
    wait 2>/dev/null
    echo "[*] Stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# Start TX process
echo "[*] Starting TX process..."
python3 "$SCRIPT_DIR/ruben-tx.py" &
TX_PID=$!
sleep 1

if ! kill -0 $TX_PID 2>/dev/null; then
    echo "[-] TX process failed to start"
    exit 1
fi

# Start video pipeline
echo "[*] Starting video pipeline..."
"$SCRIPT_DIR/ruben-video.sh" &
VIDEO_PID=$!

wait -n $VIDEO_PID $TX_PID
echo "[-] Process exited unexpectedly"
cleanup
