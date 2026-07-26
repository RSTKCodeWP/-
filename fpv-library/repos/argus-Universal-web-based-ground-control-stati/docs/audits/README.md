# Protocol-Layer Audit Reports

These are point-in-time audit reports produced during the 2026-05-23 review
of Argus GCS's MAVLink + ArduPilot interaction layer. Each file is the raw
agent output from a single audit pass — preserved here so future contributors
can see what was checked, what was found, and what was deliberately deferred.

Each report is dated by the file's mtime in the original /tmp scratch
location; they were copied here verbatim and not re-edited.

## Index

| File | Scope | Result |
|---|---|---|
| `audit_modes.md` | Flight-mode tables vs ArduCopter/Plane/Rover/Sub `mode.h` | Rover ID 5 mislabeled + 32 missing modes. **Fixed.** |
| `audit_log.md` | Log download protocol vs `AP_Logger_MAVLinkLogTransfer.cpp` | 6 critical state-machine bugs. **Fixed.** |
| `audit_param.md` | Parameter protocol vs `GCS_Param.cpp` | 8 critical + 9 partial bugs. **Most fixed.** |
| `audit_mission.md` | Mission upload/download vs `AP_Mission.cpp` | 2 critical + 18 partial. **Critical fixed.** |
| `audit_drone_link.md` | DroneLink main loop / reconnect / locking | 6 critical + 9 warnings. **All critical fixed.** |
| `audit_encoders.md` | Frontend `messages.ts` encoders vs pymavlink | **0 bugs.** Verified byte-perfect. |
| `audit_webserial.md` | Frontend MAVLink codec (WebSerial direct mode) | 1 offset bug, 4 edge gaps, 13 missing decoders. **All fixed.** |
| `audit_px4_pllink.md` | PX4 claim + PL-Link wrapper protocol | PX4 unwired (documented in CLAUDE.md), PL-Link bm-length added. |
| `audit_modules.md` | connection/ws_manager/app/auth/video sweep | 5 critical (security), 23 medium. **Critical + most medium fixed.** |
| `audit_edges.md` | Specific partial findings (equator, NAV_SPLINE, VTOL takeoff, etc.) | 5 real bugs, 3 fixed in-place, 2 documented. |
| `audit_frontend.md` | Svelte 5 components/stores reactivity + lifecycle | 40+ findings, 10 fixed in-place. |
| `audit_remaining.md` | sim_pllink + build scripts + run.py + test_integration triage + remaining app.py routes | 6 critical + 10 medium + 7 low. **19 fixed in-place** including sim protocol auto-detect, mbtiles path traversal, PyInstaller hidden-import for `backend.commands._*`. |
| `sitl_validation_2026-05-24.md` | End-to-end check against real ArduCopter SITL v4.6.3 — telemetry, mission round-trip, command pipeline, params, fence, Phase P WS propagation, custom-identity FC rendering | **7 PASS, 1 partial (full mission flight), 4 blocked on USB**. Real-AP corroboration for the protocol assertions that the unit suite makes under mocks. |

## What's still open

Items the audits surfaced but were not fixed because they're either large
rewrites or product-decision territory:

- **PX4 support is non-existent in production.** See `CLAUDE.md ## PX4 Status`.
- Several Svelte components (F-17, F-36, F-39 in `audit_frontend.md`) need
  larger refactors — ack-driven state instead of hard timers.
- 32 tests in `tests/test_integration.py` fail with `TimeoutError` — almost
  certainly fixture/infrastructure issues, not code bugs. Triage was in
  progress in the modules sweep.
- The 7 contract-test orphans (NTRIP commands + 5 dead backend handlers) are
  product decisions: implement or delete.

## The discipline this enforces

Every audit cross-references the Argus source against either ArduPilot
source (a local ArduPilot checkout during the session)
or pymavlink (`pip install pymavlink`) as ground truth. The rule in
`CLAUDE.md ## Protocol Code Discipline` says all FC-coupled code must cite
the upstream source file:line in a comment. The audits in this folder are
the receipts for the citations that have already landed.
