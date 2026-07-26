import { describe, it, expect } from 'vitest';
import { parseTlog } from './tlog-replay';

/** Build a MAVLink v2 frame (no signing). */
function v2Frame(msgid: number, sysid: number, compid: number, seq: number, payload: number[]): number[] {
  return [
    0xfd,
    payload.length,
    0, // incompat
    0, // compat
    seq,
    sysid,
    compid,
    msgid & 0xff,
    (msgid >> 8) & 0xff,
    (msgid >> 16) & 0xff,
    ...payload,
    0, // crc lo (not validated by parseTlog)
    0, // crc hi
  ];
}

/** Build a MAVLink v1 frame. */
function v1Frame(msgid: number, sysid: number, compid: number, seq: number, payload: number[]): number[] {
  return [0xfe, payload.length, seq, sysid, compid, msgid & 0xff, ...payload, 0, 0];
}

/** Prepend an 8-byte big-endian microsecond timestamp (tlog record framing). */
function record(tUs: bigint, frame: number[]): number[] {
  const ts: number[] = [];
  for (let i = 7; i >= 0; i--) ts.push(Number((tUs >> BigInt(i * 8)) & 0xffn));
  return [...ts, ...frame];
}

function toBuffer(bytes: number[]): ArrayBuffer {
  return new Uint8Array(bytes).buffer;
}

describe('parseTlog', () => {
  it('parses a sequence of v2 records with timestamps and payloads', () => {
    const bytes = [
      ...record(2_000_000n, v2Frame(30, 1, 1, 0, [1, 2, 3, 4])), // ATTITUDE
      ...record(2_100_000n, v2Frame(74, 1, 1, 1, [5, 6])), // VFR_HUD
    ];
    const packets = parseTlog(toBuffer(bytes));
    expect(packets).toHaveLength(2);
    expect(packets[0]).toMatchObject({ msgid: 30, sysid: 1, compid: 1, t: 2000 });
    expect(packets[0]!.payload).toEqual([1, 2, 3, 4]);
    expect(packets[1]).toMatchObject({ msgid: 74, sysid: 1, compid: 1, t: 2100 });
  });

  it('parses v1 frames', () => {
    const bytes = record(5_000_000n, v1Frame(0, 1, 1, 0, [9, 9])); // HEARTBEAT
    const packets = parseTlog(toBuffer(bytes));
    expect(packets).toHaveLength(1);
    expect(packets[0]).toMatchObject({ msgid: 0, sysid: 1, compid: 1, t: 5000 });
    expect(packets[0]!.payload).toEqual([9, 9]);
  });

  it('handles a high (24-bit) msgid in v2', () => {
    const bytes = record(1_000_000n, v2Frame(245, 1, 1, 0, [2, 1])); // EXTENDED_SYS_STATE
    const packets = parseTlog(toBuffer(bytes));
    expect(packets[0]!.msgid).toBe(245);
  });

  it('returns an empty array for an empty buffer', () => {
    expect(parseTlog(new ArrayBuffer(0))).toEqual([]);
  });
});
