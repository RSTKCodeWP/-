/**
 * WebSerial parameter-fetch state machine (transport.ts paramFetch) — the
 * serial twin of backend/param_manager.py. Drives the REAL read-loop
 * intercept and gap-fill ticker against a mocked serial port and a recording
 * paramStore fake.
 *
 * Regression anchor: until 2026-07-16 the serial path sent PARAM_REQUEST_LIST
 * but had no PARAM_VALUE consumer — the FC streamed 1000+ params into the
 * void and the panel sat empty forever (found live against a real FC; the
 * SIM never exercises the WebSerial path).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const H = vi.hoisted(() => ({
  writes: [] as Uint8Array[],
  fcInject: null as ((chunk: Uint8Array) => void) | null,
  store: {
    batches: [] as Record<string, unknown>[],
    rows: [] as Record<string, unknown>[],
    completes: 0,
    timeouts: 0,
    starts: 0,
  },
}));

vi.mock('./serial', () => ({
  isWebSerialSupported: () => true,
  openSerial: vi.fn(async () => ({
    readable: {} as ReadableStream<Uint8Array>,
    writable: {} as WritableStream<Uint8Array>,
    close: vi.fn(async () => {}),
    info: {},
  })),
  serialWrite: vi.fn(async (_conn: unknown, data: Uint8Array) => {
    H.writes.push(new Uint8Array(data));
  }),
  serialReadLoop: vi.fn((_conn: unknown, onChunk: (c: Uint8Array) => void) => {
    H.fcInject = onChunk;
    return new Promise<void>(() => {});
  }),
}));
vi.mock('./stores.svelte', () => ({
  app: { activeTransport: 'none', drone: {} },
  addToast: vi.fn(),
  addEvent: vi.fn(),
  isPlane: () => false,
}));
vi.mock('./i18n.svelte', () => ({
  t: (key: string) => key,
  i18nState: { locale: 'en' },
}));
vi.mock('./logStore.svelte', () => ({
  logState: { list: [] },
  setLogList: vi.fn(),
  startDownload: vi.fn(),
  appendLogChunkBinary: vi.fn(),
  updateDownloadProgress: vi.fn(),
  completeDownload: vi.fn(),
  cancelDownload: vi.fn(),
}));
vi.mock('./paramStore.svelte', () => ({
  handleParamBatch: vi.fn((b: Record<string, unknown>[]) => {
    H.store.batches.push(...b);
  }),
  handleParamsComplete: vi.fn(() => {
    H.store.completes++;
  }),
  handleParamTimeout: vi.fn(() => {
    H.store.timeouts++;
  }),
  startParamFetch: vi.fn(() => {
    H.store.starts++;
  }),
  updateParamRow: vi.fn((name: string, value: number, ptype: number, index: number) => {
    H.store.rows.push({ name, value, ptype, index });
  }),
}));
vi.mock('./ws', () => ({ sendCommand: vi.fn() }));

// Import AFTER mocks.
import { connectSerial, disconnectSerial, dispatch } from './transport';
import { encodeFrame } from './mavlink';
import { addToast } from './stores.svelte';

const msgIdOf = (f: Uint8Array): number => f[7] | (f[8] << 8) | (f[9] << 16);
const writesOf = (id: number): Uint8Array[] => H.writes.filter((f) => msgIdOf(f) === id);

// PARAM_VALUE (22) payload — same wire layout the backend parses
// (param_manager.handle_param_value): f32 value @0, u16 count @4,
// u16 index @6, char[16] name @8, u8 type @24.
function paramValue(name: string, value: number, index: number, count: number, ptype = 9): Uint8Array {
  const buf = new Uint8Array(25);
  const dv = new DataView(buf.buffer);
  dv.setFloat32(0, value, true);
  dv.setUint16(4, count, true);
  dv.setUint16(6, index, true);
  new TextEncoder().encodeInto(name, buf.subarray(8, 24));
  dv.setUint8(24, ptype);
  return buf;
}

let fcSeq = 0;
const inject = (name: string, value: number, index: number, count: number): void => {
  H.fcInject!(encodeFrame(22, paramValue(name, value, index, count), 1, 1, fcSeq++ & 0xff));
};

describe('WebSerial param fetch state machine', () => {
  beforeEach(async () => {
    vi.clearAllMocks(); // call history only — implementations survive
    vi.useFakeTimers();
    H.writes.length = 0;
    H.store.batches.length = 0;
    H.store.rows.length = 0;
    H.store.completes = 0;
    H.store.timeouts = 0;
    H.store.starts = 0;
    expect(await connectSerial(115200, {})).toBe(true);
    H.writes.length = 0; // drop the connect-time stream-setup frames
  });

  afterEach(async () => {
    await disconnectSerial();
    vi.useRealTimers();
  });

  it('request sends PARAM_REQUEST_LIST once and flags the store', () => {
    dispatch('param_request_all');
    expect(H.store.starts).toBe(1);
    expect(writesOf(21).length).toBe(1);
    // target ids ride at payload bytes 0-1 (backend _request_list layout)
    expect(writesOf(21)[0][10]).toBe(1);
    expect(writesOf(21)[0][11]).toBe(1);
  });

  it('streams values into the store and completes at total', () => {
    dispatch('param_request_all');
    inject('A', 1, 0, 3);
    inject('B', 2, 1, 3);
    expect(H.store.completes).toBe(0);
    inject('C', 3, 2, 3);
    expect(H.store.completes).toBe(1);
    expect(H.store.batches.map((b) => b.received)).toEqual([1, 2, 3]);
    expect(H.store.batches.every((b) => b.total === 3)).toBe(true);
  });

  it('duplicate values update the store without double-counting', () => {
    dispatch('param_request_all');
    inject('A', 1, 0, 2);
    inject('A', 1.5, 0, 2); // retransmit with a newer value
    expect(H.store.completes).toBe(0);
    expect(H.store.batches.at(-1)!.received).toBe(1);
    inject('B', 2, 1, 2);
    expect(H.store.completes).toBe(1);
  });

  it('re-requests missing indexes via PARAM_REQUEST_READ after silence', () => {
    dispatch('param_request_all');
    inject('A', 1, 0, 3);
    inject('C', 3, 2, 3); // index 1 lost
    vi.advanceTimersByTime(3000);
    const reads = writesOf(20);
    expect(reads.length).toBe(1);
    const p = new DataView(reads[0].buffer, reads[0].byteOffset + 10);
    expect(p.getInt16(0, true)).toBe(1); // exactly the missing index
    inject('B', 2, 1, 3);
    expect(H.store.completes).toBe(1);
    // Ticker stopped — no further gap-fill traffic.
    vi.advanceTimersByTime(10_000);
    expect(writesOf(20).length).toBe(1);
  });

  it('gap-fill retries a missing index at most 3 times', () => {
    dispatch('param_request_all');
    inject('A', 1, 0, 2); // index 1 never arrives
    vi.advanceTimersByTime(30_000);
    expect(writesOf(20).length).toBe(3);
  });

  it('re-sends a dropped PARAM_REQUEST_LIST up to 3 extra times', () => {
    dispatch('param_request_all');
    expect(writesOf(21).length).toBe(1);
    vi.advanceTimersByTime(30_000); // no PARAM_VALUE ever arrives
    expect(writesOf(21).length).toBe(4); // initial + 3 retries, then gives up
  });

  it('counts 0xFFFF-index replies without marking an index slot', () => {
    dispatch('param_request_all');
    inject('A', 1, 0, 2);
    // By-name reply: ArduPilot echoes param_index -1 (GCS_Param.cpp:420).
    inject('B', 2, 0xffff, 2);
    expect(H.store.completes).toBe(1);
  });

  it('aborts with timeout + toast when the fetch stalls past the deadline', () => {
    dispatch('param_request_all');
    inject('A', 1, 0, 500);
    vi.advanceTimersByTime(61_000);
    expect(H.store.timeouts).toBe(1);
    expect(vi.mocked(addToast)).toHaveBeenCalledWith('param.timeout', 'error', 5000);
    // Machine is dead — param traffic frozen (heartbeats keep flowing).
    const paramSent = writesOf(20).length + writesOf(21).length;
    vi.advanceTimersByTime(10_000);
    expect(writesOf(20).length + writesOf(21).length).toBe(paramSent);
  });

  it('routes a PARAM_SET echo outside any fetch through the counters-free row update', () => {
    inject('WPNAV_SPEED', 750, 42, 1034);
    expect(H.store.rows.at(-1)).toMatchObject({ name: 'WPNAV_SPEED', value: 750 });
    // handleParamBatch must NOT run — it would replay fetch counters.
    expect(H.store.batches.length).toBe(0);
    expect(H.store.starts).toBe(0);
    expect(H.store.completes).toBe(0);
  });

  it('echo after a timed-out partial fetch cannot re-latch the fetching flag', () => {
    dispatch('param_request_all');
    inject('A', 1, 0, 1000); // 1/1000, then stall
    vi.advanceTimersByTime(61_000);
    expect(H.store.timeouts).toBe(1);
    const batchesAfterTimeout = H.store.batches.length;
    // A later PARAM_SET echo carries stale-looking counters; feeding it to
    // handleParamBatch would recompute fetching=true with no ticker alive,
    // permanently disabling the Read-All button.
    inject('WPNAV_SPEED', 750, 42, 1000);
    expect(H.store.batches.length).toBe(batchesAfterTimeout);
    expect(H.store.rows.at(-1)).toMatchObject({ name: 'WPNAV_SPEED', value: 750 });
  });

  it('disconnect mid-fetch stops the ticker without a timeout toast', async () => {
    dispatch('param_request_all');
    inject('A', 1, 0, 3);
    await disconnectSerial();
    expect(H.store.timeouts).toBe(1); // fetching flag released
    expect(vi.mocked(addToast)).not.toHaveBeenCalled();
    const sent = H.writes.length;
    vi.advanceTimersByTime(70_000);
    expect(H.writes.length).toBe(sent);
  });

  it('ignores an all-zero/garbage PARAM_VALUE (empty name)', () => {
    dispatch('param_request_all');
    inject('', 0, 0, 3);
    expect(H.store.batches.length).toBe(0);
  });
});
