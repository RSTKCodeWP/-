#!/usr/bin/env bash
# Starts the HackRF multi-band monitor (VTX 5 GHz + 2.4/900 MHz ELRS) in the
# background and opens the dashboard. The HackRF can only be used by one process
# at a time, so this first stops any running sweep.
#
#   ./start_monitor.sh            # on :8080
#   ./start_monitor.sh 9000       # custom port
#
# macOS/Linux counterpart of start_monitor.ps1. Uses the project venv if present
# (./.venv), else the python3 on PATH.
set -euo pipefail

PORT="${1:-8080}"
PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Prefer the project virtualenv's python if it exists.
if [ -x "$PROJ/.venv/bin/python" ]; then
  PY="$PROJ/.venv/bin/python"
else
  PY="$(command -v python3 || command -v python)"
fi

# Make sure Homebrew's hackrf tools are reachable (no-op if already on PATH).
if command -v brew >/dev/null 2>&1; then
  eval "$(brew shellenv)"
fi

# The radio is single-user: stop any lingering sweep first.
pkill -f hackrf_sweep 2>/dev/null || true
sleep 0.4

cd "$PROJ"
nohup "$PY" -m hackrf_api webapp --port "$PORT" >/tmp/hackrf_monitor.log 2>&1 &
echo $! > "$PROJ/.monitor.pid"
sleep 3

URL="http://localhost:$PORT/"
if command -v open >/dev/null 2>&1; then open "$URL"          # macOS
elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" # Linux
fi

echo "Multi-band monitor started (pid $(cat "$PROJ/.monitor.pid")) -> $URL"
echo "Quick checks:  python -m hackrf_api vtx   |   python -m hackrf_api elrs"
echo "Logs:          tail -f /tmp/hackrf_monitor.log"
echo "Stop:          kill \$(cat .monitor.pid)"
