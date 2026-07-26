#!/bin/bash
# Video capture and H.264 encoding pipeline
# Outputs MPEG-TS stream to UDP for raw packet transmission

set -e

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
source "$SCRIPT_DIR/config.sh"

echo "[*] Starting video pipeline..."
echo "    Device: $VIDEO_DEVICE"
echo "    Resolution: ${VIDEO_WIDTH}x${VIDEO_HEIGHT} @ ${VIDEO_FPS}fps"
echo "    Bitrate: $VIDEO_BITRATE"
echo "    Output: udp://127.0.0.1:$VIDEO_PORT"

# Check if video device exists
if [ ! -e "$VIDEO_DEVICE" ]; then
    echo "[-] Video device $VIDEO_DEVICE not found!"
    echo "    Available devices:"
    v4l2-ctl --list-devices 2>/dev/null || echo "    (v4l2-ctl not available)"
    exit 1
fi

# Run ffmpeg
# -f v4l2: V4L2 input
# -input_format mjpeg: Request MJPEG from camera (most USB cams support this)
# -c:v h264_v4l2m2m: Hardware H.264 encoder (Pi GPU)
# -g: Keyframe interval (important for recovery after packet loss)
# -bf 0: No B-frames (reduces latency)
# -f mpegts: MPEG-TS container (handles packet boundaries well)

exec ffmpeg -hide_banner -loglevel warning \
    -f v4l2 \
    -input_format mjpeg \
    -video_size "${VIDEO_WIDTH}x${VIDEO_HEIGHT}" \
    -framerate "$VIDEO_FPS" \
    -i "$VIDEO_DEVICE" \
    -c:v h264_v4l2m2m \
    -b:v "$VIDEO_BITRATE" \
    -g "$VIDEO_GOP" \
    -bf 0 \
    -f mpegts \
    "udp://127.0.0.1:${VIDEO_PORT}?pkt_size=1316"
