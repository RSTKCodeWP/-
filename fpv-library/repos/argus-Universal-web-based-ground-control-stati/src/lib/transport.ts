/**
 * Transport abstraction layer — unified interface for both:
 * 1. WebSerial direct connection (no backend needed)
 * 2. WebSocket connection via Python backend
 *
 * The frontend code calls transport functions which internally route
 * to the appropriate backend based on the active connection mode.
 */

import { parseFrames, encodeFrame, dispatchFrame } from './mavlink';
import type { MessageHandlers } from './mavlink';
import {
  encodeHeartbeat,
  encodeCommandLong,
  encodeSetMode,
  encodeParamRequestList,
  encodeParamRequestRead,
  encodeParamSet,
  encodeRequestDataStream,
  encodeMissionCount,
  encodeMissionItemInt,
  encodeMissionClearAll,
  encodeMissionSetCurrent,
  encodeMissionRequestList,
  encodeMissionRequestInt,
  encodeMissionAck,
  encodeLogRequestList,
  encodeLogRequestData,
  encodeLogRequestEnd,
  encodeCommandAck,
} from './mavlink';
import { openSerial, serialWrite, serialReadLoop, isWebSerialSupported } from './serial';
import type { SerialConnection } from './serial';
import { addToast, addEvent, app, isPlane as _isPlane } from './stores.svelte';
import { t } from './i18n.svelte';
import {
  buildMissionItems,
  buildFenceItems,
  missionItemsToWaypoints,
  validateMissionWaypoints,
  validateFencePolygon,
} from './missionUpload';
import type { MissionItem, RawMissionItem } from './missionUpload';
import type { Waypoint } from './types';
import {
  logState,
  setLogList,
  startDownload,
  appendLogChunkBinary,
  updateDownloadProgress,
  completeDownload,
  cancelDownload,
} from './logStore.svelte';
import type { LogEntry as LogEntryShape } from './logStore.svelte';
import {
  handleParamBatch,
  handleParamsComplete,
  handleParamTimeout,
  startParamFetch,
  updateParamRow,
} from './paramStore.svelte';

export type TransportMode = 'websocket' | 'serial';

interface SerialState {
  conn: SerialConnection | null;
  buf: Uint8Array;
  seq: number;
  running: boolean;
  hbInterval: ReturnType<typeof setInterval> | null;
  targetSysId: number;
  targetCompId: number;
  handlers: Partial<MessageHandlers>;
}

const serial: SerialState = {
  conn: null,
  buf: new Uint8Array(0),
  seq: 0,
  running: false,
  hbInterval: null,
  targetSysId: 1,
  targetCompId: 1,
  handlers: {},
};

// Coalesce repeated dispatch('mission_start') calls — match backend _timer_lock semantics.
let _missionStartTimer: ReturnType<typeof setTimeout> | null = null;

// wp_index → MAVLink seq, populated after a successful serialDownloadMission. Used by
// mission_set_current so "goto WP N" sends the correct seq even when DO_CHANGE_SPEED items
// shift the layout. Cleared on disconnect, mission_clear, and at the start of every download.
const _wpToSeq = new Map<number, number>();

function _clearMissionStartTimer(): void {
  if (_missionStartTimer !== null) {
    clearTimeout(_missionStartTimer);
    _missionStartTimer = null;
  }
}

export function getTransportMode(): TransportMode {
  return serial.conn ? 'serial' : 'websocket';
}

export function isSerialConnected(): boolean {
  return serial.conn !== null && serial.running;
}

export function webSerialAvailable(): boolean {
  return isWebSerialSupported();
}

/**
 * Connect via WebSerial.
 * Returns true if connection was established.
 */
export async function connectSerial(baudRate: number, handlers: Partial<MessageHandlers>): Promise<boolean> {
  if (serial.conn) await disconnectSerial();

  try {
    serial.conn = await openSerial(baudRate);
    serial.handlers = handlers;
    serial.running = true;
    serial.seq = 0;
    serial.buf = new Uint8Array(0);

    // Start heartbeat at 1Hz
    serial.hbInterval = setInterval(() => {
      sendSerialFrame(0, encodeHeartbeat());
    }, 1000);

    // Request data streams
    requestStreams();

    // Start read loop (runs until disconnected)
    serialReadLoop(serial.conn, (chunk) => {
      const combined = new Uint8Array(serial.buf.length + chunk.length);
      combined.set(serial.buf);
      combined.set(chunk, serial.buf.length);

      const { frames, remaining } = parseFrames(combined);
      serial.buf = remaining;

      for (const frame of frames) {
        if (serial.targetSysId === 1 && frame.sysId > 0 && frame.msgId === 0) {
          serial.targetSysId = frame.sysId;
          serial.targetCompId = frame.compId;
        }
        // Mission upload state machine runs BEFORE the external dispatch so the
        // upload completes deterministically even if the user's handler set is
        // missing onMissionRequest / onMissionAck. frame.payload is a DataView.
        if (upload?.pending) {
          if (frame.msgId === 40 || frame.msgId === 51) {
            const p = _padView(frame.payload, 2);
            _onMissionRequest(p.getUint16(0, true));
          } else if (frame.msgId === 47) {
            // MISSION_ACK type is at offset 2 (after target_system, target_component).
            const p = _padView(frame.payload, 3);
            _onMissionAck(p.getUint8(2));
          }
        }
        // Mission download state machine listens on MISSION_COUNT (44) and
        // MISSION_ITEM_INT (73). Upload and download are mutually exclusive,
        // so the order of these intercepts doesn't matter.
        if (download.pending) {
          if (frame.msgId === 44) _onMissionCountDl(_padView(frame.payload, 4));
          else if (frame.msgId === 73) _onMissionItemIntDl(_padView(frame.payload, 37));
        }
        // Log list / download state machines listen on LOG_ENTRY (118) and
        // LOG_DATA (120). Internal intercept first; external dispatch still
        // runs so user handlers see the frames if registered.
        if (logSession.listPending && frame.msgId === 118) {
          _onLogEntry(_padView(frame.payload, 14));
        } else if (logSession.dlPending && frame.msgId === 120) {
          // Full 97-byte pad: a zero-trimmed data tail must reconstruct to
          // the advertised count, not get shortened (see _onLogData).
          _onLogData(_padView(frame.payload, 97));
        }
        // Compass cal progress: translate binary MAG_CAL_PROGRESS (191) and
        // MAG_CAL_REPORT (192) into the same locale-aware event-stream
        // entries the backend emits, so the existing CalibrationPanel
        // regex heuristic (compassParsed) keeps working unchanged.
        if (frame.msgId === 191) _onMagCalProgress(_padView(frame.payload, 17));
        else if (frame.msgId === 192) _onMagCalReport(_padView(frame.payload, 44));
        // PARAM_VALUE (22) feeds the param store always — during a fetch it
        // drives progress/gap-fill; outside one it's a PARAM_SET echo that
        // must still update the edited row (backend handle_param_value has
        // the same always-on behavior).
        if (frame.msgId === 22) _onParamValue(_padView(frame.payload, 25));
        dispatchFrame(frame, serial.handlers);
      }
    })
      .catch((e) => {
        console.error('[Serial] read loop error', e);
      })
      .finally(() => {
        const wasRunning = serial.running;
        serial.running = false;
        if (wasRunning) {
          addToast(t('conn.serialLost'), 'error', 8000);
          // Release the transport mutex so the user can switch to WS without
          // having to click the (now-stale) USB button first.
          if (app.activeTransport === 'serial') app.activeTransport = 'none';
        }
        // Surface a link-lost error to any in-flight upload promise so the
        // MissionPanel doesn't wait the full 30s timeout.
        if (upload?.pending) {
          _resolveUpload({ ok: false, error: 'Serial link lost mid-upload' });
        }
        if (download.pending) {
          _resolveDownload({ ok: false, error: 'Serial link lost mid-download' });
        }
        // Tear down any in-flight log operation so its watchdog doesn't
        // fire spuriously after disconnect.
        if (logSession.listPending) _resolveLogList({ ok: false, error: 'Serial link lost' });
        if (logSession.dlPending) _abortLogDownload('Serial link lost mid-download');
        // Param fetch: stop the gap-fill ticker; link-lost toast already
        // shown above, so no second toast.
        _abortParamFetch(false);
      });

    return true;
  } catch {
    serial.conn = null;
    return false;
  }
}

export async function disconnectSerial(): Promise<void> {
  serial.running = false;
  if (serial.hbInterval) {
    clearInterval(serial.hbInterval);
    serial.hbInterval = null;
  }
  if (serial.conn) {
    await serial.conn.close();
    serial.conn = null;
  }
  serial.buf = new Uint8Array(0);
  _clearMissionStartTimer();
  _wpToSeq.clear();
  _abortParamFetch(false);
}

function sendSerialFrame(msgId: number, payload: Uint8Array): void {
  if (!serial.conn || !serial.running) return;
  const frame = encodeFrame(msgId, payload, 255, 190, serial.seq++);
  serialWrite(serial.conn, frame).catch((e) => {
    console.error('[Serial] write error', e);
  });
}

// MAVLink 2 zero-trim defense for the in-loop interceptors that read at
// specific offsets. dispatchFrame() pads via padPayload() before invoking
// user handlers, but our state-machine intercepts run on the raw payload
// BEFORE dispatchFrame, so trimmed frames would silently drop without this.
// Mirrors backend/mavlink_handlers.py:_pad. See protocol_design.md #2.
function _padView(p: DataView, minBytes: number): DataView {
  if (p.byteLength >= minBytes) return p;
  const buf = new Uint8Array(minBytes);
  buf.set(new Uint8Array(p.buffer, p.byteOffset, p.byteLength));
  return new DataView(buf.buffer);
}

function requestStreams(): void {
  // Rates match the backend's SET_MESSAGE_INTERVAL table in _helpers.py:
  // ATTITUDE (stream 10) and POSITION (stream 6) run at 10Hz so the
  // heading needle and position arrow animate as smoothly as the WS path.
  const streams = [
    [1, 4],  // RAW_SENSORS — GPS_RAW_INT at 4Hz to match WS _helpers.py:186
    [2, 2],  // EXTENDED_STATUS (SYS_STATUS, battery)
    [3, 2],  // RC_CHANNELS, SERVO_OUTPUT_RAW
    [6, 10], // POSITION — GLOBAL_POSITION_INT at 10Hz (was 5Hz)
    [10, 10], // EXTRA1 — ATTITUDE at 10Hz (was 2Hz)
    [11, 2], // EXTRA2 — VFR_HUD
    // EXTRA3 also carries MAG_CAL_PROGRESS/REPORT (STREAM_EXTRA3_msgs in
    // AP libraries/GCS_MAVLink/GCS_MAVLink_Parameters.cpp) — this stream
    // request is what makes compass-cal progress reach the WebSerial path.
    [12, 2], // EXTRA3 — VIBRATION, EKF_STATUS, MAG_CAL_*
  ];
  for (const [id, rate] of streams) {
    sendSerialFrame(66, encodeRequestDataStream(serial.targetSysId, serial.targetCompId, id, rate, 1));
  }
}

/* ── Serial command API (mirrors ws.ts sendCommand) ── */

export function serialSendArm(): void {
  sendSerialFrame(76, encodeCommandLong(serial.targetSysId, serial.targetCompId, 400, 0, 1, 0, 0, 0, 0, 0, 0));
}

export function serialSendDisarm(): void {
  sendSerialFrame(76, encodeCommandLong(serial.targetSysId, serial.targetCompId, 400, 0, 0, 0, 0, 0, 0, 0, 0));
}

export function serialSendMode(mode: number): void {
  sendSerialFrame(11, encodeSetMode(serial.targetSysId, 0x01, mode));
}

export function serialSendParamRequestAll(): void {
  sendSerialFrame(21, encodeParamRequestList(serial.targetSysId, serial.targetCompId));
}

export function serialSendParamSet(name: string, value: number, type: number = 9): void {
  sendSerialFrame(23, encodeParamSet(serial.targetSysId, serial.targetCompId, name, value, type));
}

export function serialSendCommandLong(command: number, p1 = 0, p2 = 0, p3 = 0, p4 = 0, p5 = 0, p6 = 0, p7 = 0): void {
  sendSerialFrame(
    76,
    encodeCommandLong(serial.targetSysId, serial.targetCompId, command, 0, p1, p2, p3, p4, p5, p6, p7),
  );
}

// SET_POSITION_TARGET_GLOBAL_INT (msg 86, 53 bytes). Mirrors backend cmd_guided_goto's struct.pack at
// backend/commands/_hardware.py:42 — int32 lat/lon × 1e7 for cm-level precision (float32 in COMMAND_LONG
// loses precision at typical lat magnitudes). type_mask 0x0FF8 ignores velocity, accel, yaw, yaw_rate.
// frame=6 = MAV_FRAME_GLOBAL_RELATIVE_ALT_INT (alt relative to home).
export function serialSendPositionTargetGlobal(lat: number, lon: number, alt: number): void {
  const buf = new ArrayBuffer(53);
  const dv = new DataView(buf);
  dv.setUint32(0, 0, true);                          // time_boot_ms
  dv.setInt32(4, Math.trunc(lat * 1e7), true);       // lat_int
  dv.setInt32(8, Math.trunc(lon * 1e7), true);       // lon_int
  dv.setFloat32(12, alt, true);                       // alt (relative)
  // vx/vy/vz/afx/afy/afz/yaw/yaw_rate at offsets 16..48 stay 0 (default ArrayBuffer fill)
  dv.setUint16(48, 0x0FF8, true);                     // type_mask
  dv.setUint8(50, serial.targetSysId);                // target_system
  dv.setUint8(51, serial.targetCompId);               // target_component
  dv.setUint8(52, 6);                                 // coordinate_frame = MAV_FRAME_GLOBAL_RELATIVE_ALT_INT
  sendSerialFrame(86, new Uint8Array(buf));
}

/**
 * Serial command dispatch table. Each entry maps a command name to a
 * function that sends it via WebSerial MAVLink. Commands not in this
 * table fall through to the WebSocket backend. Adding a new serial-
 * capable command = one line here, no switch/case to maintain.
 */
type CmdHandler = (param?: number, data?: Record<string, unknown>) => void;

// Coerce a numeric field the way the backend does: undefined falls back to
// the default (dict.get), everything else goes through Number() — with null
// mapped to NaN because Python float(None)/int(None) raises and the backend
// error-drops the whole command (a `?? default` here would silently
// substitute a value instead). NaN then fails every range check below.
const num = (v: unknown, dflt: number): number => (v === undefined ? dflt : v === null ? NaN : Number(v));
const _serialDispatch: Record<string, CmdHandler> = {
  arm: () => serialSendArm(),
  disarm: () => serialSendDisarm(),
  // 21196 = force-bypass magic from MAV_CMD_COMPONENT_ARM_DISARM. AP source: AP_Arming::handle_aux_function.
  force_disarm: () => serialSendCommandLong(400, 0, 21196),
  // Backend cmd_mode returns without sending when param is None — mirror that
  // instead of coercing undefined to custom_mode 0 (= Copter STABILIZE).
  mode: (p) => { if (p == null) return; serialSendMode(p); },
  // Plane RTL=11 (NOT 21=QRTL), Copter RTL=6. AP source: ArduPlane/mode.h, ArduCopter/mode.h `enum class Number`.
  rtl: () => serialSendMode(_isPlane() ? 11 : 6),
  // MAV_CMD_NAV_TAKEOFF (22): p7=alt. AP source ArduPlane/quadplane.cpp:3948 (QuadPlane::do_user_takeoff)
  // rejects unless control_mode == mode_guided — switch Plane to GUIDED (15) first to match backend cmd_takeoff.
  takeoff: (_, d) => {
    const alt = num(d?.alt, 30);
    // Bounds mirror backend cmd_takeoff (_flight.py:47-49), and run BEFORE
    // the Plane mode switch so an invalid alt doesn't leak a bare GUIDED
    // transition the backend path would never have sent.
    if (!(alt >= 1 && alt <= 1000)) return;
    if (_isPlane()) serialSendMode(15);
    serialSendCommandLong(22, 0, 0, 0, 0, 0, 0, alt);
  },
  // Backend cmd_mission_start: switch to AUTO, then send MAV_CMD_MISSION_START (300) after a delay.
  // Copter requires the explicit MISSION_START — switching to AUTO alone leaves it idle while disarmed-on-ground.
  // AP source: ModeAuto::start in ArduCopter/mode_auto.cpp.
  // Delay mirrors cfg.MISSION_START_DELAY = 0.3 in backend/config.py. Timer is cancelled on re-entry so
  // double-tap doesn't queue two MISSION_START sends (matches backend's _timer_lock + .cancel() pattern).
  mission_start: () => {
    serialSendMode(_isPlane() ? 10 : 3);
    if (_missionStartTimer !== null) clearTimeout(_missionStartTimer);
    _missionStartTimer = setTimeout(() => {
      _missionStartTimer = null;
      serialSendCommandLong(300);
    }, 300);
  },
  mission_clear: () => serialClearMission(),
  // Mission seq mapping: backend prepends HOME (seq 0) + TAKEOFF (seq 1), and inserts DO_CHANGE_SPEED (178)
  // before any waypoint with speed > 0. _seqToWp (populated on serialDownloadMission completion) gives the
  // accurate mapping. Falls back to `wp_index + 2` when no map exists, matching backend cmd_mission_set_current
  // (commands/_mission.py:47-52) — that fallback is wrong when speed inserts exist, but at least it doesn't divert to HOME.
  mission_set_current: (_, d) => {
    // Math.trunc mirrors backend int(); NaN (incl. null input) drops like
    // the backend's int(None) TypeError → error-drop.
    const wpIndex = Math.trunc(num(d?.wp_index, 0));
    if (!Number.isFinite(wpIndex)) return;
    const seq = _wpToSeq.get(wpIndex) ?? wpIndex + 2;
    serialMissionSetCurrent(seq);
  },
  // MAV_CMD_DO_SET_RELAY (181): p1=relay instance, p2=state. AP source:
  // GCS_Common.cpp:5848 routes to AP_ServoRelayEvents::do_set_relay
  // (AP_ServoRelayEvents.cpp:70). The payload-drop rig hangs off relay 0,
  // active-low: drop=state 0, drop_stop=state 1. Mirrors backend cmd_drop.
  // (Previously mislabeled DO_PARACHUTE — that is cmd 208.)
  drop: () => serialSendCommandLong(181, 0, 0),
  drop_stop: () => serialSendCommandLong(181, 0, 1),
  // SET_POSITION_TARGET_GLOBAL_INT (msg 86) with int32 lat/lon × 1e7 — cm-level precision vs MAV_CMD float32's 1-3m.
  // Mirror backend cmd_guided_goto (_hardware.py): switch to GUIDED first (Plane=15, Copter=4), then msg 86.
  // ArduPilot rejects DO_REPOSITION outside GUIDED unless CHANGE_MODE flag is set — using msg 86 sidesteps that.
  // Validation mirrors backend's coord bounds — silently drop on invalid (matches motor_test pattern; the dispatch
  // table has no error-return path, but NaN/zero would write a (0,0) "Null Island" waypoint).
  guided_goto: (_, d) => {
    const lat = num(d?.lat, 0);
    const lon = num(d?.lon, 0);
    const alt = num(d?.alt, 30);
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || !Number.isFinite(alt)) return;
    if (Math.abs(lat) < 0.001 && Math.abs(lon) < 0.001) return;
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180 || alt < -500 || alt > 100000) return;
    serialSendMode(_isPlane() ? 15 : 4);
    serialSendPositionTargetGlobal(lat, lon, alt);
  },
  // MAV_CMD_DO_SET_ROI (201) with p1=3 = ROI_LOCATION mode. cmd 197 is DO_SET_ROI_NONE per common.xml —
  // it CLEARS the ROI and ignores lat/lon, so the previous wiring made setRoi() and clearRoi() identical.
  // AP source: AP_Mount handle_command DO_SET_ROI branch in libraries/AP_Mount/AP_Mount.cpp.
  do_set_roi: (_, d) => {
    const lat = num(d?.lat, 0);
    const lon = num(d?.lon, 0);
    const alt = num(d?.alt, 0);
    // lat/lon bounds mirror backend cmd_do_set_roi (_hardware.py:220-226);
    // (0,0) stays legal — it is the ROI-clear convention.
    if (!(lat >= -90 && lat <= 90) || !(lon >= -180 && lon <= 180) || !Number.isFinite(alt)) return;
    serialSendCommandLong(201, 3, 0, 0, 0, lat, lon, alt);
  },
  param_set: (_, d) => serialSendParamSet(d?.name as string, d?.value as number),
  param_request_all: () => serialParamRequestAll(),
  // MAV_CMD_PREFLIGHT_STORAGE (245), p1=1: write running params to FC NVRAM. AP source: GCS_MAVLINK::handle_command_preflight_storage.
  // `param_save` is intentionally NOT in this table — it writes a host-side JSON backup over WS, which serial can't do
  // (would silently do the wrong thing). UIs that want FC flash use `param_save_to_flash` explicitly.
  param_save_to_flash: () => serialSendCommandLong(245, 1),
  // MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN (246). p1: 1=reboot autopilot, 3=reboot to bootloader. AP source: GCS_MAVLINK::handle_preflight_reboot.
  reboot: () => serialSendCommandLong(246, 1),
  reboot_bootloader: () => serialSendCommandLong(246, 3),
  rc_override: (_, d) => {
    const ch = d?.channels as number[];
    // Backend cmd_rc_override (_hardware.py:100-111) refuses lists shorter
    // than 8 channels rather than zero-filling: an accidental short array
    // would otherwise RELEASE channels 2..8 back to RC (0 = release) on a
    // live vehicle. Same for a null/non-numeric ELEMENT (backend int(None)
    // raises → whole command error-drops), and in-range coercion clamps to
    // u16 like the backend's max(0, min(65535, ...)) instead of wrapping.
    // All production callers (gamepad, EscCalPanel) send all 8 as ints.
    if (ch && ch.length >= 8) {
      const vals: number[] = [];
      for (let i = 0; i < 8; i++) {
        const v = ch[i] == null ? NaN : Number(ch[i]);
        if (!Number.isFinite(v)) return;
        vals.push(Math.max(0, Math.min(65535, Math.trunc(v))));
      }
      const payload = new Uint8Array(18);
      const dv = new DataView(payload.buffer);
      for (let i = 0; i < 8; i++) dv.setUint16(i * 2, vals[i], true);
      dv.setUint8(16, serial.targetSysId);
      dv.setUint8(17, serial.targetCompId);
      sendSerialFrame(70, payload);
    }
  },
  cal_compass: () => serialCalCompass(),
  cal_compass_accept: () => serialCalCompassAccept(),
  cal_cancel: () => serialCalCancel(),
  cal_gyro: () => serialCalGyro(),
  cal_level: () => serialCalLevel(),
  cal_baro: () => serialCalBaro(),
  cal_accel: () => serialCalAccel(),
  cal_accel_next: () => serialCalAccelNext(),
  log_cancel: () => serialLogCancel(),
  gimbal_pitchyaw: (_, d) => serialGimbalPitchYaw(d as Parameters<typeof serialGimbalPitchYaw>[0]),
  // MAV_CMD_DO_MOUNT_CONTROL (205): p1=pitch, p3=yaw, p7=MAV_MOUNT_MODE_MAVLINK_TARGETING (2). AP source: AP_Mount.cpp:363-417.
  gimbal_angle: (_, d) => {
    const pitch = num(d?.pitch, 0);
    const yaw = num(d?.yaw, 0);
    // Bounds mirror backend cmd_gimbal_angle (_hardware.py:141-146); NaN
    // fails the range check and drops, same as the backend's float(nan).
    if (!(pitch >= -90 && pitch <= 90) || !(yaw >= -180 && yaw <= 180)) return;
    serialSendCommandLong(205, pitch, 0, yaw, 0, 0, 0, 2);
  },
  // MAV_CMD_DO_DIGICAM_CONTROL (203): p5=1 is the shoot command. Sending all zeros is a no-op AP_Camera ignores.
  // Mirrors backend cmd_camera_trigger (_hardware.py:198-202).
  camera_trigger: () => serialSendCommandLong(203, 0, 0, 0, 0, 1),
  // MAV_CMD_VIDEO_START_CAPTURE (2500): p1=stream_id (0=all), p2=status_freq (0=quiet), p3=target_camera (1).
  // Mirrors backend cmd_camera_video_start (_hardware.py:205-206) — explicit camera id targeting. STOP=2501.
  camera_video_start: () => serialSendCommandLong(2500, 0, 0, 1),
  camera_video_stop: () => serialSendCommandLong(2501),
  // MAV_CMD_SET_CAMERA_ZOOM (531): p1=zoom_type (1=CAMERA_ZOOM_TYPE_CONTINUOUS), p2=zoom_value.
  // Default 1 and bounds 0.1..100 mirror backend cmd_camera_zoom
  // (_hardware.py:213-217); the previous `?? 0` default silently diverged.
  camera_zoom: (_, d) => {
    const zoom = num(d?.zoom, 1);
    if (!(zoom >= 0.1 && zoom <= 100)) return;
    serialSendCommandLong(531, 1, zoom);
  },
  // MAV_CMD_DO_MOTOR_TEST (209): p1=motor(1-based), p2=THROTTLE_PERCENT(0), p3=%, p4=duration, p5=count
  // ArduPilot: GCS_MAVLink_Copter.cpp:702 — GCS_MAVLINK_Copter::handle_command_long_packet
  // Bounds match backend/commands/_hardware.py:120-127 — drop silently rather than blast FC with bad values.
  motor_test: (_, d) => {
    // Math.trunc(motor) mirrors backend int(); positive-form bounds so NaN
    // (incl. null input) drops instead of slipping past `< 0 || > 7`.
    const motor = Math.trunc(num(d?.motor, 0));
    const throttle = num(d?.throttle, 5);
    const duration = num(d?.duration, 2);
    if (!(motor >= 0 && motor <= 7)) return;
    if (!(throttle >= 0 && throttle <= 100)) return;
    if (!(duration > 0 && duration <= 30)) return;
    serialSendCommandLong(209, motor + 1, 0, throttle, duration, 1);
  },
  motor_test_stop: () => {
    for (let i = 1; i <= 8; i++) serialSendCommandLong(209, i, 0, 0, 0, 1);
  },
};

/**
 * Unified command dispatcher. Routes through WebSerial when USB-
 * connected and the command has a serial handler; otherwise falls
 * back to the WebSocket backend. Use this everywhere instead of
 * sendCommand() — new serial commands only need a table entry above.
 */
export function dispatch(name: string, param?: number, data?: Record<string, unknown>): void {
  if (isSerialConnected()) {
    // Mirror backend commands.execute (commands/__init__.py:153-155): once a
    // non-ArduPilot autopilot is latched (0 = not yet known, 3 = ArduPilot),
    // refuse FC-bound commands — every _serialDispatch entry is ArduPilot-
    // specific (mode ids, cal handshakes, command params). The latch itself
    // is set by the serial heartbeat handler (serialHandlers.ts).
    const ap = app.drone?.autopilot;
    // null/undefined = store not initialized yet — same as 0 (not latched).
    if (ap != null && ap !== 0 && ap !== 3) {
      const fcName = ap === 12 ? 'PX4' : `autopilot=${ap}`;
      addToast(t('conn.unsupportedFc').replace('{fc}', fcName), 'error', 5000);
      return;
    }
    const handler = _serialDispatch[name];
    if (handler) { handler(param, data); return; }
  }
  import('./ws').then((ws) => ws.sendCommand(name, param, data));
}

/** @deprecated Use dispatch() instead */
export const flightCmd = dispatch;

/** True when `name` has a WebSerial-native handler. Used by the parity
 * harness to reject typo'd op names that would otherwise pass vacuously
 * (unknown names fall through to the WS backend and emit no serial frame). */
export function hasSerialHandler(name: string): boolean {
  return name in _serialDispatch;
}

/**
 * Gimbal pitch/yaw: wraps the COMMAND_INT (msg 75) path the gimbal manager
 * handler expects. Mirrors backend cmd_gimbal_pitchyaw at
 * backend/commands/_hardware.py — same NaN-as-skip semantics for the four
 * angle/rate params, same flags-as-x bitfield, same instance-as-z (z is the
 * float slot but the AP handler casts to uint8). See AP_Mount.cpp:363-417.
 */
export function serialGimbalPitchYaw(data: {
  pitch?: number;
  yaw?: number;
  pitch_rate?: number;
  yaw_rate?: number;
  flags?: number;
  instance?: number;
}): void {
  if (!isSerialConnected()) return;
  const f = (v: number | undefined): number => (v == null ? NaN : Number(v));
  const pitch = f(data.pitch);
  const yaw = f(data.yaw);
  const pitchRate = f(data.pitch_rate);
  const yawRate = f(data.yaw_rate);
  // Math.trunc mirrors backend int(); null → NaN (int(None) raises there).
  const flags = Math.trunc(num(data.flags, 0));
  const instance = Math.trunc(num(data.instance, 0));

  // Range validation mirrors backend cmd_gimbal_pitchyaw (_hardware.py:179-193):
  // NaN means "skip this slot" for the four angle/rate params; a finite
  // out-of-range value drops the whole command rather than clamping. flags
  // and instance are NOT skippable — NaN there must drop, hence the
  // positive-form bounds.
  const inRange = (v: number, lo: number, hi: number): boolean => Number.isNaN(v) || (v >= lo && v <= hi);
  if (!inRange(pitch, -90, 90) || !inRange(yaw, -180, 180) ||
      !inRange(pitchRate, -180, 180) || !inRange(yawRate, -180, 180)) return;
  if (!(flags >= -0x80000000 && flags <= 0x7fffffff)) return;
  if (!(instance >= 0 && instance <= 6)) return;

  const payload = new Uint8Array(35);
  const dv = new DataView(payload.buffer);
  dv.setFloat32(0, pitch, true);
  dv.setFloat32(4, yaw, true);
  dv.setFloat32(8, pitchRate, true);
  dv.setFloat32(12, yawRate, true);
  dv.setInt32(16, flags | 0, true); // x: GIMBAL_MANAGER_FLAGS bitfield
  dv.setInt32(20, 0, true); // y: unused
  dv.setFloat32(24, instance, true); // z: gimbal device id
  dv.setUint16(28, 1000, true); // command = MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW
  dv.setUint8(30, serial.targetSysId);
  dv.setUint8(31, serial.targetCompId);
  dv.setUint8(32, 0); // frame (unused for COMMAND_INT)
  dv.setUint8(33, 0); // current
  dv.setUint8(34, 0); // autocontinue
  sendSerialFrame(75, payload);
}

/* ── Mission upload state machine (WebSerial direct mode) ───────────────
 *
 * Mirrors backend/commands/_mission.py:_upload_mission so the FC sees the
 * exact same MISSION_COUNT → MISSION_REQUEST_INT → MISSION_ITEM_INT → ...
 * → MISSION_ACK handshake as it would from a WebSocket-backed upload.
 *
 * The FC drives the cadence — every MISSION_REQUEST(_INT) we receive maps to
 * a single MISSION_ITEM_INT response. The 5s per-item timer guards against a
 * silent FC; the 30s overall guard catches the link-up-but-not-responding
 * case so the UI doesn't hang.
 */

interface UploadState {
  items: MissionItem[];
  missionType: number; // 0=MISSION, 1=FENCE, 2=RALLY — passed through on
  // MISSION_COUNT + each MISSION_ITEM_INT so the FC's
  // AP_Mission/AP_Fence routes the upload correctly.
  resolve: (result: { ok: boolean; error?: string }) => void;
  itemTimer: ReturnType<typeof setTimeout> | null;
  overallTimer: ReturnType<typeof setTimeout> | null;
  pending: boolean;
  lastSeq: number; // last seq the FC requested, -1 before first MISSION_REQUEST
}

let upload: UploadState | null = null;

function _resolveUpload(result: { ok: boolean; error?: string }): void {
  if (!upload) return;
  const u = upload;
  upload = null;
  if (u.itemTimer) clearTimeout(u.itemTimer);
  if (u.overallTimer) clearTimeout(u.overallTimer);
  if (u.pending) u.resolve(result);
}

function _onMissionRequest(seq: number): void {
  if (!upload?.pending) return;
  if (seq < 0 || seq >= upload.items.length) {
    _resolveUpload({ ok: false, error: `FC requested out-of-range seq ${seq}` });
    return;
  }
  const item = upload.items[seq];
  upload.lastSeq = seq;
  sendSerialFrame(
    73,
    encodeMissionItemInt(
      serial.targetSysId,
      serial.targetCompId,
      item.seq,
      item.command,
      item.frame,
      item.current,
      item.autocontinue,
      upload.missionType,
      item.p1,
      item.p2,
      item.p3,
      item.p4,
      item.x,
      item.y,
      item.z,
    ),
  );
  // 5s per-item watchdog: if the FC never asks for the next seq, fail loud.
  if (upload.itemTimer) clearTimeout(upload.itemTimer);
  upload.itemTimer = setTimeout(() => {
    _resolveUpload({ ok: false, error: `FC stopped requesting items after seq ${seq}` });
  }, 5000);
}

function _onMissionAck(type: number): void {
  if (!upload?.pending) return;
  // MAV_MISSION_ACCEPTED = 0. Anything else is a rejection from AP_Mission.
  if (type === 0) {
    _resolveUpload({ ok: true });
  } else {
    _resolveUpload({ ok: false, error: `MISSION_ACK type=${type}` });
  }
}

export function isSerialMissionUploading(): boolean {
  return upload?.pending === true;
}

function _startUpload(items: MissionItem[], missionType: number): Promise<{ ok: boolean; error?: string }> {
  return new Promise((resolve) => {
    upload = {
      items,
      missionType,
      resolve,
      itemTimer: null,
      overallTimer: setTimeout(() => {
        _resolveUpload({ ok: false, error: 'Mission upload timed out (30s overall)' });
      }, 30000),
      pending: true,
      lastSeq: -1,
    };
    sendSerialFrame(44, encodeMissionCount(serial.targetSysId, serial.targetCompId, items.length, missionType));
  });
}

export async function serialUploadMission(
  waypoints: Waypoint[],
  takeoffAlt: number,
): Promise<{ ok: boolean; error?: string }> {
  if (!isSerialConnected()) return { ok: false, error: 'Not connected via serial' };
  if (upload?.pending) return { ok: false, error: 'Another upload is in progress' };
  if (download.pending) return { ok: false, error: 'A mission download is in progress' };

  const validation = validateMissionWaypoints(waypoints);
  if (!validation.ok) return validation;
  return _startUpload(buildMissionItems(waypoints, takeoffAlt), 0);
}

/**
 * Fence polygon upload. Same protocol as a mission upload but with
 * mission_type=1 (MAV_MISSION_TYPE_FENCE) on both MISSION_COUNT and every
 * MISSION_ITEM_INT, so AP_Fence routes the upload to the fence buffer
 * instead of the mission buffer. Mirrors backend cmd_fence_upload.
 */
export async function serialUploadFence(
  polygon: { lat: number; lon: number }[],
): Promise<{ ok: boolean; error?: string }> {
  if (!isSerialConnected()) return { ok: false, error: 'Not connected via serial' };
  if (upload?.pending) return { ok: false, error: 'Another upload is in progress' };
  if (download.pending) return { ok: false, error: 'A mission download is in progress' };

  const validation = validateFencePolygon(polygon);
  if (!validation.ok) return validation;
  return _startUpload(buildFenceItems(polygon), 1);
}

export function serialClearMission(): void {
  if (!isSerialConnected()) return;
  sendSerialFrame(45, encodeMissionClearAll(serial.targetSysId, serial.targetCompId, 0));
  _wpToSeq.clear();
}

export function serialMissionSetCurrent(seq: number): void {
  if (!isSerialConnected()) return;
  sendSerialFrame(41, encodeMissionSetCurrent(serial.targetSysId, serial.targetCompId, seq));
}

/* ── Mission DOWNLOAD state machine (WebSerial direct mode) ─────────────
 *
 * GCS → MISSION_REQUEST_LIST (43)
 * FC  → MISSION_COUNT (44)
 * GCS → MISSION_REQUEST_INT (51) for each seq 0..count-1
 * FC  → MISSION_ITEM_INT (73) for each
 * GCS → MISSION_ACK (47, type=0) on completion
 *
 * Mirrors backend handle_mission_count / handle_mission_item_int /
 * _request_dl_item in backend/mavlink_handlers.py. The items→Waypoint
 * collapse runs through missionItemsToWaypoints so the on-screen layout
 * matches a backend-mediated download for the same FC state.
 */

interface DownloadState {
  pending: boolean;
  resolve: ((r: { ok: boolean; error?: string; waypoints?: Waypoint[] }) => void) | null;
  items: (RawMissionItem | null)[];
  total: number;
  timer: ReturnType<typeof setTimeout> | null;
}

const download: DownloadState = {
  pending: false,
  resolve: null,
  items: [],
  total: 0,
  timer: null,
};

function _resetDownloadTimer(): void {
  if (download.timer) clearTimeout(download.timer);
  download.timer = setTimeout(() => {
    _resolveDownload({ ok: false, error: 'Mission download stalled (no FC reply in 5s)' });
  }, 5000);
}

function _resolveDownload(result: { ok: boolean; error?: string; waypoints?: Waypoint[] }): void {
  if (!download.pending) return;
  download.pending = false;
  if (download.timer) {
    clearTimeout(download.timer);
    download.timer = null;
  }
  download.items = [];
  download.total = 0;
  const r = download.resolve;
  download.resolve = null;
  if (r) r(result);
}

function _onMissionCountDl(p: DataView): void {
  // p is pre-padded to ≥4 bytes by the read-loop interceptor.
  if (!download.pending) return;
  const count = p.getUint16(0, true);
  download.total = count;
  download.items = new Array(count).fill(null);
  if (count === 0) {
    // FC has no mission. Send the ACK so we don't leak the request, and
    // resolve with an empty waypoint list.
    sendSerialFrame(47, encodeMissionAck(serial.targetSysId, serial.targetCompId, 0, 0));
    _resolveDownload({ ok: true, waypoints: [] });
    return;
  }
  sendSerialFrame(51, encodeMissionRequestInt(serial.targetSysId, serial.targetCompId, 0, 0));
  _resetDownloadTimer();
}

function _onMissionItemIntDl(p: DataView): void {
  // p is pre-padded to ≥37 bytes by the read-loop interceptor (matches
  // backend handle_mission_item_int's `_pad(p, 37)` at mavlink_handlers.py:406).
  if (!download.pending) return;
  // MISSION_ITEM_INT layout (matches decodeMissionItemInt at messages.ts:345
  // and backend handle_mission_item_int at mavlink_handlers.py:402-427).
  const p1 = p.getFloat32(0, true);
  const p2 = p.getFloat32(4, true);
  const p3 = p.getFloat32(8, true);
  const p4 = p.getFloat32(12, true);
  const x = p.getInt32(16, true);
  const y = p.getInt32(20, true);
  const z = p.getFloat32(24, true);
  const seq = p.getUint16(28, true);
  const cmd = p.getUint16(30, true);
  const frame = p.getUint8(34);
  const current = p.getUint8(35);
  const autocontinue = p.getUint8(36);

  if (seq < download.total) {
    download.items[seq] = {
      seq,
      cmd,
      lat: x / 1e7,
      lon: y / 1e7,
      alt: z,
      p1,
      p2,
      p3,
      p4,
      frame,
      current,
      autocontinue,
    };
  }

  // Request the lowest still-missing seq, not blindly seq+1, and finalize only
  // when every slot is filled. Mirrors backend handle_mission_item_int: a
  // duplicated/out-of-order final MISSION_ITEM_INT (seq == total-1) must not
  // finalize early and silently drop the gaps into a truncated mission.
  const nextMissing = download.items.findIndex((i) => i === null);
  if (nextMissing !== -1) {
    sendSerialFrame(51, encodeMissionRequestInt(serial.targetSysId, serial.targetCompId, nextMissing, 0));
    _resetDownloadTimer();
  } else {
    // All slots filled — send the MISSION_ACK and collapse to Waypoints.
    sendSerialFrame(47, encodeMissionAck(serial.targetSysId, serial.targetCompId, 0, 0));
    const items: RawMissionItem[] = download.items.filter((i): i is RawMissionItem => i !== null);
    const waypoints = missionItemsToWaypoints(items);
    _buildWpToSeqMap(items);
    _resolveDownload({ ok: true, waypoints });
  }
}

// Mirror missionItemsToWaypoints' iteration order: walk by seq, skip DO_CHANGE_SPEED (178),
// skip seq 0 (HOME, cmd 16) and the various non-nav DO_* / TAKEOFF / RTL items, and only count
// the nav-WP family (cmd 16/18/19/82 with seq > 0). Result is parallel-indexed with the waypoints
// the UI sees, so mission_set_current's wp_index lookup hits the right seq.
function _buildWpToSeqMap(items: RawMissionItem[]): void {
  _wpToSeq.clear();
  const sorted = [...items].sort((a, b) => a.seq - b.seq);
  let wpIndex = 0;
  for (const item of sorted) {
    if (item.cmd === 178) continue;  // DO_CHANGE_SPEED — carries forward, doesn't consume a wp
    if ((item.cmd === 16 || item.cmd === 18 || item.cmd === 19 || item.cmd === 82) && item.seq > 0) {
      _wpToSeq.set(wpIndex, item.seq);
      wpIndex++;
    }
  }
}

export async function serialDownloadMission(): Promise<{ ok: boolean; error?: string; waypoints?: Waypoint[] }> {
  if (!isSerialConnected()) return { ok: false, error: 'Not connected via serial' };
  if (download.pending) return { ok: false, error: 'Another mission download is in progress' };
  if (upload?.pending) return { ok: false, error: 'A mission upload is in progress' };

  return new Promise((resolve) => {
    download.pending = true;
    download.resolve = resolve;
    download.items = [];
    download.total = 0;
    _wpToSeq.clear();  // stale map from previous download would otherwise mislead mission_set_current
    _resetDownloadTimer();
    sendSerialFrame(43, encodeMissionRequestList(serial.targetSysId, serial.targetCompId, 0));
  });
}

/* ── Compass calibration (WebSerial direct mode) ─────────────────────────
 *
 * GCS → MAV_CMD_DO_START_MAG_CAL (42424) via COMMAND_LONG
 * FC  → MAG_CAL_PROGRESS (191) at ~10Hz with pct byte at offset 16
 * FC  → MAG_CAL_REPORT (192) once per compass with cal_status at offset 42
 *        (cal_status == 4 = MAG_CAL_SUCCESS, anything else = failed)
 * GCS → MAV_CMD_DO_ACCEPT_MAG_CAL (42425) when done, or
 *       MAV_CMD_DO_CANCEL_MAG_CAL (42426) to abort
 *
 * Mirrors backend's handle_mag_cal_progress / handle_mag_cal_report at
 * backend/mavlink_handlers.py:215-244 exactly — same dedup (5% bucket,
 * one-shot done flag) so the events sent to addEvent() match what the
 * WS-mediated path would have produced. CalibrationPanel's compassParsed
 * regex matches both locales.
 */

interface MagCalState {
  pct: number; // last %% emitted, -1 = none
  done: boolean; // one-shot to avoid double "complete" or progress-after-done
}

const magCal: MagCalState = { pct: -1, done: false };

function _resetMagCal(): void {
  magCal.pct = -1;
  magCal.done = false;
}

function _onMagCalProgress(p: DataView): void {
  // p is pre-padded to ≥17 bytes (matches backend's `_pad(p, 17)`).
  if (magCal.done) return;
  const pct = p.getUint8(16);
  // Emit only when crossing a new 5% bucket — same filter as backend
  // handle_mag_cal_progress (mavlink_handlers.py:223-226). Prevents 200+
  // events flooding the log over a 30s cal.
  if (pct > magCal.pct && Math.floor(pct / 5) !== Math.floor(magCal.pct / 5)) {
    magCal.pct = pct;
    addEvent({
      type: 'event',
      time: new Date().toLocaleTimeString(),
      text: t('cal.s.compassPct').replace('{pct}', String(pct)),
      event_type: 'cal_compass',
    });
  } else if (pct > magCal.pct) {
    magCal.pct = pct; // track the value so the next bucket cross fires
  }
}

function _onMagCalReport(p: DataView): void {
  // p is pre-padded to ≥44 bytes (matches backend's `_pad(p, 44)`).
  // cal_status is at offset 42 — see backend handler.
  if (magCal.done) return;
  const calStatus = p.getUint8(42);
  magCal.done = true;
  magCal.pct = -1;
  if (calStatus === 4) {
    // MAG_CAL_SUCCESS. Backend emits TWO events (done + reboot hint);
    // CalibrationPanel only reads the first for completion detection but
    // we replicate both so the message log looks identical.
    addEvent({
      type: 'event',
      time: new Date().toLocaleTimeString(),
      text: t('cal.s.compassDone'),
      event_type: 'cal_compass',
    });
    addEvent({
      type: 'event',
      time: new Date().toLocaleTimeString(),
      text: t('cal.s.compassReboot'),
      event_type: 'cal_compass',
    });
  } else {
    addEvent({
      type: 'event',
      time: new Date().toLocaleTimeString(),
      text: t('cal.s.compassFailed'),
      event_type: 'cal_compass',
    });
  }
}

export function serialCalCompass(): void {
  if (!isSerialConnected()) return;
  _resetMagCal();
  // MAV_CMD_DO_START_MAG_CAL: p1=mag_mask(0=all), p2-p4=options(0). Matches
  // backend cmd_cal_compass (send_cmd(link, 42424, p1=0, p2=0, p3=0, p4=0)).
  serialSendCommandLong(42424, 0, 0, 0, 0, 0, 0, 0);
}

export function serialCalCompassAccept(): void {
  if (!isSerialConnected()) return;
  serialSendCommandLong(42425, 0, 0, 0, 0, 0, 0, 0);
}

export function serialCalCancel(): void {
  if (!isSerialConnected()) return;
  // MAV_CMD_DO_CANCEL_MAG_CAL only cancels MAG cal (per cmd_cal_cancel
  // comment in backend/commands/_setup.py:62-68 — gyro/level/baro complete
  // in <1s and have no FC-side cancel). UI state reset stays the same.
  serialSendCommandLong(42426, 0, 0, 0, 0, 0, 0, 0);
  _resetMagCal();
}

export function serialCalGyro(): void {
  if (!isSerialConnected()) return;
  // MAV_CMD_PREFLIGHT_CALIBRATION (241), p1=1 = gyro cal.
  serialSendCommandLong(241, 1, 0, 0, 0, 0, 0, 0);
}

export function serialCalLevel(): void {
  if (!isSerialConnected()) return;
  // MAV_CMD_PREFLIGHT_CALIBRATION (241), p5=4 = level (board-orientation) cal.
  serialSendCommandLong(241, 0, 0, 0, 0, 4, 0, 0);
}

export function serialCalBaro(): void {
  if (!isSerialConnected()) return;
  // MAV_CMD_PREFLIGHT_CALIBRATION (241), p3=1 = ground pressure cal.
  serialSendCommandLong(241, 0, 0, 1, 0, 0, 0, 0);
}

/**
 * Accel calibration uses a TWO-PHASE protocol. Phase 1 (serialCalAccel) is
 * a standard COMMAND_LONG. Phase 2 (serialCalAccelNext) is NOT — it abuses
 * COMMAND_ACK (msg 77) with field semantics that contradict the MAVLink
 * spec. Anyone "cleaning up" the wire by sending MAV_CMD_ACCELCAL_VEHICLE_POS
 * (42429) or result=MAV_RESULT_ACCEPTED(0) will silently break accel cal.
 *
 * See [[feedback-protocol-discipline]] and protocol_design.md #1 — this is
 * the canonical example of FC-coupled code that looks wrong but is correct.
 */
export function serialCalAccel(): void {
  if (!isSerialConnected()) return;
  // MAV_CMD_PREFLIGHT_CALIBRATION (241), p5=1 = accel cal. Matches backend
  // cmd_cal_accel at backend/commands/_setup.py:27-29.
  serialSendCommandLong(241, 0, 0, 0, 0, 1, 0, 0);
}

export function serialCalAccelNext(): void {
  if (!isSerialConnected()) return;
  // AP_AccelCal::handle_command_ack (libraries/AP_AccelCal/AP_AccelCal.cpp:
  // 366-393) hijacks COMMAND_ACK with private semantics:
  //   if (packet.command > 6)                        return;  // not a MAV_CMD value
  //   if (packet.result != TEMPORARILY_REJECTED(1))  return;  // result MUST be 1
  // QGC sends command=0, result=1; we mirror QGC. Backend equivalent at
  // backend/commands/_setup.py:cmd_cal_accel_next (lines 47-58).
  sendSerialFrame(77, encodeCommandAck(0, 1));
}

/* ── Log list + download state machines (WebSerial direct mode) ─────────
 *
 * List: GCS → LOG_REQUEST_LIST (117). FC streams LOG_ENTRY (118) per log; the
 *       entry with id == last_log_num signals end-of-list and resolves the
 *       promise.
 * Download: GCS → LOG_REQUEST_DATA (119) for the WHOLE log (ofs=0,
 *           count=size) — the MAVProxy pattern ArduPilot explicitly
 *           tolerates (AP_Logger_MAVLinkLogTransfer.cpp:112-113). AP
 *           streams LOG_DATA (120) as one paced burst and ends its transfer
 *           at remaining==0 or a short read (:337-341); while the burst is
 *           active it silently drops any new same-channel request
 *           (:111-120), so follow-up requests (gap-fill, stall retry) go
 *           out only at burst boundaries. Received ranges are tracked as
 *           coverage intervals; when the stream ends with holes (lost
 *           frames), each gap is re-requested until coverage is complete.
 *           count==0 in a LOG_DATA is AP_Logger's "EOF / log unreadable"
 *           signal — finalize as truncated. Same machine as backend
 *           handle_log_data.
 * Cancel:  GCS → LOG_REQUEST_END (122). Aborts any in-flight download.
 */

interface LogSessionState {
  listPending: boolean;
  listResolve: ((r: { ok: boolean; error?: string }) => void) | null;
  listTimer: ReturnType<typeof setTimeout> | null;
  listEntries: LogEntryShape[];

  dlPending: boolean;
  dlResolve: ((r: { ok: boolean; error?: string }) => void) | null;
  dlTimer: ReturnType<typeof setTimeout> | null;
  dlId: number;
  dlSize: number;
  dlOfs: number;
  // End offset of the currently-requested LOG_REQUEST_DATA window — the
  // next request may only go out once dlOfs reaches this boundary (twin of
  // backend LogState._log_window_end).
  dlWindowEnd: number;
  // Stall re-requests issued without progress (twin of backend
  // LogState._log_stall_retries); reset on every accepted frame.
  dlStallRetries: number;
  // Coverage of accepted LOG_DATA byte ranges as sorted disjoint [start,end)
  // intervals — mid-window frame loss leaves zero-filled holes the window
  // cadence never revisits, and covered-bytes short of the size is the only
  // tell. Intervals (not a raw sum) because stall re-requests can
  // legitimately overlap late frames of the old burst (twin of backend
  // LogState._log_recv_intervals).
  dlRecvIntervals: Array<[number, number]>;
}

const logSession: LogSessionState = {
  listPending: false,
  listResolve: null,
  listTimer: null,
  listEntries: [],
  dlPending: false,
  dlResolve: null,
  dlTimer: null,
  dlId: -1,
  dlSize: 0,
  dlOfs: 0,
  dlWindowEnd: 0,
  dlStallRetries: 0,
  dlRecvIntervals: [],
};

// Merge [start, end) into a sorted, disjoint coverage list (twin of backend
// _mark_received). In-order bursts extend the tail interval in O(1).
function _markReceived(intervals: Array<[number, number]>, start: number, end: number): void {
  if (intervals.length > 0) {
    const last = intervals[intervals.length - 1];
    if (last[0] <= start && start <= last[1]) {
      if (end > last[1]) last[1] = end;
      return;
    }
  }
  intervals.push([start, end]);
  intervals.sort((a, b) => a[0] - b[0]);
  const merged: Array<[number, number]> = [intervals[0]];
  for (let i = 1; i < intervals.length; i++) {
    const [s, e] = intervals[i];
    const m = merged[merged.length - 1];
    if (s <= m[1]) m[1] = Math.max(m[1], e);
    else merged.push([s, e]);
  }
  intervals.length = 0;
  intervals.push(...merged);
}

function _coveredBytes(intervals: Array<[number, number]>): number {
  let sum = 0;
  for (const [s, e] of intervals) sum += e - s;
  return sum;
}

// First uncovered byte range of the download, or null when coverage is
// complete. With whole-log streaming this doubles as the resume point: no
// holes means the first gap starts exactly at the high-water mark (twin of
// backend _next_log_gap).
function _nextLogGap(): [number, number] | null {
  let prevEnd = 0;
  for (const [s, e] of logSession.dlRecvIntervals) {
    if (s > prevEnd) return [prevEnd, s];
    prevEnd = Math.max(prevEnd, e);
  }
  if (prevEnd < logSession.dlSize) return [prevEnd, logSession.dlSize];
  return null;
}

// Request the first uncovered byte range in one LOG_REQUEST_DATA — the
// MAVProxy pattern ArduPilot explicitly tolerates (AP_Logger_MAVLink-
// LogTransfer.cpp:112-113 names it): stream big ranges, then fill holes.
// AP anchors the transfer to our ofs and caps count to the remaining log
// size (:144-152), so requesting an entire gap is always in-spec. Returns
// false when coverage is complete (twin of backend _request_next_log_gap).
function _requestNextLogGap(): boolean {
  const gap = _nextLogGap();
  if (!gap) return false;
  logSession.dlWindowEnd = gap[1];
  sendSerialFrame(
    119,
    encodeLogRequestData(serial.targetSysId, serial.targetCompId, logSession.dlId, gap[0], gap[1] - gap[0])
  );
  return true;
}

function _resolveLogList(result: { ok: boolean; error?: string }): void {
  if (!logSession.listPending) return;
  logSession.listPending = false;
  if (logSession.listTimer) {
    clearTimeout(logSession.listTimer);
    logSession.listTimer = null;
  }
  const r = logSession.listResolve;
  logSession.listResolve = null;
  if (r) r(result);
}

function _onLogEntry(p: DataView): void {
  // p is pre-padded to ≥14 bytes by the read-loop interceptor.
  const entry: LogEntryShape = {
    time_utc: p.getUint32(0, true),
    size: p.getUint32(4, true),
    id: p.getUint16(8, true),
    // num_logs at offset 10 (uint16) is informational; last_log_num at 12 is
    // what we actually check.
  };
  const lastLogNum = p.getUint16(12, true);
  logSession.listEntries.push(entry);
  // Reset the watchdog every time a new entry shows up — slow FCs can take
  // tens of seconds to list 100+ logs.
  if (logSession.listTimer) clearTimeout(logSession.listTimer);
  logSession.listTimer = setTimeout(() => {
    _resolveLogList({ ok: false, error: 'FC stopped sending LOG_ENTRY' });
  }, 5000);
  if (entry.id === lastLogNum) {
    setLogList([...logSession.listEntries]);
    _resolveLogList({ ok: true });
  }
}

function _abortLogDownload(error: string): void {
  if (!logSession.dlPending) return;
  logSession.dlPending = false;
  if (logSession.dlTimer) {
    clearTimeout(logSession.dlTimer);
    logSession.dlTimer = null;
  }
  cancelDownload();
  const r = logSession.dlResolve;
  logSession.dlResolve = null;
  if (r) r({ ok: false, error });
}

function _finishLogDownload(truncated: boolean, reason?: string): void {
  if (!logSession.dlPending) return;
  const id = logSession.dlId;
  const size = logSession.dlOfs;
  logSession.dlPending = false;
  logSession.dlId = -1; // match backend _log_download_id=-1 (see below)
  if (logSession.dlTimer) {
    clearTimeout(logSession.dlTimer);
    logSession.dlTimer = null;
  }
  // Mid-window frame loss leaves zero-filled holes the window cadence never
  // revisits. Coverage intervals make the check exact — duplicates and
  // re-request overlaps never inflate it — so covered short of the size is a
  // definite loss: flag the file rather than shipping silently corrupted
  // zeros (twin of backend _finalize_log_download).
  const missing = size - _coveredBytes(logSession.dlRecvIntervals);
  if (!truncated && missing > 0) {
    truncated = true;
    reason = `Frame loss — ${missing} bytes missing (zero-filled)`;
  }
  // Clear coverage only AFTER the missing check reads it. Resetting dlId +
  // intervals matches the backend (which sets _log_download_id=-1 on
  // finalize): left set, a late/duplicate same-id LOG_DATA would pass the
  // `logId !== dlId` guard, re-arm the watchdog and re-run coverage on a
  // completed session — harmless today (every downstream effect is
  // separately guarded) but a real cross-stack divergence.
  logSession.dlRecvIntervals = [];
  // Pass empty b64 — the streaming chunks already populated logState._chunks;
  // completeDownload assembles + triggers the browser download.
  completeDownload(id, undefined, size);
  const r = logSession.dlResolve;
  logSession.dlResolve = null;
  if (r) r({ ok: !truncated, error: truncated ? (reason ?? 'Download truncated (count=0 from FC)') : undefined });
}

const LOG_DL_STALL_MS = 5000; // matches backend LOG_DL_STALL_TIMEOUT
const LOG_DL_STALL_RETRIES = 3; // matches backend LOG_DL_STALL_RETRIES

function _armDlWatchdog(): void {
  if (logSession.dlTimer) clearTimeout(logSession.dlTimer);
  logSession.dlTimer = setTimeout(_onDlStall, LOG_DL_STALL_MS);
}

// Stall watchdog — twin of backend check_log_dl_stall. The window cadence
// only sends the next LOG_REQUEST_DATA from _onLogData, so a lost
// window-boundary frame means no LOG_DATA ever arrives again and nothing
// would re-request. Re-requesting the unreceived remainder from the
// high-water mark is safe: AP already ended its burst when it sent the
// (lost) boundary frame (AP_Logger_MAVLinkLogTransfer.cpp:337-341,
// end_log_transfer() at remaining==0), and the :111-118 guard only drops
// requests that arrive while a transfer is actively sending — an idle AP
// honors the retry, a still-bursting AP harmlessly drops it. The old
// behavior aborted outright and discarded every received chunk — a 16 MB
// download lost to one dropped frame at 99%.
function _onDlStall(): void {
  if (!logSession.dlPending) return;
  if (logSession.dlStallRetries >= LOG_DL_STALL_RETRIES) {
    // Deliver what we have (zero-filled, flagged) instead of discarding —
    // twin of backend check_log_dl_stall's finalize(truncated=True).
    _finishLogDownload(true, 'FC stopped sending LOG_DATA (re-requests unanswered)');
    return;
  }
  logSession.dlStallRetries += 1;
  if (!_requestNextLogGap()) {
    // Coverage complete but the finish never ran — should be unreachable
    // (_onLogData finishes on covered >= size); close out cleanly.
    _finishLogDownload(false);
    return;
  }
  _armDlWatchdog();
}

function _onLogData(p: DataView): void {
  // p is pre-padded to the full 97-byte LOG_DATA payload, so a MAVLink2
  // zero-trimmed tail reconstructs to exactly `count` bytes — taking only
  // the untrimmed bytes here used to silently shorten zero-tailed chunks
  // (backend handle_log_data pads to 97 for the same reason).
  const ofs = p.getUint32(0, true);
  const logId = p.getUint16(4, true);
  // The LOG_DATA data field is uint8_t[90] (MAVLink common.xml) but count is
  // a free u8 — a corrupt frame that passes CRC could advertise up to 255.
  // Unclamped, the Uint8Array view below would either throw RangeError past
  // the buffer end (tearing down the whole read loop) or spill into the CRC
  // and following-frame bytes.
  const count = Math.min(p.getUint8(6), 90);
  if (logId !== logSession.dlId) return;
  // FC count==0 is the AP_Logger "EOF / unreadable log" sentinel — see the
  // count==0 branch in backend handle_log_data (backend/mavlink_handlers.py).
  if (count === 0) {
    _finishLogDownload(true);
    return;
  }
  const end = ofs + count;
  // ofs shares count's threat model: every LOG_REQUEST_DATA we send is
  // capped to the remaining bytes, so an out-of-range frame is never
  // legitimate. Unguarded, a garbage ofs would push the high-water mark
  // past the size — completeDownload sizes its assembly buffer from the
  // largest ofs+length, up to 4 GB for a u32 ofs.
  if (end > logSession.dlSize) return;
  const data = new Uint8Array(p.buffer, p.byteOffset + 7, count);
  appendLogChunkBinary(logId, ofs, data);
  _markReceived(logSession.dlRecvIntervals, ofs, end);
  // High-water mark: only used as the delivered-file size when a truncated
  // finish ships a partial download. Progress/completion run on coverage.
  if (end > logSession.dlOfs) logSession.dlOfs = end;
  const covered = _coveredBytes(logSession.dlRecvIntervals);
  updateDownloadProgress(covered, logSession.dlSize);

  // Any accepted frame is progress — re-arm the stall watchdog and forget
  // past retries.
  logSession.dlStallRetries = 0;
  _armDlWatchdog();

  if (covered >= logSession.dlSize) {
    _finishLogDownload(false);
    return;
  }
  if (end >= logSession.dlWindowEnd || count < 90) {
    // AP's burst for our current request just ended — either this frame
    // reached the end of the requested range, or AP sent a short frame (a
    // short read ends its transfer too, AP_Logger_MAVLinkLogTransfer.cpp
    // :339-341). AP SILENTLY DROPS requests that arrive mid-burst
    // (:111-120), so this boundary is the only safe moment to ask for more.
    // Ask for the first uncovered gap: during the main whole-log stream
    // that's simply the resume point; after it, it fills holes left by
    // lost frames (end-of-transfer gap-fill, MAVProxy-style).
    _requestNextLogGap();
  }
}

export function isSerialLogBusy(): boolean {
  return logSession.listPending || logSession.dlPending;
}

export async function serialLogList(): Promise<{ ok: boolean; error?: string }> {
  if (!isSerialConnected()) return { ok: false, error: 'Not connected via serial' };
  if (logSession.listPending || logSession.dlPending) {
    return { ok: false, error: 'Another log operation is in progress' };
  }
  return new Promise((resolve) => {
    logSession.listPending = true;
    logSession.listResolve = resolve;
    logSession.listEntries = [];
    logSession.listTimer = setTimeout(() => {
      _resolveLogList({ ok: false, error: 'LOG_REQUEST_LIST timed out (no LOG_ENTRY in 5s)' });
    }, 5000);
    sendSerialFrame(117, encodeLogRequestList(serial.targetSysId, serial.targetCompId, 0, 0xffff));
  });
}

export async function serialLogDownload(id: number): Promise<{ ok: boolean; error?: string }> {
  if (!isSerialConnected()) return { ok: false, error: 'Not connected via serial' };
  if (logSession.listPending || logSession.dlPending) {
    return { ok: false, error: 'Another log operation is in progress' };
  }
  const entry = logState.list.find((e) => e.id === id);
  if (!entry) return { ok: false, error: 'Log not in list — request the list first' };
  if (entry.size === 0) return { ok: false, error: 'Log is empty' };

  startDownload(id, entry.size);
  return new Promise((resolve) => {
    logSession.dlPending = true;
    logSession.dlResolve = resolve;
    logSession.dlId = id;
    logSession.dlSize = entry.size;
    logSession.dlOfs = 0;
    logSession.dlRecvIntervals = [];
    logSession.dlStallRetries = 0;
    // Arm the stall watchdog now so even a lost FIRST request gets retried.
    _armDlWatchdog();
    // Request the WHOLE log in one LOG_REQUEST_DATA — the MAVProxy pattern
    // ArduPilot explicitly tolerates (AP_Logger_MAVLinkLogTransfer.cpp
    // :112-113 names it) and caps in-spec (:144-152). Windowed 4500 B
    // requests paid one ~20 ms round trip per window — an RTT-bound
    // ~225 KB/s ceiling on a ~700 KB/s USB link. Lost frames are
    // re-requested from the coverage intervals once the stream ends.
    logSession.dlWindowEnd = entry.size;
    sendSerialFrame(119, encodeLogRequestData(serial.targetSysId, serial.targetCompId, id, 0, entry.size));
  });
}

export function serialLogCancel(): void {
  if (!isSerialConnected()) return;
  sendSerialFrame(122, encodeLogRequestEnd(serial.targetSysId, serial.targetCompId));
  if (logSession.dlPending) _abortLogDownload('Cancelled');
  if (logSession.listPending) _resolveLogList({ ok: false, error: 'Cancelled' });
}

// ── Parameter fetch (serial twin of backend/param_manager.py) ──────────────
/**
 * Protocol (mirrors ParamManager exactly — divergence here means the two
 * transports fetch different param sets):
 * Fetch:   GCS → PARAM_REQUEST_LIST (21); the FC streams PARAM_VALUE (22),
 *          each carrying param_count — the first reply pins the expected
 *          total (param_manager.handle_param_value).
 * Gaps:    after PARAM_GAP_FILL_MS of silence with slots still missing,
 *          re-request individually via PARAM_REQUEST_READ (20) by index,
 *          ≤10 per window and ≤3 tries per index; a dropped initial msg 21
 *          (total still unknown) is re-sent up to 3 times instead
 *          (param_manager.check_timeout — one dropped request must not
 *          stall the whole fetch).
 * 0xFFFF:  by-name replies carry param_index -1: ArduPilot GCS_Param.cpp:396
 *          branches on `req.param_index != -1` and :420 echoes it back —
 *          count the param, never mark an index slot.
 * Timeout: PARAM_FETCH_TIMEOUT_MS overall → handleParamTimeout + toast.
 * Until 2026-07-16 the serial path SENT msg 21 but dropped every PARAM_VALUE
 * reply (no handler) — the panel sat empty while the FC streamed 1000+
 * params. Found live against a real FC; the SIM path never exercises this.
 */

const PARAM_GAP_FILL_MS = 2000; // backend cfg.PARAM_GAP_FILL_DELAY
const PARAM_FETCH_TIMEOUT_MS = 60_000; // backend cfg.PARAM_FETCH_TIMEOUT

interface ParamFetchState {
  active: boolean;
  total: number;
  names: Set<string>;
  indices: Set<number>;
  gapAttempts: Map<number, number>;
  listAttempts: number;
  startTime: number;
  lastValueTime: number;
  timer: ReturnType<typeof setInterval> | null;
}

const paramFetch: ParamFetchState = {
  active: false,
  total: -1,
  names: new Set(),
  indices: new Set(),
  gapAttempts: new Map(),
  listAttempts: 0,
  startTime: 0,
  lastValueTime: 0,
  timer: null,
};

function serialParamRequestAll(): void {
  // Restart-in-flight is allowed, like backend request_all(): reset all
  // bookkeeping and start a fresh stream.
  _stopParamTimer();
  paramFetch.active = true;
  paramFetch.total = -1;
  paramFetch.names.clear();
  paramFetch.indices.clear();
  paramFetch.gapAttempts.clear();
  paramFetch.listAttempts = 1;
  paramFetch.startTime = Date.now();
  paramFetch.lastValueTime = Date.now();
  startParamFetch();
  paramFetch.timer = setInterval(_paramFetchTick, 500);
  serialSendParamRequestAll();
}

function _onParamValue(p: DataView): void {
  // Wire layout mirrors backend param_manager.handle_param_value:
  // param_value f32 @0, param_count u16 @4, param_index u16 @6,
  // param_id char[16] @8, param_type u8 @24.
  const value = p.getFloat32(0, true);
  const count = p.getUint16(4, true);
  const index = p.getUint16(6, true);
  const bytes = new Uint8Array(p.buffer, p.byteOffset + 8, 16);
  let end = bytes.indexOf(0);
  if (end < 0) end = 16;
  const name = new TextDecoder().decode(bytes.slice(0, end));
  const ptype = p.getUint8(24);
  // Empty name = all-zero/garbage frame — don't poison the store with a
  // blank row (same guard as the backend).
  if (!name) return;

  if (!paramFetch.active) {
    // PARAM_SET echo or unsolicited value: upsert the row only. Feeding
    // handleParamBatch here would replay stale total/received counters and
    // re-latch paramState.fetching after a timed-out partial fetch,
    // bricking the Read-All button (fresh-eyes finding, 2026-07-16).
    updateParamRow(name, value, ptype, index);
    return;
  }

  paramFetch.lastValueTime = Date.now();
  if (paramFetch.total < 0) paramFetch.total = count;
  if (index !== 0xffff) paramFetch.indices.add(index);
  paramFetch.names.add(name);
  handleParamBatch([
    { name, value, ptype, index, total: paramFetch.total, received: paramFetch.names.size },
  ]);
  if (paramFetch.total > 0 && paramFetch.names.size >= paramFetch.total) {
    paramFetch.active = false;
    _stopParamTimer();
    handleParamsComplete();
  }
}

function _paramFetchTick(): void {
  if (!paramFetch.active) return;
  const now = Date.now();
  const silent = now - paramFetch.lastValueTime > PARAM_GAP_FILL_MS;
  if (paramFetch.total <= 0 && silent) {
    if (paramFetch.listAttempts <= 3) {
      paramFetch.listAttempts++;
      paramFetch.lastValueTime = now; // back off until the next window
      serialSendParamRequestAll();
    }
  } else if (paramFetch.total > 0 && silent) {
    let sent = 0;
    // Intentional divergence from backend check_timeout: it slices
    // missing[:10] BEFORE the retry filter, so retry-exhausted indices eat
    // window slots (a fully-exhausted head wedges it at 0 sends/window).
    // Here exhausted indices don't consume a slot and the scan goes deeper.
    for (let i = 0; i < paramFetch.total && sent < 10; i++) {
      if (paramFetch.indices.has(i)) continue;
      const attempts = paramFetch.gapAttempts.get(i) ?? 0;
      if (attempts >= 3) continue;
      paramFetch.gapAttempts.set(i, attempts + 1);
      sendSerialFrame(20, encodeParamRequestRead(serial.targetSysId, serial.targetCompId, i));
      sent++;
    }
    paramFetch.lastValueTime = now;
  }
  if (now - paramFetch.startTime > PARAM_FETCH_TIMEOUT_MS) {
    _abortParamFetch(true);
  }
}

function _stopParamTimer(): void {
  if (paramFetch.timer) {
    clearInterval(paramFetch.timer);
    paramFetch.timer = null;
  }
}

function _abortParamFetch(timedOut: boolean): void {
  _stopParamTimer();
  if (!paramFetch.active) return;
  paramFetch.active = false;
  handleParamTimeout();
  if (timedOut) addToast(t('param.timeout'), 'error', 5000);
}
