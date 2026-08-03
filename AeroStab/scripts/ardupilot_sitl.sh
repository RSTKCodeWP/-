#!/usr/bin/env bash
# Build and run ArduPilot SITL (ArduCopter) for full-stack testing.
# Note: ArduPilot prereqs target Ubuntu 22.04; on newer releases use mock FC instead:
#   python3 scripts/sitl_hil.py
set -euo pipefail

ARDUPILOT_DIR="${ARDUPILOT_DIR:-/tmp/ardupilot}"
VEHICLE="${ARDUPILOT_VEHICLE:-ArduCopter}"
PORT="${AEROSTAB_SITL_PORT:-5760}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ ! -d "$ARDUPILOT_DIR" ]]; then
  echo "Cloning ArduPilot (shallow)..."
  git clone --depth 1 --branch Copter-4.5.7 https://github.com/ArduPilot/ardupilot.git "$ARDUPILOT_DIR"
fi

cd "$ARDUPILOT_DIR"

if [[ ! -f build/sitl/bin/arducopter ]]; then
  echo "Installing ArduPilot prerequisites (may take several minutes)..."
  Tools/environment_install/install-prereqs-ubuntu.sh -y
  ./waf configure --board sitl
  ./waf copter
fi

echo "Starting ArduPilot SITL on TCP $PORT..."
# Serial0 → TCP for companion computer link (AeroStab)
./Tools/autotest/sim_vehicle.py \
  -v "$VEHICLE" \
  --no-mavproxy \
  --aircraft AeroStabTest \
  -A "--serial1=tcp:0.0.0.0:${PORT}" \
  --out "tcp:127.0.0.1:5762" &
SITL_PID=$!

cleanup() {
  kill "$SITL_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Waiting for SITL..."
sleep 8

export AEROSTAB_CONFIG="$ROOT/config/sitl.yaml"
python3 "$ROOT/scripts/sitl_hil.py" -c "$AEROSTAB_CONFIG" --port "$PORT" --seconds 10
