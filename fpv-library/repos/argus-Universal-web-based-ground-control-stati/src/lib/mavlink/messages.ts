/**
 * MAVLink message decoders and encoders for the most common messages.
 *
 * Each decoder takes a DataView (the payload) and returns a typed object.
 * Encoders return a Uint8Array payload ready for encodeFrame().
 */

import type { MavFrame } from './codec';

/* ── Decoded message types ── */

export interface Heartbeat {
  customMode: number;
  type: number;
  autopilot: number;
  baseMode: number;
  systemStatus: number;
  mavlinkVersion: number;
}

export interface SysStatus {
  voltage: number;
  current: number;
  remaining: number;
}

export interface GpsRawInt {
  fixType: number;
  lat: number;
  lon: number;
  alt: number;
  sats: number;
}

export interface Attitude {
  roll: number;
  pitch: number;
  yaw: number;
}

export interface GlobalPositionInt {
  lat: number;
  lon: number;
  altMsl: number;
  altRel: number;
  vx: number;
  vy: number;
  vz: number;
  hdg: number;
}

export interface VfrHud {
  airspeed: number;
  groundspeed: number;
  heading: number;
  throttle: number;
  alt: number;
  climb: number;
}

export interface RcChannels {
  chancount: number;
  channels: number[];
  rssi: number;
}

export interface ServoOutput {
  outputs: number[];
}

export interface StatusText {
  severity: number;
  text: string;
}

export interface ParamValue {
  paramId: string;
  paramValue: number;
  paramType: number;
  paramCount: number;
  paramIndex: number;
}

export interface CommandAck {
  command: number;
  result: number;
}

export interface MissionCurrent {
  seq: number;
}

export interface MissionAck {
  type: number;
}

export interface MissionCount {
  count: number;
}

export interface MissionItemInt {
  seq: number;
  frame: number;
  command: number;
  current: number;
  autocontinue: number;
  param1: number;
  param2: number;
  param3: number;
  param4: number;
  x: number; // lat * 1e7
  y: number; // lon * 1e7
  z: number; // alt
}

export interface HomePosition {
  lat: number;
  lon: number;
  alt: number;
}

// RAW_IMU (27) — mag fields only (milligauss); feeds the compass-cal sphere.
// Layout per ArduPilot GCS_Common.cpp:2237 send_raw_imu: time_usec u64 @0,
// acc/gyro i16 pairs, xmag/ymag/zmag i16 @20/22/24.
export interface RawImu {
  xmag: number;
  ymag: number;
  zmag: number;
}

export interface Vibration {
  x: number;
  y: number;
  z: number;
  clip0: number;
  clip1: number;
  clip2: number;
}

export interface Wind {
  direction: number;
  speed: number;
}

export interface AutopilotVersion {
  flightSwVersion: number;
  boardVersion: number;
  uid: bigint;
}

export interface MissionItemReached {
  seq: number;
}

export interface MissionRequest {
  seq: number;
  missionType: number;
}

export interface LogEntry {
  id: number;
  numLogs: number;
  lastLogNum: number;
  timeUtc: number;
  size: number;
}

export interface LogData {
  ofs: number;
  id: number;
  count: number;
  data: Uint8Array;
}

export interface SerialControl {
  count: number;
  data: Uint8Array;
}

export interface TerrainReport {
  lat: number;
  lon: number;
  terrainHeight: number;
  currentHeight: number;
}

export interface BatteryStatus {
  cells: number[];
  voltage: number;
  current: number;
  remaining: number;
}

export interface MountStatus {
  pitch: number;
  yaw: number;
}

export interface MagCalProgress {
  compassId: number;
  completionPct: number;
  calStatus: number;
}

export interface MagCalReport {
  compassId: number;
  calStatus: number;
  autosaved: number;
}

export interface EkfStatus {
  velVar: number;
  posHVar: number;
  posVVar: number;
  compassVar: number;
  terrainVar: number;
  flags: number;
}

export interface AdsbVehicle {
  icao: number;
  lat: number;
  lon: number;
  alt: number;
  hdg: number;
  speed: number;
  vs: number;
  callsign: string;
}

/* ── Decoders ── */

export function decodeHeartbeat(p: DataView): Heartbeat {
  return {
    customMode: p.getUint32(0, true),
    type: p.getUint8(4),
    autopilot: p.getUint8(5),
    baseMode: p.getUint8(6),
    systemStatus: p.getUint8(7),
    mavlinkVersion: p.getUint8(8),
  };
}

export function decodeSysStatus(p: DataView): SysStatus {
  return {
    voltage: p.getUint16(14, true) / 1000,
    current: p.getInt16(16, true) / 100,
    remaining: p.getInt8(30),
  };
}

export function decodeGpsRawInt(p: DataView): GpsRawInt {
  return {
    fixType: p.getUint8(28),
    lat: p.getInt32(8, true) / 1e7,
    lon: p.getInt32(12, true) / 1e7,
    alt: p.getInt32(16, true) / 1000,
    sats: p.byteLength > 29 ? p.getUint8(29) : 0,
  };
}

export function decodeAttitude(p: DataView): Attitude {
  return {
    roll: (p.getFloat32(4, true) * 180) / Math.PI,
    pitch: (p.getFloat32(8, true) * 180) / Math.PI,
    yaw: (p.getFloat32(12, true) * 180) / Math.PI,
  };
}

export function decodeGlobalPositionInt(p: DataView): GlobalPositionInt {
  return {
    lat: p.getInt32(4, true) / 1e7,
    lon: p.getInt32(8, true) / 1e7,
    altMsl: p.getInt32(12, true) / 1000,
    altRel: p.getInt32(16, true) / 1000,
    vx: p.getInt16(20, true) / 100,
    vy: p.getInt16(22, true) / 100,
    vz: p.getInt16(24, true) / 100,
    hdg: p.getUint16(26, true) / 100,
  };
}

export function decodeVfrHud(p: DataView): VfrHud {
  return {
    airspeed: p.getFloat32(0, true),
    groundspeed: p.getFloat32(4, true),
    alt: p.getFloat32(8, true),
    climb: p.getFloat32(12, true),
    heading: p.getInt16(16, true),
    throttle: p.getUint16(18, true),
  };
}

export function decodeRcChannels(p: DataView): RcChannels {
  const channels: number[] = [];
  for (let i = 0; i < 18 && 4 + i * 2 + 1 < p.byteLength; i++) {
    channels.push(p.getUint16(4 + i * 2, true));
  }
  const chancount = p.byteLength > 40 ? p.getUint8(40) : 0;
  return { chancount, channels, rssi: p.byteLength > 41 ? p.getUint8(41) : 0 };
}

export function decodeServoOutput(p: DataView): ServoOutput {
  // SERVO_OUTPUT_RAW (36) wire layout (MAVLink 2, sorted by size):
  //   time_usec(u32, 0..3), servo1..8 raw(u16, 4..19), port(u8, 20),
  //   extensions: servo9..16 raw(u16, 21..36).
  // servo9-16 sit AFTER the port byte, not contiguous with servo1-8.
  const outputs: number[] = [];
  for (let i = 0; i < 8 && 4 + i * 2 + 1 < p.byteLength; i++) {
    outputs.push(p.getUint16(4 + i * 2, true));
  }
  for (let i = 0; i < 8 && 21 + i * 2 + 1 < p.byteLength; i++) {
    outputs.push(p.getUint16(21 + i * 2, true));
  }
  while (outputs.length < 16) outputs.push(0);
  return { outputs };
}

export function decodeStatusText(p: DataView): StatusText {
  const severity = p.getUint8(0);
  const bytes = new Uint8Array(p.buffer, p.byteOffset + 1, Math.min(p.byteLength - 1, 50));
  let end = bytes.indexOf(0);
  if (end < 0) end = bytes.length;
  const text = new TextDecoder().decode(bytes.slice(0, end));
  return { severity, text };
}

export function decodeParamValue(p: DataView): ParamValue {
  const bytes = new Uint8Array(p.buffer, p.byteOffset + 8, 16);
  let end = bytes.indexOf(0);
  if (end < 0) end = 16;
  const paramId = new TextDecoder().decode(bytes.slice(0, end));
  return {
    paramValue: p.getFloat32(0, true),
    paramId,
    paramType: p.getUint8(24),
    paramCount: p.getUint16(4, true),
    paramIndex: p.getUint16(6, true),
  };
}

export function decodeCommandAck(p: DataView): CommandAck {
  return { command: p.getUint16(0, true), result: p.getUint8(2) };
}

export function decodeMissionCurrent(p: DataView): MissionCurrent {
  return { seq: p.getUint16(0, true) };
}

export function decodeMissionAck(p: DataView): MissionAck {
  return { type: p.getUint8(2) };
}

export function decodeMissionCount(p: DataView): MissionCount {
  return { count: p.getUint16(0, true) };
}

export function decodeMissionItemInt(p: DataView): MissionItemInt {
  return {
    param1: p.getFloat32(0, true),
    param2: p.getFloat32(4, true),
    param3: p.getFloat32(8, true),
    param4: p.getFloat32(12, true),
    x: p.getInt32(16, true),
    y: p.getInt32(20, true),
    z: p.getFloat32(24, true),
    seq: p.getUint16(28, true),
    command: p.getUint16(30, true),
    frame: p.getUint8(34),
    current: p.getUint8(35),
    autocontinue: p.getUint8(36),
  };
}

export function decodeHomePosition(p: DataView): HomePosition {
  return {
    lat: p.getInt32(0, true) / 1e7,
    lon: p.getInt32(4, true) / 1e7,
    alt: p.getInt32(8, true) / 1000,
  };
}

export function decodeRawImu(p: DataView): RawImu {
  return {
    xmag: p.getInt16(20, true),
    ymag: p.getInt16(22, true),
    zmag: p.getInt16(24, true),
  };
}

export function decodeVibration(p: DataView): Vibration {
  return {
    x: p.getFloat32(8, true),
    y: p.getFloat32(12, true),
    z: p.getFloat32(16, true),
    clip0: p.getUint32(20, true),
    clip1: p.getUint32(24, true),
    clip2: p.getUint32(28, true),
  };
}

export function decodeWind(p: DataView): Wind {
  return {
    direction: p.getFloat32(0, true),
    speed: p.getFloat32(4, true),
  };
}

export function decodeMissionItemReached(p: DataView): MissionItemReached {
  return { seq: p.getUint16(0, true) };
}

export function decodeMissionRequest(p: DataView): MissionRequest {
  // 0..1 seq, 2 target_system, 3 target_component, 4 mission_type
  return { seq: p.getUint16(0, true), missionType: p.getUint8(4) };
}

export function decodeLogEntry(p: DataView): LogEntry {
  // LOG_ENTRY (118) wire layout (sorted by size):
  //   0..3   time_utc (u32)
  //   4..7   size (u32)
  //   8..9   id (u16)
  //   10..11 num_logs (u16)
  //   12..13 last_log_num (u16)
  return {
    timeUtc: p.getUint32(0, true),
    size: p.getUint32(4, true),
    id: p.getUint16(8, true),
    numLogs: p.getUint16(10, true),
    lastLogNum: p.getUint16(12, true),
  };
}

export function decodeLogData(p: DataView): LogData {
  // LOG_DATA (120): 0..3 ofs(u32), 4..5 id(u16), 6 count(u8), 7..96 data[90]
  const count = p.getUint8(6);
  const dataLen = Math.min(count, p.byteLength - 7);
  return {
    ofs: p.getUint32(0, true),
    id: p.getUint16(4, true),
    count,
    data: new Uint8Array(p.buffer, p.byteOffset + 7, Math.max(0, dataLen)),
  };
}

export function decodeSerialControl(p: DataView): SerialControl {
  // SERIAL_CONTROL (126): 0..3 baudrate, 4..5 timeout, 6 device, 7 flags,
  //                       8 count, 9..78 data
  const count = p.getUint8(8);
  const dataLen = Math.min(count, p.byteLength - 9);
  return {
    count,
    data: new Uint8Array(p.buffer, p.byteOffset + 9, Math.max(0, dataLen)),
  };
}

export function decodeTerrainReport(p: DataView): TerrainReport {
  // TERRAIN_REPORT (136): 0 lat(i32), 4 lon(i32),
  //                       8 terrain_height(f), 12 current_height(f),
  //                       16 spacing(u16), 18 pending(u16), 20 loaded(u16)
  return {
    lat: p.getInt32(0, true) / 1e7,
    lon: p.getInt32(4, true) / 1e7,
    terrainHeight: p.getFloat32(8, true),
    currentHeight: p.getFloat32(12, true),
  };
}

export function decodeBatteryStatus(p: DataView): BatteryStatus {
  // BATTERY_STATUS (147) wire layout (sorted by size, partial):
  //   0..3 current_consumed(i32), 4..7 energy_consumed(i32),
  //   8..9 temperature(i16),
  //   10..29 voltages[10] (u16) — cells in mV, 0xFFFF == not present
  //   30..31 current_battery(i16), 32 id(u8), 33 battery_function(u8),
  //   34 type(u8), 35 battery_remaining(i8)
  const cells: number[] = [];
  for (let i = 0; i < 10; i++) {
    const v = p.getUint16(10 + i * 2, true);
    if (v === 0xffff) break;
    cells.push(v / 1000);
  }
  return {
    cells,
    voltage: cells.reduce((a, b) => a + b, 0),
    current: p.getInt16(30, true) / 100,
    remaining: p.getInt8(35),
  };
}

export function decodeMountStatus(p: DataView): MountStatus {
  // MOUNT_STATUS (158): 0..3 pitch_cdeg(i32), 4..7 roll_cdeg(i32),
  //                     8..11 yaw_cdeg(i32), 12 target_system, 13 target_component
  return {
    pitch: p.getInt32(0, true) / 100,
    yaw: p.getInt32(8, true) / 100,
  };
}

export function decodeMagCalProgress(p: DataView): MagCalProgress {
  // MAG_CAL_PROGRESS (191): 0..11 direction xyz(f),
  //                         12 compass_id, 13 cal_mask, 14 cal_status,
  //                         15 attempt, 16 completion_pct, 17..26 mask[10]
  return {
    compassId: p.getUint8(12),
    calStatus: p.getUint8(14),
    completionPct: p.getUint8(16),
  };
}

export function decodeMagCalReport(p: DataView): MagCalReport {
  // MAG_CAL_REPORT (192) — see backend handle_mag_cal_report for layout.
  // cal_status at offset 42.
  return {
    compassId: p.getUint8(40),
    calStatus: p.getUint8(42),
    autosaved: p.getUint8(43),
  };
}

export function decodeEkfStatus(p: DataView): EkfStatus {
  // EKF_STATUS_REPORT (193): 0..3 velocity_var(f), 4..7 pos_horiz_var(f),
  //                          8..11 pos_vert_var(f), 12..15 compass_var(f),
  //                          16..19 terrain_alt_var(f), 20..21 flags(u16)
  return {
    velVar: p.getFloat32(0, true),
    posHVar: p.getFloat32(4, true),
    posVVar: p.getFloat32(8, true),
    compassVar: p.getFloat32(12, true),
    terrainVar: p.getFloat32(16, true),
    flags: p.getUint16(20, true),
  };
}

export function decodeAdsbVehicle(p: DataView): AdsbVehicle {
  // ADSB_VEHICLE (246) wire layout (sorted by size):
  //   0..3 icao(u32), 4..7 lat(i32), 8..11 lon(i32), 12..15 alt(i32),
  //   16..17 hdg(u16), 18..19 horizontal_velocity(u16),
  //   20..21 vertical_velocity(i16), 22..23 flags(u16), 24..25 squawk(u16),
  //   26 altitude_type, 27..35 callsign[9]
  const callsignBytes = new Uint8Array(p.buffer, p.byteOffset + 27, Math.min(9, p.byteLength - 27));
  let end = callsignBytes.indexOf(0);
  if (end < 0) end = callsignBytes.length;
  return {
    icao: p.getUint32(0, true),
    lat: p.getInt32(4, true) / 1e7,
    lon: p.getInt32(8, true) / 1e7,
    alt: p.getInt32(12, true) / 1000,
    hdg: p.getUint16(16, true) / 100,
    speed: p.getUint16(18, true) / 100,
    vs: p.getInt16(20, true) / 100,
    callsign: new TextDecoder().decode(callsignBytes.slice(0, end)),
  };
}

export function decodeAutopilotVersion(p: DataView): AutopilotVersion {
  // AUTOPILOT_VERSION (148) — partial decode of useful fields.
  //   0..7 capabilities (u64)
  //   8..11 uid (u64 low) — we expose flightSwVersion + board_version instead
  //   16..19 flight_sw_version (u32)
  //   28..31 board_version (u32)
  return {
    flightSwVersion: p.getUint32(16, true),
    boardVersion: p.getUint32(28, true),
    uid: p.getBigUint64(8, true),
  };
}

/* ── Encoders ── */

export function encodeHeartbeat(sysType: number = 6, autopilot: number = 8): Uint8Array {
  const buf = new Uint8Array(9);
  const dv = new DataView(buf.buffer);
  dv.setUint32(0, 0, true); // custom_mode
  dv.setUint8(4, sysType); // MAV_TYPE_GCS = 6
  dv.setUint8(5, autopilot); // MAV_AUTOPILOT_INVALID = 8
  dv.setUint8(6, 0); // base_mode
  dv.setUint8(7, 4); // system_status = MAV_STATE_ACTIVE (matches backend send_heartbeat)
  dv.setUint8(8, 3); // mavlink_version
  return buf;
}

export function encodeCommandLong(
  targetSys: number,
  targetComp: number,
  command: number,
  confirmation: number,
  p1: number,
  p2: number,
  p3: number,
  p4: number,
  p5: number,
  p6: number,
  p7: number,
): Uint8Array {
  const buf = new Uint8Array(33);
  const dv = new DataView(buf.buffer);
  dv.setFloat32(0, p1, true);
  dv.setFloat32(4, p2, true);
  dv.setFloat32(8, p3, true);
  dv.setFloat32(12, p4, true);
  dv.setFloat32(16, p5, true);
  dv.setFloat32(20, p6, true);
  dv.setFloat32(24, p7, true);
  dv.setUint16(28, command, true);
  dv.setUint8(30, targetSys);
  dv.setUint8(31, targetComp);
  dv.setUint8(32, confirmation);
  return buf;
}

export function encodeSetMode(targetSys: number, baseMode: number, customMode: number): Uint8Array {
  const buf = new Uint8Array(6);
  const dv = new DataView(buf.buffer);
  dv.setUint32(0, customMode, true);
  dv.setUint8(4, targetSys);
  dv.setUint8(5, baseMode);
  return buf;
}

export function encodeParamRequestList(targetSys: number, targetComp: number): Uint8Array {
  const buf = new Uint8Array(2);
  buf[0] = targetSys;
  buf[1] = targetComp;
  return buf;
}

export function encodeParamRequestRead(targetSys: number, targetComp: number, index: number): Uint8Array {
  // PARAM_REQUEST_READ (20), size-sorted wire layout: param_index i16 @0,
  // target_system u8 @2, target_component u8 @3, param_id char[16] @4.
  // An all-zero name means "look up by index" — ArduPilot GCS_Param.cpp:396
  // takes the index branch whenever param_index != -1. Byte-identical twin
  // of backend/param_manager.py:_request_one, with one accepted delta:
  // the backend hardcodes target_component=1 while callers here pass the
  // heartbeat-learned compid (identical whenever the FC heartbeats compid 1,
  // i.e. every ArduPilot autopilot).
  const buf = new Uint8Array(20);
  const dv = new DataView(buf.buffer);
  dv.setInt16(0, index, true);
  dv.setUint8(2, targetSys);
  dv.setUint8(3, targetComp);
  return buf;
}

export function encodeParamSet(
  targetSys: number,
  targetComp: number,
  paramId: string,
  value: number,
  paramType: number,
): Uint8Array {
  const buf = new Uint8Array(23);
  const dv = new DataView(buf.buffer);
  dv.setFloat32(0, value, true);
  dv.setUint8(4, targetSys);
  dv.setUint8(5, targetComp);
  const enc = new TextEncoder();
  const nameBytes = enc.encode(paramId);
  buf.set(nameBytes.slice(0, 16), 6);
  dv.setUint8(22, paramType);
  return buf;
}

export function encodeRequestDataStream(
  targetSys: number,
  targetComp: number,
  streamId: number,
  rate: number,
  startStop: number,
): Uint8Array {
  const buf = new Uint8Array(6);
  const dv = new DataView(buf.buffer);
  dv.setUint16(0, rate, true);
  dv.setUint8(2, targetSys);
  dv.setUint8(3, targetComp);
  dv.setUint8(4, streamId);
  dv.setUint8(5, startStop);
  return buf;
}

/**
 * MISSION_COUNT (msg 44, 4-byte payload). Sent by the GCS to start an upload;
 * the FC then requests each item with MISSION_REQUEST(_INT) (msg 40/51) and
 * acknowledges the batch with MISSION_ACK (msg 47).
 *
 * missionType: 0 = MAV_MISSION_TYPE_MISSION, 1 = FENCE, 2 = RALLY.
 */
export function encodeMissionCount(
  targetSys: number,
  targetComp: number,
  count: number,
  missionType: number = 0,
): Uint8Array {
  const buf = new Uint8Array(4);
  const dv = new DataView(buf.buffer);
  dv.setUint16(0, count, true);
  dv.setUint8(2, targetSys);
  dv.setUint8(3, targetComp);
  // missionType is an extension byte appended by MAVLink 2 — only send it
  // when non-zero so the trim-friendly wire matches the backend's 4-byte
  // packing (see backend/commands/_helpers.py:send_mission_count).
  if (missionType !== 0) {
    const ext = new Uint8Array(5);
    ext.set(buf);
    ext[4] = missionType;
    return ext;
  }
  return buf;
}

/**
 * MISSION_ITEM_INT (msg 73, 38-byte payload). Wire layout matches the
 * pymavlink ordering and the backend's send_mission_item_int helper at
 * backend/commands/_helpers.py:59.
 *
 * frame: 3 = GLOBAL_RELATIVE_ALT_INT for nav waypoints (cmd 16/18/19/21/22/82),
 *        2 = MISSION for everything else (delays / servo / ROI / cam_trig / yaw).
 * current: 1 only on seq 0 (the home item), 0 otherwise.
 */
export function encodeMissionItemInt(
  targetSys: number,
  targetComp: number,
  seq: number,
  command: number,
  frame: number,
  current: number,
  autocontinue: number,
  missionType: number,
  p1: number,
  p2: number,
  p3: number,
  p4: number,
  x: number,
  y: number,
  z: number,
): Uint8Array {
  const buf = new Uint8Array(38);
  const dv = new DataView(buf.buffer);
  dv.setFloat32(0, p1, true);
  dv.setFloat32(4, p2, true);
  dv.setFloat32(8, p3, true);
  dv.setFloat32(12, p4, true);
  dv.setInt32(16, x, true);
  dv.setInt32(20, y, true);
  dv.setFloat32(24, z, true);
  dv.setUint16(28, seq, true);
  dv.setUint16(30, command, true);
  dv.setUint8(32, targetSys);
  dv.setUint8(33, targetComp);
  dv.setUint8(34, frame);
  dv.setUint8(35, current);
  dv.setUint8(36, autocontinue);
  dv.setUint8(37, missionType);
  return buf;
}

/**
 * MISSION_CLEAR_ALL (msg 45, 2- or 3-byte payload). Wipes the on-FC mission
 * for the given mission type before starting a fresh upload (or just to
 * abandon an in-progress one).
 */
export function encodeMissionClearAll(targetSys: number, targetComp: number, missionType: number = 0): Uint8Array {
  if (missionType !== 0) {
    return new Uint8Array([targetSys, targetComp, missionType]);
  }
  return new Uint8Array([targetSys, targetComp]);
}

/**
 * COMMAND_ACK (msg 77, normally RECEIVED from FC). This encoder exists only
 * for one use case: the AccelCal "advance to next orientation" protocol,
 * where the GCS sends a COMMAND_ACK *back to the FC* with semantics the
 * MAVLink spec does not document. The handler is at
 * libraries/AP_AccelCal/AP_AccelCal.cpp:367-393 — it requires
 *   packet.command <= 6              (NOT the MAV_CMD value 42429)
 *   packet.result == TEMPORARILY_REJECTED(1)  (NOT ACCEPTED(0))
 * QGC sends command=0, result=1 — we mirror that. Do NOT "fix" this to
 * look like a normal ACK; it will silently break accel calibration.
 *
 * Backend mirror: backend/commands/_setup.py:cmd_cal_accel_next at
 * backend/commands/_setup.py:47-58. Same payload, same 3-byte trim.
 */
export function encodeCommandAck(command: number, result: number): Uint8Array {
  const buf = new Uint8Array(3);
  const dv = new DataView(buf.buffer);
  dv.setUint16(0, command, true);
  dv.setUint8(2, result);
  return buf;
}

/**
 * MISSION_SET_CURRENT (msg 41, 4-byte payload). Tells the FC to jump to a
 * specific waypoint seq during AUTO flight.
 * ArduPilot: GCS_MAVLINK::handle_mission_set_current (GCS_Common.cpp)
 */
export function encodeMissionSetCurrent(targetSys: number, targetComp: number, seq: number): Uint8Array {
  const buf = new Uint8Array(4);
  const dv = new DataView(buf.buffer);
  dv.setUint16(0, seq, true);
  dv.setUint8(2, targetSys);
  dv.setUint8(3, targetComp);
  return buf;
}

/**
 * MISSION_REQUEST_LIST (msg 43, 3-byte payload). Asks the FC to start a
 * mission download — it responds with MISSION_COUNT (44).
 */
export function encodeMissionRequestList(targetSys: number, targetComp: number, missionType: number = 0): Uint8Array {
  if (missionType !== 0) {
    return new Uint8Array([targetSys, targetComp, missionType]);
  }
  return new Uint8Array([targetSys, targetComp, 0]);
}

/**
 * MISSION_REQUEST_INT (msg 51, 5-byte payload). Asks the FC for a specific
 * mission item by seq. Layout matches backend's _request_dl_item at
 * backend/mavlink_handlers.py:468 → <HBBB>.
 */
export function encodeMissionRequestInt(
  targetSys: number,
  targetComp: number,
  seq: number,
  missionType: number = 0,
): Uint8Array {
  const buf = new Uint8Array(5);
  const dv = new DataView(buf.buffer);
  dv.setUint16(0, seq, true);
  dv.setUint8(2, targetSys);
  dv.setUint8(3, targetComp);
  dv.setUint8(4, missionType);
  return buf;
}

/**
 * MISSION_ACK (msg 47, 3 or 4-byte payload). Sent by the GCS to acknowledge
 * the end of a mission download (type=0 = MAV_MISSION_ACCEPTED). Matches the
 * backend's send at handle_mission_item_int line 465 — <BBB>.
 */
export function encodeMissionAck(
  targetSys: number,
  targetComp: number,
  type: number = 0,
  missionType: number = 0,
): Uint8Array {
  if (missionType !== 0) {
    return new Uint8Array([targetSys, targetComp, type, missionType]);
  }
  return new Uint8Array([targetSys, targetComp, type]);
}

/**
 * LOG_REQUEST_LIST (msg 117, 6-byte payload). Asks the FC for log inventory.
 * The FC streams a LOG_ENTRY (msg 118) per log file in the range [start, end];
 * the entry with id == last_log_num signals end-of-list. Pass start=0,
 * end=0xFFFF to request the full inventory.
 */
export function encodeLogRequestList(
  targetSys: number,
  targetComp: number,
  start: number = 0,
  end: number = 0xffff,
): Uint8Array {
  const buf = new Uint8Array(6);
  const dv = new DataView(buf.buffer);
  dv.setUint16(0, start, true);
  dv.setUint16(2, end, true);
  dv.setUint8(4, targetSys);
  dv.setUint8(5, targetComp);
  return buf;
}

/**
 * LOG_REQUEST_DATA (msg 119, 12-byte payload). Requests a byte range of a
 * specific log. The FC responds with one or more LOG_DATA (msg 120) chunks,
 * each ≤ 90 bytes. count is the maximum total bytes to send back; backend
 * uses 90*50 = 4500 as the per-request window (see send_cmd in
 * backend/commands/_setup.py:cmd_log_download).
 */
export function encodeLogRequestData(
  targetSys: number,
  targetComp: number,
  id: number,
  ofs: number,
  count: number,
): Uint8Array {
  const buf = new Uint8Array(12);
  const dv = new DataView(buf.buffer);
  dv.setUint32(0, ofs, true);
  dv.setUint32(4, count, true);
  dv.setUint16(8, id, true);
  dv.setUint8(10, targetSys);
  dv.setUint8(11, targetComp);
  return buf;
}

/**
 * LOG_REQUEST_END (msg 122, 2-byte payload). Tells the FC to stop streaming
 * any in-flight log data — used as the "cancel" path during a download.
 */
export function encodeLogRequestEnd(targetSys: number, targetComp: number): Uint8Array {
  return new Uint8Array([targetSys, targetComp]);
}

/**
 * Pad a DataView's underlying payload to at least `minBytes` with trailing zeros.
 * MAVLink 2 senders may zero-trim trailing zero bytes; receivers must treat
 * the missing bytes as zero. Without this, decoders calling getUint16(2) etc.
 * on a trimmed payload throw RangeError. Returns a fresh DataView that the
 * decoder can read from at any offset up to minBytes-1.
 */
function padPayload(p: DataView, minBytes: number): DataView {
  if (p.byteLength >= minBytes) return p;
  const padded = new Uint8Array(minBytes);
  padded.set(new Uint8Array(p.buffer, p.byteOffset, p.byteLength));
  return new DataView(padded.buffer);
}

/**
 * Dispatch a decoded frame to the appropriate handler. Each msg id is paired
 * with the maximum byte offset its decoder reads, so we zero-pad up to that
 * size before invoking the decoder.
 */
export function dispatchFrame(frame: MavFrame, handlers: Partial<MessageHandlers>): void {
  const pl = frame.payload;
  switch (frame.msgId) {
    case 0:
      handlers.onHeartbeat?.(decodeHeartbeat(padPayload(pl, 9)), frame);
      break;
    case 1:
      handlers.onSysStatus?.(decodeSysStatus(padPayload(pl, 31)), frame);
      break;
    case 24:
      handlers.onGpsRawInt?.(decodeGpsRawInt(padPayload(pl, 30)), frame);
      break;
    case 30:
      handlers.onAttitude?.(decodeAttitude(padPayload(pl, 28)), frame);
      break;
    case 33:
      handlers.onGlobalPositionInt?.(decodeGlobalPositionInt(padPayload(pl, 28)), frame);
      break;
    case 65:
      handlers.onRcChannels?.(decodeRcChannels(padPayload(pl, 42)), frame);
      break;
    case 36:
      handlers.onServoOutput?.(decodeServoOutput(padPayload(pl, 37)), frame);
      break;
    case 74:
      handlers.onVfrHud?.(decodeVfrHud(padPayload(pl, 20)), frame);
      break;
    case 22:
      handlers.onParamValue?.(decodeParamValue(padPayload(pl, 25)), frame);
      break;
    case 77:
      handlers.onCommandAck?.(decodeCommandAck(padPayload(pl, 10)), frame);
      break;
    case 42:
      handlers.onMissionCurrent?.(decodeMissionCurrent(padPayload(pl, 2)), frame);
      break;
    case 47:
      handlers.onMissionAck?.(decodeMissionAck(padPayload(pl, 4)), frame);
      break;
    case 44:
      handlers.onMissionCount?.(decodeMissionCount(padPayload(pl, 4)), frame);
      break;
    case 73:
      handlers.onMissionItemInt?.(decodeMissionItemInt(padPayload(pl, 38)), frame);
      break;
    case 242:
      handlers.onHomePosition?.(decodeHomePosition(padPayload(pl, 60)), frame);
      break;
    case 241:
      handlers.onVibration?.(decodeVibration(padPayload(pl, 32)), frame);
      break;
    case 27:
      handlers.onRawImu?.(decodeRawImu(padPayload(pl, 26)), frame);
      break;
    case 168:
      handlers.onWind?.(decodeWind(padPayload(pl, 12)), frame);
      break;
    case 253:
      handlers.onStatusText?.(decodeStatusText(padPayload(pl, 51)), frame);
      break;
    case 40:
      handlers.onMissionRequest?.(decodeMissionRequest(padPayload(pl, 5)), frame);
      break;
    case 46:
      handlers.onMissionItemReached?.(decodeMissionItemReached(padPayload(pl, 2)), frame);
      break;
    case 51:
      handlers.onMissionRequest?.(decodeMissionRequest(padPayload(pl, 5)), frame);
      break;
    case 118:
      handlers.onLogEntry?.(decodeLogEntry(padPayload(pl, 14)), frame);
      break;
    case 120:
      handlers.onLogData?.(decodeLogData(padPayload(pl, 97)), frame);
      break;
    case 126:
      handlers.onSerialControl?.(decodeSerialControl(padPayload(pl, 79)), frame);
      break;
    case 136:
      handlers.onTerrainReport?.(decodeTerrainReport(padPayload(pl, 22)), frame);
      break;
    case 147:
      handlers.onBatteryStatus?.(decodeBatteryStatus(padPayload(pl, 36)), frame);
      break;
    case 148:
      handlers.onAutopilotVersion?.(decodeAutopilotVersion(padPayload(pl, 60)), frame);
      break;
    case 158:
      handlers.onMountStatus?.(decodeMountStatus(padPayload(pl, 14)), frame);
      break;
    case 191:
      handlers.onMagCalProgress?.(decodeMagCalProgress(padPayload(pl, 27)), frame);
      break;
    case 192:
      handlers.onMagCalReport?.(decodeMagCalReport(padPayload(pl, 44)), frame);
      break;
    case 193:
      handlers.onEkfStatus?.(decodeEkfStatus(padPayload(pl, 22)), frame);
      break;
    case 246:
      handlers.onAdsbVehicle?.(decodeAdsbVehicle(padPayload(pl, 38)), frame);
      break;
    default:
      handlers.onUnknown?.(frame);
      break;
  }
}

export interface MessageHandlers {
  onHeartbeat: (msg: Heartbeat, frame: MavFrame) => void;
  onSysStatus: (msg: SysStatus, frame: MavFrame) => void;
  onGpsRawInt: (msg: GpsRawInt, frame: MavFrame) => void;
  onAttitude: (msg: Attitude, frame: MavFrame) => void;
  onGlobalPositionInt: (msg: GlobalPositionInt, frame: MavFrame) => void;
  onRcChannels: (msg: RcChannels, frame: MavFrame) => void;
  onServoOutput: (msg: ServoOutput, frame: MavFrame) => void;
  onVfrHud: (msg: VfrHud, frame: MavFrame) => void;
  onParamValue: (msg: ParamValue, frame: MavFrame) => void;
  onCommandAck: (msg: CommandAck, frame: MavFrame) => void;
  onMissionCurrent: (msg: MissionCurrent, frame: MavFrame) => void;
  onMissionAck: (msg: MissionAck, frame: MavFrame) => void;
  onMissionCount: (msg: MissionCount, frame: MavFrame) => void;
  onMissionItemInt: (msg: MissionItemInt, frame: MavFrame) => void;
  onHomePosition: (msg: HomePosition, frame: MavFrame) => void;
  onVibration: (msg: Vibration, frame: MavFrame) => void;
  onRawImu: (msg: RawImu, frame: MavFrame) => void;
  onWind: (msg: Wind, frame: MavFrame) => void;
  onStatusText: (msg: StatusText, frame: MavFrame) => void;
  onMissionRequest: (msg: MissionRequest, frame: MavFrame) => void;
  onMissionItemReached: (msg: MissionItemReached, frame: MavFrame) => void;
  onLogEntry: (msg: LogEntry, frame: MavFrame) => void;
  onLogData: (msg: LogData, frame: MavFrame) => void;
  onSerialControl: (msg: SerialControl, frame: MavFrame) => void;
  onTerrainReport: (msg: TerrainReport, frame: MavFrame) => void;
  onBatteryStatus: (msg: BatteryStatus, frame: MavFrame) => void;
  onAutopilotVersion: (msg: AutopilotVersion, frame: MavFrame) => void;
  onMountStatus: (msg: MountStatus, frame: MavFrame) => void;
  onMagCalProgress: (msg: MagCalProgress, frame: MavFrame) => void;
  onMagCalReport: (msg: MagCalReport, frame: MavFrame) => void;
  onEkfStatus: (msg: EkfStatus, frame: MavFrame) => void;
  onAdsbVehicle: (msg: AdsbVehicle, frame: MavFrame) => void;
  onUnknown: (frame: MavFrame) => void;
}
