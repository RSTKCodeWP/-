#!/usr/bin/env bash
# Triple verification: unit → integration → E2E (SITL), then combined pass.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== Tier 1: Unit tests ==="
python3 -m pytest -q tests/

echo "=== Tier 2: Integration tests ==="
python3 -m pytest -q tests/test_mavlink_integration.py tests/test_flight_path.py

echo "=== Tier 3: E2E (SITL + self-check) ==="
python3 scripts/selfcheck.py --simulate
python3 scripts/sitl_hil.py --seconds 5
python3 scripts/sitl_scenarios.py
python3 scripts/simulate.py

echo "=== Triple verification PASS ==="
