/**
 * WebSerial DECODE-direction dump for the dual-stack state-parity harness —
 * the inbound twin of transport.parity.test.ts (outbound commands).
 *
 * Feeds each pymavlink-encoded FC frame from tests/fixtures/parity_frames.json
 * through the REAL inbound path — parseFrames (CRC check) → dispatchFrame
 * (payload decode) → buildSerialHandlers (store mapping) — and snapshots the
 * resulting app.drone fields per frame. tests/test_contract_dualstack_state_parity.py
 * runs this spec with PARITY_STATE_DUMP_PATH set, replays the SAME bytes
 * through the backend handlers on a real DroneLink, and compares get_state()
 * against these snapshots: one FC frame, two transports, same UI state.
 */
import { describe, it, expect, vi } from 'vitest';
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

// vi.mock factories are hoisted; shared mutable state must be vi.hoisted.
const H = vi.hoisted(() => ({
  drone: {} as Record<string, unknown>,
}));

vi.mock('./stores.svelte', () => ({
  app: { drone: H.drone, activeTransport: 'serial' },
  addToast: vi.fn(),
  addEvent: vi.fn(),
  isPlane: () => false,
}));
vi.mock('./i18n.svelte', () => ({
  t: (key: string) => key,
  i18nState: { locale: 'en' },
}));

// Import AFTER mocks.
import { parseFrames, dispatchFrame } from './mavlink';
import { buildSerialHandlers } from './serialHandlers';

interface ParityFrame {
  id: string;
  msg: string;
  hex: string;
  compare: string[];
  note?: string;
}

const fixturePath = fileURLToPath(new URL('../../tests/fixtures/parity_frames.json', import.meta.url));
const fixture: { frames: ParityFrame[] } = JSON.parse(readFileSync(fixturePath, 'utf-8'));

const fromHex = (hex: string): Uint8Array =>
  new Uint8Array(hex.match(/.{2}/g)!.map((b) => parseInt(b, 16)));

describe('dual-stack state-parity dump (FC → app.drone)', () => {
  it('decodes every fixture frame through the real serial inbound path', () => {
    const handlers = buildSerialHandlers();
    const dump: Record<string, Record<string, unknown>> = {};

    for (const spec of fixture.frames) {
      // Fresh store per frame — each snapshot must be attributable to
      // exactly one frame, like the fresh DroneLink on the backend side.
      for (const k of Object.keys(H.drone)) delete H.drone[k];

      const { frames, remaining } = parseFrames(fromHex(spec.hex));
      expect(remaining.length, `${spec.id}: undecoded trailing bytes`).toBe(0);
      // A CRC_EXTRA mismatch in crc.ts would silently drop the frame here —
      // surface it as a hard failure instead.
      expect(frames.length, `${spec.id}: frame did not parse (CRC/framing)`).toBe(1);
      dispatchFrame(frames[0], handlers);

      const snapshot: Record<string, unknown> = {};
      for (const key of spec.compare) snapshot[key] = H.drone[key];
      dump[spec.id] = snapshot;
    }

    for (const spec of fixture.frames) {
      for (const key of spec.compare) {
        expect(dump[spec.id][key], `${spec.id}: handler never wrote app.drone.${key}`).toBeDefined();
      }
    }

    const outPath = process.env.PARITY_STATE_DUMP_PATH;
    if (outPath) writeFileSync(outPath, JSON.stringify(dump, null, 1));
  });
});
