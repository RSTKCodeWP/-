#!/usr/bin/env bash
# Backend for the "HackRF Monitor" desktop app icon.
# (Re)starts the monitor — killing any running instance first — then opens the
# dashboard in the browser.
# Shares the radio with nothing: any hackrf_sweep is stopped before starting.
set -uo pipefail

PORT="${1:-8080}"
PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -x "$PROJ/.venv/bin/python" ]; then
  PY="$PROJ/.venv/bin/python"
else
  PY="$(command -v python3 || command -v python)"
fi

# GUI apps get a bare PATH (/usr/bin:/bin:...), so add Homebrew explicitly —
# the webapp needs hackrf_sweep and friends on PATH.
for BREW in /opt/homebrew/bin/brew /usr/local/bin/brew; do
  if [ -x "$BREW" ]; then
    eval "$("$BREW" shellenv)"
    break
  fi
done

pkill -f "hackrf_api webapp" 2>/dev/null
pkill -f hackrf_sweep 2>/dev/null
sleep 1

cd "$PROJ"
nohup "$PY" -m hackrf_api webapp --port "$PORT" >/tmp/hackrf_monitor.log 2>&1 &
echo $! > "$PROJ/.monitor.pid"

# Wait until the web app answers (up to ~10 s) so failures are caught here.
URL="http://localhost:$PORT/"
for _ in $(seq 1 20); do
  if curl -s -o /dev/null --max-time 1 "$URL"; then
    open "$URL"
    exit 0
  fi
  sleep 0.5
done

echo "Monitor did not come up on $URL — see /tmp/hackrf_monitor.log" >&2
exit 1
