# Argus GCS — Remaining-Module Audit (2026-05-23)

Scope: scripts/sim_pllink.py, scripts/build_package.py, scripts/build_desktop.sh,
run.py, tests/test_integration.py, backend/app.py routes not previously
audited, plus a test-coverage gap survey.

Result summary (original 2026-05-23; updated 2026-05-24)
- 6 critical findings: **all fixed** (C1–C6)
- 9 medium findings: **all fixed** (M4/M7/M9 fixed 2026-05-24; M8 fixed shortly after audit)
- Low/info: L2/L4/L5 fixed 2026-05-24; L1/L3 remain documented; L6/L7 info/by-design, no action needed
- Gap A/B/C: **all fixed** (unit tests added 2026-05-24)
- Integration tests: 20/52 → 52/52 (xfail removed 2026-05-24) + `test_connect_with_pllink_protocol` = **53 defined**
- Unit + contract tests: **1043 / 1043 passing**

----------------------------------------------------------------------
## 1. scripts/sim_pllink.py — Simulator deviations from real ArduPilot

The simulator was the **single biggest source of misleading behavior in the
codebase** — five separate wire-protocol deviations meant the sim and backend
agreed on a wrong format, hiding production bugs that would manifest on real
hardware. All five are now fixed.

### C1 [CRITICAL — FIXED] sim sent EKF_STATUS_REPORT under VFR_HUD msg id (74)
- `msg_ekf_status` packed 5 floats + uint16 (EKF variances) and sent with
  `msg_id=74`. msg id 74 is **VFR_HUD**, not **EKF_STATUS_REPORT (193)**.
- Effect on backend: `handle_vfr_hud` ran on EKF bytes, so the telemetry
  overlay showed `airspeed≈0.02`, `climb≈0.01` (actually `vel_var`,
  `compass_var`). The real EKF handler at msg 193 **never ran** — the EKF
  panel showed zeros even though sim was "sending EKF data". Hidden by the
  PL-Link framing layer which doesn't validate inner CRC.
- Fix: changed to `bm(193, …)`, added a separate `msg_vfr_hud` that emits
  real VFR_HUD (airspeed/groundspeed/alt/climb/heading/throttle) and wired
  it into the broadcast loop.
- File: `scripts/sim_pllink.py:303-322` (msg_ekf_status, new msg_vfr_hud),
  `:746` (broadcast loop).

### C2 [CRITICAL — FIXED] sim only supported PL-Link framing; TCP+auto connections fail
- The backend's `connect()` forces `protocol='standard'` for TCP+auto (commit
  b662e7a). The sim only emitted PL-Link XOR-wrapped frames, so any GCS
  connecting via `tcp:host:port` with the default protocol saw no parseable
  frames at all.
- Effect: 32+ integration tests failed with `TimeoutError: predicate not met
  within 8s` — they never saw `connected=True` because heartbeat frames were
  ignored by the standard-MAVLink parser.
- Fix: sim now auto-detects the client's protocol (0x50/0x4C → PL-Link,
  0xFD → standard) and replies in the matching dialect. Single sim binary
  now works for both connection modes.
- File: `scripts/sim_pllink.py:702-746` (serve loop, protocol detection +
  conditional tx wrapping).

### C3 [CRITICAL — FIXED] sim's `mid == 126` for log cancel; real msg id is 122
- (Pre-existing finding noted in CLAUDE.md, but the comment said it was
  fixed — the code itself still had `mid == 126`.)
- Sim listened for `mid == 126` (SERIAL_CONTROL) as "cancel log download";
  the real cancel is **LOG_REQUEST_END = 122** and that's what the backend
  sends in `cmd_log_cancel` (`backend/commands/_setup.py:155`).
- Effect: log-download cancel was silently ignored by the sim, leaving the
  sim spamming LOG_DATA after the GCS told it to stop.
- Fix: `elif mid == 122:` plus comment explaining the msg-id rationale.
- File: `scripts/sim_pllink.py:497-503`.

### C4 [CRITICAL — FIXED] AUTOPILOT_VERSION wire layout was wrong (firmware showed v0.0.0)
- `msg_autopilot_version` placed `flight_sw_version` at byte 8 (the UID
  slot per MAVLink 2 size-sorted wire layout). The backend's
  `handle_autopilot_version` correctly reads `fw_ver = struct.unpack_from('<I',
  p, 16)` (the real position) so it saw `0` → reported `v0.0.0` in sim mode.
- Same issue for the git hash (offset 36 in real wire) and board_version
  (offset 28). All three came out as zero/garbage.
- Fix: rewrote the packer to follow the real wire layout (capabilities Q@0,
  uid Q@8, flight_sw I@16, middleware I@20, os_sw I@24, board I@28, vendor
  H@32, product H@34, three 8-byte custom_versions @36/44/52).
- File: `scripts/sim_pllink.py:360-376`.

### C5 [CRITICAL — FIXED] RC_CHANNELS layout off by one byte
- Sim packed `<IB`+18×H+B putting `chancount` at byte 4 and shifting all 18
  channels one byte right. The backend correctly reads chan1 at offset 4 (real
  wire layout: time(4)+18×chan(36)+chancount(1)+rssi(1)). On the sim the
  backend got `(chancount<<8 | chan1_lo)` ≈ junk values.
- Effect: RC panel showed bogus channel values in sim mode (correct on real
  hardware).
- Fix: packed `<I` + 18×H + `<BB` (chancount, rssi) per real wire order.
- File: `scripts/sim_pllink.py:265-282`.

### M1 [MEDIUM — FIXED] WIND msg crc_extra wrong (231, should be 1)
- `msg_wind` used `bm(168, p, sq, 231)`. Real WIND crc_extra is 1.
- Effect on PL-Link: silent — the inner CRC isn't validated by the XOR
  wrapper. Effect on raw-MAVLink path (now reachable thanks to C2 fix):
  the wind frame would fail CRC check and increment `_parse_errors`.
- Fix: `bm(168, p, sq, 1)`.
- File: `scripts/sim_pllink.py:319`.

### M2 [MEDIUM — FIXED] msg_terrain_report referenced undefined `self.alt_rel`
- `msg_terrain_report` referenced `self.alt_rel`; the simulator only defines
  `self.alt`. The method was never called by the broadcast loop so it didn't
  crash, but anyone wiring it in (or unit-testing it) would get AttributeError.
- Fix: changed to `self.alt`.
- File: `scripts/sim_pllink.py:319-326`.

### Notes (verified OK)
- SERVO_OUTPUT_RAW: sim and backend both use time_usec as uint32 at offset 0
  (real ArduPilot uses uint32 too — pymavlink confirms `<IHHHHHHHHB` then
  extension 8H). Sim layout matches real wire. ✓
- GPS_RAW_INT, ATTITUDE, GLOBAL_POSITION_INT, SYS_STATUS, VIBRATION,
  HOME_POSITION, MISSION_*, PARAM_*, STATUSTEXT, COMMAND_ACK, COMMAND_LONG:
  all match real wire layout and msg id / crc_extra. ✓

----------------------------------------------------------------------
## 2. scripts/build_package.py — Windows packaging

### C6 [CRITICAL — FIXED] `glob('*.py')` only copies top-level backend files; misses commands/ subpackage
- Original: `for f in (SCRIPT_DIR / 'backend').glob('*.py')`. This pattern
  doesn't recurse — every file in `backend/commands/` (the entire command
  dispatch tree) was excluded from the .zip. The packaged backend would
  raise `ImportError: No module named backend.commands` at startup.
- Fix: switched to `shutil.copytree('backend', be_dst, ignore=...)` so all
  subpackages are included.
- File: `scripts/build_package.py:107-121`.

### M3 [MEDIUM — FIXED] sim_pllink.py path wrong (looked in repo root, not scripts/)
- Original: `sim_src = SCRIPT_DIR / 'sim_pllink.py'`. The file lives at
  `scripts/sim_pllink.py`. So `sim_src.exists()` returned False and the
  sim launcher .bat referenced a file that wasn't in the zip — sim wouldn't
  start.
- Fix: `sim_src = SCRIPT_DIR / 'scripts' / 'sim_pllink.py'`.
- File: `scripts/build_package.py:122-128`.

### L1 [LOW — documented] Doesn't validate pip download for ARM64 Windows
- `--platform=win_amd64` is hardcoded. If anyone runs the build on ARM Windows
  it would silently produce a broken zip for the wrong arch. Add an
  `--arch` argparse arg if you need ARM64 support.

### L2 [LOW — FIXED 2026-05-24] PIP_DEPS missing `python-multipart`
- `pyproject.toml` declares `python-multipart>=0.0.9` (needed for FastAPI
  UploadFile). The packager's PIP_DEPS list omits it, so `/api/firmware/upload`
  will return 500 ("Form data requires python-multipart") on the packaged build.
- Fix: added `'python-multipart'` to `PIP_DEPS` in `scripts/build_package.py`.

----------------------------------------------------------------------
## 3. scripts/build_desktop.sh — Tauri desktop build

### M4 [MEDIUM — FIXED 2026-05-24] PyInstaller --hidden-import doesn't include backend.commands._*
- The script listed `--hidden-import backend.commands` but the subpackage
  contains `_flight.py`, `_mission.py`, `_setup.py`, `_hardware.py`,
  `_helpers.py`. PyInstaller would not automatically pick those up because
  they're imported dynamically via `commands/__init__.py`.
- Risk: built executable may run until the first non-helper command is
  invoked, then fail with ModuleNotFoundError.
- Fix: replaced the 19 individual `--hidden-import` lines with
  `--collect-submodules backend` and `--collect-submodules uvicorn`.
- File: `scripts/build_desktop.sh`.

### L3 [LOW — documented] No verification of TARGET_TRIPLE against tauri.conf.json
- The script names the binary `python-backend-${TARGET_TRIPLE}`. If
  `tauri.conf.json` lists a different externalBin pattern the Tauri build
  will silently skip embedding the sidecar.

----------------------------------------------------------------------
## 4. run.py — One-click launcher

### M5 [MEDIUM — FIXED] Race condition: blind `time.sleep(1)` before starting backend
- Sim subprocess starts, then `time.sleep(1)` — on slow boxes the backend
  could start (and clients could connect) before the sim socket was bound.
  First connect attempt would fail confusingly.
- Fix: poll for `socket.create_connection(('127.0.0.1', 5770))` with a
  5s deadline, and also check `sim_proc.poll()` so we detect early sim
  exit (e.g. port already in use).
- File: `run.py:35-50`.

### M6 [MEDIUM — FIXED] `sim_proc.wait()` with no timeout could hang on shutdown
- After Ctrl+C, run.py calls `sim_proc.terminate(); sim_proc.wait()` without
  a timeout. If the sim ignores SIGTERM (e.g. blocked in socket recv on
  Windows), this hangs forever and the operator has to kill -9 the launcher.
- Fix: `wait(timeout=5)` then fall back to `kill()`.
- File: `run.py:93-102`.

### L4 [LOW — FIXED 2026-05-24] `--host` defaults to `0.0.0.0`
- Exposes the backend on all interfaces by default. Auth middleware
  mitigates this if a token is configured, but unset-token mode allows any
  device on the LAN to drive the vehicle.
- Fix: changed default to `127.0.0.1`; added help text explaining
  `--host 0.0.0.0` to opt into network exposure.
- File: `run.py` (argparse default + help string).

----------------------------------------------------------------------
## 5. tests/test_integration.py — Failing-test categorization

Originally 32+ failures. After fixes: **51/52 passing, 1 xpassed**.

### Category A: Real production bug (fixed)
1. `TestConfirmCoverage::test_dangerous_commands_guarded` — SchedulerPanel.svelte
   `runNow()` called `sendCommand('mission_start')` without any confirm guard.
   This is a real safety issue: clicking "run now" on a scheduled mission would
   start AUTO mode immediately on an armed vehicle without confirmation.
   **Fix**: added `showConfirm(...)` guard + new locale key `sched.confirmRun`.
   Files: `src/components/planning/SchedulerPanel.svelte:104-115`,
   `src/lib/locales/{zh,en}.ts`.

### Category B: Tests masking the sim bug C2 (fixed by sim, not tests)
   30+ tests timed out waiting for `state.connected=True` because the sim
   couldn't talk to the TCP-default-standard backend. **Fixed by C2** — they
   now all pass without any test changes.

### Category C: Outdated test infrastructure (fixed)
1. `TestCommands::test_arm_disarm` — used `lambda m: not m.get('armed')`
   which matches any state that lacks `armed` (delta-push artefact). Tightened
   predicate to `'armed' in m and m['armed'] is False`.
2. `TestDataStreams::test_rc_channels_in_state` — predicate matched a delta
   that contained `rc` but didn't contain `rc_rssi`. Added `'rc_rssi' in m`.
3. `TestDataStreams::test_vibration_in_state` — same delta-push issue;
   added `'vibe_clip' in m`.
4. `TestVzConvention::test_vz_field_exists` — needed predicate to require
   `'vz' in m` (delta pushes don't include unchanged fields).
5. `TestOnboardLog::test_log_download` — protocol changed to streaming
   chunks (`log_chunk` messages → `log_complete` with no `data`). Test now
   accumulates chunks and validates total size against `done['size']`.
6. `TestVersionApi::test_tile_sources_endpoint` — asserted `'china' in
   data` but tile_sources is `{source_id: {region: 'china'|'global'}}`.
   Rewrote to check the set of `region` values across entries.

### Category D: Pre-existing xfail (FIXED 2026-05-24)
- `test_compass_calibration` was marked `xfail` (sim timing flakiness) but
  had been passing consistently since the C2 sim fix. Decorator removed;
  test now counts as a normal pass.
- File: `tests/test_integration.py`.

----------------------------------------------------------------------
## 6. backend/app.py routes — security & error-handling

(Routes already audited elsewhere: tile/SRTM/firmware download/upload —
generally well-guarded with SSRF, size caps, path-traversal defense.)

### M7 [MEDIUM — FIXED 2026-05-24] /api/tile_bulk_download blocks the event loop
- `urlreq.urlopen(req, timeout=5).read()` was called synchronously from an
  `async` handler. With 5000 tiles at 5s timeout each = up to 7+ hours of
  blocked event loop. Also missing per-tile size cap.
- Fix: wrapped each `urlopen(...).read()` call with `_aio(lambda: ...)`;
  promoted `_TILE_MAX_BYTES = 2 * 1024 * 1024` to module level (shared with
  single-tile endpoint); added per-tile size check; wrapped `write_bytes`
  with `_aio`.
- File: `backend/app.py` (module-level constant + api_tile_bulk_download).

### M8 [MEDIUM — FIXED] /api/mbtiles/{name}/{z}/{x}/{y} traversal guard via `str.startswith` has a subtle hole
- `str(path).startswith(str(MBTILES_DIR.resolve()))` returns True for paths
  inside `/mbtiles` AND for paths inside `/mbtiles2/...` or `/mbtilesx/...`.
- A sibling directory whose name happens to start with the same prefix is
  not prevented. (In practice the file then has to also `.endswith('.mbtiles')`
  and exist — so the practical impact is low — but it's a latent footgun.)
- Fix: switched to `path.relative_to(MBTILES_DIR.resolve())` with
  try/except ValueError, the same pattern used in `/api/firmware/download`.
- File: `backend/app.py` (api_mbtiles_tile).

### M9 [MEDIUM — FIXED 2026-05-24] /api/firmware/upload buffers entire file in memory
- Reads 1MB at a time into a `list[bytes]`, then `b''.join()` doubles peak
  memory. For a 50MB cap that's 100MB transient. On embedded/low-memory
  hosts this can OOM the process.
- Fix: replaced list accumulation with streaming write to a `.apj.tmp`
  sidecar file; on success atomically renames to final path; on
  size-cap violation unlinks the partial `.tmp`. Peak memory: one 1MB
  chunk at a time regardless of firmware size.
- File: `backend/app.py` (api_firmware_upload).

### L5 [LOW — FIXED 2026-05-24] /api/firmware/upload accepts files named just `.apj`
- `Path('.apj').name == '.apj'`, which passes both `endswith('.apj')` and
  `if not file.filename` (since `.apj` is truthy). The resulting filename
  is a hidden dotfile in FIRMWARE_DIR. No security impact (still confined),
  but worth rejecting since it's never a legitimate name.
- Fix: added `if not safe_name[:-4]:` check — strips the 4-char `.apj`
  suffix; empty result means it's a bare dotfile. Covered by new test
  `TestFirmwareUpload::test_dotfile_apj_rejected`.
- File: `backend/app.py` (api_firmware_upload), `tests/test_unit_app_routes.py`.

### L6 [LOW — info] /api/version subprocess git invocation
- `git rev-parse --short HEAD` is shelled out. `cwd=ROOT_DIR` (constant),
  timeout=2s, stderr=DEVNULL. Safe but unnecessarily slow on PyInstaller
  builds (no `.git/`). Already returns `git: ''` on failure. OK.

### L7 [LOW — info] /api/auth/generate is unauthenticated when no token yet exists
- This is by design (bootstrap flow). Acceptable as long as the operator
  is aware they should call this exactly once on first run. Worth noting
  in deployment docs.

----------------------------------------------------------------------
## 7. Test coverage gaps

### Gap A [FIXED 2026-05-24] handle_log_data count=0 path
- `count == 0` triggers `_finalize_log_download(truncated=True)`. Code
  path exists (mavlink_handlers.py:631-633) but no unit test covers it.
- Fix: added `test_count_zero_finalizes_as_truncated` to
  `tests/test_unit_handlers.py::TestLogData`.

### Gap B [FIXED 2026-05-24] handle_log_data out-of-order chunks
- `max(lg._log_download_ofs, end)` prevents rewinding (added by previous
  audit), but no test covers it.
- Fix: added `test_out_of_order_chunk_ofs_stays_at_max` to
  `tests/test_unit_handlers.py::TestLogData`. Sends two chunks out of
  order (ofs=10 first, then ofs=0), verifies both positions written and
  `_log_download_ofs` stays at the higher value.

### Gap C [FIXED 2026-05-24] WSManager dual-protocol sim coverage
- The sim now speaks both PL-Link and raw MAVLink. There's no
  integration test that explicitly forces `protocol='pllink'` on a TCP
  connection — every test uses default `auto` (which falls back to
  standard).
- Fix: added `TestConnection::test_connect_with_pllink_protocol` to
  `tests/test_integration.py`. Connects with `protocol='pllink'`, waits
  for `connect_result.ok == True` and first `gps_sats > 0` state push.

----------------------------------------------------------------------
## Files modified in original audit (2026-05-23)
- scripts/sim_pllink.py — 6 fixes (C1, C3, C4, C5, M1, M2) + dual-protocol
- scripts/build_package.py — 2 fixes (C6, M3)
- run.py — 2 fixes (M5, M6)
- tests/test_integration.py — 7 test fixes (Category C above)
- src/components/planning/SchedulerPanel.svelte — confirm guard (Category A)
- src/lib/locales/{zh,en}.ts — new `sched.confirmRun` key

## Files modified in follow-up (2026-05-24)
- backend/app.py — M7 (tile_bulk async), M8 (mbtiles relative_to), M9 (streaming upload), L5 (dotfile reject)
- scripts/build_desktop.sh — M4 (--collect-submodules)
- scripts/build_package.py — L2 (python-multipart)
- run.py — L4 (host default 127.0.0.1)
- tests/test_unit_handlers.py — Gap A + Gap B (2 new tests)
- tests/test_unit_app_routes.py — L5 (test_dotfile_apj_rejected), test_valid_apj_accepted refactor
- tests/test_integration.py — Gap C (test_connect_with_pllink_protocol), Category D (xfail removed)

## Remaining open findings
- L1 (build_package.py --arch for ARM64 Windows) — documented only
- L3 (build_desktop.sh TARGET_TRIPLE verification) — documented only
- L6, L7 — info/by-design, no action needed
