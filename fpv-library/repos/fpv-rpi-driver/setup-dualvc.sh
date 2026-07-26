#!/bin/bash
# setup-dualvc.sh - configure the rp1-cfe media pipeline for the canlab
# dual virtual-channel camera.
#
# Usage:
#   ./setup-dualvc.sh <mode>
#   ./setup-dualvc.sh          (prompts interactively if no mode given)
#
# Modes (VC0 is always 1920x1080):
#   vga    VC1 640x480    (default canlab-downstream overlay)
#   qvga   VC1 320x240    (dtoverlay=canlab-downstream,qvga)
set -e

MODE="$1"

if [ -z "$MODE" ]; then
    echo "Select VC1 mode:"
    echo "  1) vga   (640x480)"
    echo "  2) qvga  (320x240)"
    read -rp "Enter 1/2 or vga/qvga: " CHOICE
    case "$CHOICE" in
        1|vga)  MODE="vga"  ;;
        2|qvga) MODE="qvga" ;;
        *) echo "Invalid selection: $CHOICE"; exit 1 ;;
    esac
fi

case "$MODE" in
    vga)  VC1_W=640;  VC1_H=480  ;;
    qvga) VC1_W=320;  VC1_H=240  ;;
    *)
        echo "Unknown mode: $MODE (expected vga | qvga)"
        exit 1
        ;;
esac

echo "mode: $MODE (VC0 1920x1080, VC1 ${VC1_W}x${VC1_H})"

MDEV=""
for m in /dev/media*; do
    if media-ctl -d "$m" -p 2>/dev/null | grep -q "model *rp1-cfe"; then
        MDEV=$m
        break
    fi
done

if [ -z "$MDEV" ]; then
    echo "rp1-cfe media device not found"
    exit 1
fi
echo "rp1-cfe: $MDEV"

CAMSD=$(media-ctl -d "$MDEV" -p | grep -oE "canlab [0-9]+-001a" | head -1)
if [ -z "$CAMSD" ]; then
    echo "canlab subdev not found"
    exit 1
fi
echo "sensor: $CAMSD"

# Enable raw CSI-2 capture nodes:
# csi2 pad4 -> /dev/video0 (VC0)
# csi2 pad6 -> /dev/video2 (VC1)
media-ctl -d "$MDEV" -l "'csi2':4 -> 'rp1-cfe-csi2_ch0':0 [1]"
media-ctl -d "$MDEV" -l "'csi2':6 -> 'rp1-cfe-csi2_ch2':0 [1]"

media-ctl -d "$MDEV" -V "'$CAMSD':0 [fmt:UYVY8_1X16/1920x1080 field:none]"
media-ctl -d "$MDEV" -V "'$CAMSD':2 [fmt:UYVY8_1X16/${VC1_W}x${VC1_H} field:none]"
media-ctl -d "$MDEV" -V "'csi2':0 [fmt:UYVY8_1X16/1920x1080 field:none]"
media-ctl -d "$MDEV" -V "'csi2':2 [fmt:UYVY8_1X16/${VC1_W}x${VC1_H} field:none]"
media-ctl -d "$MDEV" -V "'csi2':4 [fmt:UYVY8_1X16/1920x1080 field:none]"
media-ctl -d "$MDEV" -V "'csi2':6 [fmt:UYVY8_1X16/${VC1_W}x${VC1_H} field:none]"

# embedded/filler pad mirrors VC0 so link_validate passes
media-ctl -d "$MDEV" -V "'csi2':1 [fmt:UYVY8_1X16/1920x1080 field:none]"

v4l2-ctl -d /dev/video0 \
  --set-fmt-video=width=1920,height=1080,pixelformat=UYVY

v4l2-ctl -d /dev/video2 \
  --set-fmt-video=width=${VC1_W},height=${VC1_H},pixelformat=UYVY

echo "done"
