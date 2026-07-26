#!/bin/bash
# Ruben-FPV Ground Station Launcher

set -e

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
source "$SCRIPT_DIR/config.sh"

# Export config for Python script
export WIFI_INTERFACE
export VIDEO_PORT

echo "=========================================="
echo "       RUBEN-FPV GROUND STATION"
echo "=========================================="
echo ""
echo "Interface: $WIFI_INTERFACE"
echo "Channel:   $WIFI_CHANNEL"
echo ""

cleanup() {
    echo ""
    echo "[*] Stopping Ruben-FPV Ground Station..."
    [ -n "$DISPLAY_PID" ] && kill $DISPLAY_PID 2>/dev/null || true
    [ -n "$RX_PID" ] && kill $RX_PID 2>/dev/null || true
    wait 2>/dev/null
    echo "[*] Stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# Start RX process
echo "[*] Starting RX process..."
python3 "$SCRIPT_DIR/ruben-rx.py" &
RX_PID=$!
sleep 1

if ! kill -0 $RX_PID 2>/dev/null; then
    echo "[-] RX process failed to start"
    exit 1
fi

# Start display
echo "[*] Starting video display..."
"$SCRIPT_DIR/ruben-display.sh" &
DISPLAY_PID=$!

wait -n $DISPLAY_PID $RX_PID
echo "[-] Process exited unexpectedly"
cleanup
