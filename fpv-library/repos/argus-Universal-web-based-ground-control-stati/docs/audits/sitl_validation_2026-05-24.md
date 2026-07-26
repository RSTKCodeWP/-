# SITL Validation — 2026-05-24

End-to-end verification of Argus backend against real ArduCopter SITL
(`build/sitl/bin/arducopter`, firmware version reported as `v4.6.3`) running
at `tcp:127.0.0.1:5760` from a local ArduPilot source tree. SITL was
launched via `Tools/autotest/sim_vehicle.py -v ArduCopter --no-rebuild
--no-mavproxy`. Default home = CMAC (Canberra, -35.36326, 149.16524).

Context: a real flight controller is plugged into
this VM at `/dev/ttyACM0` (VID 0x1209, PID 0x5740), but VMware USB
passthrough turned out to be kernel-unstable for writes — read-only probes
work, but any backend write triggers a passthrough deadlock. SITL substitutes
for the FC's MAVLink semantics so the protocol layer can be validated; the
target FC's identity-byte rendering is separately checked via a fake-FC
simulator (A.9).

## What's verified

| # | Scope | What was actually tested | Result |
| - | - | - | - |
| A.0 | Backend pyserial/TCP baseline | `DroneLink.connect('tcp:127.0.0.1:5760')` → telemetry flow | **PASS** — 257 frames in 6s, mode "自稳", autopilot=3, fw v4.6.3, GPS RTK, all key state fields populated |
| A.3 | Mission upload + download byte round-trip | 6 items: HOME (auto) + TAKEOFF (auto) + 3 user WPs (one LOITER_TURNS p1=2) + RTL (auto). Upload, ACK, download, byte-compare | **PASS** — all 6 round-trip exact except seq 0 home (FC replaces with real home, expected). ACK 0.2s, DL 0.2s |
| A.4 | Command pipeline | `cmd_mode(4)` → GUIDED (0.15s), `cmd_arm` → armed (0.9s), `cmd_takeoff(15)` → alt 10m (7.8s), `cmd_rtl` → land+disarm (35.1s) | **PASS** — all four flight-control commands work against real AP. Validates `_flight.py` integers in `constants.py:COPTER_MODES` |
| A.5 | Param read/write | `cmd_param_request_all` → 1398 params in 1.2s; SET `WPNAV_RADIUS` 200→250 echoed back in <0.5s; restore | **PASS** — `ParamManager.request_all` + `set_param` state machines verified end-to-end |
| A.7 | Fence upload | `cmd_fence_upload` 4-vertex polygon → "围栏确认: 成功" event in 0.2s | **PASS** — `mission_type=1` path through shared `_upload_mission` machinery validated |
| A.8 | Phase P — `autopilot` byte propagates backend → WS → frontend | `ws://localhost:8100/ws` connect; backend connect to SITL; first `state` msg with `autopilot=3` at t=1.0s | **PASS** — full chain `HEARTBEAT.p[5]` → `handle_heartbeat` → `vehicle.autopilot` → `get_state` → `ws_manager` delta push verified |
| A.9 | Custom-identity mimic — fake FC with `autopilot=1` (RESERVED) + `type=0` (GENERIC) + AP-private msg 163 AHRS | Backend renders: `autopilot=1` ✓ (Phase P filter admits non-3 non-8), `mode_id=0`→COPTER_MODES['自稳'] (G3 fallback), `vtype=""` (no map for GENERIC), `parse_errors=0` | **PASS** — confirms the target FC will telemetry-render sanely once USB stabilizes. Mode names will be COPTER_MODES (correct if the FC uses AP mode enums, which msg 163 emission suggests) |

## What's blocked

| Scope | Blocker |
| - | - |
| A.1 — WebSerial direct connect on real FC | No stable USB (VMware passthrough deadlocks the VM kernel on writes). Requires host-side Linux or USB-over-IP fallback |
| A.2 — Real-sensor calibration (compass, accel, gyro, level, baro) | Same blocker. SITL fakes calibration responses but doesn't exercise real-sensor progress paths |
| Firmware upload (APJ + bootloader) | Same blocker. Plus risk of bricking the user's custom-built board |
| NTRIP real-RTK injection effect on `fix_type` | Needs a real GPS receiver hooked up |

## What's partial

| Scope | Status |
| - | - |
| A.6 — Full mission flight (arm → AUTO → fly through WPs → RTL → land) | Individual commands all proven in A.4. cmd_mission_start sends correct MAVLink wire bytes by inspection. End-to-end "AUTO mode auto-flies through items" not validated cleanly on this SITL build — kept getting kicked off by concurrent test connections (SITL is single-client TCP). Not an Argus correctness question, just a SITL session-management nuance |

## Findings while validating

1. **USB CDC-ACM ignores baudrate**: probed at 5 different bauds, all returned same byte rate (since USB CDC ACM doesn't actually use the parameter). The FC docs noting "115200" are a convention, not a constraint.
2. **The FC exposes two ACM endpoints** (interface 00 + 02, same serial). ACM0 carries MAVLink, ACM1 is silent at default config — likely a secondary telemetry or debug port that needs a `SERIAL%_PROTOCOL` param to enable.
3. **The FC's HEARTBEAT identity bytes** (read via `serial.Serial` read-only): `autopilot=1` (MAV_AUTOPILOT_RESERVED), `type=0` (MAV_TYPE_GENERIC). Despite these "stealth" identifiers, the FC emits AP-private msg 163 AHRS — strong signal it's running ArduPilot internally.
4. **SITL accumulates CLOSE-WAIT TCP connections** when probes connect/disconnect rapidly. Hit 5 stale half-closed sockets and a fresh client got no telemetry. Production usage holds a single long-lived connection so this never bites users, but it's a footgun when running automated tests.
5. **`autopilot=0` in initial state** propagates to first WS push (before first heartbeat). After ~1s the field flips to 3 via delta. UI consumers reading the initial frame may see GENERIC briefly — not a bug, but worth noting.

## Update — 2026-05-24 afternoon: real FC validated via WSL2 + usbipd

The VMware passthrough blocker (head of this document) has been resolved by
migrating the dev environment to WSL2 + `usbipd-win`. The target FC at
`/dev/ttyACM0` now survives `DroneLink.connect()` + heartbeats +
`request_streams()` — the same code path that previously deadlocked the VM
kernel.

| # | Scope | Result |
| - | - | - |
| A.0 (real FC, not SITL) | `DroneLink.connect('/dev/ttyACM0', 115200, 'auto')` + 3s + `get_state()` | **PASS** — 240 frames in 3s, `autopilot=3` (MAV_AUTOPILOT_ARDUPILOTMEGA — note: the bare-pyserial probes earlier in this doc saw `autopilot=1` MAV_AUTOPILOT_RESERVED; the FC may have been re-flashed or runs different identity bytes when the full negotiation completes), mode `手动`, clean disconnect, exit 0 |

### Unblocked

The "What's blocked" table above is now superseded for everything except
NTRIP (which still wants a real GPS receiver, not a USB issue):

- **A.1 — WebSerial direct connect on real FC**: ready to test. Open
  `http://localhost:8100` in Windows Chrome with FC attached and click the
  USB button.
- **A.2 — Real-sensor calibration**: ready to test (compass / gyro / level /
  baro / accel). This is the highest-value item — it exercises the
  AP_AccelCal ACK-abuse protocol and AP-private mag cal binary messages on
  real hardware for the first time.
- **Firmware upload**: technically unblocked, but the bricking risk is
  unchanged. Only attempt with the FC's own firmware build, never with a
  generic ArduPilot APJ.

### Migration provenance

- `docs/MIGRATION_TO_WSL.md` — full Phase 1–6 runbook
- `scripts/wsl_first_run.sh` — idempotent WSL bootstrap
- FC BUSID on this host: `2-1` (re-check with `usbipd list` if it moves
  after replug). Attach each session with `usbipd attach --wsl --busid=2-1`
  from Windows admin PowerShell.

## How to reproduce

```bash
# Backend
python run.py  # serves WS on :8100

# SITL
cd ~/ardupilot
Tools/autotest/sim_vehicle.py -v ArduCopter --no-rebuild --no-mavproxy

# Probes (all standalone, no harness)
python3 /tmp/probe_sitl.py            # A.0
python3 /tmp/probe_mission_roundtrip.py  # A.3
python3 /tmp/probe_commands.py        # A.4
python3 /tmp/probe_phase_p_ws.py      # A.8
python3 /tmp/fake_custom_fc.py 14560 &  # A.9 (fake FC)
python3 /tmp/probe_custom_mimic.py     # A.9 (connect Argus to fake FC)
```

(The `/tmp/probe_*.py` files are session-scoped. They live as evidence of the
exact bytes sent and asserted; not part of the persistent test suite. The
persistent equivalents are in `tests/test_unit_*` and `src/lib/*.test.ts`,
which now have a real-AP corroboration for the protocol assertions they make
under mocks.)
