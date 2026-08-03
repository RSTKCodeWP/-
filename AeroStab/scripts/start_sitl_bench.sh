#!/usr/bin/env bash
# Start mock MAVLink FC + AeroStab for bench / CI (no ArduPilot build required).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${AEROSTAB_SITL_PORT:-5760}"
SECONDS="${AEROSTAB_SITL_SECONDS:-0}"

cd "$ROOT"

cleanup() {
  [[ -n "${FC_PID:-}" ]] && kill "$FC_PID" 2>/dev/null || true
  [[ -n "${AS_PID:-}" ]] && kill "$AS_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

python3 - <<PY &
import time
from aerostab.sitl.mock_fc import MockFlightController
fc = MockFlightController(port=${PORT})
fc.start()
fc.wait_client(timeout_s=60.0)
print(f"Mock FC ready on tcp:{PORT}", flush=True)
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    fc.stop()
PY
FC_PID=$!
sleep 0.5

export AEROSTAB_CONFIG="$ROOT/config/sitl-bench.yaml"
if [[ "$SECONDS" -gt 0 ]]; then
  python3 -m aerostab --simulate -c "$AEROSTAB_CONFIG" &
  AS_PID=$!
  sleep "$SECONDS"
  echo "Bench run finished (${SECONDS}s)"
else
  echo "Mock FC PID=$FC_PID — starting AeroStab (Ctrl+C to stop)"
  exec python3 -m aerostab --simulate -c "$AEROSTAB_CONFIG"
fi
