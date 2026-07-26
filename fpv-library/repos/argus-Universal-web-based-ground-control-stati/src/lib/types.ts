export interface DroneState {
  type: 'state';
  connected: boolean;
  frames: number;
  mode: string;
  mode_id: number;
  armed: boolean;
  roll: number;
  pitch: number;
  yaw: number;
  lat: number;
  lon: number;
  alt_rel: number;
  alt_msl: number;
  gs: number;
  airspeed: number;
  throttle: number;
  climb: number;
  vz: number;
  hdg: number;
  dist_home: number;
  flight_time: number;
  voltage: number;
  current: number;
  remaining: number;
  gps_fix: string;
  gps_fix_raw: number;
  gps_sats: number;
  wp: number;
  wp_idx: number;
  vtype: string;
  vtype_raw: number;
  // MAV_AUTOPILOT enum byte from HEARTBEAT — 3 = ArduPilot, 12 = PX4,
  // 0 = unknown (not yet seen). Surfaced so the FC-adapter layer in
  // src/lib/fc/ can branch on autopilot stack. See CLAUDE.md ## PX4 Status
  // for why the rest of the codebase still assumes ArduPilot.
  autopilot: number;
  mode_btns: [number, string][];
  link_age: number;
  bat_time: number;
  home_lat: number;
  home_lon: number;
  parse_errors: number;
  flight_summary: FlightSummary | null;
  log_active: boolean;
  fw_version: string;
  fw_git: string;
  board_id: number;
  rc: number[];
  rc_rssi: number;
  vibe: number[];
  vibe_clip: number[];
  // Raw magnetometer field (milligauss, RAW_IMU) — compass-cal sample sphere
  mag: number[];
  servo: number[];
  ekf_vel: number;
  ekf_pos_h: number;
  ekf_pos_v: number;
  ekf_compass: number;
  ekf_flags: number;
  wind_dir: number;
  wind_speed: number;
  terrain_alt: number;
  param_count: number;
  param_total: number;
  param_fetching: boolean;
  vehicles: {
    sysid: number;
    lat: number;
    lon: number;
    alt: number;
    hdg: number;
    armed?: boolean;
    mode?: number;
    vtype?: number;
  }[];
  prearm: string[];
  adsb: {
    icao: number;
    lat: number;
    lon: number;
    alt: number;
    hdg: number;
    speed: number;
    vs: number;
    callsign: string;
  }[];
  cells: number[];
  gimbal_pitch: number;
  gimbal_yaw: number;
}

export interface FlightSummary {
  duration: number;
  max_alt: number;
  max_speed: number;
  total_dist: number;
  bat_used: number;
}

export interface DroneEvent {
  type: 'event';
  time: string;
  text: string;
  event_type: string;
  // Monotonic counter assigned by backend.add_event. Survives the events ring
  // buffer trim (see drone_link.py:_events_emitted_total) so frontend code
  // that watches new events can use a high-water-mark cursor instead of array
  // index, which would shift on trim.
  seq?: number;
}

export interface ConnectResult {
  type: 'connect_result';
  ok: boolean;
  error: string;
}

// Reply to a ws 'command' message (backend/ws_manager.py receive_loop —
// commands.execute()'s result dict spread onto {"type": "cmd_result"}).
export interface CmdResult {
  type: 'cmd_result';
  ok: boolean;
  error?: string;
}

export type AltMode = 'relative' | 'msl' | 'terrain';

export interface Waypoint {
  lat: number;
  lon: number;
  alt: number;
  drop: boolean;
  delay: number;
  speed: number;
  type: 'wp' | 'loiter_turns' | 'loiter_time' | 'spline';
  loiter_param: number;
  altMode?: AltMode;
  cmd_servo?: { num: number; pwm: number };
  cmd_roi?: { lat: number; lon: number; alt: number };
  cmd_cam_trig?: { dist: number };
  cmd_yaw?: { deg: number; dir: number };
  cmd_vtol?: { mode: number };
}

export interface RallyPoint {
  lat: number;
  lon: number;
  alt: number;
}

export interface Toast {
  id: number;
  text: string;
  level: 'info' | 'warn' | 'error' | 'success';
  count: number;
}

export interface Param {
  name: string;
  value: number;
  type: number;
  index: number;
}

export interface ParamBatchMsg {
  type: 'param_batch';
  params: {
    type: string;
    name: string;
    value: number;
    ptype: number;
    index: number;
    total: number;
    received: number;
  }[];
}

export interface ParamsCompleteMsg {
  type: 'params_complete';
  count: number;
}

export interface ParamTimeoutMsg {
  type: 'param_timeout';
  missing: number;
}

export interface MissionDownloadedMsg {
  type: 'mission_downloaded';
  waypoints: Waypoint[];
}

export interface LogListMsg {
  type: 'log_list';
  logs: { id: number; size: number; time_utc: number }[];
}

export interface LogProgressMsg {
  type: 'log_progress';
  received: number;
  total: number;
}

export interface LogChunkMsg {
  type: 'log_chunk';
  id: number;
  ofs: number;
  data: string; // base64-encoded slice of the log
}

export interface LogCompleteMsg {
  type: 'log_complete';
  id: number;
  size: number;
  /** Optional legacy field — the backend used to send the full base64
   * blob here. Now sent in log_chunk messages; absent on log_complete. */
  data?: string;
  /** True if the FC signalled EOF mid-stream (count=0). */
  truncated?: boolean;
}

export interface InspectorMsg {
  type: 'inspector';
  messages: {
    id: number;
    name: string;
    hz: number;
    count: number;
    size: number;
    last_fields: Record<string, unknown>;
  }[];
}

export interface ConsoleOutputMsg {
  type: 'console_output';
  text: string;
}

export type WSMessage =
  | DroneState
  | DroneEvent
  | ConnectResult
  | CmdResult
  | ParamBatchMsg
  | ParamsCompleteMsg
  | ParamTimeoutMsg
  | MissionDownloadedMsg
  | LogListMsg
  | LogProgressMsg
  | LogChunkMsg
  | LogCompleteMsg
  | InspectorMsg
  | ConsoleOutputMsg;

export const defaultState: DroneState = {
  type: 'state',
  connected: false,
  frames: 0,
  mode: '---',
  mode_id: 0,
  armed: false,
  roll: 0,
  pitch: 0,
  yaw: 0,
  lat: 0,
  lon: 0,
  alt_rel: 0,
  alt_msl: 0,
  gs: 0,
  airspeed: 0,
  throttle: 0,
  climb: 0,
  vz: 0,
  hdg: 0,
  dist_home: 0,
  flight_time: 0,
  voltage: 0,
  current: 0,
  remaining: -1,
  gps_fix: '---',
  gps_fix_raw: 0,
  gps_sats: 0,
  wp: 0,
  wp_idx: 0,
  vtype: '',
  vtype_raw: 0,
  autopilot: 0,
  mode_btns: [],
  link_age: -1,
  bat_time: -1,
  home_lat: 0,
  home_lon: 0,
  parse_errors: 0,
  flight_summary: null,
  log_active: false,
  fw_version: '',
  fw_git: '',
  board_id: 0,
  rc: [],
  rc_rssi: 0,
  vibe: [0, 0, 0],
  vibe_clip: [0, 0, 0],
  mag: [0, 0, 0],
  servo: [],
  ekf_vel: 0,
  ekf_pos_h: 0,
  ekf_pos_v: 0,
  ekf_compass: 0,
  ekf_flags: 0,
  wind_dir: 0,
  wind_speed: 0,
  terrain_alt: -1,
  param_count: 0,
  param_total: -1,
  param_fetching: false,
  vehicles: [],
  prearm: [],
  adsb: [],
  cells: [],
  gimbal_pitch: 0,
  gimbal_yaw: 0,
};
