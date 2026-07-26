/**
 * WebSerial wire-frame dump for the dual-stack parity harness.
 *
 * Drives the REAL production command paths (transport.dispatch table, the
 * mission/fence upload state machines, the log/mission-download initiators)
 * against a mocked serial port and records every emitted MAVLink frame, per
 * operation, from the shared input list tests/fixtures/parity_ops.json.
 *
 * tests/test_contract_dualstack_parity.py runs this spec with
 * PARITY_DUMP_PATH set, then replays the SAME inputs through the Python
 * backend (commands.execute) and compares both frame streams field-by-field
 * with pymavlink as the decoding oracle. That machine-to-machine comparison
 * replaces the two hand-maintained expectation mirrors
 * (transport.dispatch.test.ts ↔ test_contract_pymavlink.py) as the guarantee
 * that the WebSerial path and the backend path stay semantically identical.
 *
 * Run standalone (no env var) it still executes every op and sanity-checks
 * the dump shape, so a crash in any choreography fails the normal vitest run.
 */
import { describe, it, expect, vi } from 'vitest';
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

// vi.mock factories are hoisted above every other statement, so all mutable
// state they close over must be created via vi.hoisted (a plain `const` would
// hit its temporal dead zone when the factory runs during module mocking).
const H = vi.hoisted(() => ({
  writes: [] as Uint8Array[],
  fcInject: null as ((chunk: Uint8Array) => void) | null,
  isPlane: false,
  logList: { list: [] as { id: number; size: number; time_utc: number }[] },
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
  // Capture onChunk so the harness can play the FC side of the mission /
  // fence upload handshakes (MISSION_REQUEST_INT → ... → MISSION_ACK).
  serialReadLoop: vi.fn(
    (_conn: unknown, onChunk: (c: Uint8Array) => void) => {
      H.fcInject = onChunk;
      return new Promise<void>(() => {});
    },
  ),
}));

vi.mock('./stores.svelte', () => ({
  app: { activeTransport: 'none', drone: {} },
  addToast: vi.fn(),
  addEvent: vi.fn(),
  isPlane: () => H.isPlane,
}));
vi.mock('./i18n.svelte', () => ({
  t: (key: string) => key,
  i18nState: { locale: 'en' },
}));
vi.mock('./logStore.svelte', () => ({
  logState: H.logList,
  setLogList: vi.fn(),
  startDownload: vi.fn(),
  appendLogChunkBinary: vi.fn(),
  updateDownloadProgress: vi.fn(),
  completeDownload: vi.fn(),
  cancelDownload: vi.fn(),
}));
vi.mock('./ws', () => ({ sendCommand: vi.fn() }));

// Import AFTER mocks.
import {
  connectSerial,
  dispatch,
  hasSerialHandler,
  serialLogList,
  serialLogDownload,
  serialDownloadMission,
  serialUploadMission,
  serialUploadFence,
} from './transport';
import { encodeFrame } from './mavlink';
import { encodeMissionRequestInt, encodeMissionAck } from './mavlink';
import type { Waypoint } from './types';

interface ParityOp {
  id: string;
  kind: string;
  op?: string;
  param?: number;
  data?: Record<string, unknown>;
  plane?: boolean;
  flush_timer_ms?: number;
  log_entry?: { id: number; size: number };
  expect: string;
}
interface ParityFixture {
  golden_waypoints: Record<string, unknown>[];
  golden_takeoff_alt: number;
  fence_polygon: { lat: number; lon: number }[];
  ops: ParityOp[];
}

const fixturePath = fileURLToPath(new URL('../../tests/fixtures/parity_ops.json', import.meta.url));
const fixture: ParityFixture = JSON.parse(readFileSync(fixturePath, 'utf-8'));

const msgIdOf = (frame: Uint8Array): number => frame[7] | (frame[8] << 8) | (frame[9] << 16);
const toHex = (frames: Uint8Array[]): string[] =>
  frames.map((f) => Array.from(f).map((b) => b.toString(16).padStart(2, '0')).join(''));

// FC-side frames for driving the upload state machines. The FC is sysid 1 /
// compid 1 (matches the backend FakeLink and a real ArduPilot autopilot).
function fcMissionRequestInt(seq: number, missionType: number): Uint8Array {
  return encodeFrame(51, encodeMissionRequestInt(255, 190, seq, missionType), 1, 1, seq);
}
function fcMissionAck(missionType: number): Uint8Array {
  return encodeFrame(47, encodeMissionAck(255, 190, 0, missionType), 1, 1, 99);
}

async function driveUpload(
  start: () => Promise<{ ok: boolean; error?: string }>,
  missionType: number,
): Promise<{ ok: boolean; error?: string }> {
  const done = start();
  // The MISSION_COUNT frame is the first frame; its count field (u16 @0)
  // tells us how many MISSION_REQUEST_INTs to play back as the FC.
  const countFrame = H.writes[0];
  expect(countFrame, 'upload sent no MISSION_COUNT').toBeDefined();
  expect(msgIdOf(countFrame)).toBe(44);
  const count = countFrame[10] | (countFrame[11] << 8);
  for (let seq = 0; seq < count; seq++) H.fcInject!(fcMissionRequestInt(seq, missionType));
  H.fcInject!(fcMissionAck(missionType));
  return done;
}

describe('dual-stack parity dump', () => {
  it('captures wire frames for every fixture op', async () => {
    vi.useFakeTimers();
    const dump: Record<string, string[]> = {};
    try {
    H.writes.length = 0;
    const ok = await connectSerial(115200, {});
    expect(ok).toBe(true);
    // One heartbeat-interval tick so the boot heartbeat lands in `writes`.
    await vi.advanceTimersByTimeAsync(1000);
    const bootHeartbeat = H.writes.find((w) => msgIdOf(w) === 0);
    expect(bootHeartbeat, 'no boot heartbeat captured').toBeDefined();
    // Kill the 1 Hz heartbeat interval: from here on, every captured frame
    // must come from the op under test — no msgId-based filtering that could
    // hide a command handler spuriously emitting heartbeat/stream frames.
    vi.clearAllTimers();

    for (const op of fixture.ops) {
      H.isPlane = op.plane === true;
      H.writes.length = 0;
      if (op.kind === 'dispatch') {
        // A typo'd op name would fall through to the (mocked) WS backend and
        // "pass" every zero-frame expectation — reject it up front.
        expect(hasSerialHandler(op.op!), `op '${op.op}' not in _serialDispatch`).toBe(true);
      }

      switch (op.kind) {
        case 'boot_heartbeat':
          dump[op.id] = toHex([bootHeartbeat!]);
          continue;
        case 'dispatch':
          dispatch(op.op!, op.param, op.data);
          if (op.flush_timer_ms) await vi.advanceTimersByTimeAsync(op.flush_timer_ms);
          break;
        case 'log_list': {
          const p = serialLogList();
          dump[op.id] = toHex(H.writes);
          await vi.advanceTimersByTimeAsync(6000); // let the watchdog resolve
          await p;
          continue;
        }
        case 'log_download': {
          H.logList.list.length = 0;
          H.logList.list.push({ ...op.log_entry!, time_utc: 0 });
          const p = serialLogDownload(op.log_entry!.id);
          dump[op.id] = toHex(H.writes);
          // The stall watchdog re-requests 3× (5s apart) before giving up —
          // walk the full ladder so the promise settles (dump already
          // captured; the retry frames land after it and writes reset per op).
          await vi.advanceTimersByTimeAsync(21000);
          await p;
          continue;
        }
        case 'mission_download': {
          const p = serialDownloadMission();
          dump[op.id] = toHex(H.writes);
          await vi.advanceTimersByTimeAsync(6000);
          await p;
          continue;
        }
        case 'mission_upload': {
          const result = await driveUpload(
            () => serialUploadMission(fixture.golden_waypoints as unknown as Waypoint[], fixture.golden_takeoff_alt),
            0,
          );
          expect(result.ok, `mission upload failed: ${result.error}`).toBe(true);
          break;
        }
        case 'fence_upload': {
          const result = await driveUpload(() => serialUploadFence(fixture.fence_polygon), 1);
          expect(result.ok, `fence upload failed: ${result.error}`).toBe(true);
          break;
        }
        default:
          throw new Error(`unknown op kind: ${op.kind}`);
      }
      dump[op.id] = toHex(H.writes);
    }
    } finally {
      vi.useRealTimers();
    }

    // Sanity: every op captured; parity/pinned counts are plausible. The
    // real field-by-field assertions live in the pytest side.
    for (const op of fixture.ops) {
      expect(dump[op.id], `op ${op.id} missing from dump`).toBeDefined();
      if (op.expect === 'both_drop') {
        expect(dump[op.id], `op ${op.id} should emit nothing`).toEqual([]);
      }
      if (op.expect === 'parity' && op.kind !== 'boot_heartbeat') {
        expect(dump[op.id].length, `op ${op.id} emitted no frames`).toBeGreaterThan(0);
      }
    }

    const outPath = process.env.PARITY_DUMP_PATH;
    if (outPath) writeFileSync(outPath, JSON.stringify(dump, null, 1));
  });
});
