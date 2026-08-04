#!/bin/sh

chmod +x ./tools/mediamtx
./tools/mediamtx ./tools/mediamtx.yml &
ffmpeg -f fbdev -framerate 25 -i /dev/fb0 \
  -vf "format=yuv420p" \
  -c:v libx264 -preset ultrafast -tune zerolatency \
  -x264-params "keyint=25:min-keyint=25:scenecut=0:rc-lookahead=0" \
  -b:v 900k -maxrate 900k -bufsize 900k -g 25 -bf 0 \
  -fflags nobuffer -flags low_delay -flush_packets 1 -muxdelay 0 -muxpreload 0 \
  -f rtsp -rtsp_transport udp rtsp://127.0.0.1:8554/fb0 &


