/**
 * WebSerial telemetry handlers: decoded MAVLink messages → app.drone store.
 *
 * This is the serial-mode twin of the backend path (mavlink_handlers.py →
 * get_state() → ws push → updateState). Extracted from ConnectionForm.svelte
 * so tests/test_contract_dualstack_state_parity.py can drive the REAL mapping
 * code: the same FC frame must land in app.drone with the same values on both
 * transports, and that harness is the only thing keeping these two mappings
 * from drifting apart — update BOTH sides (and the parity fixture) when
 * adding a field.
 */
import type { MessageHandlers } from './mavlink';
import { app, addEvent, addToast } from './stores.svelte';
import { t, i18nState } from './i18n.svelte';
import { getModeName, vehicleType } from './modeStore';

export function buildSerialHandlers(): Partial<MessageHandlers> {
  // One-shot per connection, like the backend's _unsupported_fc_warned
  // (reset on connect) — a mixed AP+GCS link must not toast every second.
  let warnedUnsupported = false;
  return {
    onHeartbeat: (msg) => {
      if (!app.drone.connected) {
        app.drone.connected = true;
        addToast(t('conn.serialConnected'), 'success');
      }
      app.drone.vtype_raw = msg.type;
      app.drone.armed = (msg.baseMode & 128) !== 0;
      app.drone.mode_id = msg.customMode;
      // Localized mode NAME — the WS path pushes get_state()'s "mode"
      // (backend _get_vehicle_info: vtype → table → locale) and StatusBar
      // reads it; until 2026-07-14 serial mode left it blank forever.
      app.drone.mode = getModeName(vehicleType(msg.type), msg.customMode, i18nState.locale === 'zh' ? 'zh' : 'en');
      // Autopilot latch mirrors backend handle_heartbeat
      // (mavlink_handlers.py:49-51): ignore 0 (GENERIC/uninit) and 8
      // (INVALID — GCS/relay heartbeats), latch anything else. transport.ts
      // dispatch() refuses FC-bound serial commands while a non-ArduPilot
      // value (not 0/3) is latched, mirroring commands.execute().
      if (msg.autopilot > 0 && msg.autopilot !== 8 && msg.autopilot !== app.drone.autopilot) {
        app.drone.autopilot = msg.autopilot;
        if (msg.autopilot !== 3 && !warnedUnsupported) {
          warnedUnsupported = true;
          const name = msg.autopilot === 12 ? 'PX4' : `autopilot=${msg.autopilot}`;
          addToast(t('conn.unsupportedFc').replace('{fc}', name), 'error', 10000);
        }
      }
    },
    onGlobalPositionInt: (msg) => {
      app.drone.lat = msg.lat;
      app.drone.lon = msg.lon;
      app.drone.alt_msl = msg.altMsl;
      app.drone.alt_rel = msg.altRel;
      // NED vz is positive-down; the UI (and backend get_state) shows
      // positive-up climb rate.
      app.drone.vz = -msg.vz;
      app.drone.hdg = msg.hdg;
    },
    onAttitude: (msg) => {
      app.drone.roll = msg.roll;
      app.drone.pitch = msg.pitch;
      // Backend handle_attitude normalizes yaw to 0..360 for the compass
      // rose; ATTITUDE.yaw is ±π. Mirror it (state-parity finding 2026-07-14:
      // a west-facing vehicle read -90° on the WebSerial path, 270° on WS).
      app.drone.yaw = msg.yaw < 0 ? msg.yaw + 360 : msg.yaw;
    },
    onSysStatus: (msg) => {
      app.drone.voltage = msg.voltage;
      app.drone.current = msg.current;
      app.drone.remaining = msg.remaining;
    },
    onGpsRawInt: (msg) => {
      app.drone.gps_fix_raw = msg.fixType;
      app.drone.gps_sats = msg.sats;
    },
    onVfrHud: (msg) => {
      // gs source differs by design: the backend derives it from
      // GLOBAL_POSITION_INT vx/vy (state.py hypot), serial mode uses the
      // FC's own VFR_HUD.groundspeed — same quantity, so it is excluded
      // from the state-parity compare rather than force-aligned.
      app.drone.gs = msg.groundspeed;
      // airspeed/climb/throttle were dropped here until the 2026-07-14
      // state-parity pass — the serial-mode PFD showed 0 for all three
      // while the WS path (get_state) has always pushed them.
      app.drone.airspeed = msg.airspeed;
      app.drone.climb = msg.climb;
      app.drone.throttle = msg.throttle;
    },
    onRcChannels: (msg) => {
      // Backend handle_rc_channels stores 16 channels (mavlink_handlers.py:349)
      // and every RC widget is written against that WS shape — slice the
      // 18-channel wire message to match.
      app.drone.rc = msg.channels.slice(0, 16);
      app.drone.rc_rssi = msg.rssi;
    },
    onVibration: (msg) => {
      app.drone.vibe = [msg.x, msg.y, msg.z];
      app.drone.vibe_clip = [msg.clip0, msg.clip1, msg.clip2];
    },
    onRawImu: (msg) => {
      // RAW_SENSORS stream is already requested at connect — this keeps
      // the compass-cal sphere fed on the WebSerial path too.
      app.drone.mag = [msg.xmag, msg.ymag, msg.zmag];
    },
    onHomePosition: (msg) => {
      app.drone.home_lat = msg.lat;
      app.drone.home_lon = msg.lon;
    },
    onStatusText: (msg) => {
      // Use addEvent so the 200-entry cap in stores.svelte applies; a direct
      // push would let serial-mode events grow unbounded. (Intentionally NOT
      // state-parity-tested: the backend runs statustext filtering + locale.)
      addEvent({ type: 'event', time: new Date().toLocaleTimeString(), text: msg.text, event_type: 'statustext' });
    },
  };
}
