# Argus GCS

Web-based MAVLink ground control station. ArduPilot only (PX4 unwired — see below).

## Build & Test

```bash
npm install && pip install -e .        # deps
python run.py --sim                    # backend + simulator
npm run dev                            # frontend dev server :5173

npx svelte-check --tsconfig ./tsconfig.json   # 0 errors 0 warnings
npx vitest run                                # frontend tests
python -m pytest tests/test_unit_*.py tests/test_contract_*.py  # backend tests
ruff check backend/ scripts/ tests/           # Python lint
```

## Commit Convention

`<type>: <imperative description>` — types: feat / fix / refactor / test / docs / ci / chore

## Protocol Code Discipline

FC-coupled code (MAVLink commands, ACKs, field offsets, CRC extras, calibration handshakes, mode IDs, parameter semantics) **must cite the ArduPilot/PX4 source file:line in a code comment**. Do not infer from the MAVLink XML spec alone — FCs hijack generic fields for private protocols.

Workflow: stop guessing → fetch AP source (`raw.githubusercontent.com/ArduPilot/ardupilot/master/...`) → quote the exact condition → implement to match.

Examples already in the codebase:
- `backend/commands/_setup.py:cmd_cal_accel_next` — AP_AccelCal ACK semantics
- `backend/mavlink_handlers.py:handle_mag_cal_progress` — binary MAG_CAL msgs
- `src/components/params/FailsafeConfigPanel.svelte` — BATT_FS_LOW_ACT values

## PX4 Status

Only ArduPilot is wired end-to-end. The backend reads the `autopilot` byte from HEARTBEAT and surfaces it as `drone.autopilot`, but nothing branches on it. A PX4 vehicle connecting today would show `MODE%d` for all modes, fail calibration handshakes, and misinterpret every command enum. PX4 support is greenfield work — weeks not days.
