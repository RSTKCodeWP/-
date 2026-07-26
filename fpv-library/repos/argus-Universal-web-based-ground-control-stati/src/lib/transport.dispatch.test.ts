/**
 * Wire-byte contract test for _serialDispatch ↔ backend _DISPATCH semantic parity.
 *
 * The existing test_contract_serial_dispatch.py only verifies that every
 * backend command key is present in _serialDispatch (and vice versa). The
 * 2026-05-28 ultrareview found 7 bugs where key parity passed but wire
 * bytes diverged — camera_trigger sent all zeros (no-op), do_set_roi sent
 * cmd 197 (DO_SET_ROI_NONE) instead of 201, takeoff/guided_goto skipped
 * mode switches, mission_set_current ignored the HOME/TAKEOFF seq offset,
 * mission_start omitted the explicit MISSION_START cmd, param_save did
 * FC NVRAM instead of host JSON backup.
 *
 * This test decodes the frames each serial dispatch entry emits and
 * asserts the command id + relevant params + mode-switch ordering match
 * what the corresponding backend cmd_* handler would have sent. Run
 * alongside the python contract test for both directions of guarantee.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const writes: Uint8Array[] = [];
let readLoopResolve: ((v: void) => void) | null = null;
let _isPlaneFlag = false;

vi.mock('./serial', () => ({
  isWebSerialSupported: () => true,
  openSerial: vi.fn(async () => ({
    readable: {} as ReadableStream<Uint8Array>,
    writable: {} as WritableStream<Uint8Array>,
    close: vi.fn(async () => {}),
    info: {},
  })),
  serialWrite: vi.fn(async (_conn: unknown, data: Uint8Array) => {
    writes.push(new Uint8Array(data));
  }),
  serialReadLoop: vi.fn(
    (_conn: unknown, _onChunk: (c: Uint8Array) => void) =>
      new Promise<void>((resolve) => {
        readLoopResolve = resolve;
      }),
  ),
}));

vi.mock('./stores.svelte', () => ({
  app: { activeTransport: 'none' as 'none' | 'ws' | 'serial', drone: {} },
  addToast: vi.fn(),
  addEvent: vi.fn(),
  isPlane: () => _isPlaneFlag,
}));

vi.mock('./i18n.svelte', () => ({
  t: (key: string) => key,
  i18nState: { locale: 'en' },
}));

vi.mock('./logStore.svelte', () => ({
  logState: { list: [], downloading: false, downloadId: -1, progress: 0 },
  setLogList: vi.fn(),
  startDownload: vi.fn(),
  appendLogChunkBinary: vi.fn(),
  updateDownloadProgress: vi.fn(),
  completeDownload: vi.fn(),
  cancelDownload: vi.fn(),
}));

const wsSendCommand = vi.fn();
vi.mock('./ws', () => ({
  sendCommand: wsSendCommand,
}));

// Import AFTER mocks
import { connectSerial, disconnectSerial, dispatch } from './transport';

// ─────────────────────────────────────────────────────────────────────────
// Frame decode helpers — MAVLink 2 wire layout
// ─────────────────────────────────────────────────────────────────────────

interface DecodedFrame {
  msgId: number;
  payload: Uint8Array;  // re-padded if zero-trimmed
}

function decodeFrame(bytes: Uint8Array, expectedPayloadLen?: number): DecodedFrame {
  // MAVLink 2 header: STX(1) len(1) incompat(1) compat(1) seq(1) sys(1) comp(1) msgId(3)
  // then payload, then CRC(2).
  const len = bytes[1];
  const msgId = bytes[7] | (bytes[8] << 8) | (bytes[9] << 16);
  let payload = bytes.slice(10, 10 + len);
  if (expectedPayloadLen !== undefined && payload.length < expectedPayloadLen) {
    // MAVLink 2 zero-trim — pad back to full length so offset reads work.
    const padded = new Uint8Array(expectedPayloadLen);
    padded.set(payload);
    payload = padded;
  }
  return { msgId, payload };
}

interface CommandLong {
  command: number;
  p1: number;
  p2: number;
  p3: number;
  p4: number;
  p5: number;
  p6: number;
  p7: number;
  targetSys: number;
  targetComp: number;
}

function decodeCommandLong(bytes: Uint8Array): CommandLong {
  const { msgId, payload } = decodeFrame(bytes, 33);
  expect(msgId).toBe(76);  // COMMAND_LONG
  const dv = new DataView(payload.buffer, payload.byteOffset, payload.byteLength);
  return {
    p1: dv.getFloat32(0, true),
    p2: dv.getFloat32(4, true),
    p3: dv.getFloat32(8, true),
    p4: dv.getFloat32(12, true),
    p5: dv.getFloat32(16, true),
    p6: dv.getFloat32(20, true),
    p7: dv.getFloat32(24, true),
    command: dv.getUint16(28, true),
    targetSys: dv.getUint8(30),
    targetComp: dv.getUint8(31),
  };
}

function decodeSetMode(bytes: Uint8Array): { customMode: number; baseMode: number; targetSys: number } {
  const { msgId, payload } = decodeFrame(bytes, 6);
  expect(msgId).toBe(11);  // SET_MODE
  const dv = new DataView(payload.buffer, payload.byteOffset, payload.byteLength);
  return {
    customMode: dv.getUint32(0, true),
    targetSys: dv.getUint8(4),
    baseMode: dv.getUint8(5),
  };
}

function decodeMissionSetCurrent(bytes: Uint8Array): { seq: number } {
  const { msgId, payload } = decodeFrame(bytes, 4);
  expect(msgId).toBe(41);
  const dv = new DataView(payload.buffer, payload.byteOffset, payload.byteLength);
  return { seq: dv.getUint16(0, true) };
}

function decodePositionTargetGlobal(bytes: Uint8Array): {
  lat: number;
  lon: number;
  alt: number;
  typeMask: number;
  frame: number;
} {
  const { msgId, payload } = decodeFrame(bytes, 53);
  expect(msgId).toBe(86);
  const dv = new DataView(payload.buffer, payload.byteOffset, payload.byteLength);
  return {
    lat: dv.getInt32(4, true) / 1e7,
    lon: dv.getInt32(8, true) / 1e7,
    alt: dv.getFloat32(12, true),
    typeMask: dv.getUint16(48, true),
    frame: dv.getUint8(52),
  };
}

function decodeCommandAck(bytes: Uint8Array): { command: number; result: number } {
  const { msgId, payload } = decodeFrame(bytes, 3);
  expect(msgId).toBe(77); // COMMAND_ACK
  const dv = new DataView(payload.buffer, payload.byteOffset, payload.byteLength);
  return { command: dv.getUint16(0, true), result: dv.getUint8(2) };
}

function decodeRcOverride(bytes: Uint8Array): { channels: number[]; targetSys: number; targetComp: number } {
  const { msgId, payload } = decodeFrame(bytes, 18);
  expect(msgId).toBe(70); // RC_CHANNELS_OVERRIDE
  const dv = new DataView(payload.buffer, payload.byteOffset, payload.byteLength);
  const channels: number[] = [];
  for (let i = 0; i < 8; i++) channels.push(dv.getUint16(i * 2, true));
  return { channels, targetSys: dv.getUint8(16), targetComp: dv.getUint8(17) };
}

interface CommandInt {
  command: number;
  p1: number;
  p2: number;
  x: number;
  y: number;
  z: number;
}

function decodeCommandInt(bytes: Uint8Array): CommandInt {
  const { msgId, payload } = decodeFrame(bytes, 35);
  expect(msgId).toBe(75); // COMMAND_INT
  const dv = new DataView(payload.buffer, payload.byteOffset, payload.byteLength);
  return {
    p1: dv.getFloat32(0, true),
    p2: dv.getFloat32(4, true),
    x: dv.getInt32(16, true),
    y: dv.getInt32(20, true),
    z: dv.getFloat32(24, true),
    command: dv.getUint16(28, true),
  };
}

// Skip the connect-boot frames (heartbeat + REQUEST_DATA_STREAMs) and
// return only msgIds that this test cares about.
function filterAppFrames(allWrites: Uint8Array[]): Uint8Array[] {
  return allWrites.filter((w) => {
    const msgId = w[7] | (w[8] << 8) | (w[9] << 16);
    // Drop boot-time msgs: HEARTBEAT(0), REQUEST_DATA_STREAM(66).
    return msgId !== 0 && msgId !== 66;
  });
}

beforeEach(async () => {
  writes.length = 0;
  wsSendCommand.mockClear();
  readLoopResolve = null;
  _isPlaneFlag = false;
  await connectSerial(115200, {});
  writes.length = 0;  // discard boot frames
});

afterEach(async () => {
  const r = readLoopResolve;
  readLoopResolve = null;
  if (r) r();
  await new Promise<void>((res) => setTimeout(res, 0));
  await disconnectSerial();
});

describe('_serialDispatch wire-byte semantics', () => {
  // ── arm/disarm sanity ────────────────────────────────────────────────
  it('arm sends MAV_CMD_COMPONENT_ARM_DISARM (400) p1=1', () => {
    dispatch('arm');
    const cmd = decodeCommandLong(writes[0]);
    expect(cmd.command).toBe(400);
    expect(cmd.p1).toBe(1);
  });

  it('disarm sends MAV_CMD_COMPONENT_ARM_DISARM (400) p1=0', () => {
    dispatch('disarm');
    const cmd = decodeCommandLong(writes[0]);
    expect(cmd.command).toBe(400);
    expect(cmd.p1).toBe(0);
  });

  // ── force_disarm: 21196 magic ────────────────────────────────────────
  it('force_disarm uses AP arming-bypass magic 21196 in p2', () => {
    dispatch('force_disarm');
    const cmd = decodeCommandLong(writes[0]);
    expect(cmd.command).toBe(400);
    expect(cmd.p1).toBe(0);
    expect(cmd.p2).toBe(21196);
  });

  // ── rtl: Plane=11, Copter=6 ──────────────────────────────────────────
  it('rtl on Plane sends SET_MODE custom_mode=11 (RTL, NOT 21=QRTL)', () => {
    _isPlaneFlag = true;
    dispatch('rtl');
    expect(decodeSetMode(writes[0]).customMode).toBe(11);
  });

  it('rtl on Copter sends SET_MODE custom_mode=6', () => {
    _isPlaneFlag = false;
    dispatch('rtl');
    expect(decodeSetMode(writes[0]).customMode).toBe(6);
  });

  // ── takeoff: Plane needs GUIDED first ────────────────────────────────
  it('takeoff on Plane switches to GUIDED (15) before sending NAV_TAKEOFF (22)', () => {
    _isPlaneFlag = true;
    dispatch('takeoff', undefined, { alt: 50 });
    expect(writes.length).toBe(2);
    expect(decodeSetMode(writes[0]).customMode).toBe(15);  // GUIDED
    const cmd = decodeCommandLong(writes[1]);
    expect(cmd.command).toBe(22);
    expect(cmd.p7).toBe(50);
  });

  it('takeoff on Copter sends NAV_TAKEOFF directly (no mode switch)', () => {
    _isPlaneFlag = false;
    dispatch('takeoff', undefined, { alt: 30 });
    expect(writes.length).toBe(1);
    const cmd = decodeCommandLong(writes[0]);
    expect(cmd.command).toBe(22);
    expect(cmd.p7).toBe(30);
  });

  // ── mission_start: AUTO mode + delayed MISSION_START (300) ───────────
  it('mission_start sets AUTO mode then sends MAV_CMD_MISSION_START (300) after 300ms', async () => {
    vi.useFakeTimers();
    _isPlaneFlag = false;
    dispatch('mission_start');
    expect(writes.length).toBe(1);
    expect(decodeSetMode(writes[0]).customMode).toBe(3);  // Copter AUTO
    // Delay = cfg.MISSION_START_DELAY = 0.3s in backend/config.py.
    await vi.advanceTimersByTimeAsync(300);
    expect(writes.length).toBe(2);
    expect(decodeCommandLong(writes[1]).command).toBe(300);
    vi.useRealTimers();
  });

  it('mission_start double-tap coalesces — second call cancels first timer', async () => {
    vi.useFakeTimers();
    _isPlaneFlag = false;
    dispatch('mission_start');
    expect(writes.length).toBe(1);  // SET_MODE
    // Tap again before the 300ms delay elapses — the first timer should be cancelled.
    await vi.advanceTimersByTimeAsync(100);
    dispatch('mission_start');
    expect(writes.length).toBe(2);  // SET_MODE #2 fires immediately; cmd 300 NOT yet
    await vi.advanceTimersByTimeAsync(300);
    // After the full delay from the SECOND call, exactly one cmd 300 should land — not two.
    const cmd300Writes = writes.filter((w) => {
      try { return decodeCommandLong(w).command === 300; }
      catch { return false; }
    });
    expect(cmd300Writes.length).toBe(1);
    vi.useRealTimers();
  });

  // ── mission_set_current: HOME/TAKEOFF offset ─────────────────────────
  it('mission_set_current adds +2 HOME/TAKEOFF offset to wp_index', () => {
    dispatch('mission_set_current', undefined, { wp_index: 0 });
    expect(decodeMissionSetCurrent(writes[0]).seq).toBe(2);
  });

  it('mission_set_current wp_index=5 sends seq=7', () => {
    dispatch('mission_set_current', undefined, { wp_index: 5 });
    expect(decodeMissionSetCurrent(writes[0]).seq).toBe(7);
  });

  // ── guided_goto: mode switch + SET_POSITION_TARGET_GLOBAL_INT ────────
  it('guided_goto on Plane: GUIDED (15) then msg 86 with int32 lat/lon', () => {
    _isPlaneFlag = true;
    dispatch('guided_goto', undefined, { lat: 40.7128, lon: -74.006, alt: 100 });
    expect(writes.length).toBe(2);
    expect(decodeSetMode(writes[0]).customMode).toBe(15);
    const tgt = decodePositionTargetGlobal(writes[1]);
    expect(tgt.lat).toBeCloseTo(40.7128, 6);
    expect(tgt.lon).toBeCloseTo(-74.006, 6);
    expect(tgt.alt).toBe(100);
    expect(tgt.typeMask).toBe(0x0FF8);
    expect(tgt.frame).toBe(6);  // MAV_FRAME_GLOBAL_RELATIVE_ALT_INT
  });

  it('guided_goto on Copter: GUIDED (4) then msg 86', () => {
    _isPlaneFlag = false;
    dispatch('guided_goto', undefined, { lat: 40, lon: -74, alt: 50 });
    expect(decodeSetMode(writes[0]).customMode).toBe(4);
    expect(decodePositionTargetGlobal(writes[1]).alt).toBe(50);
  });

  it('guided_goto drops Null Island (lat≈0, lon≈0) — no SET_MODE, no target sent', () => {
    dispatch('guided_goto', undefined, { lat: 0, lon: 0, alt: 30 });
    expect(filterAppFrames(writes).length).toBe(0);
  });

  it('guided_goto drops NaN coords', () => {
    dispatch('guided_goto', undefined, { lat: NaN, lon: -74, alt: 30 });
    expect(filterAppFrames(writes).length).toBe(0);
  });

  it('guided_goto drops out-of-range lat', () => {
    dispatch('guided_goto', undefined, { lat: 91, lon: 0, alt: 30 });
    expect(filterAppFrames(writes).length).toBe(0);
  });

  // ── do_set_roi: cmd 201 (NOT 197), p1=3 ──────────────────────────────
  it('do_set_roi sends MAV_CMD_DO_SET_ROI (201) with p1=3, NOT 197 (DO_SET_ROI_NONE)', () => {
    dispatch('do_set_roi', undefined, { lat: 40.7, lon: -74, alt: 50 });
    const cmd = decodeCommandLong(writes[0]);
    expect(cmd.command).toBe(201);
    expect(cmd.command).not.toBe(197);  // explicit anti-regression
    expect(cmd.p1).toBe(3);
    expect(cmd.p5).toBeCloseTo(40.7, 3);
    expect(cmd.p6).toBeCloseTo(-74, 3);
    expect(cmd.p7).toBe(50);
  });

  // ── camera_trigger: p5=1 (NOT all zeros) ─────────────────────────────
  it('camera_trigger sends DO_DIGICAM_CONTROL (203) with p5=1', () => {
    dispatch('camera_trigger');
    const cmd = decodeCommandLong(writes[0]);
    expect(cmd.command).toBe(203);
    expect(cmd.p5).toBe(1);  // shoot command — all zeros is a no-op
  });

  it('camera_video_start sends VIDEO_START_CAPTURE (2500) with p3=1 to match backend', () => {
    dispatch('camera_video_start');
    const cmd = decodeCommandLong(writes[0]);
    expect(cmd.command).toBe(2500);
    expect(cmd.p3).toBe(1);
  });

  // ── param_save split: save_to_flash hits FC NVRAM, save falls through to WS
  it('param_save_to_flash sends PREFLIGHT_STORAGE (245) p1=1', () => {
    dispatch('param_save_to_flash');
    const cmd = decodeCommandLong(writes[0]);
    expect(cmd.command).toBe(245);
    expect(cmd.p1).toBe(1);
  });

  it('param_save falls through to WS (no serial write) — writes JSON backup, not FC NVRAM', async () => {
    dispatch('param_save');
    // Give the dynamic import time to resolve.
    await new Promise<void>((res) => setTimeout(res, 0));
    expect(filterAppFrames(writes).length).toBe(0);
    expect(wsSendCommand).toHaveBeenCalledWith('param_save', undefined, undefined);
  });

  // ── drop / drop_stop ─────────────────────────────────────────────────
  it('drop sends DO_PARACHUTE (181) p2=0 (RELEASE)', () => {
    dispatch('drop');
    const cmd = decodeCommandLong(writes[0]);
    expect(cmd.command).toBe(181);
    expect(cmd.p2).toBe(0);
  });

  it('drop_stop sends DO_PARACHUTE (181) p2=1 (DISABLE)', () => {
    dispatch('drop_stop');
    const cmd = decodeCommandLong(writes[0]);
    expect(cmd.command).toBe(181);
    expect(cmd.p2).toBe(1);
  });

  // ── reboot variants ──────────────────────────────────────────────────
  it('reboot sends PREFLIGHT_REBOOT_SHUTDOWN (246) p1=1 (autopilot reboot)', () => {
    dispatch('reboot');
    const cmd = decodeCommandLong(writes[0]);
    expect(cmd.command).toBe(246);
    expect(cmd.p1).toBe(1);
  });

  it('reboot_bootloader sends PREFLIGHT_REBOOT_SHUTDOWN (246) p1=3', () => {
    dispatch('reboot_bootloader');
    const cmd = decodeCommandLong(writes[0]);
    expect(cmd.command).toBe(246);
    expect(cmd.p1).toBe(3);
  });

  // ── motor_test bounds (defensive — UI clamps, but dispatch must too) ──
  it('motor_test rejects out-of-bounds motor index (>7)', () => {
    dispatch('motor_test', undefined, { motor: 99, throttle: 5, duration: 2 });
    expect(filterAppFrames(writes).length).toBe(0);
  });

  it('motor_test rejects out-of-bounds throttle (>100)', () => {
    dispatch('motor_test', undefined, { motor: 0, throttle: 200, duration: 2 });
    expect(filterAppFrames(writes).length).toBe(0);
  });

  it('motor_test rejects out-of-bounds duration (>30)', () => {
    dispatch('motor_test', undefined, { motor: 0, throttle: 5, duration: 60 });
    expect(filterAppFrames(writes).length).toBe(0);
  });

  it('motor_test with valid input sends DO_MOTOR_TEST (209) with 1-based motor index', () => {
    dispatch('motor_test', undefined, { motor: 0, throttle: 10, duration: 2 });
    const cmd = decodeCommandLong(writes[0]);
    expect(cmd.command).toBe(209);
    expect(cmd.p1).toBe(1);  // motor 0 (UI) → 1 (AP wire)
    expect(cmd.p3).toBe(10);  // throttle %
    expect(cmd.p4).toBe(2);   // duration s
    expect(cmd.p5).toBe(1);   // motor count
  });
});

// ─────────────────────────────────────────────────────────────────────────
// Calibration / gimbal / RC-override wire bytes — FC-coupled, previously
// untested on the WebSerial path (only the backend twins had wire tests).
// A "cleanup" of the deliberately spec-violating cal_accel_next COMMAND_ACK,
// or a byte-offset regression in rc_override, would silently miscalibrate the
// vehicle or drive the wrong control channel with no failing test.
// ─────────────────────────────────────────────────────────────────────────
describe('_serialDispatch calibration + gimbal + RC wire bytes', () => {
  // ── cal_accel_next: the spec-violating COMMAND_ACK (the critical one) ──
  it('cal_accel_next sends COMMAND_ACK(command=0, result=1) — NOT a MAV_CMD', () => {
    // AP_AccelCal::handle_command_ack (AP_AccelCal.cpp:366-393) requires
    // command<=6 and result==TEMPORARILY_REJECTED(1). QGC sends command=0,
    // result=1; anyone "fixing" this to (42429, 0) breaks 6-position accel cal.
    dispatch('cal_accel_next');
    const ack = decodeCommandAck(writes[0]);
    expect(ack.command).toBe(0);
    expect(ack.result).toBe(1);
  });

  // ── compass cal COMMAND_LONGs ────────────────────────────────────────
  it('cal_compass sends DO_START_MAG_CAL (42424) with p1=0 (all mags)', () => {
    dispatch('cal_compass');
    const cmd = decodeCommandLong(writes[0]);
    expect(cmd.command).toBe(42424);
    expect(cmd.p1).toBe(0);
  });

  it('cal_compass_accept sends DO_ACCEPT_MAG_CAL (42425)', () => {
    dispatch('cal_compass_accept');
    expect(decodeCommandLong(writes[0]).command).toBe(42425);
  });

  it('cal_cancel sends DO_CANCEL_MAG_CAL (42426)', () => {
    dispatch('cal_cancel');
    expect(decodeCommandLong(writes[0]).command).toBe(42426);
  });

  // ── PREFLIGHT_CALIBRATION (241) axis flags: each cal type sets a distinct
  //    param, and swapping them would run the wrong calibration ──────────
  it('cal_gyro sends PREFLIGHT_CALIBRATION (241) with p1=1 (gyro axis)', () => {
    dispatch('cal_gyro');
    const cmd = decodeCommandLong(writes[0]);
    expect(cmd.command).toBe(241);
    expect(cmd.p1).toBe(1);
    expect(cmd.p3).toBe(0);
    expect(cmd.p5).toBe(0);
  });

  it('cal_baro sends PREFLIGHT_CALIBRATION (241) with p3=1 (ground pressure)', () => {
    dispatch('cal_baro');
    const cmd = decodeCommandLong(writes[0]);
    expect(cmd.command).toBe(241);
    expect(cmd.p3).toBe(1);
    expect(cmd.p1).toBe(0);
  });

  it('cal_level sends PREFLIGHT_CALIBRATION (241) with p5=4 (board level)', () => {
    dispatch('cal_level');
    const cmd = decodeCommandLong(writes[0]);
    expect(cmd.command).toBe(241);
    expect(cmd.p5).toBe(4);
  });

  it('cal_accel sends PREFLIGHT_CALIBRATION (241) with p5=1 (accel), distinct from level p5=4', () => {
    dispatch('cal_accel');
    const cmd = decodeCommandLong(writes[0]);
    expect(cmd.command).toBe(241);
    expect(cmd.p5).toBe(1);
  });

  // ── gimbal_pitchyaw: COMMAND_INT with flags-as-x bitfield ────────────
  it('gimbal_pitchyaw sends COMMAND_INT (75) cmd=1000 with pitch/yaw + flags in x', () => {
    dispatch('gimbal_pitchyaw', undefined, { pitch: 30, yaw: 45, flags: 5, instance: 2 });
    const cmd = decodeCommandInt(writes[0]);
    expect(cmd.command).toBe(1000); // MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW
    expect(cmd.p1).toBeCloseTo(30, 3); // pitch
    expect(cmd.p2).toBeCloseTo(45, 3); // yaw
    expect(cmd.x).toBe(5); // GIMBAL_MANAGER_FLAGS bitfield rides x, not a param
    expect(cmd.z).toBeCloseTo(2, 3); // instance rides z
  });

  it('gimbal_pitchyaw omitted angles become NaN (skip), not 0 (which would command level)', () => {
    dispatch('gimbal_pitchyaw', undefined, { yaw: 90 });
    const cmd = decodeCommandInt(writes[0]);
    expect(Number.isNaN(cmd.p1)).toBe(true); // pitch omitted → NaN skip
    expect(cmd.p2).toBeCloseTo(90, 3);
  });

  // ── rc_override: 8×uint16 channel packing to a live vehicle ──────────
  it('rc_override packs 8 channels as little-endian uint16 into RC_CHANNELS_OVERRIDE (70)', () => {
    dispatch('rc_override', undefined, { channels: [1500, 1600, 1700, 1800, 1000, 2000, 1234, 1899] });
    const rc = decodeRcOverride(writes[0]);
    expect(rc.channels).toEqual([1500, 1600, 1700, 1800, 1000, 2000, 1234, 1899]);
  });

  it('rc_override drops short channel lists (backend parity — zero-fill would release ch2-8)', () => {
    dispatch('rc_override', undefined, { channels: [1500] });
    expect(filterAppFrames(writes).length).toBe(0);
  });

  it('rc_override with no channels sends nothing', () => {
    dispatch('rc_override', undefined, {});
    expect(filterAppFrames(writes).length).toBe(0);
  });

  // ── remaining simple passthroughs (bundled for completeness) ─────────
  it('mode sends SET_MODE (11) with the requested custom mode', () => {
    dispatch('mode', 5);
    expect(decodeSetMode(writes[0]).customMode).toBe(5);
  });

  it('camera_zoom sends SET_CAMERA_ZOOM (531) p1=1 (continuous) p2=zoom', () => {
    dispatch('camera_zoom', undefined, { zoom: 50 });
    const cmd = decodeCommandLong(writes[0]);
    expect(cmd.command).toBe(531);
    expect(cmd.p1).toBe(1);
    expect(cmd.p2).toBe(50);
  });

  it('camera_video_stop sends VIDEO_STOP_CAPTURE (2501)', () => {
    dispatch('camera_video_stop');
    expect(decodeCommandLong(writes[0]).command).toBe(2501);
  });

  it('motor_test_stop sends DO_MOTOR_TEST (209) with zero throttle for every motor', () => {
    dispatch('motor_test_stop');
    const cmds = filterAppFrames(writes).map(decodeCommandLong);
    expect(cmds.length).toBe(8);
    for (const cmd of cmds) {
      expect(cmd.command).toBe(209);
      expect(cmd.p3).toBe(0); // throttle 0 = stop
    }
  });
});
