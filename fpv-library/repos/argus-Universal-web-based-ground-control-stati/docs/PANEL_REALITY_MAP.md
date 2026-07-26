# Panel Reality Map — 2026-07-13 static audit

Every component under `src/components/` cross-referenced against the backend
ws command set (52 commands), REST routes (27), the WebSerial transport
dispatch table, and the store/telemetry fields the backend actually pushes.

**Verdicts** — `WIRED`: drives real backend commands/routes and/or consumes
real pushed telemetry. `GCS-LOCAL`: fully functional, purely client-side by
design (planning geometry, local analysis, UI primitives). `PARTIAL`: some
functions real, some dead/stubbed. `DEMO`: hardcoded data or cosmetic shell.

## Tally

| verdict | count | share |
|---|---|---|
| WIRED | 46 | 60% |
| GCS-LOCAL | 26 | 34% |
| PARTIAL | 2 | 3% |
| DEMO | 3 | 4% |

(77 panels after the same-day fixes below; original audit found 78 with
44/26/5/3.)

Every `sendCommand`/`dispatch` name used by any panel exists in the backend
dispatch table; every `fetch` route exists. No `Math.random` telemetry and no
fake progress bars anywhere. The 8 problem panels below are the complete list.

## Problem panels — audit findings and same-day resolutions (2026-07-13)

| panel | audit finding | resolution |
|---|---|---|
| map/Compass3DPanel | sample sphere plotted `vibe` as if mag samples | FIXED — backend now parses RAW_IMU (27, subscribed 5Hz) and pushes `mag`; sphere plots the real field |
| planning/SchedulerPanel | no timer; autoArm/mission-select ignored | FIXED — app-level scheduler service ticks all session, confirm-gated firing honoring autoArm; vestigial mission dropdown removed (saved-mission slots never existed) |
| vehicle/MultiVehiclePanel | placeholder no-op switch, duplicate of FleetDashboard | REMOVED — palette entry now opens FleetDashboard |
| map/AirspacePanel | 50 hardcoded airports could read as authoritative | LABELED — in-UI demo-data banner; data unchanged (still DEMO) |
| shared/RolePanel | `argus_role` written, never enforced | LABELED — in-UI "display-only, not enforced" banner (still DEMO) |
| planning/AiPlannerPanel | "AI" is a regex heuristic, no LLM | LABELED — in-UI note: local rule parser, not a cloud LLM (still functional) |
| planning/AiAnnotationPanel | `aiDetect()` is a toast stub | LABELED — honest toast: auto-detect unavailable, annotate manually |
| tools/RemotePanel | no tunnel/relay behind 远程操控 | LABELED — hint states no built-in tunnel; needs reachable backend |

Trivial cleanup applied: `mission/PoiPanel`'s stale "do_set_roi not
implemented" comment removed (the command has been implemented for a while).

## Cross-cutting findings

- **Dual transport paths.** Besides the Python backend (ws), the frontend
  ships a complete WebSerial direct-connect MAVLink stack (~4,000 lines:
  `src/lib/mavlink/`, `transport.ts`, `serial.ts`, `fc/`). `transport.dispatch()`
  routes 11 flight commands to serial when USB-connected and falls back to ws
  otherwise; params/mission/calibration/log have dedicated `serial*` functions.
  Panels calling `ws.sendCommand` directly are ws-only (they fail loud with a
  toast in serial-only mode).
- **PX4 nuance.** `src/lib/fc/px4.ts` implements a real PX4 mode table
  (main/sub-mode bit scheme) for the WebSerial path — so CLAUDE.md's "PX4
  unwired" is accurate for the backend path only. The backend-side
  unsupported-FC guard (75c3182) does not apply to WebSerial sessions.
- **Test coverage shape.** All 31 vitest files are lib-level; there are zero
  component-level tests. e2e exercises panels only through main flows
  (connection, control, params, mission, palette, navigation).

## Full map

Format: `Panel | verdict | what it does / evidence`.

### core/

| panel | verdict | note |
|---|---|---|
| ChartPanel | GCS-LOCAL | canvas sparklines of 6 real telemetry channels; sends nothing |
| ConnectionForm | WIRED | real ws connect/disconnect + WebSerial path + /api/ports |
| ControlPanel | WIRED | arm/disarm/rtl/mode/takeoff/mission/drop — all real, gated on live state |
| EventLog | GCS-LOCAL | filters/exports the real event stream client-side |
| HudOverlay | GCS-LOCAL | SVG PFD rendering real pitch/roll/gs/alt/vz/hdg |
| LazyPanelHost | GCS-LOCAL | dynamic-import host for panels |
| MapControls | WIRED | map-overlay quick commands (rtl/mode/arm/disarm), all real |
| MapView | WIRED | Leaflet + /api/tile/* + guided_goto |
| StatusBar | WIRED | live link/gps/ekf/batt indicators + /api/log download |
| ToastContainer | GCS-LOCAL | notification UI primitive |

### layers/

| panel | verdict | note |
|---|---|---|
| DroneLayer | GCS-LOCAL | renders real drone/home/trail/multi-vehicle/ADS-B positions |
| FenceLayer | GCS-LOCAL | draws local fence polygon state |
| GuidedLayer | GCS-LOCAL | visualizes guided target set via MapView |
| ReplayLayer | GCS-LOCAL | renders local log-replay position |
| SurveyLayer | GCS-LOCAL | draws local survey polygon |
| WaypointLayer | GCS-LOCAL | edits local plan; active-WP ring from real wp_idx |

### map/

| panel | verdict | note |
|---|---|---|
| AirspacePanel | DEMO | 50 hardcoded airports (in-UI demo-data banner since 2026-07-13) |
| Compass3DPanel | WIRED | real cal_compass; sphere plots real RAW_IMU mag field |
| Map3DView | WIRED | maplibre 3D + tiles + guided_goto + live telemetry |
| Mission3DPanel | GCS-LOCAL | client-side 3D render of local plan |
| OfflineMapPanel | WIRED | /api/tile_bulk_download + /api/tile_cache |
| OrthoOverlayPanel | GCS-LOCAL | localStorage-persisted image overlays |

### mission/

| panel | verdict | note |
|---|---|---|
| CorridorPanel | GCS-LOCAL | corridor-scan waypoint generation (pure geometry) |
| FencePanel | WIRED | real fence_upload (+serial fallback), ack-driven |
| MissionPanel | WIRED | mission_upload/set_current + /api/terrain/elevation, ack-driven |
| MissionProgress | WIRED | live progress HUD from mode_id/wp_idx/gs |
| PoiPanel | WIRED | do_set_roi real |
| SurveyPanel | GCS-LOCAL | survey grid generation (pure geometry) |
| TerrainProfilePanel | GCS-LOCAL | profile chart via real /api/terrain/elevation |

### params/

| panel | verdict | note |
|---|---|---|
| AutoTunePanel | WIRED | AUTOTUNE_AXES param_set + AutoTune mode switch |
| FailsafeConfigPanel | WIRED | FS_*/BATT_* read/write through real param store |
| FlightModePanel | WIRED | FLTMODE1-6 read/write; active slot from live mode_id |
| ParamDiffPanel | WIRED | diff .param file vs live store, apply via param_set |
| ParamPanel | WIRED | full browser/editor + /api/param_meta; WebSerial param stream wired 2026-07-16 (before that, serial sent the request but dropped every PARAM_VALUE — empty panel). Param metadata still needs the backend (/api/param_meta) |
| PidPanel | WIRED | ATC_RAT_* sliders + param_save_to_flash |
| PowerCalPanel | WIRED | BATT_* calibration using live voltage |

### setup/

| panel | verdict | note |
|---|---|---|
| CalibrationPanel | WIRED | all cal commands; progress parsed from live events |
| EscCalPanel | WIRED | ESC wizard via real rc_override |
| FirmwarePanel | WIRED | /api/firmware/* + reboot/reboot_bootloader |
| FrameSelectPanel | WIRED | FRAME_CLASS/TYPE via param store |
| MotorTestPanel | WIRED | motor_test/stop real; countdown cosmetic |
| NtripPanel | WIRED | ntrip_start/stop, ack-driven, live gps_fix_raw |
| PositionSourcePanel | WIRED | read-only decode of live EKF flags |
| RcCalibPanel | WIRED | captures live rc[], writes RC*_MIN/MAX/TRIM |
| SetupWizard | GCS-LOCAL | step navigator opening real sub-panels |

### telemetry/

| panel | verdict | note |
|---|---|---|
| EkfPanel | WIRED | real EKF_STATUS_REPORT variances/flags |
| RcPanel | WIRED | real RC_CHANNELS bars + RSSI |
| ServoPanel | WIRED | real SERVO_OUTPUT_RAW bars |
| TelemetryOverlay | WIRED | flight HUD from live state |
| VibrationPanel | WIRED | real VIBRATION chart + clip counts |

### tools/

| panel | verdict | note |
|---|---|---|
| AdvancedCmdPanel | GCS-LOCAL | DO_* waypoint annotations consumed by real mission upload |
| ConsolePanel | WIRED | serial_control + console_output push |
| FFTPanel | GCS-LOCAL | client-side FFT of local DF log + notch advice |
| FlightReportPanel | WIRED | real flight_summary/events; local txt export |
| InspectorPanel | WIRED | inspector_toggle + inspector push |
| LogPanel | WIRED | log_list/download/cancel with real chunked progress |
| LogViewerPanel | GCS-LOCAL | client-side DF log charting |
| RemotePanel | PARTIAL | real session/link status; "share" = clipboard URL, no tunnel |
| ReplayPanel | GCS-LOCAL | local CSV/DF playback driving map replay layer |

### planning/

| panel | verdict | note |
|---|---|---|
| AiAnnotationPanel | PARTIAL | manual bbox annotation real; aiDetect() is a toast stub |
| AiPlannerPanel | DEMO | regex heuristic, no LLM; does append real waypoints |
| AnnotationPanel | GCS-LOCAL | localStorage POI notes CRUD |
| CustomDashboard | WIRED | tile dashboard of live telemetry; localStorage layout |
| OverlapCalcPanel | GCS-LOCAL | GSD/overlap math; feeds surveySpacing to SurveyPanel |
| SchedulerPanel | WIRED | app-level timer, confirm-gated firing, autoArm honored |
| ScriptPanel | WIRED | user JS with real send()/drone-state API |

### shared/

| panel | verdict | note |
|---|---|---|
| CommandPalette | WIRED | dispatches real flight/cal/mission commands |
| ConfirmDialog | GCS-LOCAL | confirm primitive gating real commands |
| FlightSummary | WIRED | real post-flight stats; local export |
| LoginDialog | WIRED | /api/auth/login token flow |
| PreflightPanel | WIRED | readiness checks from live telemetry/prearm |
| RolePanel | DEMO | RBAC unenforced (in-UI banner says display-only) |
| SettingsPanel | GCS-LOCAL | localStorage settings feeding real commands; embeds FirmwarePanel |
| SlideConfirm | GCS-LOCAL | slide gesture executing real command callbacks |

### vehicle/

| panel | verdict | note |
|---|---|---|
| FleetDashboard | WIRED | live per-vehicle cards + real switch_vehicle |
| GimbalPanel | WIRED | gimbal/camera/ROI — all six commands real |
| VideoOverlay | WIRED | /api/video proxy + AR overlay from live pose |
