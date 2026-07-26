#!/bin/bash
# Video decoder and display for ground station
# Receives MPEG-TS stream from ruben-rx.py via UDP

set -e

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
source "$SCRIPT_DIR/config.sh"

echo "[*] Starting video display..."
echo "    Input: udp://127.0.0.1:$VIDEO_PORT"
echo "    Buffer: ${DECODE_BUFFER}ms"

# Try different players in order of preference
if command -v mpv &> /dev/null; then
    echo "[*] Using mpv"
    exec mpv --no-cache \
        --untimed \
        --no-demuxer-thread \
        --video-sync=audio \
        --vd-lavc-threads=1 \
        --profile=low-latency \
        "udp://127.0.0.1:${VIDEO_PORT}"

elif command -v ffplay &> /dev/null; then
    echo "[*] Using ffplay"
    exec ffplay -hide_banner \
        -fflags nobuffer \
        -flags low_delay \
        -framedrop \
        -strict experimental \
        -probesize 32 \
        -analyzeduration 0 \
        -sync ext \
        "udp://127.0.0.1:${VIDEO_PORT}"

elif command -v vlc &> /dev/null; then
    echo "[*] Using VLC"
    exec vlc --network-caching=$DECODE_BUFFER \
        --clock-jitter=0 \
        --clock-synchro=0 \
        "udp://@:${VIDEO_PORT}"
else
    echo "[-] No video player found!"
    echo "    Install one of: mpv, ffplay (ffmpeg), vlc"
    exit 1
fi
