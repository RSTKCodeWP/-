/**
 * State-machine tests for transport.ts WebSerial helpers.
 *
 * Closes audit finding #11 from the Phase A–H session self-review: the
 * mission/log/cal state machines had been exercised only by encoder
 * round-trips, never end-to-end. This file mocks ./serial so we can feed
 * synthetic MAVLink wire frames through the same read loop the real code
 * uses (via the captured onChunk callback), and asserts the outgoing bytes
 * + side effects match the protocol contract documented in
 * backend/mavlink_handlers.py.
 *
 * What we explicitly DO NOT test here (because the value is low and the
 * setup cost is high): timer-based watchdog firing — clearTimeout/setTimeout
 * coordination would need fake-timers across multiple promise resolutions.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const writes: Uint8Array[] = [];
let readLoopOnChunk: ((c: Uint8Array) => void) | null = null;
let readLoopResolve: ((v: void) => void) | null = null;
const events: Array<{ text: string; event_type: string }> = [];
const toasts: Array<{ text: string; level: string }> = [];

vi.mock('./serial', () => ({
  isWebSerialSupported: () => true,
  openSerial: vi.fn(async () => ({
    readable: {} as ReadableStream<Uint8Array>,
    writable: {} as WritableStream<Uint8Array>,
    close: vi.fn(async () => {}),
    info: {},
  })),
  serialWrite: vi.fn(async (_conn: unknown, data: Uint8Array) => {
    // Clone — transport may reuse its buffer between writes.
    writes.push(new Uint8Array(data));
  }),
  serialReadLoop: vi.fn(
    (_conn: unknown, onChunk: (c: Uint8Array) => void) =>
      new Promise<void>((resolve) => {
        readLoopOnChunk = onChunk;
        readLoopResolve = resolve;
      }),
  ),
}));

vi.mock('./stores.svelte', () => ({
  app: { activeTransport: 'none' as 'none' | 'ws' | 'serial' },
  addToast: vi.fn((text: string, level: string) => {
    toasts.push({ text, level });
  }),
  addEvent: vi.fn((ev: { text: string; event_type: string }) => {
    events.push(ev);
  }),
}));

vi.mock('./i18n.svelte', () => ({
  t: (key: string) => key,
  i18nState: { locale: 'en' },
}));

vi.mock('./logStore.svelte', () => ({
  logState: {
    list: [] as Array<{ id: number; size: number; time_utc: number }>,
    downloading: false,
    downloadId: -1,
    progress: 0,
  },
  setLogList: vi.fn(),
  startDownload: vi.fn(),
  appendLogChunkBinary: vi.fn(),
  updateDownloadProgress: vi.fn(),
  completeDownload: vi.fn(),
  cancelDownload: vi.fn(),
}));

// Import AFTER mocks. Real modules under test:
import {
  connectSerial,
  disconnectSerial,
  serialUploadMission,
  serialDownloadMission,
  serialUploadFence,
  serialLogList,
  serialLogDownload,
  serialLogCancel,
  serialCalCompass,
  dispatch,
  serialClearMission,
} from './transport';
import { encodeFrame } from './mavlink/codec';
import {
  encodeMissionCount,
  encodeMissionItemInt,
  encodeMissionAck,
  encodeMissionRequestInt,
} from './mavlink/messages';
import * as logStoreMock from './logStore.svelte';

// ─────────────────────────────────────────────────────────────────────────
// Frame helpers — wrap a payload in a real MAVLink 2 frame so transport's
// parseFrames produces the exact MavFrame our state machines expect.
// ─────────────────────────────────────────────────────────────────────────

let _seq = 0;
function fcFrame(msgId: number, payload: Uint8Array): Uint8Array {
  // sysId=1, compId=1 — typical AP defaults; serial.targetSysId is set on
  // first HEARTBEAT but the state machines read it as-is, so this works.
  return encodeFrame(msgId, payload, 1, 1, _seq++ & 0xff);
}

function mkMissionItemInt(seq: number, cmd: number, lat: number, lon: number, alt: number): Uint8Array {
  return encodeMissionItemInt(
    1,
    1,
    seq,
    cmd,
    3,
    seq === 0 ? 1 : 0,
    1,
    0,
    0,
    0,
    0,
    0,
    Math.trunc(lat * 1e7),
    Math.trunc(lon * 1e7),
    alt,
  );
}

function mkLogData(ofs: number, logId: number, count: number, data: Uint8Array = new Uint8Array(0)): Uint8Array {
  // LOG_DATA wire layout: ofs(u32) id(u16) count(u8) data[90]
  const buf = new Uint8Array(7 + data.length);
  const dv = new DataView(buf.buffer);
  dv.setUint32(0, ofs, true);
  dv.setUint16(4, logId, true);
  dv.setUint8(6, count);
  buf.set(data, 7);
  return buf;
}

function mkLogEntry(id: number, size: number, timeUtc: number, lastLogNum: number): Uint8Array {
  // LOG_ENTRY wire (sorted): time_utc(u32) size(u32) id(u16) num_logs(u16) last_log_num(u16)
  const buf = new Uint8Array(14);
  const dv = new DataView(buf.buffer);
  dv.setUint32(0, timeUtc, true);
  dv.setUint32(4, size, true);
  dv.setUint16(8, id, true);
  dv.setUint16(10, 1, true); // num_logs (not used by transport)
  dv.setUint16(12, lastLogNum, true);
  return buf;
}

function mkMagCalProgress(pct: number): Uint8Array {
  // 27-byte full payload; pct lives at offset 16. Leave xyz fields zero —
  // they're cosmetic (compass3D visualizer) and don't affect the bucket logic.
  const buf = new Uint8Array(27);
  buf[16] = pct;
  return buf;
}

function mkMagCalReport(calStatus: number): Uint8Array {
  // cal_status at offset 42; total length 44 (autosaved+orientation trim
  // is irrelevant after _padView). We pre-pad to 44 in transport, so a
  // 43-byte payload would also work, but tests use the full 44 for clarity.
  const buf = new Uint8Array(44);
  buf[42] = calStatus;
  return buf;
}

function inject(frame: Uint8Array): void {
  if (!readLoopOnChunk) throw new Error('Connect first');
  readLoopOnChunk(frame);
}

// ─────────────────────────────────────────────────────────────────────────

beforeEach(async () => {
  writes.length = 0;
  events.length = 0;
  toasts.length = 0;
  readLoopOnChunk = null;
  readLoopResolve = null;
  _seq = 0;
  await connectSerial(115200, {});
  // connectSerial issues an immediate heartbeat + a batch of REQUEST_DATA_STREAM
  // frames at boot. Flush them so each test starts with an empty write log.
  writes.length = 0;
});

afterEach(async () => {
  // Drain any pending state machines so they don't leak across tests.
  // Resolving the captured read-loop promise triggers the .finally() in
  // connectSerial which calls _resolveUpload / _resolveDownload /
  // _resolveLogList / _abortLogDownload for any pending operation.
  const r = readLoopResolve;
  readLoopResolve = null;
  if (r) r();
  await new Promise<void>((res) => setTimeout(res, 0));
  await disconnectSerial();
});

// Helper: find the first write whose payload starts with `msgId` (MAVLink2
// magic byte 0xFD + length byte + ... + 7 bytes header includes msgId24).
// MAVLink 2 frame layout: 0xFD, len, incompat, compat, seq, sysid, compid,
// msgid_lo, msgid_mid, msgid_hi, [payload...], crc16. msg id starts at byte 7.
function writeMsgId(w: Uint8Array): number {
  return w[7] | (w[8] << 8) | (w[9] << 16);
}
function findWrite(msgId: number): Uint8Array | undefined {
  return writes.find((w) => writeMsgId(w) === msgId);
}
function countWrites(msgId: number): number {
  return writes.filter((w) => writeMsgId(w) === msgId).length;
}

// ─────────────────────────────────────────────────────────────────────────
// Mission upload (Phase B)
// ─────────────────────────────────────────────────────────────────────────

describe('serialUploadMission', () => {
  it('happy path: COUNT → REQUEST_INT → ITEM_INT loop → ACK(0) resolves ok', async () => {
    const wps = [{ lat: 30, lon: 120, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp' as const, loiter_param: 0 }];
    const promise = serialUploadMission(wps, 30);
    // First wire emission must be MISSION_COUNT (msg 44).
    expect(countWrites(44)).toBe(1);
    // FC drives the rest. Built mission for 1 WP = [HOME, TAKEOFF, WP, RTL] = 4 items.
    for (let seq = 0; seq < 4; seq++) {
      writes.length = 0;
      inject(fcFrame(51, encodeMissionRequestInt(1, 1, seq)));
      const item = findWrite(73);
      expect(item, `seq=${seq} expected MISSION_ITEM_INT`).toBeDefined();
    }
    writes.length = 0;
    inject(fcFrame(47, encodeMissionAck(1, 1, 0)));
    await expect(promise).resolves.toEqual({ ok: true });
  });

  it('fails loud on MISSION_ACK with non-zero type (rejected upload)', async () => {
    const wps = [{ lat: 30, lon: 120, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp' as const, loiter_param: 0 }];
    const promise = serialUploadMission(wps, 30);
    inject(fcFrame(47, encodeMissionAck(1, 1, 14))); // MAV_MISSION_INVALID_PARAM7
    await expect(promise).resolves.toEqual({ ok: false, error: 'MISSION_ACK type=14' });
  });

  it('REGRESSION: rejects upload while a download is pending', async () => {
    // Start a download (no MISSION_COUNT injected yet → stays pending).
    void serialDownloadMission();
    // Should have sent MISSION_REQUEST_LIST.
    expect(countWrites(43)).toBe(1);
    // Now try an upload — must reject.
    const wps = [{ lat: 30, lon: 120, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp' as const, loiter_param: 0 }];
    const result = await serialUploadMission(wps, 30);
    expect(result.ok).toBe(false);
    expect(result.error).toMatch(/download/i);
  });
});

// ─────────────────────────────────────────────────────────────────────────
// Fence upload (Phase K) — same protocol as mission, mission_type=1
// ─────────────────────────────────────────────────────────────────────────

describe('serialUploadFence', () => {
  it('sends MISSION_COUNT with mission_type=1 and items with command=5001', async () => {
    const poly = [
      { lat: 30, lon: 120 },
      { lat: 31, lon: 120 },
      { lat: 31, lon: 121 },
      { lat: 30, lon: 121 },
    ];
    const promise = serialUploadFence(poly);
    // First write: MISSION_COUNT (msg 44). Decode it and verify mission_type
    // extension byte. With non-zero mission_type the payload is 5 bytes.
    const count = findWrite(44)!;
    // MAVLink 2 frame header is 10 bytes; payload follows. Payload[0..1]=count,
    // [2]=tgt_sys, [3]=tgt_comp, [4]=mission_type.
    expect(count[10 + 4]).toBe(1); // FENCE
    // Now drive the state machine through the 4-vertex upload.
    for (let seq = 0; seq < 4; seq++) {
      writes.length = 0;
      inject(fcFrame(51, encodeMissionRequestInt(1, 1, seq, 1)));
      const item = findWrite(73);
      expect(item, `seq=${seq}`).toBeDefined();
      // Verify cmd=5001 (NAV_FENCE_POLYGON_VERTEX_INCLUSION) at offset 10+30.
      const cmd = item![10 + 30] | (item![10 + 31] << 8);
      expect(cmd).toBe(5001);
      // mission_type extension at offset 10+37 must be 1 (FENCE).
      expect(item![10 + 37]).toBe(1);
    }
    writes.length = 0;
    inject(fcFrame(47, encodeMissionAck(1, 1, 0, 1)));
    await expect(promise).resolves.toEqual({ ok: true });
  });

  it('rejects polygons with < 3 vertices', async () => {
    const res = await serialUploadFence([
      { lat: 30, lon: 120 },
      { lat: 31, lon: 121 },
    ]);
    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/3 vertices/i);
  });
});

// ─────────────────────────────────────────────────────────────────────────
// Mission download (Phase D)
// ─────────────────────────────────────────────────────────────────────────

describe('serialDownloadMission', () => {
  it('collapses received items → Waypoint[] via missionItemsToWaypoints', async () => {
    const promise = serialDownloadMission();
    // GCS sent MISSION_REQUEST_LIST.
    expect(countWrites(43)).toBe(1);
    // FC: 4 items (HOME, TAKEOFF, WP, RTL) → 1 Waypoint after collapse.
    inject(fcFrame(44, encodeMissionCount(1, 1, 4)));
    inject(fcFrame(73, mkMissionItemInt(0, 16, 0, 0, 0))); // HOME
    inject(fcFrame(73, mkMissionItemInt(1, 22, 0, 0, 30))); // TAKEOFF
    inject(fcFrame(73, mkMissionItemInt(2, 16, 31.5, 121.2, 50))); // WP
    inject(fcFrame(73, mkMissionItemInt(3, 20, 0, 0, 0))); // RTL
    const res = await promise;
    expect(res.ok).toBe(true);
    expect(res.waypoints?.length).toBe(1);
    expect(res.waypoints?.[0].lat).toBeCloseTo(31.5, 5);
    expect(res.waypoints?.[0].lon).toBeCloseTo(121.2, 5);
    // Final MISSION_ACK (msg 47) must have been sent before resolve.
    expect(countWrites(47)).toBe(1);
  });

  it('empty mission (count=0): sends MISSION_ACK + resolves with empty waypoints', async () => {
    const promise = serialDownloadMission();
    inject(fcFrame(44, encodeMissionCount(1, 1, 0)));
    const res = await promise;
    expect(res.ok).toBe(true);
    expect(res.waypoints).toEqual([]);
    expect(countWrites(47)).toBe(1);
  });
});

// ─────────────────────────────────────────────────────────────────────────
// Log download (Phase C)
// ─────────────────────────────────────────────────────────────────────────

describe('serialLogList + serialLogDownload', () => {
  it('list accumulates LOG_ENTRY until id == last_log_num', async () => {
    const promise = serialLogList();
    // GCS sent LOG_REQUEST_LIST.
    expect(countWrites(117)).toBe(1);
    // FC: 2 logs, last_log_num=2.
    inject(fcFrame(118, mkLogEntry(1, 1024, 1700000000, 2)));
    inject(fcFrame(118, mkLogEntry(2, 2048, 1700001000, 2))); // last
    const res = await promise;
    expect(res.ok).toBe(true);
    expect(logStoreMock.setLogList).toHaveBeenCalledTimes(1);
    const entries = (logStoreMock.setLogList as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(entries.length).toBe(2);
    expect(entries[1].size).toBe(2048);
  });

  it('download truncates on count=0 sentinel (AP_Logger EOF / unreadable log)', async () => {
    // Pre-seed the list mock with a 90-byte log.
    (logStoreMock.logState as unknown as { list: Array<{ id: number; size: number; time_utc: number }> }).list = [
      { id: 7, size: 200, time_utc: 0 },
    ];
    const promise = serialLogDownload(7);
    // GCS sent LOG_REQUEST_DATA for log 7.
    expect(countWrites(119)).toBe(1);
    // FC returns first chunk normally, then count=0 sentinel.
    inject(fcFrame(120, mkLogData(0, 7, 90, new Uint8Array(90).fill(0xaa))));
    // Window cadence: 200-byte window not exhausted yet, so no re-request
    // went out; flush anyway to isolate the sentinel handling.
    writes.length = 0;
    inject(fcFrame(120, mkLogData(90, 7, 0, new Uint8Array(0)))); // EOF sentinel
    const res = await promise;
    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/truncated/i);
    expect(logStoreMock.completeDownload).toHaveBeenCalled();
  });

  it('streams the whole log from ONE request — no per-window round trips', async () => {
    // The whole log rides one LOG_REQUEST_DATA (the MAVProxy pattern,
    // AP_Logger_MAVLinkLogTransfer.cpp:112-113); AP streams the full range
    // as one paced burst and silently drops same-channel requests that
    // arrive mid-burst (:111-120). Per-window round trips were the
    // ~225 KB/s RTT ceiling on a ~700 KB/s USB link.
    (logStoreMock.logState as unknown as { list: Array<{ id: number; size: number; time_utc: number }> }).list = [
      { id: 3, size: 5000, time_utc: 0 },
    ];
    const promise = serialLogDownload(3);
    expect(countWrites(119)).toBe(1);
    const req = writes.filter((f) => f[7] === 119).at(-1)!;
    const dv = new DataView(req.buffer, req.byteOffset + 10);
    expect(dv.getUint32(0, true)).toBe(0); // whole log: ofs 0
    expect(dv.getUint32(4, true)).toBe(5000); // count = full size
    expect(dv.getUint16(8, true)).toBe(3);
    for (let ofs = 0; ofs < 5000; ofs += 90) {
      const n = Math.min(90, 5000 - ofs);
      inject(fcFrame(120, mkLogData(ofs, 3, n, new Uint8Array(n).fill(1))));
    }
    const res = await promise;
    expect(res.ok).toBe(true);
    expect(countWrites(119)).toBe(1); // the GCS never spoke again
  });

  it('a short mid-stream frame re-requests the uncovered remainder (AP ended its transfer)', async () => {
    (logStoreMock.logState as unknown as { list: Array<{ id: number; size: number; time_utc: number }> }).list = [
      { id: 4, size: 9000, time_utc: 0 },
    ];
    const promise = serialLogDownload(4);
    expect(countWrites(119)).toBe(1);
    inject(fcFrame(120, mkLogData(0, 4, 90, new Uint8Array(90).fill(1))));
    expect(countWrites(119)).toBe(1);
    // AP short read (nbytes < 90) ends its transfer mid-stream — the GCS
    // must resume from the first gap instead of waiting forever.
    inject(fcFrame(120, mkLogData(90, 4, 30, new Uint8Array(30).fill(2))));
    expect(countWrites(119)).toBe(2);
    const req = writes.filter((f) => f[7] === 119).at(-1)!;
    const dv = new DataView(req.buffer, req.byteOffset + 10);
    expect(dv.getUint32(0, true)).toBe(120);
    expect(dv.getUint32(4, true)).toBe(9000 - 120);
    serialLogCancel(); // tear down the pending promise + watchdog
    await promise;
  });

  it('gap-fills a mid-stream hole and completes CLEAN', async () => {
    // Lost frame 90..110; the stream reaches its end with a hole. The GCS
    // re-requests exactly the gap and — once answered — resolves ok:true.
    // The old window machinery shipped the file zero-filled and flagged;
    // gap-fill actually repairs it.
    (logStoreMock.logState as unknown as { list: Array<{ id: number; size: number; time_utc: number }> }).list = [
      { id: 5, size: 200, time_utc: 0 },
    ];
    const promise = serialLogDownload(5);
    inject(fcFrame(120, mkLogData(0, 5, 90, new Uint8Array(90).fill(1))));
    inject(fcFrame(120, mkLogData(110, 5, 90, new Uint8Array(90).fill(2)))); // stream end, hole behind
    expect(countWrites(119)).toBe(2);
    const req = writes.filter((f) => f[7] === 119).at(-1)!;
    const dv = new DataView(req.buffer, req.byteOffset + 10);
    expect(dv.getUint32(0, true)).toBe(90); // exactly the hole
    expect(dv.getUint32(4, true)).toBe(20);
    inject(fcFrame(120, mkLogData(90, 5, 20, new Uint8Array(20).fill(3))));
    const res = await promise;
    expect(res.ok).toBe(true); // repaired, not flagged
  });

  it('ignores a late/duplicate frame arriving after completion (dlId reset)', async () => {
    // On finish the machine resets dlId to -1 (mirrors backend
    // _log_download_id=-1). A straggler same-id LOG_DATA must then hit the
    // `logId !== dlId` guard and be dropped — not re-run coverage or re-arm
    // the watchdog on a completed session.
    (logStoreMock.logState as unknown as { list: Array<{ id: number; size: number; time_utc: number }> }).list = [
      { id: 7, size: 180, time_utc: 0 },
    ];
    const promise = serialLogDownload(7);
    inject(fcFrame(120, mkLogData(0, 7, 90, new Uint8Array(90).fill(1))));
    inject(fcFrame(120, mkLogData(90, 7, 90, new Uint8Array(90).fill(2)))); // reaches size → finish
    const res = await promise;
    expect(res.ok).toBe(true);
    const appendsAtFinish = vi.mocked(logStoreMock.appendLogChunkBinary).mock.calls.length;
    const writesAtFinish = countWrites(119);
    // Straggler for the just-finished log.
    inject(fcFrame(120, mkLogData(90, 7, 90, new Uint8Array(90).fill(3))));
    expect(vi.mocked(logStoreMock.appendLogChunkBinary).mock.calls.length).toBe(appendsAtFinish);
    expect(countWrites(119)).toBe(writesAtFinish); // no re-request, no re-arm side effects
  });

  it('reconstructs zero-tailed chunks that MAVLink2 trimmed on the wire', async () => {
    // A LOG_DATA whose data ends in zeros arrives trimmed; the machine must
    // pad back to the advertised count — the old code silently shortened
    // the chunk, corrupting the assembled log.
    (logStoreMock.logState as unknown as { list: Array<{ id: number; size: number; time_utc: number }> }).list = [
      { id: 9, size: 90, time_utc: 0 },
    ];
    const promise = serialLogDownload(9);
    const head = new Uint8Array(3).fill(0xbb);
    inject(fcFrame(120, mkLogData(0, 9, 90, head))); // payload carries 3 of 90 bytes
    const res = await promise;
    expect(res.ok).toBe(true);
    const call = vi.mocked(logStoreMock.appendLogChunkBinary).mock.calls.at(-1)!;
    const data = call[2] as Uint8Array;
    expect(data.length).toBe(90);
    expect(Array.from(data.slice(0, 3))).toEqual([0xbb, 0xbb, 0xbb]);
    expect(data.slice(3).every((b) => b === 0)).toBe(true);
  });

  it('drops a frame whose ofs+count exceeds the log size (corrupt ofs)', async () => {
    // ofs shares count's threat model — unguarded, a garbage ofs would push
    // the high-water mark past the size and completeDownload would allocate
    // a buffer sized by the largest ofs+length (up to 4 GB for a u32 ofs).
    (logStoreMock.logState as unknown as { list: Array<{ id: number; size: number; time_utc: number }> }).list = [
      { id: 8, size: 1000, time_utc: 0 },
    ];
    const promise = serialLogDownload(8);
    const appends = vi.mocked(logStoreMock.appendLogChunkBinary).mock.calls.length;
    inject(fcFrame(120, mkLogData(990, 8, 90, new Uint8Array(90).fill(4))));
    expect(vi.mocked(logStoreMock.appendLogChunkBinary).mock.calls.length).toBe(appends); // dropped
    serialLogCancel();
    await promise;
  });

  it('duplicate frames do not mask a real hole (coverage is intervals, not a sum)', async () => {
    // After a stall re-request a late tail of the old burst can legitimately
    // duplicate frames — a raw byte sum (90+90+90=270 > 200 here) would
    // declare the file complete while bytes 90..110 were never received.
    // The tell: the machine asks for exactly the missing 20 bytes instead
    // of resolving.
    (logStoreMock.logState as unknown as { list: Array<{ id: number; size: number; time_utc: number }> }).list = [
      { id: 2, size: 200, time_utc: 0 },
    ];
    const promise = serialLogDownload(2);
    inject(fcFrame(120, mkLogData(0, 2, 90, new Uint8Array(90).fill(9))));
    inject(fcFrame(120, mkLogData(0, 2, 90, new Uint8Array(90).fill(9)))); // duplicate
    inject(fcFrame(120, mkLogData(110, 2, 90, new Uint8Array(90).fill(9)))); // stream end
    const req = writes.filter((f) => f[7] === 119).at(-1)!;
    const dv = new DataView(req.buffer, req.byteOffset + 10);
    expect(dv.getUint32(0, true)).toBe(90);
    expect(dv.getUint32(4, true)).toBe(20);
    inject(fcFrame(120, mkLogData(90, 2, 20, new Uint8Array(20).fill(9))));
    const res = await promise;
    expect(res.ok).toBe(true);
  });

  it('out-of-order frames merge into full coverage — arrival order is not completeness', async () => {
    (logStoreMock.logState as unknown as { list: Array<{ id: number; size: number; time_utc: number }> }).list = [
      { id: 1, size: 200, time_utc: 0 },
    ];
    const promise = serialLogDownload(1);
    inject(fcFrame(120, mkLogData(90, 1, 90, new Uint8Array(90).fill(5)))); // middle first
    inject(fcFrame(120, mkLogData(0, 1, 90, new Uint8Array(90).fill(5)))); // then the head (bridges)
    inject(fcFrame(120, mkLogData(180, 1, 20, new Uint8Array(20).fill(5)))); // tail reaches size
    const res = await promise;
    expect(res.ok).toBe(true); // covered 0..200 with no hole despite the order
  });

  it('clamps a corrupt count>90 instead of crashing the read loop', async () => {
    // count is a free u8 but the data field is uint8_t[90] (MAVLink
    // common.xml) — unclamped, the payload view would throw RangeError past
    // the buffer end and tear down the whole serial connection.
    (logStoreMock.logState as unknown as { list: Array<{ id: number; size: number; time_utc: number }> }).list = [
      { id: 6, size: 9000, time_utc: 0 },
    ];
    const promise = serialLogDownload(6);
    inject(fcFrame(120, mkLogData(0, 6, 200, new Uint8Array(90).fill(3))));
    const call = vi.mocked(logStoreMock.appendLogChunkBinary).mock.calls.at(-1)!;
    expect((call[2] as Uint8Array).length).toBe(90);
    serialLogCancel();
    await promise;
  });
});

// ─────────────────────────────────────────────────────────────────────────
// Log download stall watchdog (fake-timers) — twin of backend
// check_log_dl_stall. A lost window-boundary frame leaves AP idle (it ended
// its burst, AP_Logger_MAVLinkLogTransfer.cpp:337-341) and the window
// cadence with no trigger — the watchdog must re-request, not abort.
// ─────────────────────────────────────────────────────────────────────────

describe('log download stall watchdog', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(logStoreMock.completeDownload).mockClear();
    vi.mocked(logStoreMock.cancelDownload).mockClear();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  const seedList = (id: number, size: number) => {
    (logStoreMock.logState as unknown as { list: Array<{ id: number; size: number; time_utc: number }> }).list = [
      { id, size, time_utc: 0 },
    ];
  };

  it('a lost stream tail triggers a re-request of the remaining gap and the download recovers', async () => {
    seedList(3, 9000);
    const promise = serialLogDownload(3);
    expect(countWrites(119)).toBe(1);
    // The stream dies at 4410 — everything after is lost on the wire.
    for (let ofs = 0; ofs < 4410; ofs += 90) {
      inject(fcFrame(120, mkLogData(ofs, 3, 90, new Uint8Array(90).fill(1))));
    }
    expect(countWrites(119)).toBe(1); // nothing to trigger a request — stalled
    await vi.advanceTimersByTimeAsync(5001);
    expect(countWrites(119)).toBe(2);
    const req = writes.filter((f) => f[7] === 119).at(-1)!;
    const dv = new DataView(req.buffer, req.byteOffset + 10);
    expect(dv.getUint32(0, true)).toBe(4410); // first gap = resume point
    expect(dv.getUint32(4, true)).toBe(9000 - 4410);
    // FC answers the remainder; the download completes clean (no holes).
    for (let ofs = 4410; ofs < 9000; ofs += 90) {
      inject(fcFrame(120, mkLogData(ofs, 3, 90, new Uint8Array(90).fill(2))));
    }
    const res = await promise;
    expect(res.ok).toBe(true);
    expect(countWrites(119)).toBe(2); // one initial + one resume, nothing else
    expect(logStoreMock.completeDownload).toHaveBeenCalled();
  });

  it('gives up after bounded retries and delivers the partial data flagged, not discarded', async () => {
    seedList(4, 9000);
    const promise = serialLogDownload(4);
    inject(fcFrame(120, mkLogData(0, 4, 90, new Uint8Array(90).fill(1))));
    for (let i = 0; i < 3; i++) {
      await vi.advanceTimersByTimeAsync(5001);
    }
    expect(countWrites(119)).toBe(4); // initial + 3 stall re-requests
    await vi.advanceTimersByTimeAsync(5001); // retries exhausted
    const res = await promise;
    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/re-requests unanswered/);
    // The 90 bytes received still reach the user (twin of backend
    // finalize(truncated=True)) — the old code discarded everything.
    expect(logStoreMock.completeDownload).toHaveBeenCalled();
    expect(logStoreMock.cancelDownload).not.toHaveBeenCalled();
  });

  it('a hole whose gap-fill goes unanswered ends flagged, with partial data delivered', async () => {
    seedList(5, 200);
    const promise = serialLogDownload(5);
    // The 0..110 range was lost; only the tail arrives, ending the stream.
    inject(fcFrame(120, mkLogData(110, 5, 90, new Uint8Array(90).fill(9))));
    // The gap request for 0..110 went out immediately at the stream end.
    expect(countWrites(119)).toBe(2);
    const req = writes.filter((f) => f[7] === 119).at(-1)!;
    const dv = new DataView(req.buffer, req.byteOffset + 10);
    expect(dv.getUint32(0, true)).toBe(0);
    expect(dv.getUint32(4, true)).toBe(110);
    // FC never answers: 3 stall retries re-ask, then give up flagged.
    for (let i = 0; i < 4; i++) {
      await vi.advanceTimersByTimeAsync(5001);
    }
    const res = await promise;
    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/re-requests unanswered/);
    expect(logStoreMock.completeDownload).toHaveBeenCalled();
  });
});

// ─────────────────────────────────────────────────────────────────────────
// Compass cal (Phase E)
// ─────────────────────────────────────────────────────────────────────────

describe('serialCalCompass + MAG_CAL events', () => {
  it('emits one event per 5% bucket cross, dedupes within-bucket increments', () => {
    serialCalCompass();
    // 5 % bucket crossings at pct 5, 10, 15, 20 — sub-bucket increments
    // (e.g. 12, 13) must NOT emit additional events.
    // pct=0 IS a bucket crossing (floor(0/5)=0 != floor(-1/5)=-1) — matches
    // backend handle_mag_cal_progress's `(pct // 5) != (prev // 5)` check at
    // mavlink_handlers.py:225 since Python's // floor-divides -1//5 to -1.
    inject(fcFrame(191, mkMagCalProgress(0))); // emit (bucket 0)
    inject(fcFrame(191, mkMagCalProgress(5))); // emit (bucket 1)
    inject(fcFrame(191, mkMagCalProgress(6))); // dedup
    inject(fcFrame(191, mkMagCalProgress(9))); // dedup
    inject(fcFrame(191, mkMagCalProgress(10))); // emit (bucket 2)
    inject(fcFrame(191, mkMagCalProgress(11))); // dedup
    inject(fcFrame(191, mkMagCalProgress(15))); // emit (bucket 3)
    inject(fcFrame(191, mkMagCalProgress(20))); // emit (bucket 4)
    const pctEvents = events.filter((e) => e.event_type === 'cal_compass');
    expect(pctEvents.length).toBe(5);
  });

  it('MAG_CAL_REPORT with cal_status=4 emits done + reboot events, sets one-shot guard', () => {
    serialCalCompass();
    inject(fcFrame(191, mkMagCalProgress(50)));
    events.length = 0;
    inject(fcFrame(192, mkMagCalReport(4))); // MAG_CAL_SUCCESS
    expect(events.length).toBe(2); // done + reboot
    // Subsequent progress frames suppressed.
    inject(fcFrame(191, mkMagCalProgress(99)));
    expect(events.filter((e) => e.event_type === 'cal_compass').length).toBe(2);
  });

  it('MAG_CAL_REPORT with non-success status emits failure event', () => {
    serialCalCompass();
    events.length = 0;
    inject(fcFrame(192, mkMagCalReport(5))); // MAG_CAL_FAILED
    expect(events.length).toBe(1);
    expect(events[0].text).toMatch(/Failed|failed|cal\.s\.compassFailed/i);
  });
});

// ─────────────────────────────────────────────────────────────────────────
// Disconnect cleanup
// ─────────────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────────────
// Watchdogs (fake-timers). The heartbeat setInterval set up in connectSerial
// was registered BEFORE useFakeTimers, so it stays on the real clock and
// won't pollute our writes during fake-time advancement.
// ─────────────────────────────────────────────────────────────────────────

describe('upload watchdogs', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  const oneWp = () => [
    {
      lat: 30,
      lon: 120,
      alt: 50,
      drop: false,
      delay: 0,
      speed: 0,
      type: 'wp' as const,
      loiter_param: 0,
    },
  ];

  it('30s overall watchdog rejects upload when FC sends no MISSION_REQUEST', async () => {
    const promise = serialUploadMission(oneWp(), 30);
    // No FC frame injected. Advance just past the 30s overall timeout.
    await vi.advanceTimersByTimeAsync(30001);
    const res = await promise;
    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/timed out|30s/i);
  });

  it('5s per-item watchdog fires when FC stops requesting mid-upload', async () => {
    const promise = serialUploadMission(oneWp(), 30);
    // FC sends the first request — this arms the 5s per-item timer.
    inject(fcFrame(51, encodeMissionRequestInt(1, 1, 0)));
    // No further FC traffic. The per-item watchdog should fire.
    await vi.advanceTimersByTimeAsync(5001);
    const res = await promise;
    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/stopped requesting|seq 0/i);
  });

  it('per-item timer resets on each MISSION_REQUEST so a slow-but-steady FC succeeds', async () => {
    const promise = serialUploadMission(oneWp(), 30);
    // Drip 4 requests with 4s between each — under 5s per-item, so the
    // watchdog never fires. Then send the ACK.
    for (let seq = 0; seq < 4; seq++) {
      inject(fcFrame(51, encodeMissionRequestInt(1, 1, seq)));
      await vi.advanceTimersByTimeAsync(4000);
    }
    inject(fcFrame(47, encodeMissionAck(1, 1, 0)));
    await expect(promise).resolves.toEqual({ ok: true });
  });
});

describe('log cancel', () => {
  it('serialLogCancel sends LOG_REQUEST_END (msg 122) and aborts the download', async () => {
    // Pre-seed the log list so serialLogDownload(7) finds the entry.
    type LogList = Array<{ id: number; size: number; time_utc: number }>;
    (logStoreMock.logState as unknown as { list: LogList }).list = [{ id: 7, size: 1024, time_utc: 0 }];
    const promise = serialLogDownload(7);
    writes.length = 0;
    serialLogCancel();
    expect(countWrites(122)).toBe(1);
    const res = await promise;
    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/cancel/i);
  });
});

describe('disconnect cleanup', () => {
  it('serialUploadMission rejects pending promise on disconnect', async () => {
    const wps = [{ lat: 30, lon: 120, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp' as const, loiter_param: 0 }];
    const promise = serialUploadMission(wps, 30);
    // Don't send any FC response — disconnect mid-upload.
    await disconnectSerial();
    // The read-loop resolve simulates the underlying stream closing.
    readLoopResolve?.();
    // Promise should reject — the finally() inside connectSerial's read
    // loop runs _resolveUpload({ok:false, error:'Serial link lost ...'}).
    const res = await promise;
    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/lost|disconnect/i);
  });
});

describe('download rejects during upload', () => {
  it('serialDownloadMission rejects when an upload is in progress', async () => {
    const wps = [{ lat: 30, lon: 120, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp' as const, loiter_param: 0 }];
    void serialUploadMission(wps, 30);
    const result = await serialDownloadMission();
    expect(result.ok).toBe(false);
    expect(result.error).toMatch(/upload/i);
  });
});

describe('upload out-of-range seq handling', () => {
  it('rejects when FC requests seq beyond item count', async () => {
    const wps = [{ lat: 30, lon: 120, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp' as const, loiter_param: 0 }];
    const promise = serialUploadMission(wps, 30);
    // Built mission for 1 WP = 4 items (HOME, TAKEOFF, WP, RTL). Request seq=99.
    inject(fcFrame(51, encodeMissionRequestInt(1, 1, 99)));
    const res = await promise;
    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/out-of-range/i);
  });
});

describe('download with multi-item mission', () => {
  it('downloads 3 items and collapses HOME+WP+RTL to single waypoint', async () => {
    const promise = serialDownloadMission();
    // FC → MISSION_COUNT = 3
    inject(fcFrame(44, encodeMissionCount(1, 1, 3)));
    // FC → 3 MISSION_ITEM_INT
    inject(fcFrame(73, mkMissionItemInt(0, 16, 0, 0, 0))); // HOME
    inject(fcFrame(73, mkMissionItemInt(1, 16, 34.258, 108.942, 50))); // WP (seq>0 cmd=16)
    inject(fcFrame(73, mkMissionItemInt(2, 20, 0, 0, 0))); // RTL
    const res = await promise;
    expect(res.ok).toBe(true);
    expect(res.waypoints).toHaveLength(1);
    expect(res.waypoints![0].lat).toBeCloseTo(34.258, 4);
    // GCS should have sent MISSION_ACK (msg 47)
    expect(countWrites(47)).toBe(1);
  });
});

describe('mission_set_current seq map (post-download)', () => {
  // Decode MISSION_SET_CURRENT (msg 41) seq from a captured write frame.
  // Wire layout: byte 10 = first payload byte; seq = uint16 little-endian.
  function decodeSeq(w: Uint8Array): number {
    const dv = new DataView(w.buffer, w.byteOffset + 10, 2);
    return dv.getUint16(0, true);
  }

  it('uses downloaded seq map when DO_CHANGE_SPEED shifts the layout', async () => {
    // Mission layout: HOME(0) TAKEOFF(1) WP_A(2) SPEED(3) WP_B(4) RTL(5)
    // wp_index 0 → seq 2 (matches +2 fallback)
    // wp_index 1 → seq 4 (NOT seq 3 = SPEED, NOT seq 1+2=3 from fallback)
    const promise = serialDownloadMission();
    inject(fcFrame(44, encodeMissionCount(1, 1, 6)));
    inject(fcFrame(73, mkMissionItemInt(0, 16, 0, 0, 0)));            // HOME
    inject(fcFrame(73, mkMissionItemInt(1, 22, 0, 0, 30)));           // TAKEOFF
    inject(fcFrame(73, mkMissionItemInt(2, 16, 34.258, 108.942, 50))); // WP A
    inject(fcFrame(73, mkMissionItemInt(3, 178, 0, 0, 0)));           // DO_CHANGE_SPEED
    inject(fcFrame(73, mkMissionItemInt(4, 16, 34.259, 108.943, 50))); // WP B
    inject(fcFrame(73, mkMissionItemInt(5, 20, 0, 0, 0)));            // RTL
    await promise;
    writes.length = 0;

    // Goto WP B (wp_index=1). With the map, seq should be 4. Without the map (broken case), seq would be 3.
    dispatch('mission_set_current', undefined, { wp_index: 1 });
    expect(countWrites(41)).toBe(1);
    expect(decodeSeq(findWrite(41)!)).toBe(4);
  });

  it('falls back to wp_index + 2 when no mission has been downloaded', () => {
    dispatch('mission_set_current', undefined, { wp_index: 3 });
    expect(decodeSeq(findWrite(41)!)).toBe(5);
  });

  it('clears the seq map on mission_clear so a follow-up goto uses the fallback', async () => {
    const promise = serialDownloadMission();
    inject(fcFrame(44, encodeMissionCount(1, 1, 3)));
    inject(fcFrame(73, mkMissionItemInt(0, 16, 0, 0, 0)));
    inject(fcFrame(73, mkMissionItemInt(1, 22, 0, 0, 30)));
    inject(fcFrame(73, mkMissionItemInt(2, 16, 34.258, 108.942, 50)));
    await promise;
    writes.length = 0;
    // wp_index 0 was at seq 2 in the downloaded mission. Same seq from the +2 fallback,
    // so to distinguish: clear, then a goto whose fallback would be different from any map entry.
    serialClearMission();
    writes.length = 0;
    // After clear, no map. wp_index=5 → fallback seq=7 (no map could have produced this).
    dispatch('mission_set_current', undefined, { wp_index: 5 });
    expect(decodeSeq(findWrite(41)!)).toBe(7);
  });
});
