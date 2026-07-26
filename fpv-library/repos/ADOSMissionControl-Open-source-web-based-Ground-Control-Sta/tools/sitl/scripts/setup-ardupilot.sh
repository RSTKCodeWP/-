#!/bin/bash
# setup-ardupilot.sh - Clone and build ArduPilot SITL on macOS
# SPDX-License-Identifier: GPL-3.0-only

ARDUPILOT_HOME="${ARDUPILOT_HOME:-$HOME/.ardupilot}"

echo "=== Altnautica SITL - ArduPilot Setup ==="
echo ""

# Check prerequisites
for cmd in python3 pip3 git; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: $cmd is required but not found. Install it first."
    exit 1
  fi
done

if [ -d "$ARDUPILOT_HOME" ]; then
  echo "ArduPilot already exists at $ARDUPILOT_HOME"
  echo ""
  echo "To rebuild:  cd $ARDUPILOT_HOME && ./waf copter"
  echo "To update:   cd $ARDUPILOT_HOME && git pull && git submodule update --init --recursive && ./waf copter"
  echo ""
  if [ -f "$ARDUPILOT_HOME/build/sitl/bin/arducopter" ]; then
    echo "ArduCopter SITL binary found. Ready to use."
    exit 0
  else
    echo "WARNING: ArduCopter binary not found. Rebuilding..."
    cd "$ARDUPILOT_HOME"
    ./waf configure --board sitl
    ./waf copter
    echo "Done!"
    exit 0
  fi
fi

echo "Cloning ArduPilot to $ARDUPILOT_HOME ..."
echo "(This may take a few minutes - large repo with submodules)"
echo ""
git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git "$ARDUPILOT_HOME"
cd "$ARDUPILOT_HOME"

echo ""
echo "Installing macOS prerequisites..."
echo "(This runs ArduPilot's official install-prereqs-mac.sh)"
echo ""
Tools/environment_install/install-prereqs-mac.sh -y

echo ""
echo "Building ArduCopter SITL..."
./waf configure --board sitl
./waf copter

echo ""
echo "=== Setup Complete ==="
echo ""
echo "ArduPilot SITL built at: $ARDUPILOT_HOME"
echo "ArduCopter binary:       $ARDUPILOT_HOME/build/sitl/bin/arducopter"
echo ""
echo "Add to your shell profile:"
echo "  export ARDUPILOT_HOME=$ARDUPILOT_HOME"
echo ""
echo "Run the simulator:"
echo "  cd tools/sitl && npx tsx src/index.ts"
