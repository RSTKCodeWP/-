/**
 * @module protocol/event-message.test
 * @description Unit tests for the MAVLink EVENT (msg 410) decoder and its
 * independently-derived CRC_EXTRA seed. The CRC is derived from the message
 * field signature (not read from the table) so a wrong table value — which
 * would silently drop every EVENT frame — fails the build.
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { decodeEvent } from "../messages/core";
import { crc16Accumulate, CRC_EXTRA, PAYLOAD_LENGTHS } from "../mavlink-parser";

describe("EVENT CRC_EXTRA + payload length", () => {
  it("derives CRC_EXTRA = 160 from the message signature (independent of the table)", () => {
    // MAVLink CRC_EXTRA: X.25 CRC over "NAME " then, per field in WIRE order
    // (fields sorted descending by base-type size; ties keep declared order),
    // "type " "name ", plus the array-length byte for array fields, folded to
    // 8 bits. EVENT has no <extensions/> block; wire order (from the generated
    // header) is the two uint32, the uint16, then the uint8 fields, arguments
    // last as uint8[40].
    const accStr = (s: string, crc: number) => {
      for (let i = 0; i < s.length; i++) crc = crc16Accumulate(s.charCodeAt(i), crc);
      return crc;
    };
    let crc = 0xffff;
    crc = accStr("EVENT ", crc);
    crc = accStr("uint32_t id ", crc);
    crc = accStr("uint32_t event_time_boot_ms ", crc);
    crc = accStr("uint16_t sequence ", crc);
    crc = accStr("uint8_t destination_component ", crc);
    crc = accStr("uint8_t destination_system ", crc);
    crc = accStr("uint8_t log_levels ", crc);
    crc = accStr("uint8_t arguments ", crc);
    crc = crc16Accumulate(40, crc); // arguments is uint8_t[40]
    const extra = (crc ^ (crc >> 8)) & 0xff;
    expect(extra).toBe(160);
    expect(CRC_EXTRA.get(410)).toBe(160);
  });

  it("registers the canonical payload length (53 bytes)", () => {
    expect(PAYLOAD_LENGTHS.get(410)).toBe(53);
  });
});

describe("decodeEvent", () => {
  function buildPayload(fields: {
    id: number;
    timeBootMs: number;
    sequence: number;
    destComp: number;
    destSys: number;
    logLevels: number;
    args: number[];
  }): DataView {
    const buf = new Uint8Array(53);
    const dv = new DataView(buf.buffer);
    dv.setUint32(0, fields.id, true);
    dv.setUint32(4, fields.timeBootMs, true);
    dv.setUint16(8, fields.sequence, true);
    dv.setUint8(10, fields.destComp);
    dv.setUint8(11, fields.destSys);
    dv.setUint8(12, fields.logLevels);
    buf.set(fields.args.slice(0, 40), 13);
    return dv;
  }

  it("round-trips every field including the 40-byte arguments array", () => {
    const args = Array.from({ length: 40 }, (_, i) => i & 0xff);
    const dv = buildPayload({
      id: 0x01000045, // component 1, sub-id 0x45
      timeBootMs: 987654,
      sequence: 4242,
      destComp: 190,
      destSys: 1,
      logLevels: 0x24, // internal=2, external=4 (warning)
      args,
    });
    const m = decodeEvent(dv);
    expect(m.id).toBe(0x01000045);
    expect(m.eventTimeBootMs).toBe(987654);
    expect(m.sequence).toBe(4242);
    expect(m.destinationComponent).toBe(190);
    expect(m.destinationSystem).toBe(1);
    expect(m.logLevels).toBe(0x24);
    expect(m.logLevels & 0x0f).toBe(4); // external nibble = display severity
    expect(Array.from(m.arguments)).toEqual(args);
  });

  it("returns a copy of the arguments, decoupled from the source buffer", () => {
    const dv = buildPayload({
      id: 1, timeBootMs: 0, sequence: 0, destComp: 0, destSys: 0, logLevels: 0,
      args: [7, 8, 9],
    });
    const m = decodeEvent(dv);
    // Mutating the source buffer must not change the decoded copy.
    new Uint8Array(dv.buffer)[13] = 99;
    expect(m.arguments[0]).toBe(7);
  });
});
