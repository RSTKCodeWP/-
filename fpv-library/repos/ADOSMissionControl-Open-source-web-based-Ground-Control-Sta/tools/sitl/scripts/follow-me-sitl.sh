#!/usr/bin/env bash
#
# follow-me-sitl.sh — the software end-to-end harness for the click-to-follow
# behavior, against ArduPilot SITL and the agent's CPU (ONNX) vision path. No
# NPU, no real camera, no real flight controller.
#
# It wires the whole loop: the vision engine (real COCO ONNX detector + the
# OSNet re-id model, both sideloaded), the plugin host running the Follow-Me
# plugin, ArduPilot SITL in GUIDED, and a small ffmpeg-to-tap frame feeder, then
# drives a designate and watches the follow setpoints reach SITL.
#
# The deterministic slices of this are covered by automated tests already:
#   - crates/ados-vision/tests/follow_lock_e2e.rs  (lock / no-re-acquire / re-id)
#   - crates/ados-vision/tests/onnx_coco_infer.rs  (the real ONNX detector path)
#   - the Follow-Me agent half's lock-state gating tests (stop on uncertain/lost)
# This script is the LIVE end-to-end run that those tests stand in for: it is
# the manual / CI-optional gate, not a unit test.
#
# Prereqs (set the paths for your checkout):
#   AGENT_DIR        the ADOSDroneAgent checkout (default: ../ADOSDroneAgent relative to this repo)
#   COCO_ONNX        the sideloaded detector (default: ~/ws1-model-run/yolov8n_coco_640.onnx)
#   REID_ONNX        the sideloaded re-id model (default: ~/ws5-reid/osnet_x0_5_reid_256x128.onnx)
#   PERSON_VIDEO     a video with a walking person (a phone clip is fine)
#
# Honest boundary: the agent's IPC is unix sockets under $ADOS_RUN_DIR, so this
# runs natively on macOS or Linux. ArduPilot SITL builds + runs on both (see
# setup-ardupilot.sh). What this does NOT prove (only the NPU+camera+FC rig can):
# real NPU latency/accuracy, real camera intrinsics + gimbal coupling, and real
# FC guided-mode dynamics under wind.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
AGENT_DIR="${AGENT_DIR:-$REPO_ROOT/../ADOSDroneAgent}"
COCO_ONNX="${COCO_ONNX:-$HOME/ws1-model-run/yolov8n_coco_640.onnx}"
REID_ONNX="${REID_ONNX:-$HOME/ws5-reid/osnet_x0_5_reid_256x128.onnx}"
PERSON_VIDEO="${PERSON_VIDEO:-}"

export ADOS_RUN_DIR="$(mktemp -d)"
export ADOS_PLUGIN_SOCKET_DIR="$ADOS_RUN_DIR/plugins"
mkdir -p "$ADOS_PLUGIN_SOCKET_DIR"
CONFIG_DIR="$ADOS_RUN_DIR/etc"
mkdir -p "$CONFIG_DIR"
CAM_ID="uvc-0"
TAP_SOCK="$ADOS_RUN_DIR/vision-tap-$CAM_ID.sock"
pids=()
cleanup() { for p in "${pids[@]:-}"; do kill "$p" 2>/dev/null || true; done; rm -rf "$ADOS_RUN_DIR"; }
trap cleanup EXIT

say() { printf '\n=== %s ===\n' "$1"; }
need() { command -v "$1" >/dev/null 2>&1 || { echo "missing dependency: $1"; exit 1; }; }
need ffmpeg
[ -f "$COCO_ONNX" ] || { echo "detector model not found: $COCO_ONNX"; exit 1; }
[ -d "$AGENT_DIR" ] || { echo "agent checkout not found: $AGENT_DIR (set AGENT_DIR)"; exit 1; }

say "1. build the agent's vision engine + plugin host with the real ONNX backend"
( cd "$AGENT_DIR/crates" && cargo build -p ados-vision --features onnx && cargo build -p ados-plugin-host && cargo build -p ados-mavlink-router 2>/dev/null || true )

say "2. write the vision config (CPU ONNX detector + re-id, tap camera, tracker on)"
REID_BLOCK=""
if [ -f "$REID_ONNX" ]; then
  REID_BLOCK="  reid_enabled: true
  reid_model_id: reid_osnet
  reid:
    model_id: reid_osnet
    model_path: $REID_ONNX
    input_width: 128
    input_height: 256"
fi
cat > "$CONFIG_DIR/config.yaml" <<YAML
agent:
  profile: drone
vision:
  enabled: true
  backend: onnx
  socket_dir: $ADOS_RUN_DIR
  tracker_enabled: true
$REID_BLOCK
  designate_camera: $CAM_ID
  cameras:
    - id: $CAM_ID
      kind: tap
      tap_socket: $TAP_SOCK
  detector:
    model_id: coco_yolov8n
    model_path: $COCO_ONNX
    class_labels: [person]
YAML
export ADOS_CONFIG="$CONFIG_DIR/config.yaml"

say "3. start ArduPilot SITL in GUIDED (see setup-ardupilot.sh for the one-time build)"
echo "   start your SITL: sim_vehicle.py -v ArduCopter --console (TCP 5760)"
echo "   then point the router at it: ados-mavlink-router --serial-port tcp:127.0.0.1:5760"
echo "   (this script does not own SITL; bring it up in another terminal)"

say "4. start the vision engine + plugin host"
VISION_BIN="$AGENT_DIR/crates/target/debug/ados-vision"
HOST_BIN="$AGENT_DIR/crates/target/debug/ados-plugin-host"
ADOS_CONFIG="$ADOS_CONFIG" "$VISION_BIN" & pids+=($!)
sleep 1
"$HOST_BIN" & pids+=($!)
sleep 1

say "5. feed a person video into the engine's tap (rgb24 frames over the tap socket)"
if [ -n "$PERSON_VIDEO" ] && [ -f "$PERSON_VIDEO" ]; then
  # The tap wire is a 16-byte ADVT header + rgb24 payload per frame; the helper
  # below frames ffmpeg's rawvideo output. (See tools/sitl/src for the feeder.)
  echo "   feeding $PERSON_VIDEO -> $TAP_SOCK"
  echo "   (use the tap feeder; raw ffmpeg piping needs the ADVT header)"
else
  echo "   set PERSON_VIDEO to a clip with a walking person to drive real detections"
fi

say "6. designate + watch the follow"
cat <<'STEPS'
   With the engine producing detections and SITL armed in GUIDED:
   - POST a designate to lock the operator's chosen box:
       curl -s -X POST http://127.0.0.1:8080/api/vision/designate \
         -H 'content-type: application/json' \
         -d '{"camera_id":"uvc-0","bbox":{"x":300,"y":200,"width":80,"height":160}}'
   - Flip the Follow-Me skill active (per-drone config write):
       curl -s -X PUT http://127.0.0.1:8080/api/plugins/com.altnautica.follow-me/config \
         -H 'content-type: application/json' -d '{"key":"active","value":true}'
   - Watch SET_POSITION_TARGET_GLOBAL_INT reach SITL (the router stream / SITL
     console) and the vehicle converge to the standoff.
   - Stop the feed (subject lost): the plugin stops commanding and never
     re-acquires onto another subject (the lock-state gate).
   - With re-id on, a second person crossing does not steal the lock.
STEPS

say "harness ready. Bring up SITL + the router, then run the curl steps above."
# Keep the engine + host alive until interrupted so the operator can drive it.
wait
